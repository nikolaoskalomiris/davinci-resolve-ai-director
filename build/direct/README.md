# Direct source-build authority

This directory is the canonical AI Director Builder build/provenance authority for the fixed Direct llama.cpp lane.
It does not contain or consume prebuilt Direct server binaries.

## Source authority

The source repository is `nikolaoskalomiris/llama-cpp-flashnext-direct`. The first-release accepted source baseline is immutable commit
`c8f321699adbd0035c8c755bdefcb4182705262b` with tree `a17cf64683bc6877e2dbc4e0b4ef8933106257fb`.
The separate repository maintenance head carries reproducibility tooling only; the Builder build controller requires an exact clean checkout of the accepted commit/tree.

Before public Gate 6D, the Direct repository must be publicly readable. Public builds must pin the immutable commit/tree, not a mutable branch name.

## Build

`build_direct.py` consumes a clean Git checkout, verifies the exact commit/tree and pinned Windows/CUDA toolchain, configures the evidence-corrected
Ninja Release recipe with UI provisioning disabled and `CMAKE_CUDA_ARCHITECTURES` unset, builds from source, and emits exactly the 17 allowlisted Direct shipping files.
Historical accepted hashes are recorded as release/provenance references; a source build is not promoted merely because hashes match or differ.

## Ownership boundary

Direct is fixed product-owned runtime content. The ordinary Upstream updater owns only `Upstream/Current`; it must not update Direct or shared CUDA.
See `../../provenance/direct/AI-Director-Direct-Provenance-v1.json` for the bound authority.
