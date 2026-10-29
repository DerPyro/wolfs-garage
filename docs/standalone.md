# Standalone alpha: operator and developer guide

Wolfs Garage standalone is an early, independent vehicle record application. It uses its own SQLite database and does not read or write the existing LubeLogger installation. The private reference instance now runs schema 5 after the explicitly authorized and rehearsed 2026-10-29 migration; this did not replace or import the separate LubeLogger installation. Other operators must plan and rehearse their own migrations.

## Run locally with Docker Compose

From the repository root, build the image:

```sh
docker compose --env-file .env.example -f deploy/compose.standalone.yaml build
```

Initialize the database explicitly, once, before starting the service:

```sh
docker compose --env-file .env.example -f deploy/compose.standalone.yaml run --rm --no-deps garage python -m wolfs_garage init-db
```

Start the app and open <http://localhost:8080>:

```sh
docker compose --env-file .env.example -f deploy/compose.standalone.yaml up -d
```

Compose stores the SQLite database in the named `garage_data` volume, mounted at `/var/lib/wolfs-garage`. Container recreation preserves that volume. Database initialization uses create-only semantics: it will fail if a database file already exists. Do not rerun initialization to repair or upgrade an existing database.

To stop the container while retaining its data, use `docker compose ... down` (without `-v`). Do not remove the data volume as a cleanup step.

`deploy/compose.release.yaml` is prepared for a future pinned image, but no registry image is published yet. Continue using the source-build target above until the release is explicitly available. After that, the release guide explains how to provide `GARAGE_IMAGE` and switch Compose files while preserving the same project name and data volume: [container releases](container-releases.md).

## Views and preferences

The header navigation opens **Garage**, **Sicherungen** and **Einstellungen**. The Garage view opens directly without an intro screen; vehicle creation remains there. **Sicherungen** contains the portable JSON export, the complete SQLite backup download and the offline restore instructions. There is no browser upload or JSON restore. The JSON file and SQLite backup are separate formats and purposes.

The navigation uses `#garage`, `#sicherungen` and `#einstellungen`; browser Back/Forward changes views. Switching views does not submit or discard an open form, and returning to Garage restores the selected vehicle and unsaved editor draft. Escape closes the navigation and returns focus to its button; clicking outside closes it without moving focus from the clicked control.

**Einstellungen** shows the application version and a local motion preference. **Systemeinstellung** follows the browser/operating-system `prefers-reduced-motion` setting; **Animationen reduzieren** disables smooth card-selection scrolling. The choice is saved in this browser's local storage and does not write to the Garage database or sync to other browsers.

**Verifiziert am 2026-10-29:** Synthetic real-Chromium checks passed for navigation, browser Back/Forward, draft preservation, keyboard/outside-click focus behavior, version and motion preferences, and the SQLite download at 320, 390, 768 and 1280 px. The navigation screenshot uses synthetic/empty app data: [mobile navigation menu](discovery/evidence/navigation-menu-mobile.png). The separate [SQLite backup browser check](../tests/database_backup_browser.cjs) verifies the downloaded SQLite file. These checks did not use live vehicle data.

## Network boundary and access

The Compose service binds to `127.0.0.1` on the host, by default port `8080`. Keep that loopback binding; never publish the container directly to the public Internet. The app has no in-app login or user authorization. Anyone who can reach it can view and change all vehicle data.

For access beyond the local machine, place an authenticated reverse proxy in front of the loopback-bound service and require authentication there. Configure `GARAGE_PUBLIC_ORIGIN` to the exact external HTTPS origin, including its port when nonstandard; its host and port must match requests reaching the app. HTTP origins are accepted only for localhost or a loopback IP. Origin and request-header checks prevent some cross-site writes, but do not authenticate users. A Cloudflare setup is not required for other proxy choices.

For a different local port, set `GARAGE_PORT` in a private environment file and open that port. Set `GARAGE_PUBLIC_ORIGIN` to the matching local URL. Do not put credentials, private hostnames, or vehicle data in a committed environment file.

## Data and alpha feature scope

The current app supports vehicle create/edit, readiness (`ready`, `not_ready`, or `unknown`) and open issues, dated odometer readings, service/repair records with optional decimal-string cost and currency, HTTPS document references, and an append-only application history. A repair can close an explicitly selected open issue in the same transaction. Odometer and record create commands accept a `commandId` for idempotent retries.

