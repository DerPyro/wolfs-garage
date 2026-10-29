"""Frozen schema-5 to current schema-6 migration and backup compatibility."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest

from wolfs_garage.store import SCHEMA, Store


class Schema6MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_schema5(self, name="schema5.sqlite3"):
        path = self.root / name
        with closing(sqlite3.connect(path)) as db:
            db.executescript((Path(__file__).parent / "fixtures" / "schema5_fixture.txt")
                             .read_text(encoding="utf-8"))
        return path

    @staticmethod
    def table_rows(db, table, columns):
        selection = ",".join(f'"{column}"' for column in columns)
        return db.execute(f'SELECT {selection} FROM "{table}" ORDER BY rowid').fetchall()

    def test_schema5_backup_upgrade_defaults_preserves_measurements_links_history_and_sequences(self):
        path = self.make_schema5()
        backup = self.root / "before-schema6.sqlite3"
        old_columns = {
            "vehicles": ["id", "make", "model", "name", "year", "license_plate", "vehicle_type",
                         "unit", "revision", "inspection_due_month"],
            "states": ["vehicle_id", "readiness", "issues", "revision"],
            "odometer_readings": ["id", "vehicle_id", "day", "value", "unit", "note",
                                  "revision", "provenance", "source_record_id"],
            "records": ["id", "vehicle_id", "description", "kind", "day", "odometer", "unit",
                        "cost", "currency", "document_url", "closed_issue_id", "revision"],
            "commands": ["vehicle_id", "action", "command_id", "payload_hash", "response"],
            "history": ["sequence", "vehicle_id", "action", "occurred_at", "before_json", "after_json"],
        }
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(Store._validate_restore_backup(db), 5)
            rows_before = {table: self.table_rows(db, table, columns)
                           for table, columns in old_columns.items()}
            sequences_before = db.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name").fetchall()

        store = Store(path)
        with self.assertRaises(sqlite3.DatabaseError):
            store.list_vehicles()
        self.assertTrue(store.upgrade(backup))
        self.assertEqual(SCHEMA, 6)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone(), (6,))
            vehicle_columns = [row[1] for row in db.execute("PRAGMA table_info(vehicles)")]
            self.assertEqual(vehicle_columns[-2:], ["annual_usage", "reading_prompt_days"])
            self.assertEqual(db.execute("SELECT annual_usage,reading_prompt_days FROM vehicles WHERE id=7").fetchone(),
                             (None, 30))
            for table, columns in old_columns.items():
                self.assertEqual(self.table_rows(db, table, columns), rows_before[table], table)
            self.assertEqual(db.execute("SELECT name,seq FROM sqlite_sequence ORDER BY name").fetchall(),
                             sequences_before)
            self.assertEqual(db.execute("""SELECT id,revision,provenance,source_record_id
                FROM odometer_readings ORDER BY id""").fetchall(), [
                (17, 3, "legacy_unknown", None),
                (18, 4, "record", 11),
                (19, 2, "manual", None),
            ])
            self.assertEqual(db.execute("SELECT id,revision FROM records WHERE id=11").fetchone(), (11, 6))
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(Store._validate_restore_backup(db), 5)
            backup_columns = {row[1] for row in db.execute("PRAGMA table_info(vehicles)")}
            self.assertFalse({"annual_usage", "reading_prompt_days"} & backup_columns)
            self.assertEqual(db.execute("SELECT id,revision,provenance,source_record_id FROM odometer_readings ORDER BY id").fetchall(), [
                (17, 3, "legacy_unknown", None),
                (18, 4, "record", 11),
                (19, 2, "manual", None),
            ])
        replay_backup = self.root / "restored-schema5.sqlite3"
        store.restore_backup(backup, replay_backup)
        with closing(sqlite3.connect(replay_backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone(), (5,))
            self.assertEqual(db.execute("SELECT id,revision,provenance,source_record_id FROM odometer_readings ORDER BY id").fetchall(), [
                (17, 3, "legacy_unknown", None),
                (18, 4, "record", 11),
                (19, 2, "manual", None),
            ])

        no_backup = self.root / "no-op-must-not-exist.sqlite3"
        self.assertFalse(store.upgrade(no_backup))
        self.assertFalse(no_backup.exists())
        self.assertEqual(store.list_vehicles()[0]["readingPromptDays"], 30)

    def test_failed_schema6_upgrade_rolls_back_fields_and_keeps_checked_schema5_copy(self):
        path = self.make_schema5("rollback.sqlite3")
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TRIGGER reject_schema6 BEFORE UPDATE ON meta BEGIN SELECT RAISE(ABORT,'synthetic schema-6 failure'); END")
        backup = self.root / "rollback-before.sqlite3"
        with self.assertRaises(sqlite3.IntegrityError):
            Store(path).upgrade(backup)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone(), (5,))
            columns = {row[1] for row in db.execute("PRAGMA table_info(vehicles)")}
            self.assertFalse({"annual_usage", "reading_prompt_days"} & columns)
            self.assertEqual(db.execute("SELECT id,revision,provenance,source_record_id FROM odometer_readings ORDER BY id").fetchall(), [
                (17, 3, "legacy_unknown", None),
                (18, 4, "record", 11),
                (19, 2, "manual", None),
            ])
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(Store._validate_backup(db), 5)

    def test_frozen_schema5_fixture_has_strict_canonical_constraints_and_no_forecast_fields(self):
        path = self.make_schema5("validate-schema5.sqlite3")
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(Store._validate_restore_backup(db), 5)
            self.assertNotIn("annual_usage", {row[1] for row in db.execute("PRAGMA table_info(vehicles)")})
            self.assertNotIn("reading_prompt_days", {row[1] for row in db.execute("PRAGMA table_info(vehicles)")})


if __name__ == "__main__":
    unittest.main()
