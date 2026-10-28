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
| `POST /vehicles/{id}/odometer` | `date`, `odometer`, `unit`, `commandId`; optional `note`. Returns reading. |
| `GET /vehicles/{id}/records` | `{records: [...]}` |
| `POST /vehicles/{id}/records` | `description`, `kind` (`service` or `repair`), `date`, `commandId`; optional reading, cost/currency, document reference and selected issue closure. Returns `{record, status}`. |
| `GET /vehicles/{id}/history` | `{events: [{sequence, action, occurredAt, before, after}]}` |

Dates are ISO calendar dates (`YYYY-MM-DD`); history timestamps are UTC. Cost is an exact decimal **string**, nonnegative with at most two fractional digits, and requires an explicit uppercase three-letter currency. No conversion is performed. Current reading follows the latest dated reading; backdated entries remain history. A vehicle's unit cannot be relabelled after readings exist.

A record may contain `documentUrl` (HTTPS, no URL credentials); this is only a reference and is never fetched. To close an issue, supply its `closeIssueId` and expected `statusRevision`. The record, optional reading, issue closure and history commit atomically. This never changes readiness automatically.

Reading/record commands require a UUID `commandId`. Repeating the same vehicle/action/key/payload returns the original result without another write; a changed payload under that key conflicts. Revisions protect metadata/status from stale writes. Vehicle creation does not yet have this retry guarantee: after a lost response inspect the list before retrying.

Errors use `{error: ...}`: invalid values `400`, failed write boundary `403`, absent object `404`, stale/conflicting command `409`, excessive request body `413`, unsupported media type `415`, unavailable database `503`. `/healthz` exposes only storage availability. There are no delete operations or file uploads in this alpha.
