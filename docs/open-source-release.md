# Open-source preparation

The owner chose independent development and the MIT license on 2026-10-28. This choice authorizes preparing the project for reuse; this document is not a claim that the new source has already been published or that a migration has occurred.

Completed locally:

- Original code has a root MIT license; third-party artwork and dependencies have separate notices.
- The standalone application has a generic Compose target, an example configuration and no runtime LubeLogger dependency.
- Personal attachments, runtime databases, backup files, local environment files and development environments are ignored. An ignore rule does not remove any previously tracked file or its history.
- The initial limited history/pattern review found no credential matches in the inspected planning commits. This is not a guarantee about all future staged content.

Before a public source release, review the actual staged snapshot and its history. Historical deployment notes need anonymization; originals can be retained in ignored private operational files. Inspect filenames, screenshots and document contents as well as token patterns. Do not include personal data merely because a scanner did not find a secret.

The project is an early alpha: describe supported flows accurately, preserve third-party notices, and include installation, authentication-boundary, backup and restore instructions. Publishing a repository does not make an unfinished release production-ready. Productive LubeLogger data, private configuration and a future cutover remain separate from the public source.

## Container release preparation

`deploy/compose.release.yaml` and the [container release plan](container-releases.md) prepare a pinned-image install path. No GHCR image has been published by this change; source-build Compose remains the supported installation method. The release policy requires a deliberately public GHCR package before anonymous pulls are documented.

The local Compose files validated, and an isolated same-volume switch smoke check passed using an already available local image. The pinned Python base manifest has `amd64` and `arm64` variants, but the application image has not yet been built or published as a multi-platform image. No release or package has been published; see the container plan for the full test evidence.

Before publishing a GitHub Release, complete this review against the exact release commit:

- Review source and history, dependency/artwork notices, changelog, screenshots and build context for secrets, personal data and license issues.
- Confirm the strict `v<application-version>` tag points to a commit on `main`; run tests and build the image from that same source SHA.
- Verify both intended Linux architectures (`amd64` and `arm64`), health behavior, non-root operation and the hardened Compose runtime settings.
- Verify schema upgrade and restore behavior with fresh isolated copies. Keep pre-upgrade backups and never test rollback by starting an old image against a schema-3 database.
- Publish only on an explicit release-published event. Manual workflow dispatch must be build-only with no registry push permission.
- Publish an exact version tag, avoid `latest`, record the manifest digest, and separately set GHCR package visibility before documenting public pulls.
- Recheck all docs and links, and ensure no production deployment or LubeLogger migration is coupled to artifact publishing.
