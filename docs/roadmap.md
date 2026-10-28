# Roadmap

Wolfs Garage is an independent, self-hosted application under MIT. The standalone alpha owns its data and does not require LubeLogger. This roadmap describes targets, not delivery dates or features already present. The [requirements](requirements.md) retain the full product scope.

## Available: 0.1 alpha

- [x] Responsive vehicle dashboard with types, manufacturer artwork and monochrome plates.
- [x] INOP for manually recorded unavailability and a wrench for open work; no task counter or green readiness check.
- [x] Vehicle creation and metadata editing with stable local identities.
- [x] Readiness and open issues maintained independently.
- [x] Dated odometer readings and service/repair records with explicit currency and optional HTTPS document references.
- [x] Atomic work-record creation and explicit issue closure; readable change history.
- [x] Revision checks and idempotent reading/record submissions.
- [x] Bounded completed-record corrections with a reason, revision check, retry handling and before/after history; date, odometer, unit and issue-closure changes remain out of scope.
- [x] Explicit schema-1/2-to-3 upgrade command with checked pre-upgrade backup; startup never upgrades automatically.
- [x] Consistent SQLite backup and synthetic isolated restore evidence.
- [x] Generic Docker Compose installation, MIT license, third-party notices, contribution guide and automated checks.

[Standalone guide](standalone.md) · [API contract](api.md) · [verification evidence](discovery/standalone-core.md)

## Next: complete the daily maintenance workflow

- [ ] Implement a safe date/odometer correction workflow with explicit links to measurement history.
- [x] Browse complete odometer and maintenance history in date-sorted pages, with inclusive date filters, record-kind filtering, safe cursor restart after changes, and correction access on later record pages.
- [x] Give existing open work optional due dates, user-assigned nullable severity and an `open`/`observed` lifecycle; show an active-work dashboard with Europe/Berlin date boundaries.
- [ ] Connect the maintenance indicator to due work as well as manually open issues, with clear reasons.
- [ ] Improve empty/error states, mobile forms and accessibility from actual use.
- [ ] Provide a clear path for optional interface translations.

## Maintenance planning

- [ ] Date-based and distance-based rules, including whichever limit comes first.
- [ ] Explicit completion and next-due calculation, with fixed versus completion-based intervals.
- [ ] Test month-end, leap-year and Europe/Berlin date boundaries.
- [ ] Track manufacturer sources and applicability; do not invent maintenance intervals or diagnoses.
- [ ] Keep readiness a separate explicit assessment rather than inferring it from completed tasks.

## Documents, parts and costs

- [ ] Choose secure local attachments, Paperless references, or both, with the required access and backup behavior.
- [ ] Link documents and parts to vehicles and individual work records.
- [ ] Distinguish part purchase, consumption and work costs to avoid double counting.
- [ ] Show useful annual vehicle costs and clearly define their relationship to payments.

## Reliable 1.0 operation

- [x] Explicit schema-1/2-to-3 upgrade with a verified pre-upgrade backup; initialization is create-only and startup never migrates.
- [ ] Complete export and documented isolated restore for all supported data and files.
- [ ] Rehearse authenticated reverse-proxy deployment and direct-origin protection.
- [ ] Establish release notes, upgrade instructions and repeatable independent backups.
- [ ] Validate and enable pinned multi-architecture container releases; publish only from an explicitly published GitHub Release, with manual builds remaining push-free. The prepared [release Compose file](../deploy/compose.release.yaml) does not imply a published image.
- [ ] Prepare a dry-run LubeLogger import with identity, unit, amount and document comparisons.
- [ ] Decide and explicitly authorize any productive cutover; preserve the original data and account for new writes during rollback.

## Later integrations

- [ ] Telegram with a configurable allowed user, confirmed writes and durable duplicate handling.
- [ ] Reminders and Google Calendar synchronization with explicit failure and retry behavior.
- [ ] Mileage projections clearly marked as estimates.
- [ ] Advisory AI using approved history and verifiable sources, with confirmation before changes.
- [ ] OBD screenshot interpretation and manually maintained fault-code history.

Each instance initially serves a trusted owner; a public multi-tenant service, a complex role system, video analysis and automatic OBD access are not part of this roadmap. Fuel tracking is outside the MVP.

## Decisions and historical evidence

The decision to build an independent core is accepted in [ADR-0009](adr/0009-backend-ownership-challenge.md), and MIT/reuse in [ADR-0010](adr/0010-open-source-mit.md). LubeLogger remains the data source for the separately running legacy installation until an authorized migration. The earlier [challenge](planning/lubelogger-vs-own.md) and [historical implementation log](discovery/roadmap-history.md) document how this direction was chosen; their old pending items do not reverse these decisions.
