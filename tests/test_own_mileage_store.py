"""Store-level tests for schema-6 mileage projections and prompt timing."""
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from wolfs_garage.store import Conflict, SCHEMA, Store, ValidationError


FIXTURES = Path(__file__).parent / "fixtures"


class MileageProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        self.today = date(2027, 1, 1)
        self.calls = 0

        def provider():
            self.calls += 1
            return self.today

        self.store = Store(self.path, today_provider=provider)
        self.store.initialize()
        self.vehicle = self.store.create_vehicle({"make": "Synthetic", "model": "Mileage"})
        self.vehicle_id = self.vehicle["id"]

    def reading(self, day, value, unit="km", note="", command_id=None):
        return self.store.add_odometer(self.vehicle_id, {
            "date": day, "odometer": value, "unit": unit, "note": note,
            "commandId": command_id or str(uuid.uuid4()),
        })

    def test_create_defaults_projection_states_and_prompt_boundary(self):
        self.assertEqual(SCHEMA, 6)
        self.assertIsNone(self.vehicle["annualUsage"])
        self.assertEqual(self.vehicle["readingPromptDays"], 30)
        self.assertEqual(self.vehicle["mileageEstimate"]["state"], "anchor_missing")
        self.assertEqual(self.vehicle["readingPrompt"]["state"], "needs_reading")

        self.reading("2026-12-02", "1000")
        vehicle = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual(vehicle["readingPrompt"], {
            "asOf": "2027-01-01", "timeZone": "Europe/Berlin", "state": "due",
            "intervalDays": 30, "dueDate": "2027-01-01", "reason": None,
        })
        self.assertEqual(vehicle["mileageEstimate"]["state"], "annual_usage_missing")
        self.today = date(2026, 12, 31)
        self.assertEqual(self.store.get_vehicle(self.vehicle_id)["readingPrompt"]["state"], "not_due")

    def test_exact_fixed_365_day_projection_zero_rate_and_prompt_disable(self):
        self.store.update_vehicle(self.vehicle_id, {
            "revision": 1, "annualUsage": "100.125", "readingPromptDays": None,
        })
        self.reading("2026-01-01", "1234.125")
        result = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual(result["mileageEstimate"], {
            "asOf": "2027-01-01", "timeZone": "Europe/Berlin", "state": "estimated",
            "annualUsage": "100.125", "unit": "km",
            "anchor": {"id": 1, "date": "2026-01-01", "odometer": "1234.125", "unit": "km"},
            "elapsedDays": 365, "estimatedOdometer": "1334.25",
        })
        self.assertEqual(result["readingPrompt"]["state"], "disabled")
        self.assertIsNone(result["readingPrompt"]["dueDate"])

        result = self.store.update_vehicle(self.vehicle_id, {
            "revision": result["revision"], "annualUsage": "0",
        })
        self.assertEqual(result["mileageEstimate"]["state"], "estimated")
        self.assertEqual(result["mileageEstimate"]["estimatedOdometer"], "1234.125")
        self.assertIsNone(result["readingPromptDays"])

    def test_latest_actual_tie_wins_and_correction_reanchors_projection(self):
        self.store.update_vehicle(self.vehicle_id, {"revision": 1, "annualUsage": "365"})
        first = self.reading("2026-01-01", "100")
        second = self.reading("2026-01-01", "200")
        result = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual(result["mileageEstimate"]["anchor"]["id"], second["id"])
        self.assertEqual(result["mileageEstimate"]["estimatedOdometer"], "565")
        self.assertEqual(first["id"], second["id"] - 1)

        self.store.correct_odometer_reading(self.vehicle_id, second["id"], {
            "revision": 1, "date": "2027-01-01", "odometer": "250", "note": "corrected",
            "commandId": str(uuid.uuid4()), "correctionReason": "Synthetic correction",
        })
        changed = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual(changed["mileageEstimate"]["anchor"]["odometer"], "250")
        self.assertEqual(changed["mileageEstimate"]["elapsedDays"], 0)
        self.assertEqual(changed["mileageEstimate"]["estimatedOdometer"], "250")
        self.assertEqual(changed["readingPrompt"]["dueDate"], "2027-01-31")

    def test_future_mismatch_and_out_of_range_never_extrapolate_or_convert(self):
        self.store.update_vehicle(self.vehicle_id, {"revision": 1, "annualUsage": "100"})
        self.reading("2027-01-02", "1000")
        future = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual(future["mileageEstimate"]["state"], "future_anchor")
        self.assertIsNone(future["mileageEstimate"]["estimatedOdometer"])
        self.assertEqual((future["readingPrompt"]["state"], future["readingPrompt"]["reason"]),
                         ("needs_review", "future_anchor"))

        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE odometer_readings SET day='2026-01-01',unit='mi' WHERE id=1")
        mismatch = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual(mismatch["mileageEstimate"]["state"], "unit_mismatch")
        self.assertEqual((mismatch["readingPrompt"]["state"], mismatch["readingPrompt"]["reason"]),
                         ("needs_review", "unit_mismatch"))

        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE odometer_readings SET unit='km',value='1000000000' WHERE id=1")
        self.today = date(2027, 1, 2)
        overflow = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual(overflow["mileageEstimate"]["state"], "out_of_range")
        self.assertIsNone(overflow["mileageEstimate"]["estimatedOdometer"])

    def test_vehicle_validation_omission_preserves_and_unit_change_requires_rate_decision(self):
        created = self.store.update_vehicle(self.vehicle_id, {
            "revision": 1, "annualUsage": "0010.500", "readingPromptDays": 45,
        })
        self.assertEqual((created["annualUsage"], created["readingPromptDays"]), ("10.5", 45))
        preserved = self.store.update_vehicle(self.vehicle_id, {
            "revision": created["revision"], "name": "Updated name",
        })
        self.assertEqual((preserved["annualUsage"], preserved["readingPromptDays"]), ("10.5", 45))
        with self.assertRaises(Conflict):
            self.store.update_vehicle(self.vehicle_id, {
                "revision": preserved["revision"], "odometerUnit": "mi",
            })
        changed = self.store.update_vehicle(self.vehicle_id, {
            "revision": preserved["revision"], "odometerUnit": "mi", "annualUsage": None,
        })
        self.assertEqual(changed["odometerUnit"], "mi")
        self.assertIsNone(changed["annualUsage"])

        for annual, prompt in ((100.0, 30), ("1e3", 30), ("1.0000", 30), ("1000000000.001", 30),
                               (None, True), (None, 0), (None, 3651)):
            with self.subTest(annual=annual, prompt=prompt), self.assertRaises(ValidationError):
                self.store.update_vehicle(self.vehicle_id, {
                    "revision": changed["revision"], "annualUsage": annual, "readingPromptDays": prompt,
                })

    def test_reading_prompt_due_date_overflow_is_needs_review(self):
        self.store.update_vehicle(self.vehicle_id, {"revision": 1, "readingPromptDays": 3650})
        self.reading("9999-12-31", "10")
        self.today = date(9999, 12, 31)
        result = self.store.get_vehicle(self.vehicle_id)
        self.assertEqual((result["readingPrompt"]["state"], result["readingPrompt"]["reason"]),
                         ("needs_review", "date_out_of_range"))

    def test_upgrade_schema5_preserves_provenance_and_sets_defaults(self):
        path = Path(self.temp.name) / "legacy5.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.executescript((FIXTURES / "schema5_fixture.txt").read_text(encoding="utf-8"))
        backup = Path(self.temp.name) / "schema5-before.sqlite3"
        legacy = Store(path)
        self.assertTrue(legacy.upgrade(backup))
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 6)
            self.assertEqual(db.execute("SELECT annual_usage,reading_prompt_days FROM vehicles WHERE id=7").fetchone(),
                             (None, 30))
            self.assertEqual(db.execute("SELECT id,revision,provenance,source_record_id FROM odometer_readings ORDER BY id").fetchall(),
                             [(17, 3, "legacy_unknown", None), (18, 4, "record", 11),
                              (19, 2, "manual", None)])
        with closing(sqlite3.connect(backup)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 5)
        self.assertEqual(legacy.get_vehicle(7)["readingPrompt"]["state"], "due")

    def test_schema6_backup_restore_is_strict_and_preserves_raw_settings(self):
        self.store.update_vehicle(self.vehicle_id, {
            "revision": 1, "annualUsage": "125.005", "readingPromptDays": 365,
        })
        backup = Path(self.temp.name) / "schema6-backup.sqlite3"
        restored = Path(self.temp.name) / "schema6-restored.sqlite3"
        self.store.backup(backup)
        self.store.restore_backup(backup, restored)
        recovered = Store(restored, today_provider=lambda: self.today).get_vehicle(self.vehicle_id)
        self.assertEqual((recovered["annualUsage"], recovered["readingPromptDays"]), ("125.005", 365))

        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE vehicles SET annual_usage='1e3' WHERE id=?", (self.vehicle_id,))
        invalid_backup = Path(self.temp.name) / "invalid-settings.sqlite3"
        with self.assertRaises(sqlite3.DatabaseError):
            self.store.backup(invalid_backup)
        self.assertFalse(invalid_backup.exists())

    def test_projection_is_not_written_to_history_or_export(self):
        self.store.update_vehicle(self.vehicle_id, {"revision": 1, "annualUsage": "1"})
        self.reading("2026-01-01", "50")
        export = self.store.export_data()
        self.assertEqual(export["formatVersion"], 4)
        self.assertEqual(export["vehicles"][0]["annualUsage"], "1")
        self.assertEqual(export["vehicles"][0]["readingPromptDays"], 30)
        encoded = json.dumps(export)
        self.assertNotIn('"mileageEstimate":', encoded)
        self.assertNotIn('"readingPrompt":', encoded)
        history = self.store.list_history(self.vehicle_id)
        encoded_history = json.dumps(history)
        self.assertNotIn('"mileageEstimate":', encoded_history)
        self.assertNotIn('"readingPrompt":', encoded_history)

    def test_provider_is_called_once_for_vehicle_list_and_summary(self):
        before = self.calls
        self.store.list_vehicles()
        self.assertEqual(self.calls - before, 1)
        before = self.calls
        self.store.get_summary(self.vehicle_id)
        self.assertEqual(self.calls - before, 1)


if __name__ == "__main__":
    unittest.main()
