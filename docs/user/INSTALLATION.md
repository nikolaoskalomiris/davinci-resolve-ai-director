# Installation

## Download

Download AI Director from the official [GitHub Releases](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/releases/latest) page.

The **main installer** installs the desktop application. Resolve Workflow Integration is optional: the main installer can install it for you, or you can use the separate Integration installer from the same release.

## Requirements

You need:

- Windows x64;
- a supported NVIDIA GPU (CUDA compute capability 7.5, 8.0, 8.6, 8.9, 9.0, 12.0 or 12.1);
- an NVIDIA driver with major version 580 or newer under the current CUDA compatibility policy;
- enough RAM, VRAM and storage for the local model you intend to use;
- at least one local GGUF model;
- DaVinci Resolve if you want Resolve automation;
- FFmpeg/FFprobe only if you want FFmpeg-backed media operations.

AI Director does not require the LM Studio application itself. See [Local Models](MODELS.md).

## Before running an installer

Check the signing status in the release notes. If Windows SmartScreen warns, confirm that the file came from the official release page.

For checksum verification:

```powershell
Get-FileHash -LiteralPath '.\your-downloaded-installer.exe' -Algorithm SHA256
```

Compare the result with the checksum published for that same release asset. See [Release Verification](../release/RELEASE_VERIFICATION.md).

## Install

1. Run the main AI Director installer.
2. Keep **Resolve Integration** enabled if you want to launch AI Director from DaVinci Resolve.
3. Keep or disable the desktop shortcut option as preferred.
4. If Resolve Integration is selected, approve the Windows elevation prompt for that component.
5. Start AI Director.

The desktop application is installed for the current Windows user. Resolve Integration is a separate machine-scoped component.

## Upgrading

> **Before installing a newer release, uninstall the existing AI Director application. If Resolve Integration is installed, uninstall that Windows entry too. Then install the new release and re-enable the integration if you use it.**

You do not need to manually delete model files or user settings during a normal upgrade.

## First run

1. Open AI Director.
2. Choose **Direct** or **Upstream**.
3. Select a detected local GGUF model.
4. Apply the settings and start the server.
5. Configure FFmpeg in Settings only if you need FFmpeg-backed features.
6. If you installed Resolve Integration while Resolve was open, restart Resolve before testing the Workflow Integration menu.

See [Runtimes](RUNTIMES.md), [Local Models](MODELS.md), [FFmpeg](FFMPEG.md) and [Resolve Integration](RESOLVE_INTEGRATION.md).

## Updates

Direct is the pinned product runtime. Upstream and MCP use separate managed update transactions with integrity checks and health validation.

See [Updater and Rollback](UPDATER_AND_ROLLBACK.md).

## Uninstall

The desktop application and Resolve Integration have separate Windows uninstall entries.

- Remove **DaVinci Resolve AI Director** to uninstall the desktop application.
- Remove **DaVinci Resolve AI Director Integration** to remove the Resolve launcher.

Uninstall both components to remove the desktop application and Resolve launcher.
