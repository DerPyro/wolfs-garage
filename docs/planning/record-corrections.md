# Bounded record corrections: contract and acceptance plan

## Scope decision

The first correction workflow applies to a completed service or repair record. It can replace only `description`, `kind`, `cost`, `currency`, and the optional HTTPS `documentUrl`. The user must give a nonblank correction reason (maximum 1600 characters). A successful correction increments the record revision and appends a `record.corrected` event with `{record: oldRecord}` in `before` and `{record: newRecord, correctionReason}` in `after`.

Date, odometer value, odometer unit, record identity, vehicle ownership, and `closedIssueId` are immutable through this workflow. A correction does not create or edit an odometer reading and does not reopen an issue or change readiness. A safe date/odometer correction workflow remains unimplemented and requires explicit links to measurement history. This bounded behavior is not full feature parity with the earlier maintenance-log requirements.

## HTTP behavior

- `GET /garage-api/vehicles/{vehicleId}/records/{recordId}` returns the record, including `revision`.
- `PUT` takes an exact full-replacement object: `revision`, `commandId`, `description`, `kind`, `cost`, `currency`, `documentUrl`, and `correctionReason`.
- `cost` is a decimal string with at most two fractional digits and requires an uppercase three-letter `currency`. Both values may be `null` together. A URL must use HTTPS without embedded credentials or be `null`.
- No-op requests and attempts to include locked or unknown keys are rejected without writes. A stale revision returns `409`; an identical retry returns the original result; changed content under the same command ID returns `409`.
- A record accessed through the wrong vehicle path returns `404`. Existing host, JSON, `Origin`, and request-header guards continue to apply.

## Storage and operation assumptions

Fresh databases use schema 2, with record revision defaulting to 1. The application does not upgrade on startup. An operator explicitly runs `python -m wolfs_garage upgrade-db NEW_BACKUP_PATH` against a stopped schema-1 standalone service. The command must make and integrity-check a consistent backup before altering the original, verify the resulting schema, and leave an already-schema-2 database unchanged. Backup reading accepts schema 1 and 2 so the pre-upgrade backup remains usable. Unknown schemas fail closed. This procedure is for the application's own database and does not import LubeLogger data.

The public deployment and existing LubeLogger instance remain untouched. Upgrade and correction acceptance uses synthetic records only. The operator copies the backup to independent storage before restarting; recovery rehearsals use a separate database volume.

## Acceptance evidence

Automated HTTP coverage in `tests/test_own_record_api.py` checks lookup, full replacement, revision increment, retry precedence, changed-command conflict, stale writes, immutable fields, wrong-vehicle isolation, validation, host/write boundaries, summary freshness, and before/after history. The complete standalone backend suite passed (41 tests, as reported by the orchestrating agent). `tests/record_corrections_browser.cjs` passed against a local synthetic schema-2 database in Chromium: create vehicle and INOP issue, create a dated/odometer record with issue closure, correct editable fields and remove its document link, reload, and inspect the targeted correction history for previous values, new values and reason. Date, odometer, issue closure and INOP readiness remained unchanged. Layout had no horizontal overflow at 320, 390, 768 and 1280 pixels. The [synthetic mobile correction history](../discovery/evidence/record-corrections-mobile.png) and [correction editor](../discovery/evidence/record-correction-editor-mobile.png) are included as visual evidence. These checks did not access a production database or deployment.

The explicit schema-upgrade command and repeat-upgrade no-op also passed against an earlier synthetic schema-1 database copy. A container rehearsal then upgraded a copy of that synthetic database in a separate named volume with UID 65532 and a read-only root filesystem; schema-2 `check-db` and repeat-upgrade no-op both passed. The earlier test volume remained untouched. This is isolated synthetic evidence, not a production upgrade.

The bounded first correction stage is complete for the tested workflow. Safe date/odometer corrections linked to measurement history, complete history browsing, recurring maintenance, and external integrations remain separate roadmap work.
