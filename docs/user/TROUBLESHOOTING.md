# Troubleshooting

## Installer is blocked by Windows SmartScreen

First determine whether the release is intentionally unsigned.

- Confirm you downloaded the file from the official GitHub Release.
- Verify its SHA-256 against the published checksum.
- Confirm the release notes explicitly identify the artifact as unsigned when applicable.

Unsigned and self-signed applications can receive SmartScreen warnings. Enterprise policy may prevent continuation. See [../release/RELEASE_VERIFICATION.md](../release/RELEASE_VERIFICATION.md).

## No local models appear

AI Director recursively scans:

```text
%USERPROFILE%\.lmstudio\models
%USERPROFILE%\.cache\lm-studio\models
```

Check that the primary model file ends in `.gguf`. Auxiliary MTP/draft/mmproj files are not shown as standalone primary models, and non-primary multipart pieces are not listed separately.

For Qwen3.8 Flash Next, make sure the compatible MTP draft GGUF is beside the primary model. See [MODELS.md](MODELS.md).

## FFmpeg shows unavailable or validation failed

The selected `ffmpeg.exe` and `ffprobe.exe` must:

- exist at absolute paths;
- be named exactly `ffmpeg.exe` and `ffprobe.exe`;
- come from the same directory;
- execute successfully;
- identify compatible versions;
- expose the capabilities AI Director requires.

Re-select the pair in Settings or disable FFmpeg if you do not need FFmpeg-backed operations. See [FFMPEG.md](FFMPEG.md).

## AI Director says setup is required

The server cannot start until a runtime profile and an available local model have been selected. Open Settings, choose Direct or Upstream, select a detected model and apply the settings.

## Port 8091 is already in use

Identify the listener before terminating anything. Do not assume a process is stale merely because it owns AI Director's usual local llama-server port.

If another AI Director-managed server is already running, use the application's normal stop/restart controls rather than killing unrelated processes.

## Upstream update was rejected

A rejected update can be a successful safety outcome. The Upstream transaction verifies release/asset identity, SHA-256, staged executable viability, local runtime identity and live server/backend/cache health before finalizing.

If the live-health gate fails and rollback succeeds, the previous runtime is restored and the candidate remains rejected. Preserve the error message; do not delete the backup/rejected runtime directories as a first response.

If rollback itself fails, stop update attempts until the runtime state is inspected. See [UPDATER_AND_ROLLBACK.md](UPDATER_AND_ROLLBACK.md).

## MCP update says Resolve must be open

This is expected for an installable MCP candidate. MCP updates can change the Resolve-facing tool contract, so the transaction requires a live read-only Resolve canary before commit.

Open DaVinci Resolve and retry the MCP update.

## MCP update says the dependency/runtime contract changed

This is also an expected safety outcome.

If the candidate's dependency/runtime semantics no longer match the accepted immutable dependency image, AI Director refuses the update before replacing accepted files. The accepted MCP remains active.

Do not manually copy the new MCP over the accepted installation and do not weaken the hash/lockfile checks. Wait for an AI Director compatibility bundle/runtime image that explicitly validates that MCP dependency contract.

## Resolve Integration is installed but does not launch AI Director

The integration is only a launcher. Confirm that the standalone AI Director application is installed for the current Windows user.

If the integration was installed or updated while Resolve was open, restart Resolve. If necessary, repair it with the separate `DaVinci Resolve AI Director Integration Setup <version>.exe` artifact.

See [RESOLVE_INTEGRATION.md](RESOLVE_INTEGRATION.md).

## Source build fails before compilation

For a maintained/source build, distinguish bootstrap failure from compiler failure.

Check:

- the Direct repository is reachable and the pinned commit/tree can be checked out;
- the Upstream source asset matches the contracted size/SHA-256;
- the exact external MSVC/Windows SDK/CMake/Ninja/CUDA Toolkit identities required by the build contracts are present;
- the runtime-base bootstrap asset and NVIDIA shared-CUDA redistributable archives are available and match their contracted SHA-256 values;
- no inherited `CL`, `_CL_`, `NVCC_PREPEND_FLAGS`, `NVCC_APPEND_FLAGS`, `CUDAARCHS` or `CMAKE_CUDA_ARCHITECTURES` contamination is changing the build environment.

Do not substitute historical server binaries when a source acquisition/build prerequisite fails.

## Builder health for maintainers

On a maintained repository, use the documented build/health entrypoints and preserve operation evidence after any failure. A fresh public-source build may legitimately start without `_inputs`, `_toolchain` or `_cache`; plain `BUILD.cmd` bootstraps the owned/downloaded inputs before compilation. Do not manually delete active transaction journals or candidate evidence merely to make a subsequent check pass.
