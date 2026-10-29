"""Synthetic API, calendar-projection, export and frozen legacy migration checks."""
from contextlib import closing
import calendar
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from wolfs_garage.api import create_app
from wolfs_garage.store import Conflict, Store, ValidationError


FIXTURES = Path(__file__).parent / "fixtures"


def build_schema1(path):
    with closing(sqlite3.connect(path)) as db:
        db.executescript((FIXTURES / "schema1_fixture.txt").read_text())
        with db:
            db.execute("INSERT INTO vehicles VALUES(7,'Synthetic','Legacy','Synthetic Legacy',2020,'','Car','km',1)")
            db.execute("INSERT INTO states VALUES(7,'ready','[]',4)")
            db.execute("INSERT INTO records VALUES(11,7,'Legacy service','service','2025-04-05','1000','km','9.99','EUR',NULL,NULL)")
            db.execute("INSERT INTO commands VALUES(7,'record','legacy-id','legacy-hash','{\"ok\":true}')")
            db.execute("INSERT INTO history VALUES(13,7,'record.created','2025-04-05T00:00:00+00:00','null','{\"legacy\":true}')")


def build_fixture(path, schema):
    fixture = FIXTURES / f"schema{schema}_fixture.txt"
    with closing(sqlite3.connect(path)) as db:
        db.executescript(fixture.read_text())


class InspectionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        self.calls = []
        self.today = date(2026, 10, 1)

        def today_provider():
            self.calls.append(self.today)
            return self.today

        self.provider = today_provider
        self.store = Store(self.path, today_provider=today_provider)
        self.store.initialize()
        self.app = create_app({"TESTING": True, "GARAGE_DB": str(self.path),
                               "GARAGE_PUBLIC_ORIGIN": "https://garage.test",
                               "GARAGE_TODAY_PROVIDER": today_provider})
        self.client = self.app.test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def send(self, method, path, data=None):
        return self.client.open(path, method=method, base_url="https://garage.test", json=data,
                                headers=self.headers if method in {"POST", "PUT", "PATCH", "DELETE"} else None)

    def create(self, due_month=None, **extra):
        payload = {"make": "Synthetic", "model": "Inspection", **extra}
        if due_month is not None or "inspectionDueMonth" in extra:
            payload["inspectionDueMonth"] = due_month
        result = self.send("POST", "/garage-api/vehicles", payload)
        self.assertEqual(result.status_code, 201, result.json)
        return result.json

    def test_capability_create_defaults_and_unknown_inspection_projection(self):
        capabilities = self.send("GET", "/garage-api/capabilities")
        self.assertEqual(capabilities.status_code, 200)
        self.assertIn("inspectionStatus", capabilities.json["features"])
        vehicle = self.create()
        self.assertIsNone(vehicle["inspectionDueMonth"])
        self.assertEqual(vehicle["inspection"], {
            "asOf": "2026-10-01", "timeZone": "Europe/Berlin", "dueMonth": None,
            "validUntil": None, "blockingFrom": None, "state": "unknown",
            "monthsUntilDue": None, "blocksReadiness": False,
            "batteryLevel": None, "scaleMonths": 12,
        })
        self.assertEqual(vehicle["status"]["readiness"], "unknown")
        self.assertEqual(vehicle["effectiveReadiness"], "unknown")
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").json, vehicle)
        summary = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/summary")
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json["vehicle"]["inspection"], vehicle["inspection"])
        events_before = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json["events"]
        self.send("GET", "/garage-api/vehicles")
        self.send("GET", f"/garage-api/vehicles/{vehicle['id']}")
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json["events"], events_before)

    def test_inspection_month_states_boundary_and_clamped_battery(self):
        cases = [
            ("2027-11", "upcoming", 13, 12, False, "2027-11-30", "2028-01-01"),
            ("2026-10", "due", 0, 0, False, "2026-10-31", "2026-12-01"),
            ("2026-09", "overdue", -1, 0, False, "2026-09-30", "2026-11-01"),
            ("2026-08", "blocking", -2, 0, True, "2026-08-31", "2026-10-01"),
            ("2028-02", "upcoming", 16, 12, False, "2028-02-29", "2028-04-01"),
        ]
        for month, state, months, battery, blocks, valid_until, blocking_from in cases:
            with self.subTest(month=month):
                result = self.store.create_vehicle({"make": "Synthetic", "model": "Month",
                                                    "inspectionDueMonth": month})
                derived = result["inspection"]
                self.assertEqual((derived["state"], derived["monthsUntilDue"], derived["batteryLevel"],
                                  derived["blocksReadiness"], derived["validUntil"], derived["blockingFrom"]),
                                 (state, months, battery, blocks, valid_until, blocking_from))
                self.assertEqual(result["effectiveReadiness"], "not_ready" if blocks else "unknown")

    def test_valid_until_and_blocking_from_are_correct_for_each_month(self):
        for month in range(1, 13):
            with self.subTest(month=month):
                due = f"2027-{month:02d}"
                result = self.store.create_vehicle({"make": "Synthetic", "model": f"Month {month}",
                                                    "inspectionDueMonth": due})
                inspection = result["inspection"]
                valid_until = f"2027-{month:02d}-{calendar.monthrange(2027, month)[1]:02d}"
                absolute_blocking_month = 2027 * 12 + month - 1 + 2
                blocking_year, month_index = divmod(absolute_blocking_month, 12)
                blocking_from = f"{blocking_year:04d}-{month_index + 1:02d}-01"
                self.assertEqual(inspection["validUntil"], valid_until)
                self.assertEqual(inspection["blockingFrom"], blocking_from)

    def test_user_policy_due_august_becomes_overdue_then_blocks_on_october_first(self):
        due = self.store.create_vehicle({"make": "Synthetic", "model": "Policy", "inspectionDueMonth": "2027-08"})
        self.assertEqual(due["inspection"]["blockingFrom"], "2027-10-01")
        self.today = date(2027, 9, 30)
        september = self.store.get_vehicle(due["id"])
        self.assertEqual(september["inspection"]["state"], "overdue")
        self.assertFalse(september["inspection"]["blocksReadiness"])
        self.today = date(2027, 10, 1)
        october = self.store.get_vehicle(due["id"])
        self.assertEqual(october["inspection"]["state"], "blocking")
        self.assertTrue(october["inspection"]["blocksReadiness"])
        self.assertEqual(october["effectiveReadiness"], "not_ready")

    def test_month_arithmetic_handles_december_january_and_valid_year_extremes(self):
        self.today = date(2027, 1, 1)
        dec = self.store.create_vehicle({"make": "Synthetic", "model": "Dec", "inspectionDueMonth": "2026-12"})
        self.assertEqual(dec["inspection"]["state"], "overdue")
        self.assertEqual(dec["inspection"]["blockingFrom"], "2027-02-01")
        self.today = date(2027, 2, 1)
        self.assertEqual(self.store.get_vehicle(dec["id"])["inspection"]["state"], "blocking")

        self.today = date(1, 1, 1)
        first = self.store.create_vehicle({"make": "Synthetic", "model": "First", "inspectionDueMonth": "0001-01"})
        self.assertEqual(first["inspection"]["state"], "due")
        self.today = date(9998, 10, 1)
        last = self.store.create_vehicle({"make": "Synthetic", "model": "Last", "inspectionDueMonth": "9998-12"})
        self.assertEqual(last["inspection"]["state"], "upcoming")
        self.assertEqual(last["inspection"]["validUntil"], "9998-12-31")
        self.assertEqual(last["inspection"]["blockingFrom"], "9999-02-01")

    def test_default_clock_uses_berlin_date_for_winter_and_summer_utc_boundaries(self):
        vehicle = self.store.create_vehicle({"make": "Synthetic", "model": "Clock", "inspectionDueMonth": "2026-07"})

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
        default_store = Store(self.path)
        with patch("wolfs_garage.store.datetime", FrozenDateTime):
            for instant, expected in cases:
                with self.subTest(instant=instant):
                    FrozenDateTime.instant = instant
                    self.assertEqual(default_store.get_vehicle(vehicle["id"])["inspection"]["asOf"], expected)

    def test_read_projection_calls_date_provider_once_per_list_request(self):
        self.store.create_vehicle({"make": "Synthetic", "model": "One"})
        self.store.create_vehicle({"make": "Synthetic", "model": "Two"})
        self.calls.clear()
        listed = self.send("GET", "/garage-api/vehicles")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json["vehicles"]), 2)
        self.assertEqual(self.calls, [date(2026, 10, 1)])

    def test_manual_readiness_is_preserved_and_only_inspection_adds_effective_block(self):
        vehicle = self.create("2026-08")
        reading = self.send("POST", f"/garage-api/vehicles/{vehicle['id']}/odometer", {
            "date": "2026-09-30", "odometer": 100, "unit": "km", "note": "Synthetic unchanged reading",
            "commandId": "00000000-0000-4000-8000-000000000001",
        })
        self.assertEqual(reading.status_code, 201)
        readings_before = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/odometer").json
        updated = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}/status", {
            "readiness": "ready", "issues": [{"text": "Synthetic open issue"}], "revision": 0,
        })
        self.assertEqual(updated.status_code, 200)
        public = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").json
        self.assertEqual(public["status"]["readiness"], "ready")
        self.assertEqual(public["effectiveReadiness"], "not_ready")
        self.assertEqual(public["status"]["issues"], updated.json["issues"])

        renewed = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}", {
            "revision": public["revision"], "inspectionDueMonth": "2027-08",
        })
        self.assertEqual(renewed.status_code, 200, renewed.json)
        self.assertEqual(renewed.json["inspection"]["state"], "upcoming")
        self.assertEqual(renewed.json["status"]["readiness"], "ready")
        self.assertEqual(renewed.json["effectiveReadiness"], "ready")
        self.assertEqual(renewed.json["status"]["issues"], updated.json["issues"])
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/odometer").json, readings_before)

        manual = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}/status", {
            "readiness": "not_ready", "issues": updated.json["issues"], "revision": updated.json["revision"],
        })
        after_manual = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").json
        self.assertEqual(manual.status_code, 200)
        self.assertEqual(after_manual["effectiveReadiness"], "not_ready")
        cleared = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}", {
            "revision": after_manual["revision"], "inspectionDueMonth": None,
        })
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(cleared.json["inspection"]["state"], "unknown")
        self.assertEqual(cleared.json["effectiveReadiness"], "not_ready")
        self.assertEqual(cleared.json["status"]["readiness"], "not_ready")
        self.assertEqual(cleared.json["status"]["issues"], updated.json["issues"])
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/odometer").json, readings_before)

    def test_omitted_due_month_preserves_value_null_clears_and_audit_is_raw(self):
        vehicle = self.create("2026-08")
        changed = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}", {
            "revision": vehicle["revision"], "name": "Updated synthetic name",
        })
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(changed.json["inspectionDueMonth"], "2026-08")
        self.assertEqual(changed.json["revision"], vehicle["revision"] + 1)
        cleared = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}", {
            "revision": changed.json["revision"], "inspectionDueMonth": None,
        })
        self.assertEqual(cleared.status_code, 200)
        self.assertIsNone(cleared.json["inspectionDueMonth"])
        history = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json["events"]
        update = [event for event in history if event["action"] == "vehicle.updated"][-1]
        self.assertNotIn("inspection", update["before"])
        self.assertNotIn("effectiveReadiness", update["after"])
        self.assertEqual(update["before"]["inspectionDueMonth"], "2026-08")
        self.assertIsNone(update["after"]["inspectionDueMonth"])

    def test_invalid_due_months_and_stale_vehicle_revision_do_not_write(self):
        for bad in ("2026-1", "2026-00", "2026-13", "0000-01", "9999-12", 202610, True, [], {}):
            with self.subTest(value=bad):
                result = self.send("POST", "/garage-api/vehicles", {
                    "make": "Synthetic", "model": "Invalid", "inspectionDueMonth": bad,
                })
                self.assertEqual(result.status_code, 400, result.json)
        vehicle = self.create("2026-08")
        before_history = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json
        for bad in ("2026-13", "2026-1", "0000-12", "9999-01", 123):
            with self.subTest(update=bad):
                result = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}", {
                    "revision": vehicle["revision"], "inspectionDueMonth": bad,
                })
                self.assertEqual(result.status_code, 400, result.json)
        stale = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}", {
            "revision": vehicle["revision"] - 1, "inspectionDueMonth": "2027-08",
        })
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").json["inspectionDueMonth"], "2026-08")
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json, before_history)

    def test_invalid_stored_month_fails_closed_as_unavailable_database(self):
        vehicle = self.create("2027-01")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE vehicles SET inspection_due_month='2027-13' WHERE id=?", (vehicle["id"],))
        result = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}")
        self.assertEqual(result.status_code, 503)

    def test_current_export_contains_raw_month_but_no_derived_inspection_fields(self):
        vehicle = self.create("2027-08")
        exported = self.store.export_data()
        self.assertEqual((exported["formatVersion"], exported["databaseSchema"]), (4, 6))
        raw = next(item for item in exported["vehicles"] if item["id"] == vehicle["id"])
        self.assertEqual(raw["inspectionDueMonth"], "2027-08")
        self.assertNotIn("inspection", raw)
        self.assertNotIn("effectiveReadiness", raw)
        self.assertEqual(json.loads(json.dumps(exported))["vehicles"], exported["vehicles"])
        self.assertNotIn("inspection", json.loads(json.dumps(exported["history"]))[0]["after"])


class InspectionSchemaUpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def path(self, schema):
        path = self.directory / f"schema{schema}.sqlite3"
        if schema == 1:
            build_schema1(path)
        else:
            build_fixture(path, schema)
        return path

    def test_explicit_checked_backup_upgrade_from_schema1_2_3_preserves_rows(self):
        for schema in (1, 2, 3):
            with self.subTest(schema=schema):
                path = self.path(schema)
                backup = self.directory / f"schema{schema}-before-6.sqlite3"
                with closing(sqlite3.connect(path)) as db:
                    before_history = db.execute("SELECT * FROM history").fetchall()
                    before_record = db.execute("SELECT * FROM records").fetchall()
                    before_command = db.execute("SELECT * FROM commands").fetchall()
                store = Store(path, today_provider=lambda: date(2026, 10, 1))
                self.assertTrue(store.upgrade(backup))
                with closing(sqlite3.connect(path)) as db:
                    self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 6)
                    self.assertIn("inspection_due_month", [row[1] for row in db.execute("PRAGMA table_info(vehicles)")])
                    self.assertIsNone(db.execute("SELECT inspection_due_month FROM vehicles").fetchone()[0])
                    self.assertEqual(db.execute("SELECT * FROM records").fetchall(), before_record if schema != 1 else [(*before_record[0], 1)])
                    self.assertEqual(db.execute("SELECT * FROM commands").fetchall(), before_command)
                    self.assertEqual(db.execute("SELECT * FROM history").fetchall(), before_history)
                    self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                with closing(sqlite3.connect(backup)) as db:
                    self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], schema)
                vehicle = store.get_vehicle(7)
                self.assertIsNone(vehicle["inspectionDueMonth"])
                self.assertEqual(vehicle["inspection"]["state"], "unknown")
                self.assertFalse(store.upgrade(self.directory / f"schema{schema}-second.sqlite3"))
                self.assertFalse((self.directory / f"schema{schema}-second.sqlite3").exists())

    def test_schema3_application_refuses_reads_until_explicit_upgrade(self):
        path = self.path(3)
        client = create_app({"TESTING": True, "GARAGE_DB": str(path),
                             "GARAGE_PUBLIC_ORIGIN": "https://garage.test"}).test_client()
        before = client.get("/garage-api/vehicles", base_url="https://garage.test")
        self.assertEqual(before.status_code, 503)
        self.assertTrue(Store(path).upgrade(self.directory / "schema3-pre-upgrade.sqlite3"))
        after = client.get("/garage-api/vehicles", base_url="https://garage.test")
        self.assertEqual(after.status_code, 200, after.json)
        self.assertEqual(after.json["vehicles"][0]["inspection"]["state"], "unknown")

    def test_failed_schema6_migration_rolls_back_columns_and_version(self):
        path = self.path(3)
        with closing(sqlite3.connect(path)) as db, db:
            db.execute("CREATE TRIGGER reject_schema6 BEFORE UPDATE ON meta BEGIN SELECT RAISE(ABORT,'synthetic schema6 failure'); END")
        backup = self.directory / "schema3-failed-upgrade-backup.sqlite3"
        with self.assertRaises(sqlite3.IntegrityError):
            Store(path).upgrade(backup)
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 3)
            self.assertNotIn("inspection_due_month", [row[1] for row in db.execute("PRAGMA table_info(vehicles)")])
            self.assertFalse({"revision", "provenance", "source_record_id"} &
                             {row[1] for row in db.execute("PRAGMA table_info(odometer_readings)")})
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 3)

    def test_backup_accepts_current_schema6_and_upgrade6_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "current.sqlite3"
            store = Store(path)
            store.initialize()
            backup = Path(tmp) / "schema6-backup.sqlite3"
            store.backup(backup)
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 6)
            self.assertFalse(store.upgrade(Path(tmp) / "unused.sqlite3"))
            self.assertFalse((Path(tmp) / "unused.sqlite3").exists())


if __name__ == "__main__":
    unittest.main()
