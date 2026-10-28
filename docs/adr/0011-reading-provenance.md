# ADR-0011: Link record odometers to their readings

- **Status:** Proposed — not accepted or implemented
- **Date:** 2026-10-28

## Context

Creating a completed record with an odometer value currently creates a separate odometer reading in the same transaction. The reading note may say `Record <id>`, but that text is not provenance: there is no foreign key and consumers must not infer a relationship from the note, date, or matching value. The current schema is version 4, which adds an optional inspection due month; record date, odometer value and unit remain locked by the bounded correction workflow.

Safe date/odometer correction therefore needs a durable link to the exact reading the record created. Existing data must not acquire invented links during an upgrade.

## Proposed direction

1. Prepare an additive schema 5 with a nullable `odometer_readings.source_record_id` reference and `revision` defaulting to 1. A record may source at most one reading; new manual readings have no source record. Add a provenance value: `legacy_unknown` for existing readings, `manual` for new explicit readings, and `record` for readings created with a completed record.
2. Preserve legacy rows and their notes. Do not infer historical links from note text, matching dates, values, units, or IDs. A foreign key alone does not prove vehicle/date/value/unit equality. Design same-vehicle enforcement with a composite foreign key and transaction validation; verify exact record/readings facts when creating or changing a link.
3. Upgrade schemas 1, 2, 3, and 4 only through an explicit schema-5 command after a checked backup. Initialization remains create-only; normal startup must not create or upgrade a missing or incompatible database. Reuse the existing schema-1 record revision step and preserve the schema-4 inspection due-month column. Upgrade and restore rehearsals use separate synthetic copies.
4. In a follow-up stage after provenance preparation, add a separate, explicit correction operation taking expected record and reading revisions, `commandId`, and a reason. It atomically updates the record date and exact odometer value (at most three fractional digits) plus its linked reading and appends before/after audit history. A record without a reading can change its date only. Unit, vehicle, readiness, and issue closure remain immutable; do not add reading insertion/removal or unit conversion to the first correction stage.
5. Do not offer linked correction for a legacy record with an odometer but no verified source reading. Define a separate resolution contract before allowing an operator to select or establish that link.
6. Warn before confirmation when changing date/value would alter the vehicle's current reading projection. Current reading is selected by latest date, then descending reading ID; it is not the maximum odometer value.
7. Version the portable JSON export contract before including provenance/revision fields. The current format version 2 stays unchanged; a future format version must explicitly describe the new fields.

## Constraints and future validation

The record, reading, link, and audit event must commit or roll back together. Expected tests include explicit upgrades and backups from schemas 1–4; preservation of legacy rows, command responses and history; uniqueness and same-vehicle/date/value/unit link checks; rollback and idempotent retries; stale record/reading revisions; exact values with at most three fractional digits for km/mi/h; same-date reading ties; zero values; current-reading projection changes; and export format versioning. These are acceptance requirements for a later implementation, not tests run for this proposal.

## Consequences and open decision

This proposal leaves schema 4 behavior and current correction/API contracts unchanged. It does not declare schema 5 or date/odometer correction approved. Review must settle the exact link constraints, legacy resolution policy, event payload, and export-version transition before implementation.
