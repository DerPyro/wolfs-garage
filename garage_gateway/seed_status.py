"""One-off private status bootstrap. Reads explicitly supplied data from stdin."""
import json
import sys

import server
import status_store


def resolve_entries(plan, vehicles):
    if not isinstance(plan, dict) or set(plan) != {'entries'} or not isinstance(plan['entries'], list) or not 1 <= len(plan['entries']) <= 20:
        raise ValueError('invalid plan')
    resolved = []
    for entry in plan['entries']:
        if not isinstance(entry, dict) or set(entry) != {'make', 'models', 'readiness', 'issues'}:
            raise ValueError('invalid entry')
        if not server.normalise_name(entry['make']) or not isinstance(entry['models'], list) or not entry['models']:
            raise ValueError('invalid vehicle match')
        models = {server.normalise_name(m) for m in entry['models'] if isinstance(m, str)}
        if not models or '' in models or len(models) != len(entry['models']):
            raise ValueError('invalid model list')
        matches = [row for row in vehicles if server.normalise_name(row.get('make')) == server.normalise_name(entry['make'])
                   and server.normalise_name(row.get('model')) in models]
        if len(matches) != 1:
            raise ValueError('vehicle match is missing or ambiguous')
        if not isinstance(entry['issues'], list):
            raise ValueError('invalid issues')
        payload = {'readiness': entry['readiness'], 'issues': [{'text': text} for text in entry['issues']], 'revision': 0}
        status_store.validate(payload)
        resolved.append((matches[0], payload))
    if len({row['id'] for row, _ in resolved}) != len(resolved):
        raise ValueError('duplicate vehicle')
    return resolved


def main():
    try:
        raw = sys.stdin.buffer.read(32769)
        if len(raw) > 32768:
            raise ValueError('plan too large')
        entries = resolve_entries(json.loads(raw), server.fetch('/api/vehicles'))
        status_store.update_batch(server.STATUS_DB, server.PROVIDER_ID, entries)
    except Exception:
        raise SystemExit('Status bootstrap failed; no partial batch was committed. Check matches and existing status before retrying.')
    print(f'Initial status saved for {len(entries)} uniquely matched vehicles.')


if __name__ == '__main__':
    main()
