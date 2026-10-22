# DaVinci Resolve AI Director

DaVinci Resolve AI Director is a Windows desktop companion for DaVinci Resolve built around local LLM inference, a standalone Electron interface, and controlled Resolve automation through a managed MCP/scripting runtime.

AI Director is **local-first**: the normal model-inference path runs on the user's machine through bundled llama.cpp-derived runtime components. It does not require a paid hosted inference subscription or tie the user to one cloud model vendor.

> **Release status:** engineering authority **0.3.25** is accepted in the repository. Official public binaries are distributed only through this repository's GitHub Releases. Until the first GitHub Release is published, development mirrors and copied installers are not public release authority.

## Supported platform

The current runtime contract targets:

| Area | Current requirement |
| --- | --- |
| OS | Windows x64 |
| GPU | NVIDIA GPU on one of the supported compute-capability targets: 7.5, 8.0, 8.6, 8.9, 9.0, 12.0 or 12.1 |
| NVIDIA driver | Major version 580 or newer under the current CUDA 13 compatibility policy |
| Runtime line | CUDA 13.3.1 |
| DaVinci Resolve | Required for Resolve automation; the desktop application itself is a separate standalone application |
| Model format | Local GGUF models discovered from the supported model directories |
| FFmpeg | External and optional for application startup, but required for FFmpeg-backed media operations and the full offline feature set |

RAM, VRAM and storage needs vary substantially with model size, quantization and context length. This project does not publish a single universal RAM/VRAM minimum that would be valid for every supported local model.

## What it includes

- a standalone current-user Electron desktop application;
- local GGUF model discovery and local llama.cpp-derived inference;
- two runtime profiles: **Direct** and **Upstream**;
- a managed DaVinci Resolve MCP/backend runtime;
- an optional, separately elevated Resolve Workflow Integration launcher;
- transactional Upstream and MCP update flows with integrity checks, live health validation and rollback;
- optional external FFmpeg/FFprobe integration.

## Installation

The main release artifact is named:

`DaVinci Resolve AI Director Setup <version>.exe`

The main installer presents assisted options for the Resolve Workflow Integration launcher and a desktop shortcut. The Resolve Integration option is enabled by default; if selected, Windows prompts for elevation only when the separate machine-scoped integration installer runs. The core AI Director application remains a current-user install.

A separate artifact is also produced for the Resolve launcher:

`DaVinci Resolve AI Director Integration Setup <version>.exe`

**Supported upgrade procedure for the first public release line:** uninstall the previous AI Director application before installing a newer release. If the Resolve Integration is installed, uninstall its separate Windows entry as well and reinstall it from the new release. In-place/dirty upgrade is not currently a supported release path because it has not proven reliable replacement of all managed runtime/backend files.

Read [docs/user/INSTALLATION.md](docs/user/INSTALLATION.md) before installing, especially if the release is unsigned.

## Local models

AI Director scans these LM Studio-compatible model roots recursively:

- `%USERPROFILE%\.lmstudio\models`
- `%USERPROFILE%\.cache\lm-studio\models`

The LM Studio application is not required to run AI Director. If the `lms` CLI is available, AI Director can use its catalog metadata; otherwise it falls back to filesystem discovery.

AI Director currently recognizes dedicated recipes for Qwen3.8 Flash Next and Qwen3.6-35B-A3B and can expose other GGUF files as unvalidated generic models. Detection does not guarantee that an arbitrary GGUF will work correctly. See [docs/user/MODELS.md](docs/user/MODELS.md).

## FFmpeg

FFmpeg is **not bundled** with AI Director's managed runtime. Settings can point to an existing `ffmpeg.exe` / `ffprobe.exe` pair from the same directory, and AI Director validates the pair before enabling it. The application can also open the project-selected external FFmpeg download page.

See [docs/user/FFMPEG.md](docs/user/FFMPEG.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Direct and Upstream runtimes

**Direct** is the pinned product runtime lane. **Upstream** is the independently updateable llama.cpp-derived lane. Ordinary Upstream updates do not replace Direct or the shared CUDA runtime.

The installed-product updater is separate from the source-build path. A source build constructs both Direct and Upstream server payloads from pinned source authorities; it does not use historical prebuilt Direct/Upstream server binaries as normal build inputs.

See [docs/user/RUNTIMES.md](docs/user/RUNTIMES.md) and [docs/user/UPDATER_AND_ROLLBACK.md](docs/user/UPDATER_AND_ROLLBACK.md).

## MCP update compatibility

The accepted first-release runtime base contains davinci-resolve-mcp `4.10.4`. MCP updates are fail-closed: if a candidate changes the validated dependency/runtime contract, AI Director keeps the accepted MCP active and refuses replacement unless a matching validated compatibility bundle/runtime image is available.

That behavior is intentional. A blocked dependency-changing update is not itself evidence that the installed product is unhealthy. See [docs/user/UPDATER_AND_ROLLBACK.md](docs/user/UPDATER_AND_ROLLBACK.md).

## Build from source

The accepted 0.3.25 public-source build path bootstraps its project-owned tools and downloaded inputs, validates the external Windows compiler/toolkit prerequisites, builds both Direct and Upstream from pinned source authorities, and constructs a fresh candidate runtime stack.

The shipping CUDA runtime DLLs come from pinned official NVIDIA CUDA 13.3.1 redistributable archives. The machine CUDA Toolkit remains an external compiler/inspection prerequisite and is **not** the shipping CUDA payload source.

The final release reproducibility gate is still a literal fresh checkout of the published/tagged repository followed by plain `BUILD.cmd` with no pre-existing generated inputs/toolchain, private credentials, installed-product dependency, or continuity state.

See [docs/build/BUILDING.md](docs/build/BUILDING.md).

## Documentation

- [Installation](docs/user/INSTALLATION.md)
- [Models](docs/user/MODELS.md)
- [FFmpeg](docs/user/FFMPEG.md)
- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Direct and Upstream runtimes](docs/user/RUNTIMES.md)
- [Updater and rollback](docs/user/UPDATER_AND_ROLLBACK.md)
- [Resolve Integration](docs/user/RESOLVE_INTEGRATION.md)
- [Troubleshooting](docs/user/TROUBLESHOOTING.md)
- [Build from source](docs/build/BUILDING.md)
- [Public-source boundary](docs/build/PUBLIC_SOURCE_BOUNDARY.md)
- [Release provenance](docs/release/RELEASE_PROVENANCE.md)
- [Release verification](docs/release/RELEASE_VERIFICATION.md)
- [Post-first-release TODO](TODO.md)

## Privacy, security and licensing

AI Director is designed for local operation and the accepted source contains no third-party advertising or product-analytics telemetry upload endpoint. Update checks and managed dependency updates do use external network services. See [PRIVACY.md](PRIVACY.md).

Security reporting and release-verification guidance are in [SECURITY.md](SECURITY.md). First-party source and documentation are Apache-2.0 unless a file says otherwise; third-party components retain their own licenses and notices. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

DaVinci Resolve is a product/trademark of Blackmagic Design Pty Ltd. NVIDIA and CUDA are trademarks of NVIDIA Corporation. This project is not presented as an official Blackmagic Design or NVIDIA product.
