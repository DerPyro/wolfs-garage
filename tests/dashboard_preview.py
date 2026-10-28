"""Run a localhost-only dashboard preview backed by synthetic data."""
import sys
import threading
import json
import tempfile
import os
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'garage_gateway'))
import server
import status_store
from test_server import Stub

class PreviewStub(Stub):
    def do_GET(self):
        if self.path != '/api/vehicles':
            return super().do_GET()
        data = [
            {'id': 7, 'make': 'Peugeot', 'model': 'Muster', 'year': 2020,
             'licensePlate': 'XY AB 123', 'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'Limousine'}]},
            {'id': 8, 'make': 'Yamaha', 'model': 'Muster', 'year': 2000, 'licensePlate': 'XY C 42',
             'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'Cross-Motorrad'}]},
            {'id': 9, 'make': 'Opel', 'model': 'Muster', 'year': 2022,
             'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'Hochdachkombi'}]},
            {'id': 10, 'make': 'Suzuki', 'model': 'Muster', 'year': 2020,
             'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'Naked Bike'}]},
            {'id': 11, 'make': 'Opel', 'model': 'Muster2', 'year': 2004,
             'extraFields': [{'name': 'Fahrzeugtyp', 'value': 'Schrägheck'}]},
        ]
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


upstream = ThreadingHTTPServer(('127.0.0.1', 0), PreviewStub)
server.UPSTREAM = f'http://127.0.0.1:{upstream.server_port}'
server.PUBLIC_ORIGIN = os.environ.get('GARAGE_PREVIEW_PUBLIC_ORIGIN', '')
preview_dir = Path(tempfile.mkdtemp(prefix='wolfs-garage-preview-'))
server.STATUS_DB = str(preview_dir / 'status.sqlite3')
status_store.initialize(server.STATUS_DB)
status_store.update(server.STATUS_DB,
                    {'id': 7, 'make': 'Peugeot', 'model': 'Muster', 'year': 2020},
                    server.PROVIDER_ID,
                    {'readiness': 'ready', 'issues': [{'text': 'Inspektion prüfen'}], 'revision': 0})
status_store.update(server.STATUS_DB,
                    {'id': 8, 'make': 'Yamaha', 'model': 'Muster', 'year': 2000},
                    server.PROVIDER_ID,
                    {'readiness': 'not_ready', 'issues': [{'text': 'Beispielreparatur offen'}], 'revision': 0})
threading.Thread(target=upstream.serve_forever, daemon=True).start()
dashboard = ThreadingHTTPServer(('127.0.0.1', 18980), server.Handler)
print(f'Synthetic dashboard: http://127.0.0.1:18980/; synthetic store: {preview_dir}', flush=True)
try:
    dashboard.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    dashboard.server_close()
    upstream.shutdown()
    upstream.server_close()
