"""Explicitly initialized, transactional local vehicle status store."""
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
READINESS = {'ready', 'not_ready', 'unknown'}


class Conflict(Exception): pass
class IdentityMismatch(Exception): pass
class InvalidStatus(Exception): pass


def identity(vehicle, provider_id):
    """Detect changes to the provider vehicle identity, without storing its details."""
    def normalize(value):
        return ' '.join(str(value or '').split()).casefold()
    fields = [provider_id, normalize(vehicle.get('make')), normalize(vehicle.get('model')),
              normalize(vehicle.get('year'))]
    if not provider_id or not fields[1] or not fields[2] or not fields[3]:
        raise IdentityMismatch('vehicle identity incomplete')
    return hashlib.sha256(json.dumps(fields, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def initialize(path):
    """Create an empty store only when explicitly invoked by an operator."""
    if not path:
        raise ValueError('database path required')
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE meta (schema INTEGER NOT NULL)')
        db.execute('INSERT INTO meta(schema) VALUES (?)', (SCHEMA,))
        db.execute('CREATE TABLE states (vehicle_id INTEGER PRIMARY KEY, identity TEXT NOT NULL, revision INTEGER NOT NULL, readiness TEXT NOT NULL, issues TEXT NOT NULL)')
        db.execute('CREATE TABLE audit (sequence INTEGER PRIMARY KEY AUTOINCREMENT, vehicle_id INTEGER NOT NULL, occurred_at TEXT NOT NULL, revision INTEGER NOT NULL, before_json TEXT NOT NULL, after_json TEXT NOT NULL)')
        db.execute("CREATE TRIGGER audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END")
        db.execute("CREATE TRIGGER audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT, 'audit is append-only'); END")


def connect(path):
    if not path:
        raise sqlite3.OperationalError('status store not configured')
    uri = Path(path).resolve().as_uri() + '?mode=rw'
    db = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
    db.execute('PRAGMA busy_timeout=5000')
    try:
        rows = db.execute('SELECT schema FROM meta').fetchall()
        if rows != [(SCHEMA,)]:
            raise sqlite3.DatabaseError('unsupported status schema')
        return db
    except Exception:
        db.close()
        raise


def read_row(db, vehicle_id, fingerprint):
    row = db.execute('SELECT identity,revision,readiness,issues FROM states WHERE vehicle_id=?', (vehicle_id,)).fetchone()
    if not row:
        return {'readiness': 'unknown', 'issues': [], 'revision': 0}
    if row[0] != fingerprint:
        raise IdentityMismatch('vehicle identity changed')
    try:
        issues = json.loads(row[3])
        validate({'readiness': row[2], 'issues': issues, 'revision': row[1]})
        if any(not item.get('id') for item in issues):
            raise InvalidStatus('missing stored issue id')
    except (ValueError, TypeError, InvalidStatus) as exc:
        raise sqlite3.DatabaseError('corrupt status') from exc
    if not isinstance(row[1], int) or row[1] < 1:
        raise sqlite3.DatabaseError('corrupt status')
    return {'readiness': row[2], 'issues': issues, 'revision': row[1]}


def read_many(path, vehicles, provider_id):
    with closing(connect(path)) as db:
        db.execute('BEGIN')
        return {int(v['id']): read_row(db, int(v['id']), identity(v, provider_id)) for v in vehicles}


def validate(payload):
    if not isinstance(payload, dict) or set(payload) != {'readiness', 'issues', 'revision'}:
        raise InvalidStatus('invalid fields')
    revision = payload['revision']
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0 or revision > 2147483646:
        raise InvalidStatus('invalid revision')
    if not isinstance(payload['readiness'], str) or payload['readiness'] not in READINESS or not isinstance(payload['issues'], list) or len(payload['issues']) > 20:
        raise InvalidStatus('invalid status or issue count')
    issues = []
    seen = set()
    for item in payload['issues']:
        if not isinstance(item, dict) or not set(item).issubset({'id', 'text'}) or 'text' not in item:
            raise InvalidStatus('invalid issue')
        value = item['text']
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 160 or any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise InvalidStatus('invalid issue text')
        issue_id = item.get('id')
        if issue_id is not None and (not isinstance(issue_id, str) or len(issue_id) != 32 or any(c not in '0123456789abcdef' for c in issue_id)):
            raise InvalidStatus('invalid issue id')
        if issue_id in seen and issue_id is not None:
            raise InvalidStatus('duplicate issue id')
        seen.add(issue_id)
        issues.append({'id': issue_id, 'text': value.strip()})
    return revision, payload['readiness'], issues


def update(path, vehicle, provider_id, payload):
    return update_batch(path, provider_id, [(vehicle, payload)])[0]


def _update_in_transaction(db, vehicle, provider_id, payload):
    expected, readiness, items = validate(payload)
    vehicle_id = int(vehicle['id'])
    fingerprint = identity(vehicle, provider_id)
    before = read_row(db, vehicle_id, fingerprint)
    if before['revision'] != expected:
        raise Conflict('revision changed')
    existing = {item['id'] for item in before['issues']}
    if any(item['id'] is not None and item['id'] not in existing for item in items):
        raise InvalidStatus('unknown issue id')
    issues = [{'id': item['id'] or uuid.uuid4().hex, 'text': item['text']} for item in items]
    after = {'readiness': readiness, 'issues': issues, 'revision': expected + 1}
    db.execute('INSERT INTO states(vehicle_id,identity,revision,readiness,issues) VALUES(?,?,?,?,?) ON CONFLICT(vehicle_id) DO UPDATE SET revision=excluded.revision,readiness=excluded.readiness,issues=excluded.issues',
               (vehicle_id, fingerprint, after['revision'], readiness, json.dumps(issues, ensure_ascii=False)))
    db.execute('INSERT INTO audit(vehicle_id,occurred_at,revision,before_json,after_json) VALUES(?,?,?,?,?)',
               (vehicle_id, datetime.now(timezone.utc).isoformat(), after['revision'], json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False)))
    return after


def update_batch(path, provider_id, entries):
    """Write a bounded set of distinct vehicles and audit events atomically."""
    if not entries or len(entries) > 20:
        raise InvalidStatus('invalid batch size')
    ids = [int(vehicle['id']) for vehicle, _ in entries]
    if len(ids) != len(set(ids)):
        raise InvalidStatus('duplicate batch vehicle')
    db = connect(path)
    try:
        db.execute('BEGIN IMMEDIATE')
        result = [_update_in_transaction(db, vehicle, provider_id, payload) for vehicle, payload in entries]
        db.execute('COMMIT')
        return result
    except BaseException:
        if db.in_transaction:
            db.execute('ROLLBACK')
        raise
    finally:
        db.close()
