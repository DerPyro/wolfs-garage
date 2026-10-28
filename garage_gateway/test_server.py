import json
import threading
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import server
import status_store


class Stub(BaseHTTPRequestHandler):
    calls = []
    def log_message(self, *args): pass
    def do_GET(self):
        Stub.calls.append(self.path)
        if self.path == '/api/vehicles':
            data = [{'id': 7, 'make': 'Test', 'model': 'Auto', 'year': 2020, 'licensePlate': 'XX-TEST',
                     'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'Limousine'}]}]
        elif self.path == '/api/vehicle/reminders?vehicleId=7':
            data = [{'description': 'Wartung', 'metric': 'Date', 'dueDate': '30.10.2026', 'urgency': 'PastDue'}]
        elif self.path == '/api/vehicle/servicerecords?vehicleId=7':
            data = [{'description': 'Prüfung', 'date': '01.10.2026', 'cost': '12.50', 'odometer': '123'}]
        else:
            self.send_error(404); return
        body = json.dumps(data).encode()
        self.send_response(200); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        server.STATUS_DB = str(Path(cls.tmp.name) / 'status.sqlite3')
        status_store.initialize(server.STATUS_DB)
        server.PUBLIC_ORIGIN = 'https://garage.example.test'
        cls.upstream = ThreadingHTTPServer(('127.0.0.1', 0), Stub)
        cls.api = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        server.UPSTREAM = 'http://127.0.0.1:%s' % cls.upstream.server_port
        cls.base = 'http://127.0.0.1:%s' % cls.api.server_port
        for service in (cls.upstream, cls.api): threading.Thread(target=service.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        for service in (cls.upstream, cls.api): service.shutdown(); service.server_close()
        cls.tmp.cleanup()

    def test_overview_uses_only_documented_reads(self):
        Stub.calls.clear()
        result = json.load(urlopen(self.base + '/garage-api/vehicles/7/summary'))
        self.assertEqual(result['vehicle']['name'], 'Test Auto')
        self.assertEqual(result['vehicle']['vehicleType'], 'Limousine')
        self.assertIsNone(result['vehicle']['odometer'])
        self.assertEqual(result['reminders'][0]['description'], 'Wartung')
        self.assertEqual(result['services'][0]['cost'], 12.5)
        self.assertEqual(Stub.calls, ['/api/vehicles', '/api/vehicle/reminders?vehicleId=7', '/api/vehicle/servicerecords?vehicleId=7'])

    def test_unknown_vehicle_never_requests_vehicle_details(self):
        Stub.calls.clear()
        with self.assertRaises(HTTPError) as err: urlopen(self.base + '/garage-api/vehicles/9/summary')
        self.assertEqual(err.exception.code, 404)
        self.assertEqual(Stub.calls, ['/api/vehicles'])

    def test_backend_has_no_upstream_write_or_native_proxy(self):
        Stub.calls.clear()
        with self.assertRaises(HTTPError) as err: urlopen(Request(self.base + '/garage-api/vehicles', data=b'{}', method='POST'))
        self.assertEqual(err.exception.code, 501)
        with self.assertRaises(HTTPError) as err: urlopen(self.base + '/Home')
        self.assertEqual(err.exception.code, 404)
        self.assertEqual(Stub.calls, [])

    def test_missing_upstream_fails_closed(self):
        saved = server.UPSTREAM
        server.UPSTREAM = 'http://127.0.0.1:1'
        try:
            with self.assertRaises(HTTPError) as err: urlopen(self.base + '/garage-api/vehicles')
            self.assertEqual(err.exception.code, 502)
            self.assertNotIn('127.0.0.1', err.exception.read().decode())
        finally: server.UPSTREAM = saved

    def test_type_comes_only_from_vehicle_extra_field(self):
        self.assertEqual(server.vehicle({'extraFields': [{'name': 'Fahrzeugtyp', 'value': ' Limousine '}]})['vehicleType'], 'Limousine')
        self.assertEqual(server.vehicle({'extraFields': [{'name': ' fahrzeugtyp ', 'value': 'Cross-Motorrad'}]})['vehicleType'], 'Cross-Motorrad')
        self.assertIsNone(server.vehicle({'make': 'Yamaha', 'model': 'XT500'})['vehicleType'])
        self.assertIsNone(server.vehicle({'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'A'}, {'name': 'fahrzeugtyp', 'value': 'B'}]})['vehicleType'])
        self.assertIsNone(server.vehicle({'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'x\nInjected'}]})['vehicleType'])
        self.assertIsNone(server.vehicle({'extraFields': 'unexpected'})['vehicleType'])

    def test_type_override_is_exact_and_explicit_extra_field_wins(self):
        mapping = {('example', 'road 1'): 'Limousine'}
        with patch.object(server, 'TYPE_OVERRIDES', mapping):
            self.assertEqual(server.vehicle({'make':'  Example ', 'model':'ROAD   1'})['vehicleType'], 'Limousine')
            self.assertIsNone(server.vehicle({'make':'Example', 'model':'ROAD 10'})['vehicleType'])
            self.assertEqual(server.vehicle({'make':'Example', 'model':'Road 1', 'extraFields':[{'name':'Fahrzeugtyp', 'value':'Kombi'}]})['vehicleType'], 'Kombi')
            self.assertIsNone(server.vehicle({'make':'Example', 'model':'Road 1', 'extraFields':[{'name':'Fahrzeugtyp', 'value':'A'}, {'name':'Fahrzeugtyp', 'value':'B'}]})['vehicleType'])

    def test_config_requires_valid_unambiguous_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            filename = Path(tmp) / 'types.json'
            filename.write_text(json.dumps({'vehicleTypes':[{'make':'Example', 'model':'Road 1', 'type':'Cross-Motorrad'}]}))
            self.assertEqual(server.load_vehicle_type_overrides(str(filename)), {('example', 'road 1'):'Cross-Motorrad'})
            filename.write_text(json.dumps({'vehicleTypes':[{'make':'Example', 'model':'Road 1', 'type':'A'}, {'make':'example', 'model':'ROAD 1', 'type':'B'}]}))
            with self.assertRaises(ValueError): server.load_vehicle_type_overrides(str(filename))

if __name__ == '__main__': unittest.main()
