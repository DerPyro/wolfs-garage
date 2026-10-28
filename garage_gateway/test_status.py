import concurrent.futures
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

import server
import status_store
from test_server import Stub


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.tmp.name) / 'status.sqlite3')
        status_store.initialize(self.path)
        self.vehicle = {'id': 7, 'make': 'Test', 'model': 'Auto', 'year': 2020}

    def tearDown(self): self.tmp.cleanup()

    def test_persistence_updates_deletions_and_audit(self):
        first = status_store.update(self.path, self.vehicle, 'test', {'readiness':'not_ready', 'issues':[{'text':'Prüfung'}], 'revision':0})
        self.assertEqual(first['revision'], 1)
        self.assertEqual(status_store.read_many(self.path, [self.vehicle], 'test')[7], first)
        second = status_store.update(self.path, self.vehicle, 'test', {'readiness':'ready', 'issues':[], 'revision':1})
        self.assertEqual(second['issues'], [])
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute('SELECT before_json,after_json FROM audit ORDER BY sequence').fetchall()
            with self.assertRaises(sqlite3.IntegrityError): db.execute('DELETE FROM audit')
        self.assertEqual(len(rows), 2)
        self.assertEqual(json.loads(rows[1][0])['issues'][0]['text'], 'Prüfung')

    def test_concurrent_edits_use_revision_and_single_audit(self):
        payload = {'readiness':'ready', 'issues':[], 'revision':0}
        def apply():
            try: return status_store.update(self.path, self.vehicle, 'test', payload)['revision']
            except status_store.Conflict: return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: apply(), range(2)))
        self.assertCountEqual(results, [1, 'conflict'])
        with closing(sqlite3.connect(self.path)) as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM audit').fetchone()[0], 1)

    def test_batch_conflict_rolls_back_all_changes_and_audit(self):
        status_store.update(self.path, self.vehicle, 'test', {'readiness':'ready','issues':[],'revision':0})
        other = {'id': 8, 'make': 'Test', 'model': 'Zwei', 'year': 2020}
        entries = [(self.vehicle, {'readiness':'not_ready','issues':[],'revision':1}),
                   (other, {'readiness':'ready','issues':[],'revision':1})]
        with self.assertRaises(status_store.Conflict): status_store.update_batch(self.path, 'test', entries)
        statuses = status_store.read_many(self.path, [self.vehicle, other], 'test')
        self.assertEqual(statuses[7]['readiness'], 'ready')
        self.assertEqual(statuses[8]['revision'], 0)
        with closing(sqlite3.connect(self.path)) as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM audit').fetchone()[0], 1)

    def test_new_provider_or_changed_vehicle_does_not_inherit_status(self):
        status_store.update(self.path, self.vehicle, 'test', {'readiness':'ready','issues':[],'revision':0})
        with self.assertRaises(status_store.IdentityMismatch): status_store.read_many(self.path, [dict(self.vehicle,model='Andere')], 'test')
        with self.assertRaises(status_store.IdentityMismatch): status_store.read_many(self.path, [self.vehicle], 'other-instance')

    def test_invalid_issue_id_and_inputs(self):
        for payload in [
            {'readiness':'ready','issues':[{'id':'a'*32,'text':'x'}],'revision':0},
            {'readiness':'ready','issues':[{'text':'x\nnot allowed'}],'revision':0},
            {'readiness':[],'issues':[],'revision':0},
            {'readiness':'ready','issues':[{'text':'x'}]*21,'revision':0},
        ]:
            with self.assertRaises(status_store.InvalidStatus): status_store.update(self.path, self.vehicle, 'test', payload)

    def test_missing_or_corrupt_database_is_error_not_unknown(self):
        with self.assertRaises(sqlite3.Error): status_store.read_many(str(Path(self.tmp.name)/'missing'), [self.vehicle], 'test')
        with self.assertRaises(FileExistsError): status_store.initialize(self.path)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE meta SET schema=999')
        with self.assertRaises(sqlite3.Error): status_store.read_many(self.path, [self.vehicle], 'test')


class StatusHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        server.STATUS_DB = str(Path(cls.tmp.name)/'db')
        status_store.initialize(server.STATUS_DB)
        server.PUBLIC_ORIGIN = 'https://garage.example.test'
        cls.upstream = ThreadingHTTPServer(('127.0.0.1',0), Stub)
        cls.api = ThreadingHTTPServer(('127.0.0.1',0), server.Handler)
        server.UPSTREAM = f'http://127.0.0.1:{cls.upstream.server_port}'
        cls.base = f'http://127.0.0.1:{cls.api.server_port}'
        for s in (cls.upstream,cls.api): threading.Thread(target=s.serve_forever,daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for s in (cls.upstream,cls.api): s.shutdown(); s.server_close()
        cls.tmp.cleanup()

    def request(self, path, origin='https://garage.example.test', host='garage.example.test', headers=None, payload=None):
        h={'Host':host, 'Origin':origin, 'X-Garage-Request':'1', 'Content-Type':'application/json'}
        if headers: h.update(headers)
        req = Request(self.base+path, data=json.dumps(payload or {'readiness':'ready','issues':[],'revision':0}).encode(), headers=h, method='PUT')
        try:
            with urlopen(req) as response: return response.status, json.load(response)
        except HTTPError as exc: return exc.code, json.loads(exc.read())

    def test_cross_origin_host_header_and_content_type_rejected(self):
        path='/garage-api/vehicles/7/status'
        self.assertEqual(self.request(path,origin='https://evil.example')[0],403)
        self.assertEqual(self.request(path,host='evil.example')[0],403)
        self.assertEqual(self.request(path,headers={'X-Garage-Request':'0'})[0],403)
        self.assertEqual(self.request(path,headers={'Content-Type':'text/plain'})[0],403)
        self.assertEqual(self.request(path,headers={'Sec-Fetch-Site':'cross-site'})[0],403)

    def test_upstream_vehicle_validation_and_revision(self):
        self.assertEqual(self.request('/garage-api/vehicles/99/status')[0],404)
        code, response = self.request('/garage-api/vehicles/7/status')
        self.assertEqual(code,200); self.assertEqual(response['revision'],1)
        self.assertEqual(self.request('/garage-api/vehicles/7/status')[0],409)
        with urlopen(self.base+'/garage-api/vehicles/7/summary') as r:
            self.assertEqual(json.load(r)['status']['readiness'],'ready')

    def test_unconfigured_origin_and_missing_store_fail_closed(self):
        with patch.object(server,'PUBLIC_ORIGIN',''):
            self.assertEqual(self.request('/garage-api/vehicles/7/status')[0],503)
        with patch.object(server,'STATUS_DB',str(Path(self.tmp.name)/'missing')):
            with self.assertRaises(HTTPError) as exc: urlopen(self.base+'/garage-api/vehicles')
            self.assertEqual(exc.exception.code,503)
            self.assertEqual(self.request('/garage-api/vehicles/7/status')[0],503)
            self.assertFalse(Path(server.STATUS_DB).exists())


if __name__ == '__main__': unittest.main()
