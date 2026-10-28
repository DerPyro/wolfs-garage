# History browsing contract

This contract describes the standalone HTTP API for browsing complete odometer and completed-work histories in bounded pages. It does not change the legacy unpaged routes, their consumers, or the separate append-only audit history.

## API

Both routes are advertised through the `historyBrowsing` capability:

- `GET /garage-api/vehicles/{id}/records/page`
- `GET /garage-api/vehicles/{id}/odometer/page`

Both accept optional `from` and `to` ISO calendar dates, inclusive, and `limit` (default 25, range 1–100). Only records additionally accept `kind=service|repair`. `cursor` is an opaque continuation token returned by the server. Unknown, repeated, empty, malformed, or out-of-range query parameters return `400`; a missing vehicle returns `404`.

The records response is `{ "records": [...], "nextCursor": null|string }`, and each record has the existing full record representation. The odometer response is `{ "readings": [...], "nextCursor": null|string }`, with the existing dated reading representation. Rows sort by calendar day descending and then stable row ID descending. The server fetches at most `limit + 1` matching rows to determine whether another page exists.

Cursor payloads bind the vehicle, resource, date and kind filters, page size, last `(day, id)` key, and the vehicle's latest audit sequence. The token is opaque to clients and must not be edited or synthesized. A malformed token or one replayed against a different vehicle, resource, filter, or page size returns `400`. A token whose vehicle audit sequence changed after the first page returns `409`; clients restart from the first page. This also detects new backdated entries and corrections that change a record's kind.

Each page reads the current audit sequence and rows in one SQLite read transaction. Paging does not create audit events or mutate records, readings, vehicle state, or schema. These routes use the same configured host boundary as other API reads; they do not introduce authentication. The standalone deployment still requires the documented authenticated proxy for non-local access.

## Browser behavior

Vehicle detail exposes separate work-record and odometer-history views. Each view shows a bounded page, supports applicable filters, and offers a load-more action when a continuation cursor exists. Record correction remains available for each loaded record, including records on later pages. If data changes while the user pages, the client discards that continuation and asks the user to reload the current list from its first page.

## Acceptance coverage

The public HTTP acceptance test uses only synthetic vehicles and data. It covers same-day ordering and no duplicate/missing rows across pages, inclusive filters, all invalid and duplicate parameter cases, cursor binding and invalidation, vehicle isolation, configured-host checks, unchanged unpaged routes, read-only behavior, and persistence across app recreation. The complete standalone backend suite passed: 55 tests. The Chromium acceptance script passed with 32 synthetic work records (including one backdated insert) and 31 odometer readings. It verified both pages, date and kind filters, correction of the oldest record from a later page, stale-cursor recovery, and layouts at 320, 390, 768 and 1280 pixels without horizontal overflow. No live vehicle data or external service was used. The [synthetic mobile browser screenshot](../discovery/evidence/history-browser-mobile.png) is retained as visual evidence.

To reproduce against a separate local Docker volume, initialize and start the app with a unique Compose project name and loopback-only port 18984. Run these commands from the repository root; the existing standalone project and legacy installation are not selected:

```sh
GARAGE_PORT=18984 GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18984 \
  docker compose --project-name wg-history-browser --env-file .env.example \
  -f deploy/compose.standalone.yaml run --rm --no-deps garage \
  python -m wolfs_garage init-db

GARAGE_PORT=18984 GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18984 \
  docker compose --project-name wg-history-browser --env-file .env.example \
  -f deploy/compose.standalone.yaml up -d
```

In a browser-test environment with Node.js, Chromium available under `/ms-playwright`, and a writable `/out` directory, run:

```sh
node tests/history_browser.cjs
```

The browser script creates its own synthetic vehicle and rows through the public app UI/API. For the HTTP acceptance tests, run `.venv/bin/python -m unittest discover -s tests -p 'test_own_*.py'`. Keep the test Compose project and its volume isolated; these checks do not require or modify production or legacy data. The API contract's `history` audit endpoint remains distinct and unchanged.
