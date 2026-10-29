"""Frozen schema 1–4 upgrade acceptance for synthetic reading provenance data."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from wolfs_garage.store import SCHEMA, Store


FIXTURES = {1: "schema1_fixture.txt", 2: "schema2_fixture.txt",
            3: "schema3_fixture.txt", 4: "schema4_fixture.txt"}


class ReadingProvenanceUpgradeTests(unittest.TestCase):
    def make_legacy(self, directory, schema):
        path = Path(directory) / f"schema{schema}.sqlite3"
        fixture = Path(__file__).parent / "fixtures" / FIXTURES[schema]
        with closing(sqlite3.connect(path)) as db:
            db.executescript(fixture.read_text(encoding="utf-8"))
            with db:
                if schema == 1:
                    db.execute("INSERT INTO vehicles VALUES(7,'Synthetic','Legacy','Synthetic Legacy',2020,'','Car','km',1)")
                    db.execute("INSERT INTO states VALUES(7,'not_ready','[]',2)")
                    db.execute("INSERT INTO records VALUES(11,7,'Legacy service','service','2025-04-05','1234.125','km','9.99','EUR',NULL,NULL)")
                    db.execute("INSERT INTO commands VALUES(7,'record','legacy-command','legacy-hash','{\"record\":{\"id\":11,\"description\":\"Legacy service\"}}')")
                    db.execute("INSERT INTO history VALUES(13,7,'record.created','2025-04-05T00:00:00+00:00','null','{\"record\":{\"id\":11,\"description\":\"Legacy service\"}}')")
                # The matching text, date, value and unit are intentionally not
                # proof of a relation. Schema-4 data used only this note.
                if schema != 4:
                    db.execute("INSERT INTO odometer_readings VALUES(17,7,'2025-04-05','1234.125','km','Record 11')")
                if schema == 1:
                    db.execute("UPDATE records SET odometer='1234.125' WHERE id=11")
                else:
                    db.execute("UPDATE records SET odometer='1234.125' WHERE id=11")
        return path

    def assert_migrated_synthetic_data(self, path, original_schema):
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 5)
            columns = {row[1] for row in db.execute("PRAGMA table_info(odometer_readings)")}
            self.assertTrue({"revision", "provenance", "source_record_id"} <= columns)
            self.assertEqual(db.execute("SELECT id,vehicle_id,day,value,unit,note,revision,provenance,source_record_id FROM odometer_readings WHERE id=17").fetchone(),
                             (17, 7, "2025-04-05", "1234.125", "km", "Record 11", 1, "legacy_unknown", None))
            self.assertEqual(db.execute("SELECT id,vehicle_id,description,kind,day,odometer,unit FROM records WHERE id=11").fetchone(),
                             (11, 7, "Legacy service", "service", "2025-04-05", "1234.125", "km"))
            self.assertEqual(db.execute("SELECT sequence,action FROM history WHERE sequence=13").fetchone(), (13, "record.created"))
            self.assertEqual(db.execute("SELECT action,command_id,response FROM commands WHERE vehicle_id=7").fetchone(),
                             ("record", "legacy-command", '{"record":{"id":11,"description":"Legacy service"}}'))
            self.assertEqual(db.execute("SELECT inspection_due_month FROM vehicles WHERE id=7").fetchone()[0],
                             "2027-04" if original_schema == 4 else None)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_explicit_backup_upgrade_preserves_legacy_rows_and_never_guesses_links(self):
        with tempfile.TemporaryDirectory() as directory:
            for schema in range(1, 5):
                with self.subTest(schema=schema):
                    path = self.make_legacy(directory, schema)
                    before = path.read_bytes()
                    backup = Path(directory) / f"before-{schema}.sqlite3"
                    store = Store(path)
                    self.assertTrue(store.upgrade(backup))
                    self.assert_migrated_synthetic_data(path, schema)
                    with closing(sqlite3.connect(backup)) as db:
                        self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], schema)
                        self.assertEqual(db.execute("SELECT id,note FROM odometer_readings WHERE id=17").fetchone(),
                                         (17, "Record 11"))
                    self.assertFalse(store.upgrade(Path(directory) / f"unused-{schema}.sqlite3"))
                    self.assertFalse((Path(directory) / f"unused-{schema}.sqlite3").exists())
                    self.assertNotEqual(path.read_bytes(), before)

    def test_failed_schema5_migration_rolls_back_all_new_columns_and_keeps_checked_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_legacy(directory, 4)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("CREATE TRIGGER reject_schema5 BEFORE UPDATE ON meta BEGIN SELECT RAISE(ABORT,'synthetic schema-5 failure'); END")
            backup = Path(directory) / "pre-failed-upgrade.sqlite3"
            with self.assertRaises(sqlite3.IntegrityError):
                Store(path).upgrade(backup)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 4)
                cols = {row[1] for row in db.execute("PRAGMA table_info(odometer_readings)")}
                self.assertFalse({"revision", "provenance", "source_record_id"} & cols)
                self.assertEqual(db.execute("SELECT value,note FROM odometer_readings WHERE id=17").fetchone(),
                                 ("1234.125", "Record 11"))
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 4)

    def test_startup_refuses_schema4_until_explicit_upgrade_and_schema5_reupgrade_is_noop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_legacy(directory, 4)
            with self.assertRaises(sqlite3.DatabaseError):
                Store(path).list_vehicles()
            backup = Path(directory) / "pre-schema5.sqlite3"
            self.assertTrue(Store(path).upgrade(backup))
            self.assertEqual(Store(path).list_vehicles()[0]["id"], 7)
            self.assertEqual(SCHEMA, 5)
            second = Path(directory) / "must-not-exist.sqlite3"
            self.assertFalse(Store(path).upgrade(second))
            self.assertFalse(second.exists())

    def test_upgrade_preserves_sqlite_sequence_highwater_for_records_and_readings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make_legacy(directory, 4)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE sqlite_sequence SET seq=51 WHERE name='records'")
                db.execute("UPDATE sqlite_sequence SET seq=88 WHERE name='odometer_readings'")
            store = Store(path)
            self.assertTrue(store.upgrade(Path(directory) / "sequence-before.sqlite3"))
            created = store.add_record(7, {
                "description": "Synthetic post-upgrade work", "kind": "service",
                "date": "2026-10-01", "odometer": "1400.125",
                "commandId": str(uuid.uuid4()),
            })
            self.assertEqual(created["record"]["id"], 52)
            new_reading = next(row for row in store.list_odometer(7) if row["sourceRecordId"] == 52)
            self.assertEqual(new_reading["id"], 89)
            self.assertEqual((new_reading["odometerExact"], new_reading["provenance"]), ("1400.125", "record"))


if __name__ == "__main__":
    unittest.main()
