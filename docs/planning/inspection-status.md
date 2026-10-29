# Inspection due-month status

This feature stores the vehicle owner's recorded inspection due month and derives a calendar status from it. The date comes from the operator's own evidence; the application does not infer a due month or make a claim about legal deadlines.

## Owner policy

The stored value is nullable `YYYY-MM`. An unknown value stays `unknown` with no guessed deadline. For a known month, `monthsUntilDue` compares the due month to the current calendar month in `Europe/Berlin`:

- Positive: `upcoming`; zero: `due`; minus one: `overdue`; minus two or less: `blocking`.
- `validUntil` is the last calendar day of the due month. `blockingFrom` is the first day two calendar months after that month.
- Thus an August due month becomes overdue during September and blocks the readiness projection on October 1 under this owner's policy. This is a product rule, not a statement of law.
- The API compatibility fields remain `batteryLevel` (remaining month count clamped to 0–12) and `scaleMonths: 12`; unknown dates have a `null` battery level. The card-bottom indicator keeps its visual-only 24-month window for upcoming states: derived from unclamped `monthsUntilDue`, clamp to 0–24; at 24 or more months it is full green, then right-anchored fill empties from the left and shifts gradually toward red. Special card markers remain unchanged: unknown month is a full purple bar with a centered `?`; current-month `due` is a full yellow bar and is not expired; `overdue` or `blocking` is a full red bar with a centered `!`; an invalid/unavailable projection uses neutral gray with `!`. These markers communicate status, not remaining time.
- The vehicle detail shows a compact HU summary only: a known due date plus approximate remaining time, with explicit phrases for due this month, overdue, and the automatic INOP date when blocking. Unknown and unavailable states have clear text. It does not repeat the date at which the projection was calculated and has no meter or second progress scale. Initial loading, automatic summary refresh and work refresh keep the user's scroll position; clicking a vehicle card intentionally moves to the detail actions. The card's status colors do not change inspection state or readiness behavior. None of these displays infer a due date, define a maintenance interval, or alter API values or inspection policy.

The projected `effectiveReadiness` is `not_ready` if manually stored readiness is already `not_ready` or inspection state is `blocking`; otherwise it equals stored readiness. Inspection never changes the stored readiness, issue list, odometer readings, or history. Updating/clearing the due month removes only the inspection-derived block. Manual `not_ready` remains in effect.

## API and persistence

Vehicle create/update accepts `inspectionDueMonth` as `null` or canonical `YYYY-MM`, years 0001–9998. Omission during update preserves the existing value; explicit `null` clears it. A successful update increments the vehicle revision and audits the stored vehicle fields. Public vehicle and summary responses add `inspection` and `effectiveReadiness`; `status.readiness` remains the manual value. The date provider is read once for a list projection and each returned object carries `asOf` and `timeZone`.

Schema 4 introduced nullable `vehicles.inspection_due_month`; fresh databases currently use schema 6. Schemas 1–5 require an explicit checked-backup upgrade to schema 6; startup does not migrate. Schema 1 also gains its existing `records.revision` field. A current-schema upgrade is a no-op without a backup. Backups can read schemas 1–6. Automatic live updates must keep the running and candidate schemas equal. The private reference installation now uses schema 6; its migration and recovery evidence is in the [rollout record](../live-updates.md#reference-installation-status-2026-10-29).

Portable export format 2 historically added the raw `inspectionDueMonth` in stored vehicle metadata, but omitted `inspection` and `effectiveReadiness`. Current export format 4 also includes stored `annualUsage` and `readingPromptDays`, while omitting all derived projections. Existing audit payloads retain their original recorded fields.

## Acceptance focus

Synthetic tests cover month and year boundaries, leap-year month ends, the Berlin date, clamped and unknown API compatibility values, manual/effective readiness separation, renewal and clearing behavior, stale revisions, invalid stored values, export shape, and explicit upgrades from schema 1/2/3 with rollback and backup checks. Browser acceptance uses a fixed-clock test-only WSGI app and synthetic vehicles. It checks compact detail text for known and unknown states, absence of a detail meter, card purple unknown/yellow due/red expired markers, intentional scroll on explicit card selection, no scroll during initial/periodic refresh, and stable card height across supported viewports. No live vehicle data belongs in fixtures or screenshots.

For the browser run, initialize a new temporary schema-4 database, then serve only the preview app on loopback. Its fixed clock is test-only:

```sh
export GARAGE_DB=/tmp/wg-inspection-preview.sqlite3
export GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18988
.venv/bin/python -m wolfs_garage init-db
.venv/bin/gunicorn --pythonpath tests --bind 127.0.0.1:18988 inspection_preview:app
```

In the isolated Chromium environment run `node tests/inspection_browser.cjs`. The script creates its own synthetic vehicles and captures mobile evidence under `/out`; remove the temporary database after stopping the preview server.

## Verification evidence — 2026-10-28

Backend regression baseline: 120 Python tests passed during work-completion verification. The current UI verification includes the frontend DOM suite and real Chromium against the fixed-clock preview: compact due-date/rest-time text for upcoming, current-month due, overdue, blocking, unknown and unavailable states; no detail meter, scale or duplicate projection timestamp; initial load and the scheduled refresh preserved scroll; an explicit card click scrolled to focused detail actions; rapid vehicle selection kept the final selection; and there was no horizontal overflow or card-height change at 320, 390, 768 and 1280 pixels. Updated screenshots: [vehicle-card markers](../discovery/evidence/inspection-cards-mobile.png) and [320px INOP card](../discovery/evidence/inspection-inop-card-320.png). No compact-detail screenshot was captured. The older [detail meter screenshot](../discovery/evidence/inspection-status-bar-mobile.png) and [battery-design screenshot](../discovery/evidence/inspection-battery-mobile.png) are historical evidence only.

An isolated CLI rehearsal upgraded a copy of a synthetic schema-3 database to schema 4, verified the backup remained schema 3, restored that backup to a separate file, and checked it with the older schema-3 image. All six pre-existing tables' data matched across source and upgraded copy; only the vehicle rows gained the new nullable column. The original source copy was unchanged. These checks used synthetic data; no production migration or deployment was part of this verification.

## Private reference rollout note

This is a historical checkpoint from before the schema-5 rollout: merged `main` revision `f0b8c0c` ran schema 4 on the private reference instance. A fresh checked schema-3 backup was copied to independent NAS storage and checksum-verified. Upgrade and old-image restore preflight on a separate copy preserved all six tables; only `vehicles` gained the nullable inspection field, and all five existing vehicles remained. Runtime/API `0.1.0a6`, `inspectionStatus`, and export format 2 were verified. Existing inspection months remain unknown until entered by the owner; no values were inferred. At that point the maintenance/update timer was enabled and automatic updates accepted matching schemas 3 or 4; routine schema-4 redeployment had not yet been verified. The later schema-4-to-5 migration and current updater state are recorded in [measurement-correction rollout evidence](measurement-corrections.md).
