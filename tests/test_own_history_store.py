"""Bounded, read-only history pagination checks using synthetic records."""
from contextlib import closing
import base64
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from wolfs_garage.api import create_app
from wolfs_garage.store import Conflict, NotFound, Store, ValidationError


class HistoryPageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        self.store = Store(self.path)
        self.store.initialize()
        self.vehicle = self.store.create_vehicle({"make": "Example", "model": "Car"})
        self.vehicle_id = self.vehicle["id"]

    def add_record(self, day, description, kind="service"):
        return self.store.add_record(self.vehicle_id, {
            "description": description, "kind": kind, "date": day,
            "commandId": str(uuid.uuid4()),
        })["record"]

    def add_reading(self, day, odometer, note="synthetic"):
        return self.store.add_odometer(self.vehicle_id, {
            "date": day, "odometer": odometer, "unit": "km", "note": note,
            "commandId": str(uuid.uuid4()),
        })

    def test_records_page_has_stable_ties_and_record_shape(self):
        # Insert out of display order and deliberately tie dates: ID is the
        # deterministic second sort key on every page.
        first = self.add_record("2026-02-01", "first")
        second = self.add_record("2026-03-01", "second", "repair")
        third = self.add_record("2026-03-01", "third")
        page1 = self.store.page_records(self.vehicle_id, limit=2)
        self.assertEqual([r["id"] for r in page1["records"]], [third["id"], second["id"]])
        self.assertEqual(set(page1), {"records", "nextCursor"})
        self.assertIsNotNone(page1["nextCursor"])
        page2 = self.store.page_records(self.vehicle_id, limit=2, cursor=page1["nextCursor"])
        self.assertEqual([r["id"] for r in page2["records"]], [first["id"]])
        self.assertIsNone(page2["nextCursor"])
        self.assertEqual(set(page1["records"][0]), set(third))

    def test_filters_are_inclusive_and_kind_can_be_scoped(self):
        self.add_record("2026-01-31", "before")
        repair = self.add_record("2026-02-01", "repair", "repair")
        service = self.add_record("2026-02-02", "service")
        self.add_record("2026-02-03", "after")
        result = self.store.page_records(self.vehicle_id, from_date="2026-02-01",
                                         to_date="2026-02-02", kind="repair")
        self.assertEqual([row["id"] for row in result["records"]], [repair["id"]])
        result = self.store.page_records(self.vehicle_id, from_date="2026-02-02", to_date="2026-02-02")
        self.assertEqual([row["id"] for row in result["records"]], [service["id"]])

    def test_odometer_pagination_uses_current_reading_shape_and_stable_ties(self):
        a = self.add_reading("2026-01-01", 100)
        b = self.add_reading("2026-02-01", 200)
        c = self.add_reading("2026-02-01", 201)
        page1 = self.store.page_odometer(self.vehicle_id, limit=2)
        self.assertEqual([row["id"] for row in page1["readings"]], [c["id"], b["id"]])
        page2 = self.store.page_odometer(self.vehicle_id, limit=2, cursor=page1["nextCursor"])
        self.assertEqual([row["id"] for row in page2["readings"]], [a["id"]])
        self.assertEqual(set(page1["readings"][0]), {"id", "date", "odometer", "unit", "note",
                                                     "odometerExact", "revision", "provenance", "sourceRecordId"})

    def test_cursor_rejects_mismatch_and_mutation_requires_restart(self):
        self.add_record("2026-01-01", "one")
        self.add_record("2026-01-02", "two")
        page = self.store.page_records(self.vehicle_id, limit=1)
        cursor = page["nextCursor"]
        with self.assertRaises(ValidationError):
            self.store.page_records(self.vehicle_id, limit=2, cursor=cursor)
        with self.assertRaises(ValidationError):
            self.store.page_odometer(self.vehicle_id, limit=1, cursor=cursor)
        self.add_record("2026-01-03", "new record")
        with self.assertRaises(Conflict):
            self.store.page_records(self.vehicle_id, limit=1, cursor=cursor)

    def test_cursor_rejects_boolean_or_out_of_range_sqlite_integers(self):
        data = {"v": 1, "vehicle": self.vehicle_id, "resource": "records", "from": None,
                "to": None, "kind": None, "limit": 1, "day": "2026-01-01",
                "id": 1, "sequence": 0}
        for key, invalid in (("id", True), ("id", 9223372036854775808),
                             ("vehicle", 9223372036854775808),
                             ("sequence", 9223372036854775808)):
            changed = {**data, key: invalid}
            token = base64.urlsafe_b64encode(json.dumps(changed).encode()).rstrip(b"=").decode()
            with self.subTest(key=key, invalid=invalid), self.assertRaises(ValidationError):
                self.store.page_records(self.vehicle_id, limit=1, cursor=token)
        with self.assertRaises(NotFound):
            self.store.page_records(9223372036854775808)
        with self.assertRaises(ValidationError):
            self.store.page_records(self.vehicle_id, kind={"service": True})

    def test_query_values_are_bound_and_reads_do_not_write(self):
        self.add_record("2026-01-01", "one")
        before = self.counts()
        with self.assertRaises(ValidationError):
            self.store.page_records(self.vehicle_id, from_date="2026-01-01' OR 1=1 --")
        self.assertEqual(self.counts(), before)
        for kwargs in ({"from_date": "2026-03-02", "to_date": "2026-03-01"},
                       {"limit": 0}, {"limit": 101}, {"kind": "other"}, {"cursor": "%%%"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValidationError):
                self.store.page_records(self.vehicle_id, **kwargs)
        with self.assertRaises(NotFound):
            self.store.page_odometer(999, limit=10)
        self.assertEqual(self.counts(), before)

    def counts(self):
        with closing(sqlite3.connect(self.path)) as db:
            return tuple(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                         for table in ("records", "odometer_readings", "history", "commands"))

    def test_api_rejects_unknown_and_duplicate_query_parameters(self):
        app = create_app({"TESTING": True, "GARAGE_DB": str(self.path),
                          "GARAGE_PUBLIC_ORIGIN": "https://garage.test"})
        client = app.test_client()
        base = f"https://garage.test/garage-api/vehicles/{self.vehicle_id}/records/page"
        for suffix in ("?limit=1&limit=2", "?unexpected=x", "?from=2026-02-30", "?limit=101"):
            with self.subTest(suffix=suffix):
                self.assertEqual(client.get(base + suffix).status_code, 400)
        self.assertEqual(client.get(base + "?kind=service&limit=1").status_code, 200)
        self.assertEqual(client.get(base.replace("records", "odometer") + "?kind=service").status_code, 400)


if __name__ == "__main__":
    unittest.main()
