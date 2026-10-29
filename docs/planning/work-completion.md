# Active issue actions and work completion

## Intended interaction

From an active issue in vehicle detail:

- **Bearbeiten** opens the existing status editor and focuses the row for that issue. Its saved due date, severity and `open`/`observed` lifecycle remain the existing fields.
- **Erledigt** opens the existing completed-work form. The issue description is a draft, the date defaults to today, and odometer and cost are optional. The operator can review and edit the description and choose the work kind before saving.
- Opening either editor is read-only. **Abbrechen** discards its unsaved changes. Only an explicit **Speichern** writes data.
- A successful completion writes the work record and closes only the selected issue in one existing atomic operation, using the expected status revision. Other issues and their metadata are retained. The manually stored readiness is not recalculated from this action.
- The resulting record appears in the vehicle's latest-work panel, paginated logbook and application history. Closure does not change inspection status or create a new issue note, priority, or severity.

## Boundaries and assumptions

This uses the existing record-creation and issue-closure contract; it requires no database schema or new status fields. Existing severity (`observation`, `repair`, `critical`, or null), due date, and `open`/`observed` lifecycle remain the only issue metadata. If the status revision is stale, the operation must fail without partially creating the record or closing the issue.

An HTTPS document URL remains an optional reference on a completed record. File upload for vehicle photos or invoices is deferred. By the user's decision of 2026-10-29, maintenance planning and reliable 1.0 operation are higher priority than uploads. This does not remove or change current document-reference behavior.

## Acceptance coverage

Use a fresh synthetic schema-4 database and the normal app on loopback. For example:

```sh
export GARAGE_DB=/tmp/wg-work-completion.sqlite3
export GARAGE_PUBLIC_ORIGIN=http://127.0.0.1:18989
.venv/bin/python -m wolfs_garage init-db
.venv/bin/gunicorn --bind 127.0.0.1:18989 'wolfs_garage.api:create_app()'
```

In the isolated Chromium environment run `node tests/work_completion_browser.cjs`. Exercise issue editing and focus, cancel without writes, completion draft values and explicit save, cancellation without writes, selected-issue-only closure, preservation of other issue metadata and manual readiness, and visibility in logbook/history after reload. Check responsive layout at 320, 390, 768 and 1280 pixels. Never use live vehicle data for this acceptance run.

## Verification evidence — 2026-10-29

The 120-test Python suite and the frontend DOM suite passed. Real Chromium passed this synthetic workflow: editing focuses the selected issue, cancellation writes nothing, the completion draft holds the selected issue ID and status revision, explicit save creates the record and closes only that issue, other issue metadata and manual readiness stay intact, and the record and both history events remain visible after reload. The card keeps its measured height and the page has no horizontal overflow at 320, 390, 768 and 1280 pixels. The browser test does not capture screenshots.
