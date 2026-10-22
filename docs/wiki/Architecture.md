# Architecture

AI Director has a few clear parts:

- a per-user desktop application;
- a pinned **Direct** model runtime;
- an updateable **Upstream** model runtime;
- a shared managed CUDA runtime;
- a managed Resolve MCP/backend;
- an optional machine-scoped Resolve Integration launcher.

The Resolve launcher only starts or foregrounds the standalone application; it is not a second AI Director runtime.

Source builds construct Direct and Upstream from pinned source authorities and assemble them with the managed runtime inputs.

See the full [Architecture guide](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/architecture/ARCHITECTURE.md).
