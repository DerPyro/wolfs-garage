"""Ephemeral, shared public demo backed by a disposable schema-6 database."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import shutil
import threading
import time
import uuid
import fcntl
import stat
import tempfile
from zoneinfo import ZoneInfo
from werkzeug.test import Client

from .api import create_app
from .store import Store, ValidationError


class DemoQuotaExceeded(ValidationError):
    pass


class DemoStore(Store):
    """Store with transactional row quotas and a bounded SQLite file size."""

    QUOTAS = {"vehicles": 20, "odometer_readings": 2000, "records": 2000,
              "history": 6000, "commands": 2000}

    def _connect(self):
        db = super()._connect()
        try:
            db.execute("PRAGMA max_page_count=8192")
            return db
        except BaseException:
            db.close()
            raise

    def _transaction(self):
        from contextlib import contextmanager

        @contextmanager
        def transaction():
            with closing(self._connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    yield db
                    for table, limit in self.QUOTAS.items():
                        if db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] > limit:
                            raise DemoQuotaExceeded("Demo-Speicherlimit erreicht.")
                    db.execute("COMMIT")
                except BaseException:
                    if db.in_transaction:
                        db.execute("ROLLBACK")
                    raise
        return transaction()


def _berlin_today():
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def _month_offset(today, offset):
    month = today.month - 1 + offset
    year = today.year + month // 12
    month = month % 12 + 1
    return f"{year:04d}-{month:02d}"


def _seed(store):
    today = store.today_provider()
    vehicles = [
        ("Peugeot", "508", "Peugeot 508 · Demo", 2018, "DEMO-508", "Limousine", "km", 14500, _month_offset(today, 5), "ready", [
            {"text": "Reifenwechsel vormerken", "dueDate": (today + timedelta(days=14)).isoformat(), "severity": "observation"}]),
        ("Yamaha", "WR250F", "Yamaha WR250F · Demo", 2022, "DEMO-WR250", "Cross-Motorrad", "km", 4200, _month_offset(today, 8), "ready", []),
        ("Opel", "Combo", "Opel Combo · Demo", 2020, "DEMO-COMBO", "Hochdachkombi", "km", 11200, _month_offset(today, 0), "not_ready", [
            {"text": "Schiebetür läuft schwergängig", "severity": "repair", "lifecycle": "observed"},
            {"text": "Kühlmittelstand beobachten", "severity": "critical", "dueDate": (today - timedelta(days=2)).isoformat()}]),
        ("Suzuki", "SV650", "Suzuki SV650 · Demo", 2019, "DEMO-SV650", "Naked-Bike", "km", 5800, None, "unknown", []),
        ("Toyota", "Corolla", "Toyota Corolla · Demo", 2016, "DEMO-COROLLA", "Schrägheck", "km", 9600, _month_offset(today, -2), "ready", [
            {"text": "Leichte Vibration bei Autobahntempo prüfen", "severity": "observation"}]),
    ]
    for index, (make, model, name, year, plate, vtype, unit, annual, inspection, readiness, issues) in enumerate(vehicles):
        vehicle = store.create_vehicle({"make": make, "model": model, "name": name, "year": year,
            "licensePlate": plate, "vehicleType": vtype, "odometerUnit": unit,
            "annualUsage": str(annual), "inspectionDueMonth": inspection})
        vehicle_id = vehicle["id"]
        store.update_status(vehicle_id, {"readiness": readiness, "issues": issues, "revision": 0})
        base = today - timedelta(days=380 + index * 19)
        prior = 25000 + index * 17000
        for offset in (0, 190, 365):
            store.add_odometer(vehicle_id, {"date": (base + timedelta(days=offset)).isoformat(),
                "odometer": str(prior + offset * (30 + index)), "unit": unit,
                "note": "Beispielablesung", "commandId": uuid.uuid4().hex})
        for record_index, offset in enumerate((80, 300)):
            store.add_record(vehicle_id, {"description": ("Inspektion und Ölwechsel" if record_index == 0 else "Bremsen geprüft"),
                "kind": ("service" if record_index == 0 else "repair"),
                "date": (base + timedelta(days=offset)).isoformat(),
                "odometer": str(prior + offset * (30 + index)), "cost": ("185.00" if record_index == 0 else "72.50"),
                "currency": "EUR", "commandId": uuid.uuid4().hex})


def _new_generation(temp_parent=None, today_provider=None, public_origin=None):
    directory = tempfile.mkdtemp(prefix="wolfs-garage-demo-", dir=temp_parent)
    os.chmod(directory, 0o700)
    db_path = Path(directory) / "garage.sqlite3"
    store = DemoStore(db_path, today_provider=today_provider)
    try:
        store.initialize()
        _seed(store)
        generation = uuid.uuid4().hex
        reset_at = datetime.now(timezone.utc) + timedelta(hours=1)
        app = create_app({
            "GARAGE_DB": str(db_path), "GARAGE_PUBLIC_ORIGIN": public_origin,
            "MAX_CONTENT_LENGTH": 16 * 1024, "GARAGE_STORE_FACTORY": DemoStore,
            "GARAGE_TODAY_PROVIDER": today_provider,
            "GARAGE_DEMO": {"shared": True, "generation": generation,
                            "resetAt": reset_at.isoformat()},
        })
        return app, directory, generation
    except BaseException:
        shutil.rmtree(directory, ignore_errors=True)
        raise


def _runtime_parent():
    """Create and lock the one private process runtime, reaping its old generations."""
    parent = Path("/tmp/wolfs-garage-demo-runtime")
    try:
        parent.mkdir(mode=0o700)
    except FileExistsError:
        pass
    info = parent.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise RuntimeError("Demo runtime directory must be an owned private directory.")
    lock_path = parent / "process.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        os.close(fd)
        raise RuntimeError("Demo runtime lock must be an owned private file.")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise RuntimeError("Only one demo worker process is supported.") from exc
    for entry in parent.iterdir():
        if entry.name.startswith("wolfs-garage-demo-") and entry.is_dir() and not entry.is_symlink():
            shutil.rmtree(entry, ignore_errors=True)
    return parent, fd


class _LockedIterable:
    def __init__(self, iterable, lock):
        self._iterable = iterable
        self._lock = lock
        self._closed = False

    def __iter__(self):
        return iter(self._iterable)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            close = getattr(self._iterable, "close", None)
            if close:
                close()
        finally:
            self._lock.release()


class DemoApplication:
    """Serialize request lifetimes so generation replacement cannot race a response."""

    def __init__(self, config=None, *, monotonic=None, temp_parent=None):
        config = dict(config or {})
        self._clock = monotonic or time.monotonic
        if temp_parent is None:
            self._temp_parent, self._runtime_lock_fd = _runtime_parent()
        else:
            self._temp_parent, self._runtime_lock_fd = temp_parent, None
        self._today_provider = config.get("GARAGE_TODAY_PROVIDER")
        self._public_origin = (config.get("GARAGE_PUBLIC_ORIGIN")
                               or os.environ.get("GARAGE_PUBLIC_ORIGIN", "http://localhost:8080"))
        self._lock = threading.RLock()
        try:
            self._app, self._directory, self._generation = _new_generation(self._temp_parent, self._today_provider, self._public_origin)
        except BaseException:
            if self._runtime_lock_fd is not None:
                os.close(self._runtime_lock_fd)
            raise
        self._created_at = self._clock()

    def __call__(self, environ, start_response):
        self._lock.acquire()
        try:
            now = self._clock()
            if now - self._created_at >= 3600:
                old_directory = self._directory
                self._app, self._directory, self._generation = _new_generation(self._temp_parent, self._today_provider, self._public_origin)
                self._created_at = now
                shutil.rmtree(old_directory, ignore_errors=True)
            iterable = self._app(environ, start_response)
            return _LockedIterable(iterable, self._lock)
        except BaseException:
            self._lock.release()
            raise

    def test_client(self, **kwargs):
        """Convenience for Flask-style tests while preserving the WSGI wrapper."""
        response_class = self._app.response_class
        return Client(self, response_wrapper=response_class, **kwargs)


def create_demo_app(config=None, *, monotonic=None, temp_parent=None):
    """Create demo WSGI app. ``monotonic`` and ``temp_parent`` support isolated tests."""
    return DemoApplication(config, monotonic=monotonic, temp_parent=temp_parent)
