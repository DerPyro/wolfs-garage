# Container release plan

This is release preparation only. No release tag or GHCR image is published by this change. Source builds remain the supported default described in the [standalone guide](standalone.md). In particular, `ghcr.io/derpyro/wolfs-garage:0.1.0a6` below is an example for a possible first release, not a published image or promise that the tag can be pulled.

## Release image configuration

`deploy/compose.release.yaml` selects an image but does not build source. `GARAGE_IMAGE` is required; set it to an exact version tag or digest. The file keeps the same Compose project name, service name, data volume, loopback port binding, public-origin setting, dropped capabilities, read-only root filesystem, `no-new-privileges`, and `/tmp` tmpfs as `compose.standalone.yaml`. Running either file in the same Compose project uses the same `garage_data` volume. Do not change the project name during a build-to-image switch.

After a first image has actually been published, a fresh installation could use commands like these. They intentionally do not work until that image exists and is accessible:

```sh
export GARAGE_IMAGE=ghcr.io/derpyro/wolfs-garage:0.1.0a6

docker compose --env-file .env.example -f deploy/compose.release.yaml pull
docker compose --env-file .env.example -f deploy/compose.release.yaml run --rm --no-deps garage python -m wolfs_garage init-db
docker compose --env-file .env.example -f deploy/compose.release.yaml up -d
```

The version above is a placeholder example only. Before a real release, replace it with the published, verified version and record both the source commit and manifest digest. Keep `GARAGE_IMAGE` in the shell environment (not `.env.example`), so it overrides Compose interpolation from the example environment file. Do not substitute `latest`. A version tag is a release name, not an inherently immutable reference; never move or reuse a published release tag. A digest pin provides the strongest reproducibility.

## Existing standalone installation

The source-build Compose target remains available. To switch image sources while preserving an installation, use both Compose files with the same project name so `garage_data` remains the same volume. Before updating, make an independent backup and rehearse a restore against an isolated copy. If the database is schema 1–5, perform the explicit checked-backup schema-6 upgrade before normal operation. With a future published image selected in `GARAGE_IMAGE`, the upgrade command would use the release image while the existing project volume is mounted:

```sh
docker compose --env-file .env.example -f deploy/compose.release.yaml stop garage
docker compose --env-file .env.example -f deploy/compose.release.yaml pull
docker compose --env-file .env.example -f deploy/compose.release.yaml run --rm --no-deps garage python -m wolfs_garage upgrade-db /var/lib/wolfs-garage/garage-before-schema6-upgrade-UNIQUE.sqlite3
```

Copy the checked pre-upgrade backup to independent protected storage before restarting the service. Only after that copy has been verified should you restart the service:

```sh
docker compose --env-file .env.example -f deploy/compose.release.yaml up -d
```

If the installation uses a custom Compose project name, pass that same `-p` value to every command so the existing `garage_data` volume remains selected. Never rerun `init-db` for an existing volume.

An upgrade changes the database in place only after writing and checking the designated pre-upgrade backup. Schema-1–5 binaries reject schema 6: do not start an older image against the upgraded database. A rollback needs a separate restored copy of the pre-upgrade database with a compatible image; keep the upgraded database untouched until recovery is understood. These instructions do not import LubeLogger data or change proxy/access configuration. The reference-instance schema-4-to-5 migration completed on 2026-10-29; the private reference database remains schema 5 pending separate schema-6 migration approval. The schema-5-to-6 rehearsal used isolated copies only. This does not perform or authorize a LubeLogger import or changes to the access boundary.

## Prepared publishing workflow

The prepared `.github/workflows/release.yml` implements this policy:

- Only a GitHub Release event with action `published` and a non-draft release can publish; the publication job waits for checks.
- A manual `workflow_dispatch` validates the checked-out repository and source, runs the checks, and builds both target architectures without pushing. It has no registry-publish permission.
- The release tag must exactly match the strict app version as `v<application-version>`; for example, version `0.1.0a6` requires `v0.1.0a6`. The checked-out HEAD must equal the tag commit, and that commit must be an ancestor of `origin/main`.
- Tests and image build use the same exact source commit SHA; the workflow passes the validated full SHA to the reusable checks workflow. A release build targets both `linux/amd64` and `linux/arm64`.
- Publish the exact version tag only; do not publish or update a floating `latest` tag. Never move or reuse a released tag. Record the release source commit and resulting manifest digest in the release notes; a digest is the immutable image reference.
- The image name is `ghcr.io/derpyro/wolfs-garage`. GHCR package visibility is a separate setting and must be deliberately made public before anonymous pulls are documented.
- Only the release-only publish job receives `packages:write` and logs in to GHCR. Published image metadata records the application version, source revision, source repository and MIT license; the workflow summary reports the manifest digest and platforms.

The workflow is prepared, but no release tag or GHCR image has been published in this change. These gates do not establish that both architectures, package visibility, or image distribution have been verified by a published release. Confirm them before publishing. See the [release checklist](open-source-release.md).

## Preparation validation evidence

On 2026-10-28, both the source-build and release Compose configurations passed local Compose configuration validation. A test container using an already available local image (not a GHCR image) started from a fresh, separate project and volume on loopback port 18986; explicit schema-3 initialization, health check, and synthetic vehicle creation passed. The source-build Compose file was then run with `--no-build` and the existing local image override in that same project. The vehicle ID remained present after switching back to the release Compose file, confirming both targets use the same project volume. The service was stopped and the test volume retained. No published image was pulled, and no registry build or push was run.

The pinned Python base-image manifest was checked and lists `linux/amd64` and `linux/arm64` support. This confirms the base image platforms only; it does not verify a multi-platform build of the Wolfs Garage image. The 76 local workflow/application checks passed, and `actionlint` 1.7.12 passed on both workflows. Manual release-metadata validation returned `publish: false`. The GitHub multi-platform workflow itself has not been executed and no tag, release, package, or image was published.

## Pre-release checklist

- Review the exact source tree, commit history, licenses, screenshots, and changelog for private data or credentials.
- Confirm the app version, strict tag, commit on `main`, and release notes agree.
- Run the complete backend, frontend, browser, and security checks on that exact SHA.
- Build one image from that SHA and verify the `amd64` and `arm64` manifests; retain and document the final digest.
- Rehearse the release Compose file in a fresh isolated volume, then rehearse schema-1/2 upgrade and restore using separate test copies.
- Check loopback publishing, non-root execution, read-only root filesystem, health behavior, and network/access guidance.
- Set package visibility deliberately. Publish only after the owner explicitly chooses the release-published event; no productive deployment is part of this checklist.
