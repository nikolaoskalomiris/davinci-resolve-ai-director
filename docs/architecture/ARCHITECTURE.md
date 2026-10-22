# Architecture

## Product split

DaVinci Resolve AI Director is a standalone Windows desktop application with separately managed local runtimes and an optional DaVinci Resolve launcher.

### Desktop application

The per-user Electron application owns:

- the UI and settings;
- local model discovery;
- Direct/Upstream runtime selection;
- local llama-server orchestration;
- the managed Resolve MCP/backend process;
- runtime update transactions;
- optional external FFmpeg configuration.

### Resolve Workflow Integration

Resolve Integration is a small machine-scoped launcher installed with elevation. It starts or foregrounds the standalone application from DaVinci Resolve; it does not contain a second application, model server or updater.

See [Resolve Integration](../user/RESOLVE_INTEGRATION.md).

## Runtime layout

AI Director manages three runtime concerns:

- **Direct** — the pinned product llama.cpp-derived runtime;
- **Upstream** — the independently updateable llama.cpp-derived runtime;
- **Shared CUDA** — the product-owned NVIDIA runtime libraries used by both lanes.

The managed backend/MCP runtime is maintained separately from the two model-server lanes.

For source builds, Direct and Upstream are constructed from pinned source authorities. Shipping CUDA DLLs come from pinned official NVIDIA redistributable archives; the machine CUDA Toolkit is a compiler/inspection prerequisite, not the shipping-runtime source.

See [Direct and Upstream Runtimes](../user/RUNTIMES.md) and [Release Provenance](../release/RELEASE_PROVENANCE.md).

## Installed update boundaries

- **Upstream:** staged and validated independently; ordinary updates do not replace Direct or shared CUDA.
- **MCP:** updated through a separate transaction and requires a live read-only Resolve canary before commit.
- **Direct:** fixed product runtime lane.
- **Shared CUDA:** outside ordinary Upstream/MCP updater ownership.

See [Updater and Rollback](../user/UPDATER_AND_ROLLBACK.md).

## Build-time architecture

The release build:

1. acquires and verifies the pinned Direct source;
2. reconstructs and verifies the pinned Upstream source;
3. builds both server lanes from source;
4. assembles them with the shared CUDA runtime;
5. packages the desktop application and Resolve Integration;
6. emits build/provenance evidence.

Historical runtime binaries are comparison/provenance evidence, not normal clean-build inputs.

## Public-source boundary

The public repository contains the source, build controls, contracts, provenance and documentation needed to understand and reproduce the product. Generated toolchains, caches, installers, models, credentials, installed-user state and private engineering workspaces are excluded.

See [Public Source Boundary](../build/PUBLIC_SOURCE_BOUNDARY.md).
