"""Synthetic API acceptance for annual-usage projections and odometer prompts."""
from contextlib import closing
from datetime import date
import sqlite3
import tempfile
from pathlib import Path
import unittest
import uuid

from wolfs_garage.api import create_app
from wolfs_garage.store import Store


class MileageProjectionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        self.today = date(2026, 3, 1)
        self.clock_calls = []

        def today_provider():
            self.clock_calls.append(self.today)
            return self.today

        self.today_provider = today_provider
        self.store = Store(self.path, today_provider=today_provider)
        self.store.initialize()
        self.client = create_app({"TESTING": True, "GARAGE_DB": str(self.path),
                                  "GARAGE_PUBLIC_ORIGIN": "https://garage.test",
                                  "GARAGE_TODAY_PROVIDER": today_provider}).test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def send(self, method, path, payload=None, *, base="https://garage.test", headers=None):
        return self.client.open(path, method=method, base_url=base, json=payload,
                                headers=self.headers if headers is None else headers)

    def create_vehicle(self, **extra):
        response = self.send("POST", "/garage-api/vehicles", {
            "make": "Synthetic", "model": "Mileage", "odometerUnit": "km", **extra,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def add_reading(self, vehicle, day, value, *, unit=None, note="Synthetic actual reading"):
        response = self.send("POST", f"/garage-api/vehicles/{vehicle['id']}/odometer", {
            "date": day, "odometer": value, "unit": unit or vehicle["odometerUnit"],
            "note": note, "commandId": str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def update_vehicle(self, vehicle, **fields):
        response = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}", {
            "revision": vehicle["revision"], **fields,
        })
        return response

    def counts(self, vehicle_id):
        with closing(sqlite3.connect(self.path)) as db:
            return tuple(db.execute(f"SELECT COUNT(*) FROM {table} WHERE vehicle_id=?", (vehicle_id,)).fetchone()[0]
                         for table in ("odometer_readings", "history", "commands"))

    def test_capabilities_defaults_anchor_missing_and_projection_reads_are_read_only(self):
        features = self.send("GET", "/garage-api/capabilities").get_json()["features"]
        self.assertIn("mileageForecast", features)

        vehicle = self.create_vehicle()
        self.assertIsNone(vehicle["annualUsage"])
        self.assertEqual(vehicle["readingPromptDays"], 30)
        self.assertEqual(vehicle["mileageEstimate"], {
            "asOf": "2026-03-01", "timeZone": "Europe/Berlin", "state": "anchor_missing",
            "annualUsage": None, "unit": "km", "anchor": None, "elapsedDays": None,
            "estimatedOdometer": None,
        })
        self.assertEqual(vehicle["readingPrompt"], {
            "asOf": "2026-03-01", "timeZone": "Europe/Berlin", "state": "needs_reading",
            "intervalDays": 30, "dueDate": None, "reason": None,
        })
        before = self.counts(vehicle["id"])
        for _ in range(2):
            self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").status_code, 200)
            self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/summary").status_code, 200)
            self.assertEqual(self.send("GET", "/garage-api/vehicles").status_code, 200)
        self.assertEqual(self.counts(vehicle["id"]), before)

    def test_estimate_uses_latest_actual_tie_breaks_by_id_and_rounds_half_up(self):
        vehicle = self.create_vehicle(annualUsage="12000")
        self.add_reading(vehicle, "2025-03-01", "1234.125")
        first = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").get_json()["mileageEstimate"]
        self.assertEqual(first, {
            "asOf": "2026-03-01", "timeZone": "Europe/Berlin", "state": "estimated",
            "annualUsage": "12000", "unit": "km",
            "anchor": {"id": 1, "date": "2025-03-01", "odometer": "1234.125", "unit": "km"},
            "elapsedDays": 365, "estimatedOdometer": "13234.125",
        })

        tied = self.add_reading(vehicle, "2025-03-01", "2000.125")
        estimate = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").get_json()["mileageEstimate"]
        self.assertEqual(estimate["anchor"]["id"], tied["id"])
        self.assertEqual(estimate["estimatedOdometer"], "14000.125")

        tiny = self.update_vehicle(vehicle, annualUsage="1")
        self.assertEqual(tiny.status_code, 200, tiny.get_json())
        vehicle = tiny.get_json()
        # 183/365 rounds 0.501... upward to one decimal-place-thousandth.
        self.today = date(2025, 9, 1)
        self.add_reading(vehicle, "2025-03-02", "0")
        half_up = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").get_json()["mileageEstimate"]
        self.assertEqual(half_up["estimatedOdometer"], "0.501")

    def test_zero_and_missing_rate_are_distinct_and_all_supported_units_are_labeled(self):
        km = self.create_vehicle(annualUsage="0")
        actual = self.add_reading(km, "2026-02-01", "0")
        estimate = self.send("GET", f"/garage-api/vehicles/{km['id']}").get_json()["mileageEstimate"]
        self.assertEqual((estimate["state"], estimate["annualUsage"], estimate["unit"],
                          estimate["anchor"]["id"], estimate["estimatedOdometer"]),
                         ("estimated", "0", "km", actual["id"], "0"))

        missing = self.create_vehicle()
        self.add_reading(missing, "2026-02-01", "42")
        no_rate = self.send("GET", f"/garage-api/vehicles/{missing['id']}").get_json()["mileageEstimate"]
        self.assertEqual(no_rate["state"], "annual_usage_missing")
        self.assertIsNone(no_rate["estimatedOdometer"])
        self.assertEqual(no_rate["anchor"]["odometer"], "42")

        hours = self.create_vehicle(odometerUnit="h", annualUsage="100")
        hour_reading = self.add_reading(hours, "2026-02-01", "17.250", unit="h")
        hour_estimate = self.send("GET", f"/garage-api/vehicles/{hours['id']}").get_json()["mileageEstimate"]
        self.assertEqual((hour_estimate["state"], hour_estimate["unit"], hour_estimate["anchor"]["id"]),
                         ("estimated", "h", hour_reading["id"]))
        self.assertEqual(hour_estimate["estimatedOdometer"], "24.921")

        miles = self.create_vehicle(odometerUnit="mi", annualUsage="1.250")
        mile_reading = self.add_reading(miles, "2026-02-01", "100.125", unit="mi")
        mile_estimate = self.send("GET", f"/garage-api/vehicles/{miles['id']}").get_json()["mileageEstimate"]
        self.assertEqual((mile_estimate["unit"], mile_estimate["anchor"]["unit"],
                          mile_estimate["anchor"]["id"]), ("mi", "mi", mile_reading["id"]))

    def test_future_mismatched_and_out_of_range_anchors_are_review_only(self):
        future = self.create_vehicle(annualUsage="100")
        self.add_reading(future, "2026-03-02", "100")
        future_vehicle = self.send("GET", f"/garage-api/vehicles/{future['id']}").get_json()
        self.assertEqual(future_vehicle["mileageEstimate"]["state"], "future_anchor")
        self.assertIsNone(future_vehicle["mileageEstimate"]["estimatedOdometer"])
        self.assertEqual(future_vehicle["readingPrompt"]["state"], "needs_review")
        self.assertEqual(future_vehicle["readingPrompt"]["reason"], "future_anchor")

        mismatch = self.create_vehicle(annualUsage="100")
        reading = self.add_reading(mismatch, "2026-02-01", "100")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE odometer_readings SET unit='mi' WHERE id=?", (reading["id"],))
        mismatch_vehicle = self.send("GET", f"/garage-api/vehicles/{mismatch['id']}").get_json()
        self.assertEqual(mismatch_vehicle["mileageEstimate"]["state"], "unit_mismatch")
        self.assertIsNone(mismatch_vehicle["mileageEstimate"]["estimatedOdometer"])
        self.assertEqual(mismatch_vehicle["readingPrompt"]["state"], "needs_review")
        self.assertEqual(mismatch_vehicle["readingPrompt"]["reason"], "unit_mismatch")

        overflow = self.create_vehicle(annualUsage="1000000000")
        self.add_reading(overflow, "2025-02-28", "1000000000")
        overflow_vehicle = self.send("GET", f"/garage-api/vehicles/{overflow['id']}").get_json()
        self.assertEqual(overflow_vehicle["mileageEstimate"]["state"], "out_of_range")
        self.assertIsNone(overflow_vehicle["mileageEstimate"]["estimatedOdometer"])

    def test_read_prompt_default_custom_disabled_boundaries_and_new_actual_reading(self):
        vehicle = self.create_vehicle()
        self.add_reading(vehicle, "2026-02-01", "100")
        detail_path = f"/garage-api/vehicles/{vehicle['id']}"
        before_due = self.send("GET", detail_path).get_json()["readingPrompt"]
        self.assertEqual(before_due, {
            "asOf": "2026-03-01", "timeZone": "Europe/Berlin", "state": "not_due",
            "intervalDays": 30, "dueDate": "2026-03-03", "reason": None,
        })
        self.today = date(2026, 3, 2)
        self.assertEqual(self.send("GET", detail_path).get_json()["readingPrompt"]["state"], "not_due")
        self.today = date(2026, 3, 3)
        self.assertEqual(self.send("GET", detail_path).get_json()["readingPrompt"]["state"], "due")

        updated = self.update_vehicle(vehicle, readingPromptDays=7)
        self.assertEqual(updated.status_code, 200, updated.get_json())
        vehicle = updated.get_json()
        prompt = vehicle["readingPrompt"]
        self.assertEqual((prompt["intervalDays"], prompt["dueDate"], prompt["state"]), (7, "2026-02-08", "due"))
        disabled = self.update_vehicle(vehicle, readingPromptDays=None)
        self.assertEqual(disabled.status_code, 200, disabled.get_json())
        self.assertEqual(disabled.get_json()["readingPrompt"]["state"], "disabled")
        self.assertIsNone(disabled.get_json()["readingPrompt"]["dueDate"])

        enabled = self.update_vehicle(disabled.get_json(), readingPromptDays=1)
        self.assertEqual(enabled.status_code, 200, enabled.get_json())
        actual = self.add_reading(enabled.get_json(), "2026-03-03", "101")
        self.today = date(2026, 3, 3)
        refreshed = self.send("GET", detail_path).get_json()
        self.assertEqual(refreshed["readingPrompt"]["state"], "not_due")
        self.assertEqual(refreshed["readingPrompt"]["dueDate"], "2026-03-04")
        self.assertEqual(refreshed["mileageEstimate"]["anchor"]["id"], actual["id"])

    def test_read_prompt_review_handles_date_overflow_and_projection_clock_is_once_per_list(self):
        vehicle = self.create_vehicle(annualUsage="1", readingPromptDays=3650)
        self.add_reading(vehicle, "9999-11-30", "100")
        self.today = date(9999, 12, 1)
        response = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["readingPrompt"]["state"], "needs_review")
        self.assertEqual(response.get_json()["readingPrompt"]["reason"], "date_out_of_range")

        self.create_vehicle(annualUsage="1")
        self.clock_calls.clear()
        listing = self.send("GET", "/garage-api/vehicles")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(len(self.clock_calls), 1)
        self.assertTrue(all(item["mileageEstimate"]["asOf"] == "9999-12-01"
                            and item["readingPrompt"]["asOf"] == "9999-12-01"
                            for item in listing.get_json()["vehicles"]))

    def test_profile_validation_zero_and_explicit_reset_on_empty_unit_change(self):
        vehicle = self.create_vehicle(annualUsage="0")
        invalid_rates = [None, "-1", "1e3", "1.0001", "1000000000.001", 1, True, ""]
        # Null is valid as an explicit clear; the other invalid values must fail.
        for invalid in invalid_rates[1:]:
            with self.subTest(annualUsage=invalid):
                response = self.update_vehicle(vehicle, annualUsage=invalid)
                self.assertEqual(response.status_code, 400, response.get_json())
        needs_reset = self.update_vehicle(vehicle, odometerUnit="mi")
        self.assertEqual(needs_reset.status_code, 409, needs_reset.get_json())
        reset = self.update_vehicle(vehicle, odometerUnit="mi", annualUsage=None)
        self.assertEqual(reset.status_code, 200, reset.get_json())
        self.assertEqual((reset.get_json()["odometerUnit"], reset.get_json()["annualUsage"]), ("mi", None))

        invalid_days = [0, -1, 3651, True, "30", 1.5]
        for invalid in invalid_days:
            with self.subTest(readingPromptDays=invalid):
                response = self.update_vehicle(reset.get_json(), readingPromptDays=invalid)
                self.assertEqual(response.status_code, 400, response.get_json())

    def test_unit_change_with_actual_readings_is_blocked_and_backdated_correction_reanchors(self):
        vehicle = self.create_vehicle(annualUsage="100")
        earlier = self.add_reading(vehicle, "2026-01-01", "100")
        later = self.add_reading(vehicle, "2026-02-01", "200")
        current_vehicle = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").get_json()
        self.assertEqual(current_vehicle["mileageEstimate"]["anchor"]["id"], later["id"])
        blocked = self.update_vehicle(current_vehicle, odometerUnit="mi", annualUsage=None)
        self.assertEqual(blocked.status_code, 409, blocked.get_json())

        corrected = self.send("PUT", f"/garage-api/vehicles/{vehicle['id']}/odometer/{later['id']}", {
            "revision": later["revision"], "date": "2025-12-31", "odometer": "200.500",
            "note": "Backdated synthetic correction", "commandId": str(uuid.uuid4()),
            "correctionReason": "Synthetic source checked.",
        })
        self.assertEqual(corrected.status_code, 200, corrected.get_json())
        reanchored = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}").get_json()["mileageEstimate"]
        self.assertEqual(reanchored["anchor"]["id"], earlier["id"])
        self.assertEqual(reanchored["anchor"]["odometer"], "100")

    def test_format4_export_contains_raw_fields_but_no_derived_projections(self):
        vehicle = self.create_vehicle(annualUsage="1234.500", readingPromptDays=None)
        self.add_reading(vehicle, "2026-02-01", "100")
        response = self.send("GET", "/garage-api/export")
        self.assertEqual(response.status_code, 200, response.get_json())
        exported = response.get_json()
        self.assertEqual((exported["formatVersion"], exported["databaseSchema"]), (4, 6))
        exported_vehicle = next(item for item in exported["vehicles"] if item["id"] == vehicle["id"])
        self.assertEqual((exported_vehicle["annualUsage"], exported_vehicle["readingPromptDays"]),
                         ("1234.5", None))
        for derived in ("mileageEstimate", "readingPrompt"):
            self.assertNotIn(derived, exported_vehicle)
            for event in exported["history"]:
                for key in ("before", "after"):
                    payload = event.get(key)
                    if isinstance(payload, dict):
                        self.assertNotIn(derived, payload)
        no_query = self.send("GET", "/garage-api/export?x=1")
        self.assertEqual(no_query.status_code, 400)


if __name__ == "__main__":
    unittest.main()
