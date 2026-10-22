# Architecture

AI Director consists of:

- a per-user Electron desktop application;
- a runtime base containing managed backend/MCP support;
- a shared CUDA 13.3.1 runtime lane;
- a pinned Direct llama.cpp-derived server lane;
- an independently updateable Upstream server lane;
- an optional machine-scoped Resolve Workflow Integration launcher.

The release build creates Direct and Upstream from source, then assembles a fresh candidate runtime stack. Shipping shared-CUDA DLLs come from pinned official NVIDIA redistributable archives; the machine CUDA Toolkit remains an external compiler/inspection prerequisite.

The Resolve launcher does not contain a second desktop application/runtime.

See [Architecture](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/architecture/ARCHITECTURE.md) in the repository for the full component and build/update boundaries.
