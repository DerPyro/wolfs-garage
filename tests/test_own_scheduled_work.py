"""Synthetic public-API checks for scheduled work and the historical schema-2 upgrade path."""
from contextlib import closing
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid
from unittest.mock import patch

from wolfs_garage.api import create_app
from wolfs_garage.store import Store


class ScheduledWorkApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        Store(self.path).initialize()
        self.today_calls = []

        def today_provider():
            self.today_calls.append(True)
            return date(2026, 10, 28)

        self.config = {"TESTING": True, "GARAGE_DB": str(self.path),
                       "GARAGE_PUBLIC_ORIGIN": "https://garage.test",
                       "GARAGE_TODAY_PROVIDER": today_provider}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def send(self, method, path, data=None, headers=None):
        return self.client.open(path, method=method, base_url="https://garage.test", json=data,
                                headers=self.headers if headers is None else headers)

    def create_vehicle(self, make="Synthetic"):
        response = self.send("POST", "/garage-api/vehicles",
                             {"make": make, "model": "Work", "odometerUnit": "km"})
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def update_status(self, vehicle_id, issues, readiness="not_ready", revision=0):
        response = self.send("PUT", f"/garage-api/vehicles/{vehicle_id}/status", {
            "readiness": readiness, "revision": revision, "issues": issues,
        })
        return response

    def issue(self, text, *, dueDate=None, severity=None, lifecycle="open"):
        return {"text": text, "dueDate": dueDate, "severity": severity,
                "lifecycle": lifecycle}

    def test_capability_and_active_work_projection_boundaries_and_no_mutation(self):
        vehicle = self.create_vehicle()
        created = self.update_status(vehicle["id"], [
            self.issue("Overdue critical", dueDate="2026-10-27", severity="critical"),
            self.issue("Due today", dueDate="2026-10-28", severity="repair"),
            self.issue("Upcoming observation", dueDate="2026-11-01", severity="observation", lifecycle="observed"),
            self.issue("Unscheduled open"),
        ])
        self.assertEqual(created.status_code, 200, created.json)
        before_status = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/status").json
        before_history = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json
        self.assertIn("scheduledWork", self.send("GET", "/garage-api/capabilities").json["features"])

        self.today_calls.clear()
        result = self.send("GET", "/garage-api/work")
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(self.today_calls, [True], "date provider is evaluated once per projection request")
        self.assertEqual(result.json["today"], "2026-10-28")
        self.assertEqual(result.json["timeZone"], "Europe/Berlin")
        items = result.json["items"]
        self.assertEqual([item["text"] for item in items], [
            "Overdue critical", "Due today", "Upcoming observation", "Unscheduled open",
        ])
        by_text = {item["text"]: item for item in items}
        self.assertEqual(by_text["Overdue critical"]["dueState"], "overdue")
        self.assertEqual(by_text["Due today"]["dueState"], "today")
        self.assertEqual(by_text["Upcoming observation"]["dueState"], "upcoming")
        self.assertEqual(by_text["Unscheduled open"]["dueState"], "unscheduled")
        self.assertEqual(by_text["Upcoming observation"]["lifecycle"], "observed")
        self.assertEqual(set(by_text["Due today"]), {
            "vehicleId", "id", "text", "dueDate", "severity", "lifecycle", "dueState",
        })
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/status").json, before_status)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json, before_history)

    def test_query_parameters_are_rejected_even_if_empty_or_duplicated(self):
        for suffix in ("?limit=1", "?unknown=", "?unknown=1&unknown=2", "?vehicleId=7"):
            with self.subTest(query=suffix):
                response = self.send("GET", "/garage-api/work" + suffix)
                self.assertEqual(response.status_code, 400, response.json)

    def test_critical_first_then_due_state_date_vehicle_and_issue_tie_order(self):
        first, second = self.create_vehicle("First"), self.create_vehicle("Second")
        fixtures = [
            (first, self.issue("Critical upcoming", dueDate="2026-10-30", severity="critical")),
            (first, self.issue("Critical today", dueDate="2026-10-28", severity="critical")),
            (first, self.issue("Critical overdue", dueDate="2026-10-27", severity="critical")),
            (second, self.issue("Observation overdue later", dueDate="2026-10-22", severity="observation")),
            (first, self.issue("Repair overdue same day", dueDate="2026-10-20", severity="repair")),
            (first, self.issue("Observation overdue same day", dueDate="2026-10-20", severity="observation")),
            (second, self.issue("Unclassified today", dueDate="2026-10-28")),
            (first, self.issue("Observed unscheduled", lifecycle="observed")),
        ]
        ids = {}
        for vehicle, issue in fixtures:
            status_path = f"/garage-api/vehicles/{vehicle['id']}/status"
            current = self.send("GET", status_path).json
            updated = self.update_status(vehicle["id"], current["issues"] + [issue],
                                         readiness="unknown", revision=current["revision"])
            self.assertEqual(updated.status_code, 200, updated.json)
            ids[issue["text"]] = next(row["id"] for row in updated.json["issues"] if row["text"] == issue["text"])
        items = self.send("GET", "/garage-api/work").json["items"]
        self.assertEqual(set(item["text"] for item in items), set(ids))
        priority = {"overdue": 0, "today": 1, "upcoming": 2, "unscheduled": 3}
        sort_key = lambda item: (item["severity"] != "critical", priority[item["dueState"]],
                                 item["dueDate"] or "9999-12-31", item["vehicleId"], item["id"])
        self.assertEqual([item["text"] for item in items],
                         [item["text"] for item in sorted(items, key=sort_key)])
        critical_items = [item for item in items if item["severity"] == "critical"]
        self.assertEqual([item["text"] for item in critical_items],
                         ["Critical overdue", "Critical today", "Critical upcoming"])
        same_day = [item for item in items if item["dueDate"] == "2026-10-20"]
        self.assertEqual([item["id"] for item in same_day], sorted(item["id"] for item in same_day))

    def test_issue_metadata_update_preserves_omitted_fields_and_null_clears_allowed_fields(self):
        vehicle = self.create_vehicle()
        initial = self.update_status(vehicle["id"], [
            self.issue("Metadata", dueDate="2026-11-02", severity="critical", lifecycle="observed"),
        ])
        self.assertEqual(initial.status_code, 200)
        issue = initial.json["issues"][0]
        self.assertEqual(set(issue), {"id", "text", "dueDate", "severity", "lifecycle"})

        changed = self.update_status(vehicle["id"], [{"id": issue["id"], "text": "Updated text"}],
                                     readiness=initial.json["readiness"], revision=initial.json["revision"])
        self.assertEqual(changed.status_code, 200, changed.json)
        self.assertEqual(changed.json["issues"], [{**issue, "text": "Updated text"}])

        cleared = self.update_status(vehicle["id"], [{
            "id": issue["id"], "text": "Updated text", "dueDate": None,
            "severity": None,
        }], readiness=changed.json["readiness"], revision=changed.json["revision"])
        self.assertEqual(cleared.status_code, 200, cleared.json)
        self.assertEqual(cleared.json["issues"], [{
            "id": issue["id"], "text": "Updated text", "dueDate": None,
            "severity": None, "lifecycle": "observed",
        }])

    def test_invalid_metadata_duplicate_or_foreign_issue_and_stale_revision_do_not_audit(self):
        vehicle, other = self.create_vehicle("One"), self.create_vehicle("Two")
        initial = self.update_status(vehicle["id"], [self.issue("Valid")])
        issue = initial.json["issues"][0]
        history = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json
        invalid = [
            {"id": issue["id"], "text": "x", "dueDate": "2026-02-30"},
            {"id": issue["id"], "text": "x", "dueDate": "20261028"},
            {"id": issue["id"], "text": "x", "severity": "unknown"},
            {"id": issue["id"], "text": "x", "lifecycle": "closed"},
            {"id": issue["id"], "text": "x", "lifecycle": None},
            {"id": issue["id"], "text": "x", "extra": True},
            {"id": issue["id"], "text": " "},
            {"id": issue["id"], "text": "x", "dueDate": 20261028},
        ]
        for bad_issue in invalid:
            with self.subTest(issue=bad_issue):
                response = self.update_status(vehicle["id"], [bad_issue], revision=initial.json["revision"])
                self.assertEqual(response.status_code, 400, response.json)

        duplicate = self.update_status(vehicle["id"], [issue, issue], revision=initial.json["revision"])
        self.assertEqual(duplicate.status_code, 400)
        foreign = self.update_status(other["id"], [issue], readiness="unknown", revision=0)
        self.assertEqual(foreign.status_code, 400)
        stale = self.update_status(vehicle["id"], [issue], revision=initial.json["revision"] - 1)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/status").json, initial.json)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json, history)

    def test_record_closure_keeps_readiness_and_other_issue_metadata_and_retry_is_exact(self):
        vehicle = self.create_vehicle()
        status = self.update_status(vehicle["id"], [
            self.issue("Close this", dueDate="2026-10-20", severity="critical"),
            self.issue("Keep this", dueDate="2026-11-01", severity="repair", lifecycle="observed"),
        ], readiness="not_ready")
        self.assertEqual(status.status_code, 200)
        close_id, kept_issue = status.json["issues"]
        payload = {
            "description": "Synthetic issue completion", "kind": "repair",
            "date": "2026-10-28", "commandId": str(uuid.uuid4()),
            "closeIssueId": close_id["id"], "statusRevision": status.json["revision"],
        }
        base = f"/garage-api/vehicles/{vehicle['id']}"
        result = self.send("POST", base + "/records", payload)
        self.assertEqual(result.status_code, 201, result.json)
        self.assertEqual(result.json["status"]["readiness"], "not_ready")
        self.assertEqual(result.json["status"]["issues"], [kept_issue])
        history_after = self.send("GET", base + "/history").json
        self.assertEqual(self.send("POST", base + "/records", payload).json, result.json)
        self.assertEqual(self.send("GET", base + "/history").json, history_after)
        work = self.send("GET", "/garage-api/work").json["items"]
        self.assertEqual([item["text"] for item in work if item["vehicleId"] == vehicle["id"]], ["Keep this"])

    def test_configured_origin_boundary_and_no_writes_from_projection(self):
        vehicle = self.create_vehicle()
        status = self.update_status(vehicle["id"], [self.issue("Only projection")])
        self.assertEqual(status.status_code, 200)
        history_before = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json
        wrong_host = self.client.get("/garage-api/work", base_url="https://elsewhere.test")
        self.assertEqual(wrong_host.status_code, 400)
        for _ in range(3):
            self.assertEqual(self.send("GET", "/garage-api/work").status_code, 200)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/status").json, status.json)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json, history_before)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 5)

    def test_default_clock_uses_berlin_calendar_date_across_winter_and_summer_midnight(self):
        app = create_app({"TESTING": True, "GARAGE_DB": str(self.path),
                          "GARAGE_PUBLIC_ORIGIN": "https://garage.test"})
        client = app.test_client()

        class FrozenDateTime:
            instant = None

            @classmethod
            def now(cls, tz=None):
                return cls.instant.astimezone(tz)

        cases = [
            (datetime(2026, 1, 1, 22, 59, tzinfo=timezone.utc), "2026-01-01"),
            (datetime(2026, 1, 1, 23, 1, tzinfo=timezone.utc), "2026-01-02"),
            (datetime(2026, 6, 30, 21, 59, tzinfo=timezone.utc), "2026-06-30"),
            (datetime(2026, 6, 30, 22, 1, tzinfo=timezone.utc), "2026-07-01"),
        ]
        with patch("wolfs_garage.store.datetime", FrozenDateTime):
            for instant, expected in cases:
                with self.subTest(instant=instant):
                    FrozenDateTime.instant = instant
                    result = client.get("/garage-api/work", base_url="https://garage.test")
                    self.assertEqual(result.status_code, 200, result.json)
                    self.assertEqual(result.json["today"], expected)
                    self.assertEqual(result.json["timeZone"], "Europe/Berlin")


