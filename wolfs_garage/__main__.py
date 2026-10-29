"""Explicit local administration; never initializes an existing store silently."""
import argparse
import os
from pathlib import Path
import sqlite3

from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Wolfs Garage database administration")
    parser.add_argument("command", choices=["init-db", "backup", "check-db", "upgrade-db", "export", "restore-backup"])
    parser.add_argument("destination", nargs="?")
    parser.add_argument("restore_destination", nargs="?")
    args = parser.parse_args()
    if args.restore_destination and args.command != "restore-backup":
        parser.error(f"{args.command} accepts only one destination path")
    if args.command in {"init-db", "check-db"} and args.destination:
        parser.error(f"{args.command} does not accept a destination path")
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
        elif args.command == "export":
            if not args.destination:
                parser.error("export requires a new destination filename")
            store.export_to_file(args.destination)
            print("Owner data export created.")
        elif args.command == "restore-backup":
            if not args.destination or not args.restore_destination:
                parser.error("restore-backup requires SOURCE and NEW_DB_PATH")
            store.restore_backup(args.destination, args.restore_destination)
            print("Checked backup restored to a new database path; no schema upgrade was performed.")
        elif args.command == "upgrade-db":
            if args.restore_destination:
                parser.error("upgrade-db accepts only one destination filename")
            if not args.destination:
                parser.error("upgrade-db requires a new backup destination filename")
            print("Explicit schema upgrade requested. Stop the application first and test recovery on a separate database copy.")
            if store.upgrade(args.destination):
                print("Database upgraded to schema 6 after a checked backup was created.")
                print("Keep the backup until the upgraded database has been verified.")
            else:
                print("Database is already schema 6; no upgrade or backup file was written.")
        else:
            if args.destination or args.restore_destination:
                parser.error(f"{args.command} does not accept destination paths")
            vehicles = store.list_vehicles()
            print(f"Garage database readable; vehicles: {len(vehicles)}.")
    except (OSError, sqlite3.Error, ValueError) as exc:
        raise SystemExit(f"Database operation failed ({type(exc).__name__}); check path, permissions and schema.") from None


if __name__ == "__main__":
    main()
