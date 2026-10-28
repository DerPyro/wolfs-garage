"""Standalone SQLite storage; no network calls or LubeLogger dependency.

The store must be explicitly initialized. Every write and its history entry are
committed together. Application history is append-only, not protection against a
database administrator. Money stays an exact decimal string throughout storage.
"""
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit
import uuid


SCHEMA = 1
UNITS = {"km", "mi", "h"}
READINESS = {"ready", "not_ready", "unknown"}


class ValidationError(ValueError):
    """A submitted value does not satisfy the public input contract."""


class NotFound(Exception):
    """A requested local object does not exist."""


class Conflict(Exception):
    """The revision or an idempotency key conflicts with stored data."""


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fields(payload, allowed, required=()):
    if not isinstance(payload, dict) or not set(payload) <= set(allowed) or not set(required) <= set(payload):
        raise ValidationError("Invalid or missing fields.")


def _text(value, name, limit=160, required=False, multiline=False):
    if not isinstance(value, str):
        raise ValidationError(f"{name} must be text.")
    value = value.strip()
    if (required and not value) or len(value) > limit or any(
        (ord(c) < 32 and not (multiline and c in "\n\t")) or ord(c) == 127 or 0xD800 <= ord(c) <= 0xDFFF for c in value
    ):
        raise ValidationError(f"Invalid {name}.")
    return value


def _revision(value):
    if type(value) is not int or not 0 <= value <= 2147483646:
        raise ValidationError("Invalid revision.")
    return value


def _day(value):
    if not isinstance(value, str):
        raise ValidationError("Date must be YYYY-MM-DD.")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError("Date must be YYYY-MM-DD.") from exc
    if parsed.isoformat() != value:
        raise ValidationError("Date must be YYYY-MM-DD.")
    return value


