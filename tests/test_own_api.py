"""Synthetic HTTP boundary and standalone workflow checks."""
import tempfile
from pathlib import Path
import unittest
import uuid

from wolfs_garage.api import create_app, public_origin
from wolfs_garage.store import Store


class StandaloneApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "garage.sqlite3"
        Store(self.path).initialize()
        self.config = {"TESTING": True, "GARAGE_DB": str(self.path), "GARAGE_PUBLIC_ORIGIN": "https://garage.test"}
        self.app = create_app(self.config)
        self.client = self.app.test_client()
        self.headers = {"Origin": "https://garage.test", "X-Garage-Request": "1"}

    def send(self, method, path, data=None, headers=None):
        return self.client.open(path, method=method, base_url="https://garage.test", json=data,
                                headers=self.headers if headers is None else headers)

    def create(self):
        response = self.send("POST", "/garage-api/vehicles", {"make": "Demo", "model": "Test", "vehicleType": "Limousine"})
        self.assertEqual(response.status_code, 201)
        return response.json

    def test_standalone_creation_update_and_no_native_dependency(self):
        self.assertEqual(self.send("GET", "/garage-api/capabilities").json["backend"], "standalone")
        vehicle = self.create()
        updated = self.send("PUT", f'/garage-api/vehicles/{vehicle["id"]}', {"model": "Korrektur", "revision": vehicle["revision"]})
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json["id"], vehicle["id"])
        self.assertEqual(updated.json["status"]["readiness"], "unknown")
        self.assertEqual(self.send("GET", "/Home").status_code, 404)

    def test_write_origin_header_content_type_and_host_guards(self):
        for headers in ({}, {"Origin": "https://foreign.test", "X-Garage-Request": "1"},
                        {"Origin": "https://garage.test"}, {**self.headers, "Sec-Fetch-Site": "cross-site"}):
            with self.subTest(headers=headers):
                self.assertEqual(self.send("POST", "/garage-api/vehicles", {"make": "Demo", "model": "Test"}, headers).status_code, 403)
        response = self.client.post("/garage-api/vehicles", base_url="https://garage.test", headers=self.headers,
                                    data="{}", content_type="text/plain")
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.client.get("/garage-api/vehicles", base_url="https://foreign.test").status_code, 400)
        self.assertEqual(self.send("GET", "/garage-api/vehicles").json, {"vehicles": []})

    def test_atomic_repair_completion_replay_and_restart(self):
        vehicle = self.create()
        base = f'/garage-api/vehicles/{vehicle["id"]}'
        status = self.send("PUT", base + "/status", {"readiness": "not_ready", "revision": 0,
                           "issues": [{"text": "Testreparatur"}, {"text": "Weitere Arbeit"}]}).json
        data = {"description": "Testreparatur erledigt", "kind": "repair", "date": "2026-10-28",
                "odometer": 1234, "cost": "12.30", "currency": "EUR", "closeIssueId": status["issues"][0]["id"],
                "statusRevision": status["revision"], "commandId": str(uuid.uuid4()), "documentUrl": "https://documents.example.test/record/1"}
        response = self.send("POST", base + "/records", data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["status"]["readiness"], "not_ready")
        self.assertEqual(len(response.json["status"]["issues"]), 1)
        self.assertEqual(self.send("POST", base + "/records", data).json, response.json)
        client = create_app(self.config).test_client()
        summary = client.get(base + "/summary", base_url="https://garage.test").json
        self.assertEqual(len(summary["services"]), 1)
        self.assertEqual(summary["services"][0]["cost"], "12.30")
        self.assertEqual(summary["vehicle"]["odometer"], 1234)
        self.assertTrue(self.send("GET", base + "/history").json["events"])

    def test_invalid_inputs_and_unavailable_store_fail_closed(self):
        self.assertEqual(self.send("POST", "/garage-api/vehicles", []).status_code, 400)
        self.assertEqual(self.send("GET", "/garage-api/vehicles/999/summary").status_code, 404)
        response = self.client.post("/garage-api/vehicles", base_url="https://garage.test", headers=self.headers,
                                    data=b"{" + b"x" * 65536, content_type="application/json")
        self.assertEqual(response.status_code, 413)
        missing = Path(self.temp.name) / "missing.sqlite3"
        client = create_app({**self.config, "GARAGE_DB": str(missing)}).test_client()
        self.assertEqual(client.get("/garage-api/vehicles", base_url="https://garage.test").status_code, 503)
        self.assertFalse(missing.exists())

    def test_static_paths_and_security_headers(self):
        response = self.send("GET", "/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])
        response.close()
        self.assertEqual(self.send("GET", "/garage-assets/../wolfs_garage/store.py").status_code, 404)

    def test_nonlocal_plain_http_and_malformed_origin_rejected(self):
        for value in ["http://example.test", "https://user:password@example.test", "https://example.test/path", "https://example.test?x=1", "https://example.test:bad"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                public_origin(value)
        self.assertEqual(public_origin("http://localhost:8080"), "http://localhost:8080")


if __name__ == "__main__":
    unittest.main()
