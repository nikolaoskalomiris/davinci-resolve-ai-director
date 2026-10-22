# Building from Source

## Accepted public-source build status

The accepted engineering authority is **0.3.25 / ACCEPTED_READY**.

The public-source build path has already been exercised from a clean generated-state start with `_inputs`, `_toolchain` and `_cache` absent. Plain `BUILD.cmd` bootstrapped the project-owned/downloaded inputs, strictly validated the external system toolchain, built Direct and Upstream from source, assembled the source-built runtime stack, and produced the accepted `0.3.25/static-build-001` release candidate.

The remaining reproducibility release gate is **Gate 6D**: after the repository is published/tagged, a literal fresh public checkout must run plain `BUILD.cmd` successfully with no private credentials/history/continuity, no pre-existing generated inputs/toolchain, no accepted Builder workspace and no installed-product dependency.

Do not confuse "project-owned bootstrap is self-populating" with "zero prerequisites." The Windows compiler/toolkit boundary remains an explicit external prerequisite.

## Normal build entrypoint

From the repository root:

```powershell
.\BUILD.cmd
```

Plain `BUILD.cmd` uses the checked-out version state and is non-mutating with respect to semantic release authority. It may create generated `_inputs`, `_toolchain` and `_cache` state while bootstrapping/building; those paths are ignored repository-local working state, not source.

A successful release-candidate build does **not** install the product and does **not** advance accepted release authority. Acceptance is a separate explicit maintainer gate after installation and live testing.

## Build invariant

The normal release-candidate path must build both server payloads from source:

- **Direct:** clone the pinned public repository and detach at the immutable accepted commit/tree;
- **Upstream:** download the authenticated source release asset, verify its byte identity, reconstruct the accepted source tree and build from that tree.

Historical accepted Direct/Upstream server binaries and the historical accepted `RUNTIME-STACK.7z` are comparison/release authority only. They are not normal server build inputs.

## Source authorities

### Direct

```text
repository: nikolaoskalomiris/llama-cpp-flashnext-direct
commit:     c8f321699adbd0035c8c755bdefcb4182705262b
tree:       a17cf64683bc6877e2dbc4e0b4ef8933106257fb
```

The acquisition step disables interactive Git prompting, checks out the exact commit detached, verifies `HEAD`, verifies `HEAD^{tree}`, and requires a clean working tree.

### Upstream

```text
repository:           unslothai/llama.cpp
accepted source tree: edd784f1d459cd39f2605ccf66adc0c79ef75a93
runtime source id:    b7eb4a03a1285c50ebe86c6bd2fc7a70c6f7214d
source asset SHA256:  CBD0E8C756DA5B2F46DF4DDACDED46C7733316C44D86A1A5D176FE3ADE7B0675
```

The reconstruction tool verifies the source archive size/SHA-256, rejects unsafe tar members, applies the versioned normalization set, and verifies the complete reconstructed file tree against the published manifest.

## System toolchain boundary

Both server build contracts require the same Windows system toolchain identities:

| Component | Current contract |
| --- | --- |
| Platform | Windows x64 |
| Visual Studio | Visual Studio 2022 Build Tools |
| MSVC toolset | 14.44.35207 |
| Windows SDK | 10.0.26100.0 |
| CMake | 3.31.6-msvc6 from Visual Studio Build Tools |
| Ninja | 1.12.1 from Visual Studio Build Tools |
| CUDA Toolkit | 13.3 |
| nvcc | V13.3.73 |
| vcvars | `vcvars64.bat -vcvars_ver=14.44` |

The contracts are strict path/hash bound. Git must also be available for Direct source acquisition.

These tools are external machine prerequisites and are **not auto-installed** by AI Director bootstrap.

`cuobjdump.exe` is derived from the pinned `CUDA_PATH` inspection lane for CUDA topology verification. It is an inspection executable, not an additional formal compiler-contract key.

## Bootstrap-managed inputs

`bootstrap/bootstrap-inputs.json` has public URLs bound and SHA-256-verifies the project-owned/downloaded inputs. The current manifest includes:

- Python 3.11.9 embeddable x64;
- Node 24.18.0 with npm 11.16.0;
- Electron 36.3.2 archive;
- NSIS 3.0.4.1;
- NSIS resources 3.4.1;
- the pinned electron-builder 7-Zip helper;
- official NVIDIA CUDA 13.3.1 `cuda_cudart` redistributable archive;
- official NVIDIA CUDA 13.3.1 `libcublas` redistributable archive;
- `CUDA13-Native-Base-v3` from the public `builder-inputs-v1` release asset.