def _distance(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValidationError("Invalid odometer.")
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationError("Invalid odometer.") from exc
    if not number.is_finite() or number < 0 or number > 1_000_000_000 or number.as_tuple().exponent < -3:
        raise ValidationError("Odometer must be nonnegative with at most three decimal places.")
    return format(number.normalize(), "f")


def _number(value):
    if value is None:
        return None
    number = Decimal(value)
    return int(number) if number == number.to_integral() else float(number)


def _command(value):
    if not isinstance(value, str):
        raise ValidationError("commandId must be a UUID.")
    try:
        result = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValidationError("commandId must be a UUID.") from exc
    if value not in {str(result), result.hex}:
        raise ValidationError("commandId must be a canonical UUID.")
    return result.hex


def _issue_id(value):
    if not isinstance(value, str) or len(value) != 32 or any(c not in "0123456789abcdef" for c in value):
        raise ValidationError("Invalid issue id.")
    return value


def _document(value):
    value = _text(value, "documentUrl", limit=2000)
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        valid = parsed.scheme == "https" and parsed.hostname and not parsed.username and not parsed.password
        parsed.port  # Reject malformed ports, too.
    except ValueError as exc:
        raise ValidationError("Invalid documentUrl.") from exc
    if not valid or "\\" in value or any(c.isspace() for c in value):
        raise ValidationError("documentUrl must be an HTTPS URL without credentials.")
    # A reference only: the application never fetches this URL.
    return value


class Store:
    def __init__(self, path):
        self.path = Path(path)

    def initialize(self):
        """Create schema 1 once; an existing file or symlink is never replaced."""
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                PRAGMA synchronous=FULL;
                BEGIN IMMEDIATE;
                CREATE TABLE meta(schema INTEGER NOT NULL);
                INSERT INTO meta VALUES(1);
                CREATE TABLE vehicles(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    make TEXT NOT NULL, model TEXT NOT NULL, name TEXT NOT NULL,
                    year INTEGER, license_plate TEXT NOT NULL, vehicle_type TEXT NOT NULL,
                    unit TEXT NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE states(
                    vehicle_id INTEGER PRIMARY KEY REFERENCES vehicles(id),
                    readiness TEXT NOT NULL, issues TEXT NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE odometer_readings(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    day TEXT NOT NULL, value TEXT NOT NULL, unit TEXT NOT NULL, note TEXT NOT NULL);
                CREATE TABLE records(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    description TEXT NOT NULL, kind TEXT NOT NULL, day TEXT NOT NULL,
                    odometer TEXT, unit TEXT NOT NULL, cost TEXT, currency TEXT,
                    document_url TEXT, closed_issue_id TEXT);
                CREATE TABLE commands(
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    action TEXT NOT NULL, command_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL, response TEXT NOT NULL,
                    PRIMARY KEY(vehicle_id,action,command_id));
                CREATE TABLE history(
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    action TEXT NOT NULL, occurred_at TEXT NOT NULL,
                    before_json TEXT NOT NULL, after_json TEXT NOT NULL);
                CREATE TRIGGER history_no_update BEFORE UPDATE ON history
                    BEGIN SELECT RAISE(ABORT, 'history is append-only'); END;
                CREATE TRIGGER history_no_delete BEFORE DELETE ON history
                    BEGIN SELECT RAISE(ABORT, 'history is append-only'); END;
                CREATE INDEX odometer_vehicle_date ON odometer_readings(vehicle_id,day,id);
                CREATE INDEX records_vehicle_date ON records(vehicle_id,day,id);
                COMMIT;
            """)

    def _connect(self):
        uri = self.path.resolve().as_uri() + "?mode=rw"
        db = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            if [tuple(row) for row in db.execute("SELECT schema FROM meta")] != [(SCHEMA,)]:
                raise sqlite3.DatabaseError("Unsupported standalone schema.")
            return db
        except BaseException:
            db.close()
            raise

    @contextmanager
    def _transaction(self):
        with closing(self._connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    @staticmethod
    def _status(db, vehicle_id):
        row = db.execute("SELECT readiness,issues,revision FROM states WHERE vehicle_id=?", (vehicle_id,)).fetchone()
        if row is None:
            if db.execute("SELECT 1 FROM vehicles WHERE id=?", (vehicle_id,)).fetchone():
                raise sqlite3.DatabaseError("Missing vehicle status.")
            raise NotFound("Vehicle not found.")
        try:
            issues = json.loads(row["issues"])
            if row["readiness"] not in READINESS or type(row["revision"]) is not int or row["revision"] < 0 or not isinstance(issues, list) or len(issues) > 20:
                raise ValidationError("Invalid stored status.")
            seen = set()
            for item in issues:
                _fields(item, {"id", "text"}, {"id", "text"})
                issue_id = _issue_id(item["id"])
                _text(item["text"], "issue", required=True)
                if issue_id in seen:
                    raise ValidationError("Duplicate stored issue.")
                seen.add(issue_id)
        except (ValueError, TypeError) as exc:
            raise sqlite3.DatabaseError("Invalid stored status.") from exc
        return {"readiness": row["readiness"], "issues": issues, "revision": row["revision"]}

    @staticmethod
    def _vehicle(db, vehicle_id):
        row = db.execute("SELECT * FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()
        if row is None:
            raise NotFound("Vehicle not found.")
        # The latest dated explicit reading is the current stand. Historical
        # backdated readings remain stored and never silently replace it.
        latest = db.execute("SELECT value FROM odometer_readings WHERE vehicle_id=? ORDER BY day DESC,id DESC LIMIT 1", (vehicle_id,)).fetchone()
        return {"id": row["id"], "make": row["make"], "model": row["model"],
                "name": row["name"] or f'{row["make"]} {row["model"]}', "year": row["year"],
                "licensePlate": row["license_plate"], "vehicleType": row["vehicle_type"],
                "odometer": _number(latest["value"]) if latest else None,
                "odometerUnit": row["unit"], "revision": row["revision"],
                "status": Store._status(db, vehicle_id)}

    @staticmethod
    def _audit(db, vehicle_id, action, before, after):
        db.execute("INSERT INTO history(vehicle_id,action,occurred_at,before_json,after_json) VALUES(?,?,?,?,?)",
                   (vehicle_id, action, datetime.now(timezone.utc).isoformat(), _json(before), _json(after)))

    @staticmethod
    def _vehicle_values(payload, old=None):
        allowed = {"make", "model", "name", "year", "licensePlate", "vehicleType", "odometerUnit"}
        _fields(payload, allowed | ({"revision"} if old else set()), {"revision"} if old else {"make", "model"})
        result = {"make": "", "model": "", "name": "", "year": None, "licensePlate": "", "vehicleType": "", "odometerUnit": "km"}
        if old:
            result.update({key: old[key] for key in result})
        result.update({key: value for key, value in payload.items() if key in allowed})
        for key in ("make", "model", "name", "licensePlate", "vehicleType"):
            result[key] = _text(result[key], key, required=key in {"make", "model"})
        year = result["year"]
        if year is not None and (type(year) is not int or not 1800 <= year <= 2100):
            raise ValidationError("Invalid year.")
        if not isinstance(result["odometerUnit"], str) or result["odometerUnit"] not in UNITS:
            raise ValidationError("Invalid odometerUnit.")
        return result

    def create_vehicle(self, payload):
        values = self._vehicle_values(payload)
        with self._transaction() as db:
            cursor = db.execute("INSERT INTO vehicles(make,model,name,year,license_plate,vehicle_type,unit,revision) VALUES(?,?,?,?,?,?,?,1)",
                                tuple(values[k] for k in ("make", "model", "name", "year", "licensePlate", "vehicleType", "odometerUnit")))
            vehicle_id = cursor.lastrowid
            db.execute("INSERT INTO states VALUES(?,'unknown','[]',0)", (vehicle_id,))
            result = self._vehicle(db, vehicle_id)
            self._audit(db, vehicle_id, "vehicle.created", None, result)
            return result

    def list_vehicles(self):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            return [self._vehicle(db, row[0]) for row in db.execute("SELECT id FROM vehicles ORDER BY id")]

    def get_vehicle(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            return self._vehicle(db, vehicle_id)

    def update_vehicle(self, vehicle_id, payload):
        with self._transaction() as db:
            before = self._vehicle(db, vehicle_id)
            base = dict(before)
            base["name"] = db.execute("SELECT name FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()[0]
            values = self._vehicle_values(payload, base)
            if _revision(payload["revision"]) != before["revision"]:
                raise Conflict("Vehicle revision changed.")
            if values["odometerUnit"] != before["odometerUnit"] and db.execute("SELECT 1 FROM odometer_readings WHERE vehicle_id=? LIMIT 1", (vehicle_id,)).fetchone():
                raise Conflict("A unit with recorded readings cannot be relabelled; conversion is a separate operation.")
            db.execute("UPDATE vehicles SET make=?,model=?,name=?,year=?,license_plate=?,vehicle_type=?,unit=?,revision=revision+1 WHERE id=?",
                       tuple(values[k] for k in ("make", "model", "name", "year", "licensePlate", "vehicleType", "odometerUnit")) + (vehicle_id,))
            result = self._vehicle(db, vehicle_id)
            self._audit(db, vehicle_id, "vehicle.updated", before, result)
            return result

    def get_status(self, vehicle_id):
        with closing(self._connect()) as db:
            return self._status(db, vehicle_id)

    def update_status(self, vehicle_id, payload):
        _fields(payload, {"readiness", "issues", "revision"}, {"readiness", "issues", "revision"})
        expected = _revision(payload["revision"])
        if not isinstance(payload["readiness"], str) or payload["readiness"] not in READINESS or not isinstance(payload["issues"], list) or len(payload["issues"]) > 20:
            raise ValidationError("Invalid readiness or issues.")
        with self._transaction() as db:
            before = self._status(db, vehicle_id)
            if before["revision"] != expected:
                raise Conflict("Status revision changed.")
            existing = {item["id"] for item in before["issues"]}
            issues, seen = [], set()
            for item in payload["issues"]:
                _fields(item, {"id", "text"}, {"text"})
                issue_id = _issue_id(item["id"]) if "id" in item else uuid.uuid4().hex
                if "id" in item and issue_id not in existing:
                    raise ValidationError("Unknown issue id.")
                if issue_id in seen:
                    raise ValidationError("Duplicate issue id.")
                seen.add(issue_id)
                issues.append({"id": issue_id, "text": _text(item["text"], "issue", required=True)})
            after = {"readiness": payload["readiness"], "issues": issues, "revision": expected + 1}
            db.execute("UPDATE states SET readiness=?,issues=?,revision=? WHERE vehicle_id=?", (after["readiness"], _json(issues), after["revision"], vehicle_id))
            self._audit(db, vehicle_id, "status.updated", before, after)
            return after

    @staticmethod
    def _replay(db, vehicle_id, action, command_id, payload):
        digest = hashlib.sha256(_json(payload).encode()).hexdigest()
        row = db.execute("SELECT payload_hash,response FROM commands WHERE vehicle_id=? AND action=? AND command_id=?", (vehicle_id, action, command_id)).fetchone()
        if row:
            if row["payload_hash"] != digest:
                raise Conflict("commandId was already used for different values.")
            return digest, json.loads(row["response"])
        return digest, None

    @staticmethod
    def _remember(db, vehicle_id, action, command_id, digest, response):
        db.execute("INSERT INTO commands VALUES(?,?,?,?,?)", (vehicle_id, action, command_id, digest, _json(response)))

    def add_odometer(self, vehicle_id, payload):
        _fields(payload, {"date", "odometer", "unit", "note", "commandId"}, {"date", "odometer", "unit", "commandId"})
        day, value, command_id = _day(payload["date"]), _distance(payload["odometer"]), _command(payload["commandId"])
        if not isinstance(payload["unit"], str) or payload["unit"] not in UNITS:
            raise ValidationError("Invalid unit.")
        note = _text(payload.get("note", ""), "note", 1600, multiline=True)
        with self._transaction() as db:
            vehicle = self._vehicle(db, vehicle_id)
            digest, replay = self._replay(db, vehicle_id, "odometer", command_id, payload)
            if replay is not None:
                return replay
            if payload["unit"] != vehicle["odometerUnit"]:
                raise Conflict("Odometer unit does not match vehicle.")
            cursor = db.execute("INSERT INTO odometer_readings(vehicle_id,day,value,unit,note) VALUES(?,?,?,?,?)", (vehicle_id, day, value, payload["unit"], note))
            result = {"id": cursor.lastrowid, "date": day, "odometer": _number(value), "unit": payload["unit"], "note": note}
            self._audit(db, vehicle_id, "odometer.created", None, result)
            self._remember(db, vehicle_id, "odometer", command_id, digest, result)
            return result

    def list_odometer(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._vehicle(db, vehicle_id)
            return [{"id": r["id"], "date": r["day"], "odometer": _number(r["value"]), "unit": r["unit"], "note": r["note"]}
                    for r in db.execute("SELECT * FROM odometer_readings WHERE vehicle_id=? ORDER BY day DESC,id DESC", (vehicle_id,))]

    @staticmethod
    def _record(row):
        return {"id": row["id"], "description": row["description"], "kind": row["kind"], "date": row["day"],
                "odometer": _number(row["odometer"]), "odometerUnit": row["unit"], "cost": row["cost"],
                "currency": row["currency"], "documentUrl": row["document_url"], "closedIssueId": row["closed_issue_id"]}

    def add_record(self, vehicle_id, payload):
        _fields(payload, {"description", "kind", "date", "odometer", "cost", "currency", "documentUrl", "closeIssueId", "statusRevision", "commandId"}, {"description", "kind", "date", "commandId"})
        description = _text(payload["description"], "description", required=True)
        if not isinstance(payload["kind"], str) or payload["kind"] not in {"service", "repair"}:
            raise ValidationError("Invalid record kind.")
        day, command_id = _day(payload["date"]), _command(payload["commandId"])
        odometer = _distance(payload["odometer"]) if payload.get("odometer") is not None else None
        cost, currency = None, None
        if payload.get("cost") is not None:
            if not isinstance(payload["cost"], str):
                raise ValidationError("Cost must be an exact decimal string.")
            try:
                amount = Decimal(payload["cost"])
            except InvalidOperation as exc:
                raise ValidationError("Invalid cost.") from exc
            if not amount.is_finite() or amount < 0 or amount > 1_000_000_000 or amount.as_tuple().exponent < -2:
                raise ValidationError("Cost must be nonnegative with at most two decimal places.")
            cost = format(amount.quantize(Decimal("0.01")), "f")
            currency = payload.get("currency")
            if not isinstance(currency, str) or len(currency) != 3 or not all("A" <= c <= "Z" for c in currency):
                raise ValidationError("Cost requires an uppercase three-letter currency.")
        elif payload.get("currency") is not None:
            raise ValidationError("Currency requires cost.")
        document = _document(payload["documentUrl"]) if payload.get("documentUrl") is not None else None
        issue_id = _issue_id(payload["closeIssueId"]) if payload.get("closeIssueId") is not None else None
        if issue_id:
            expected = _revision(payload.get("statusRevision"))
        elif "statusRevision" in payload:
            raise ValidationError("statusRevision requires closeIssueId.")
        with self._transaction() as db:
            vehicle = self._vehicle(db, vehicle_id)
            digest, replay = self._replay(db, vehicle_id, "record", command_id, payload)
            if replay is not None:
                return replay
            before = self._status(db, vehicle_id)
            after = before
            if issue_id:
                if before["revision"] != expected:
                    raise Conflict("Status revision changed.")
                if not any(item["id"] == issue_id for item in before["issues"]):
                    raise Conflict("The selected issue is no longer open.")
                after = {"readiness": before["readiness"], "issues": [item for item in before["issues"] if item["id"] != issue_id], "revision": before["revision"] + 1}
                db.execute("UPDATE states SET issues=?,revision=? WHERE vehicle_id=?", (_json(after["issues"]), after["revision"], vehicle_id))
                self._audit(db, vehicle_id, "issue.completed", before, after)
            cursor = db.execute("INSERT INTO records(vehicle_id,description,kind,day,odometer,unit,cost,currency,document_url,closed_issue_id) VALUES(?,?,?,?,?,?,?,?,?,?)",
                                (vehicle_id, description, payload["kind"], day, odometer, vehicle["odometerUnit"], cost, currency, document, issue_id))
            record_id = cursor.lastrowid
            record = self._record(db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone())
            if odometer is not None:
                db.execute("INSERT INTO odometer_readings(vehicle_id,day,value,unit,note) VALUES(?,?,?,?,?)", (vehicle_id, day, odometer, vehicle["odometerUnit"], f"Record {record_id}"))
            self._audit(db, vehicle_id, "record.created", None, record)
            result = {"record": record, "status": after}
            self._remember(db, vehicle_id, "record", command_id, digest, result)
            return result

    def get_summary(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            vehicle = self._vehicle(db, vehicle_id)
            records = [self._record(row) for row in db.execute("SELECT * FROM records WHERE vehicle_id=? ORDER BY day DESC,id DESC", (vehicle_id,))]
            return {"vehicle": vehicle, "status": vehicle["status"], "reminders": [], "services": records}

    def list_history(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._vehicle(db, vehicle_id)
            return [{"sequence": row["sequence"], "action": row["action"], "occurredAt": row["occurred_at"], "before": json.loads(row["before_json"]), "after": json.loads(row["after_json"])}
                    for row in db.execute("SELECT * FROM history WHERE vehicle_id=? ORDER BY sequence", (vehicle_id,))]

    def backup(self, destination):
        """Create a new consistent full-store backup with restrictive permissions."""
        destination = Path(destination)
        with closing(self._connect()) as source:
            fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
            os.close(fd)
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)] or target.execute("PRAGMA foreign_key_check").fetchall():
                    raise sqlite3.DatabaseError("Backup integrity check failed.")
            with open(destination, "rb") as saved:
                os.fsync(saved.fileno())
