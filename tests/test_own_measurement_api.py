"""Synthetic HTTP acceptance for linked and manual measurement corrections."""
from contextlib import closing
import sqlite3
import tempfile
from pathlib import Path
import unittest
import uuid

from wolfs_garage.api import create_app
from wolfs_garage.store import Store


class MeasurementCorrectionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        Store(self.path).initialize()
        self.config = {"TESTING": True, "GARAGE_DB": str(self.path),
                       "GARAGE_PUBLIC_ORIGIN": "https://garage.test"}
        self.client = create_app(self.config).test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}
        self.vehicle = self.send("POST", "/garage-api/vehicles", {
            "make": "Synthetic", "model": "Measurement", "odometerUnit": "km"}).json
        self.base = f'/garage-api/vehicles/{self.vehicle["id"]}'

    def send(self, method, path, data=None, *, headers=None, client=None, base="https://garage.test"):
        return (client or self.client).open(path, method=method, base_url=base, json=data,
                                             headers=self.headers if headers is None else headers)

    def create_record(self, *, day="2026-01-10", value="1234.125"):
        response = self.send("POST", self.base + "/records", {
            "description": "Synthetic linked work", "kind": "service", "date": day,
            "odometer": value, "commandId": str(uuid.uuid4())})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.json["record"]

    def linked_payload(self, record, reading, **overrides):
        return {"revision": record["revision"], "readingRevision": reading["revision"],
                "date": "2026-01-11", "odometer": "1234.250",
                "commandId": str(uuid.uuid4()), "correctionReason": "Synthetic source document verified.",
                **overrides}

    def test_linked_measurement_correction_updates_both_facts_and_audits_exact_values(self):
        record = self.create_record()
        path = self.base + f'/records/{record["id"]}/measurement'
        before = self.send("GET", path)
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json["correctionMode"], "linked")
        reading = before.json["sourceReading"]
        self.assertEqual((reading["provenance"], reading["sourceRecordId"], reading["odometerExact"]),
                         ("record", record["id"], "1234.125"))

        payload = self.linked_payload(record, reading, date="2026-01-09", odometer="0")
        corrected = self.send("PUT", path, payload)
        self.assertEqual(corrected.status_code, 200, corrected.get_json())
        self.assertEqual((corrected.json["record"]["date"], corrected.json["record"]["odometer"]),
                         ("2026-01-09", 0))
        self.assertEqual((corrected.json["record"]["revision"], corrected.json["reading"]["revision"]), (2, 2))
        self.assertEqual((corrected.json["reading"]["date"], corrected.json["reading"]["odometerExact"]),
                         ("2026-01-09", "0"))
        self.assertEqual(corrected.json["reading"]["sourceRecordId"], record["id"])
        self.assertEqual(corrected.json["currentReadingBefore"]["odometerExact"], "1234.125")
        self.assertEqual(corrected.json["currentReadingAfter"]["odometerExact"], "0")

        replay = self.send("PUT", path, payload)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json, corrected.json)
        events = self.send("GET", self.base + "/history").json["events"]
        event = next(item for item in events if item["action"] == "record.measurement-corrected")
        self.assertEqual(event["after"]["correctionReason"], payload["correctionReason"])
        self.assertEqual(event["before"]["record"]["odometer"], 1234.125)
        self.assertEqual(event["after"]["record"]["odometer"], 0)
        self.assertEqual(event["before"]["reading"]["odometerExact"], "1234.125")
        self.assertEqual(event["after"]["reading"]["odometerExact"], "0")

    def test_linked_measurement_rejects_stale_revisions_invalid_values_and_locked_unit(self):
        record = self.create_record()
        path = self.base + f'/records/{record["id"]}/measurement'
        source = self.send("GET", path).json
        reading = source["sourceReading"]
        valid = self.linked_payload(record, reading)
        for change in ({"revision": record["revision"] - 1},
                       {"readingRevision": reading["revision"] - 1}):
            stale = self.send("PUT", path, {**valid, "commandId": str(uuid.uuid4()), **change})
            self.assertEqual(stale.status_code, 409, stale.get_json())
        self.assertEqual(self.send("PUT", path, {**valid, "commandId": str(uuid.uuid4()), "odometer": "1.0001"}).status_code, 400)
        self.assertEqual(self.send("PUT", path, {**valid, "commandId": str(uuid.uuid4()), "unit": "mi"}).status_code, 400)
        noop = {**valid, "date": record["date"], "odometer": record["odometer"]}
        self.assertEqual(self.send("PUT", path, {**noop, "commandId": str(uuid.uuid4())}).status_code, 400)
        self.assertEqual(self.send("GET", path).json["record"], record)

    def test_manual_reading_correction_is_separate_and_cannot_edit_linked_reading(self):
        created = self.send("POST", self.base + "/odometer", {
            "date": "2026-02-01", "odometer": "500.125", "unit": "km",
            "note": "Synthetic manual note", "commandId": str(uuid.uuid4())})
        self.assertEqual(created.status_code, 201, created.get_json())
        reading = created.json
        path = self.base + f'/odometer/{reading["id"]}'
        self.assertEqual(self.send("GET", path).json["reading"]["provenance"], "manual")
        payload = {"revision": reading["revision"], "date": "2026-02-02", "odometer": "0.001",
                   "note": "Verified synthetic correction", "commandId": str(uuid.uuid4()),
                   "correctionReason": "Transcription checked against synthetic note."}
        corrected = self.send("PUT", path, payload)
        self.assertEqual(corrected.status_code, 200, corrected.get_json())
        self.assertEqual(corrected.json["reading"]["odometerExact"], "0.001")
        self.assertEqual(corrected.json["reading"]["revision"], 2)
        self.assertEqual(corrected.json["reading"]["provenance"], "manual")
        linked = self.create_record(day="2026-02-03", value="700")
        linked_reading = self.send("GET", self.base + f'/records/{linked["id"]}/measurement').json["sourceReading"]
        rejected = self.send("PUT", self.base + f'/odometer/{linked_reading["id"]}', {
            **payload, "revision": linked_reading["revision"], "commandId": str(uuid.uuid4())})
        self.assertEqual(rejected.status_code, 409)

    def test_legacy_unknown_reading_requires_explicit_matching_record_confirmation(self):
        record = self.create_record(day="2026-03-01", value="800.125")
        path = self.base + f'/records/{record["id"]}/measurement'
        reading = self.send("GET", path).json["sourceReading"]
        # Model a genuine schema-4 row after migration: old records/readings had
        # no durable association, so no link may be inferred from their note.
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE odometer_readings SET provenance='legacy_unknown',source_record_id=NULL WHERE id=?", (reading["id"],))
        before = self.send("GET", path).json
        self.assertEqual(before["correctionMode"], "legacy_unresolved")
        locked = self.send("PUT", path, {
            "revision": record["revision"], "readingRevision": None,
            "date": "2026-03-02", "odometer": None,
            "commandId": str(uuid.uuid4()), "correctionReason": "Synthetic legacy source is not yet confirmed.",
        })
        self.assertEqual(locked.status_code, 409, locked.get_json())
        self.assertEqual(self.send("GET", path).json["record"], record)
        unknown_path = self.base + f'/odometer/{reading["id"]}'
        unknown = self.send("GET", unknown_path).json["reading"]
        resolution = {"revision": unknown["revision"], "commandId": str(uuid.uuid4()),
                      "provenance": "record", "sourceRecordId": record["id"],
                      "recordRevision": record["revision"],
                      "correctionReason": "Owner verified the synthetic record and reading."}
        resolved = self.send("PUT", unknown_path + "/provenance", resolution)
        self.assertEqual(resolved.status_code, 200, resolved.get_json())
        self.assertEqual(resolved.json["reading"]["provenance"], "record")
        self.assertEqual(resolved.json["reading"]["sourceRecordId"], record["id"])
        replay = self.send("PUT", unknown_path + "/provenance", resolution)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json, resolved.json)

    def test_date_only_legacy_record_and_vehicle_scoped_not_found(self):
        record = self.send("POST", self.base + "/records", {
            "description": "Synthetic date-only record", "kind": "repair", "date": "2026-04-01",
            "commandId": str(uuid.uuid4())}).json["record"]
        path = self.base + f'/records/{record["id"]}/measurement'
        self.assertEqual(self.send("GET", path).json["correctionMode"], "date_only")
        payload = {"revision": record["revision"], "readingRevision": None,
                   "date": "2026-04-02", "odometer": None,
                   "commandId": str(uuid.uuid4()), "correctionReason": "Synthetic date checked."}
        response = self.send("PUT", path, payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIsNone(response.json["reading"])
        self.assertEqual(response.json["record"]["date"], "2026-04-02")
        other = self.send("POST", "/garage-api/vehicles", {"make": "Synthetic", "model": "Other"}).json
        self.assertEqual(self.send("GET", f'/garage-api/vehicles/{other["id"]}/records/{record["id"]}/measurement').status_code, 404)

    def test_capability_routes_and_write_host_boundary(self):
        capabilities = self.send("GET", "/garage-api/capabilities").json
        self.assertIn("measurementCorrections", capabilities["features"])
        record = self.create_record()
        path = self.base + f'/records/{record["id"]}/measurement'
        self.assertEqual(self.send("GET", path).status_code, 200)
        denied = self.send("PUT", path, {"bad": True}, headers={})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(self.send("GET", path, base="https://foreign.test").status_code, 400)


if __name__ == "__main__":
    unittest.main()
