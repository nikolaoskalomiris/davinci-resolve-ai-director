# Changelog

This changelog starts from the accepted pre-public baseline. Earlier internal development history is preserved in release-engineering evidence rather than reconstructed here.

## 0.3.25 — accepted public-source engineering authority

- Public-source `BUILD.cmd` bootstrap/build path completed from a clean generated-state start and produced `static-build-001`.
- Direct and Upstream server payloads are built from pinned source authorities; the historical accepted runtime-stack archive is comparison authority only and is not consumed as the normal server payload input.
- Shipping CUDA 13.3.1 runtime DLLs are sourced from pinned official NVIDIA redistributable archives instead of the machine compiler Toolkit.
- Added live build-progress streaming and contained Direct/Upstream compiler TEMP/TMP/TMPDIR under the active static-build workspace.
- Clean installation, live product use, Direct runtime, Upstream runtime/update behavior and Resolve Integration passed validation.
- Dirty/in-place upgrade from 0.3.24 was not accepted as a supported release path because mixed-version backend/server residue was observed; first-release guidance requires uninstalling the previous version before installing the new one.
- MCP 4.14.4 correctly exercised the fail-closed dependency/runtime compatibility boundary. Accepted MCP 4.10.4 remained active; dependency-changing MCP updates require a matching validated compatibility bundle/runtime image.
- Acceptance validation was corrected to bind installed Direct to the selected candidate's hash-bound Direct source-build report and verify the full 17-file Direct payload.
- `0.3.25/static-build-001` was explicitly promoted with live attestation to `ACCEPTED_READY`.

Public release status: engineering authority accepted. GitHub publication/tagging and the final Gate 6D literal fresh-clone build proof remain before the first official release.

## 0.3.24 — accepted predecessor baseline

- Served as the live accepted authority immediately before 0.3.25 promotion.
- Its historical runtime-stack byte identities remain provenance/comparison evidence; 0.3.25 deliberately transitions normal server construction to source-built Direct and Upstream successors.

Public release status: not declared.

## 0.3.23 — accepted updater-boundary correction

- Corrected Upstream llama.cpp post-install validation so DaVinci Resolve may remain closed; the Resolve canary is optional for Upstream and remains mandatory for MCP updates.
- Preserved the MCP pre-update Resolve prerequisite and kept the Component Updates UI distinction concise.
- Bound Upstream transactions to concrete GitHub release/asset identity plus SHA-256 and size; mutable Git tag movement is not treated as release-asset provenance authority.
- Validated an in-place upgrade from 0.3.22 and a successful Upstream update to b11696-mix-7baeb9a against the managed CUDA 13.3.1 stack with Resolve closed.
- Preserved Direct and shared CUDA ownership boundaries during ordinary Upstream updates.
- Builder/docs-only post-acceptance hardening added a Builder-owned interactive `BUILD.cmd --accept` gate with dry-run preflight, exact release-candidate binding, durable recovery/rollback, and external promotion evidence; accepted 0.3.23 application/runtime bytes were not changed by this control-plane update.

Public release status: not yet declared. Signing/reproducibility/public-release gates remain.

## 0.3.22 — accepted engineering baseline

- Corrected product/publisher identity across packaged and installed Windows metadata.
- Corrected uninstall-record acceptance discovery.
- Made Builder root guards compatible with inert repository documentation/metadata.
- Completed live upgrade and focused runtime smoke acceptance.
- Hardened semantic-version preparation against abrupt PowerShell termination/power loss.
- Preserved accepted `0.3.22/static-build-001` product bytes while applying Builder/docs-only hardening.

Public release status: not yet declared. Signing/reproducibility/public-release gates remain.
