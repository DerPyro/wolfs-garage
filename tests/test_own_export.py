"""Synthetic owner-export API, SQLite snapshot, and safe-file checks."""
from contextlib import closing
from datetime import datetime
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

from wolfs_garage import __version__ as APPLICATION_VERSION
from wolfs_garage.api import create_app
from wolfs_garage.store import Store


class OwnerExportApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        self.store = Store(self.path)
        self.store.initialize()
        self.app_config = {"TESTING": True, "GARAGE_DB": str(self.path),
                           "GARAGE_PUBLIC_ORIGIN": "https://garage.test"}
        self.app = create_app(self.app_config)
        self.client = self.app.test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def send(self, method, path, data=None, headers=None, base_url="https://garage.test"):
        return self.client.open(path, method=method, base_url=base_url, json=data,
                                headers=self.headers if headers is None else headers)

    def vehicle(self, make, model, unit="km"):
        response = self.send("POST", "/garage-api/vehicles", {
            "make": make, "model": model, "odometerUnit": unit,
        })
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def status(self, vehicle_id, issues, readiness="unknown", revision=0):
        return self.send("PUT", f"/garage-api/vehicles/{vehicle_id}/status", {
            "readiness": readiness, "issues": issues, "revision": revision,
        })

    def fixture(self):
        first = self.vehicle("Synthetic A", "Export One", "km")
        second = self.vehicle("Synthetic B", "Export Two", "mi")
        initial = self.status(first["id"], [
            {"text": "Close after repair", "dueDate": "2026-10-20", "severity": "critical"},
            {"text": "Keep open", "dueDate": "2026-11-30", "severity": "observation", "lifecycle": "observed"},
        ], readiness="not_ready")
        self.assertEqual(initial.status_code, 200, initial.json)
        close_issue, kept_issue = initial.json["issues"]
        created = self.send("POST", f"/garage-api/vehicles/{first['id']}/records", {
            "description": "Synthetic completed repair", "kind": "repair", "date": "2026-10-25",
            "odometer": 12345.125, "cost": "14.50", "currency": "EUR",
            "documentUrl": "https://documents.example.test/synthetic/receipt",
            "closeIssueId": close_issue["id"], "statusRevision": initial.json["revision"],
            "commandId": str(uuid.uuid4()),
        })
        self.assertEqual(created.status_code, 201, created.json)
        record = created.json["record"]
        corrected = self.send("PUT", f"/garage-api/vehicles/{first['id']}/records/{record['id']}", {
            "revision": record["revision"], "commandId": str(uuid.uuid4()),
            "description": "Synthetic repair corrected", "kind": "service", "cost": "14.75",
            "currency": "EUR", "documentUrl": "https://documents.example.test/synthetic/updated",
            "correctionReason": "Synthetic receipt rechecked.",
        })
        self.assertEqual(corrected.status_code, 200, corrected.json)

        for vehicle, reading in ((first, 12345.875), (second, 9876.125)):
            response = self.send("POST", f"/garage-api/vehicles/{vehicle['id']}/odometer", {
                "date": "2026-10-27", "odometer": reading,
                "unit": vehicle["odometerUnit"], "note": "Synthetic fractional reading",
                "commandId": str(uuid.uuid4()),
            })
            self.assertEqual(response.status_code, 201, response.json)

        # Preserve a representative pre-existing audit snapshot whose odometer
        # values were decoded as JSON numbers in older history rows.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT INTO history(vehicle_id,action,occurred_at,before_json,after_json) VALUES(?,?,?,?,?)", (
                first["id"], "legacy.snapshot", "2025-01-01T00:00:00+00:00",
                '{"record":{"odometer":12345}}', '{"record":{"odometer":12345.125}}',
            ))
        return first, second, kept_issue, corrected.json["record"]

    def counts(self):
        tables = ("vehicles", "states", "odometer_readings", "records", "history", "commands")
        with closing(sqlite3.connect(self.path)) as db:
            return {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                    for table in tables}

    def test_api_export_format_all_business_rows_types_order_and_no_internal_commands(self):
        first, second, kept_issue, corrected = self.fixture()
        before_counts = self.counts()
        before_history = {vehicle_id: self.send("GET", f"/garage-api/vehicles/{vehicle_id}/history").json
                          for vehicle_id in (first["id"], second["id"])}

        response = self.send("GET", "/garage-api/export")
        self.assertEqual(response.status_code, 200)
        self.assertIn("dataExport", self.send("GET", "/garage-api/capabilities").json["features"])
        self.assertEqual(response.headers["Content-Disposition"],
                         'attachment; filename="wolfs-garage-export.json"')
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        exported = json.loads(response.data)
        self.assertEqual(exported["format"], "wolfs-garage-owner-export")
        self.assertEqual(exported["formatVersion"], 1)
        self.assertEqual(exported["applicationVersion"], APPLICATION_VERSION)
        self.assertEqual(exported["databaseSchema"], 3)
        timestamp = datetime.fromisoformat(exported["exportedAt"].replace("Z", "+00:00"))
        self.assertIsNotNone(timestamp.utcoffset())
        self.assertEqual(timestamp.utcoffset().total_seconds(), 0)
        self.assertEqual(set(exported), {"format", "formatVersion", "applicationVersion", "databaseSchema",
                                         "exportedAt", "vehicles", "statuses", "odometerReadings", "records", "history"})

        self.assertEqual([row["id"] for row in exported["vehicles"]],
                         sorted(row["id"] for row in exported["vehicles"]))
        self.assertEqual([row["vehicleId"] for row in exported["statuses"]],
                         sorted(row["vehicleId"] for row in exported["statuses"]))
        self.assertEqual([row["id"] for row in exported["odometerReadings"]],
                         sorted(row["id"] for row in exported["odometerReadings"]))
        self.assertEqual([row["id"] for row in exported["records"]],
                         sorted(row["id"] for row in exported["records"]))
        self.assertEqual([row["sequence"] for row in exported["history"]],
                         sorted(row["sequence"] for row in exported["history"]))

        vehicle_keys = {"id", "make", "model", "name", "year", "licensePlate", "vehicleType", "odometerUnit", "revision"}
        self.assertEqual(set(exported["vehicles"][0]), vehicle_keys)
        self.assertFalse({"currentReading", "odometer", "status", "summary"} & set(exported["vehicles"][0]))
        self.assertTrue(all(set(row) == {"vehicleId", "readiness", "issues", "revision"}
                            for row in exported["statuses"]))
        self.assertTrue(all(set(row) == {"id", "vehicleId", "date", "odometer", "unit", "note"}
                            for row in exported["odometerReadings"]))
        status_by_id = {row["vehicleId"]: row for row in exported["statuses"]}
        self.assertEqual(status_by_id[first["id"]]["readiness"], "not_ready")
        self.assertEqual(status_by_id[first["id"]]["issues"], [kept_issue])
        self.assertEqual(status_by_id[second["id"]]["issues"], [])

        first_readings = [row for row in exported["odometerReadings"] if row["vehicleId"] == first["id"]]
        self.assertEqual([row["odometer"] for row in first_readings], ["12345.125", "12345.875"])
        record = next(row for row in exported["records"] if row["vehicleId"] == first["id"])
        self.assertEqual(set(record), {"id", "vehicleId", "description", "kind", "date", "odometer",
                                       "odometerUnit", "cost", "currency", "documentUrl", "closedIssueId", "revision"})
        expected_record = {**corrected, "odometer": "12345.125"}
        self.assertEqual(record, {"vehicleId": first["id"], **expected_record})
        self.assertEqual(record["odometer"], "12345.125")
        self.assertEqual(record["cost"], "14.75")
        self.assertEqual(record["documentUrl"], "https://documents.example.test/synthetic/updated")

        legacy = next(row for row in exported["history"] if row["action"] == "legacy.snapshot")
        self.assertEqual(set(legacy), {"sequence", "vehicleId", "action", "occurredAt", "before", "after"})
        self.assertTrue(all(set(event) == {"sequence", "vehicleId", "action", "occurredAt", "before", "after"}
                            for event in exported["history"]))
        self.assertEqual(legacy["before"]["record"]["odometer"], 12345)
        self.assertIs(type(legacy["before"]["record"]["odometer"]), int)
        self.assertEqual(legacy["after"]["record"]["odometer"], 12345.125)
        self.assertIs(type(legacy["after"]["record"]["odometer"]), float)
        self.assertTrue(any(event["action"] == "record.corrected" for event in exported["history"]))
        self.assertTrue(any(event["action"] == "issue.completed" for event in exported["history"]))
        self.assertNotIn("commands", exported)
        self.assertNotIn("commandId", response.data.decode("utf-8"))
        self.assertNotIn("GARAGE_DB", response.data.decode("utf-8"))
        self.assertNotIn("receipt bytes", response.data.decode("utf-8"))

        self.assertEqual(self.counts(), before_counts)
        self.assertEqual({vehicle_id: self.send("GET", f"/garage-api/vehicles/{vehicle_id}/history").json
                          for vehicle_id in (first["id"], second["id"])}, before_history)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 3)

    def test_query_parameters_host_and_unavailable_database_fail_closed(self):
        self.fixture()
        for path in ("/garage-api/export?x=1", "/garage-api/export?x=", "/garage-api/export?x=1&x=2"):
            with self.subTest(path=path):
                self.assertEqual(self.send("GET", path).status_code, 400)
        wrong_host = self.client.get("/garage-api/export", base_url="https://elsewhere.test")
        self.assertEqual(wrong_host.status_code, 400)

        missing = Path(self.temp.name) / "not-initialized.sqlite3"
        client = create_app({**self.app_config, "GARAGE_DB": str(missing)}).test_client()
        unavailable = client.get("/garage-api/export", base_url="https://garage.test")
        self.assertEqual(unavailable.status_code, 503)
        self.assertFalse(missing.exists())

    def test_export_read_transaction_is_a_single_consistent_snapshot_while_writer_commits(self):
        first, _, _, _ = self.fixture()
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("PRAGMA journal_mode=WAL")
        reader_started = threading.Event()
        writer_committed = threading.Event()
        original_connect = self.store._connect
        connect_count = []

        class ReadConnection:
            def __init__(self, db):
                self.db = db
                self.paused = False

            def execute(self, sql, *args):
                cursor = self.db.execute(sql, *args)
                normalized = " ".join(sql.lower().split())
                if not self.paused and normalized.startswith("select") and " from vehicles" in normalized:
                    self.paused = True
                    reader_started.set()
                    if not writer_committed.wait(5):
                        raise TimeoutError("writer did not commit during export read")
                return cursor

            def close(self):
                self.db.close()

            def __getattr__(self, name):
                return getattr(self.db, name)

        def tracked_connect():
            connect_count.append(True)
            return ReadConnection(original_connect())
        self.store._connect = tracked_connect
        outcome = {}

        def export():
            try:
                outcome["data"] = self.store.export_data()
            except BaseException as exc:
                outcome["error"] = exc

        reader = threading.Thread(target=export)
        reader.start()
        self.assertTrue(reader_started.wait(5), "export did not establish its first read")
        concurrent = Store(self.path).create_vehicle({"make": "Concurrent", "model": "Writer", "odometerUnit": "km"})
        writer_committed.set()
        reader.join(5)
        self.assertFalse(reader.is_alive(), "export read did not finish")
        if "error" in outcome:
            raise outcome["error"]
        exported = outcome["data"]
        self.assertEqual(len(connect_count), 1, "one export uses one SQLite connection")
        self.assertNotIn(concurrent["id"], [item["id"] for item in exported["vehicles"]])
        self.assertNotIn(concurrent["id"], [item["vehicleId"] for item in exported["statuses"]])
        self.assertNotIn(concurrent["id"], [item["vehicleId"] for item in exported["history"]])
        self.assertIn(first["id"], [item["id"] for item in exported["vehicles"]])
        self.assertEqual(len(exported["statuses"]), len(exported["vehicles"]))


class OwnerExportFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        self.store = Store(self.path)
        self.store.initialize()
        self.store.create_vehicle({"make": "Synthetic", "model": "File export", "odometerUnit": "km"})

    def test_file_export_has_owner_only_permissions_and_refuses_existing_symlink_and_database(self):
        destination = Path(self.temp.name) / "wolfs-garage-export.json"
        returned = self.store.export_to_file(destination)
        self.assertEqual(Path(returned), destination)
        parsed = json.loads(destination.read_text(encoding="utf-8"))
        self.assertEqual(parsed["format"], "wolfs-garage-owner-export")
        if os.name == "posix":
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

        destination.write_text("preserve existing file", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            self.store.export_to_file(destination)
        self.assertEqual(destination.read_text(encoding="utf-8"), "preserve existing file")

        target = Path(self.temp.name) / "symlink-target.json"
        target.write_text("preserve symlink target", encoding="utf-8")
        link = Path(self.temp.name) / "export-link.json"
        link.symlink_to(target)
        with self.assertRaises(FileExistsError):
            self.store.export_to_file(link)
        self.assertEqual(target.read_text(encoding="utf-8"), "preserve symlink target")

        with self.assertRaises(FileExistsError):
            self.store.export_to_file(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 3)

    def test_partial_write_failure_removes_only_the_export_file_it_created(self):
        destination = Path(self.temp.name) / "partial-export.json"
        protected = Path(self.temp.name) / "unrelated.json"
        protected.write_text("leave this file", encoding="utf-8")
        with patch("wolfs_garage.store.os.fsync", side_effect=OSError("synthetic fsync failure")):
            with self.assertRaises(OSError):
                self.store.export_to_file(destination)
        self.assertFalse(destination.exists())
        self.assertEqual(protected.read_text(encoding="utf-8"), "leave this file")

    def test_cli_export_creates_a_fresh_file_and_preserves_existing_database_on_refusal(self):
        destination = Path(self.temp.name) / "cli-export.json"
        env = {**os.environ, "GARAGE_DB": str(self.path)}
        result = subprocess.run([sys.executable, "-m", "wolfs_garage", "export", str(destination)],
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(destination.read_text(encoding="utf-8"))["databaseSchema"], 3)
        if os.name == "posix":
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
        before = self.path.read_bytes()
        refused = subprocess.run([sys.executable, "-m", "wolfs_garage", "export", str(self.path)],
                                 env=env, capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
