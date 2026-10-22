# Installation

## Release authority

Install AI Director only from the project's official GitHub Release assets. A copied installer, development mirror or engineering build is not public release authority unless its SHA-256 matches an explicitly published release checksum.

The release produces two Windows x64 installers:

1. `DaVinci Resolve AI Director Setup <version>.exe` — the standalone current-user application and managed runtime.
2. `DaVinci Resolve AI Director Integration Setup <version>.exe` — the separate machine-scoped DaVinci Resolve Workflow Integration launcher.

The main Setup embeds the exact same Resolve Integration installer and can launch it for you when the integration option is selected.

## Before installing

You need:

- Windows x64;
- an NVIDIA GPU supported by the current runtime contract;
- an NVIDIA driver with major version 580 or newer under the current CUDA 13 compatibility policy;
- enough system RAM, VRAM and free storage for the local model you intend to use;
- DaVinci Resolve if you want Resolve automation;
- at least one local GGUF model in a supported model directory;
- an external FFmpeg/FFprobe pair if you want FFmpeg-backed media operations.

AI Director does not require the LM Studio application itself. See [MODELS.md](MODELS.md).

## Verify the installer first

Every public release should publish SHA-256 checksums for the distributed assets. Verify the file before running it:

```powershell
Get-FileHash -LiteralPath '.\DaVinci Resolve AI Director Setup X.Y.Z.exe' -Algorithm SHA256
```

Compare the result with the checksum published for that exact release asset. See [../release/RELEASE_VERIFICATION.md](../release/RELEASE_VERIFICATION.md).

## Unsigned releases and SmartScreen

Trusted Authenticode signing is desirable but is not allowed to block engineering or the first public release. If a release is explicitly labeled **unsigned**, Windows SmartScreen may show **Windows protected your PC** or another unknown-publisher warning. A self-signed development certificate does not make an installer Windows-trusted.

Do not bypass a warning until you have confirmed that:

- the file came from the official GitHub Release;
- the SHA-256 matches the published checksum; and
- the release notes explicitly say the artifact is unsigned when applicable.

Enterprise policy may prevent users from running unsigned or low-reputation binaries even when the user trusts the file.

## Upgrading from an earlier AI Director version

For the first public release line, **do not rely on an in-place/dirty upgrade**.

The supported procedure is:

1. Quit AI Director.
2. Quit DaVinci Resolve.
3. Uninstall **DaVinci Resolve AI Director** through Windows installed-app controls.
4. If **DaVinci Resolve AI Director Integration** is installed, uninstall that separate machine-scoped component too.
5. Run the new `DaVinci Resolve AI Director Setup <version>.exe`.
6. Reinstall/enable Resolve Integration from the new release when wanted.
7. Start AI Director and re-check the selected runtime/model plus any external FFmpeg configuration.

This procedure is intentionally conservative. Engineering testing found that an in-place 0.3.24 -> 0.3.25 install could preserve previous backend/server files, producing a mixed-version installation. That result does not imply that the clean 0.3.25 product is defective; it means in-place upgrade is not yet a supported release contract.

Do not manually delete user settings/model files as part of a normal upgrade unless a troubleshooting procedure explicitly calls for it.

## Main Setup

Run:

`DaVinci Resolve AI Director Setup <version>.exe`

The current installer is a per-user application install and does not offer an installation-directory chooser.

The assisted options page includes two default-checked choices:

- **Add AI Director launcher to DaVinci Resolve** / Resolve Workflow Integration;
- **Create a desktop shortcut**.

Installer details are visible and report the major installation stages.

### Resolve Integration elevation boundary

If the Resolve Integration option is selected, the main Setup launches the embedded Integration Setup through the Windows `runas` elevation path. The elevated child installer owns the machine-scoped Resolve Workflow Integration files and registration; the main current-user installer does not directly take ownership of that machine-scoped surface.

If you leave the option unchecked on a fresh install, only the standalone application is installed. Existing integration-preservation behavior is an implementation detail, not the supported first-release upgrade procedure; uninstall the previous Integration component before installing a newer AI Director release.

You can also install or repair the integration later by running the separate `DaVinci Resolve AI Director Integration Setup <version>.exe` artifact.

## First run

On first run, AI Director needs a runtime profile and a local model before it can start its managed server.

1. Open AI Director.
2. Choose **Direct** or **Upstream** under runtime/profile settings.
3. Select a detected local GGUF model.
4. Apply the settings and start the AI Director server.
5. If you use FFmpeg-backed features, configure an external `ffmpeg.exe` / `ffprobe.exe` pair in Settings.
6. If you installed Resolve Integration, restart DaVinci Resolve if it was open during installation, then launch AI Director from Resolve's Workflow Integration menu to confirm the launcher path.

See [RUNTIMES.md](RUNTIMES.md), [MODELS.md](MODELS.md), [FFMPEG.md](FFMPEG.md), and [RESOLVE_INTEGRATION.md](RESOLVE_INTEGRATION.md).

## Updates

AI Director manages Upstream llama.cpp-derived updates and DaVinci Resolve MCP updates as separate transactions. Update installation is integrity-checked and health-gated; failed candidates are rolled back when the required previous-state evidence is available.

Direct is not replaced by ordinary Upstream updates. See [UPDATER_AND_ROLLBACK.md](UPDATER_AND_ROLLBACK.md).

## Uninstalling

The standalone AI Director application and the machine-scoped Resolve Integration are separate ownership domains. Removing the standalone application is not a substitute for removing the Resolve Integration launcher, and the core installer is deliberately prevented from directly deleting the machine-scoped integration surface.

Use Windows installed-app/uninstall entries for the component you intend to remove. If the Resolve Integration remains installed after removing the core application, remove the separate **DaVinci Resolve AI Director Integration** entry as well.
