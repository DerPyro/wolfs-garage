"""Backend contract checks for completing one selected open issue with a record."""
import tempfile
from pathlib import Path
import unittest
import uuid

from wolfs_garage.store import Conflict, Store, ValidationError


class IssueCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "garage.sqlite3")
        self.store.initialize()
        self.vehicle = self.store.create_vehicle({"make": "Demo", "model": "First", "odometerUnit": "km"})
        self.other = self.store.create_vehicle({"make": "Demo", "model": "Second", "odometerUnit": "km"})

    def add_issues(self, vehicle, readiness, issues):
        return self.store.update_status(vehicle["id"], {
            "readiness": readiness,
            "revision": 0,
            "issues": issues,
        })

    def payload(self, status, issue_id, **overrides):
        return {
            "description": "Selected repair completed",
            "kind": "repair",
            "date": "2026-10-28",
            "odometer": 45678,
            "cost": "12.30",
            "currency": "EUR",
            "closeIssueId": issue_id,
            "statusRevision": status["revision"],
            "commandId": str(uuid.uuid4()),
            **overrides,
        }

    def test_completion_closes_only_selected_issue_and_preserves_manual_status(self):
        status = self.add_issues(self.vehicle, "ready", [
            {"text": "Selected work", "dueDate": "2026-10-27", "severity": "critical", "lifecycle": "observed"},
            {"text": "Retained work", "dueDate": "2026-11-12", "severity": "repair", "lifecycle": "open"},
        ])
        selected, retained = status["issues"]

        result = self.store.add_record(
            self.vehicle["id"], self.payload(status, selected["id"]),
        )

        self.assertEqual(result["record"]["closedIssueId"], selected["id"])
        self.assertEqual(result["status"]["readiness"], "ready")
        self.assertEqual(result["status"]["issues"], [retained])
        self.assertEqual(result["status"]["revision"], status["revision"] + 1)

    def test_foreign_issue_and_stale_status_cannot_close_or_create_work(self):
        own = self.add_issues(self.vehicle, "not_ready", [{"text": "Own issue"}])
        foreign = self.add_issues(self.other, "ready", [{"text": "Other vehicle issue"}])
        before_history = self.store.list_history(self.vehicle["id"])

        with self.assertRaises(Conflict):
            self.store.add_record(self.vehicle["id"], self.payload(own, foreign["issues"][0]["id"]))
        with self.assertRaises(Conflict):
            self.store.add_record(self.vehicle["id"], self.payload(
                own, own["issues"][0]["id"], statusRevision=own["revision"] - 1,
            ))

        self.assertEqual(self.store.get_status(self.vehicle["id"]), own)
        self.assertEqual(self.store.get_status(self.other["id"]), foreign)
        self.assertEqual(self.store.get_summary(self.vehicle["id"])["services"], [])
        self.assertEqual(self.store.list_odometer(self.vehicle["id"]), [])
        self.assertEqual(self.store.list_history(self.vehicle["id"]), before_history)

    def test_invalid_cost_rolls_back_and_identical_retry_is_exactly_once(self):
        status = self.add_issues(self.vehicle, "not_ready", [
            {"text": "Selected work", "dueDate": "2026-10-27", "severity": "critical"},
            {"text": "Keep open", "severity": "observation", "lifecycle": "observed"},
        ])
        selected = status["issues"][0]
        payload = self.payload(status, selected["id"])
        before_history = self.store.list_history(self.vehicle["id"])

        with self.assertRaises(ValidationError):
            self.store.add_record(self.vehicle["id"], {**payload, "cost": "12.345"})
        self.assertEqual(self.store.get_status(self.vehicle["id"]), status)
        self.assertEqual(self.store.get_summary(self.vehicle["id"])["services"], [])
        self.assertEqual(self.store.list_odometer(self.vehicle["id"]), [])
        self.assertEqual(self.store.list_history(self.vehicle["id"]), before_history)

        first = self.store.add_record(self.vehicle["id"], payload)
        after_first = self.store.list_history(self.vehicle["id"])
        retry = Store(self.store.path).add_record(self.vehicle["id"], payload)

        self.assertEqual(retry, first)
        self.assertEqual(len(self.store.get_summary(self.vehicle["id"])["services"]), 1)
        self.assertEqual(len(self.store.list_odometer(self.vehicle["id"])), 1)
        self.assertEqual(self.store.get_vehicle(self.vehicle["id"])["odometer"], 45678)
        self.assertEqual(self.store.list_history(self.vehicle["id"]), after_first)
        self.assertEqual([event["action"] for event in after_first[-2:]], ["issue.completed", "record.created"])


if __name__ == "__main__":
    unittest.main()
