# Security Policy

## Supported release line

Before the first public release is published, the accepted engineering baseline is **0.3.25**. After public release authority exists, supported versions should be identified by the project's GitHub Releases/security advisories rather than by this pre-release engineering statement.

## Reporting a vulnerability

Prefer GitHub's **private vulnerability reporting / Security Advisory** feature once the public repository enables it. Do not publish exploit details in a normal issue before coordinated disclosure.

If private reporting is temporarily unavailable, open a non-sensitive issue requesting a private contact path without including exploit details, credentials, tokens, private project data or working proof-of-concept code.

A useful report includes:

- affected AI Director version/build;
- Windows and DaVinci Resolve versions;
- whether the Resolve Integration launcher is installed;
- selected Direct/Upstream runtime profile when relevant;
- exact reproduction steps;
- expected versus actual security impact;
- logs with secrets and personal data removed.

## Security boundaries

AI Director includes several distinct trust boundaries:

- Electron desktop application;
- local Direct and Upstream llama.cpp-derived runtimes;
- managed davinci-resolve-mcp runtime;
- DaVinci Resolve scripting/Workflow Integration launcher;
- update/download paths for supported managed components;
- source-build bootstrap/download paths;
- optional external FFmpeg/FFprobe configured by the user.

The Resolve Integration launcher is separate from the current-user desktop application and requires elevation for its machine-scoped installation.

## Release verification

Release assets must be accompanied by SHA-256 checksums and provenance. See [docs/release/RELEASE_VERIFICATION.md](docs/release/RELEASE_VERIFICATION.md).

Trusted Authenticode signing may be deferred. If a release is unsigned, it must be explicitly labeled unsigned. A self-signed development certificate must not be presented as Windows-trusted production signing.
