"""Explicit local administration; never initializes an existing store silently."""
import argparse
import os
from pathlib import Path
import sqlite3

from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Wolfs Garage database administration")
    parser.add_argument("command", choices=["init-db", "backup", "check-db"])
    parser.add_argument("destination", nargs="?")
    args = parser.parse_args()
    path = Path(os.environ.get("GARAGE_DB", "data/garage.sqlite3"))
    store = Store(path)
    try:
        if args.command == "init-db":
            path.parent.mkdir(parents=True, exist_ok=True)
            store.initialize()
            print("Empty garage database initialized.")
        elif args.command == "backup":
            if not args.destination:
                parser.error("backup requires a new destination filename")
            store.backup(args.destination)
            print("Consistent garage backup created and checked.")
        else:
            vehicles = store.list_vehicles()
            print(f"Garage database readable; vehicles: {len(vehicles)}.")
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise SystemExit(f"Database operation failed ({type(exc).__name__}); check path, permissions and schema.") from None


if __name__ == "__main__":
    main()
