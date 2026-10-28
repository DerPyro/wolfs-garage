# Scheduled open work contract

This feature adds optional scheduling and user-assigned classification to existing vehicle issue entries. It is not a recurring maintenance-rule engine or a technical diagnosis system. The original requirement for a complete technical logbook remains broader and is not fulfilled by this subset.

## Issue fields and updates

The status representation is `{readiness, issues, revision}`. Every issue reads as `{id, text, dueDate, severity, lifecycle}`:

- `dueDate`: nullable ISO calendar date (`YYYY-MM-DD`).
- `severity`: nullable `observation`, `repair`, or `critical`. `null` means not classified; the app does not infer a severity.
- `lifecycle`: `open` or `observed`. Both remain active and appear in the work projection. A completed issue is removed by the existing atomic record-completion workflow.

Old stored `{id,text}` entries are normalized at read time to null `dueDate`, null `severity`, and lifecycle `open`. A schema upgrade preserves the original JSON bytes; it does not manufacture an audit event or rewrite old rows.

When a status update includes an existing issue ID, omitting `dueDate`, `severity`, or `lifecycle` preserves that field. Explicit `null` clears `dueDate` or `severity`; `lifecycle` is not nullable. New IDs are assigned by the server. IDs from other vehicles, duplicate IDs, malformed dates, unknown fields, invalid severities/lifecycles, and stale status revisions are rejected without partial writes or audit events. The existing readiness value stays independent from issue fields and closure.

Record completion may close one selected issue atomically. Other issues retain all scheduling metadata and lifecycle values, and readiness is unchanged. A repeated completion command returns the original response without duplicating record, status revision, or audit writes.

## Read-only active work projection

`GET /garage-api/work` has no query parameters and returns:

```json
{
  "today": "2026-10-28",
  "timeZone": "Europe/Berlin",
  "items": [
    {
      "vehicleId": 1,
      "id": "0123456789abcdef0123456789abcdef",
      "text": "Synthetic work item",
      "dueDate": "2026-10-28",
      "severity": "critical",
      "lifecycle": "open",
      "dueState": "today"
    }
  ]
}
```

Items include every `open` and `observed` issue across all vehicles. The endpoint reads all statuses and obtains the clock date once in a single SQLite read transaction. `GARAGE_TODAY_PROVIDER` can inject a fixed `datetime.date` in API tests. The default provider uses `datetime.now(ZoneInfo("Europe/Berlin")).date()`; it does not compare UTC dates directly.

`dueState` is derived: a null due date is `unscheduled`, a date before today is `overdue`, an equal date is `today`, and a later date is `upcoming`. Sort order is critical first, then overdue/today/upcoming/unscheduled, due date ascending, vehicle ID ascending, and issue ID ascending. Only `critical` receives severity priority; no extra ordering is implied between repair, observation, and unclassified items.

The projection is read-only. It adds no audit events and does not update readiness or issue status. It is advertised through `scheduledWork`; any query string, including an empty or duplicate parameter, returns `400`.

## Historical schema-3 baseline (2026-10-28)

This section records the feature's tested schema-3 state at that date. The current application uses schema 4; see the [current standalone upgrade guide](../standalone.md) and [inspection status contract](inspection-status.md) for present behavior. The results below remain evidence for the earlier schema-3 release and are not rewritten as schema-4 checks.

Fresh databases initialize at schema 3. Schema 1 and 2 require an explicit upgrade, with a new unused destination for a checked SQLite backup. The upgrade runs transactionally. Schema 1 receives the `records.revision` column it lacked; schema 2 needs only the schema version update. Stored issue JSON remains unchanged. A schema-3 upgrade request is a no-op and writes no backup. Backup accepts schema 1, 2 and 3 without migrating the source. Schema-2 binaries reject schema 3 and must never be started against a schema-3 database; downgrade requires a separate pre-upgrade copy.

The public API acceptance tests cover field normalization, omission and null semantics, validation, stale revisions, ownership, duplicates, readiness independence, record closure and retries, read-only projection, deterministic ordering, request query rejection, Berlin day boundaries, and schema 1/2/3 migration safety. All 66 tests matching `test_own_*.py` pass. An isolated CLI rehearsal upgraded a copy of a synthetic schema-2 database, checked the resulting schema-3 file, verified repeated upgrade was a no-op, and compared the six tables across source, pre-upgrade backup, and upgraded copy; the original source was untouched.

The real-Chromium acceptance script passed on a fresh schema-3 database with synthetic data. It verified issue fields and priority, overdue/today/critical/observed filters, clearing a due date and reloading, atomic completion, preservation of other issue metadata and INOP, and responsive layouts at 320, 390, 768 and 1280 pixels with no horizontal overflow. The existing record-correction Chromium acceptance script also passed against schema 3. The [synthetic mobile dashboard screenshot](../discovery/evidence/scheduled-work-mobile.png) is retained as visual evidence. No live vehicle data, production database or external service was used.

The Docker image was also built and exercised against a new synthetic-only volume on an isolated container with no network, non-root UID 65532, read-only root filesystem, dropped capabilities and `no-new-privileges`. After explicit schema-3 initialization, Gunicorn health and the public API smoke check passed: a ready vehicle with a manually entered critical issue due today appeared with `dueState: today`, and readiness remained `ready`. The test container was stopped; its test volume was retained. Nothing was pushed to a registry or deployed.

To reproduce with a separate loopback-only Docker volume, initialize and start a fresh test project at port 18985 from the repository root:

```sh
GARAGE_PORT=18985 GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18985 \
  docker compose --project-name wg-scheduled-work-browser --env-file .env.example \
  -f deploy/compose.standalone.yaml run --rm --no-deps garage \
  python -m wolfs_garage init-db

GARAGE_PORT=18985 GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18985 \
  docker compose --project-name wg-scheduled-work-browser --env-file .env.example \
  -f deploy/compose.standalone.yaml up -d
```

In the browser-test environment with Node.js, Chromium under `/ms-playwright`, and writable `/out`, run `node tests/scheduled_work_browser.cjs`. The script creates its own vehicle and work through the UI. The API suite command is `.venv/bin/python -m unittest discover -s tests -p 'test_own_*.py'`. Use only the isolated test project; these checks do not touch the existing standalone or legacy installation. See the API contract and [standalone operator guide](../standalone.md).
