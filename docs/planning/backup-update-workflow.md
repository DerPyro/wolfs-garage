# Backup, restore and update workflow

This runbook separates two downloads with different jobs:

- **Owner-data JSON** is a portable inspection/transfer projection. It excludes command replay state and has no supported import or restore operation.
- **SQLite backup** is the complete recovery artifact. It preserves all database tables, including command replay state, and keeps its source schema. Use **Datenbank sichern** in the UI/API or `python -m wolfs_garage backup NEW_PATH`.

Treat both files as sensitive vehicle data. Keep a backup outside the application host and data volume. The HTTP backup is an authenticated-boundary administrative download, accepts no query parameters, and uses a private temporary snapshot removed when the response closes. A failure returns an unavailable response and removes the temporary file.

## Before updating

1. Select a candidate source revision that is a known Git tag or full commit. Record the tag, resolved 40-character commit SHA, application version, current database schema, and resulting container image digest. Use a clean source checkout. An exact image digest is the strongest pin; a source tag alone does not freeze a rebuilt image's dependencies unless those inputs are pinned too.
2. Confirm the candidate is compatible with the current schema. Normal startup never creates or upgrades an existing database. Automatic deployment must fail closed on schema mismatch.
3. Stop writes for the backup point. Create a fresh SQLite backup destination and copy it to independent protected storage. Check the retained file with `python -m wolfs_garage check-db` against a copy or use the isolated restore procedure below; do not treat successful download alone as a restore test.
4. Preserve the previous known-good image digest and its matching schema information. Keep the backup until the update and recovery window have passed.

For example, with the standalone Compose project running and the application image already selected:

```sh
docker compose --project-name wolfs-garage-standalone \
  --env-file .env -f deploy/compose.standalone.yaml stop garage

docker compose --project-name wolfs-garage-standalone \
  --env-file .env -f deploy/compose.standalone.yaml run --rm --no-deps --interactive=false garage \
  python -m wolfs_garage backup /var/lib/wolfs-garage/backup-before-update-UNIQUE.sqlite3
```

Copy that new backup off-host before restarting. The same-volume file is only a staging copy, not an independent backup. Use an authenticated, protected channel for off-host copies.

### Pin the source build

Until a release image is actually published, source-build from a reviewed tag resolved to a full commit. Replace `REVIEWED_TAG` with a real tag; record the resolved SHA and ensure the checkout is clean before building:

```sh
git fetch --tags
git rev-parse 'REVIEWED_TAG^{commit}'
git checkout --detach FULL_40_CHARACTER_COMMIT_SHA
git status --short
docker compose --project-name wolfs-garage-standalone \
  --env-file .env -f deploy/compose.standalone.yaml build garage
docker compose --project-name wolfs-garage-standalone \
  --env-file .env -f deploy/compose.standalone.yaml images -q garage
```

Record the built image ID alongside the source SHA; rebuilding the same tag is not guaranteed to produce identical bytes. When a registry release is published, pin its version or preferably the manifest digest in `GARAGE_IMAGE`, then pull and update through the release Compose file:

```sh
export GARAGE_IMAGE=ghcr.io/derpyro/wolfs-garage@sha256:REPLACE_WITH_RECORDED_MANIFEST_DIGEST
docker compose --project-name wolfs-garage-standalone \
  --env-file .env -f deploy/compose.release.yaml pull garage
docker compose --project-name wolfs-garage-standalone \
  --env-file .env -f deploy/compose.release.yaml up -d garage
curl --fail "$GARAGE_PUBLIC_ORIGIN/healthz"
```

This is future guidance only: no GHCR image is published yet. For rollback without a schema change, set `GARAGE_IMAGE` back to the recorded prior digest, then use the same release Compose `up -d garage` command; only do so if the prior image supports the current database schema.

## Restore rehearsal

Use a unique Compose project name, which creates a new named volume. Put a copy of the backup in a local `recovery/` directory. The current application supports restore sources with schema 1–4; restore validates SQLite integrity, foreign keys, canonical schema layout and supported version, then writes a new exclusive `0600` destination. It does not migrate, overwrite a destination, follow a symlink, alter its source, or replace the configured live database.

```sh
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml run --build --rm --no-deps --interactive=false \
  --user 0 --cap-add DAC_OVERRIDE --cap-add CHOWN \
  --volume "$PWD/recovery:/recovery:ro" \
  -e GARAGE_DB=/var/lib/wolfs-garage/live-placeholder.sqlite3 garage \
  sh -c 'python -m wolfs_garage restore-backup /recovery/wolfs-garage-backup.sqlite3 /var/lib/wolfs-garage/garage.sqlite3 && chown 65532:65532 /var/lib/wolfs-garage/garage.sqlite3'
```