Generated destinations live under `_toolchain` and `_inputs` and are intentionally gitignored.

## Shared CUDA shipping source

Shipping shared CUDA is **not copied from the machine CUDA Toolkit**.

The accepted shared runtime lane is sourced from pinned official NVIDIA redistributable archives:

```text
cuda_cudart 13.3.29
SHA256 1FEB7DD266813FFE8DBC24E115183A5AC35A4795C8D34ACA0DF85AB616B64D9C

libcublas 13.6.0.2
SHA256 62E9FA30560C8F0A28E0CDCF9D6FC1FED347BCFAB8847239B9AE1FDC1D86408A
```

Those archives supply the accepted shipping DLLs:

```text
cudart64_13.dll
B00CA6F53699120DA815BF3E06E2E4285FAE2F201235B883DCBB50EEC51E2A2A

cublas64_13.dll
8C6BAC24474AF29627EC96500025A5D410A1B7E8FFA00E1FE13B1781FC6B3DDC

cublasLt64_13.dll
E323ABD89E0F03C1DB91A09D7AEB1928DE08E1F86192CC713B335FEFE3E368A9
```

The external CUDA Toolkit is used for compilation/inspection only.

## Runtime-stack construction

The release build creates a disposable server-source/work area, then:

1. acquires Direct source;
2. downloads and reconstructs Upstream source;
3. extracts/verifies the three shared CUDA DLLs from the pinned NVIDIA redistributable archives;
4. runs `build/direct/build_direct.py`;
5. runs `build/upstream/build_upstream.py`;
6. stages the new runtime tree from shared CUDA + Direct shipping files + Upstream candidate files;
7. writes fresh per-file SHA-256 values into the candidate manifest;
8. creates a new `RUNTIME-STACK.7z`;
9. extracts it and requires full staged/extracted tree-hash parity;
10. writes source-build reports for the runtime stack, Direct and Upstream.

Direct and Upstream compiler child processes use dedicated TEMP/TMP/TMPDIR directories under the active static-build workspace; compiler temporary files must not spill into unrelated user Temp locations.

A successful construction reports:

```text
SOURCE_BUILT_RUNTIME_STACK=PASS
DIRECT_SOURCE_BUILD=PASS
UPSTREAM_SOURCE_BUILD=PASS
ACCEPTED_RUNTIME_STACK_ARCHIVE_CONSUMED=NO
```

## Application and installers

The canonical application is Electron 36.3.2 packaged with electron-builder 26.15.3. The application source is ASAR-packed and the build validates final ASAR/source parity.

The release build produces:

- `DaVinci Resolve AI Director Setup <version>.exe`;
- `DaVinci Resolve AI Director Integration Setup <version>.exe`;
- build/provenance reports including Direct, Upstream and source-built runtime-stack identities.

The accepted 0.3.25 candidate is `static-build-001`. Its acceptance is recorded separately from the build itself.

## Maintainer version lifecycle

Semantic target preparation, build and acceptance are separate operations.

Maintainer release engineering may prepare a successor with selectors such as:

```powershell
.\BUILD.cmd --patch
.\BUILD.cmd --minor
.\BUILD.cmd --major
.\BUILD.cmd --version X.Y.Z
```

Do not run a selector merely to rebuild an already prepared/accepted version.

Acceptance of an installed, live-tested candidate is a separate explicit gate:

```powershell
.\BUILD.cmd --accept --candidate static-build-NNN --dry-run
.\BUILD.cmd --accept --candidate static-build-NNN
```

The apply path requires a dedicated live attestation and writes promotion evidence. A plain build never silently performs acceptance.

## Gate 6D fresh-clone rule

Before the first official release is declared reproducible, the published/tagged repository must pass a literal fresh-clone build using only:

- the public repository/tag;
- the public bootstrap/source assets bound by the repository;
- the documented external system-toolchain prerequisites.

The proof must not depend on:

- `C:\AI\AI-Director-Builder`;
- pre-existing `_inputs`, `_toolchain` or `_cache`;
- installed AI Director product state;
- private credentials or private source workspaces;
- release-candidate directories;
- continuity/history files.

Gate 6D is a publication/release proof. It does not reverse the already accepted 0.3.25 engineering authority.
