# Troubleshooting

## Windows SmartScreen blocks the installer

Confirm that the installer came from the official [GitHub Releases](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/releases/latest) page and check the release's signing status.

If needed, verify its checksum as described in [Release Verification](../release/RELEASE_VERIFICATION.md).

Enterprise Windows policy may prevent unsigned or low-reputation applications from running even when the file is legitimate.

## No local models appear

AI Director scans:

```text
%USERPROFILE%\.lmstudio\models
%USERPROFILE%\.cache\lm-studio\models
```

Check that your primary model is a `.gguf` file. Auxiliary draft/MTP/mmproj files and non-primary multipart pieces are not listed as separate primary models.

For Qwen3.8 Flash Next, keep the compatible MTP draft GGUF beside the primary model.

See [Local Models](MODELS.md).

## AI Director says setup is required

Open Settings and select:

1. a runtime profile (**Direct** or **Upstream**);
2. an available local model.

Apply the settings, then start the server.

## FFmpeg is unavailable

Select `ffmpeg.exe` and `ffprobe.exe` from the same compatible FFmpeg installation, or leave FFmpeg disabled if you do not need FFmpeg-backed operations.

See [FFmpeg](FFMPEG.md).

## Port 8091 is already in use

Do not terminate processes blindly.

If AI Director already has a managed server running, use the application's normal stop/restart controls. If another application owns the port, stop or reconfigure that application before retrying.

## An Upstream update was rejected

A rejected candidate can be a successful safety outcome. AI Director stages and health-checks the candidate before finalizing it.

If rollback succeeds, the previous runtime remains active. Preserve the reported error instead of manually deleting update or backup directories.

If rollback itself fails, stop further update attempts until the installed runtime state is inspected.

See [Updater and Rollback](UPDATER_AND_ROLLBACK.md).

## An MCP update says Resolve must be open

Open DaVinci Resolve and retry.

MCP updates require a live read-only Resolve check before the new MCP runtime can be committed.

## An MCP update reports a compatibility/dependency change

This can be an intentional fail-closed refusal. AI Director keeps the accepted MCP active when the candidate requires a dependency/runtime image that has not been validated yet.

Do not manually overwrite the accepted MCP or bypass the compatibility checks. Wait for an AI Director release/update that provides a matching compatibility bundle.

## Resolve Integration does not launch AI Director

1. Confirm the standalone AI Director application is installed for the current Windows user.
2. Restart DaVinci Resolve.
3. Repair/reinstall Resolve Integration from the current release if needed.

See [Resolve Integration](RESOLVE_INTEGRATION.md).

## Building from source

Build failures and maintainer toolchain diagnostics are documented separately in [Building from Source](../build/BUILDING.md).
