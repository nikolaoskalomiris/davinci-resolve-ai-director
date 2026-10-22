# Building from Source

AI Director's public build path is designed to start from a clean repository checkout and bootstrap the project-owned/downloaded inputs it needs. The Windows compiler/CUDA toolchain remains an external prerequisite.

## Quick start

From the repository root:

```powershell
.\BUILD.cmd
```

A normal build may create `_inputs`, `_toolchain` and `_cache`. These are generated local state and are intentionally not source-controlled.

A successful build does **not** install the product and does **not** automatically advance accepted release authority. Acceptance is a separate maintainer operation after installation and live testing.

## External prerequisites

The current build contracts require:

| Component | Contract |
| --- | --- |
| Platform | Windows x64 |
| Visual Studio | Visual Studio 2022 Build Tools |
| MSVC toolset | 14.44.35207 |
| Windows SDK | 10.0.26100.0 |
| CMake | 3.31.6-msvc6 from Visual Studio Build Tools |
| Ninja | 1.12.1 from Visual Studio Build Tools |
| CUDA Toolkit | 13.3 |
| nvcc | V13.3.73 |
| Git | Required for source acquisition |

The build contracts validate these tools strictly. They are not auto-installed by project bootstrap.

## What bootstrap manages

`bootstrap/bootstrap-inputs.json` is the authority for downloaded build inputs and their hashes. Bootstrap currently manages items such as:

- embeddable Python;
- Node/npm;
- Electron;
- NSIS and packaging helpers;
- official NVIDIA CUDA redistributable archives;
- the product runtime-base input.

Generated copies live under `_toolchain` and `_inputs`.

## Runtime build invariant

A clean release build constructs both model-server lanes from pinned source authorities:

- **Direct:** acquired as an exact clean Git commit/tree;
- **Upstream:** reconstructed from an authenticated source asset and verified source-tree manifest.

Historical accepted Direct/Upstream binaries and runtime-stack archives are comparison/provenance evidence only; they are not normal server build inputs.

Exact source identities are recorded in [Release Provenance](../release/RELEASE_PROVENANCE.md) and the versioned build contracts.

## Shared CUDA

Shipping CUDA runtime DLLs are extracted from pinned official NVIDIA redistributable archives. They are **not** copied from the machine CUDA Toolkit.

The installed CUDA Toolkit is used for compilation and inspection only.

## Build outputs

The release build produces:

- the AI Director Windows installer;
- the optional Resolve Integration installer;
- Direct, Upstream and runtime-stack build/provenance reports;
- a release-candidate workspace for subsequent validation.

The application is packaged with Electron/electron-builder and the build validates packaged application/source parity.

## Maintainer version lifecycle

Preparing a semantic version, building a candidate and accepting a tested candidate are separate operations.

Version preparation supports:

```powershell
.\BUILD.cmd --patch
.\BUILD.cmd --minor
.\BUILD.cmd --major
.\BUILD.cmd --version X.Y.Z
```

Do not use a version selector merely to rebuild an already prepared or accepted version.

Acceptance is explicit:

```powershell
.\BUILD.cmd --accept --candidate static-build-NNN --dry-run
.\BUILD.cmd --accept --candidate static-build-NNN
```

The apply path requires live attestation and writes promotion evidence. Plain `BUILD.cmd` never performs acceptance implicitly.

## Reproducibility verification

A reproducibility proof should start from a fresh checkout of the exact public release tag and rely only on:

- the public repository/tag;
- the public source/bootstrap assets bound by that checkout;
- the documented external toolchain prerequisites.

It must not depend on private Builder workspaces, installed-product state, release-candidate directories, private credentials or historical continuity data.

See [Public Source Boundary](PUBLIC_SOURCE_BOUNDARY.md) and [Release Provenance](../release/RELEASE_PROVENANCE.md).
