# Public Source Boundary

The public repository is a curated source/reproducibility projection, not a dump of an engineering Builder machine.

## Publish as project/reproducibility source

Publish the material required to understand, audit and reproduce the product, including:

- first-party application/backend/Resolve-integration source;
- `BUILD.cmd` and public bootstrap controls;
- `build/direct/` and `build/upstream/` source-build contracts/tools;
- `provenance/direct/`, `provenance/upstream/`, runtime/third-party provenance;
- installer scripts/policies;
- branding source needed to reproduce first-party assets;
- repository documentation and contribution/security/privacy policy;
- hash-bound descriptors/manifests for binary inputs that are acquired separately.

## Do not publish as project source

Do not commit or present these as first-party source:

- `_toolchain/` caches or locally owned toolchain archives;
- generated release candidates, installers or server binaries;
- accepted/historical runtime `.7z` archives as source;
- operation caches and transaction journals;
- `node_modules`, transient `dist`/`out`, local logs;
- models, media, user settings, local databases or Resolve project data;
- credentials, signing certificates/private keys or tokens;
- continuity files or historical forensic workspaces.

## Third-party material

The repository's Apache-2.0 license does not relicense third-party source or binary components.

Preserve original upstream license/provenance, especially for llama.cpp/ggml-derived source, davinci-resolve-mcp dependencies and NVIDIA CUDA redistributables. Never imply AI Director authorship of third-party source.

## Binary acquisition

Required binary/bootstrap inputs must be acquired through explicit, versioned, hash-bound contracts. A binary may be a legitimate reproducibility input without being first-party open-source code.

The clean public build must fail closed when an expected input cannot be fetched or its size/hash/identity does not match.
