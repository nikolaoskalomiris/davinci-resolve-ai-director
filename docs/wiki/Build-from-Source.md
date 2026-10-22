# Build from Source

AI Director's accepted 0.3.25 public-source build path constructs both Direct and Upstream server payloads from pinned source authorities. Historical accepted server binaries are comparison/provenance only and are not normal clean-build inputs.

Plain `BUILD.cmd` can bootstrap the project-owned/downloaded inputs from an otherwise clean generated-state start. The external Windows compiler boundary remains a real prerequisite: Visual Studio/MSVC, Windows SDK, CMake/Ninja, CUDA Toolkit 13.3 and Git must satisfy the pinned contracts.

Shipping CUDA runtime DLLs come from pinned official NVIDIA CUDA 13.3.1 redistributable archives, not from the machine CUDA Toolkit.

The final first-release reproducibility proof is Gate 6D after publication/tagging: a literal fresh public checkout must complete plain `BUILD.cmd` without pre-existing `_inputs`, `_toolchain`, private credentials/history/continuity, accepted Builder state or installed-product dependency.

The authoritative technical procedure is repository `docs/build/BUILDING.md`.
