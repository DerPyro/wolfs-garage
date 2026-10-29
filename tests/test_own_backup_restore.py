"""Failure and concurrency checks for full SQLite backup/restore."""
from contextlib import closing
from pathlib import Path
import hashlib
import sqlite3
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

from wolfs_garage.store import Store


FIXTURES = Path(__file__).parent / "fixtures"


class BackupRestoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.live = self.root / "live.sqlite3"
        self.store = Store(self.live)
        self.store.initialize()
        self.vehicle = self.store.create_vehicle({
            "make": "Synthetic", "model": "Restore", "odometerUnit": "km",
        })

    def record_payload(self, description, *, close_issue=None, status_revision=None):
        payload = {
            "description": description, "kind": "repair", "date": "2026-10-28",
            "odometer": 1234, "cost": "10.50", "currency": "EUR",
            "commandId": str(uuid.uuid4()),
        }
        if close_issue is not None:
            payload.update(closeIssueId=close_issue, statusRevision=status_revision)
        return payload

    def test_failed_target_validation_removes_partial_restore_only(self):
        status = self.store.update_status(self.vehicle["id"], {
            "readiness": "not_ready", "issues": [{"text": "Synthetic open issue"}], "revision": 0,
        })
        self.store.add_record(self.vehicle["id"], self.record_payload("Existing live work"))
        source = self.root / "source-backup.sqlite3"
        self.store.backup(source)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        destination = self.root / "partial-restore.sqlite3"
        before = {
            "vehicles": self.store.list_vehicles(),
            "status": self.store.get_status(self.vehicle["id"]),
            "summary": self.store.get_summary(self.vehicle["id"]),
            "history": self.store.list_history(self.vehicle["id"]),
            "readings": self.store.list_odometer(self.vehicle["id"]),
        }
        self.assertEqual(before["status"], status)
        validate = Store._validate_restore_backup
        calls = 0

        def reject_after_copy(db):
            nonlocal calls
            calls += 1
            schema = validate(db)
            if calls == 2:
                raise sqlite3.DatabaseError("synthetic post-copy verification failure")
            return schema

        with patch.object(Store, "_validate_restore_backup", side_effect=reject_after_copy):
            with self.assertRaisesRegex(sqlite3.DatabaseError, "post-copy"):
                self.store.restore_backup(source, destination)

        self.assertEqual(calls, 2)
        self.assertFalse(destination.exists())
        for suffix in ("-wal", "-shm", "-journal"):
            self.assertFalse(Path(str(destination) + suffix).exists())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
        self.assertEqual(self.store.list_vehicles(), before["vehicles"])
        self.assertEqual(self.store.get_status(self.vehicle["id"]), before["status"])
        self.assertEqual(self.store.get_summary(self.vehicle["id"]), before["summary"])
        self.assertEqual(self.store.list_history(self.vehicle["id"]), before["history"])
        self.assertEqual(self.store.list_odometer(self.vehicle["id"]), before["readings"])

    def test_online_backup_is_one_consistent_snapshot_during_atomic_writer_commit(self):
        with closing(sqlite3.connect(self.live)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
        status = self.store.update_status(self.vehicle["id"], {
            "readiness": "not_ready", "issues": [{"text": "Concurrent work"}], "revision": 0,
        })
        baseline_payload = self.record_payload("Baseline work")
        baseline = self.store.add_record(self.vehicle["id"], baseline_payload)
        baseline_status = self.store.get_status(self.vehicle["id"])
        baseline_summary = self.store.get_summary(self.vehicle["id"])
        baseline_readings = self.store.list_odometer(self.vehicle["id"])
        baseline_history = self.store.list_history(self.vehicle["id"])
        backup = self.root / "concurrent-snapshot.sqlite3"
        pinned = threading.Event()
        writer_done = threading.Event()
        writer_result = []
        writer_error = []
        original_backup = Store._new_backup

        def concurrent_writer():
            if not pinned.wait(5):
                writer_error.append(TimeoutError("backup snapshot was not pinned"))
                return
            try:
                writer_result.append(Store(self.live).add_record(
                    self.vehicle["id"], self.record_payload(
                        "Concurrent completion", close_issue=status["issues"][0]["id"],
                        status_revision=status["revision"],
                    ),
                ))
            except BaseException as exc:
                writer_error.append(exc)
            finally:
                writer_done.set()

        def pin_snapshot_then_copy(source, destination):
            source.execute("BEGIN")
            self.assertEqual(source.execute("SELECT count(*) FROM records").fetchone()[0], 1)
            pinned.set()
            self.assertTrue(writer_done.wait(5), "concurrent SQLite writer did not commit")
            return original_backup(source, destination)

        writer = threading.Thread(target=concurrent_writer)
        writer.start()
        try:
            with patch.object(Store, "_new_backup", side_effect=pin_snapshot_then_copy):
                self.store.backup(backup)
        finally:
            writer.join(timeout=5)
        self.assertFalse(writer.is_alive())
        self.assertEqual(writer_error, [])
        self.assertEqual(len(writer_result), 1)
        self.assertEqual(writer_result[0]["record"]["closedIssueId"], status["issues"][0]["id"])

        restored_path = self.root / "restored-snapshot.sqlite3"
        self.store.restore_backup(backup, restored_path)
        restored = Store(restored_path)
        self.assertEqual(restored.get_status(self.vehicle["id"]), baseline_status)
        self.assertEqual(restored.get_summary(self.vehicle["id"]), baseline_summary)
        self.assertEqual(restored.list_odometer(self.vehicle["id"]), baseline_readings)
        self.assertEqual(restored.list_history(self.vehicle["id"]), baseline_history)
        self.assertEqual(restored.add_record(self.vehicle["id"], baseline_payload), baseline)
        with closing(sqlite3.connect(restored_path)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            counts = {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                      for table in ("records", "odometer_readings", "commands", "history")}
            self.assertEqual(counts, {"records": 1, "odometer_readings": 1,
                                      "commands": 1, "history": 3})
            self.assertEqual(db.execute("SELECT count(*) FROM states WHERE vehicle_id=?", (self.vehicle["id"],)).fetchone()[0], 1)
        self.assertEqual(self.store.get_summary(self.vehicle["id"])["services"],
                         [writer_result[0]["record"], baseline["record"]])
        self.assertEqual(len(self.store.get_summary(self.vehicle["id"])["services"]), 2)
        self.assertEqual(len(self.store.list_odometer(self.vehicle["id"])), 2)
        self.assertEqual(len(self.store.list_history(self.vehicle["id"])), 5)

    def test_schema1_to_3_restore_keeps_original_schema_without_migration(self):
        for schema in (1, 2, 3):
            with self.subTest(schema=schema):
                source = self.root / f"schema-{schema}.sqlite3"
                destination = self.root / f"schema-{schema}-restored.sqlite3"
                with closing(sqlite3.connect(source)) as db:
                    db.executescript((FIXTURES / f"schema{schema}_fixture.txt").read_text())
                Store(source).restore_backup(source, destination)
                with closing(sqlite3.connect(destination)) as db:
                    self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], schema)
                    self.assertEqual(db.execute("PRAGMA integrity_check").fetchall(), [("ok",)])


if __name__ == "__main__":
    unittest.main()
