# Changelog

This file tracks changes for a future release. Entries under **Unreleased** do not imply that a version tag, package, or container image has been published.

## Unreleased

### Added

- Browse complete odometer and completed-work histories through date-filtered, keyset-paginated views with safe cursor restart after vehicle changes.
- Schedule existing open work with optional due dates, a user-assigned nullable severity, and `open`/`observed` lifecycle. A read-only dashboard derives due status using `Europe/Berlin` and keeps vehicle readiness independent.
- Record a nullable HU due month and derive inspection state plus an effective-readiness projection using the documented owner policy. Manual readiness and issue data remain unchanged; this is not a legal deadline calculation.
- Explicitly upgrade standalone schemas 1, 2 or 3 to schema 4 after a checked backup; initialization is create-only, and startup neither creates nor migrates a database.
- Export owner data as format version 2, including stored inspection month but no derived inspection projection. This portable JSON attachment is not a restorable backup and excludes command replay state.
- Document the bounded completed-record correction workflow: description, work kind, cost, currency, and document reference can be corrected with a reason and before/after audit. Record date, odometer, unit, and issue closure remain fixed in this workflow.

### Release preparation

- Add a pinned-image Compose configuration and container release guidance. No release tag or GHCR image has been published as part of these unreleased changes.
