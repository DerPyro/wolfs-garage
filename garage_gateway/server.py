"""Wolfs Garage adapter. Run behind the Access-protected reverse proxy."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError, URLError
import json
import mimetypes
import math
import os
import re
import sqlite3
import sys
from datetime import date
import status_store

ROOT = Path(os.environ.get('GARAGE_FRONTEND', Path(__file__).resolve().parent.parent / 'frontend')).resolve()
UPSTREAM = os.environ.get('GARAGE_UPSTREAM', 'http://127.0.0.1:8080').rstrip('/')
if urlsplit(UPSTREAM).scheme not in ('http', 'https') or not urlsplit(UPSTREAM).hostname:
    raise SystemExit('GARAGE_UPSTREAM must be an absolute HTTP(S) origin')
# Avoid accidental proxying of internal service traffic through environment HTTP_PROXY.
OPENER = build_opener(ProxyHandler({}))
MAX_RESPONSE = 8 * 1024 * 1024
STATUS_DB = os.environ.get('GARAGE_STATUS_DB', '')
PROVIDER_ID = os.environ.get('GARAGE_PROVIDER_ID', 'lubelogger-primary')
PUBLIC_ORIGIN = os.environ.get('GARAGE_PUBLIC_ORIGIN', '')


def valid_type(value):
    return (isinstance(value, str) and bool(value.strip()) and len(value.strip()) <= 80
            and not any(ord(char) < 32 or ord(char) == 127 for char in value.strip()))


def normalise_name(value):
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


def load_vehicle_type_overrides(path):
    """Optional private config, keyed by exact make + model, not inferred classes."""
    if not path:
        return {}
    raw = Path(path).read_bytes()
    if len(raw) > 131072:
        raise ValueError('vehicle type config too large')
    data = json.loads(raw)
    if not isinstance(data, dict) or set(data) != {'vehicleTypes'} or not isinstance(data['vehicleTypes'], list):
        raise ValueError('vehicle type config must contain a vehicleTypes list')
    result = {}
    for item in data['vehicleTypes']:
        if not isinstance(item, dict) or set(item) != {'make', 'model', 'type'}:
            raise ValueError('invalid vehicle type mapping')
        if not all(valid_type(item[key]) for key in ('make', 'model', 'type')):
            raise ValueError('invalid vehicle type mapping value')
        key = (normalise_name(item['make']), normalise_name(item['model']))
        if key in result and result[key] != item['type'].strip():
            raise ValueError('conflicting vehicle type mappings')
        result[key] = item['type'].strip()
    return result


TYPE_OVERRIDES = load_vehicle_type_overrides(os.environ.get('GARAGE_VEHICLE_TYPES'))


def fetch(path, params=None):
    url = UPSTREAM + path + ('?' + urlencode(params) if params else '')
    request = Request(url, headers={'Accept': 'application/json', 'culture-invariant': 'true'})
    with OPENER.open(request, timeout=8) as response:
        raw = response.read(MAX_RESPONSE + 1)
    if len(raw) > MAX_RESPONSE:
        raise ValueError('upstream response too large')
    data = json.loads(raw)
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError('upstream response must be a list of objects')
    return data


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return value if math.isfinite(value) else None
        text = str(value).strip()
        if ',' in text and '.' not in text:
            text = text.replace(',', '.')
        if not re.fullmatch(r'-?\d+(?:\.\d+)?', text):
            return None
        return float(text) if '.' in text else int(text)
    except (ValueError, OverflowError):
        return None


def vehicle(row):
    make, model = row.get('make'), row.get('model')
    name = ' '.join(str(x).strip() for x in (make, model) if x and str(x).strip()) or None
    return {'id': number(row.get('id')), 'name': name, 'make': make, 'model': model,
            'year': number(row.get('year')), 'licensePlate': row.get('licensePlate'),
            'vehicleType': vehicle_type(row.get('extraFields'), make, model),
            # No authoritative current value or verified unit; do not pretend zero is known.
            'odometer': None}


def vehicle_type(fields, make=None, model=None):
    """Use the operator's explicit vehicle extra field; never infer from make/model."""
    values = set()
    invalid_explicit = False
    for field in fields if isinstance(fields, list) else []:
        if not isinstance(field, dict):
            continue
        name, value = field.get('name'), field.get('value')
        if not isinstance(name, str) or name.strip().casefold() != 'fahrzeugtyp':
            continue
        if value is None or value == '':
            continue
        if not valid_type(value):
            if not isinstance(value, str) or value.strip():
                invalid_explicit = True
            continue
        values.add(value.strip())
    if invalid_explicit or len(values) > 1:
        return None
    if values:
        return next(iter(values))
    key = (normalise_name(make), normalise_name(model))
    return TYPE_OVERRIDES.get(key) if all(key) else None


