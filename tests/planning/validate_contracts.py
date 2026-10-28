#!/usr/bin/env python3
"""Offline consistency checks for proposed design artifacts; no services or writes."""
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import unquote

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/planning/contracts'
SCHEMA = json.loads((BASE / 'command.schema.json').read_text())
API = yaml.safe_load((BASE / 'garage.openapi.yaml').read_text())
Draft202012Validator.check_schema(SCHEMA)
checks = 0


def validator(name):
    root = dict(SCHEMA)
    root['$ref'] = '#/$defs/' + name
    return Draft202012Validator(root, format_checker=FormatChecker())


def verify(instance, name, valid=True):
    global checks
    errors = list(validator(name).iter_errors(instance))
    assert bool(errors) != valid, ('unexpected validation result', name, valid,
                                  [e.message for e in errors])
    checks += 1


examples = {
    'draft-odometer.json': 'DraftRequest',
    'draft-maintenance.json': 'DraftRequest',
    'draft-problem.json': 'DraftRequest',
    'draft-hu-month.json': 'DraftRequest',
    'confirm.json': 'ConfirmRequest',
    'command-uncertain.json': 'CommandStatus',
    'tasks.json': 'TaskPage',
    'tasks-forecast.json': 'TaskPage',
}
for filename, name in examples.items():
    verify(json.loads((BASE / 'examples' / filename).read_text()), name)

reading = json.loads((BASE / 'examples/draft-odometer.json').read_text())
maintenance = json.loads((BASE / 'examples/draft-maintenance.json').read_text())
confirm = json.loads((BASE / 'examples/confirm.json').read_text())
hu = json.loads((BASE / 'examples/draft-hu-month.json').read_text())

for field, value in [('actorId', 'attacker'), ('chatId', '123'), ('confirmedAt', '2026-10-26T10:00:00Z')]:
    item = deepcopy(reading)
    item[field] = value
    verify(item, 'DraftRequest', False)
for field, value in [('kilometers', -1), ('kilometers', 12.5), ('recordedOn', '2026-02-30'),
                     ('recordedOn', '26.10.2026'), ('notes', ''), ('unit', 'miles')]:
    item = deepcopy(reading)
    item['payload'][field] = value
    verify(item, 'DraftRequest', False)
for field, value in [('amountMinor', 123.45), ('amountMinor', -1), ('currency', 'USD')]:
    item = deepcopy(maintenance)
    item['payload']['totalCost'][field] = value
    verify(item, 'DraftRequest', False)
for field, value in [('expectedCommandRevision', -1), ('payloadHash', 'invalid'),
                     ('confirmationNonce', 'short'), ('actorId', 'attacker')]:
    item = deepcopy(confirm)
    item[field] = value
    verify(item, 'ConfirmRequest', False)
for payload in [dict(hu['payload'], confirmedNextDueOn='2028-10-31'),
                dict(hu['payload'], confirmedNextDueMonth='2028-13'),
                {k:v for k,v in hu['payload'].items() if k!='duePrecision'}]:
    item = deepcopy(hu)
    item['payload'] = payload
    verify(item, 'DraftRequest', False)
item = deepcopy(hu)
item['payload'].pop('confirmedNextDueMonth')
item['payload'].update(duePrecision='day', confirmedNextDueOn='2028-10-31')
verify(item, 'DraftRequest')
item = deepcopy(reading)
item['operation'] = 'inventedProviderRoute'
verify(item, 'DraftRequest', False)
item = deepcopy(reading)
item['operation'] = 'appendProblemEvent'
item['payload'] = {'problemId': reading['vehicleId'], 'eventType':'status_changed',
                   'occurredOn':'2026-10-26','description':'synthetic event'}
verify(item, 'DraftRequest', False)
item['payload']['status'] = 'observing'
verify(item, 'DraftRequest')

forecast_page = json.loads((BASE / 'examples/tasks-forecast.json').read_text())
item = deepcopy(forecast_page)
item['items'][0]['basis'] = 'estimate'
verify(item, 'TaskPage', False)
item = deepcopy(forecast_page)
del item['items'][0]['forecast']['measurementRefs']
verify(item, 'TaskPage', False)
item = deepcopy(forecast_page)
item['items'][0]['forecast']['rateElapsedDays'] = 0
verify(item, 'TaskPage', False)

# Resolve every JSON reference locally. No remote schema retrieval.
refs = 0


def walk(value, owner):
    global refs
    if isinstance(value, dict):
        if '$ref' in value:
            ref = value['$ref']
            assert '://' not in ref, 'Remote references deliberately unsupported'
            filename, _, pointer = ref.partition('#')
            path = (owner.parent / filename).resolve() if filename else owner
            assert path.is_relative_to(BASE.resolve()) and path.exists(), ref
            document = yaml.safe_load(path.read_text())
            if pointer:
                assert pointer.startswith('/'), ref
                for part in pointer[1:].split('/'):
                    document = document[unquote(part).replace('~1', '/').replace('~0', '~')]
            assert isinstance(document, dict), ref
            refs += 1
        for child in value.values():
            walk(child, owner)
    elif isinstance(value, list):
        for child in value:
            walk(child, owner)


walk(API, BASE / 'garage.openapi.yaml')
walk(SCHEMA, BASE / 'command.schema.json')
assert API['openapi'] == '3.1.1'
assert API['security'] == [{'garageSession': []}]
operation_ids = set()
for path, methods in API['paths'].items():
    for method, operation in methods.items():
        assert method in ('get', 'post'), (path, method)
        oid = operation['operationId']
        assert oid not in operation_ids
        operation_ids.add(oid)
        params = operation.get('parameters', [])
        pathnames = {p['name'] for p in params if p['in'] == 'path' and p.get('required')}
        assert pathnames == set(re.findall(r'\{([^}]+)\}', path)), path
        if method == 'post':
            headers = {p['name'] for p in params if p['in'] == 'header' and p.get('required')}
            assert {'X-CSRF-Token', 'Idempotency-Key'} <= headers, path
        assert '401' in operation['responses'] and '404' in operation['responses'], path

print('JSON Schema Draft 2020-12: structural check passed')
print(f'Examples and targeted valid/invalid payloads: {checks} passed')
print(f'Local references: {refs} resolved; unique OpenAPI operations: {len(operation_ids)}')
print('Design consistency only; no complete OpenAPI conformance, runtime or authorization test.')
