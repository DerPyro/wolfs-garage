# Third-party notices

Wolfs Garage's original code is licensed under [MIT](LICENSE). This does not replace the licenses or trademark rights of third-party components.

## Vehicle pictograms

The embedded vehicle pictograms retain their source licenses. See [the source and attribution manifest](frontend/vehicle-icons-LICENSE.md), the included [Pictogrammers notice](frontend/vehicle-icons-Pictogrammers-LICENSE.txt), and [Apache 2.0 text](frontend/vehicle-icons-APACHE-2.0.txt). Health Icons are identified as CC0 in that manifest.

## Manufacturer logos

The manufacturer artwork is sourced from Simple Icons. The project's CC0 license does not grant third-party trademark rights or guarantee that each brand permits a particular use. See [the provenance and disclaimer links](frontend/brands/README.md). Our MIT license does not relicense manufacturer logos. Unknown makes use a text fallback; displaying a vehicle manufacturer does not indicate endorsement.

## Runtime dependencies

The Python dependencies are installed from the versions in [requirements.lock](requirements.lock), not vendored into the application source. Their distributions retain their own license files and metadata. Flask, Werkzeug, Jinja2, MarkupSafe, Click and ItsDangerous use BSD licenses; Blinker and Gunicorn use MIT licenses. Preserve the installed package notices when distributing images. The Python base image also retains its runtime and operating-system notices.

## Legacy integration fixtures

Historical LubeLogger fixtures and the unmodified upstream license remain under [tests/lubelogger/upstream](tests/lubelogger/upstream). LubeLogger itself is a separate MIT-licensed application and is not required by the standalone backend. Its license text is not a statement that manufacturer artwork is MIT-licensed.
