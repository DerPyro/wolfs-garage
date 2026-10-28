# Open-source preparation

The owner chose independent development and the MIT license on 2026-10-28. This choice authorizes preparing the project for reuse; this document is not a claim that the new source has already been published or that a migration has occurred.

Completed locally:

- Original code has a root MIT license; third-party artwork and dependencies have separate notices.
- The standalone application has a generic Compose target, an example configuration and no runtime LubeLogger dependency.
- Personal attachments, runtime databases, backup files, local environment files and development environments are ignored. An ignore rule does not remove any previously tracked file or its history.
- The initial limited history/pattern review found no credential matches in the inspected planning commits. This is not a guarantee about all future staged content.

Before a public source release, review the actual staged snapshot and its history. Historical deployment notes need anonymization; originals can be retained in ignored private operational files. Inspect filenames, screenshots and document contents as well as token patterns. Do not include personal data merely because a scanner did not find a secret.

The project is an early alpha: describe supported flows accurately, preserve third-party notices, and include installation, authentication-boundary, backup and restore instructions. Publishing a repository does not make an unfinished release production-ready. Productive LubeLogger data, private configuration and a future cutover remain separate from the public source.
