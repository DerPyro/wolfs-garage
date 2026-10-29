"""Standalone SQLite storage; no network calls or LubeLogger dependency.

The store must be explicitly initialized. Every write and its history entry are
committed together. Application history is append-only, not protection against a
database administrator. Money stays an exact decimal string throughout storage.
"""
from contextlib import closing, contextmanager
import calendar
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

from . import __version__


SCHEMA = 6
UNITS = {"km", "mi", "h"}
READINESS = {"ready", "not_ready", "unknown"}
SEVERITIES = {"observation", "repair", "critical"}
LIFECYCLES = {"open", "observed"}
READING_PROVENANCE = {"legacy_unknown", "manual", "record"}


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


def _inspection_month(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", value):
        raise ValidationError("inspectionDueMonth must be null or YYYY-MM.")
    year = int(value[:4])
    if not 1 <= year <= 9998:
        raise ValidationError("inspectionDueMonth year must be between 0001 and 9998.")
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


def _distance_string(value):
    """Parse a correction value from plain decimal text, never JSON float."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,3})?", value):
        raise ValidationError("Odometer correction must be a plain decimal string with at most three fractional digits.")
    return _distance(value)


def _annual_usage(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]{1,3})?", value):
        raise ValidationError("annualUsage must be a plain decimal string with at most three fractional digits.")
    return _distance(value)


def _reading_prompt_days(value):
    if value is None:
        return None
    if type(value) is not int or not 1 <= value <= 3650:
        raise ValidationError("readingPromptDays must be null or an integer from 1 to 3650.")
    return value


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
                INSERT INTO meta VALUES(6);
                CREATE TABLE vehicles(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    make TEXT NOT NULL, model TEXT NOT NULL, name TEXT NOT NULL,
                    year INTEGER, license_plate TEXT NOT NULL, vehicle_type TEXT NOT NULL,
                    unit TEXT NOT NULL, revision INTEGER NOT NULL,
                    inspection_due_month TEXT,
                    annual_usage TEXT CHECK(annual_usage IS NULL OR typeof(annual_usage)='text'),
                    reading_prompt_days INTEGER DEFAULT 30 CHECK(reading_prompt_days IS NULL OR
                        (typeof(reading_prompt_days)='integer' AND reading_prompt_days BETWEEN 1 AND 3650)));
                CREATE TABLE states(
                    vehicle_id INTEGER PRIMARY KEY REFERENCES vehicles(id),
                    readiness TEXT NOT NULL, issues TEXT NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE records(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    description TEXT NOT NULL, kind TEXT NOT NULL, day TEXT NOT NULL,
                    odometer TEXT, unit TEXT NOT NULL, cost TEXT, currency TEXT,
                    document_url TEXT, closed_issue_id TEXT,
                    revision INTEGER NOT NULL DEFAULT 1);
                CREATE UNIQUE INDEX records_id_vehicle_unique ON records(id,vehicle_id);
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
                CREATE TABLE odometer_readings(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
                    day TEXT NOT NULL, value TEXT NOT NULL, unit TEXT NOT NULL, note TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1 CHECK(typeof(revision)='integer' AND revision>=1),
                    provenance TEXT NOT NULL CHECK(provenance IN ('legacy_unknown','manual','record')),
                    source_record_id INTEGER,
                    CHECK((provenance='record' AND source_record_id IS NOT NULL) OR
                          (provenance IN ('legacy_unknown','manual') AND source_record_id IS NULL)),
                    FOREIGN KEY(source_record_id,vehicle_id) REFERENCES records(id,vehicle_id));
                CREATE UNIQUE INDEX odometer_source_record_unique ON odometer_readings(source_record_id) WHERE source_record_id IS NOT NULL;
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
        if len(rows) != 1 or rows[0][0] not in (1, 2, 3, 4, 5, 6):
            raise sqlite3.DatabaseError("Unsupported standalone schema.")
        return rows[0][0]

    @staticmethod
    def _validate_backup(db):
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise sqlite3.DatabaseError("Backup integrity check failed.")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise sqlite3.DatabaseError("Backup foreign key check failed.")
        schema = Store._schema(db)
        if schema not in (1, 2, 3, 4, 5, 6):
            raise sqlite3.DatabaseError("Backup schema is unsupported.")
        return schema

    @staticmethod
    def _validate_restore_backup(db):
        schema = Store._validate_backup(db)
        expected_columns = {
            "meta": ["schema"],
            "vehicles": ["id", "make", "model", "name", "year", "license_plate",
                         "vehicle_type", "unit", "revision"] +
                        (["inspection_due_month"] if schema >= 4 else []) +
                        (["annual_usage", "reading_prompt_days"] if schema >= 6 else []),
            "states": ["vehicle_id", "readiness", "issues", "revision"],
            "odometer_readings": ["id", "vehicle_id", "day", "value", "unit", "note"] +
                                 (["revision", "provenance", "source_record_id"] if schema >= 5 else []),
            "records": ["id", "vehicle_id", "description", "kind", "day", "odometer", "unit",
                        "cost", "currency", "document_url", "closed_issue_id"] + ([] if schema == 1 else ["revision"]),
            "commands": ["vehicle_id", "action", "command_id", "payload_hash", "response"],
            "history": ["sequence", "vehicle_id", "action", "occurred_at", "before_json", "after_json"],
        }
        tables = {row[0] for row in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
        if tables != set(expected_columns):
            raise sqlite3.DatabaseError("Backup table layout is unsupported.")
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='view' LIMIT 1").fetchone():
            raise sqlite3.DatabaseError("Backup view layout is unsupported.")
        for table, expected in expected_columns.items():
            actual = [row[1] for row in db.execute(f'PRAGMA table_info("{table}")')]
            if actual != expected:
                raise sqlite3.DatabaseError("Backup table layout is unsupported.")

        expected_foreign_keys = {
            "states": {("vehicle_id", "vehicles", "id")},
            "odometer_readings": {("vehicle_id", "vehicles", "id")},
            "records": {("vehicle_id", "vehicles", "id")},
            "commands": {("vehicle_id", "vehicles", "id")},
            "history": {("vehicle_id", "vehicles", "id")},
            "meta": set(), "vehicles": set(),
        }
        if schema >= 5:
            expected_foreign_keys["odometer_readings"].update({
                ("source_record_id", "records", "id"),
                ("vehicle_id", "records", "vehicle_id"),
            })
        for table, expected in expected_foreign_keys.items():
            actual = {(row[3], row[2], row[4]) for row in db.execute(f'PRAGMA foreign_key_list("{table}")')}
            if actual != expected:
                raise sqlite3.DatabaseError("Backup foreign-key layout is unsupported.")

        expected_indexes = {
            "odometer_vehicle_date": ("odometer_readings", ["vehicle_id", "day", "id"]),
            "records_vehicle_date": ("records", ["vehicle_id", "day", "id"]),
        }
        if schema >= 5:
            expected_indexes.update({
                "records_id_vehicle_unique": ("records", ["id", "vehicle_id"]),
                "odometer_source_record_unique": ("odometer_readings", ["source_record_id"]),
            })
        indexes = {row[0]: row[1] for row in db.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'")}
        if indexes != {name: table for name, (table, _) in expected_indexes.items()}:
            raise sqlite3.DatabaseError("Backup index layout is unsupported.")
        for name, (table, columns) in expected_indexes.items():
            actual = [row[2] for row in db.execute(f'PRAGMA index_info("{name}")')]
            if actual != columns:
                raise sqlite3.DatabaseError("Backup index layout is unsupported.")
        if schema >= 5:
            index_properties = {}
            for table in ("records", "odometer_readings"):
                for row in db.execute(f'PRAGMA index_list("{table}")'):
                    if not row[1].startswith("sqlite_"):
                        index_properties[row[1]] = (row[2], row[4])
            if (index_properties.get("records_id_vehicle_unique") != (1, 0)
                    or index_properties.get("odometer_source_record_unique") != (1, 1)):
                raise sqlite3.DatabaseError("Backup index layout is unsupported.")

        expected_triggers = {"history_no_update": "before update on history",
                             "history_no_delete": "before delete on history"}
        triggers = {row[0]: " ".join(row[1].lower().split()) for row in db.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='trigger'")}
        if set(triggers) != set(expected_triggers):
            raise sqlite3.DatabaseError("Backup trigger layout is unsupported.")
        if any(fragment not in triggers[name] for name, fragment in expected_triggers.items()):
            raise sqlite3.DatabaseError("Backup trigger layout is unsupported.")
        if schema >= 5:
            table_sql = db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='odometer_readings'").fetchone()[0]
            normalized = " ".join(table_sql.lower().split())
            if ("check(typeof(revision)='integer' and revision>=1)" not in normalized
                    or "check(provenance in ('legacy_unknown','manual','record'))" not in normalized
                    or "check((provenance='record' and source_record_id is not null)" not in normalized
                    or "foreign key(source_record_id,vehicle_id) references records(id,vehicle_id)" not in normalized):
                raise sqlite3.DatabaseError("Backup reading provenance constraints are unsupported.")
            invalid_reading = db.execute("""SELECT 1
                FROM odometer_readings AS reading
                LEFT JOIN records AS record
                  ON record.id=reading.source_record_id AND record.vehicle_id=reading.vehicle_id
                WHERE typeof(reading.revision)!='integer' OR reading.revision<1
                   OR reading.provenance IS NULL
                   OR reading.provenance NOT IN ('legacy_unknown','manual','record')
                   OR (reading.provenance='record' AND
                       (reading.source_record_id IS NULL OR record.id IS NULL OR record.odometer IS NULL
                        OR reading.day<>record.day OR reading.value<>record.odometer OR reading.unit<>record.unit))
                   OR (reading.provenance IN ('legacy_unknown','manual') AND reading.source_record_id IS NOT NULL)
                LIMIT 1""").fetchone()
            if invalid_reading is not None:
                raise sqlite3.DatabaseError("Backup contains inconsistent record-reading provenance.")
        if schema == 6:
            vehicle_sql = db.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='vehicles'").fetchone()[0]
            normalized = " ".join(vehicle_sql.lower().split())
            if ("check(annual_usage is null or typeof(annual_usage)='text')" not in normalized
                    or "check(reading_prompt_days is null or (typeof(reading_prompt_days)='integer' and reading_prompt_days between 1 and 3650))" not in normalized):
                raise sqlite3.DatabaseError("Backup vehicle forecast constraints are unsupported.")
            vehicle_columns = {row[1]: row for row in db.execute('PRAGMA table_info("vehicles")')}
            if (vehicle_columns["annual_usage"][3] != 0
                    or vehicle_columns["annual_usage"][4] is not None
                    or vehicle_columns["reading_prompt_days"][3] != 0
                    or vehicle_columns["reading_prompt_days"][4] != "30"):
                raise sqlite3.DatabaseError("Backup vehicle forecast defaults are unsupported.")
            for row in db.execute("SELECT annual_usage,reading_prompt_days FROM vehicles"):
                try:
                    if row[0] is not None and _annual_usage(row[0]) != row[0]:
                        raise ValidationError("Noncanonical annual usage.")
                    _reading_prompt_days(row[1])
                except (ValidationError, TypeError) as exc:
                    raise sqlite3.DatabaseError("Backup contains invalid vehicle forecast settings.") from exc
        return schema

    @staticmethod
    def _new_backup(source, destination):
        destination = Path(destination)
        fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(fd)
        try:
            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)
                Store._validate_backup(target)
            with open(destination, "rb") as saved:
                os.fsync(saved.fileno())
        except BaseException:
            try:
                destination.unlink()
            except OSError:
                pass
            raise

    @staticmethod
    def _upgrade_readings_to_schema5(db):
        old_sequence = db.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='odometer_readings'").fetchone()
        old_sequence = int(old_sequence[0]) if old_sequence else 0
        db.execute("CREATE UNIQUE INDEX records_id_vehicle_unique ON records(id,vehicle_id)")
        db.execute("""CREATE TABLE odometer_readings_v5(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER NOT NULL REFERENCES vehicles(id),
            day TEXT NOT NULL, value TEXT NOT NULL, unit TEXT NOT NULL, note TEXT NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1 CHECK(typeof(revision)='integer' AND revision>=1),
            provenance TEXT NOT NULL CHECK(provenance IN ('legacy_unknown','manual','record')),
            source_record_id INTEGER,
            CHECK((provenance='record' AND source_record_id IS NOT NULL) OR
                  (provenance IN ('legacy_unknown','manual') AND source_record_id IS NULL)),
            FOREIGN KEY(source_record_id,vehicle_id) REFERENCES records(id,vehicle_id))""")
        db.execute("""INSERT INTO odometer_readings_v5
            (id,vehicle_id,day,value,unit,note,revision,provenance,source_record_id)
            SELECT id,vehicle_id,day,value,unit,note,1,'legacy_unknown',NULL
            FROM odometer_readings ORDER BY id""")
        db.execute("DROP TABLE odometer_readings")
        db.execute("ALTER TABLE odometer_readings_v5 RENAME TO odometer_readings")
        db.execute("CREATE INDEX odometer_vehicle_date ON odometer_readings(vehicle_id,day,id)")
        db.execute("CREATE UNIQUE INDEX odometer_source_record_unique ON odometer_readings(source_record_id) WHERE source_record_id IS NOT NULL")
        sequence_row = db.execute(
            "SELECT seq FROM sqlite_sequence WHERE name='odometer_readings'").fetchone()
        sequence = int(sequence_row[0]) if sequence_row else 0
        if sequence < old_sequence:
            if sequence_row is not None:
                db.execute("UPDATE sqlite_sequence SET seq=? WHERE name='odometer_readings'", (old_sequence,))
            else:
                db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('odometer_readings',?)", (old_sequence,))

    def upgrade(self, backup_destination):
        """Explicitly upgrade schema 1–5 after a checked full backup.
        The reserved migration lock prevents writers. A separate read connection
        supplies the backup snapshot, avoiding sqlite3.Connection.backup() from
        a connection holding its own write transaction.
        """
        source_uri = self.path.resolve().as_uri() + "?mode=rw"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=5, isolation_level=None)) as db:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("PRAGMA busy_timeout=5000")
            schema = self._schema(db)
            if schema == 6:
                return False
            db.execute("BEGIN IMMEDIATE")
            try:
                # Recheck under the write reservation in case another operator
                # completed the upgrade between the initial read and lock.
                schema = self._schema(db)
                if schema == 6:
                    db.execute("ROLLBACK")
                    return False
                reader_uri = self.path.resolve().as_uri() + "?mode=ro"
                with closing(sqlite3.connect(reader_uri, uri=True, timeout=5)) as reader:
                    self._new_backup(reader, backup_destination)
                if schema == 1:
                    db.execute("ALTER TABLE records ADD COLUMN revision INTEGER NOT NULL DEFAULT 1")
                if schema <= 3:
                    db.execute("ALTER TABLE vehicles ADD COLUMN inspection_due_month TEXT")
                if schema <= 4:
                    self._upgrade_readings_to_schema5(db)
                db.execute("ALTER TABLE vehicles ADD COLUMN annual_usage TEXT CHECK(annual_usage IS NULL OR typeof(annual_usage)='text')")
                db.execute("ALTER TABLE vehicles ADD COLUMN reading_prompt_days INTEGER DEFAULT 30 CHECK(reading_prompt_days IS NULL OR (typeof(reading_prompt_days)='integer' AND reading_prompt_days BETWEEN 1 AND 3650))")
                db.execute("UPDATE meta SET schema=6")
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
        try:
            _inspection_month(row["inspection_due_month"])
        except ValidationError as exc:
            raise sqlite3.DatabaseError("Invalid stored inspection due month.") from exc
        try:
            if row["annual_usage"] is not None and _annual_usage(row["annual_usage"]) != row["annual_usage"]:
                raise ValidationError("Noncanonical annual usage.")
            _reading_prompt_days(row["reading_prompt_days"])
        except ValidationError as exc:
            raise sqlite3.DatabaseError("Invalid stored mileage forecast settings.") from exc
        # The latest dated explicit reading is the current stand. Historical
        # backdated readings remain stored and never silently replace it.
        latest = db.execute("SELECT value FROM odometer_readings WHERE vehicle_id=? ORDER BY day DESC,id DESC LIMIT 1", (vehicle_id,)).fetchone()
        return {"id": row["id"], "make": row["make"], "model": row["model"],
                "name": row["name"] or f'{row["make"]} {row["model"]}', "year": row["year"],
                "licensePlate": row["license_plate"], "vehicleType": row["vehicle_type"],
                "odometer": _number(latest["value"]) if latest else None,
                "odometerUnit": row["unit"], "revision": row["revision"],
                "inspectionDueMonth": row["inspection_due_month"],
                "annualUsage": row["annual_usage"],
                "readingPromptDays": row["reading_prompt_days"],
                "status": Store._status(db, vehicle_id)}

    def _today(self):
        today = self.today_provider()
        if type(today) is not date:
            raise ValueError("today_provider must return a datetime.date.")
        return today

    @staticmethod
    def _with_inspection(vehicle, today):
        due_month = vehicle["inspectionDueMonth"]
        try:
            due_month = _inspection_month(due_month)
        except ValidationError as exc:
            raise sqlite3.DatabaseError("Invalid stored inspection due month.") from exc

        if due_month is None:
            inspection = {"asOf": today.isoformat(), "timeZone": "Europe/Berlin", "dueMonth": None,
                          "validUntil": None, "blockingFrom": None, "state": "unknown",
                          "monthsUntilDue": None, "blocksReadiness": False,
                          "batteryLevel": None, "scaleMonths": 12}
        else:
            year, month = (int(part) for part in due_month.split("-"))
            months_until = year * 12 + month - (today.year * 12 + today.month)
            if months_until > 0:
                state = "upcoming"
            elif months_until == 0:
                state = "due"
            elif months_until == -1:
                state = "overdue"
            else:
                state = "blocking"
            blocking_index = year * 12 + month - 1 + 2
            blocking_year, blocking_month_index = divmod(blocking_index, 12)
            inspection = {
                "asOf": today.isoformat(), "timeZone": "Europe/Berlin", "dueMonth": due_month,
                "validUntil": date(year, month, calendar.monthrange(year, month)[1]).isoformat(),
                "blockingFrom": date(blocking_year, blocking_month_index + 1, 1).isoformat(),
                "state": state, "monthsUntilDue": months_until,
                "blocksReadiness": state == "blocking",
                "batteryLevel": max(0, min(12, months_until)), "scaleMonths": 12,
            }
        response = dict(vehicle)
        response["inspection"] = inspection
        response["effectiveReadiness"] = (
            "not_ready" if inspection["blocksReadiness"] or vehicle["status"]["readiness"] == "not_ready"
            else vehicle["status"]["readiness"]
        )
        return response

    @staticmethod
    def _with_mileage_projection(db, vehicle, today):
        projected = Store._with_inspection(vehicle, today)
        annual_usage = vehicle["annualUsage"]
        unit = vehicle["odometerUnit"]
        prompt_days = vehicle["readingPromptDays"]
        row = db.execute("""SELECT id,day,value,unit FROM odometer_readings
            WHERE vehicle_id=? ORDER BY day DESC,id DESC LIMIT 1""", (vehicle["id"],)).fetchone()
        anchor = None
        anchor_day = None
        elapsed_days = None
        if row is not None:
            try:
                anchor_day = date.fromisoformat(row["day"])
                if anchor_day.isoformat() != row["day"]:
                    raise ValueError("Noncanonical date")
            except ValueError as exc:
                raise sqlite3.DatabaseError("Invalid stored odometer date.") from exc
            anchor = {"id": row["id"], "date": row["day"],
                      "odometer": row["value"], "unit": row["unit"]}
            elapsed_days = (today - anchor_day).days

        estimate_state = "estimated"
        estimated_value = None
        if row is None:
            estimate_state = "anchor_missing"
        elif elapsed_days < 0:
            estimate_state = "future_anchor"
        elif row["unit"] != unit:
            estimate_state = "unit_mismatch"
        elif annual_usage is None:
            estimate_state = "annual_usage_missing"
        else:
            raw_value = Decimal(row["value"]) + Decimal(annual_usage) * Decimal(elapsed_days) / Decimal(365)
            if raw_value < 0 or raw_value > Decimal("1000000000"):
                estimate_state = "out_of_range"
            else:
                rounded = raw_value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                estimated_value = format(rounded.normalize(), "f")
        projected["mileageEstimate"] = {
            "asOf": today.isoformat(), "timeZone": "Europe/Berlin", "state": estimate_state,
            "annualUsage": annual_usage, "unit": unit, "anchor": anchor,
            "elapsedDays": elapsed_days, "estimatedOdometer": estimated_value,
        }

        prompt_state = "not_due"
        prompt_date = None
        prompt_reason = None
        if prompt_days is None:
            prompt_state = "disabled"
        elif row is None:
            prompt_state = "needs_reading"
        elif elapsed_days < 0:
            prompt_state, prompt_reason = "needs_review", "future_anchor"
        elif row["unit"] != unit:
            prompt_state, prompt_reason = "needs_review", "unit_mismatch"
        else:
            try:
                prompt_date = (anchor_day + timedelta(days=prompt_days)).isoformat()
            except (OverflowError, ValueError):
                prompt_state, prompt_reason = "needs_review", "date_out_of_range"
            else:
                prompt_state = "due" if today.isoformat() >= prompt_date else "not_due"
        projected["readingPrompt"] = {
            "asOf": today.isoformat(), "timeZone": "Europe/Berlin", "state": prompt_state,
            "intervalDays": prompt_days, "dueDate": prompt_date, "reason": prompt_reason,
        }
        return projected

    @staticmethod
    def _audit(db, vehicle_id, action, before, after):
        db.execute("INSERT INTO history(vehicle_id,action,occurred_at,before_json,after_json) VALUES(?,?,?,?,?)",
                   (vehicle_id, action, datetime.now(timezone.utc).isoformat(), _json(before), _json(after)))

    @staticmethod
    def _vehicle_values(payload, old=None):
        allowed = {"make", "model", "name", "year", "licensePlate", "vehicleType", "odometerUnit",
                   "inspectionDueMonth", "annualUsage", "readingPromptDays"}
        _fields(payload, allowed | ({"revision"} if old else set()), {"revision"} if old else {"make", "model"})
        result = {"make": "", "model": "", "name": "", "year": None, "licensePlate": "", "vehicleType": "",
                  "odometerUnit": "km", "inspectionDueMonth": None, "annualUsage": None,
                  "readingPromptDays": 30}
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
        result["inspectionDueMonth"] = _inspection_month(result["inspectionDueMonth"])
        result["annualUsage"] = _annual_usage(result["annualUsage"])
        result["readingPromptDays"] = _reading_prompt_days(result["readingPromptDays"])
        return result

    def create_vehicle(self, payload):
        values = self._vehicle_values(payload)
        today = self._today()
        with self._transaction() as db:
            cursor = db.execute("""INSERT INTO vehicles
                (make,model,name,year,license_plate,vehicle_type,unit,revision,inspection_due_month,annual_usage,reading_prompt_days)
                VALUES(?,?,?,?,?,?,?,1,?,?,?)""",
                tuple(values[k] for k in ("make", "model", "name", "year", "licensePlate", "vehicleType",
                                          "odometerUnit", "inspectionDueMonth", "annualUsage", "readingPromptDays")))
            vehicle_id = cursor.lastrowid
            db.execute("INSERT INTO states VALUES(?,'unknown','[]',0)", (vehicle_id,))
            result = self._vehicle(db, vehicle_id)
            self._audit(db, vehicle_id, "vehicle.created", None, result)
            return self._with_mileage_projection(db, result, today)

    def list_vehicles(self):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            today = self._today()
            return [self._with_mileage_projection(db, self._vehicle(db, row[0]), today)
                    for row in db.execute("SELECT id FROM vehicles ORDER BY id")]

    def get_vehicle(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            today = self._today()
            return self._with_mileage_projection(db, self._vehicle(db, vehicle_id), today)

    def update_vehicle(self, vehicle_id, payload):
        today = self._today()
        with self._transaction() as db:
            before = self._vehicle(db, vehicle_id)
            base = dict(before)
            base["name"] = db.execute("SELECT name FROM vehicles WHERE id=?", (vehicle_id,)).fetchone()[0]
            values = self._vehicle_values(payload, base)
            if _revision(payload["revision"]) != before["revision"]:
                raise Conflict("Vehicle revision changed.")
            if values["odometerUnit"] != before["odometerUnit"] and db.execute("SELECT 1 FROM odometer_readings WHERE vehicle_id=? LIMIT 1", (vehicle_id,)).fetchone():
                raise Conflict("A unit with recorded readings cannot be relabelled; conversion is a separate operation.")
            if (values["odometerUnit"] != before["odometerUnit"] and before["annualUsage"] is not None
                    and "annualUsage" not in payload):
                raise Conflict("Changing the unit requires explicitly resetting or setting annualUsage.")
            db.execute("""UPDATE vehicles SET make=?,model=?,name=?,year=?,license_plate=?,vehicle_type=?,unit=?,
                inspection_due_month=?,annual_usage=?,reading_prompt_days=?,revision=revision+1 WHERE id=?""",
                tuple(values[k] for k in ("make", "model", "name", "year", "licensePlate", "vehicleType",
                                          "odometerUnit", "inspectionDueMonth", "annualUsage", "readingPromptDays"))
                + (vehicle_id,))
            result = self._vehicle(db, vehicle_id)
            self._audit(db, vehicle_id, "vehicle.updated", before, result)
            return self._with_mileage_projection(db, result, today)

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
            cursor = db.execute("""INSERT INTO odometer_readings
                (vehicle_id,day,value,unit,note,revision,provenance,source_record_id)
                VALUES(?,?,?,?,?,1,'manual',NULL)""", (vehicle_id, day, value, payload["unit"], note))
            result = self._reading(db.execute(
                "SELECT * FROM odometer_readings WHERE id=?", (cursor.lastrowid,)).fetchone())
            self._audit(db, vehicle_id, "odometer.created", None, result)
            self._remember(db, vehicle_id, "odometer", command_id, digest, result)
            return result

    def list_odometer(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._vehicle(db, vehicle_id)
            return [self._reading(r) for r in db.execute(
                "SELECT * FROM odometer_readings WHERE vehicle_id=? ORDER BY day DESC,id DESC", (vehicle_id,))]

    @staticmethod
    def _current_reading(db, vehicle_id):
        row = db.execute("SELECT * FROM odometer_readings WHERE vehicle_id=? ORDER BY day DESC,id DESC LIMIT 1",
                         (vehicle_id,)).fetchone()
        return Store._reading(row) if row is not None else None

    @staticmethod
    def _reading_revision(value):
        if value is None:
            return None
        return _revision(value)

    @staticmethod
    def _correction_reason(value):
        return _text(value, "correctionReason", 1600, required=True, multiline=True)

    @staticmethod
    def _corrected_value(value):
        return None if value is None else _distance_string(value)

    def get_odometer_reading(self, vehicle_id, reading_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._vehicle(db, vehicle_id)
            row = db.execute("SELECT * FROM odometer_readings WHERE vehicle_id=? AND id=?",
                             (vehicle_id, reading_id)).fetchone()
            if row is None:
                raise NotFound("Odometer reading not found.")
            return {"reading": self._reading(row)}

    def _manual_reading_values(self, payload):
        allowed = {"revision", "date", "odometer", "note", "commandId", "correctionReason"}
        _fields(payload, allowed, allowed)
        return {
            "revision": _revision(payload["revision"]),
            "date": _day(payload["date"]),
            "odometer": _distance_string(payload["odometer"]),
            "note": _text(payload["note"], "note", 1600, multiline=True),
            "commandId": _command(payload["commandId"]),
            "correctionReason": self._correction_reason(payload["correctionReason"]),
        }

    def correct_odometer_reading(self, vehicle_id, reading_id, payload):
        values = self._manual_reading_values(payload)
        with self._transaction() as db:
            self._vehicle(db, vehicle_id)
            old_row = db.execute("SELECT * FROM odometer_readings WHERE vehicle_id=? AND id=?",
                                 (vehicle_id, reading_id)).fetchone()
            if old_row is None:
                raise NotFound("Odometer reading not found.")
            action = f"odometer.correct:{reading_id}"
            digest, replay = self._replay(db, vehicle_id, action, values["commandId"], payload)
            if replay is not None:
                return replay
            if old_row["provenance"] == "record":
                raise Conflict("This reading belongs to a completed record; correct it through that record.")
            if old_row["provenance"] == "legacy_unknown":
                raise Conflict("Confirm this legacy reading's provenance before correcting it.")
            if old_row["revision"] != values["revision"]:
                raise Conflict("Odometer reading revision changed.")
            if (old_row["day"] == values["date"] and old_row["value"] == values["odometer"]
                    and old_row["note"] == values["note"]):
                raise ValidationError("Correction must change at least one reading value.")
            if old_row["revision"] >= 2147483646:
                raise Conflict("Odometer reading revision cannot be advanced.")
            current_before = self._current_reading(db, vehicle_id)
            before = self._reading(old_row)
            db.execute("""UPDATE odometer_readings SET day=?,value=?,note=?,revision=revision+1
                WHERE vehicle_id=? AND id=?""",
                (values["date"], values["odometer"], values["note"], vehicle_id, reading_id))
            updated = self._reading(db.execute("SELECT * FROM odometer_readings WHERE id=?", (reading_id,)).fetchone())
            current_after = self._current_reading(db, vehicle_id)
            self._audit(db, vehicle_id, "odometer.corrected", {"reading": before},
                        {"reading": updated, "correctionReason": values["correctionReason"]})
            response = {"reading": updated, "currentReadingBefore": current_before,
                        "currentReadingAfter": current_after}
            self._remember(db, vehicle_id, action, values["commandId"], digest, response)
            return response

    def _provenance_values(self, payload):
        allowed = {"revision", "commandId", "provenance", "sourceRecordId", "recordRevision", "correctionReason"}
        _fields(payload, allowed, allowed)
        provenance = payload["provenance"]
        if not isinstance(provenance, str) or provenance not in {"manual", "record"}:
            raise ValidationError("Provenance must be manual or record.")
        source_id = payload["sourceRecordId"]
        record_revision = payload["recordRevision"]
        if provenance == "manual":
            if source_id is not None or record_revision is not None:
                raise ValidationError("Manual provenance cannot include a source record.")
        else:
            if type(source_id) is not int or not 1 <= source_id <= 9223372036854775807:
                raise ValidationError("Record provenance requires a source record ID.")
            record_revision = _revision(record_revision)
        return {"revision": _revision(payload["revision"]), "commandId": _command(payload["commandId"]),
                "provenance": provenance, "sourceRecordId": source_id,
                "recordRevision": record_revision,
                "correctionReason": self._correction_reason(payload["correctionReason"])}

    def confirm_odometer_provenance(self, vehicle_id, reading_id, payload):
        values = self._provenance_values(payload)
        with self._transaction() as db:
            self._vehicle(db, vehicle_id)
            old_row = db.execute("SELECT * FROM odometer_readings WHERE vehicle_id=? AND id=?",
                                 (vehicle_id, reading_id)).fetchone()
            if old_row is None:
                raise NotFound("Odometer reading not found.")
            action = f"odometer.provenance:{reading_id}"
            digest, replay = self._replay(db, vehicle_id, action, values["commandId"], payload)
            if replay is not None:
                return replay
            if old_row["revision"] != values["revision"]:
                raise Conflict("Odometer reading revision changed.")
            if old_row["provenance"] != "legacy_unknown" or old_row["source_record_id"] is not None:
                raise Conflict("Only unresolved legacy readings can have provenance confirmed.")
            if old_row["revision"] >= 2147483646:
                raise Conflict("Odometer reading revision cannot be advanced.")
            record_before = None
            record_after = None
            record_before_row = None
            if values["provenance"] == "record":
                record_before_row = db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?",
                                               (vehicle_id, values["sourceRecordId"])).fetchone()
                if record_before_row is None:
                    raise NotFound("Source record not found for this vehicle.")
                if record_before_row["revision"] != values["recordRevision"]:
                    raise Conflict("Source record revision changed.")
                if record_before_row["revision"] >= 2147483646:
                    raise Conflict("Source record revision cannot be advanced.")
                if (record_before_row["odometer"] is None
                        or record_before_row["day"] != old_row["day"]
                        or record_before_row["odometer"] != old_row["value"]
                        or record_before_row["unit"] != old_row["unit"]):
                    raise Conflict("Selected record does not exactly match this reading's date, value, and unit.")
                existing = db.execute("SELECT id FROM odometer_readings WHERE source_record_id=?",
                                      (values["sourceRecordId"],)).fetchone()
                if existing is not None:
                    raise Conflict("Selected record already has a linked reading.")
                record_before = self._record(record_before_row)
            reading_before = self._reading(old_row)
            db.execute("""UPDATE odometer_readings SET provenance=?,source_record_id=?,revision=revision+1
                WHERE vehicle_id=? AND id=?""",
                (values["provenance"], values["sourceRecordId"], vehicle_id, reading_id))
            if record_before_row is not None:
                db.execute("UPDATE records SET revision=revision+1 WHERE vehicle_id=? AND id=?",
                           (vehicle_id, values["sourceRecordId"]))
                record_after = self._record(db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?",
                                                       (vehicle_id, values["sourceRecordId"])).fetchone())
            reading_after = self._reading(db.execute("SELECT * FROM odometer_readings WHERE id=?",
                                                      (reading_id,)).fetchone())
            after = {"reading": reading_after, "record": record_after,
                     "correctionReason": values["correctionReason"]}
            before = {"reading": reading_before}
            if record_before is not None:
                before["record"] = record_before
            self._audit(db, vehicle_id, "odometer.provenance-confirmed", before, after)
            response = {"reading": reading_after, "record": record_after}
            self._remember(db, vehicle_id, action, values["commandId"], digest, response)
            return response

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
            return {"readings": [self._reading(row) for row in rows],
                    "nextCursor": next_cursor}

    @staticmethod
    def _reading(row):
        return {"id": row["id"], "date": row["day"], "odometer": _number(row["value"]),
                "unit": row["unit"], "note": row["note"], "odometerExact": row["value"],
                "revision": row["revision"], "provenance": row["provenance"],
                "sourceRecordId": row["source_record_id"]}

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
    def _validate_record_reading_link(record_row, reading_row):
        if (reading_row["provenance"] != "record"
                or reading_row["source_record_id"] != record_row["id"]
                or reading_row["vehicle_id"] != record_row["vehicle_id"]
                or record_row["odometer"] is None
                or reading_row["day"] != record_row["day"]
                or reading_row["value"] != record_row["odometer"]
                or reading_row["unit"] != record_row["unit"]):
            raise sqlite3.DatabaseError("Linked record and odometer facts do not match.")

    def get_record_measurement(self, vehicle_id, record_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._vehicle(db, vehicle_id)
            row = db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?", (vehicle_id, record_id)).fetchone()
            if row is None:
                raise NotFound("Record not found.")
            linked = db.execute("SELECT * FROM odometer_readings WHERE vehicle_id=? AND source_record_id=?",
                                (vehicle_id, record_id)).fetchone()
            mode = "linked" if linked is not None else ("date_only" if row["odometer"] is None else "legacy_unresolved")
            if linked is not None:
                self._validate_record_reading_link(row, linked)
            return {"record": self._record(row), "odometerExact": row["odometer"],
                    "sourceReading": self._reading(linked) if linked is not None else None,
                    "correctionMode": mode, "currentReading": self._current_reading(db, vehicle_id)}

    @staticmethod
    def _record_measurement_values(payload):
        allowed = {"revision", "readingRevision", "date", "odometer", "commandId", "correctionReason"}
        _fields(payload, allowed, allowed)
        odometer = None if payload["odometer"] is None else _distance_string(payload["odometer"])
        return {"revision": _revision(payload["revision"]),
                "readingRevision": Store._reading_revision(payload["readingRevision"]),
                "date": _day(payload["date"]), "odometer": odometer,
                "commandId": _command(payload["commandId"]),
                "correctionReason": Store._correction_reason(payload["correctionReason"])}

    def correct_record_measurement(self, vehicle_id, record_id, payload):
        values = self._record_measurement_values(payload)
        with self._transaction() as db:
            self._vehicle(db, vehicle_id)
            old_row = db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?",
                                 (vehicle_id, record_id)).fetchone()
            if old_row is None:
                raise NotFound("Record not found.")
            action = f"record.measurement:{record_id}"
            digest, replay = self._replay(db, vehicle_id, action, values["commandId"], payload)
            if replay is not None:
                return replay
            if old_row["revision"] != values["revision"]:
                raise Conflict("Record revision changed.")
            linked = db.execute("SELECT * FROM odometer_readings WHERE vehicle_id=? AND source_record_id=?",
                                (vehicle_id, record_id)).fetchone()
            if linked is None:
                if old_row["odometer"] is not None:
                    raise Conflict("This legacy record has no verified source reading; its measurements cannot be corrected.")
                if values["odometer"] is not None or values["readingRevision"] is not None:
                    raise ValidationError("A date-only record must keep odometer and readingRevision null.")
                if old_row["day"] == values["date"]:
                    raise ValidationError("Correction must change the record date.")
                if old_row["revision"] >= 2147483646:
                    raise Conflict("Record revision cannot be advanced.")
                current_before = self._current_reading(db, vehicle_id)
                before_record = self._record(old_row)
                db.execute("UPDATE records SET day=?,revision=revision+1 WHERE vehicle_id=? AND id=?",
                           (values["date"], vehicle_id, record_id))
                updated_record = self._record(db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?",
                                                         (vehicle_id, record_id)).fetchone())
                current_after = self._current_reading(db, vehicle_id)
                before = {"record": before_record, "reading": None}
                after = {"record": updated_record, "reading": None,
                         "correctionReason": values["correctionReason"]}
                response = {"record": updated_record, "reading": None,
                            "currentReadingBefore": current_before, "currentReadingAfter": current_after}
            else:
                self._validate_record_reading_link(old_row, linked)
                if values["readingRevision"] is None or values["odometer"] is None:
                    raise ValidationError("A linked record correction requires the source reading revision and decimal value.")
                if linked["revision"] != values["readingRevision"]:
                    raise Conflict("Source reading revision changed.")
                if old_row["revision"] >= 2147483646 or linked["revision"] >= 2147483646:
                    raise Conflict("Record or reading revision cannot be advanced.")
                if old_row["day"] == values["date"] and old_row["odometer"] == values["odometer"]:
                    raise ValidationError("Correction must change the record date or odometer value.")
                current_before = self._current_reading(db, vehicle_id)
                before_record, before_reading = self._record(old_row), self._reading(linked)
                db.execute("UPDATE records SET day=?,odometer=?,revision=revision+1 WHERE vehicle_id=? AND id=?",
                           (values["date"], values["odometer"], vehicle_id, record_id))
                db.execute("""UPDATE odometer_readings SET day=?,value=?,revision=revision+1
                    WHERE vehicle_id=? AND id=?""",
                    (values["date"], values["odometer"], vehicle_id, linked["id"]))
                updated_record = self._record(db.execute("SELECT * FROM records WHERE vehicle_id=? AND id=?",
                                                         (vehicle_id, record_id)).fetchone())
                updated_reading = self._reading(db.execute("SELECT * FROM odometer_readings WHERE id=?",
                                                           (linked["id"],)).fetchone())
                current_after = self._current_reading(db, vehicle_id)
                before = {"record": before_record, "reading": before_reading}
                after = {"record": updated_record, "reading": updated_reading,
                         "correctionReason": values["correctionReason"]}
                response = {"record": updated_record, "reading": updated_reading,
                            "currentReadingBefore": current_before, "currentReadingAfter": current_after}
            self._audit(db, vehicle_id, "record.measurement-corrected", before, after)
            self._remember(db, vehicle_id, action, values["commandId"], digest, response)
            return response

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
                db.execute("""INSERT INTO odometer_readings
                    (vehicle_id,day,value,unit,note,revision,provenance,source_record_id)
                    VALUES(?,?,?,?,?,1,'record',?)""",
                    (vehicle_id, day, odometer, vehicle["odometerUnit"], f"Record {record_id}", record_id))
            self._audit(db, vehicle_id, "record.created", None, record)
            result = {"record": record, "status": after}
            self._remember(db, vehicle_id, "record", command_id, digest, result)
            return result

    def get_summary(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            vehicle = self._vehicle(db, vehicle_id)
            projected_vehicle = self._with_mileage_projection(db, vehicle, self._today())
            records = [self._record(row) for row in db.execute("SELECT * FROM records WHERE vehicle_id=? ORDER BY day DESC,id DESC", (vehicle_id,))]
            return {"vehicle": projected_vehicle, "status": vehicle["status"], "reminders": [], "services": records}

    def list_history(self, vehicle_id):
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            self._vehicle(db, vehicle_id)
            return [{"sequence": row["sequence"], "action": row["action"], "occurredAt": row["occurred_at"], "before": json.loads(row["before_json"]), "after": json.loads(row["after_json"])}
                    for row in db.execute("SELECT * FROM history WHERE vehicle_id=? ORDER BY sequence", (vehicle_id,))]

    def export_data(self):
        """Return an owner data export from one consistent read transaction.

        This is a data portability view, not a restorable database backup. It
        deliberately excludes command replay state and other internal tables.
        """
        with closing(self._connect()) as db:
            db.execute("BEGIN")
            try:
                exported_at = datetime.now(timezone.utc).isoformat()
                vehicles = []
                statuses = []
                for row in db.execute("SELECT * FROM vehicles ORDER BY id"):
                    vehicle_id = row["id"]
                    vehicles.append({
                        "id": vehicle_id, "make": row["make"], "model": row["model"],
                        "name": row["name"], "year": row["year"],
                        "licensePlate": row["license_plate"], "vehicleType": row["vehicle_type"],
                        "odometerUnit": row["unit"], "revision": row["revision"],
                        "inspectionDueMonth": row["inspection_due_month"],
                        "annualUsage": row["annual_usage"],
                        "readingPromptDays": row["reading_prompt_days"],
                    })
                    status = self._status(db, vehicle_id)
                    statuses.append({"vehicleId": vehicle_id, **status})

                readings = [
                    {"id": row["id"], "vehicleId": row["vehicle_id"], "date": row["day"],
                     "odometer": row["value"], "unit": row["unit"], "note": row["note"],
                     "revision": row["revision"], "provenance": row["provenance"],
                     "sourceRecordId": row["source_record_id"]}
                    for row in db.execute("SELECT * FROM odometer_readings ORDER BY id")
                ]
                records = [
                    {"id": row["id"], "vehicleId": row["vehicle_id"],
                     "description": row["description"], "kind": row["kind"], "date": row["day"],
                     "odometer": row["odometer"], "odometerUnit": row["unit"],
                     "cost": row["cost"], "currency": row["currency"],
                     "documentUrl": row["document_url"], "closedIssueId": row["closed_issue_id"],
                     "revision": row["revision"]}
                    for row in db.execute("SELECT * FROM records ORDER BY id")
                ]
                history = [
                    {"sequence": row["sequence"], "action": row["action"],
                     "occurredAt": row["occurred_at"], "vehicleId": row["vehicle_id"],
                     "before": json.loads(row["before_json"]), "after": json.loads(row["after_json"])}
                    for row in db.execute("SELECT * FROM history ORDER BY sequence")
                ]
                result = {
                    "format": "wolfs-garage-owner-export", "formatVersion": 4,
                    "applicationVersion": __version__, "databaseSchema": SCHEMA,
                    "exportedAt": exported_at, "vehicles": vehicles, "statuses": statuses,
                    "odometerReadings": readings, "records": records, "history": history,
                }
                db.execute("COMMIT")
                return result
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise

    def export_to_file(self, destination):
        """Write a new restrictive owner export, never replacing a path."""
        data = self.export_data()
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2).encode("utf-8")
        path = os.fspath(destination)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = None
        created = False
        created_identity = None
        try:
            fd = os.open(path, flags, 0o600)
            created = True
            stat = os.fstat(fd)
            created_identity = (stat.st_dev, stat.st_ino)
            with os.fdopen(fd, "wb") as output:
                fd = None
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
        except BaseException:
            if fd is not None:
                os.close(fd)
            if created:
                try:
                    stat = os.stat(path, follow_symlinks=False)
                    if (stat.st_dev, stat.st_ino) == created_identity:
                        os.unlink(path)
                except FileNotFoundError:
                    pass
            raise
        return Path(path)

    def backup(self, destination):
        """Create a new consistent full-store backup with restrictive permissions."""
        source_uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(source_uri, uri=True, timeout=5)) as source:
            self._validate_restore_backup(source)
            self._new_backup(source, destination)

    def restore_backup(self, source_path, destination):
        """Restore a checked SQLite backup only to a new, non-live path.

        The destination is never replaced and no schema migration is performed.
        """
        source_path = Path(source_path)
        destination = Path(destination)
        if source_path.is_symlink() or not source_path.is_file():
            raise ValueError("Backup source must be an existing regular file.")
        if destination.is_symlink():
            raise FileExistsError("Restore destination must not be a symlink.")
        if source_path.resolve(strict=True) == destination.resolve(strict=False):
            raise ValueError("Restore source and destination must differ.")
        if destination.resolve(strict=False) == self.path.resolve(strict=False):
            raise ValueError("Restore destination must not be the live database path.")
        if not destination.parent.is_dir():
            raise FileNotFoundError("Restore destination directory does not exist.")
        sidecars = [Path(os.fspath(destination) + suffix) for suffix in ("-wal", "-shm", "-journal")]
        if any(path.exists() or path.is_symlink() for path in sidecars):
            raise FileExistsError("Restore destination has existing SQLite sidecar files.")

        source_uri = source_path.resolve(strict=True).as_uri() + "?mode=ro"
        destination_created = False
        destination_identity = None
        try:
            with closing(sqlite3.connect(source_uri, uri=True, timeout=5)) as source:
                schema = self._validate_restore_backup(source)
                fd = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY |
                             getattr(os, "O_NOFOLLOW", 0), 0o600)
                destination_created = True
                try:
                    os.fchmod(fd, 0o600)
                    stat = os.fstat(fd)
                    destination_identity = (stat.st_dev, stat.st_ino)
                finally:
                    os.close(fd)

                with closing(sqlite3.connect(destination, timeout=5)) as target:
                    source.backup(target)
                    if self._validate_restore_backup(target) != schema:
                        raise sqlite3.DatabaseError("Restored backup schema changed.")

            saved_fd = os.open(destination, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            try:
                saved_stat = os.fstat(saved_fd)
                if (saved_stat.st_dev, saved_stat.st_ino) != destination_identity:
                    raise OSError("Restore destination changed while being written.")
                os.fsync(saved_fd)
            finally:
                os.close(saved_fd)
            directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            if destination_created:
                try:
                    current = os.stat(destination, follow_symlinks=False)
                    if (current.st_dev, current.st_ino) == destination_identity:
                        os.unlink(destination)
                except FileNotFoundError:
                    pass
                for sidecar in sidecars:
                    try:
                        if sidecar.is_file() and not sidecar.is_symlink():
                            sidecar.unlink()
                    except FileNotFoundError:
                        pass
                try:
                    directory_fd = os.open(destination.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                    try:
                        os.fsync(directory_fd)
                    finally:
                        os.close(directory_fd)
                except OSError:
                    pass
            raise
        return destination