def reminder(row):
    metric = row.get('metric')
    urgency = {'PastDue': 'Überfällig', 'VeryUrgent': 'Sehr dringend',
               'Urgent': 'Dringend', 'NotUrgent': 'Nicht dringend'}.get(row.get('urgency'))
    return {'description': row.get('description'),
            'dueDate': row.get('dueDate') if metric in ('Date', 'Both') else None,
            'dueOdometer': number(row.get('dueOdometer')) if metric in ('Odometer', 'Both') else None,
            'status': urgency}


def service(row):
    return {'date': row.get('date'), 'description': row.get('description'),
            'odometer': number(row.get('odometer')), 'cost': number(row.get('cost'))}


def sort_date(row):
    """Known unambiguous ISO or German dates only; no inferred month/day ordering."""
    value = str(row.get('date') or '')
    iso = re.match(r'^(\d{4})-(\d{2})-(\d{2})(?:$|T)', value)
    de = re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})', value)
    try:
        if iso:
            return date(*map(int, iso.groups())).toordinal()
        if de:
            day, month, year = map(int, de.groups())
            return date(year, month, day).toordinal()
    except ValueError:
        pass
    return 0


class Handler(BaseHTTPRequestHandler):
    server_version = 'WolfsGarage/0.1'

    def log_message(self, fmt, *args):
        # Do not log user-supplied query strings or any upstream response contents.
        return

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            return self.asset('index.html')
        if path.startswith('/garage-assets/'):
            return self.asset(path[len('/garage-assets/'):])
        if path == '/garage-api/vehicles':
            try:
                rows = fetch('/api/vehicles')
                statuses = status_store.read_many(STATUS_DB, rows, PROVIDER_ID)
                vehicles = [dict(vehicle(v), status=statuses[int(v['id'])]) for v in rows]
                return self.respond(200, {'vehicles': vehicles})
            except status_store.IdentityMismatch:
                return self.respond(409, {'error': 'Fahrzeugzuordnung muss geprüft werden.'})
            except (sqlite3.Error, json.JSONDecodeError) as exc:
                if isinstance(exc, json.JSONDecodeError):
                    return self.respond(502, {'error': 'Fahrzeuge konnten nicht geladen werden.'})
                return self.respond(503, {'error': 'Fahrzeugstatus ist vorübergehend nicht verfügbar.'})
            except (OSError, ValueError, TypeError, HTTPError, URLError, json.JSONDecodeError):
                return self.respond(502, {'error': 'Fahrzeuge konnten nicht geladen werden.'})
        match = re.fullmatch(r'/garage-api/vehicles/([1-9][0-9]{0,8})/summary', path)
        if match:
            try:
                identifier = int(match.group(1))
                records = fetch('/api/vehicles')
                raw = next((v for v in records if number(v.get('id')) == identifier), None)
                if raw is None:
                    return self.respond(404, {'error': 'Fahrzeug nicht gefunden.'})
                status = status_store.read_many(STATUS_DB, [raw], PROVIDER_ID)[identifier]
                selected = dict(vehicle(raw), status=status)
                args = {'vehicleId': identifier}
                reminders = fetch('/api/vehicle/reminders', args)
                services = fetch('/api/vehicle/servicerecords', args)
                services.sort(key=sort_date, reverse=True)
                return self.respond(200, {'vehicle': selected, 'status': status, 'reminders': [reminder(x) for x in reminders],
                                          'services': [service(x) for x in services]})
            except status_store.IdentityMismatch:
                return self.respond(409, {'error': 'Fahrzeugzuordnung muss geprüft werden.'})
            except sqlite3.Error:
                return self.respond(503, {'error': 'Fahrzeugstatus ist vorübergehend nicht verfügbar.'})
            except (OSError, ValueError, TypeError, HTTPError, URLError, json.JSONDecodeError):
                return self.respond(502, {'error': 'Fahrzeugübersicht konnte nicht geladen werden.'})
        return self.respond(404, {'error': 'Nicht gefunden.'})

    def do_PUT(self):
        path = urlsplit(self.path).path
        match = re.fullmatch(r'/garage-api/vehicles/([1-9][0-9]{0,8})/status', path)
        if not match:
            return self.respond(404, {'error': 'Nicht gefunden.'})
        origin = urlsplit(PUBLIC_ORIGIN)
        valid_config = (origin.scheme == 'https' and origin.hostname and origin.netloc and not origin.username
                        and not origin.password and not origin.path and not origin.query and not origin.fragment)
        if not valid_config:
            return self.respond(503, {'error': 'Statusbearbeitung ist nicht konfiguriert.'})
        if (self.headers.get('Origin') != PUBLIC_ORIGIN or self.headers.get('Host', '').lower() != origin.netloc.lower()
                or self.headers.get('X-Garage-Request') != '1'
                or self.headers.get('Sec-Fetch-Site', 'same-origin') != 'same-origin'
                or self.headers.get('Content-Type', '').split(';', 1)[0].strip().lower() != 'application/json'
                or self.headers.get('Transfer-Encoding')):
            return self.respond(403, {'error': 'Anfrage nicht erlaubt.'})
        try:
            length = int(self.headers.get('Content-Length', ''))
            if length < 1 or length > 16384:
                return self.respond(400, {'error': 'Ungültige Anfrage.'})
            payload = json.loads(self.rfile.read(length))
            status_store.validate(payload)
            identifier = int(match.group(1))
            rows = fetch('/api/vehicles')
            raw = next((v for v in rows if number(v.get('id')) == identifier), None)
            if raw is None:
                return self.respond(404, {'error': 'Fahrzeug nicht gefunden.'})
            result = status_store.update(STATUS_DB, raw, PROVIDER_ID, payload)
            return self.respond(200, result)
        except (status_store.Conflict, status_store.IdentityMismatch):
            return self.respond(409, {'error': 'Der Status oder das Fahrzeug hat sich geändert. Bitte neu laden.'})
        except (status_store.InvalidStatus, json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError):
            return self.respond(400, {'error': 'Ungültige Anfrage.'})
        except sqlite3.Error:
            return self.respond(503, {'error': 'Fahrzeugstatus konnte nicht gespeichert werden.'})
        except (OSError, HTTPError, URLError):
            return self.respond(502, {'error': 'Fahrzeug konnte nicht geprüft werden.'})

    do_HEAD = do_GET

    def asset(self, name):
        target = (ROOT / name).resolve()
        if not target.is_relative_to(ROOT) or not target.is_file():
            return self.respond(404, {'error': 'Nicht gefunden.'})
        try:
            raw = target.read_bytes()
        except OSError:
            return self.respond(404, {'error': 'Nicht gefunden.'})
        kind = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
        return self.respond(200, raw, kind + ('; charset=utf-8' if kind.startswith('text/') or kind == 'application/javascript' else ''))


def main():
    if sys.argv[1:] == ['--init-status-store']:
        status_store.initialize(STATUS_DB)
        return
    if sys.argv[1:]:
        raise SystemExit('unknown option')
    bind = os.environ.get('GARAGE_BIND', '127.0.0.1')
    port = int(os.environ.get('GARAGE_PORT', '8000'))
    ThreadingHTTPServer((bind, port), Handler).serve_forever()


if __name__ == '__main__':
    main()
