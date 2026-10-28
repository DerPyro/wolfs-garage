#!/usr/bin/env python3
"""Offline arithmetic review of documented examples; no Garage/domain implementation.

Reads Markdown and checks its literal results against Python's calendar, datetime,
zoneinfo, Fraction and Decimal arithmetic. No services, filesystem writes or API calls.
Policy/state/transaction examples remain explicitly unexecuted.
"""
from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import re
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / 'docs/planning/due-date-spec.md'
BERLIN = ZoneInfo('Europe/Berlin')
CHECKS = []


def parse_rows(text):
    rows = {}
    for line in text.splitlines():
        match = re.fullmatch(r'\| (DV-\d{2}) \| (.*?) \| (.*?) \|', line)
        if match:
            if match[1] in rows:
                raise ValueError(f'Duplicate vector row: {match[1]}')
            rows[match[1]] = (match[2], match[3])
    if set(rows) != {f'DV-{n:02}' for n in range(1, 28)}:
        raise ValueError('Expected the documented 27 uniquely numbered vector rows')
    return rows


def match(pattern, text):
    found = re.search(pattern, text)
    if not found:
        raise ValueError(f'Document fixture no longer matches extraction pattern: {pattern}')
    return found


def iso_dates(text):
    return [date.fromisoformat(value) for value in re.findall(r'(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)', text)]


def shifted_month(anchor, count):
    # Only an arithmetic worksheet: standard-library month length, no recurrence state.
    year, month0 = divmod(anchor.year * 12 + anchor.month - 1 + count, 12)
    return date(year, month0 + 1, min(anchor.day, monthrange(year, month0 + 1)[1]))


def check(vector, aspect, actual, expected):
    passed = actual == expected
    CHECKS.append((vector, aspect, passed, actual, expected))
    print(f'{"PASS" if passed else "FAIL"} {vector} {aspect}: {actual!s} (documented {expected!s})')


