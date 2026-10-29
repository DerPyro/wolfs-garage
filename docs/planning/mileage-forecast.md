# Annual usage estimate and reading prompt

**Status:** Schema-6 implementation and local synthetic acceptance are complete. A schema-5-to-6 migration and compatible-image recovery rehearsal passed on isolated copies. The private reference database remains schema 5 (`0.1.0a8`) pending separate migration approval. No production migration is authorized by this feature work.

## Stored vehicle settings

Vehicles store an optional `annualUsage` decimal string from `0` through `1,000,000,000`, with at most three fractional digits. It is expressed in the vehicle's current odometer unit (`km`, `mi`, or `h`). `null` means no rate was provided; `"0"` is an explicit zero-use rate. Decimal strings are canonicalized without converting through binary floating point. An annual rate is a user-provided estimate, not a measured fact.

`readingPromptDays` is `null` (disabled) or an integer from 1 through 3650. New vehicles default to 30 days. Vehicle updates preserve either field when omitted; explicit `null` clears annual usage or disables the prompt. A vehicle with existing readings cannot change odometer units. Without readings, changing units requires explicitly clearing or replacing `annualUsage` so a rate is never silently relabeled.

## Read-only annual estimate

`mileageEstimate` is derived when public vehicle and summary responses are read. It is not stored, audited, exported, or written as an odometer reading. Its anchor is the latest actual reading, ordered by date descending and then reading ID descending, including readings whose historical provenance remains `legacy_unknown`. The estimate uses the exact stored anchor value and vehicle unit:

```text
estimated = anchor + annualUsage × elapsedDays / 365
```

The arithmetic uses decimal values and rounds half up to three fractional digits. `elapsedDays` is the difference from the anchor date to the current `Europe/Berlin` calendar date; the denominator is always 365 days, including leap years. The response includes `asOf`, `timeZone`, state, rate, unit, anchor, elapsed days and `estimatedOdometer`. It never rewrites the anchor. A future-dated anchor, unit mismatch, absent anchor/rate, or value beyond the supported odometer range produces a non-estimated state with a null estimate; the app does not clamp, reverse-project, convert units, or substitute another reading.

All supported units are projected without conversion: for `km` and `mi` the setting describes distance per year; for `h` it describes usage hours per year. The UI labels the unit and calls the output an estimate. No annual rate is inferred from readings.

## Reading prompt

`readingPrompt` is an independent, read-only projection. A missing reading yields `needs_reading`; otherwise the due date is the anchor date plus the configured number of calendar days. The prompt becomes `due` on that date. A missing prompt interval yields `disabled`. Future-dated anchors, unit mismatches and a due-date calculation outside Python's supported calendar yield `needs_review` with an explicit reason rather than a silently deferred reminder. A valid not-yet-due prompt is `not_due`.

The Garage shows inline prompts only for `needs_reading`, `due`, and `needs_review`. For `needs_reading` and `due`, the action opens the existing actual-reading form with today's Berlin date and an empty value. For `needs_review`, it opens the reading history for review. The form does not prefill the prior reading or estimate. Only an explicit user save creates an actual reading. That new reading, or a later correction/backdate, changes the anchor according to the ordinary date/ID rule and recalculates both projections. There is no snooze or dismissal write, recurring notification service, or Telegram integration in this feature; Telegram remains later roadmap work.

Both projections are calculated in the same read snapshot as the vehicle and share one Berlin `asOf` date per response. Repeated reads add no history, commands, reading rows, or profile revisions.

## Schema and export boundaries

Schema 6 adds nullable `vehicles.annual_usage` and nullable `vehicles.reading_prompt_days` (default 30 for existing rows during migration). Schema 1–5 upgrades are explicit and create a checked pre-upgrade backup; startup never migrates. Schemas 1–4 first receive the existing record revision, inspection month and reading provenance migrations as applicable. Schema 5 readings retain their exact revision, provenance and record links through schema 6. Backup/restore validate schemas 1–6; restore does not migrate. The automatic updater accepts same-schema 3, 4, 5 or 6 only; schema 5→6 remains a separate migration.

Portable owner export format 4 adds only raw `annualUsage` and `readingPromptDays` to each stored vehicle. It omits both derived projections. SQLite backup remains the complete restore artifact. See the [API contract](../api.md), [standalone guide](../standalone.md), and [backup/update runbook](backup-update-workflow.md).

## Acceptance focus

Acceptance covers exact canonical decimal limits and zero, nullable/default/disabled prompt intervals, `km`/`mi`/`h` labels, no-reading and missing-rate states, future and mismatched anchors, out-of-range estimates, Berlin midnight and fixed-365 rounding, same-date reading-ID selection, new readings and corrections reanchoring, and prompt boundaries. API and browser reads must leave reading/status/history/command counts unchanged. Migration coverage uses frozen schema 1–5 layouts and preserves prior rows, sequence high-water, record-reading revisions/provenance/links, audit and replay data; the schema-5 backup remains restorable with a compatible image. Format-4 exports contain raw settings only. Browser checks exercise the blank actual-reading prompt flow, explicit save, disablement and responsive Garage layout with synthetic data. The production database remains untouched until separately approved.

The browser runner uses a test-only fixed Berlin date of 2026-10-29 and binds only
to loopback port 18995. Initialize an isolated schema-6 database, then start its
preview app in one terminal:

```sh
mkdir -p .sandbox/mileage-browser
MILEAGE_DB="$PWD/.sandbox/mileage-browser/garage-$(date +%s).sqlite3"
GARAGE_DB="$MILEAGE_DB" \
  .venv/bin/python -m wolfs_garage init-db
GARAGE_DB="$MILEAGE_DB" \
GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18995 \
  .venv/bin/python -m flask --app tests.mileage_forecast_preview:app run \
  --host 127.0.0.1 --port 18995
```

In another terminal, run the browser helper in the Playwright Chromium image
(with the workspace mounted read-only and only the synthetic artifact folder
writable):

```sh
docker run --rm --network host \
  --volume "$PWD:/work:ro" \
  --volume "$PWD/.sandbox/mileage-browser:/artifacts" \
  --workdir /work mcr.microsoft.com/playwright:v1.55.0-noble \
  env GARAGE_BROWSER_SCREENSHOT=/artifacts/mobile.png \
  node tests/mileage_forecast_browser.cjs
```

The helper creates synthetic vehicles and readings through the public API,
checks prompt display, blank/cancel and explicit-save behavior, reanchoring,
disablement, and layout widths 320/390/768/1280. It writes a mobile screenshot
to `.sandbox/mileage-browser/mobile.png`. Stop the preview server with Ctrl-C;
do not reuse this synthetic database for application data.
