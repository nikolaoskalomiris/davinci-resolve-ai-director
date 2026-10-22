# Direct source-build authority

This directory defines the build and provenance authority for the pinned Direct llama.cpp lane. It does not contain or consume prebuilt Direct server binaries.

## Source authority

Direct is built from `nikolaoskalomiris/llama-cpp-flashnext-direct`. The build contract pins an immutable commit and Git tree; public builds must use those immutable identities rather than a mutable branch name.

The currently pinned source identities are recorded in the build contract and [release provenance](../../docs/release/RELEASE_PROVENANCE.md).

## Build

`build_direct.py` consumes a clean Git checkout, verifies the exact commit/tree and pinned Windows/CUDA toolchain, configures the contracted Ninja Release recipe, builds from source and emits the allowlisted Direct shipping files.

Historical accepted hashes are release/provenance references only. A source build is not accepted merely because its hashes match or differ from historical artifacts.

## Ownership boundary

Direct is fixed product-owned runtime content. Ordinary Upstream updates own only the Upstream runtime lane; they must not modify Direct or shared CUDA.

See `../../provenance/direct/AI-Director-Direct-Provenance-v1.json` for the bound provenance record.
