"""Store-level safety checks for schema-5 measurement corrections."""
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
import uuid

from wolfs_garage.store import Conflict, NotFound, Store, ValidationError


FIXTURES = Path(__file__).parent / "fixtures"


class MeasurementStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "garage.sqlite3"
        self.store = Store(self.path)
        self.store.initialize()
        self.vehicle = self.store.create_vehicle({"make": "Synthetic", "model": "Measurements", "odometerUnit": "km"})
        self.other = self.store.create_vehicle({"make": "Synthetic", "model": "Other", "odometerUnit": "km"})

    def add_manual(self, vehicle=None, day="2026-05-01", value="12.345", note="Manual reading"):
        vehicle = vehicle or self.vehicle
        return self.store.add_odometer(vehicle["id"], {
            "date": day, "odometer": value, "unit": vehicle["odometerUnit"],
            "note": note, "commandId": str(uuid.uuid4()),
        })

    def add_record(self, *, day="2026-05-01", odometer="100.125", vehicle=None, description="Synthetic work"):
        vehicle = vehicle or self.vehicle
        return self.store.add_record(vehicle["id"], {
            "description": description, "kind": "repair", "date": day,
            "odometer": odometer, "commandId": str(uuid.uuid4()),
        })

    @staticmethod
    def measurement_payload(measurement, *, day, value, command_id=None):
        return {"revision": measurement["record"]["revision"],
                "readingRevision": measurement["sourceReading"]["revision"] if measurement["sourceReading"] else None,
                "date": day, "odometer": value, "commandId": command_id or str(uuid.uuid4()),
                "correctionReason": "Checked against synthetic source data."}

    def test_schema5_new_manual_and_work_readings_have_explicit_provenance(self):
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 6)
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            cols = [row[1] for row in db.execute("PRAGMA table_info(odometer_readings)")]
            self.assertEqual(cols[-3:], ["revision", "provenance", "source_record_id"])

        manual = self.add_manual()
        self.assertEqual((manual["odometerExact"], manual["provenance"], manual["sourceRecordId"], manual["revision"]),
                         ("12.345", "manual", None, 1))
        record = self.add_record()
        reading = next(row for row in self.store.list_odometer(self.vehicle["id"])
                       if row["sourceRecordId"] == record["record"]["id"])
        self.assertEqual((reading["odometerExact"], reading["provenance"], reading["sourceRecordId"]),
                         ("100.125", "record", record["record"]["id"]))
        with closing(sqlite3.connect(self.path)) as db, db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("""INSERT INTO odometer_readings
                    (vehicle_id,day,value,unit,note,revision,provenance,source_record_id)
                    VALUES(?,?,?,?,?,1,'manual',?)""",
                    (self.vehicle["id"], "2026-05-01", "1", "km", "invalid", record["record"]["id"]))

    def test_linked_correction_updates_exact_facts_revisions_audit_and_projection_atomically(self):
        status = self.store.update_status(self.vehicle["id"], {
            "readiness": "not_ready", "issues": [{"text": "Open synthetic issue"}], "revision": 0,
        })
        manual = self.add_manual(day="2026-06-01", value="150.000")
        record_result = self.add_record(day="2026-05-01", odometer="100.125")
        record_id = record_result["record"]["id"]
        measurement = self.store.get_record_measurement(self.vehicle["id"], record_id)
        self.assertEqual(measurement["correctionMode"], "linked")
        self.assertEqual(measurement["odometerExact"], "100.125")
        self.assertEqual(measurement["sourceReading"]["sourceRecordId"], record_id)

        payload = self.measurement_payload(measurement, day="2026-07-01", value="0")
        before_history = self.store.list_history(self.vehicle["id"])
        result = self.store.correct_record_measurement(self.vehicle["id"], record_id, payload)

        self.assertEqual(result["record"]["date"], "2026-07-01")
        self.assertEqual(result["record"]["odometer"], 0)
        self.assertEqual(result["record"]["revision"], 2)
        self.assertEqual(result["reading"]["odometerExact"], "0")
        self.assertEqual(result["reading"]["revision"], 2)
        self.assertEqual(result["reading"]["unit"], "km")
        self.assertEqual(result["reading"]["sourceRecordId"], record_id)
        self.assertEqual(result["currentReadingBefore"]["id"], manual["id"])
        self.assertEqual(result["currentReadingAfter"]["id"], result["reading"]["id"])
        self.assertEqual(self.store.get_status(self.vehicle["id"]), status)
        events = self.store.list_history(self.vehicle["id"])
        self.assertEqual(len(events), len(before_history) + 1)
        event = events[-1]
        self.assertEqual(event["action"], "record.measurement-corrected")
        self.assertEqual(event["before"]["record"]["date"], "2026-05-01")
        self.assertEqual(event["before"]["reading"]["odometerExact"], "100.125")
        self.assertEqual(event["after"]["record"], result["record"])
        self.assertEqual(event["after"]["reading"], result["reading"])
        self.assertEqual(event["after"]["correctionReason"], payload["correctionReason"])

        retry = Store(self.path).correct_record_measurement(self.vehicle["id"], record_id, payload)
        self.assertEqual(retry, result)
        self.assertEqual(self.store.list_history(self.vehicle["id"]), events)
        self.assertEqual(len(self.store.list_odometer(self.vehicle["id"])), 2)

    def test_date_only_record_and_legacy_unresolved_record_are_distinct(self):
        date_only = self.store.add_record(self.vehicle["id"], {
            "description": "No reading", "kind": "service", "date": "2026-02-01",
            "commandId": str(uuid.uuid4()),
        })["record"]
        measurement = self.store.get_record_measurement(self.vehicle["id"], date_only["id"])
        self.assertEqual(measurement["correctionMode"], "date_only")
        result = self.store.correct_record_measurement(self.vehicle["id"], date_only["id"],
            self.measurement_payload(measurement, day="2026-02-02", value=None))
        self.assertIsNone(result["reading"])
        self.assertEqual(result["record"]["date"], "2026-02-02")

        legacy = self.add_record(day="2026-03-01", odometer="50")
        reading = self.store.get_record_measurement(self.vehicle["id"], legacy["record"]["id"])["sourceReading"]
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE odometer_readings SET provenance='legacy_unknown',source_record_id=NULL WHERE id=?",
                       (reading["id"],))
        measurement = self.store.get_record_measurement(self.vehicle["id"], legacy["record"]["id"])
        self.assertEqual(measurement["correctionMode"], "legacy_unresolved")
        with self.assertRaises(Conflict):
            self.store.correct_record_measurement(self.vehicle["id"], legacy["record"]["id"],
                self.measurement_payload(measurement, day="2026-03-02", value="50"))

    def test_manual_reading_correction_rejects_float_and_preserves_retry_and_tie_order(self):
        older = self.add_manual(day="2026-05-01", value="8.125")
        latest = self.add_manual(day="2026-05-01", value="8.5")
        self.assertEqual(self.store.get_vehicle(self.vehicle["id"])["odometer"], 8.5)
        detail = self.store.get_odometer_reading(self.vehicle["id"], older["id"])["reading"]
        payload = {"revision": detail["revision"], "date": "2026-05-02", "odometer": "9.007",
                   "note": "Corrected note", "commandId": str(uuid.uuid4()),
                   "correctionReason": "Verified against synthetic receipt."}
        result = self.store.correct_odometer_reading(self.vehicle["id"], older["id"], payload)
        self.assertEqual(result["reading"]["odometerExact"], "9.007")
        self.assertEqual(result["reading"]["revision"], 2)
        self.assertEqual(result["currentReadingBefore"]["id"], latest["id"])
        self.assertEqual(result["currentReadingAfter"]["id"], older["id"])
        events = self.store.list_history(self.vehicle["id"])
        self.assertEqual(events[-1]["action"], "odometer.corrected")
        self.assertEqual(self.store.correct_odometer_reading(self.vehicle["id"], older["id"], payload), result)
        self.assertEqual(self.store.list_history(self.vehicle["id"]), events)
        for invalid in (9.007, "1e2", "+1", "-1", "1.0000", "1.", "1000000000.001"):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                self.store.correct_odometer_reading(self.vehicle["id"], older["id"],
                    {**payload, "revision": 2, "commandId": str(uuid.uuid4()), "odometer": invalid})

    def test_legacy_provenance_requires_explicit_exact_same_vehicle_selection(self):
        path = self.root / "legacy4.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.executescript((FIXTURES / "schema3_fixture.txt").read_text())
            db.execute("ALTER TABLE vehicles ADD COLUMN inspection_due_month TEXT")
            db.execute("UPDATE meta SET schema=4")
            db.execute("INSERT INTO odometer_readings(id,vehicle_id,day,value,unit,note) VALUES(20,7,'2025-04-05','1000','km','Record 11')")
            db.execute("UPDATE sqlite_sequence SET seq=88 WHERE name='odometer_readings'")
            db.commit()
        legacy_store = Store(path)
        backup = self.root / "schema4-before.sqlite3"
        self.assertTrue(legacy_store.upgrade(backup))
        with closing(sqlite3.connect(path)) as db:
            self.assertEqual(db.execute("SELECT seq FROM sqlite_sequence WHERE name='odometer_readings'").fetchone()[0], 88)
            self.assertEqual(db.execute("SELECT id,revision,provenance,source_record_id FROM odometer_readings WHERE id=20").fetchone(),
                             (20, 1, "legacy_unknown", None))
            self.assertEqual(db.execute("SELECT schema FROM meta").fetchone()[0], 6)
        self.assertEqual(legacy_store.list_odometer(7)[0]["note"], "Record 11")

        before = legacy_store.get_odometer_reading(7, 20)["reading"]
        mismatch = {"revision": before["revision"], "commandId": str(uuid.uuid4()), "provenance": "record",
                    "sourceRecordId": 999, "recordRevision": 1, "correctionReason": "Owner checked source."}
        with self.assertRaises(NotFound):
            legacy_store.confirm_odometer_provenance(7, 20, mismatch)
        self.assertEqual(legacy_store.get_odometer_reading(7, 20)["reading"], before)

        wrong_vehicle = self.store.create_vehicle({"make": "Synthetic", "model": "Foreign", "odometerUnit": "km"})
        foreign_record = self.add_record(vehicle=wrong_vehicle, day="2025-04-05", odometer="1000")
        wrong = {**mismatch, "sourceRecordId": foreign_record["record"]["id"],
                 "recordRevision": foreign_record["record"]["revision"], "commandId": str(uuid.uuid4())}
        with self.assertRaises(NotFound):
            legacy_store.confirm_odometer_provenance(7, 20, wrong)

        mismatched_record = legacy_store.add_record(7, {
            "description": "Wrong value", "kind": "service", "date": "2025-04-05", "odometer": "1001",
            "commandId": str(uuid.uuid4()),
        })["record"]
        wrong = {**mismatch, "sourceRecordId": mismatched_record["id"],
                 "recordRevision": mismatched_record["revision"], "commandId": str(uuid.uuid4())}
        with self.assertRaises(Conflict):
            legacy_store.confirm_odometer_provenance(7, 20, wrong)

        selected = legacy_store.get_record(7, 11)
        valid = {**mismatch, "sourceRecordId": 11, "recordRevision": selected["revision"],
                 "commandId": str(uuid.uuid4())}
        result = legacy_store.confirm_odometer_provenance(7, 20, valid)
        self.assertEqual(result["reading"]["provenance"], "record")
        self.assertEqual(result["reading"]["sourceRecordId"], 11)
        self.assertEqual(result["reading"]["revision"], 2)
        self.assertEqual(result["record"]["revision"], selected["revision"] + 1)
        self.assertEqual(legacy_store.get_record_measurement(7, 11)["correctionMode"], "linked")
        self.assertEqual(legacy_store.list_history(7)[-1]["action"], "odometer.provenance-confirmed")
        new_id = legacy_store.add_odometer(7, {"date": "2025-04-06", "odometer": "1002", "unit": "km",
                                                     "commandId": str(uuid.uuid4())})["id"]
        self.assertEqual(new_id, 90)

    def test_empty_legacy_readings_table_preserves_sequence_high_water(self):
        path = self.root / "empty-readings-schema4.sqlite3"
        with closing(sqlite3.connect(path)) as db:
            db.executescript((FIXTURES / "schema3_fixture.txt").read_text())
            db.execute("ALTER TABLE vehicles ADD COLUMN inspection_due_month TEXT")
            db.execute("UPDATE meta SET schema=4")
            db.execute("INSERT INTO odometer_readings(id,vehicle_id,day,value,unit,note) VALUES(9,7,'2025-01-01','9','km','deleted')")
            db.execute("DELETE FROM odometer_readings")
            db.execute("UPDATE sqlite_sequence SET seq=42 WHERE name='odometer_readings'")
            db.commit()
            other_sequences = dict(db.execute("SELECT name,seq FROM sqlite_sequence WHERE name!='odometer_readings'"))
        store = Store(path)
        self.assertTrue(store.upgrade(self.root / "empty-readings-before.sqlite3"))
        with closing(sqlite3.connect(path)) as db:
            rows = db.execute("SELECT name,seq FROM sqlite_sequence WHERE name='odometer_readings'").fetchall()
            self.assertEqual(rows, [("odometer_readings", 42)])
            self.assertEqual(db.execute("SELECT count(*) FROM odometer_readings").fetchone()[0], 0)
            self.assertEqual(dict(db.execute("SELECT name,seq FROM sqlite_sequence WHERE name!='odometer_readings'")),
                             other_sequences)
        reading = store.add_odometer(7, {"date": "2025-01-02", "odometer": "10", "unit": "km",
                                          "commandId": str(uuid.uuid4())})
        self.assertEqual(reading["id"], 43)

    def test_restore_rejects_linked_fact_mismatch_without_mutating_live_or_source(self):
        record = self.add_record(day="2026-08-01", odometer="120.125")["record"]
        source = self.root / "source.sqlite3"
        self.store.backup(source)
        with closing(sqlite3.connect(source)) as db, db:
            db.execute("UPDATE records SET day='2026-08-02' WHERE id=?", (record["id"],))
        destination = self.root / "restored.sqlite3"
        before_history = self.store.list_history(self.vehicle["id"])
        before_summary = self.store.get_summary(self.vehicle["id"])
        with self.assertRaisesRegex(sqlite3.DatabaseError, "inconsistent record-reading provenance"):
            self.store.restore_backup(source, destination)
        self.assertFalse(destination.exists())
        self.assertEqual(self.store.list_history(self.vehicle["id"]), before_history)
        self.assertEqual(self.store.get_summary(self.vehicle["id"]), before_summary)

    def test_atomic_rollback_when_audit_fails_and_foreign_ids_are_scoped(self):
        record_result = self.add_record()
        measurement = self.store.get_record_measurement(self.vehicle["id"], record_result["record"]["id"])
        payload = self.measurement_payload(measurement, day="2026-05-02", value="101")
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("""CREATE TRIGGER reject_measurement_audit BEFORE INSERT ON history
                WHEN NEW.action='record.measurement-corrected'
                BEGIN SELECT RAISE(ABORT,'synthetic audit failure'); END""")
        history = self.store.list_history(self.vehicle["id"])
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.correct_record_measurement(self.vehicle["id"], record_result["record"]["id"], payload)
        self.assertEqual(self.store.get_record_measurement(self.vehicle["id"], record_result["record"]["id"]), measurement)
        self.assertEqual(self.store.list_history(self.vehicle["id"]), history)
        with self.assertRaises(NotFound):
            self.store.correct_record_measurement(self.other["id"], record_result["record"]["id"], payload)


if __name__ == "__main__":
    unittest.main()
