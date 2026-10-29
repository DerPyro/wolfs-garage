# ADR-0011: Link record odometers to their readings

- **Status:** Accepted, 2026-10-29; implemented and locally accepted, with the separately authorized reference-instance schema-4-to-5 migration completed on 2026-10-29
- **Date:** 2026-10-28; accepted 2026-10-29

## Context

Creating a completed record with an odometer value currently creates a separate odometer reading in the same transaction. The reading note may say `Record <id>`, but that text is not provenance: there is no foreign key and consumers must not infer a relationship from the note, date, or matching value. At proposal time the current schema was version 4, which adds an optional inspection due month; record date, odometer value and unit remained locked by the bounded correction workflow.

Safe date/odometer correction therefore needs a durable link to the exact reading the record created. Existing data must not acquire invented links during an upgrade.

## Accepted design

1. Prepare an additive schema 5 with a nullable `odometer_readings.source_record_id` reference and `revision` defaulting to 1. A record may source at most one reading; new manual readings have no source record. Add a provenance value: `legacy_unknown` for existing readings, `manual` for new explicit readings, and `record` for readings created with a completed record.
2. Preserve legacy rows and their notes. Do not infer historical links from note text, matching dates, values, units, or IDs. A foreign key alone does not prove vehicle/date/value/unit equality. Design same-vehicle enforcement with a composite foreign key and transaction validation; verify exact record/readings facts when creating or changing a link.
3. Upgrade schemas 1, 2, 3, and 4 only through an explicit schema-5 command after a checked backup. Initialization remains create-only; normal startup must not create or upgrade a missing or incompatible database. Reuse the existing schema-1 record revision step and preserve the schema-4 inspection due-month column. Upgrade and restore rehearsals use separate synthetic copies.
4. Provide separate operations for linked record measurement corrections, date-only records, and manual reading corrections. Linked operations take expected record and reading revisions, `commandId`, and a reason; they atomically update record date/value plus the linked reading and append before/after audit history. Values accept at most three fractional digits, including zero. Unit, vehicle, readiness, and issue closure remain immutable; do not add reading insertion/removal or unit conversion.
5. Legacy links are unresolved until an owner explicitly classifies the reading as manual or confirms a selected exact same-vehicle/date/value/unit record. This changes provenance/link metadata only and increments both revisions for a record link. A legacy record with an odometer remains locked from correction until resolution; no match is selected automatically.
6. Warn before confirmation when changing date/value would alter the vehicle's current reading projection. Current reading is selected by latest date, then descending reading ID; it is not the maximum odometer value.
7. Version the portable JSON export contract when including provenance/revision fields. Current format version 3 describes these fields; SQLite remains the full backup/restore format.

## Acceptance constraints

The record, reading, link, and audit event must commit or roll back together. Acceptance covers explicit upgrades/backups from schemas 1–4; preservation of legacy rows, command responses, history and sequence high-water; no inferred links; same-vehicle/date/value/unit validation; rollback and idempotent retries; stale record/reading revisions; exact values with at most three fractional digits for km/mi/h; same-date reading ties; zero values; current-reading projection changes; and format-3 export fields. See [measurement corrections](../planning/measurement-corrections.md) for current verification status.

## Consequences and open decision

The implementation uses schema 5, the composite same-vehicle relation, explicit owner-confirmed legacy resolution, and export format 3. It does not infer old links. Local acceptance passed on 2026-10-29 (148 Python tests and Chromium at four widths, using synthetic data). The separately authorized reference-instance migration and verification completed on 2026-10-29; existing measurement facts were preserved without inferred links. Detailed current behavior and rollout evidence are in [measurement corrections](../planning/measurement-corrections.md). Historical schema-3 and export-format-1/2 evidence remains historical and is not restated as schema-5/format-3 verification.
