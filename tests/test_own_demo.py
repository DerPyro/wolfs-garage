import contextlib
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

from wolfs_garage.demo import create_demo_app


def _write(client, generation, path, payload):
    response = client.post(path, json=payload, headers={
        "Origin": "http://localhost:8080", "X-Garage-Request": "1",
        "X-Garage-Demo-Generation": generation,
    }, base_url="http://localhost:8080")
    response.get_data()
    response.close()
    return response


def _get(client, path, **kwargs):
    response = client.get(path, base_url="http://localhost:8080", **kwargs)
    response.get_data()
    response.close()
    return response


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_demo_seeded_and_restricted(self):
        canary = self.tmp_path / "owner.sqlite3"
        canary.write_bytes(b"owner database must remain untouched")
        app = create_demo_app({"GARAGE_DB": str(canary)}, temp_parent=self.tmp_path)
        client = app.test_client()
        caps_response = _get(client, "/garage-api/capabilities")
        caps = caps_response.get_json()
        generation = caps["demo"]["generation"]
        self.assertIs(caps["demo"]["shared"], True)
        self.assertTrue(caps["demo"]["resetAt"].endswith("+00:00"))
        self.assertNotIn("dataExport", caps["features"])
        self.assertNotIn("databaseBackup", caps["features"])
        self.assertEqual(caps_response.headers["X-Garage-Demo-Generation"], generation)
        self.assertEqual(caps_response.headers["X-Robots-Tag"], "noindex, nofollow")

        vehicles = _get(client, "/garage-api/vehicles").get_json()["vehicles"]
        self.assertEqual(len(vehicles), 5)
        self.assertGreaterEqual({v["model"] for v in vehicles}, {"508", "WR250F", "Combo", "SV650"})
        self.assertTrue(all(v["licensePlate"].startswith("DEMO-") for v in vehicles))
        statuses = [_get(client, f"/garage-api/vehicles/{v['id']}/status").get_json() for v in vehicles]
        self.assertGreater(len({s["readiness"] for s in statuses}), 1)
        self.assertTrue(any(s["issues"] for s in statuses))
        self.assertTrue(_get(client, f"/garage-api/vehicles/{vehicles[0]['id']}/odometer").get_json()["readings"])
        self.assertTrue(_get(client, f"/garage-api/vehicles/{vehicles[0]['id']}/records").get_json()["records"])
        self.assertEqual(_get(client, "/garage-api/export").status_code, 404)
        self.assertEqual(_get(client, "/garage-api/backup").status_code, 404)

        blocked_doc = _write(client, generation, f"/garage-api/vehicles/{vehicles[0]['id']}/records", {
            "description": "Demo record", "kind": "service", "date": "2026-11-08",
            "documentUrl": "https://example.invalid/doc", "commandId": "a9c11e194cd1486a9d00a49ec548df01",
        })
        self.assertEqual(blocked_doc.status_code, 400)
        self.assertEqual(canary.read_bytes(), b"owner database must remain untouched")

    def test_demo_writes_and_reset_generation(self):
        now = [100.0]
        app = create_demo_app(monotonic=lambda: now[0], temp_parent=self.tmp_path)
        client = app.test_client()
        old = _get(client, "/garage-api/capabilities").get_json()["demo"]["generation"]
        valid = {"make": "Demo", "model": "One", "licensePlate": "DEMO-ONE", "vehicleType": "car"}
        self.assertEqual(_write(client, old, "/garage-api/vehicles", valid).status_code, 201)
        self.assertEqual(_write(client, old, "/garage-api/vehicles/1/odometer", {
            "date": "2026-10-01", "odometer": "12345", "unit": "km", "commandId": "a9c11e194cd1486a9d00a49ec548df01",
        }).status_code, 201)
        self.assertEqual(_write(client, old, "/garage-api/vehicles/1/records", {
            "description": "Demo inspection", "kind": "service", "date": "2026-10-02",
            "cost": "125.00", "currency": "EUR", "commandId": "b9c11e194cd1486a9d00a49ec548df01",
        }).status_code, 201)

        no_generation = client.post("/garage-api/vehicles", json=valid,
            headers={"Origin": "http://localhost:8080", "X-Garage-Request": "1"},
            base_url="http://localhost:8080")
        self.assertEqual(no_generation.status_code, 409)
        no_generation.close()
        bad_origin = client.post("/garage-api/vehicles", json=valid,
            headers={"Origin": "http://attacker.invalid", "X-Garage-Request": "1",
                     "X-Garage-Demo-Generation": old}, base_url="http://localhost:8080")
        self.assertEqual(bad_origin.status_code, 403)
        bad_origin.close()

        now[0] += 3600
        new = _get(client, "/garage-api/capabilities").get_json()["demo"]["generation"]
        self.assertNotEqual(new, old)
        self.assertEqual(len(_get(client, "/garage-api/vehicles").get_json()["vehicles"]), 5)
        stale = _write(client, old, "/garage-api/vehicles", valid)
        self.assertEqual(stale.status_code, 409)
        self.assertIn("zurückgesetzt", stale.get_json()["error"])
        self.assertEqual(stale.headers["X-Garage-Demo-Generation"], new)

    def test_quota_rolls_back_and_response_close_serializes_reset(self):
        now = [10.0]
        app = create_demo_app(monotonic=lambda: now[0], temp_parent=self.tmp_path)
        client = app.test_client()
        generation = _get(client, "/garage-api/capabilities").get_json()["demo"]["generation"]
        payload = {"make": "Demo", "model": "Vehicle", "licensePlate": "DEMO-X", "vehicleType": "car"}
        for index in range(15):
            payload["name"] = str(index)
            self.assertEqual(_write(client, generation, "/garage-api/vehicles", payload).status_code, 201)
        payload["name"] = "over quota"
        self.assertEqual(_write(client, generation, "/garage-api/vehicles", payload).status_code, 400)
        self.assertEqual(len(_get(client, "/garage-api/vehicles").get_json()["vehicles"]), 20)

        store = app._app.extensions["garage_store"]
        with contextlib.closing(store._connect()) as db:
            history_count = db.execute("SELECT COUNT(*) FROM history").fetchone()[0]
        store.QUOTAS = {**store.QUOTAS, "history": history_count}
        history_limit = _write(client, generation, "/garage-api/vehicles", {
            "make": "Demo", "model": "Rollback", "licensePlate": "DEMO-ROLLBACK", "vehicleType": "car",
        })
        self.assertEqual(history_limit.status_code, 400)
        self.assertIn("Demo-Speicherlimit", history_limit.get_json()["error"])
        self.assertEqual(len(_get(client, "/garage-api/vehicles").get_json()["vehicles"]), 20)
        with contextlib.closing(store._connect()) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM history").fetchone()[0], history_count)

        first = client.get("/garage-api/vehicles", base_url="http://localhost:8080", buffered=False)
        old_dir = app._directory
        now[0] += 3600
        finished = threading.Event()

        def rotate():
            _get(client, "/garage-api/capabilities")
            finished.set()

        worker = threading.Thread(target=rotate)
        worker.start()
        time.sleep(0.05)
        self.assertFalse(finished.is_set())
        self.assertTrue(os.path.isdir(old_dir))
        first.close()
        worker.join(timeout=2)
        self.assertTrue(finished.is_set())
        self.assertFalse(os.path.exists(old_dir))