class Schema3UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.path = self.directory / "schema2.sqlite3"
        fixture = Path(__file__).parent / "fixtures" / "schema2_fixture.txt"
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(fixture.read_text())
        self.store = Store(self.path)

    def test_schema2_upgrade_backs_up_and_preserves_rows_commands_audit_and_legacy_issue_json(self):
        backup = self.directory / "before-schema5.sqlite3"
        self.assertTrue(self.store.upgrade(backup))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 5)
            self.assertEqual(db.execute("SELECT id,description,revision FROM records").fetchone(),
                             (11, "Legacy service", 1))
            self.assertEqual(db.execute("SELECT action,command_id,response FROM commands").fetchone(),
                             ("record", "legacy-command", '{"record":{"id":11,"description":"Legacy service"}}'))
            self.assertEqual(db.execute("SELECT sequence,action,after_json FROM history").fetchone(),
                             (13, "record.created", '{"record":{"id":11,"description":"Legacy service"}}'))
            raw = db.execute("SELECT issues FROM states WHERE vehicle_id=7").fetchone()[0]
            self.assertEqual(json.loads(raw), [{"id": "0123456789abcdef0123456789abcdef", "text": "Legacy issue without schedule metadata"}])
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT id,description,revision FROM records").fetchone(),
                             (11, "Legacy service", 1))

        legacy = self.store.get_status(7)
        self.assertEqual(legacy["issues"], [{
            "id": "0123456789abcdef0123456789abcdef", "text": "Legacy issue without schedule metadata",
            "dueDate": None, "severity": None, "lifecycle": "open",
        }])
        before_backup = backup.read_bytes()
        self.assertFalse(self.store.upgrade(self.directory / "unused.sqlite3"))
        self.assertFalse((self.directory / "unused.sqlite3").exists())
        self.assertFalse(self.store.upgrade(backup))
        self.assertEqual(backup.read_bytes(), before_backup)

    def test_backup_collision_and_migration_failure_leave_schema2_database_untouched(self):
        collision = self.directory / "existing.sqlite3"
        collision.write_text("keep")
        with self.assertRaises(FileExistsError):
            self.store.upgrade(collision)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 2)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
        self.assertEqual(collision.read_text(), "keep")

        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TRIGGER reject_schema5 BEFORE UPDATE ON meta BEGIN SELECT RAISE(ABORT,'synthetic schema failure'); END")
        backup = self.directory / "rollback-backup.sqlite3"
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.upgrade(backup)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 2)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("SELECT issues FROM states WHERE vehicle_id=7").fetchone()[0],
                             '[{"id":"0123456789abcdef0123456789abcdef","text":"Legacy issue without schedule metadata"}]')
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT id,description FROM records").fetchone(), (11, "Legacy service"))

    def test_explicit_upgrade_to_schema5_is_noop_and_no_second_backup(self):
        backup = self.directory / "first-upgrade.sqlite3"
        self.assertTrue(self.store.upgrade(backup))
        self.assertFalse(self.store.upgrade(self.directory / "second-upgrade.sqlite3"))
        self.assertFalse((self.directory / "second-upgrade.sqlite3").exists())
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 5)


if __name__ == "__main__":
    unittest.main()
