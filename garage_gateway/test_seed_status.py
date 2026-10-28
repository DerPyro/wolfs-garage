import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
import seed_status
import server
import status_store


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.vehicles = [{'id': 7, 'make': 'Beispiel', 'model': 'Auto', 'year': 2020},
                         {'id': 8, 'make': 'Beispiel', 'model': 'Zwei', 'year': 2021}]
        self.plan = {'entries': [{'make': 'BEISPIEL', 'models': ['Auto'], 'readiness': 'ready', 'issues': ['Prüfung']}]}

    def test_resolves_unique_exact_match_and_separate_issue(self):
        vehicle, payload = seed_status.resolve_entries(self.plan, self.vehicles)[0]
        self.assertEqual(vehicle['id'], 7)
        self.assertEqual(payload, {'readiness': 'ready', 'issues': [{'text': 'Prüfung'}], 'revision': 0})

    def test_fails_before_writing_on_missing_or_ambiguous_match(self):
        with self.assertRaises(ValueError): seed_status.resolve_entries(self.plan, self.vehicles[1:])
        with self.assertRaises(ValueError): seed_status.resolve_entries(self.plan, self.vehicles + [dict(self.vehicles[0], id=9)])

    def test_cli_seeds_once_and_refuses_overwriting_existing_states(self):
        plan = {'entries': self.plan['entries'] + [{'make': 'Beispiel', 'models': ['Zwei'], 'readiness': 'not_ready', 'issues': ['Beispielproblem']}]}
        def input_stream(): return io.TextIOWrapper(io.BytesIO(json.dumps(plan).encode()))
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / 'status.sqlite3')
            status_store.initialize(path)
            with patch.object(server, 'STATUS_DB', path), patch.object(server, 'PROVIDER_ID', 'test'), patch.object(server, 'fetch', return_value=self.vehicles), redirect_stdout(io.StringIO()):
                with patch('sys.stdin', input_stream()): seed_status.main()
                with patch('sys.stdin', input_stream()), self.assertRaises(SystemExit): seed_status.main()
            rows = status_store.read_many(path, self.vehicles, 'test')
            self.assertEqual([rows[7]['readiness'], rows[8]['readiness']], ['ready', 'not_ready'])
            self.assertEqual([rows[7]['revision'], rows[8]['revision']], [1, 1])


if __name__ == '__main__': unittest.main()
