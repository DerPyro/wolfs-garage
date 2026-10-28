"""Synthetic standalone data lifecycle and transaction/restore checks."""
import os
from contextlib import closing
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from wolfs_garage.store import Conflict, NotFound, Store, ValidationError


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "garage.sqlite3"
        self.store = Store(self.path)
        self.store.initialize()
        self.vehicle = self.store.create_vehicle({"make": "Example", "model": "Car", "year": 2020, "odometerUnit": "km", "vehicleType": "Limousine"})
        self.id = self.vehicle["id"]

    def status(self, readiness="not_ready"):
        return self.store.update_status(self.id, {"readiness": readiness, "revision": 0, "issues": [{"text": "Synthetic repair"}, {"text": "Synthetic inspection"}]})

    def record(self, **extra):
        return {"description": "Synthetic repair performed", "kind": "repair", "date": "2026-02-28", "odometer": 1250, "cost": "12.30", "currency": "EUR", "documentUrl": "https://documents.example.test/invoice/one", "commandId": str(uuid.uuid4()), **extra}

    def test_explicit_initialization_refuses_existing_and_symlink(self):
        with self.assertRaises(FileExistsError):
            self.store.initialize()
        link = self.path.parent / "link.sqlite3"
        link.symlink_to(self.path)
        with self.assertRaises(FileExistsError):
            Store(link).initialize()
        if os.name == "posix":
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_missing_database_is_not_created_by_reads(self):
        missing = self.path.parent / "missing.sqlite3"
        with self.assertRaises(sqlite3.OperationalError):
            Store(missing).list_vehicles()
        self.assertFalse(missing.exists())

    def test_initial_state_is_unknown_and_metadata_correction_keeps_identity(self):
        self.assertEqual(self.vehicle["status"], {"readiness": "unknown", "issues": [], "revision": 0})
        status = self.status()
        updated = self.store.update_vehicle(self.id, {"make": "Corrected", "model": "Vehicle", "year": 2021, "revision": self.vehicle["revision"]})
        self.assertEqual(updated["id"], self.id)
        self.assertEqual(updated["name"], "Corrected Vehicle")
        self.assertEqual(updated["status"], status)
        self.assertEqual(Store(self.path).get_vehicle(self.id), updated)

    def test_stale_vehicle_and_status_revisions_do_not_overwrite(self):
        self.status()
        history = self.store.list_history(self.id)
        with self.assertRaises(Conflict):
            self.store.update_status(self.id, {"readiness": "ready", "issues": [], "revision": 0})
        self.store.update_vehicle(self.id, {"revision": 1, "model": "Changed"})
        with self.assertRaises(Conflict):
            self.store.update_vehicle(self.id, {"revision": 1, "model": "Stale"})
        self.assertEqual(self.store.get_vehicle(self.id)["model"], "Changed")
        self.assertEqual(len(self.store.list_history(self.id)), len(history) + 1)

    def test_status_rejects_foreign_or_duplicate_issue_ids(self):
        status = self.status()
        with self.assertRaises(ValidationError):
            self.store.update_status(self.id, {"readiness": "ready", "revision": 1, "issues": [{"id": uuid.uuid4().hex, "text": "Foreign"}]})
        with self.assertRaises(ValidationError):
            self.store.update_status(self.id, {"readiness": "ready", "revision": 1, "issues": [status["issues"][0], status["issues"][0]]})
        self.assertEqual(self.store.get_status(self.id), status)

    def test_completion_is_atomic_and_readiness_is_independent(self):
        before = self.status()
        issue = before["issues"][0]["id"]
        result = self.store.add_record(self.id, self.record(closeIssueId=issue, statusRevision=before["revision"]))
        self.assertEqual(result["record"]["closedIssueId"], issue)
        self.assertEqual(result["record"]["cost"], "12.30")
        self.assertEqual(result["status"]["readiness"], "not_ready")
        self.assertEqual(result["status"]["issues"], [before["issues"][1]])
        self.assertEqual(result["status"]["revision"], 2)
        self.assertEqual(self.store.get_vehicle(self.id)["odometer"], 1250)
        self.assertEqual(len(self.store.list_odometer(self.id)), 1)
        self.assertEqual([x["action"] for x in self.store.list_history(self.id)][-2:], ["issue.completed", "record.created"])

    def test_stale_completion_creates_no_record_or_odometer_or_audit(self):
        status = self.status()
        history = self.store.list_history(self.id)
        with self.assertRaises(Conflict):
            self.store.add_record(self.id, self.record(closeIssueId=status["issues"][0]["id"], statusRevision=0))
        self.assertEqual(self.store.get_summary(self.id)["services"], [])
        self.assertEqual(self.store.list_odometer(self.id), [])
        self.assertEqual(self.store.list_history(self.id), history)
        self.assertEqual(self.store.get_status(self.id), status)

    def test_database_failure_rolls_back_issue_close_and_entire_record(self):
        status = self.status()
        history = self.store.list_history(self.id)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TRIGGER reject_records BEFORE INSERT ON records BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.add_record(self.id, self.record(closeIssueId=status["issues"][0]["id"], statusRevision=1))
        self.assertEqual(self.store.get_status(self.id), status)
        self.assertEqual(self.store.list_history(self.id), history)
        self.assertEqual(self.store.get_summary(self.id)["services"], [])

    def test_record_command_replay_is_exact_even_after_status_changes(self):
        status = self.status()
        payload = self.record(closeIssueId=status["issues"][0]["id"], statusRevision=1)
        result = self.store.add_record(self.id, payload)
        self.store.update_status(self.id, {"revision": 2, "readiness": "ready", "issues": result["status"]["issues"]})
        history = self.store.list_history(self.id)
        self.assertEqual(Store(self.path).add_record(self.id, payload), result)
        self.assertEqual(len(self.store.get_summary(self.id)["services"]), 1)
        self.assertEqual(len(self.store.list_odometer(self.id)), 1)
        self.assertEqual(self.store.list_history(self.id), history)
        with self.assertRaises(Conflict):
            self.store.add_record(self.id, {**payload, "cost": "15.00"})

    def test_parallel_record_retry_commits_only_one_record(self):
        payload = self.record()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: Store(self.path).add_record(self.id, payload), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.store.get_summary(self.id)["services"]), 1)
        self.assertEqual(len(self.store.list_odometer(self.id)), 1)
        self.assertEqual([x["action"] for x in self.store.list_history(self.id)].count("record.created"), 1)

    def test_parallel_status_edit_has_one_winner(self):
        def update(readiness):
            try:
                return Store(self.path).update_status(self.id, {"readiness": readiness, "issues": [], "revision": 0})
            except Conflict:
                return "conflict"
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(update, ["ready", "not_ready"]))
        self.assertEqual(results.count("conflict"), 1)
        self.assertEqual(self.store.get_status(self.id)["revision"], 1)

    def test_odometer_history_date_order_idempotency_and_unit_guard(self):
        payload = {"date": "2026-03-01", "odometer": 2000, "unit": "km", "commandId": uuid.uuid4().hex}
        result = self.store.add_odometer(self.id, payload)
        self.assertEqual(self.store.add_odometer(self.id, payload), result)
        self.store.add_odometer(self.id, {"date": "2025-01-01", "odometer": 1000, "unit": "km", "commandId": uuid.uuid4().hex})
        self.assertEqual(self.store.get_vehicle(self.id)["odometer"], 2000)
        self.assertEqual(len(self.store.list_odometer(self.id)), 2)
        with self.assertRaises(Conflict):
            self.store.add_odometer(self.id, {**payload, "unit": "mi", "commandId": uuid.uuid4().hex})
        with self.assertRaises(Conflict):
            self.store.update_vehicle(self.id, {"revision": 1, "odometerUnit": "mi"})
        with self.assertRaises(Conflict):
            self.store.add_odometer(self.id, {**payload, "odometer": 3000})

    def test_invalid_values_do_not_create_records(self):
        invalid = [{"cost": 1.2}, {"cost": "1.001"}, {"cost": "NaN"}, {"cost": "-1"}, {"currency": "eur"}, {"documentUrl": "javascript:alert(1)"}, {"documentUrl": "https://user:password@example.test/file"}, {"documentUrl": "https://example.test/has space"}, {"date": "2026-02-30"}, {"date": "20260228"}, {"odometer": True}, {"kind": []}, {"unexpected": "field"}]
        for extra in invalid:
            with self.subTest(extra=extra), self.assertRaises(ValidationError):
                self.store.add_record(self.id, self.record(**extra))
        self.assertEqual(self.store.get_summary(self.id)["services"], [])

    def test_vehicle_and_status_strict_validation(self):
        for payload in [{"make": "", "model": "Car"}, {"make": "A", "model": "B", "year": True}, {"make": "A", "model": "B", "odometerUnit": []}, {"make": "A", "model": "B", "provider": "unexpected"}]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                self.store.create_vehicle(payload)
        with self.assertRaises(ValidationError):
            self.store.update_status(self.id, {"revision": True, "readiness": "ready", "issues": []})
        self.assertEqual(len(self.store.list_vehicles()), 1)

    def test_backup_restore_preserves_records_ids_history_and_command_replay(self):
        status = self.status()
        payload = self.record(closeIssueId=status["issues"][0]["id"], statusRevision=1)
        response = self.store.add_record(self.id, payload)
        backup = self.path.parent / "backup.sqlite3"
        self.store.backup(backup)
        with self.assertRaises(FileExistsError):
            self.store.backup(backup)
        restored_path = self.path.parent / "restored.sqlite3"
        shutil.copyfile(backup, restored_path)
        restored = Store(restored_path)
        self.assertEqual(restored.list_vehicles(), self.store.list_vehicles())
        self.assertEqual(restored.get_summary(self.id), self.store.get_summary(self.id))
        self.assertEqual(restored.list_history(self.id), self.store.list_history(self.id))
        self.assertEqual(restored.list_odometer(self.id), self.store.list_odometer(self.id))
        self.assertEqual(restored.add_record(self.id, payload), response)
        self.assertEqual(len(restored.get_summary(self.id)["services"]), 1)

    def test_history_trigger_blocks_normal_updates_and_deletes(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE history SET action='changed'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM history")

    def test_unknown_vehicle_and_unsupported_schema_fail_closed(self):
        with self.assertRaises(NotFound):
            self.store.get_summary(999999)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE meta SET schema=99")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.list_vehicles()

    def test_corrupt_status_is_not_rendered_as_ready(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE states SET readiness='corrupt'")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.get_vehicle(self.id)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("DELETE FROM states")
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.get_status(self.id)


if __name__ == "__main__":
    unittest.main()
