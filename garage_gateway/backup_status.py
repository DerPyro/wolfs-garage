"""Create a consistent, exclusive SQLite backup of the vehicle status store."""
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path


def backup_status(source, destination):
    source_uri = Path(source).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(source_uri, uri=True, timeout=5)) as source_db:
        if source_db.execute('SELECT schema FROM meta').fetchall() != [(1,)]:
            raise sqlite3.DatabaseError('unsupported status schema')
        # Refuse existing files and symlinks; do not silently overwrite a backup.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(destination, flags, 0o600)
        os.close(fd)
        with closing(sqlite3.connect(destination, timeout=5)) as destination_db:
            source_db.backup(destination_db)
            if destination_db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise sqlite3.DatabaseError('backup integrity check failed')
        with open(destination, 'rb') as saved:
            os.fsync(saved.fileno())


if __name__ == '__main__':
    if len(sys.argv) != 2 or not os.environ.get('GARAGE_STATUS_DB'):
        raise SystemExit('Usage: GARAGE_STATUS_DB=/path/status.sqlite3 python3 backup_status.py /path/new-backup.sqlite3')
    try:
        backup_status(os.environ['GARAGE_STATUS_DB'], sys.argv[1])
    except (OSError, sqlite3.Error, ValueError):
        raise SystemExit('Status backup failed; check paths, permissions and source integrity.')
    print('Status backup created and SQLite integrity checked.')
