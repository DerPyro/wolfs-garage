"""Create a fresh schema-5 browser fixture by explicitly upgrading synthetic schema 4."""
import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

from wolfs_garage.store import Store


def prepare(database_path, backup_path):
    database_path, backup_path = Path(database_path), Path(backup_path)
    if database_path.resolve() == backup_path.resolve():
        raise ValueError("database and backup paths must differ")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if database_path.exists() or database_path.is_symlink() or backup_path.exists() or backup_path.is_symlink():
        raise FileExistsError("choose new database and backup paths")
    fixture = Path(__file__).parent / "fixtures" / "schema4_fixture.txt"
    with closing(sqlite3.connect(database_path)) as db:
        db.executescript(fixture.read_text(encoding="utf-8"))
        with db:
            # This second old reading has no matching record and can only be
            # classified as manual after the migration, by explicit test action.
            db.execute("INSERT INTO odometer_readings VALUES(18,7,'2025-03-01','900.5','km','Synthetic old standalone reading')")
    if not Store(database_path).upgrade(backup_path):
        raise RuntimeError("fresh schema-4 fixture did not upgrade")
    if Store(database_path).list_vehicles()[0]["id"] != 7:
        raise RuntimeError("synthetic vehicle fixture is missing")
    return database_path, backup_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database_path", type=Path, help="new isolated browser database path")
    parser.add_argument("backup_path", type=Path, help="new checked schema-4 backup path")
    args = parser.parse_args()
    database, backup = prepare(args.database_path, args.backup_path)
    print(f"Prepared synthetic schema-5 fixture: {database}; checked schema-4 backup: {backup}")


if __name__ == "__main__":
    main()
