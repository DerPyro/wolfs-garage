import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import backup_status
import status_store


class BackupTests(unittest.TestCase):
    def test_snapshot_preserves_state_and_audit_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, copy = Path(tmp) / 'source.sqlite3', Path(tmp) / 'copy.sqlite3'
            status_store.initialize(source)
            vehicle = {'id': 7, 'make': 'Beispiel', 'model': 'Auto', 'year': 2020}
            status_store.update(source, vehicle, 'test-provider',
                                {'readiness': 'ready', 'issues': [{'text': 'Prüfen'}], 'revision': 0})
            backup_status.backup_status(source, copy)
            self.assertEqual(status_store.read_many(copy, [vehicle], 'test-provider')[7]['readiness'], 'ready')
            with closing(sqlite3.connect(copy)) as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM audit').fetchone(), (1,))
            self.assertEqual(os.stat(copy).st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                backup_status.backup_status(source, copy)

    def test_missing_source_does_not_create_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'backup.sqlite3'
            with self.assertRaises(sqlite3.Error):
                backup_status.backup_status(Path(tmp) / 'missing.sqlite3', dest)
            self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()
