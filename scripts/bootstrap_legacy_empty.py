"""Create a new, empty-history Garage database from a private legacy snapshot.

This is a deliberately bounded bootstrap, not a LubeLogger record importer.
It never connects to or writes to LubeLogger.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wolfs_garage.store import Store, ValidationError


FORMAT = "wolfs-garage-legacy-bootstrap-v1"
RECORD_CATEGORIES = ("odometerrecords", "servicerecords", "repairrecords",
                     "supplyrecords", "reminders", "planrecords", "taxrecords")
VEHICLE_FIELDS = {"id", "make", "model", "year", "licensePlate",
                  "vehicleType", "name", "odometer"}
UNITS = {"km", "mi", "h"}


def _fail(message):
    raise ValueError(message)


def _strict_json(path):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Snapshot contains a duplicate JSON key.")
            result[key] = value
        return result

    with Path(path).open("r", encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=object_pairs,
                         parse_constant=lambda value: _fail("Snapshot contains a non-finite number."))


def validate_snapshot(snapshot, new_reading_unit):
    """Validate the complete private snapshot before creating any output."""
    if not isinstance(snapshot, dict) or set(snapshot) != {"format", "vehicles", "sourceVehicles", "records"}:
        _fail("Snapshot must contain exactly format, vehicles, sourceVehicles, and records.")
    if snapshot["format"] != FORMAT:
        _fail("Unsupported legacy bootstrap snapshot format.")
    if not isinstance(new_reading_unit, str) or new_reading_unit not in UNITS:
        _fail("New-reading unit must be km, mi, or h; no legacy unit is inferred.")
    vehicles, source_vehicles, records = snapshot["vehicles"], snapshot["sourceVehicles"], snapshot["records"]
    if not isinstance(vehicles, list) or not vehicles:
        _fail("Snapshot must contain at least one normalized vehicle.")
    if not isinstance(source_vehicles, list) or not isinstance(records, dict):
        _fail("Snapshot source vehicles or record collections are invalid.")

    normalized_by_id = {}
    for vehicle in vehicles:
        if not isinstance(vehicle, dict) or set(vehicle) != VEHICLE_FIELDS:
            _fail("A normalized vehicle has unexpected or missing fields.")
        source_id = vehicle["id"]
        if not isinstance(source_id, (str, int)) or isinstance(source_id, bool) or not str(source_id):
            _fail("A normalized vehicle has an invalid source ID.")
        source_id = str(source_id)
        if source_id in normalized_by_id:
            _fail("Normalized vehicle source IDs must be unique.")
        if vehicle["odometer"] is not None:
            _fail("Bootstrap requires every normalized vehicle odometer to be null; import readings separately.")
        normalized_by_id[source_id] = vehicle

    raw_by_id = {}
    for vehicle in source_vehicles:
        if not isinstance(vehicle, dict) or "id" not in vehicle:
            _fail("A raw source vehicle is missing its ID.")
        source_id = vehicle["id"]
        if not isinstance(source_id, (str, int)) or isinstance(source_id, bool) or not str(source_id):
            _fail("A raw source vehicle has an invalid ID.")
        source_id = str(source_id)
        if source_id in raw_by_id:
            _fail("Raw source vehicle IDs must be unique.")
        raw_by_id[source_id] = vehicle

    if set(raw_by_id) != set(normalized_by_id) or set(records) != set(normalized_by_id):
        _fail("Normalized vehicles, raw source vehicles, and record groups must have identical IDs.")

    accepted = []
    for source_id, vehicle in normalized_by_id.items():
        collection = records[source_id]
        if not isinstance(collection, dict) or set(collection) != set(RECORD_CATEGORIES):
            _fail(f"Source vehicle {source_id} has an invalid record-category set.")
        if any(not isinstance(collection[name], list) or collection[name] for name in RECORD_CATEGORIES):
            _fail(f"Source vehicle {source_id} has history; this bootstrap accepts empty record lists only.")
        accepted.append({
            "sourceId": source_id,
            "make": vehicle["make"],
            "model": vehicle["model"],
            "year": vehicle["year"],
            "licensePlate": vehicle["licensePlate"],
            "vehicleType": vehicle["vehicleType"],
            "name": vehicle["name"],
            "odometerUnit": new_reading_unit,
        })
    return accepted


def _write_exclusive(path, content):
    path = Path(path)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def create_database(snapshot, destination, id_map_path, new_reading_unit):
    vehicles = validate_snapshot(snapshot, new_reading_unit)
    destination, id_map_path = Path(destination), Path(id_map_path)
    if destination.absolute() == id_map_path.absolute():
        _fail("Database and ID map must use different paths.")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    id_map_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if destination.exists() or destination.is_symlink() or id_map_path.exists() or id_map_path.is_symlink():
        _fail("Database and ID map must both be new paths.")

    temporary = destination.with_name(f".{destination.name}.bootstrap-{uuid.uuid4().hex}.tmp")
    created_map = False
    published_db = False
    try:
        store = Store(temporary)
        store.initialize()
        mapping = {}
        for item in vehicles:
            created = store.create_vehicle({key: item[key] for key in (
                "make", "model", "year", "licensePlate", "vehicleType", "name", "odometerUnit")})
            mapping[item["sourceId"]] = created["id"]

        map_json = json.dumps({"format": FORMAT, "sourceToLocalVehicleIds": mapping},
                              ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
        _write_exclusive(id_map_path, map_json)
        created_map = True
        # Hard-link publication is atomic and refuses an existing destination.
        os.link(temporary, destination, follow_symlinks=False)
        published_db = True
        temporary.unlink()
        return mapping
    except BaseException:
        if published_db:
            try:
                destination.unlink()
            except OSError:
                pass
        if created_map:
            try:
                id_map_path.unlink()
            except OSError:
                pass
        raise
    finally:
        for suffix in ("", "-journal", "-wal", "-shm"):
            try:
                Path(str(temporary) + suffix).unlink()
            except FileNotFoundError:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bootstrap a new Garage database from a private empty-history snapshot")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("destination", type=Path, help="new SQLite database path")
    parser.add_argument("id_map", type=Path, help="new private source-to-local ID map path")
    parser.add_argument("--new-reading-unit", required=True, choices=sorted(UNITS),
                        help="explicit unit for future readings; never inferred from legacy metadata")
    args = parser.parse_args(argv)
    try:
        snapshot = _strict_json(args.snapshot)
        create_database(snapshot, args.destination, args.id_map, args.new_reading_unit)
    except (OSError, ValueError, ValidationError) as exc:
        raise SystemExit(f"Legacy bootstrap failed ({type(exc).__name__}); no source data was changed.") from None
    print("New empty-history Garage database created; source ID map written separately.")


if __name__ == "__main__":
    main()
