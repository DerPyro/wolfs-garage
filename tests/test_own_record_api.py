"""HTTP acceptance checks for the bounded completed-record correction API."""
import tempfile
import unittest
import uuid
from pathlib import Path

from wolfs_garage.api import create_app
from wolfs_garage.store import Store


class RecordCorrectionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        Store(self.path).initialize()
        self.app = create_app({"TESTING": True, "GARAGE_DB": str(self.path),
                               "GARAGE_PUBLIC_ORIGIN": "https://garage.test"})
        self.client = self.app.test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def send(self, method, path, data=None, headers=None):
        return self.client.open(path, method=method, base_url="https://garage.test", json=data,
                                headers=self.headers if headers is None else headers)

    def create_vehicle(self, make="Demo"):
        response = self.send("POST", "/garage-api/vehicles",
                             {"make": make, "model": "Car", "odometerUnit": "km"})
        self.assertEqual(response.status_code, 201)
        return response.json

    def create_record(self, vehicle_id, close_issue=False):
        status = None
        if close_issue:
            response = self.send("PUT", f"/garage-api/vehicles/{vehicle_id}/status", {
                "readiness": "not_ready", "revision": 0, "issues": [{"text": "Synthetische Arbeit offen"}],
            })
            self.assertEqual(response.status_code, 200)
            status = response.json
        response = self.send("POST", f"/garage-api/vehicles/{vehicle_id}/records", {
            "description": "Inspektion initial", "kind": "service", "date": "2026-10-20",
            "odometer": 12345, "cost": "120.00", "currency": "EUR",
            "documentUrl": "https://documents.example.test/invoice/1", "commandId": str(uuid.uuid4()),
            **({"closeIssueId": status["issues"][0]["id"], "statusRevision": status["revision"]} if status else {}),
        })
        self.assertEqual(response.status_code, 201)
        return response.json["record"]

    def correction(self, record, **changes):
        return {"revision": record["revision"], "commandId": str(uuid.uuid4()),
                "description": "Inspektion korrigiert", "kind": "repair", "cost": "98.50",
                "currency": "EUR", "documentUrl": None,
                "correctionReason": "Rechnung nach Prüfung berichtigt.", **changes}

    def test_full_replacement_get_revision_summary_and_audit(self):
        vehicle = self.create_vehicle()
        vehicle_id = vehicle["id"]
        record = self.create_record(vehicle_id, close_issue=True)
        original_readings = self.send("GET", f"/garage-api/vehicles/{vehicle_id}/odometer").json["readings"]
        original_status = self.send("GET", f"/garage-api/vehicles/{vehicle_id}/status").json
        original_vehicle = self.send("GET", f"/garage-api/vehicles/{vehicle_id}").json
        self.assertIsNotNone(record["closedIssueId"])
        path = f"/garage-api/vehicles/{vehicle_id}/records/{record['id']}"

        fetched = self.send("GET", path)
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json, record)
        payload = self.correction(record)
        corrected = self.send("PUT", path, payload)
        self.assertEqual(corrected.status_code, 200)
        current = corrected.json["record"]
        self.assertEqual(current["revision"], record["revision"] + 1)
        for field in ("description", "kind", "cost", "currency", "documentUrl"):
            self.assertEqual(current[field], payload[field])
        for field in ("id", "date", "odometer", "odometerUnit", "closedIssueId"):
            self.assertEqual(current[field], record[field])
        self.assertEqual(self.send("GET", path).json, current)

        summary = self.send("GET", f"/garage-api/vehicles/{vehicle_id}/summary").json
        self.assertEqual(summary["services"], [current])
        events = self.send("GET", f"/garage-api/vehicles/{vehicle_id}/history").json["events"]
        event = next(item for item in events if item["action"] == "record.corrected")
        self.assertEqual(event["before"], {"record": record})
        self.assertEqual(event["after"], {"record": current, "correctionReason": payload["correctionReason"]})

        # A correction changes only the work record, not its reading, issue closure,
        # readiness, status revision, or vehicle metadata/current odometer.
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle_id}/odometer").json["readings"], original_readings)
        self.assertEqual(summary["status"], original_status)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{vehicle_id}/status").json, original_status)
        current_vehicle = self.send("GET", f"/garage-api/vehicles/{vehicle_id}").json
        for field in ("id", "make", "model", "odometer", "odometerUnit", "revision"):
            self.assertEqual(current_vehicle[field], original_vehicle[field])

    def test_identical_command_retry_precedes_revision_check_and_changed_replay_conflicts(self):
        vehicle = self.create_vehicle()
        record = self.create_record(vehicle["id"])
        path = f"/garage-api/vehicles/{vehicle['id']}/records/{record['id']}"
        payload = self.correction(record)
        first = self.send("PUT", path, payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(self.send("PUT", path, payload).json, first.json)

        changed = {**payload, "description": "Andere Korrektur"}
        self.assertEqual(self.send("PUT", path, changed).status_code, 409)
        # Same corrected field values, but a different command and stale revision:
        # stale revision takes precedence over no-op validation.
        stale = {**self.correction(record), "revision": record["revision"]}
        self.assertEqual(self.send("PUT", path, stale).status_code, 409)
        events = self.send("GET", f"/garage-api/vehicles/{vehicle['id']}/history").json["events"]
        self.assertEqual(sum(item["action"] == "record.corrected" for item in events), 1)

    def test_noop_locked_fields_wrong_vehicle_and_missing_record_fail_without_partial_write(self):
        first_vehicle = self.create_vehicle("First")
        other_vehicle = self.create_vehicle("Other")
        record = self.create_record(first_vehicle["id"])
        path = f"/garage-api/vehicles/{first_vehicle['id']}/records/{record['id']}"
        initial_events = self.send("GET", f"/garage-api/vehicles/{first_vehicle['id']}/history").json["events"]

        noop = self.correction(record, description=record["description"], kind=record["kind"],
                               cost=record["cost"], currency=record["currency"],
                               documentUrl=record["documentUrl"])
        self.assertEqual(self.send("PUT", path, noop).status_code, 400)
        locked = ("date", "odometer", "odometerUnit", "unit", "odometerPolicy",
                  "closedIssueId", "id", "vehicle", "vehicleId")
        for key in locked:
            with self.subTest(locked_key=key):
                attempt = self.correction(record, **{key: record.get(key, first_vehicle["id"])})
                self.assertEqual(self.send("PUT", path, attempt).status_code, 400)

        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{other_vehicle['id']}/records/{record['id']}").status_code, 404)
        self.assertEqual(self.send("PUT", f"/garage-api/vehicles/{other_vehicle['id']}/records/{record['id']}",
                                   self.correction(record)).status_code, 404)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{first_vehicle['id']}/records/999999").status_code, 404)
        self.assertEqual(self.send("GET", path).json, record)
        self.assertEqual(self.send("GET", f"/garage-api/vehicles/{first_vehicle['id']}/history").json["events"], initial_events)

    def test_correction_payload_validation_and_write_boundary(self):
        vehicle = self.create_vehicle()
        record = self.create_record(vehicle["id"])
        path = f"/garage-api/vehicles/{vehicle['id']}/records/{record['id']}"
        invalid = [
            {"cost": 12.3}, {"cost": "1.001"}, {"cost": "NaN"}, {"cost": "-1"},
            {"cost": None, "currency": "EUR"}, {"cost": "1.00", "currency": None},
            {"currency": "eur"}, {"documentUrl": "http://example.test/a"},
            {"documentUrl": "https://user:pass@example.test/a"}, {"documentUrl": "javascript:alert(1)"},
            {"correctionReason": ""}, {"correctionReason": " "},
            {"correctionReason": "x" * 1601}, {"kind": "other"},
        ]
        for edits in invalid:
            with self.subTest(edits=edits):
                response = self.send("PUT", path, self.correction(record, **edits))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.send("GET", path).json, record)

        missing_key = self.correction(record)
        del missing_key["correctionReason"]
        self.assertEqual(self.send("PUT", path, missing_key).status_code, 400)
        extra_key = self.correction(record, date="2026-10-21")
        self.assertEqual(self.send("PUT", path, extra_key).status_code, 400)
        self.assertEqual(self.send("PUT", path, self.correction(record), headers={}).status_code, 403)
        self.assertEqual(self.send("GET", path).json, record)


if __name__ == "__main__":
    unittest.main()
