"""Record correction and explicit schema upgrade behavior using synthetic data."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from wolfs_garage.store import Conflict, NotFound, Store, ValidationError


class RecordCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        self.store = Store(self.path)
        self.store.initialize()
        self.vehicle = self.store.create_vehicle({"make": "Synthetic", "model": "Car"})
        created = self.store.add_record(self.vehicle["id"], {
            "description": "Original service", "kind": "service", "date": "2026-01-10",
            "odometer": 1234, "cost": "20.00", "currency": "EUR",
            "documentUrl": "https://example.test/original", "commandId": str(uuid.uuid4())})
        self.record = created["record"]

    def correction(self, **changes):
        return {"revision": self.record["revision"], "commandId": str(uuid.uuid4()),
                "description": "Corrected service", "kind": "repair", "cost": "25.50",
                "currency": "EUR", "documentUrl": None,
                "correctionReason": "Invoice amount transcribed incorrectly\nVerified against synthetic receipt.", **changes}

    def test_corrects_allowed_fields_and_audits_reason_old_and_new(self):
        corrected = self.store.correct_record(self.vehicle["id"], self.record["id"], self.correction())["record"]
        self.assertEqual(corrected["revision"], 2)
        self.assertEqual((corrected["description"], corrected["kind"], corrected["cost"], corrected["currency"], corrected["documentUrl"]),
                         ("Corrected service", "repair", "25.50", "EUR", None))
        for key in ("date", "odometer", "odometerUnit", "closedIssueId"):
            self.assertEqual(corrected[key], self.record[key])
        event = self.store.list_history(self.vehicle["id"])[-1]
        self.assertEqual(event["action"], "record.corrected")
        self.assertEqual(event["before"], {"record": self.record})
        self.assertEqual(event["after"], {"record": corrected, "correctionReason": "Invoice amount transcribed incorrectly\nVerified against synthetic receipt."})

    def test_locked_fields_noop_and_bad_money_are_rejected(self):
        for locked in ("date", "odometer", "odometerPolicy", "odometerUnit", "closedIssueId", "vehicle"):
            payload = self.correction()
            payload[locked] = self.record.get(locked)
            with self.subTest(locked=locked), self.assertRaises(ValidationError):
                self.store.correct_record(self.vehicle["id"], self.record["id"], payload)
        unchanged = {"description": self.record["description"], "kind": self.record["kind"], "cost": self.record["cost"],
                     "currency": self.record["currency"], "documentUrl": self.record["documentUrl"]}
        with self.assertRaises(ValidationError):
            self.store.correct_record(self.vehicle["id"], self.record["id"], self.correction(**unchanged))
        for money in ({"cost": None, "currency": "EUR"}, {"cost": "1.001", "currency": "EUR"},
                      {"cost": "1.00", "currency": "eur"}):
            with self.subTest(money=money), self.assertRaises(ValidationError):
                self.store.correct_record(self.vehicle["id"], self.record["id"], self.correction(**money))
        self.assertEqual(self.store.get_record(self.vehicle["id"], self.record["id"]), self.record)

    def test_stale_revision_and_command_replay_rules(self):
        payload = self.correction()
        response = self.store.correct_record(self.vehicle["id"], self.record["id"], payload)
        self.assertEqual(self.store.correct_record(self.vehicle["id"], self.record["id"], payload), response)
        with self.assertRaises(Conflict):
            self.store.correct_record(self.vehicle["id"], self.record["id"], {**payload, "description": "Different payload"})
        with self.assertRaises(Conflict):
            self.store.correct_record(self.vehicle["id"], self.record["id"], self.correction(commandId=str(uuid.uuid4()), description="Third wording"))

    def test_same_command_id_is_scoped_to_each_record(self):
        second = self.store.add_record(self.vehicle["id"], {
            "description": "Original service", "kind": "service", "date": "2026-01-11",
            "commandId": str(uuid.uuid4())})["record"]
        payload = self.correction(commandId=str(uuid.uuid4()))
        first_result = self.store.correct_record(self.vehicle["id"], self.record["id"], payload)
        second_result = self.store.correct_record(self.vehicle["id"], second["id"], payload)
        self.assertEqual(first_result["record"]["id"], self.record["id"])
        self.assertEqual(second_result["record"]["id"], second["id"])
        self.assertEqual(self.store.get_record(self.vehicle["id"], second["id"])["revision"], 2)

    def test_stale_revision_wins_over_noop_check_and_invalid_kind_is_400_class(self):
        payload = self.correction()
        updated = self.store.correct_record(self.vehicle["id"], self.record["id"], payload)["record"]
        stale_noop = {**payload, "commandId": str(uuid.uuid4()), "revision": 1,
                      **{key: updated[key] for key in ("description", "kind", "cost", "currency", "documentUrl")}}
        with self.assertRaises(Conflict):
            self.store.correct_record(self.vehicle["id"], self.record["id"], stale_noop)
        with self.assertRaises(ValidationError):
            self.store.correct_record(self.vehicle["id"], self.record["id"], self.correction(kind=[]))

    def test_wrong_vehicle_and_record_are_not_found(self):
        other = self.store.create_vehicle({"make": "Other", "model": "Vehicle"})
        with self.assertRaises(NotFound):
            self.store.get_record(other["id"], self.record["id"])
        with self.assertRaises(NotFound):
            self.store.correct_record(other["id"], self.record["id"], self.correction())

    def test_audit_failure_rolls_back_record_and_command(self):
        payload = self.correction()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TRIGGER reject_correction_audit BEFORE INSERT ON history WHEN NEW.action='record.corrected' BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.correct_record(self.vehicle["id"], self.record["id"], payload)
        self.assertEqual(self.store.get_record(self.vehicle["id"], self.record["id"]), self.record)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM commands WHERE action LIKE 'record.correct:%'").fetchone()[0], 0)

    def test_parallel_corrections_have_one_winner(self):
        def correct(label):
            try:
                return Store(self.path).correct_record(self.vehicle["id"], self.record["id"],
                    self.correction(commandId=str(uuid.uuid4()), description=label))
            except Conflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(correct, ("First correction", "Second correction")))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.store.get_record(self.vehicle["id"], self.record["id"])["revision"], 2)


class SchemaUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / "schema1.sqlite3"
        fixture = Path(__file__).parent / "fixtures" / "schema1_fixture.txt"
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(fixture.read_text())
            with db:
                db.execute("INSERT INTO vehicles VALUES(7,'Synthetic','Car','Synthetic Car',2020,'','Car','km',1)")
                db.execute("INSERT INTO states VALUES(7,'unknown','[]',0)")
                db.execute("INSERT INTO records VALUES(11,7,'Legacy service','service','2025-04-05','1000','km','9.99','EUR',NULL,NULL)")
                self.legacy_response = '{"record":{"id":11,"description":"Legacy service"}}'
                db.execute("INSERT INTO commands VALUES(7,'record','legacy-id','legacy-hash',?)", (self.legacy_response,))
                db.execute("INSERT INTO history VALUES(13,7,'record.created','2025-04-05T00:00:00+00:00','null',?)", (self.legacy_response,))
        self.store = Store(self.path)

    def test_direct_backup_accepts_schema1_and_preserves_legacy_history_and_commands(self):
        backup = self.directory / "schema1-direct-backup.sqlite3"
        self.store.backup(backup)
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT id,description FROM records").fetchone(), (11, "Legacy service"))
            self.assertEqual(db.execute("SELECT action,command_id,response FROM commands").fetchone(), ("record", "legacy-id", self.legacy_response))
            self.assertEqual(db.execute("SELECT sequence,action,after_json FROM history").fetchone(), (13, "record.created", self.legacy_response))

    def test_upgrade_rejects_unsupported_version_without_backup_or_mutation(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE meta SET schema=99")
        destination = self.directory / "unsupported-backup.sqlite3"
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.upgrade(destination)
        self.assertFalse(destination.exists())
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 99)

    def test_upgrade_backups_then_preserves_data_and_old_idempotency_response(self):
        backup = self.directory / "before-upgrade.sqlite3"
        self.assertTrue(self.store.upgrade(backup))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 5)
            self.assertEqual(db.execute("SELECT id,description,revision FROM records").fetchone(), (11, "Legacy service", 1))
            self.assertEqual(db.execute("SELECT action,command_id,response FROM commands").fetchone(), ("record", "legacy-id", self.legacy_response))
            self.assertEqual(db.execute("SELECT sequence,action,after_json FROM history").fetchone(), (13, "record.created", self.legacy_response))
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT id,description FROM records").fetchone(), (11, "Legacy service"))
        # A repeated explicit request is a pure no-op and does not overwrite/create backup.
        self.assertFalse(self.store.upgrade(self.directory / "must-not-exist.sqlite3"))
        self.assertFalse((self.directory / "must-not-exist.sqlite3").exists())
        prior_backup = backup.read_bytes()
        self.assertFalse(self.store.upgrade(backup))
        self.assertEqual(backup.read_bytes(), prior_backup)

    def test_backup_failure_leaves_schema1_untouched(self):
        existing = self.directory / "already-there.sqlite3"
        existing.write_text("keep this file")
        with self.assertRaises(FileExistsError):
            self.store.upgrade(existing)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 1)
            self.assertNotIn("revision", [row[1] for row in db.execute("PRAGMA table_info(records)")])
        self.assertEqual(existing.read_text(), "keep this file")

    def test_meta_update_failure_rolls_back_upgrade_but_keeps_valid_backup(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TRIGGER reject_schema_upgrade BEFORE UPDATE ON meta BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        backup = self.directory / "backup-before-failed-upgrade.sqlite3"
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.upgrade(backup)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 1)
            self.assertNotIn("revision", [row[1] for row in db.execute("PRAGMA table_info(records)")])
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT id,description FROM records").fetchone(), (11, "Legacy service"))
            self.assertEqual(db.execute("SELECT action,command_id,response FROM commands").fetchone(), ("record", "legacy-id", self.legacy_response))
            self.assertEqual(db.execute("SELECT sequence,action,after_json FROM history").fetchone(), (13, "record.created", self.legacy_response))


if __name__ == "__main__":
    unittest.main()