def run():
    raw = SPEC.read_bytes()
    rows = parse_rows(raw.decode())
    print(f'Specification SHA256: {hashlib.sha256(raw).hexdigest()}')
    print('Scope: arithmetic only; no application, policy, persistence or provider checks.')

    inp, out = rows['DV-01']
    instant = datetime.fromisoformat(match(r'Clock `([^`]+)`', inp)[1].replace('Z', '+00:00'))
    local_day = instant.astimezone(BERLIN).date()
    expected_day = date.fromisoformat(match(r'today=(\d{4}-\d{2}-\d{2})', out)[1])
    check('DV-01', 'UTC instant -> Berlin date', local_day, expected_day)
    check('DV-01', 'local calendar-day difference', (iso_dates(inp)[-1] - local_day).days,
          int(match(r'remainingDays=(-?\d+)', out)[1]))

    inp, out = rows['DV-02']
    today, *due_dates = iso_dates(inp)
    expected = [int(n) for n in match(r'remainingDays=([−\-\d/]+)', out)[1].replace('−', '-').split('/')]
    check('DV-02', 'calendar-day differences', [(d - today).days for d in due_dates], expected)

    inp, out = rows['DV-03']
    threshold = int(match(r'/(\d+) km', inp)[1])
    readings = [int(n) for n in match(r'Stand ([\d/]+)', inp)[1].split('/')]
    # Numeric relations only; no Both/status state machine is implemented here.
    check('DV-03', 'three kilometer positions below/equal/above threshold',
          [reading - threshold for reading in readings], [-1, 0, 1])
    # DV-03 does not explicitly state today's date; do not invent a clock
    # merely to assert that its date dimension is in the future.

    inp, out = rows['DV-06']
    anchor = iso_dates(inp)[0]
    indices = [int(n) for n in match(r'n=([\d/]+)', inp)[1].split('/')]
    interval = int(match(r'fixed, (\d+) Monat', inp)[1])
    check('DV-06', 'each fixed month uses original anchor',
          [shifted_month(anchor, interval * n) for n in indices], iso_dates(out))

    inp, out = rows['DV-07']
    check('DV-07', 'leap-day month clamp',
          shifted_month(iso_dates(inp)[0], int(match(r'Intervall (\d+) Monate', inp)[1])), iso_dates(out)[0])

    inp, out = rows['DV-08']
    starts = iso_dates(inp)
    days = int(match(r'Intervall (\d+) Tage', inp)[1])
    ends = [d + timedelta(days=days) for d in starts]
    check('DV-08', 'two local date additions', ends, iso_dates(out))
    # Convert both endpoints to UTC before subtraction: Python subtracts matching
    # ZoneInfo wall times without applying a changed UTC offset otherwise.
    elapsed = []
    for start, end in zip(starts, ends):
        start_utc = datetime.combine(start, time(), BERLIN).astimezone(timezone.utc)
        end_utc = datetime.combine(end, time(), BERLIN).astimezone(timezone.utc)
        elapsed.append(Fraction(int((end_utc - start_utc).total_seconds()), 3600))
    documented_hours = [int(n) for n in match(r'(\d+/\d+) Stunden', out)[1].split('/')]
    check('DV-08', 'elapsed UTC hours across Berlin DST', elapsed, documented_hours)

    inp, out = rows['DV-09']
    months, km_interval = [int(n) for n in match(r'synthetisch (\d+) Monate/(\d+) km', inp).groups()]
    base_km = int(match(r', (\d+) km', inp)[1])
    check('DV-09', 'completion-date month arithmetic', shifted_month(iso_dates(inp)[0], months), iso_dates(out)[0])
    check('DV-09', 'completion-distance addition', base_km + km_interval, int(match(r'`/(\d+) km', out)[1]))

    inp, out = rows['DV-10']
    anchor = iso_dates(inp)[0]
    next_index = int(match(r'n=(\d+)', out)[1])
    due = shifted_month(anchor, next_index)
    check('DV-10', 'next fixed index calendar date', due, iso_dates(out)[0])
    performed = datetime.strptime(match(r'am (\d{2}\.\d{2})\.', inp)[1] + f'.{anchor.year}', '%d.%m.%Y').date()
    check('DV-10', 'next occurrence is before stated completion day', due < performed, True)

    inp, out = rows['DV-13']
    first, last = [int(n) for n in match(r'=([0-9]+), 20\.10\.=([0-9]+)', inp).groups()]
    candidates = [int(n) for n in match(r'10\.10\.=([0-9]+) bzw\. ([0-9]+)', inp).groups()]
    check('DV-13', 'inserted reading lies between neighboring values',
          [first <= candidate <= last for candidate in candidates], [True, False])

    inp, out = rows['DV-16']
    year, month = [int(n) for n in match(r'Monat `(\d{4})-(\d{2})`', inp).groups()]
    month_end = date(year, month, monthrange(year, month)[1])
    expected = iso_dates(out)
    check('DV-16', 'month precision -> proposed comparison day', month_end, expected[0])
    check('DV-16', 'exclusive calendar end date', month_end + timedelta(days=1), expected[-1])

    inp, out = rows['DV-18']
    check('DV-18', '30 calendar days before due date',
          iso_dates(inp)[0] - timedelta(days=int(match(r'Offset(\d+)', inp)[1])), iso_dates(out)[0])

    inp, out = rows['DV-21']
    parts = match(r'heute (\d{2}\.\d{2}\.\d{4}); (\d{2}\.\d{2}\.)=(\d+), (\d{2}\.\d{2}\.)=(\d+); Ziel(\d+)', inp)
    today = datetime.strptime(parts[1], '%d.%m.%Y').date()
    first_on = datetime.strptime(parts[2] + str(today.year), '%d.%m.%Y').date()
    last_on = datetime.strptime(parts[4] + str(today.year), '%d.%m.%Y').date()
    first_km, last_km, target = map(int, (parts[3], parts[5], parts[6]))
    rate = Fraction(last_km - first_km, (last_on - first_on).days)
    remaining = target - last_km
    duration = math.ceil(Fraction(remaining, 1) / rate)
    forecast_date = last_on + timedelta(days=duration)
    check('DV-21', 'exact measured rate', rate, int(match(r'Rate(\d+) km/Tag', out)[1]))
    check('DV-21', 'remaining distance', remaining, int(match(r'Rest(\d+)→', out)[1]))
    check('DV-21', 'ceiling travel days', duration, int(match(r'→(\d+) Tage', out)[1]))
    check('DV-21', 'forecast calendar date', forecast_date, iso_dates(out)[0])

    inp, out = rows['DV-22']
    later = datetime.strptime(match(r'heute (\d{2}\.\d{2}\.\d{4})', inp)[1], '%d.%m.%Y').date()
    # Same measured endpoints remain the anchor; this is a worksheet, not proof
    # that any application actually ignores its query date.
    check('DV-22', 'same endpoint-based date on later query', forecast_date, iso_dates(out)[0])
    check('DV-22', 'last measurement age', (later - last_on).days, int(match(r'Alter(\d+) Tage', out)[1]))

    inp, out = rows['DV-24']
    rate = Fraction(int(match(r'rate(\d+) km/Tag', inp)[1]), 1)
    last_km, target = int(match(r'Stand(\d+)', inp)[1]), int(match(r'Ziel(\d+)', inp)[1])
    travel_days = math.ceil(Fraction(target - last_km, 1) / rate)
    last_on = datetime.strptime(match(r'am (\d{2}\.\d{2}\.\d{4})', inp)[1], '%d.%m.%Y').date()
    check('DV-24', 'fractional days round upward', travel_days, int(match(r'ceil\(10/3\)=(\d+)', out)[1]))
    check('DV-24', 'non-integral-rate forecast date', last_on + timedelta(days=travel_days), iso_dates(out)[0])

    inp, out = rows['DV-25']
    bought, paid, used, portion, stated_total = [Decimal(n) for n in match(
        r'Einkauf(\d+) Stück/(\d+) EUR; Verwendung(\d+) Stück/(\d+) EUR in bestätigtem Gesamtvorgang(\d+) EUR', inp).groups()]
    expected_qty, expected_remaining = [Decimal(n) for n in match(r'Restlager(\d+)/(\d+)', out).groups()]
    check('DV-25', 'remaining inventory quantity', bought - used, expected_qty)
    check('DV-25', 'used-part allocation', paid / bought * used, portion)
    check('DV-25', 'remaining inventory amount', paid - portion, expected_remaining)
    check('DV-25', 'explicitly supplied total (not an automatic addition)', stated_total,
          Decimal(match(r'Vorgangskosten(\d+) einmal', out)[1]))

    inp, out = rows['DV-26']
    performed_on, paid_on, recorded_on = [datetime.strptime(s, '%d.%m.%Y').date()
        for s in re.findall(r'\d{2}\.\d{2}\.\d{4}', inp)]
    check('DV-26', 'calendar year of performance', performed_on.year, int(match(r'Vorgangskosten(\d{4})', out)[1]))
    check('DV-26', 'calendar year of payment', paid_on.year, int(match(r'Cashzahlung(\d{4})', out)[1]))
    check('DV-26', 'recording belongs to later calendar year', recorded_on.year, paid_on.year)

    # Supplemental arithmetic examples for DS-07's specified decimal/rounding
    # operator, not new financial-policy tests or acceptance of a payments ledger.
    check('DS-07 arithmetic supplement', 'exact decimal addition',
          Decimal('0.10') + Decimal('0.20'), Decimal('0.30'))
    check('DS-07 arithmetic supplement', 'final HALF_UP on fractional allocation',
          (Decimal('20') / Decimal('3')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), Decimal('6.67'))
    check('DS-07 arithmetic supplement', 'HALF_UP tie after intermediate arithmetic',
          (Decimal('2.01') / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), Decimal('1.01'))

    covered = sorted({c[0] for c in CHECKS if c[0].startswith('DV-')})
    skipped = sorted(set(rows) - set(covered))
    failures = [c for c in CHECKS if not c[2]]
    print(f'Arithmetic comparisons: {len(CHECKS)}; failures: {len(failures)}')
    print(f'Partially/arithmetically covered vector IDs ({len(covered)}): {", ".join(covered)}')
    print(f'No executable check of remaining policy/state IDs ({len(skipped)}): {", ".join(skipped)}')
    print('No proof of due-state transitions, approvals, source validity, deduplication, transactions, bot, scheduler, provider behavior or legal intervals.')
    return bool(failures)


if __name__ == '__main__':
    try:
        sys.exit(1 if run() else 0)
    except (ValueError, KeyError, IndexError, ZeroDivisionError) as exc:
        print(f'FAIL specification extraction/arithmetic: {exc}', file=sys.stderr)
        sys.exit(1)
