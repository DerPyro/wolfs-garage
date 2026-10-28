"""Confirm LubeLogger's vehicle-list extra-field round trip using synthetic data."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/wp01'))
sys.path.insert(0, str(ROOT / 'garage_gateway'))
from helpers import Client
import server

network = os.environ.get('GARAGE_TEST_NETWORK')
if not network:
    raise SystemExit('Set GARAGE_TEST_NETWORK to an empty internal sandbox network')
network_info = json.loads(subprocess.check_output(['docker', 'network', 'inspect', network], text=True))[0]
if not network_info.get('Internal') or network_info.get('Containers'):
    raise SystemExit('Test network must be internal and empty')
name = 'wolfs-type-check-' + secrets.token_hex(4)
image = 'ghcr.io/hargata/lubelogger@sha256:483a9d7582c4e6258615fd822b3de4193b4fcc4230d0a92432c6d407faf75af2'
started = False
try:
    subprocess.run(['docker', 'run', '-d', '--name', name, '--network', network,
                    '-e', 'TZ=Europe/Berlin', '-e', 'LUBELOGGER_LOCALE_OVERRIDE=de-DE', image],
                   check=True, stdout=subprocess.DEVNULL)
    started = True
    info = json.loads(subprocess.check_output(['docker', 'inspect', name], text=True))[0]
    assert not info['HostConfig'].get('PortBindings')
    address = next(iter(info['NetworkSettings']['Networks'].values()))['IPAddress']
    client = Client('http://' + address + ':8080')
    for _ in range(80):
        try:
            if client.call('/')[0] == 200:
                break
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(.25)
    else:
        raise RuntimeError('LubeLogger startup timeout')
    for model, kind in [('SyntheticSedan', 'Limousine'), ('SyntheticBike', 'Cross-Motorrad')]:
        client.ok('/api/vehicles/add', method='POST', data={
            'Year': 2020, 'Make': 'Synthetic', 'Model': model, 'LicensePlate': 'SYNTH-' + model,
            'ExtraFields': [{'Name': 'Fahrzeugtyp', 'Value': kind}],
        })
    status, rows, _ = client.call('/api/vehicles')
    assert status == 200 and isinstance(rows, list)
    models = {row['model']: row for row in rows}
    for model, kind in [('SyntheticSedan', 'Limousine'), ('SyntheticBike', 'Cross-Motorrad')]:
        fields = models[model].get('extraFields')
        assert isinstance(fields, list)
        assert any(field.get('name') == 'Fahrzeugtyp' and field.get('value') == kind for field in fields)
        assert server.vehicle(models[model])['vehicleType'] == kind
        print(model + ': GET /api/vehicles extraFields and adapter projection PASS')
    print('Synthetic test container:', name)
    print('Scope: version-pinned empty instance, two synthetic vehicles; no production data')
finally:
    if started:
        subprocess.run(['docker', 'stop', '-t', '3', name], check=False, stdout=subprocess.DEVNULL)
        print('Test container stopped; synthetic resources retained')
