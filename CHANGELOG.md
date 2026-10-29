# Changelog

This file tracks changes for a future release. Entries under **Unreleased** do not imply that a version tag, package, or container image has been published.

## Unreleased

### Added

- Download a consistent complete SQLite backup through the protected UI/API, separately from portable owner-data JSON; restore a validated backup into a new database file without overwriting the configured database or automatically migrating it.
- Document the explicit off-host backup, isolated restore, schema-upgrade and compatible-image rollback workflow. No live database replacement or automatic migration is introduced.
- Browse complete odometer and completed-work histories through date-filtered, keyset-paginated views with safe cursor restart after vehicle changes.
- Schedule existing open work with optional due dates, a user-assigned nullable severity, and `open`/`observed` lifecycle. A read-only dashboard derives due status using `Europe/Berlin` and keeps vehicle readiness independent.
- Record a nullable HU due month and derive inspection state plus an effective-readiness projection using the documented owner policy. Manual readiness and issue data remain unchanged; this is not a legal deadline calculation.
- Explicitly upgrade standalone schemas 1, 2 or 3 to schema 4 after a checked backup; initialization is create-only, and startup neither creates nor migrates a database.
- Export owner data as format version 2, including stored inspection month but no derived inspection projection. This portable JSON attachment is not a restorable backup and excludes command replay state.
- Document the bounded completed-record correction workflow: description, work kind, cost, currency, and document reference can be corrected with a reason and before/after audit. Record date, odometer, unit, and issue closure remain fixed in this workflow.
- Link record-created odometer readings explicitly and correct linked record dates/exact values atomically with expected revisions, idempotent retries and before/after audit history. Manual readings have their own correction operation; legacy links require explicit owner confirmation and are never inferred from notes or matching values.
- Add schema 5 with reading revision/provenance/source-record fields. Explicitly upgrade schema 1–4 after a checked backup; old readings remain `legacy_unknown` with no link. Startup and automatic updates do not migrate across schemas.
- Version the portable owner export as format 3 with reading provenance/revision/link fields; SQLite remains the full restore format.
- Show an annual-usage estimate derived from the latest actual reading and an inline configurable Garage prompt for a new actual reading. Projections are read-only and are never persisted as readings.
- Add schema 6 with optional exact annual usage and nullable check-prompt interval (default 30 days); explicitly upgrade schemas 1–5 only after a checked backup. Schema-6 fields are stored settings; estimates and prompt states remain derived.
- Version portable owner export as format 4 with only the stored `annualUsage` and `readingPromptDays`; omit derived projections.

### Release preparation

- Add a pinned-image Compose configuration and container release guidance. No release tag or GHCR image has been published as part of these unreleased changes.
