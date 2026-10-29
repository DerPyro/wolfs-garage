# ADR-0012: Release and update channels

- **Status:** Proposed
- **Date:** 2026-10-29
- **Decision makers:** Project owner

## Context

The private reference installation follows a tested-main updater under a standing, installation-specific authorization. Community self-hosters need a predictable way to select a release and roll back to a known image. A single implicit channel could couple the private deployment cadence to public releases or make an alpha image appear generally available before it is published.

## Options

1. **One versioned release channel:** all installations use explicitly published, versioned images pinned by tag or digest. This is simple to explain, but would change the private reference installation's existing tested-main workflow.
2. **Separate channels:** retain the private tested-main updater for the reference installation and provide versioned, explicitly published images for self-hosters. This needs clear documentation and independent checks for both paths.

## Proposal

Prefer separate channels. Keep the private reference updater and its access boundary installation-specific. For self-hosters, publish only from an explicitly published release, use an exact version tag with no moving `latest` alias, and record the immutable image manifest digest and source commit. A tag is a selector, not a guarantee that a registry tag can never be replaced; operators should retain the digest they deployed.

Updates should check the candidate against the live schema, preserve an off-host SQLite backup and previous compatible image, and validate health after start. Schema upgrades remain explicit and rehearsed separately. Rollback across a schema change uses a separate compatible database copy. These requirements do not make an unpublished image available or authorize a deployment.

## Consequences and open decision

The source-build Compose path remains available. The prepared release-image path does not imply a published registry image. The project owner must accept or revise this channel proposal before treating it as the release policy. See the [backup/update workflow](../planning/backup-update-workflow.md) for current safe operations.
