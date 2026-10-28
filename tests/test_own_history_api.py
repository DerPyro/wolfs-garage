"""Public HTTP acceptance checks for bounded vehicle history browsing."""
import tempfile
import unittest
import uuid
import sqlite3
from contextlib import closing
from pathlib import Path

from wolfs_garage.api import create_app
from wolfs_garage.store import Store


class HistoryBrowsingApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        Store(self.path).initialize()
        self.config = {"TESTING": True, "GARAGE_DB": str(self.path),
                       "GARAGE_PUBLIC_ORIGIN": "https://garage.test"}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def send(self, method, path, data=None, headers=None, base_url="https://garage.test"):
        return self.client.open(path, method=method, base_url=base_url, json=data,
                                headers=self.headers if headers is None else headers)

    def create_vehicle(self, make="Synthetic"):
        response = self.send("POST", "/garage-api/vehicles",
                             {"make": make, "model": "History", "odometerUnit": "km"})
        self.assertEqual(response.status_code, 201)
        return response.json

    def add_record(self, vehicle_id, date, description, kind="service"):
        response = self.send("POST", f"/garage-api/vehicles/{vehicle_id}/records", {
            "description": description, "kind": kind, "date": date,
            "commandId": str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 201, response.json)
        return response.json["record"]

    def add_reading(self, vehicle_id, date, odometer):
        response = self.send("POST", f"/garage-api/vehicles/{vehicle_id}/odometer", {
            "date": date, "odometer": odometer, "unit": "km", "commandId": str(uuid.uuid4()),
        })
        self.assertEqual(response.status_code, 201, response.json)
        return response.json

    def test_capability_and_same_day_keyset_pages_cover_full_shape(self):
        vehicle = self.create_vehicle()
        base = f"/garage-api/vehicles/{vehicle['id']}"
        for index in range(7):
            self.add_record(vehicle["id"], "2026-10-28", f"same day {index}")
        self.add_record(vehicle["id"], "2026-10-27", "older")
        self.assertIn("historyBrowsing", self.send("GET", "/garage-api/capabilities").json["features"])

        first = self.send("GET", base + "/records/page?limit=3")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(set(first.json), {"records", "nextCursor"})
        self.assertEqual(len(first.json["records"]), 3)
        self.assertIsInstance(first.json["nextCursor"], str)
        self.assertEqual([(r["date"], r["id"]) for r in first.json["records"]],
                         sorted([(r["date"], r["id"]) for r in first.json["records"]], reverse=True))
        self.assertTrue({"id", "description", "kind", "date", "odometer", "odometerUnit",
                         "cost", "currency", "documentUrl", "closedIssueId", "revision"}
                        <= set(first.json["records"][0]))

        all_ids = [r["id"] for r in first.json["records"]]
        cursor = first.json["nextCursor"]
        while cursor:
            page = self.send("GET", base + "/records/page?limit=3&cursor=" + cursor)
            self.assertEqual(page.status_code, 200, page.json)
            all_ids.extend(r["id"] for r in page.json["records"])
            cursor = page.json["nextCursor"]
        self.assertEqual(len(all_ids), 8)
        self.assertEqual(len(set(all_ids)), 8)
        rows = self.send("GET", base + "/records").json["records"]
        by_id = {record["id"]: record for record in rows}
        self.assertEqual([(by_id[row_id]["date"], row_id) for row_id in all_ids],
                         sorted([(by_id[row_id]["date"], row_id) for row_id in all_ids], reverse=True))

    def test_date_kind_filters_and_empty_pages(self):
        vehicle = self.create_vehicle()
        self.add_record(vehicle["id"], "2026-10-20", "included service")
        self.add_record(vehicle["id"], "2026-10-21", "included repair", "repair")
        self.add_record(vehicle["id"], "2026-10-22", "excluded future")
        base = f"/garage-api/vehicles/{vehicle['id']}"
        result = self.send("GET", base + "/records/page?from=2026-10-20&to=2026-10-21&kind=repair")
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual([r["description"] for r in result.json["records"]], ["included repair"])
        self.assertIsNone(result.json["nextCursor"])
        empty = self.send("GET", base + "/odometer/page?from=2026-10-01&to=2026-10-31")
        self.assertEqual(empty.status_code, 200)
        self.assertEqual(empty.json, {"readings": [], "nextCursor": None})

    def test_all_invalid_duplicate_and_empty_query_parameters_fail(self):
        vehicle = self.create_vehicle()
        base = f"/garage-api/vehicles/{vehicle['id']}"
        invalid = [
            "?unknown=1", "?from=", "?to=", "?limit=", "?cursor=", "?kind=",
            "?from=2026-02-30", "?from=2026-10-29&to=2026-10-28", "?to=not-a-date",
            "?limit=0", "?limit=101", "?limit=no", "?kind=other",
            "?kind=service&kind=repair", "?limit=2&limit=3", "?cursor=x&cursor=y",
            "?from=2026-10-01&from=2026-10-02", "?unknown=1&unknown=2",
        ]
        for query in invalid:
            with self.subTest(query=query):
                for resource in ("records/page", "odometer/page"):
                    response = self.send("GET", base + "/" + resource + query)
                    self.assertEqual(response.status_code, 400, (resource, query, response.json))

    def test_cursor_is_bound_to_vehicle_resource_filters_and_limit(self):
        first = self.create_vehicle("First")
        other = self.create_vehicle("Other")
        for index in range(3):
            self.add_record(first["id"], "2026-10-28", f"record {index}", "service" if index % 2 == 0 else "repair")
            self.add_reading(first["id"], "2026-10-28", 100 + index)
        base = f"/garage-api/vehicles/{first['id']}"
        cursor = self.send("GET", base + "/records/page?limit=1&kind=service").json["nextCursor"]
        self.assertTrue(cursor)
        wrong_context = [
            (f"/garage-api/vehicles/{other['id']}/records/page?limit=1&kind=service&cursor={cursor}", 400),
            (base + f"/odometer/page?limit=1&cursor={cursor}", 400),
            (base + f"/records/page?limit=2&kind=service&cursor={cursor}", 400),
            (base + f"/records/page?limit=1&kind=repair&cursor={cursor}", 400),
            (base + f"/records/page?limit=1&from=2026-10-01&cursor={cursor}", 400),
            (base + f"/records/page?limit=1&cursor=not-a-valid-cursor", 400),
        ]
        for path, status in wrong_context:
            with self.subTest(path=path):
                self.assertEqual(self.send("GET", path).status_code, status)

    def test_mutation_invalidates_cursor_across_backdated_add_correction_and_restart(self):
        vehicle = self.create_vehicle()
        base = f"/garage-api/vehicles/{vehicle['id']}"
        record_a = self.add_record(vehicle["id"], "2026-10-28", "record A", "service")
        self.add_record(vehicle["id"], "2026-10-27", "record B", "service")
        first = self.send("GET", base + "/records/page?limit=1&kind=service")
        cursor = first.json["nextCursor"]
        self.assertTrue(cursor)

        self.add_record(vehicle["id"], "2026-10-01", "backdated record", "service")
        self.assertEqual(self.send("GET", base + f"/records/page?limit=1&kind=service&cursor={cursor}").status_code, 409)

        first = self.send("GET", base + "/records/page?limit=1&kind=service")
        cursor = first.json["nextCursor"]
        path = base + f"/records/{record_a['id']}"
        corrected = {"revision": record_a["revision"], "commandId": str(uuid.uuid4()),
                     "description": "record A corrected", "kind": "repair", "cost": None,
                     "currency": None, "documentUrl": None, "correctionReason": "Corrected synthetic kind"}
        self.assertEqual(self.send("PUT", path, corrected).status_code, 200)
        self.assertEqual(self.send("GET", base + f"/records/page?limit=1&kind=service&cursor={cursor}").status_code, 409)

        self.add_reading(vehicle["id"], "2026-10-03", 30)
        self.add_reading(vehicle["id"], "2026-10-02", 20)
        first = self.send("GET", base + "/odometer/page?limit=1")
        reading_cursor = first.json["nextCursor"]
        self.assertTrue(reading_cursor)
        self.add_reading(vehicle["id"], "2026-10-01", 10)
        self.assertEqual(self.send("GET", base + f"/odometer/page?limit=1&cursor={reading_cursor}").status_code, 409)

        # The rejection survives a fresh app/client instance using the same database.
        first = self.send("GET", base + "/records/page?limit=1")
        cursor = first.json["nextCursor"]
        restarted = create_app(self.config).test_client()
        stale = restarted.get(base + f"/records/page?limit=1&cursor={cursor}", base_url="https://garage.test")
        self.assertEqual(stale.status_code, 200)
        # A separate committed mutation makes an already-issued cursor stale after restart.
        self.add_record(vehicle["id"], "2026-10-02", "another backdated", "repair")
        stale = restarted.get(base + f"/records/page?limit=1&cursor={cursor}", base_url="https://garage.test")
        self.assertEqual(stale.status_code, 409)

    def test_vehicle_isolation_host_guard_and_legacy_unpaged_routes_are_unchanged(self):
        one, two = self.create_vehicle("One"), self.create_vehicle("Two")
        record = self.add_record(one["id"], "2026-10-28", "private to one")
        reading = self.add_reading(one["id"], "2026-10-28", 777)
        for path in (f"/garage-api/vehicles/999999/records/page",
                     f"/garage-api/vehicles/{two['id']}/records/{record['id']}"):
            self.assertEqual(self.send("GET", path).status_code, 404)
        self.assertEqual(self.send("GET", "/garage-api/vehicles/" + str(one["id"]) + "/records/page",
                                   base_url="https://foreign.test").status_code, 400)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{one['id']}/records").json,
                         {"records": self.send("GET", f"/garage-api/vehicles/{one['id']}/records/page").json["records"]})
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{one['id']}/odometer").json["readings"], [reading])
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{two['id']}/records").json, {"records": []})
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{two['id']}/odometer").json, {"readings": []})

    def test_browsing_is_read_only_and_requires_no_schema_upgrade(self):
        vehicle = self.create_vehicle()
        for index in range(3):
            self.add_record(vehicle["id"], f"2026-10-{20 + index}", f"record {index}")
            self.add_reading(vehicle["id"], f"2026-10-{20 + index}", 100 + index)
        history_before = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json
        with closing(sqlite3.connect(self.path)) as db:
            schema_version = db.execute("SELECT schema FROM meta").fetchone()[0]
        for path in (f"/garage-api/vehicles/{vehicle['id']}/records/page?limit=1",
                     f"/garage-api/vehicles/{vehicle['id']}/odometer/page?limit=1"):
            response = self.send("GET", path)
            self.assertEqual(response.status_code, 200)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json, history_before)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], schema_version)


if __name__ == "__main__":
    unittest.main()
