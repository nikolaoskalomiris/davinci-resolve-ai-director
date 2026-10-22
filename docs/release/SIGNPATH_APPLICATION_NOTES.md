# SignPath Foundation Application Notes

Status: preparation notes only. Acceptance is external and non-blocking.

## Project

- Name: DaVinci Resolve AI Director
- Platform: Windows x64
- Intended public repository license: Apache-2.0 for first-party source/documentation
- Build/distribution: Electron desktop application plus NSIS installers
- Signing scope: first-party application EXE and two first-party installers only

## Third-party/upstream components that should be disclosed

### Electron

Electron `36.3.2`, MIT plus bundled Chromium/Node third-party notices.

### llama.cpp-derived runtime

Pinned llama.cpp/ggml-derived local inference binaries. Upstream is MIT-licensed; accepted runtime tracks both a direct pinned source and an Unsloth-maintained upstream/current line.

### davinci-resolve-mcp

Accepted seed `4.10.4`, commit `8911bd24aee76894238924317a461005dd013d94`, MIT license.

### NVIDIA CUDA

The installer/runtime payload includes NVIDIA CUDA 13.3.1 redistributable DLLs:

- `cudart64_13.dll`
- `cublas64_13.dll`
- `cublasLt64_13.dll`

They are distributed under NVIDIA's CUDA EULA, not the project's Apache-2.0 license, and are installed in an AI Director-specific runtime location. NVIDIA's current CUDA EULA lists CUDA Runtime and cuBLAS/cuBLASLt runtime libraries as redistributable components subject to its terms.

**Eligibility question for SignPath:** whether these proprietary but vendor-authorized runtime redistributables are acceptable under SignPath Foundation's OSS-project restrictions / System Library exception. Do not conceal or assume the answer.

### FFmpeg

Not bundled in the managed AI Director runtime. Users configure an external FFmpeg/FFprobe installation if they want FFmpeg-dependent features.

## Non-blocking policy

Do not pause Gate 5/6 engineering while the application is reviewed. If SignPath is still unavailable when all other release gates are complete, an unsigned release requires an explicit maintainer decision and clear SmartScreen/checksum disclosure.

## PE metadata identity prepared before signing

The unsigned Windows artifacts use `DaVinci Resolve AI Director` as the stable project-publisher `CompanyName` and installer Publisher, while the product name remains `DaVinci Resolve AI Director`. This metadata identity is intentionally separate from the future Authenticode certificate subject. Under the free SignPath Foundation certificate path, the certificate is issued to SignPath Foundation; the signing configuration must therefore be derived from the actual certificate subject rather than guessed from the PE `CompanyName`.

The Builder statically verifies the first-party application, main Setup, and AI Director Integration Setup metadata before a release candidate is committed. Signing remains a later transformation that preserves the deterministic unsigned SHA-256 as provenance.
