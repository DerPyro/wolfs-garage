# Owner data export

Wolfs Garage provides a portable JSON owner-data export for inspection and migration to another application. It is a one-way data file, **not** a database backup, restore image, or supported import format.

## Contents and limits

Current format version 2 uses this root shape:

```json
{
  "format": "wolfs-garage-owner-export",
  "formatVersion": 2,
  "applicationVersion": "0.1.0a6",
  "databaseSchema": 4,
  "exportedAt": "2026-10-28T12:00:00+00:00",
  "vehicles": [],
  "statuses": [],
  "odometerReadings": [],
  "records": [],
  "history": []
}
```

It includes stored vehicle metadata, including raw `inspectionDueMonth`; each vehicle's readiness, issues and revision; all odometer readings; completed records; and decoded before/after audit history. Arrays sort by their stable primary key ascending. Every reading and record includes its `vehicleId`. Stored text odometer values and costs remain decimal strings in the business-data arrays. Audit `before` and `after` values preserve the JSON types that were recorded, including numeric odometer values in older history entries.

The export deliberately excludes command-idempotency/replay rows, application secrets and configuration, computed dashboard projections, and external document bytes. `documentUrl` remains only a stored link. Nothing is fetched. There is no API or CLI operation that imports this JSON back into the application. A SQLite backup is the supported way to preserve and restore the complete application database, including command replay state.

The array objects have these field sets:

| Array | Fields |
| --- | --- |
| `vehicles` | `id`, `make`, `model`, `name`, `year`, `licensePlate`, `vehicleType`, `odometerUnit`, `revision`, `inspectionDueMonth` (stored metadata; no derived name, current reading, status, inspection, effective readiness, or summary projection) |
| `statuses` | `vehicleId`, `readiness`, `issues`, `revision`; each issue has canonical `id`, `text`, `dueDate`, `severity`, and `lifecycle` fields |
| `odometerReadings` | `id`, `vehicleId`, `date`, `odometer` (exact stored string), `unit`, `note` |
| `records` | `id`, `vehicleId`, `description`, `kind`, `date`, `odometer`, `odometerUnit`, `cost`, `currency`, `documentUrl`, `closedIssueId`, `revision`; `odometer` is the exact stored string or `null`, and costs remain decimal strings or `null` |
| `history` | `sequence`, `vehicleId`, `action`, `occurredAt`, `before`, `after` |

The export reads all included tables and the application version/schema metadata in one SQLite read transaction. It does not update the database, add audit events, or upgrade the schema.

## Download in the interface

When the standalone `dataExport` capability is available, the application toolbar shows **Daten exportieren**. The browser downloads `wolfs-garage-export.json`. Protect that file as sensitive vehicle data. The API is subject to the same configured-host boundary as other reads; the app has no built-in authentication, so non-local access still requires the documented authenticated proxy.

## HTTP API

`GET /garage-api/export` returns the JSON file as an attachment named `wolfs-garage-export.json` with `Cache-Control: no-store`. It accepts no query parameters; any query string returns `400`. The response is advertised by `dataExport` in `/garage-api/capabilities`. The route uses the configured request host and returns `503` if the application database is unavailable.

## CLI file export

Use a new path for each export:

```sh
docker compose --env-file .env.example -f deploy/compose.standalone.yaml exec garage \
  python -m wolfs_garage export /var/lib/wolfs-garage/wolfs-garage-export-UNIQUE.json
```

The CLI refuses existing paths, symlinks, and the database path. It creates a new export with owner-only `0600` permissions, flushes it, and calls `fsync`. If writing fails after creation, it removes only the partial file it created. Copy the result to the destination you choose and store it securely; a copy inside the same data volume is not an independent backup.

The explicit CLI syntax is `python -m wolfs_garage export NEW_PATH`. It reads the current database and does not initialize, upgrade, or alter it. For recoverable backups and restore instructions, use the [standalone guide](standalone.md#backup-and-isolated-restore).

## Historical format 1 evidence

On 2026-10-28, format version 1 was checked against schema 3: 82 tests matching `test_own_*.py` passed. Real Chromium passed on a fresh schema-3 database. Its synthetic export included two vehicles, a corrected record, three readings with exact string values, and closure/correction audit events; command replay data and JavaScript errors were absent. The CLI checks covered mode `0600`, overwrite and symlink/database-path refusal, and partial-file cleanup. These checks remain historical evidence for format 1 and used synthetic data only. Current application export is format 2 on schema 4.

To reproduce the current browser acceptance with an isolated local Compose volume, initialize and start a fresh schema-4 instance on loopback port 18987:

```sh
GARAGE_PORT=18987 GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18987 \
  docker compose --project-name wg-data-export-browser --env-file .env.example \
  -f deploy/compose.standalone.yaml run --rm --no-deps garage \
  python -m wolfs_garage init-db

GARAGE_PORT=18987 GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18987 \
  docker compose --project-name wg-data-export-browser --env-file .env.example \
  -f deploy/compose.standalone.yaml up -d
```

In a browser-test environment with Node.js and Chromium under `/ms-playwright`, run `node tests/data_export_browser.cjs`. The script creates both vehicles and their synthetic records through the public API, then downloads through the visible UI link. The API/file/CLI suite can be rerun with `.venv/bin/python -m unittest discover -s tests -p 'test_own_*.py'`. No production database or registry image is involved.
