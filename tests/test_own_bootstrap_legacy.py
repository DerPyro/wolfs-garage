"""Synthetic tests for the bounded, empty-history legacy bootstrap."""
from contextlib import closing
import copy
import json
import os
from pathlib import Path
import sqlite3
import stat
import tempfile
import unittest

from scripts.bootstrap_legacy_empty import (
    FORMAT, RECORD_CATEGORIES, _strict_json, create_database, validate_snapshot,
)
from wolfs_garage.store import Store


def synthetic_snapshot(count=5):
    vehicles = []
    source_vehicles = []
    records = {}
    for source_id in range(101, 101 + count):
        vehicles.append({
            "id": source_id,
            "make": "Synthetic",
            "model": f"Vehicle {source_id}",
            "year": 2020,
            "licensePlate": f"TEST-{source_id}",
            "vehicleType": "Limousine",
            "name": "",
            "odometer": None,
        })
        source_vehicles.append({
            "id": source_id,
            "isElectric": False,
            "useHours": False,
            "useMPG": True,
            "legacyPrivateField": f"raw-{source_id}",
        })
        records[str(source_id)] = {category: [] for category in RECORD_CATEGORIES}
    return {
        "format": FORMAT,
        "vehicles": vehicles,
        "sourceVehicles": source_vehicles,
        "records": records,
    }


class LegacyBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.snapshot = synthetic_snapshot()
        self.snapshot_path = self.root / "private-snapshot.json"
        self.snapshot_bytes = json.dumps(self.snapshot, sort_keys=True).encode()
        self.snapshot_path.write_bytes(self.snapshot_bytes)
        self.database = self.root / "new" / "garage.sqlite3"
        self.id_map = self.root / "private" / "source-id-map.json"

    def test_creates_only_empty_schema3_vehicles_and_explicit_unit(self):
        original = self.snapshot_path.read_bytes()
        mapping = create_database(self.snapshot, self.database, self.id_map, "km")

        self.assertEqual(set(mapping), {str(v["id"]) for v in self.snapshot["vehicles"]})
        self.assertEqual(json.loads(self.id_map.read_text())[
            "sourceToLocalVehicleIds"], mapping)
        self.assertEqual(self.snapshot_path.read_bytes(), original)
        vehicles = Store(self.database).list_vehicles()
        self.assertEqual(len(vehicles), 5)
        self.assertTrue(all(v["odometer"] is None and v["odometerUnit"] == "km" for v in vehicles))
        self.assertTrue(all(v["status"]["readiness"] == "unknown" for v in vehicles))
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 3)
            for table in ("records", "odometer_readings", "commands"):
                self.assertEqual(db.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT count(*) FROM history WHERE action='vehicle.created'").fetchone()[0], 5)
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(self.database.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(self.id_map.stat().st_mode), 0o600)

    def test_unit_is_explicit_and_legacy_usehours_flag_never_selects_one(self):
        self.assertEqual({v["odometerUnit"] for v in validate_snapshot(self.snapshot, "mi")}, {"mi"})
        with self.assertRaisesRegex(ValueError, "unit is inferred"):
            validate_snapshot(self.snapshot, None)
        changed = copy.deepcopy(self.snapshot)
        changed["sourceVehicles"][0]["useHours"] = True
        self.assertEqual(validate_snapshot(changed, "km")[0]["odometerUnit"], "km")

    def test_rejects_nonempty_history_in_each_category(self):
        for category in RECORD_CATEGORIES:
            with self.subTest(category=category):
                changed = copy.deepcopy(self.snapshot)
                changed["records"]["101"][category] = [{"id": "synthetic-history"}]
                with self.assertRaisesRegex(ValueError, "history"):
                    validate_snapshot(changed, "km")

    def test_rejects_odometer_values_and_mismatched_or_duplicate_source_ids(self):
        cases = []
        changed = copy.deepcopy(self.snapshot)
        changed["vehicles"][0]["odometer"] = 123
        cases.append(changed)
        changed = copy.deepcopy(self.snapshot)
        changed["sourceVehicles"].pop()
        cases.append(changed)
        changed = copy.deepcopy(self.snapshot)
        changed["vehicles"][1]["id"] = changed["vehicles"][0]["id"]
        cases.append(changed)
        for changed in cases:
            with self.subTest(snapshot=changed):
                with self.assertRaises(ValueError):
                    validate_snapshot(changed, "km")

    def test_rejects_unknown_schema_fields_and_wrong_format(self):
        changed = copy.deepcopy(self.snapshot)
        changed["unexpected"] = []
        with self.assertRaisesRegex(ValueError, "exactly"):
            validate_snapshot(changed, "km")
        changed = copy.deepcopy(self.snapshot)
        changed["format"] = "other"
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            validate_snapshot(changed, "km")

    def test_existing_destination_or_map_is_never_replaced(self):
        self.database.parent.mkdir()
        self.database.write_bytes(b"keep database")
        with self.assertRaisesRegex(ValueError, "new paths"):
            create_database(self.snapshot, self.database, self.id_map, "km")
        self.assertEqual(self.database.read_bytes(), b"keep database")

        other_db = self.root / "other.sqlite3"
        self.id_map.parent.mkdir(exist_ok=True)
        self.id_map.write_bytes(b"keep map")
        with self.assertRaisesRegex(ValueError, "new paths"):
            create_database(self.snapshot, other_db, self.id_map, "km")
        self.assertFalse(other_db.exists())
        self.assertEqual(self.id_map.read_bytes(), b"keep map")

    def test_creation_failure_cleans_only_its_staged_artifacts(self):
        changed = copy.deepcopy(self.snapshot)
        changed["vehicles"][2]["year"] = True
        with self.assertRaises(ValueError):
            create_database(changed, self.database, self.id_map, "km")
        self.assertFalse(self.database.exists())
        self.assertFalse(self.id_map.exists())
        self.assertEqual(list(self.database.parent.glob(".*.bootstrap-*.tmp")), [])

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_values(self):
        duplicate = self.root / "duplicate.json"
        duplicate.write_text('{"format":"one","format":"two"}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            _strict_json(duplicate)
        nonfinite = self.root / "nonfinite.json"
        nonfinite.write_text('{"format":NaN}')
        with self.assertRaisesRegex(ValueError, "non-finite"):
            _strict_json(nonfinite)


if __name__ == "__main__":
    unittest.main()