To enter the HU month, select a vehicle, choose **Fahrzeug bearbeiten**, and use **HU / TÜV gültig bis**. The adjacent information control explains where to read the month and year on the rear plate; the last HU report is an alternative source. The help links to the [TÜV NORD HU information page](https://www.tuev-nord.de/de/dienstleistungen/pruefung-und-gutachten/hauptuntersuchung/). Vehicle detail presents the recorded due date and approximate remaining time in one compact line, with clear text for due this month, overdue/blocking, unknown and unavailable; it has no separate HU meter or repeated projection-as-of date. The existing compact card bar continues to show the state across the 24-month display range.

Document references are stored as URLs only; the app does not fetch or upload documents. Do not use them as a substitute for document access control.

Completed records support two bounded correction flows. The older operation changes description, service/repair kind, cost, currency and optional HTTPS reference. A separate measurement operation changes a record date and, only when its source reading is linked, the exact odometer value; it requires both revisions, a reason and an idempotency key, and updates both rows plus audit history atomically. A record without an odometer can have its date corrected only. Manually entered readings have a separate editor. Vehicle creation has no retry `commandId`: if a create request times out with an unknown result, inspect the vehicle list before submitting it again to avoid duplicates.

Schema 5 readings carry revision and provenance (`manual`, `record` or `legacy_unknown`). Older rows stay unresolved after upgrade; a note such as `Record 123`, matching dates or equal values never creates a guessed association. An owner can explicitly confirm an unresolved reading as manual, or link it to a selected same-vehicle record only when date, exact value and unit match. Until confirmed, a legacy record with an odometer cannot be measurement-corrected. The UI warns when a correction may change the current reading; that projection is latest date and then descending reading ID, not the greatest value. Unit conversion, issue closure and readiness changes are outside these correction flows. See [measurement correction and provenance](planning/measurement-corrections.md).

Vehicle detail provides separate paginated views for completed records and odometer readings. Both support inclusive date filters; records can also be filtered by service or repair. Pages sort by date and stable ID descending. A continuation cursor is bound to its vehicle, resource, filters, limit and audit sequence. If that vehicle changes during paging, restart from the first page. These read routes do not alter application history or require a schema upgrade. The original unpaged API routes remain available for existing callers. See the [history browsing contract](planning/history-browsing.md).

Existing open work can have an optional due date, a user-selected severity (`observation`, `repair`, `critical`, or unclassified), and lifecycle `open` or `observed`. The dashboard derives overdue/today/upcoming/unscheduled labels from the current `Europe/Berlin` calendar date. From a detail row, **Bearbeiten** opens the existing status editor at that issue. **Erledigt** opens the completed-work form with the issue text drafted as the record description and today's date prefilled; odometer and cost remain optional. Nothing is written until **Speichern**. A successful save creates the record and closes only the selected issue atomically, preserving all other issue metadata and the manually stored readiness. **Abbrechen** discards the draft. This does not add issue notes, priority, recurring rules or inferred severity. Legacy issue JSON is normalized when read; upgrade does not rewrite its stored JSON. See the [scheduled work contract](planning/scheduled-work.md) and [issue completion interaction](planning/work-completion.md).

Following the user decision of 2026-10-29, maintenance planning and reliable 1.0 operation are prioritized before vehicle photo and invoice uploads. Existing HTTPS document references on completed records remain available; they are references only and do not upload or fetch files. See the [roadmap](roadmap.md).

The toolbar exposes two distinct downloads: a portable owner-data JSON export for inspection or transfer, and a complete SQLite database backup for recovery. JSON has no import/restore operation. Use the SQLite backup for restoration. See [owner data export](data-export.md) and the [backup/update workflow](planning/backup-update-workflow.md).

## Explicit schema upgrade (standalone only)

Fresh initialization creates schema version 5. The current application accepts schema 5; backup and restore support schemas 1–5. Existing schema-1, schema-2, schema-3 and schema-4 standalone databases are upgraded only by an explicit command after an isolated restore rehearsal and an independent backup. There is no automatic upgrade at application startup. This command is for Wolfs Garage's own standalone database, not for importing or replacing a LubeLogger database.

Before upgrading, stop the Compose service and build the new application image. Run the upgrade once with a new, unused backup filename inside the persistent volume:

```sh
docker compose --env-file .env.example -f deploy/compose.standalone.yaml stop garage
docker compose --env-file .env.example -f deploy/compose.standalone.yaml build garage
docker compose --env-file .env.example -f deploy/compose.standalone.yaml run --rm --no-deps garage python -m wolfs_garage upgrade-db /var/lib/wolfs-garage/garage-before-schema5-upgrade-UNIQUE.sqlite3
```

Choose a unique destination; the command refuses to overwrite an existing backup. It creates and checks a consistent backup before altering the database, then verifies the upgraded database. Schema 1 also gains the existing record `revision` column. Schemas 1–3 gain the nullable inspection due-month field; schema 4 already has it. Existing readings are rebuilt with `revision=1`, `legacy_unknown` provenance and no source link. Their IDs, exact values, dates, units and notes remain unchanged; no association is inferred from a `Record <id>` note, date or matching value. Existing records, commands, status JSON and audit history are preserved. Copy the checked backup to independent protected storage before restarting the service:

```sh
docker compose --env-file .env.example -f deploy/compose.standalone.yaml up -d
```

If the command reports that the database is already schema 5, it is a no-op and does not write a backup. Keep the schema-1–4 backup until the upgraded application data has been checked. Older schema-3 or schema-4 application images reject schema 5. A downgrade requires restoring the pre-upgrade backup to a separate stopped instance using a compatible image; never point an older image at the upgraded database. No LubeLogger import or data replacement is part of this procedure. The reference-instance schema-4-to-5 migration completed after an isolated recovery rehearsal and independent backup; see the [measurement-correction rollout record](planning/measurement-corrections.md). Other installations still require their own authorization and recovery rehearsal before migration.

## Backup and isolated restore

For a direct download, choose **Datenbank sichern** in the application toolbar. It saves the consistent SQLite snapshot with a timestamped `wolfs-garage-backup-…sqlite3` filename. The raw API attachment filename is `wolfs-garage-backup.sqlite3`. Save the file into protected off-host storage. The API requires the same trusted access boundary as the rest of the application and is not a public unauthenticated backup service.

The CLI can also create a checked SQLite backup at a new, unused destination path inside the persistent volume:

```sh
docker compose --env-file .env.example -f deploy/compose.standalone.yaml exec garage python -m wolfs_garage backup /var/lib/wolfs-garage/backup-UNIQUE.sqlite3
```

Replace `backup-UNIQUE.sqlite3` with a fresh filename each time; the command refuses to overwrite a destination. The backup is integrity-checked and created with restrictive file permissions. It can read supported schema 1–5 databases without upgrading them. Copy it off the host to your chosen protected backup storage. A backup kept only in the same volume is not an independent backup. Both download paths preserve the database schema and include command replay state; neither performs an upgrade.

Restore only into a new database file in a separate Compose project and volume. The command validates SQLite integrity, foreign keys and supported schema 1–5, then makes a restricted-permission copy. It rejects a corrupt or unsupported source, an existing or symlink destination, the source path itself and the configured live database. It does not upgrade the source or destination schema.

Example restore rehearsal after placing the backup in a local `recovery/` directory:

```sh
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml run --build --rm --no-deps --interactive=false \
  --user 0 --cap-add DAC_OVERRIDE --cap-add CHOWN \
  --volume "$PWD/recovery:/recovery:ro" \
  -e GARAGE_DB=/var/lib/wolfs-garage/live-placeholder.sqlite3 garage \
  sh -c 'python -m wolfs_garage restore-backup /recovery/wolfs-garage-backup.sqlite3 /var/lib/wolfs-garage/garage.sqlite3 && chown 65532:65532 /var/lib/wolfs-garage/garage.sqlite3'
```

The restored copy keeps the source schema. For a schema-5 backup, validate and start the isolated instance:

```sh
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml run --build --rm --no-deps --interactive=false \
  -e GARAGE_DB=/var/lib/wolfs-garage/garage.sqlite3 garage \
  python -m wolfs_garage check-db

GARAGE_PORT=18991 GARAGE_PUBLIC_ORIGIN=http://localhost:18991 \
  docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml up -d --build

curl --fail http://localhost:18991/healthz
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml down
```

The host backup remains private; do not make it world-readable to fit the container UID. The one-off restore helper runs as root with only `DAC_OVERRIDE` to read the protected read-only source mount and `CHOWN` to hand the new `0600` destination back to the application's UID 65532. Other app runs remain unprivileged. Use a unique project name so Compose creates a separate volume, and choose an unused loopback port for the temporary health check. The current runtime only opens schema 5. If the backup is schema 1, 2, 3 or 4, do not run `check-db` or start the schema-5 app yet. In the isolated project, explicitly upgrade that restored copy and create a new checked backup first:

```sh
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml run --build --rm --no-deps --interactive=false \
  -e GARAGE_DB=/var/lib/wolfs-garage/garage.sqlite3 garage \
  python -m wolfs_garage upgrade-db \
  /var/lib/wolfs-garage/schema-before-upgrade-UNIQUE.sqlite3
```

Run that upgrade only for a schema-1/2/3/4 restore. Then use the schema-5 validation/start commands above. The operation upgrades only the new rehearsal volume; the original source backup and live volume remain untouched. Keep the restore private, verify representative vehicles, records, readings (including unresolved legacy provenance), history and retry behavior, then stop it with `down` (without `-v`). Rollback uses a separate database copy and an image compatible with that database schema. See the [backup/update workflow](planning/backup-update-workflow.md) for the update sequence.

## Develop and run the focused tests

Python 3.12 is the runtime pinned by the standalone image. In a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.lock
python -m unittest discover -s tests -p 'test_own_*.py'
```

Run the Flask application factory with Gunicorn for local development:

```sh
GARAGE_PUBLIC_ORIGIN=http://localhost:8000 GARAGE_DB=data/garage.sqlite3 \
  gunicorn --bind 127.0.0.1:8000 'wolfs_garage.api:create_app()'
```

Open <http://localhost:8000> for this development server. The configured origin and request host must match, while Gunicorn listens only on loopback.

The app expects the database to have been initialized explicitly or explicitly upgraded. The factory is `wolfs_garage.api:create_app()`. `/garage-api/capabilities` advertises supported features; the [API contract](api.md) describes routes and inputs; [scheduled work](planning/scheduled-work.md) documents the open-work fields and dashboard; [inspection status](planning/inspection-status.md) documents the due-month policy and derived readiness. The UI and API currently cover only the standalone alpha features listed above.

## Licensing

The standalone project code is offered under MIT. Third-party packages and any product names or logos retain their own notices and terms; see the repository's `THIRD_PARTY_NOTICES.md` before redistribution.