The restore leaves the source schema unchanged. For a schema-4 backup, validate and start the isolated instance:

```sh
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml run --rm --no-deps --interactive=false \
  -e GARAGE_DB=/var/lib/wolfs-garage/garage.sqlite3 garage \
  python -m wolfs_garage check-db

GARAGE_PORT=18991 GARAGE_PUBLIC_ORIGIN=http://localhost:18991 \
  docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml up -d --build

curl --fail http://localhost:18991/healthz
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml down
```

Do not weaken the off-host backup's permissions for the container. This one-off helper runs as root with only `DAC_OVERRIDE` to read the protected read-only source mount and `CHOWN` to give the new `0600` destination to the application's UID 65532; the normal app remains unprivileged. The current runtime only opens schema 4. For a schema-1/2/3 backup, stop before `check-db` or startup. Explicitly migrate the restored copy in the isolated volume and create its checked backup:

```sh
docker compose --project-name wg-restore-UNIQUE --env-file .env.example \
  -f deploy/compose.standalone.yaml run --build --rm --no-deps --interactive=false \
  -e GARAGE_DB=/var/lib/wolfs-garage/garage.sqlite3 garage \
  python -m wolfs_garage upgrade-db \
  /var/lib/wolfs-garage/schema-before-upgrade-UNIQUE.sqlite3
```

Run the upgrade only for a schema-1/2/3 source; then use the schema-4 `check-db` and startup commands above. Use the same reviewed image for restore and validation. The migration applies only to the isolated copy. Choose a free loopback port for the health check. Confirm the health endpoint and representative vehicles, statuses, readings, records, audit history and command retries. Keep the restored instance private, then stop it with `down` (without `-v`). Never mount or point the rehearsal at the live project volume.

## Update, migration and rollback

After the isolated rehearsal, deploy the selected image only after its checks pass. Confirm the application reports the expected version/schema, then check `/healthz` and one read-only vehicle view. Keep the previous image pinned. If the candidate fails, stop it and return to the previous image only when it supports the database's unchanged schema. Do not run an older binary against a newer schema.

A schema change is a separate operation. Implement the explicit migration, create a checked pre-migration backup, restore and rehearse on an isolated copy, and retain an off-host copy before any live migration. For rollback across a schema change, restore the pre-migration backup into a separate database/volume and use a compatible image; never overwrite the migrated live file. Unsupported schema transitions must stop rather than guess.

The source-build Compose setup is currently the supported install path. The pinned-image Compose file is prepared, but there is no published GHCR image to pull yet. Do not treat an example tag or registry path as available. For a source build, record the exact clean source commit and the built image identifier; for a future registry image, record the release tag and immutable manifest digest. Keep the project name and volume stable when switching Compose files so normal same-schema updates retain the intended data volume.

The private reference updater follows its separate standing authorization and tested-main process. This runbook does not change private infrastructure or authorize another production deployment. The broader channel choice—versioned stable images for self-hosters versus a separately tested-main reference channel—is a **proposed** policy in [ADR-0012](../adr/0012-release-update-policy.md), not a newly accepted release-policy change.

## Acceptance evidence

`tests/test_own_backup_roundtrip.py` uses only synthetic databases. It checks API attachment bytes and headers, request-host/query boundaries, WSGI close cleanup and backup-error cleanup; CLI restore of full tables, audit history, decimal strings and retry responses; source immutability; restrictive destination mode; and refusal of existing paths, symlinks, live/source paths, corrupt/unsupported input and malformed schema layout. No live restore is part of this acceptance suite.

Verification completed on 2026-10-29: 130 Python tests passed, including the synthetic schema-1/2/3 restore checks; the frontend DOM suite passed. Real Chromium completed the database backup download at 320, 390, 768 and 1280 pixels with no horizontal overflow. The downloaded SQLite file was restored into a new file and passed integrity, foreign-key and schema-4 checks. The browser and restore fixture used synthetic data; no live database replacement or automatic migration was introduced.

A separate Docker rehearsal used a fresh schema-4 image and synthetic backup in a new retained volume. The source was mounted read-only with private permissions; a one-off root helper used only `DAC_OVERRIDE`/`CHOWN`, then the restored file was owned by UID 65532 and passed `check-db` as the normal app user with all capabilities dropped and network disabled. No live data or volume was used.
