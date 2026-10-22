# Security Policy

## Supported releases

Use the project's [GitHub Releases](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/releases/latest) page to identify the current public release. Security fixes and support status should be communicated through release notes and GitHub security advisories rather than hardcoded into this file.

## Reporting a vulnerability

Prefer GitHub's **private vulnerability reporting / Security Advisory** feature when available. Do not publish exploit details in a normal issue before coordinated disclosure.

If private reporting is unavailable, open a non-sensitive issue requesting a private contact path without including exploit details, credentials, tokens, private project data or working proof-of-concept code.

A useful report includes:

- affected AI Director version;
- Windows and DaVinci Resolve versions;
- whether Resolve Integration is installed;
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
- update/download paths for managed components;
- source-build bootstrap/download paths;
- optional external FFmpeg/FFprobe configured by the user.

The Resolve Integration launcher is separate from the current-user desktop application and requires elevation for its machine-scoped installation.

## Release verification

Release assets are accompanied by checksums and provenance information. See [docs/release/RELEASE_VERIFICATION.md](docs/release/RELEASE_VERIFICATION.md).

A release may be unsigned when the maintainer explicitly states that status. A self-signed development certificate must not be presented as Windows-trusted production signing.
