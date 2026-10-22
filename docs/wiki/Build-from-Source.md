# Build from Source

From a clean repository checkout:

```powershell
.\BUILD.cmd
```

The project bootstraps its managed/downloaded build inputs, but the documented Windows compiler/CUDA toolchain and Git remain external prerequisites.

A clean build constructs both Direct and Upstream from pinned source authorities and assembles the managed runtime stack. Historical prebuilt server binaries are provenance/comparison evidence, not normal clean-build inputs.

See the full [Building from Source guide](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/build/BUILDING.md) for prerequisites, build semantics and maintainer version/acceptance commands.
