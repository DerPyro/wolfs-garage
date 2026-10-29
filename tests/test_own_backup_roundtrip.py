"""Synthetic API/CLI checks for complete SQLite backup and create-only restore."""
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest import mock
from werkzeug.http import parse_options_header
from werkzeug.test import EnvironBuilder

from wolfs_garage.api import create_app
from wolfs_garage.store import Store


class BackupRoundtripTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db_path = self.root / "source.sqlite3"
        self.store = Store(self.db_path)
        self.store.initialize()
        temp_root = self.root / "http-temp"
        temp_root.mkdir()
        self.app = create_app({"TESTING": True, "GARAGE_DB": str(self.db_path),
                               "GARAGE_PUBLIC_ORIGIN": "https://garage.test",
                               "GARAGE_BACKUP_TEMP_DIR": str(temp_root)})
        self.client = self.app.test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def get(self, path, base_url="https://garage.test"):
        return self.client.get(path, base_url=base_url)

    def synthetic_data(self):
        vehicle = self.store.create_vehicle({"make": "Synthetic", "model": "Backup", "odometerUnit": "km"})
        status = self.store.update_status(vehicle["id"], {
            "revision": 0, "readiness": "not_ready", "issues": [{"text": "Synthetic issue"}],
        })
        issue_id = status["issues"][0]["id"]
        payload = {
            "description": "Synthetic completed work", "kind": "repair", "date": "2026-10-20",
            "odometer": 1234.125, "cost": "42.50", "currency": "EUR",
            "documentUrl": "https://documents.example.test/synthetic/receipt",
            "closeIssueId": issue_id, "statusRevision": status["revision"], "commandId": str(uuid.uuid4()),
        }
        record = self.store.add_record(vehicle["id"], payload)
        reading_payload = {"date": "2026-10-21", "odometer": 1235.875, "unit": "km",
                           "note": "Synthetic fractional reading", "commandId": str(uuid.uuid4())}
        reading = self.store.add_odometer(vehicle["id"], reading_payload)
        # Include replayable commands and a historical audit event in the snapshot.
        return vehicle, record, payload, reading, reading_payload

    def counts(self, path):
        with closing(sqlite3.connect(path)) as db:
            return {name: db.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                    for name in ("vehicles", "states", "odometer_readings", "records", "history", "commands")}

    def table_snapshot(self, path):
        with closing(sqlite3.connect(path)) as db:
            names = [row[0] for row in db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            return {name: db.execute(f'SELECT * FROM "{name}" ORDER BY rowid').fetchall() for name in names}

    def cli(self, *args):
        env = {**os.environ, "GARAGE_DB": str(self.db_path)}
        return subprocess.run([sys.executable, "-m", "wolfs_garage", *map(str, args)],
                              cwd=Path(__file__).resolve().parents[1], env=env,
                              text=True, capture_output=True, check=False)

    def test_api_snapshot_is_a_complete_checked_sqlite_file_and_query_is_rejected(self):
        vehicle, record, record_payload, reading, reading_payload = self.synthetic_data()
        before_counts = self.counts(self.db_path)
        before_hash = hashlib.sha256(self.db_path.read_bytes()).hexdigest()

        response = self.get("/garage-api/backup")
        self.addCleanup(response.close)
        self.assertEqual(response.status_code, 200)
        self.assertIn("databaseBackup", self.get("/garage-api/capabilities").json["features"])
        self.assertEqual(parse_options_header(response.headers["Content-Disposition"]),
                         ("attachment", {"filename": "wolfs-garage-backup.sqlite3"}))
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn(response.mimetype, ("application/vnd.sqlite3", "application/octet-stream"))
        backup_path = self.root / "http-download.sqlite3"
        backup_path.write_bytes(response.data)
        self.assertGreater(backup_path.stat().st_size, 0)
        with closing(sqlite3.connect(backup_path)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 6)
            self.assertEqual(db.execute("SELECT count(*) FROM commands").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT cost FROM records WHERE id=?", (record["record"]["id"],)).fetchone()[0], "42.50")
            self.assertEqual(db.execute("SELECT value FROM odometer_readings WHERE id=?", (reading["id"],)).fetchone()[0], "1235.875")
        self.assertEqual(before_counts, self.counts(self.db_path))
        self.assertEqual(before_hash, hashlib.sha256(self.db_path.read_bytes()).hexdigest())
        self.assertEqual(self.get("/garage-api/vehicles").json["vehicles"][0]["id"], vehicle["id"])
        self.assertEqual(self.get("/garage-api/backup?x=1").status_code, 400)
        self.assertEqual(self.get("/garage-api/backup?x=").status_code, 400)
        self.assertEqual(self.get("/garage-api/backup?x=1&x=2").status_code, 400)
        self.assertEqual(self.get("/garage-api/backup", base_url="https://elsewhere.test").status_code, 400)
        response.close()
        self.assertEqual(list((self.root / "http-temp").iterdir()), [], "download snapshot leaked")

    def test_wsgi_download_iterator_close_removes_private_snapshot(self):
        self.synthetic_data()
        environ = EnvironBuilder(method="GET", path="/garage-api/backup",
                                 base_url="https://garage.test").get_environ()
        response_status = {}

        def start_response(status, headers, exc_info=None):
            response_status["status"] = status
            response_status["headers"] = headers

        iterable = self.app.wsgi_app(environ, start_response)
        self.addCleanup(iterable.close)
        body = b"".join(iterable)
        self.assertTrue(response_status["status"].startswith("200"))
        self.assertTrue(list((self.root / "http-temp").iterdir()),
                        "snapshot should remain available until the WSGI iterable closes")
        database_copy = self.root / "wsgi-download.sqlite3"
        database_copy.write_bytes(body)
        with closing(sqlite3.connect(database_copy)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        iterable.close()
        self.assertEqual(list((self.root / "http-temp").iterdir()), [], "WSGI close leaked snapshot")

    def test_api_backup_failure_cleans_temporary_snapshot(self):
        # Track the route's private temporary directory without depending on its
        # implementation location or leaving test artifacts in the repository.
        import tempfile as tempfile_module
        original_tempdir = tempfile_module.TemporaryDirectory
        seen = []

        class TrackingTemporaryDirectory(original_tempdir):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                seen.append(Path(self.name))

        store = self.app.extensions["garage_store"]
        with mock.patch.object(tempfile_module, "TemporaryDirectory", TrackingTemporaryDirectory), \
             mock.patch.object(store, "backup", side_effect=sqlite3.OperationalError("synthetic read failure")):
            response = self.get("/garage-api/backup")
        self.assertEqual(response.status_code, 503)
        self.assertTrue(seen, "route did not use a private temporary directory")
        self.assertTrue(all(not path.exists() for path in seen), "temporary backup directory leaked")

    def test_cli_restores_snapshot_into_new_database_without_mutating_source(self):
        vehicle, expected_record, record_payload, expected_reading, reading_payload = self.synthetic_data()
        backup = self.root / "saved.sqlite3"
        original_tables = self.table_snapshot(self.db_path)
        self.store.backup(backup)
        source_hash = hashlib.sha256(backup.read_bytes()).hexdigest()
        destination = self.root / "restored.sqlite3"
        result = self.cli("restore-backup", backup, destination)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(destination.is_file())
        if os.name == "posix":
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        restored = Store(destination)
        self.assertEqual(restored.list_vehicles(), self.store.list_vehicles())
        self.assertEqual(restored.get_summary(vehicle["id"]), self.store.get_summary(vehicle["id"]))
        self.assertEqual(restored.list_history(vehicle["id"]), self.store.list_history(vehicle["id"]))
        self.assertEqual(restored.list_odometer(vehicle["id"]), self.store.list_odometer(vehicle["id"]))
        self.assertEqual(restored.add_record(vehicle["id"], record_payload), expected_record)
        self.assertEqual(restored.add_odometer(vehicle["id"], reading_payload), expected_reading)
        self.assertEqual(self.table_snapshot(destination), original_tables)
        self.assertEqual(self.table_snapshot(self.db_path), original_tables)
        self.assertEqual(hashlib.sha256(backup.read_bytes()).hexdigest(), source_hash)
        with closing(sqlite3.connect(destination)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("SELECT count(*) FROM commands").fetchone()[0], 2)
        self.assertEqual(self.counts(self.db_path), self.counts(destination))

    def test_cli_restore_refuses_existing_symlink_source_and_corrupt_or_unsupported_input(self):
        self.synthetic_data()
        backup = self.root / "valid.sqlite3"
        self.store.backup(backup)
        existing = self.root / "existing.sqlite3"
        existing.write_bytes(b"keep existing bytes")
        result = self.cli("restore-backup", backup, existing)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(existing.read_bytes(), b"keep existing bytes")

        link = self.root / "link.sqlite3"
        link.symlink_to(backup)
        result = self.cli("restore-backup", backup, link)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(link.is_symlink())

        result = self.cli("restore-backup", backup, backup)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(backup.is_file())

        corrupt = self.root / "corrupt.sqlite3"
        corrupt.write_bytes(b"not a sqlite database")
        corrupt_target = self.root / "corrupt-target.sqlite3"
        result = self.cli("restore-backup", corrupt, corrupt_target)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(corrupt_target.exists())

        unsupported = self.root / "unsupported.sqlite3"
        shutil_copy = self.root / "unsupported-copy.sqlite3"
        shutil_copy.write_bytes(backup.read_bytes())
        with closing(sqlite3.connect(shutil_copy)) as db, db:
            db.execute("UPDATE meta SET schema=99")
        unsupported.write_bytes(shutil_copy.read_bytes())
        unsupported_target = self.root / "unsupported-target.sqlite3"
        result = self.cli("restore-backup", unsupported, unsupported_target)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(unsupported_target.exists())

        malformed = self.root / "missing-table.sqlite3"
        malformed.write_bytes(backup.read_bytes())
        with closing(sqlite3.connect(malformed)) as db, db:
            db.execute("DROP TABLE history")
        malformed_target = self.root / "missing-table-target.sqlite3"
        result = self.cli("restore-backup", malformed, malformed_target)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(malformed_target.exists())

    def test_restore_never_overwrites_the_configured_live_database(self):
        self.synthetic_data()
        live_bytes = self.db_path.read_bytes()
        independent_source = self.root / "independent.sqlite3"
        self.store.backup(independent_source)
        result = self.cli("restore-backup", independent_source, self.db_path)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.db_path.read_bytes(), live_bytes)

    def test_cli_restores_frozen_legacy_schema1_2_3_without_upgrade_or_source_mutation(self):
        fixture_dir = Path(__file__).parent / "fixtures"
        for schema in (1, 2, 3):
            with self.subTest(schema=schema):
                source = self.root / f"legacy-schema{schema}.sqlite3"
                with closing(sqlite3.connect(source)) as db:
                    db.executescript((fixture_dir / f"schema{schema}_fixture.txt").read_text())
                original = self.table_snapshot(source)
                source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
                destination = self.root / f"restored-schema{schema}.sqlite3"
                result = self.cli("restore-backup", source, destination)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.table_snapshot(destination), original)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), source_hash)
                with closing(sqlite3.connect(destination)) as db:
                    self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], schema)


if __name__ == "__main__":
    unittest.main()
