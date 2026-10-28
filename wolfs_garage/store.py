"""Standalone SQLite storage; no network calls or LubeLogger dependency.

The store must be explicitly initialized. Every write and its history entry are
committed together. Application history is append-only, not protection against a
database administrator. Money stays an exact decimal string throughout storage.
"""
from contextlib import closing, contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import base64
import json
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import urlsplit
import uuid
from zoneinfo import ZoneInfo


SCHEMA = 3
UNITS = {"km", "mi", "h"}
READINESS = {"ready", "not_ready", "unknown"}
SEVERITIES = {"observation", "repair", "critical"}
LIFECYCLES = {"open", "observed"}


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


def _page_filters(from_date, to_date, limit, kind=None):
    if from_date is not None:
        from_date = _day(from_date)
    if to_date is not None:
        to_date = _day(to_date)
    if from_date is not None and to_date is not None and from_date > to_date:
        raise ValidationError("from must be on or before to.")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValidationError("limit must be between 1 and 100.")
    if kind is not None and (not isinstance(kind, str) or kind not in {"service", "repair"}):
        raise ValidationError("Invalid record kind.")
    return from_date, to_date, limit, kind


def _encode_page_cursor(payload):
    raw = _json(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _decode_page_cursor(value):
    if not isinstance(value, str) or not value or len(value) > 2048 or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValidationError("Invalid cursor.")
    try:
        raw = base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError("Invalid cursor.") from exc
    if not isinstance(payload, dict):
        raise ValidationError("Invalid cursor.")
    return payload


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
    def __init__(self, path, today_provider=None):
        self.path = Path(path)
        if today_provider is not None and not callable(today_provider):
            raise TypeError("today_provider must be callable.")
        self.today_provider = (today_provider if today_provider is not None
                               else lambda: datetime.now(ZoneInfo("Europe/Berlin")).date())

    def initialize(self):
        """Create the current schema once; an existing file is never replaced."""
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript("""
                PRAGMA foreign_keys=ON;
                PRAGMA synchronous=FULL;
                BEGIN IMMEDIATE;
                CREATE TABLE meta(schema INTEGER NOT NULL);
                INSERT INTO meta VALUES(3);
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
                    document_url TEXT, closed_issue_id TEXT,
                    revision INTEGER NOT NULL DEFAULT 1);
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

    @staticmethod
    def _schema(db):
        try:
            rows = db.execute("SELECT schema FROM meta").fetchall()
        except sqlite3.Error as exc:
            raise sqlite3.DatabaseError("Unsupported standalone schema.") from exc
        if len(rows) != 1 or rows[0][0] not in (1, 2, 3):
            raise sqlite3.DatabaseError("Unsupported standalone schema.")
        return rows[0][0]

    @staticmethod
    def _new_backup(source, destination):
        destination = Path(destination)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        try:
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)
                if target.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise sqlite3.DatabaseError("Backup integrity check failed.")
                if target.execute("PRAGMA foreign_key_check").fetchall():
                    raise sqlite3.DatabaseError("Backup foreign key check failed.")
                if Store._schema(target) not in (1, 2, 3):
                    raise sqlite3.DatabaseError("Backup schema is unsupported.")
            with open(destination, "rb") as saved:
                os.fsync(saved.fileno())
        except BaseException:
            try:
                destination.unlink()
            except OSError:
                pass
            raise

    def upgrade(self, backup_destination):
        """Explicitly upgrade schema 1 or 2 after a checked full backup.

        The reserved migration lock prevents writers. A separate read connection
        supplies the backup snapshot, avoiding sqlite3.Connection.backup() from
        a connection holding its own write transaction.
        """
        source_uri = self.path.resolve().as_uri() + "?mode=rw"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=5, isolation_level=None)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            schema = self._schema(db)
            if schema == 3:
                return False
            db.execute("BEGIN IMMEDIATE")
            try:
                # Recheck under the write reservation in case another operator
                # completed the upgrade between the initial read and lock.
                schema = self._schema(db)
                if schema == 3:
                    db.execute("ROLLBACK")
                    return False
                reader_uri = self.path.resolve().as_uri() + "?mode=ro"
                with closing(sqlite3.connect(reader_uri, uri=True, timeout=5)) as reader:
                    self._new_backup(reader, backup_destination)
                if schema == 1:
                    db.execute("ALTER TABLE records ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
                db.execute("UPDATE meta SET schema=3")
                if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
                    raise sqlite3.DatabaseError("Integrity check failed after upgrade.")
                if db.execute("PRAGMA foreign_key_check").fetchall():
                    raise sqlite3.DatabaseError("Foreign key check failed after upgrade.")
                db.execute("COMMIT")
                return True
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

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
            seen, normalized = set(), []
            for item in issues:
                _fields(item, {"id", "text", "dueDate", "severity", "lifecycle"}, {"id", "text"})
                issue_id = _issue_id(item["id"])
                text = _text(item["text"], "issue", required=True)
                if issue_id in seen:
                    raise ValidationError("Duplicate stored issue.")
                seen.add(issue_id)
                due_date = item.get("dueDate")
                if due_date is not None:
                    due_date = _day(due_date)
                severity = item.get("severity")
                if severity is not None and (not isinstance(severity, str) or severity not in SEVERITIES):
                    raise ValidationError("Invalid stored issue severity.")
                lifecycle = item.get("lifecycle", "open")
                if not isinstance(lifecycle, str) or lifecycle not in LIFECYCLES:
                    raise ValidationError("Invalid stored issue lifecycle.")
                normalized.append({"id": issue_id, "text": text, "dueDate": due_date,
                                   "severity": severity, "lifecycle": lifecycle})
        except (ValueError, TypeError) as exc:
            raise sqlite3.DatabaseError("Invalid stored status.") from exc
        return {"readiness": row["readiness"], "issues": normalized, "revision": row["revision"]}

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

    def list_active_work(self):
        """Return a read-only projection of explicitly recorded active issues."""
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            today = self.today_provider()
            if type(today) is not date:
                raise ValueError("today_provider must return a datetime.date.")
            today_text = today.isoformat()
            items = []
            for row in db.execute("SELECT vehicle_id FROM states ORDER BY vehicle_id"):
                vehicle_id = row["vehicle_id"]
                for issue in self._status(db, vehicle_id)["issues"]:
                    if issue["lifecycle"] not in LIFECYCLES:
                        continue
                    due_date = issue["dueDate"]
                    if due_date is None:
                        due_state = "unscheduled"
                    elif due_date < today_text:
                        due_state = "overdue"
                    elif due_date == today_text:
                        due_state = "today"
                    else:
                        due_state = "upcoming"
                    items.append({"vehicleId": vehicle_id, "id": issue["id"], "text": issue["text"],
                                  "dueDate": due_date, "severity": issue["severity"],
                                  "lifecycle": issue["lifecycle"], "dueState": due_state})
            due_state_order = {"overdue": 0, "today": 1, "upcoming": 2, "unscheduled": 3}
            items.sort(key=lambda item: (
                0 if item["severity"] == "critical" else 1,
                due_state_order[item["dueState"]],
                item["dueDate"] or "9999-12-31",
                item["vehicleId"], item["id"],
            ))
            return {"today": today_text, "timeZone": "Europe/Berlin", "items": items}

    def update_status(self, vehicle_id, payload):
        _fields(payload, {"readiness", "issues", "revision"}, {"readiness", "issues", "revision"})
        expected = _revision(payload["revision"])
        if not isinstance(payload["readiness"], str) or payload["readiness"] not in READINESS or not isinstance(payload["issues"], list) or len(payload["issues"]) > 20:
            raise ValidationError("Invalid readiness or issues.")
        with self._transaction() as db:
            before = self._status(db, vehicle_id)
            if before["revision"] != expected:
                raise Conflict("Status revision changed.")
            existing = {item["id"]: item for item in before["issues"]}
            issues, seen = [], set()
            for item in payload["issues"]:
                _fields(item, {"id", "text", "dueDate", "severity", "lifecycle"}, {"text"})
                issue_id = _issue_id(item["id"]) if "id" in item else uuid.uuid4().hex
                if "id" in item and issue_id not in existing:
                    raise ValidationError("Unknown issue id.")
                if issue_id in seen:
                    raise ValidationError("Duplicate issue id.")
                seen.add(issue_id)
                old = existing.get(issue_id)
                due_date = item.get("dueDate", old["dueDate"] if old else None)
                if due_date is not None:
                    due_date = _day(due_date)
                severity = item.get("severity", old["severity"] if old else None)
                if severity is not None and (not isinstance(severity, str) or severity not in SEVERITIES):
                    raise ValidationError("Invalid issue severity.")
                lifecycle = item.get("lifecycle", old["lifecycle"] if old else "open")
                if not isinstance(lifecycle, str) or lifecycle not in LIFECYCLES:
                    raise ValidationError("Invalid issue lifecycle.")
                issues.append({"id": issue_id, "text": _text(item["text"], "issue", required=True),
                               "dueDate": due_date, "severity": severity, "lifecycle": lifecycle})
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
    def _page_cursor(cursor, *, vehicle_id, resource, from_date, to_date, kind, limit, sequence):
        if cursor is None:
            return None
        data = _decode_page_cursor(cursor)
        keys = {"v", "vehicle", "resource", "from", "to", "kind", "limit", "day", "id", "sequence"}
        if set(data) != keys:
            raise ValidationError("Invalid cursor.")
        if (type(data["v"]) is not int or data["v"] != 1
                or type(data["vehicle"]) is not int or not 1 <= data["vehicle"] <= 9223372036854775807
                or not isinstance(data["resource"], str)
                or type(data["limit"]) is not int or not isinstance(data["day"], str)
                or type(data["id"]) is not int or not 1 <= data["id"] <= 9223372036854775807
                or type(data["sequence"]) is not int or not 0 <= data["sequence"] <= 9223372036854775807):
            raise ValidationError("Invalid cursor.")
        try:
            _day(data["day"])
            if data["from"] is not None:
                _day(data["from"])
            if data["to"] is not None:
                _day(data["to"])
        except ValidationError as exc:
            raise ValidationError("Invalid cursor.") from exc
        if data["kind"] is not None and (not isinstance(data["kind"], str)
                                         or data["kind"] not in {"service", "repair"}):
            raise ValidationError("Invalid cursor.")
        expected = {"vehicle": vehicle_id, "resource": resource, "from": from_date,
                    "to": to_date, "kind": kind, "limit": limit}
        if any(data[key] != value for key, value in expected.items()):
            raise ValidationError("Cursor does not match this query.")
        if data["sequence"] != sequence:
            raise Conflict("Vehicle history changed during pagination.")
        return data

    @staticmethod
    def _page_query(db, vehicle_id, resource, from_date, to_date, limit, cursor, kind=None):
        if type(vehicle_id) is not int or not 1 <= vehicle_id <= 9223372036854775807:
            raise NotFound("Vehicle not found.")
        from_date, to_date, limit, kind = _page_filters(from_date, to_date, limit, kind)
        db.execute("BEGIN")
        Store._vehicle(db, vehicle_id)
        sequence = db.execute("SELECT COALESCE(MAX(sequence),0) FROM history WHERE vehicle_id=?", (vehicle_id,)).fetchone()[0]
        previous = Store._page_cursor(cursor, vehicle_id=vehicle_id, resource=resource,
                                      from_date=from_date, to_date=to_date, kind=kind,
                                      limit=limit, sequence=sequence)
        clauses, params = ["vehicle_id=?"], [vehicle_id]
        if from_date is not None:
            clauses.append("day>=?")
            params.append(from_date)
        if to_date is not None:
            clauses.append("day<=?")
            params.append(to_date)
        if kind is not None:
            clauses.append("kind=?")
            params.append(kind)
        if previous is not None:
            clauses.append("(day<? OR (day=? AND id<?))")
            params.extend((previous["day"], previous["day"], previous["id"]))
        return clauses, params, previous, sequence, from_date, to_date, kind, limit

    def page_records(self, vehicle_id, *, from_date=None, to_date=None, limit=25, cursor=None, kind=None):
        with closing(self._connect()) as db:
            clauses, params, _previous, sequence, from_date, to_date, kind, limit = self._page_query(
                db, vehicle_id, "records", from_date, to_date, limit, cursor, kind)
            rows = db.execute("SELECT * FROM records WHERE " + " AND ".join(clauses)
                              + " ORDER BY day DESC,id DESC LIMIT ?", (*params, limit + 1)).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            next_cursor = None
            if has_more:
                last = rows[-1]
                next_cursor = _encode_page_cursor({"v": 1, "vehicle": vehicle_id, "resource": "records",
                    "from": from_date, "to": to_date, "kind": kind, "limit": limit,
                    "day": last["day"], "id": last["id"], "sequence": sequence})
            return {"records": [self._record(row) for row in rows], "nextCursor": next_cursor}

    def page_odometer(self, vehicle_id, *, from_date=None, to_date=None, limit=25, cursor=None):
        with closing(self._connect()) as db:
            clauses, params, _previous, sequence, from_date, to_date, _kind, limit = self._page_query(
                db, vehicle_id, "odometer", from_date, to_date, limit, cursor)
            rows = db.execute("SELECT * FROM odometer_readings WHERE " + " AND ".join(clauses)
                              + " ORDER BY day DESC,id DESC LIMIT ?", (*params, limit + 1)).fetchall()
            has_more = len(rows) > limit
            rows = rows[:limit]
            next_cursor = None
            if has_more:
                last = rows[-1]
                next_cursor = _encode_page_cursor({"v": 1, "vehicle": vehicle_id, "resource": "odometer",
                    "from": from_date, "to": to_date, "kind": None, "limit": limit,
                    "day": last["day"], "id": last["id"], "sequence": sequence})
            return {"readings": [{"id": row["id"], "date": row["day"], "odometer": _number(row["value"]),
                                  "unit": row["unit"], "note": row["note"]} for row in rows],
                    "nextCursor": next_cursor}

    @staticmethod
    def _record(row):
        return {"id": row["id"], "description": row["description"], "kind": row["kind"], "date": row["day"],
                "odometer": _number(row["odometer"]), "odometerUnit": row["unit"], "cost": row["cost"],
                "currency": row["currency"], "documentUrl": row["document_url"], "closedIssueId": row["closed_issue_id"],
                "revision": row["revision"]}

    def get_record(self, vehicle_id, record_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._vehicle(db, vehicle_id)
            row = db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?", (vehicle_id, record_id)).fetchone()
            if row is None:
                raise NotFound("Record not found.")
            return self._record(row)

    @staticmethod
    def _correction_values(payload):
        allowed = {"revision", "commandId", "description", "kind", "cost", "currency", "documentUrl", "correctionReason"}
        _fields(payload, allowed, allowed)
        values = {"revision": _revision(payload["revision"]), "commandId": _command(payload["commandId"]),
                  "description": _text(payload["description"], "description", required=True),
                  "kind": payload["kind"], "cost": None, "currency": None,
                  "documentUrl": _document(payload["documentUrl"]) if payload["documentUrl"] is not None else None,
                  "correctionReason": _text(payload["correctionReason"], "correctionReason", 1600, required=True, multiline=True)}
        if not isinstance(values["kind"], str) or values["kind"] not in {"service", "repair"}:
            raise ValidationError("Invalid record kind.")
        if payload["cost"] is None and payload["currency"] is None:
            pass
        elif isinstance(payload["cost"], str) and isinstance(payload["currency"], str):
            try:
                amount = Decimal(payload["cost"])
            except InvalidOperation as exc:
                raise ValidationError("Invalid cost.") from exc
            if not amount.is_finite() or amount < 0 or amount > 1_000_000_000 or amount.as_tuple().exponent < -2:
                raise ValidationError("Cost must be nonnegative with at most two decimal places.")
            if len(payload["currency"]) != 3 or not all("A" <= c <= "Z" for c in payload["currency"]):
                raise ValidationError("Cost requires an uppercase three-letter currency.")
            values["cost"] = format(amount.quantize(Decimal("0.01")), "f")
            values["currency"] = payload["currency"]
        else:
            raise ValidationError("Cost and currency must both be null or valid values.")
        return values

    def correct_record(self, vehicle_id, record_id, payload):
        allowed = {"revision", "commandId", "description", "kind", "cost", "currency", "documentUrl", "correctionReason"}
        _fields(payload, allowed, allowed)
        command_id = _command(payload["commandId"])
        with self._transaction() as db:
            # Vehicle/record scoping is checked before command lookup so foreign
            # IDs cannot reveal or replay another vehicle's stored response.
            self._vehicle(db, vehicle_id)
            old_row = db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?", (vehicle_id, record_id)).fetchone()
            if old_row is None:
                raise NotFound("Record not found.")
            action = f"record.correct:{record_id}"
            digest, replay = self._replay(db, vehicle_id, action, command_id, payload)
            if replay is not None:
                return replay
            values = self._correction_values(payload)
            old = self._record(old_row)
            after_fields = {key: values[key] for key in ("description", "kind", "cost", "currency", "documentUrl")}
            if old["revision"] != values["revision"]:
                raise Conflict("Record revision changed.")
            if all(old[key] == after_fields[key] for key in after_fields):
                raise ValidationError("Correction must change at least one editable field.")
            db.execute("UPDATE records SET description=?,kind=?,cost=?,currency=?,document_url=?,revision=revision+1 WHERE vehicle_id=? AND id=?",
                       (after_fields["description"], after_fields["kind"], after_fields["cost"], after_fields["currency"], after_fields["documentUrl"], vehicle_id, record_id))
            updated = self._record(db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone())
            self._audit(db, vehicle_id, "record.corrected", {"record": old}, {"record": updated, "correctionReason": values["correctionReason"]})
            response = {"record": updated}
            self._remember(db, vehicle_id, action, values["commandId"], digest, response)
            return response

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
        source_uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=5)) as source:
            if self._schema(source) not in (1, 2, 3):
                raise sqlite3.DatabaseError("Unsupported standalone schema.")
            self._new_backup(source, destination)
