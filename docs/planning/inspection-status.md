# Inspection due-month status

This feature stores the vehicle owner's recorded inspection due month and derives a calendar status from it. The date comes from the operator's own evidence; the application does not infer a due month or make a claim about legal deadlines.

## Owner policy

The stored value is nullable `YYYY-MM`. An unknown value stays `unknown` with no guessed deadline. For a known month, `monthsUntilDue` compares the due month to the current calendar month in `Europe/Berlin`:

- Positive: `upcoming`; zero: `due`; minus one: `overdue`; minus two or less: `blocking`.
- `validUntil` is the last calendar day of the due month. `blockingFrom` is the first day two calendar months after that month.
- Thus an August due month becomes overdue during September and blocks the readiness projection on October 1 under this owner's policy. This is a product rule, not a statement of law.
- `batteryLevel` is the remaining month count clamped to 0–12; `scaleMonths` is 12. Unknown dates have a `null` battery level.

The projected `effectiveReadiness` is `not_ready` if manually stored readiness is already `not_ready` or inspection state is `blocking`; otherwise it equals stored readiness. Inspection never changes the stored readiness, issue list, odometer readings, or history. Updating/clearing the due month removes only the inspection-derived block. Manual `not_ready` remains in effect.

## API and persistence

Vehicle create/update accepts `inspectionDueMonth` as `null` or canonical `YYYY-MM`, years 0001–9998. Omission during update preserves the existing value; explicit `null` clears it. A successful update increments the vehicle revision and audits the stored vehicle fields. Public vehicle and summary responses add `inspection` and `effectiveReadiness`; `status.readiness` remains the manual value. The date provider is read once for a list projection and each returned object carries `asOf` and `timeZone`.

Schema 4 adds nullable `vehicles.inspection_due_month`. Fresh databases use schema 4. Schema 1, 2, or 3 requires an explicit checked-backup upgrade; startup does not migrate. Schema 1 also gains its existing `records.revision` field. Schema-4 upgrade is a no-op without a backup. Backups can read schemas 1–4. Automatic live updates must keep the running and candidate schemas equal; schema 3 to 4 remains a separate migration and cutover.

Portable export format 2 includes the raw `inspectionDueMonth` in stored vehicle metadata, but omits `inspection` and `effectiveReadiness`. Existing audit payloads retain their original recorded fields.

## Acceptance focus

Synthetic tests cover month and year boundaries, leap-year month ends, the Berlin date, clamped and unknown battery values, manual/effective readiness separation, renewal and clearing behavior, stale revisions, invalid stored values, export shape, and explicit upgrades from schema 1/2/3 with rollback and backup checks. Browser acceptance uses a fixed-clock test-only WSGI app and synthetic vehicles. No live vehicle data belongs in fixtures or screenshots.

For the browser run, initialize a new temporary schema-4 database, then serve only the preview app on loopback. Its fixed clock is test-only:

```sh
export GARAGE_DB=/tmp/wg-inspection-preview.sqlite3
export GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18988
.venv/bin/python -m wolfs_garage init-db
.venv/bin/gunicorn --pythonpath tests --bind 127.0.0.1:18988 inspection_preview:app
```

In the isolated Chromium environment run `node tests/inspection_browser.cjs`. The script creates its own synthetic vehicles and captures mobile evidence under `/out`; remove the temporary database after stopping the preview server.

## Verification evidence — 2026-10-28

All 116 tests matching `test_own_*.py` passed. Real Chromium passed against the fixed-clock preview: unknown, upcoming, due, overdue and blocking states; month editing and renewal; manual readiness preservation; the 12-cell clamp; unchanged card height; and no horizontal overflow at 320, 390, 768 and 1280 pixels. Screenshots: [12-month battery](../discovery/evidence/inspection-battery-mobile.png), [compact vehicle cards](../discovery/evidence/inspection-cards-mobile.png), and the [320px INOP card with open work and battery](../discovery/evidence/inspection-inop-card-320.png).

An isolated CLI rehearsal upgraded a copy of a synthetic schema-3 database to schema 4, verified the backup remained schema 3, restored that backup to a separate file, and checked it with the older schema-3 image. All six pre-existing tables' data matched across source and upgraded copy; only the vehicle rows gained the new nullable column. The original source copy was unchanged. These checks used synthetic data; no production migration or deployment was part of this verification.

## Private reference rollout note

The merged `main` revision `f0a6` is running schema 4 on the private reference instance. A fresh checked schema-3 backup was copied to independent NAS storage and checksum-verified. Upgrade and old-image restore preflight on a separate copy preserved all six tables; only `vehicles` gained the nullable inspection field, and all five existing vehicles remained. Runtime/API `0.1.0a6`, `inspectionStatus`, and export format 2 were verified. Existing inspection months remain unknown until entered by the owner; no values were inferred. The maintenance/update timer is enabled; automatic updates accept same-schema 3 or 4 and fail closed across schema changes. The first schema-3 automatic rollout was independently verified; routine schema-4 automatic redeployment remains to be verified.
