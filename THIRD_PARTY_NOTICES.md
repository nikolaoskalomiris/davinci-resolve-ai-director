# Third-Party Components and Notices

AI Director's Apache-2.0 license applies only to first-party project source/documentation unless a file says otherwise. Third-party components retain their upstream licenses and notices.

This file is a high-level inventory, not a substitute for the exact license/NOTICE files distributed with dependencies.

## Electron 36.3.2

- Role: desktop runtime.
- Upstream: `electron/electron`.
- License: MIT for Electron; packaged Electron distributions also contain Chromium, Node.js and additional third-party notices that must remain with the distributed runtime.

## electron-builder 26.15.3

- Role: build/packaging tool.
- Upstream: `electron-userland/electron-builder`.
- License: MIT.
- Bundled helper/tool artifacts retain their own upstream licenses.

## llama.cpp / ggml-derived runtimes

- Role: local LLM inference / `llama-server`.
- Base upstream: `ggml-org/llama.cpp`.
- Upstream runtime source authority: `unslothai/llama.cpp`.
- Direct runtime source authority: `nikolaoskalomiris/llama-cpp-flashnext-direct`.
- License: MIT at the accepted Direct source and current llama.cpp upstream line.

Accepted first-release source identities:

```text
Direct commit: c8f321699adbd0035c8c755bdefcb4182705262b
Direct tree:   a17cf64683bc6877e2dbc4e0b4ef8933106257fb
Upstream tree: edd784f1d459cd39f2605ccf66adc0c79ef75a93
Upstream id:   b7eb4a03a1285c50ebe86c6bd2fc7a70c6f7214d
```

Preserve original upstream copyright and license notices. The existence of a project-maintained Direct fork does not transfer authorship of third-party llama.cpp/ggml source to AI Director.

## davinci-resolve-mcp

- Role: local DaVinci Resolve MCP/scripting integration runtime.
- Upstream: `samuelgursky/davinci-resolve-mcp`.
- License: MIT.
- Accepted bundled seed: version `4.10.4`, commit `8911bd24aee76894238924317a461005dd013d94`.
- AI Director may apply a version- and SHA-256-guarded downstream compatibility overlay to its managed local copy of MCP. This does not change upstream authorship or licensing. Unknown or changed MCP source is review-required rather than patched blindly.

The shipping runtime contains dependency license files; those notices must remain intact.

## NVIDIA CUDA 13.3.1 redistributables

- Role: GPU acceleration for the accepted CUDA runtime line.
- License: NVIDIA CUDA Toolkit EULA / SDK software license terms, **not Apache-2.0**.
- Current shared payload includes:
  - `cudart64_13.dll`;
  - `cublas64_13.dll`;
  - `cublasLt64_13.dll`.

NVIDIA's CUDA EULA identifies the CUDA Runtime and cuBLAS/cuBLASLt runtime libraries among redistributable CUDA components subject to its terms. These proprietary redistributables must not be represented as open-source project code.

Reference: `https://docs.nvidia.com/cuda/eula/`

## FFmpeg

- Role: optional media operations through an externally configured `ffmpeg.exe` / `ffprobe.exe` pair.
- AI Director does not bundle FFmpeg in its managed runtime.
- Upstream: `https://ffmpeg.org/`.
- Licensing: FFmpeg states that it is normally LGPL 2.1-or-later, while enabling certain optional GPL-covered parts makes the resulting build GPL 2-or-later.

Reference: `https://ffmpeg.org/legal.html`

## DaVinci Resolve / Blackmagic Design

AI Director integrates with DaVinci Resolve but does not grant rights to DaVinci Resolve itself. DaVinci Resolve, its scripting interfaces, trademarks and vendor software remain subject to Blackmagic Design's terms.

## Runtime dependency notices

The accepted runtime base contains a large dependency tree and preserves dependency `LICENSE`, `COPYING`, `NOTICE` and related files in its shipping inventory. Public releases must keep those notices and must not replace them with this summary.
