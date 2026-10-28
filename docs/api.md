# Standalone alpha HTTP API

All application routes are below `/garage-api`. `GET /garage-api/capabilities` advertises `backend: standalone`, `apiVersion: 1` and supported feature names. These endpoints belong to Wolfs Garage; they are not LubeLogger endpoints.

The configured public host/port must match requests. Every write requires JSON, `Origin` equal to `GARAGE_PUBLIC_ORIGIN` and `X-Garage-Request: 1`. If supplied, `Sec-Fetch-Site` must be `same-origin`. These checks are not authentication. The deployment must protect non-local access through its authenticated proxy.

| Method and path | Payload / result |
| --- | --- |
| `GET /vehicles` | `{vehicles: [...]}` |
| `POST /vehicles` | `make`, `model`; optional `year`, `licensePlate`, `vehicleType`, `odometerUnit` (`km`, `mi`, `h`), `name`. Returns vehicle. |
| `GET /vehicles/{id}` | Vehicle including revision, current reading and status. |
| `PUT /vehicles/{id}` | Expected `revision` plus fields to change; unspecified fields are preserved. Returns vehicle. |
| `GET /vehicles/{id}/summary` | `{vehicle, status, reminders: [], services: [...]}`. This alpha has no reminder engine. |
| `GET`, `PUT /vehicles/{id}/status` | `{readiness, issues: [{id?, text}], revision}`. New issue IDs are generated; existing IDs must belong to this vehicle. |
| `GET /vehicles/{id}/odometer` | `{readings: [...]}` with dated history. |
| `GET /vehicles/{id}/odometer/page` | Bounded `{readings: [...], nextCursor: null|string}` history page; optional `from`, `to`, `limit`, and opaque `cursor`. |
| `POST /vehicles/{id}/odometer` | `date`, `odometer`, `unit`, `commandId`; optional `note`. Returns reading. |
| `GET /vehicles/{id}/records` | `{records: [...]}` |
| `GET /vehicles/{id}/records/page` | Bounded `{records: [...], nextCursor: null|string}` page; optional `from`, `to`, `limit`, `cursor`, and `kind` (`service` or `repair`). Rows keep the existing full record shape. |
| `POST /vehicles/{id}/records` | `description`, `kind` (`service` or `repair`), `date`, `commandId`; optional reading, cost/currency, document reference and selected issue closure. Returns `{record, status}`. |
| `GET /vehicles/{id}/records/{recordId}` | One record including its current `revision`; the record must belong to the requested vehicle. |
| `PUT /vehicles/{id}/records/{recordId}` | Full replacement of editable fields using exactly `revision`, `commandId`, `description`, `kind`, `cost`, `currency`, `documentUrl`, `correctionReason`. Returns `{record}` and increments `revision`. |
| `GET /vehicles/{id}/history` | `{events: [{sequence, action, occurredAt, before, after}]}` |

Dates are ISO calendar dates (`YYYY-MM-DD`); history timestamps are UTC. Cost is an exact decimal **string**, nonnegative with at most two fractional digits, and requires an explicit uppercase three-letter currency. No conversion is performed. Current reading follows the latest dated reading; backdated entries remain history. A vehicle's unit cannot be relabelled after readings exist.

Paged history is advertised by the `historyBrowsing` capability. `from` and `to` are optional inclusive ISO calendar dates. `limit` defaults to 25 and must be 1–100. `kind` is supported only for records. Unknown, duplicate, empty, or invalid query parameters return `400`. Rows sort by date descending and stable ID descending. The continuation cursor is opaque and binds the vehicle, resource, filters, limit, last sort key, and latest vehicle audit sequence. Wrong-context or malformed cursors return `400`; a vehicle change since the page was issued returns `409` and requires restarting at the first page. Each page reads its rows and audit sequence in one SQLite read transaction. These routes do not modify history or schema. The legacy unpaged `GET /vehicles/{id}/records` and `/odometer` responses are unchanged. Full details and browser acceptance behavior are in [history browsing](planning/history-browsing.md).

A record may contain `documentUrl` (HTTPS, no URL credentials); this is only a reference and is never fetched. To close an issue, supply its `closeIssueId` and expected `statusRevision`. The record, optional reading, issue closure and history commit atomically. This never changes readiness automatically.

Record corrections apply only to completed records. The `PUT` body is a strict full replacement: all eight listed keys are required and additional keys are rejected. `cost` must remain a decimal string with at most two fractional digits and `currency` an uppercase three-letter code; both must be valid together or both `null`. `documentUrl` is either `null` or an HTTPS URL without embedded credentials. `correctionReason` must be nonblank and at most 1600 characters. The request must change at least one editable value. A successful correction increments the record revision once and appends `record.corrected` history with the prior record in `before` and the replacement plus reason in `after`. Date, odometer, odometer unit and `closedIssueId` are immutable through this operation; attempts to submit any of them are rejected. Corrections do not modify odometer history, issue state or readiness.

An identical retry with the same `commandId` returns the original response, including after the record revision has advanced. Reusing that command ID with changed content conflicts. A different command against a stale revision returns `409`; a record missing from or belonging to another vehicle returns `404`. These routes use the same configured host, JSON, `Origin`, and request-header boundary as other writes.

Reading/record commands require a UUID `commandId`. Repeating the same vehicle/action/key/payload returns the original result without another write; a changed payload under that key conflicts. Revisions protect metadata/status from stale writes. Vehicle creation does not yet have this retry guarantee: after a lost response inspect the list before retrying.

Errors use `{error: ...}`: invalid values `400`, failed write boundary `403`, absent object `404`, stale/conflicting command `409`, excessive request body `413`, unsupported media type `415`, unavailable database `503`. `/healthz` exposes only storage availability. There are no delete operations or file uploads in this alpha.
