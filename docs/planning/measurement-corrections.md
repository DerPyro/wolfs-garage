# Record date and odometer corrections

**Status:** Schema-5 implementation, acceptance and the separately authorized reference-instance migration completed on 2026-10-29. The reference installation was later migrated to schema 6; the schema-5 measurements, links and revisions were preserved. No measurement facts or historical links were inferred or edited during either migration. See the [schema-6 rollout evidence](../live-updates.md#reference-installation-status-2026-10-29).

## Provenance model

Schema 5 adds `revision`, `provenance` and nullable `source_record_id` to odometer readings. Provenance is `legacy_unknown`, `manual` or `record`; old readings migrate as `legacy_unknown` with no link. Existing notes such as `Record 123` are not evidence of a relationship. A record may source at most one reading. The composite foreign key proves the linked record belongs to the same vehicle; creation/resolution also checks matching date, exact stored value and unit.

New manually entered readings are `manual`. Readings created by a completed-work record are `record` and link to that exact record in the same transaction. A record with no reading can have its date corrected without creating one. A legacy record with an odometer but no verified link stays unresolved until the owner explicitly classifies its old reading or confirms a matching record.

## Correction operations

- A linked record correction requires expected record and reading revisions, `commandId`, reason, date and exact odometer decimal string. Odometer values accept at most three fractional digits, including `0`; date and odometer update the record and linked reading atomically. Unit, vehicle, costs, work type, issue closure and readiness are not editable here.
- A date-only record correction requires the expected record revision and an explicit null reading revision/odometer. It changes no odometer row.
- A manual reading correction requires that reading's revision and changes only its date, exact value and note. Linked and unresolved readings cannot use this route.
- Legacy provenance confirmation is explicit, reasoned and revision-checked. Choosing `manual` creates no link. Choosing `record` requires an owner-selected same-vehicle record whose date/value/unit already match; it changes provenance/link metadata only, not those facts.

Every successful change is idempotent by command ID, increments the applicable revisions and appends before/after audit history. A replay returns the original response. A stale revision or conflicting link returns `409`; validation failures roll back all rows and audit changes. The UI warns that changing date/value may change the current reading projection. “Current” means latest date, then descending reading ID, not maximum odometer value. The transaction response supplies before/after projection values; the warning is not a forecast or legal/diagnostic judgment.

The API advertises `measurementCorrections`. Readings expose `odometerExact`, `revision`, `provenance` and `sourceRecordId`; the existing numeric `odometer` field remains for compatibility. See the [API contract](../api.md).

## Upgrade and data boundaries

Explicit `upgrade-db` introduced schema 5 from schemas 1–4 after a checked backup. Schema-1 record revision handling is reused; schema 4 inspection data is preserved. Migration preserves old reading IDs, exact values, notes, commands and history, sets old rows to `legacy_unknown`, and invents no links. The current upgrade path continues through schema 6; startup never migrates. Backups and isolated restore support schemas 1–6; restore itself never migrates. Same-schema automatic updates may use schemas 3–6; cross-schema updates fail closed.

Portable owner export format 3 includes reading revision/provenance/source record ID and exact reading values. Historical audit JSON remains as originally recorded. JSON remains export-only; SQLite backup is the complete restore format. See [data export](../data-export.md), the [backup/update runbook](backup-update-workflow.md) and [ADR 0011](../adr/0011-reading-provenance.md).

## Verification

On 2026-10-29 the full Python suite passed (148 tests). Frozen synthetic schema-1/2/3/4 fixtures covered explicit backup upgrades, rollback, legacy-row preservation/no inferred links and sequence high-water; API tests covered linked/manual/date-only corrections, explicit legacy resolution, stale revisions, idempotency, exact decimals and audit history. Real Chromium passed both legacy-resolution flows, linked/manual edits, exact values, audit display, reload persistence and 320/390/768/1280 px. The browser used a synthetic schema-4 fixture explicitly upgraded to schema 5. Review the [linked correction form](../discovery/evidence/measurement-correction-form-mobile.png) and [measurement audit history](../discovery/evidence/measurement-correction-history-mobile.png). Those local acceptance checks used synthetic data; the separate private recovery rehearsal and later live rollout are documented below.

A separate private copy-only recovery rehearsal used a fresh schema-4 backup from the reference installation in isolated staging. The schema-5 candidate preserved all six existing data tables and `sqlite_sequence`; all old readings became `legacy_unknown`, unlinked, revision 1. The original backup hash stayed unchanged. A separate pre-upgrade restore opened successfully with the older schema-4 image; the candidate passed schema check, format-3 export and strict-backup validation. This was rehearsal evidence only; the subsequent authorized live migration is recorded below.

## Authorized reference-instance rollout — 2026-10-29

Main commit `0830971426c2` (application version `0.1.0a8`) passed CI and was built for the rollout. With writes drained and the service stopped, a fresh offline schema-4 backup was checked, copied to independent protected storage and hash-verified before the explicit live upgrade. After migration, the six pre-existing data tables matched exactly on their shared columns, as did `sqlite_sequence`; existing readings have revision 1, `legacy_unknown` provenance and no source links. Integrity, foreign-key and strict schema checks passed. The schema-5 API and `measurementCorrections` capability, exact reading fields, format-3 export, full SQLite backup and health endpoint were verified. Normal routing resumed behind the existing access boundary; unauthenticated access remained redirected. The updater now accepts matching schemas 3, 4 and 5 and its timer was resumed. No vehicle facts were changed, and no historical link was guessed.

To recreate the browser fixture locally, choose new temporary paths each run:

```sh
PYTHONPATH=. .venv/bin/python tests/prepare_measurement_preview.py /tmp/wg-measurement-preview.sqlite3 /tmp/wg-measurement-before-upgrade.sqlite3
GARAGE_DB=/tmp/wg-measurement-preview.sqlite3 GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18994 \
  .venv/bin/gunicorn --bind 127.0.0.1:18994 'wolfs_garage.api:create_app()'
```

In the Node.js/Chromium acceptance environment, run `node tests/measurement_corrections_browser.cjs` against that loopback server. The script uses only the synthetic preview database; never point it at a personal or production database.
