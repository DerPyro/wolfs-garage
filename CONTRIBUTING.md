# Contributing

Wolfs Garage is an early standalone vehicle logbook. Contributions to original project code are made under the project's [MIT license](LICENSE). Preserve third-party notices and identify the source of any added artwork or dependency.

Start with [the standalone guide](docs/standalone.md), [requirements](docs/requirements.md), [architecture](docs/architecture.md) and [roadmap](docs/roadmap.md). The historical LubeLogger work is integration evidence; it is not the standalone application's architecture.

Use synthetic vehicle data in examples, fixtures and screenshots. Keep personal documents, real vehicle identifiers, databases, deployment credentials and local configuration out of commits. Share a small change with its user-visible behavior, relevant checks and limitations. Never modify someone's deployed instance to demonstrate a contribution.

For backend changes:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m unittest discover -s tests -p 'test_own_*.py'
```

Frontend changes should also exercise the existing mock checks and a browser flow against synthetic data. Changes to persisted schema require an explicit upgrade and backup/restore plan. Unknown schema versions must fail visibly rather than reset the database. Manufacturer maintenance facts require a source; do not invent intervals or infer roadworthiness from an automatic suggestion.

Run the frontend mock checks with Node.js 22 or later:

```sh
node frontend/test-ui.cjs
```

GitHub Actions runs these checks, the standalone Python tests on Python 3.12/3.13, and the container build. Browser workflows remain separate synthetic integration checks; the mock checks alone are not an end-to-end browser test.
