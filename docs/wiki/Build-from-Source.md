# Build from Source

AI Director's accepted 0.3.25 public-source build path constructs both Direct and Upstream server payloads from pinned source authorities. Historical accepted server binaries are comparison/provenance only and are not normal clean-build inputs.

Plain `BUILD.cmd` can bootstrap the project-owned/downloaded inputs from an otherwise clean generated-state start. The external Windows compiler boundary remains a real prerequisite: Visual Studio/MSVC, Windows SDK, CMake/Ninja, CUDA Toolkit 13.3 and Git must satisfy the pinned contracts.

Shipping CUDA runtime DLLs come from pinned official NVIDIA CUDA 13.3.1 redistributable archives, not from the machine CUDA Toolkit.

Post-publication Gate 6D remains the final first-release reproducibility proof: a literal fresh anonymous clone of exact tag `0.3.25` must complete plain `BUILD.cmd` without pre-existing `_inputs`, `_toolchain`, private credentials/history/continuity, accepted Builder state or installed-product dependency, followed by `CHECK-STATE.cmd` and artifact-equivalence verification.

The authoritative technical procedure is [Build from Source](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/build/BUILDING.md).
