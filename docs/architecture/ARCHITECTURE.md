# Architecture

## Product split

DaVinci Resolve AI Director is a standalone Windows desktop application with separately managed runtime and Resolve-integration components.

### Standalone application

The Electron desktop application owns:

- the main UI and settings;
- local model discovery;
- Direct/Upstream runtime-profile selection;
- local llama-server orchestration;
- the managed Resolve MCP/backend process;
- updater transactions;
- optional external FFmpeg configuration.

It is installed per-user.

### Resolve Workflow Integration launcher

The Resolve Integration is a separate, machine-scoped launcher installed with elevation. It launches or foregrounds the standalone application from DaVinci Resolve.

It does not contain a second AI Director UI/runtime or an independent updater. See [../user/RESOLVE_INTEGRATION.md](../user/RESOLVE_INTEGRATION.md).

## Runtime layout

### Runtime base

`CUDA13-Native-Base-v3` contains the managed backend/MCP support tree and the pinned davinci-resolve-mcp seed. It is a release/runtime input, not first-party application source.

The current runtime base binds davinci-resolve-mcp seed version `4.10.4` / commit `8911bd24aee76894238924317a461005dd013d94` and a 15,720-file shipping inventory.

### Runtime stack

`CUDA13.3.1-Dual-Shared-v2` defines:

- shared CUDA 13.3.1 redistributable DLLs;
- the pinned Direct runtime lane;
- the Upstream runtime lane.

For clean source builds, the shared CUDA DLLs are extracted from pinned official NVIDIA redistributable archives. The machine CUDA Toolkit is an external compiler/inspection prerequisite and is not the shipping-runtime source.

Direct and Upstream have separate source authorities and ownership rules. See [../user/RUNTIMES.md](../user/RUNTIMES.md).

## Build-time architecture

The release build no longer treats the historical accepted runtime-stack archive as the normal source of server payloads.

The build path:

1. acquires the immutable Direct repository commit and verifies its Git tree;
2. downloads the authenticated Upstream source asset and reconstructs the accepted Upstream source tree;
3. builds Direct from source;
4. builds Upstream from source against the shared CUDA boundary;
5. assembles a new candidate runtime stack from shared CUDA plus those two source-built server shipping sets;
6. archives and extracts the new runtime stack and verifies tree parity;
7. builds the application, Resolve Integration installer and main installer;
8. performs static/PE/source-parity acceptance checks and writes build/provenance reports.

The accepted historical runtime-stack archive remains comparison/release authority only; the candidate build records that it was **not consumed** as the normal server-payload input.

## Installed-product update boundaries

- **Upstream llama.cpp:** independently transactional; does not require Resolve to be open, although a read-only Resolve canary runs when available.
- **DaVinci Resolve MCP:** separate transaction; Resolve must be available for the mandatory live canary before commit. Dependency-changing candidates are refused before mutation unless a matching validated compatibility bundle/runtime image is available.
- **Direct:** fixed product runtime lane; not changed by ordinary Upstream updates.
- **Shared CUDA:** separate immutable runtime lane for ordinary updater purposes.

See [../user/UPDATER_AND_ROLLBACK.md](../user/UPDATER_AND_ROLLBACK.md).

## Public-source boundary

The public source repository is a curated reproducibility projection, not a dump of an engineering machine.

It should contain first-party source/build controls, the Direct and Upstream source-build contracts, provenance, installer/branding source and public documentation. It should not contain local toolchain caches, release candidates, generated installers/server binaries, models, `node_modules`, credentials, installed-user state, continuity files or historical forensic workspaces.

See [../build/PUBLIC_SOURCE_BOUNDARY.md](../build/PUBLIC_SOURCE_BOUNDARY.md).
