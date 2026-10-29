# Optional tested-main updater

This optional updater builds Wolfs Garage from the exact `main` commit whose
GitHub Actions **Checks** workflow completed successfully. It uses the public
source repository and builds locally; it does not require a registry login or
GitHub token. The timer only installs a candidate when its commit has passed
the configured checks and differs from the active release.

The updater is intended for an operator-controlled Linux host with Docker,
systemd and an already protected reverse-proxy network. It does not change the
proxy, DNS, firewall or authentication policy. Keep the application reachable
only through the configured authenticated proxy. The live Compose file does
not publish a host port.

## Update and rollback behavior

On each timer run, the updater checks the current `main` commit and finds a
completed successful **Checks** run for that exact commit and the `push`
event. It skips the active commit. Missing, failed, in-progress or older
workflow runs do not qualify. It fetches and checks out that exact commit,
then builds a local candidate image.

Before changing the running service, it validates the candidate against an
isolated copy of the current database and makes a checked backup. Automatic
updates support schemas 3, 4, 5 and 6 only when the running database, candidate
image and checked copy all report the same schema. Any mismatch or unsupported
schema leaves the live application and database untouched; a schema change
requires a separate explicit checked-backup upgrade. Startup never performs an
implicit schema migration.

The configured maintenance-prepare hook must route requests to a maintenance
response and allow active writes to drain before the live database is copied
and the service is replaced. The updater checks the live backup before
starting the candidate. It then checks the application health endpoint. If
the candidate fails, it retains the failed database for investigation and
restores the prior image only when the database schema is still compatible;
it never starts an older image against an upgraded database. The
maintenance-finish hook restores normal routing after success or a safe
rollback. If maintenance cannot be established or safely finished, the
updater fails closed and logs the error for the operator.

SQLite and Compose volumes are not transactional deployment systems. Keep
independent backups and monitor the updater's systemd journal. Do not remove
the current or failed release directories while investigating a failed
update.

The database backup helper runs as container root with all Linux capabilities
dropped except `DAC_OVERRIDE`, which lets it read the application-owned
database file. Its source-volume mount is read-only, it has no network, and
this exception applies only to the one-shot backup helper. The live
application container keeps all capabilities dropped.

For an initial manual Compose start against an existing installation, set
`GARAGE_IMAGE` to the exact image reference that is currently serving the
database. A bootstrap placeholder can name an older or different image; using
it with `docker compose up` may replace the healthy container. After setup,
prefer the updater for releases. The updater skips a commit only after checking
that the recorded SHA matches the latest tested source, the running container
uses the corresponding local image tag, and that container is healthy. The
`active-main-sha` state file alone does not prove which image is running.

## Host configuration

The repository provides example files under `deploy/`. Copy the live Compose
file and environment template to root-owned locations outside the checkout.
Replace every placeholder with values for the host. The updater environment
file must be a root-owned regular file with mode `0600` or stricter. Keep its
parent directory and maintenance hooks root-owned and writable only by root;
the updater does not source hook files or accept hook commands from the
repository. Do not commit local paths, hostnames, credentials, vehicle data
or installation details.

Configure the environment keys shown in `deploy/live-update.env.example`:

- Compose file path, release/state directories, existing data volume and
  private proxy network.
- Public application origin, local image prefix and health timeout.
- Fixed maintenance-prepare and maintenance-finish executable paths.

The hook executables take no arguments. Prepare should switch the proxy to a
maintenance response and wait for in-flight writes to finish. Finish should
restore the normal upstream. Test both hooks against a separate test service
before enabling the timer. They must be idempotent and return a failing exit
status if the requested transition cannot be confirmed.

Install and enable the packaged systemd service and timer according to local
host policy. The provided timer polls every five minutes after boot, with a
small randomized delay. The timer controls update cadence; do not invoke the
updater concurrently with another deployment or database maintenance
operation. Check service output with `systemctl status` and
`journalctl -u wolfs-garage-update.service` using the host's normal
administrative access.

This updater is optional. The existing source-build Compose workflow remains
available for manual installation and controlled maintenance. It does not
perform data import, change external proxy configuration, or automatically
upgrade the database schema.

## Reference installation status — 2026-10-29

The privately operated reference installation was explicitly migrated from
schema 4 to schema 5 using the reviewed main commit `0830971426c2`, after its
checks passed. A fresh offline schema-4 backup was independently copied and
hash-verified before migration. Integrity, foreign-key, schema, API, export,
backup and health checks passed; the existing six data tables and sequence
state were preserved, and prior readings remain unlinked with
`legacy_unknown` provenance. The private reference installation remains at
application version `0.1.0a8` and schema 5 pending separate approval for a
schema-6 migration. The updater code in this repository accepts matching
schemas 3–6. A schema-6 candidate is rejected while the reference database is
schema 5. The installed application has not been updated to this source, and
no schema-6 migration or deployment has been performed on the reference
installation.

An isolated rehearsal used a fresh copy of a schema-5 backup. The copy upgraded
to schema 6, and a separate restore of the original backup opened successfully
with the older `0.1.0a8` image. Shared columns across the six domain tables and
`sqlite_sequence` matched; new fields held `annual_usage=NULL` and
`reading_prompt_days=30`; integrity and foreign-key checks passed. The
pre-upgrade backup and separate restore were byte-identical. This rehearsal did
not change the reference database or deploy schema 6.
