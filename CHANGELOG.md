# Changelog

This changelog starts from the accepted pre-public development baseline. Earlier internal history is preserved in release-engineering evidence rather than reconstructed here.

## 0.3.25 — first public release

- Published the first public AI Director release and public source repository.
- Validated clean installation and live use of the standalone application, Direct runtime, Upstream runtime/update flow and Resolve Integration.
- Direct and Upstream server payloads are built from pinned source authorities rather than reused from historical prebuilt server binaries.
- Shipping CUDA runtime DLLs come from pinned official NVIDIA redistributable archives rather than the machine compiler Toolkit.
- Upstream and MCP updates use staged validation, health checks and rollback/fail-closed behavior.
- Dependency-changing MCP updates are refused when the installed compatibility image cannot satisfy the candidate contract.
- The supported upgrade path remains a clean uninstall of the previous AI Director application and Resolve Integration before installing a newer release.
- The release is intentionally unsigned; signing remains a separate future distribution improvement.

## 0.3.24 — accepted predecessor baseline

- Served as the live accepted authority immediately before 0.3.25 promotion.
- Historical runtime-stack byte identities remain provenance/comparison evidence; later builds transition normal server construction to source-built Direct and Upstream successors.

Public release status: not declared.

## 0.3.23 — accepted updater-boundary correction

- Corrected Upstream llama.cpp post-install validation so DaVinci Resolve may remain closed; the Resolve canary is optional for Upstream and remains mandatory for MCP updates.
- Preserved the MCP pre-update Resolve prerequisite and kept the Component Updates UI distinction concise.
- Bound Upstream transactions to concrete GitHub release/asset identity plus SHA-256 and size; mutable Git tag movement is not treated as release-asset provenance authority.
- Validated an in-place upgrade from 0.3.22 and a successful Upstream update to b11696-mix-7baeb9a against the managed CUDA 13.3.1 stack with Resolve closed.
- Preserved Direct and shared CUDA ownership boundaries during ordinary Upstream updates.
- Builder/docs-only post-acceptance hardening added a Builder-owned interactive acceptance gate with dry-run preflight, exact release-candidate binding, durable recovery/rollback and external promotion evidence.

Public release status: not declared.

## 0.3.22 — accepted engineering baseline

- Corrected product/publisher identity across packaged and installed Windows metadata.
- Corrected uninstall-record acceptance discovery.
- Made Builder root guards compatible with inert repository documentation/metadata.
- Completed live upgrade and focused runtime smoke acceptance.
- Hardened semantic-version preparation against abrupt PowerShell termination/power loss.
- Preserved accepted product bytes while applying Builder/docs-only hardening.

Public release status: not declared.
