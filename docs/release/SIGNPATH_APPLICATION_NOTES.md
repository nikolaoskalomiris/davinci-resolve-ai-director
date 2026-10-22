# SignPath Foundation Application Notes

Status: planning notes for a future trusted signing path. SignPath acceptance is an external dependency and is not required for ordinary source development.

## Project

- Name: DaVinci Resolve AI Director
- Platform: Windows x64
- Public repository license: Apache-2.0 for first-party source/documentation
- Build/distribution: Electron desktop application plus NSIS installers
- Intended signing scope: first-party application executable and first-party installers only

## Third-party components to disclose

### Electron

Electron is MIT-licensed and its packaged distributions include Chromium, Node.js and additional third-party notices.

### llama.cpp-derived runtime

Local inference binaries are derived from pinned llama.cpp/ggml source authorities. Upstream source remains under its own license and authorship.

### davinci-resolve-mcp

The managed Resolve MCP runtime is third-party MIT-licensed software and must retain its upstream notices.

### NVIDIA CUDA

The installed runtime includes NVIDIA CUDA redistributable DLLs such as `cudart`, `cublas` and `cublasLt`. They are distributed under NVIDIA's CUDA terms, not the project's Apache-2.0 license.

**Eligibility question for SignPath:** confirm whether these vendor-authorized proprietary redistributables fit the Foundation program's project restrictions/exceptions. Do not assume or conceal the answer.

### FFmpeg

FFmpeg is not bundled in the managed AI Director runtime. Users configure an external FFmpeg/FFprobe installation when needed.

## Signing policy

Do not stamp the AI Director project signature onto third-party runtime binaries.

If trusted signing is introduced, preserve the deterministic unsigned build hash and record the signed distribution hash separately. Signing configuration must be derived from the actual certificate subject rather than guessed from product metadata.

See [../../CODE_SIGNING_POLICY.md](../../CODE_SIGNING_POLICY.md) and [RELEASE_VERIFICATION.md](RELEASE_VERIFICATION.md).
