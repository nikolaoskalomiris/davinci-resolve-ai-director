# Upstream source-build authority

This directory is the canonical AI Director build/provenance authority for the
updateable Upstream llama.cpp lane. It does not contain or consume prebuilt
Upstream server binaries.

## Source reconstruction

`reconstruct_source.py` consumes the authenticated public Unsloth source release
asset bound by `AI-Director-Upstream-Source-Build-Contract-v2.json`, applies the
18 packaging-metadata normalization leaves stored under `normalization/`, and
verifies the resulting 3,656-leaf source tree against
`AI-Director-Upstream-Source-Tree-Manifest-v1.json`. The expected accepted source
tree is `edd784f1d459cd39f2605ccf66adc0c79ef75a93`.

## Build

`build_upstream.py` accepts a VCS-free reconstructed source root, an explicit
shared-CUDA staging root, and an output root. The source-build contract pins the
Windows toolchain and CMake policy. Network access is blocked during configure
and build. The generated candidate contains the 17 shipping PE files plus the
contract-generated `UNSLOTH_PREBUILT_INFO.json` marker.

The shared CUDA root is an explicit build-stage input and must contain the
product-owned CUDA 13.3 runtime DLLs. Installed `%LOCALAPPDATA%` AI Director state
is not a normal build input.

## Ownership boundary

Ordinary Upstream updates own only `Upstream/Current`. Direct and the shared CUDA
runtime are outside that updater ownership boundary.

See `../../provenance/upstream/AI-Director-Upstream-Provenance-v1.json` for the
accepted source/build/product-test evidence bindings.
