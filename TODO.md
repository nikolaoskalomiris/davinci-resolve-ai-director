# Post-Release TODO

This file tracks deferred engineering work. Items here are not release blockers unless new evidence explicitly reopens them.

## MCP compatibility bundle

Priority: high.

The currently accepted MCP seed remains on the validated compatibility image. A newer dependency-changing MCP candidate was correctly refused before mutation because its runtime/dependency contract did not match that image.

Post-release work:

- build a version-bound compatibility bundle for the selected MCP successor;
- produce and provenance-bind a new immutable Advanced Node dependency image that satisfies the candidate package/lockfile semantics;
- update companion runtime images only when the candidate contract requires it;
- keep the fail-closed behavior: never authorize a dependency-changing candidate by weakening hash or lockfile checks;
- validate staging, source/runtime identities, the full MCP tool surface, mandatory read-only Resolve canary, commit and rollback;
- review relevant security/correctness changes before promotion;
- advance the bundled/accepted MCP authority only after the new compatibility bundle is accepted.

The first investigated successor was MCP 4.14.4:

```text
repository:           samuelgursky/davinci-resolve-mcp
tag:                  v4.14.4
annotated tag object: 096a72bf6c520aa97e728a9c1407726d3baef1e1
commit:               a07f594bc7357092432e812190909b615ef41a59
```

## Supported in-place upgrade path

The current supported upgrade procedure is to uninstall the previous AI Director application before installing a newer release, and to reinstall Resolve Integration when used.

Before claiming in-place upgrade support:

- define exact ownership/replacement rules for the application, Direct, Upstream, shared CUDA, runtime base, MCP state and Resolve Integration;
- ensure old backend/server files cannot survive as mixed-version active payload;
- verify application executable and desktop shortcut icon/registration behavior across upgrade;
- verify current-user and machine-scoped uninstall registrations independently;
- preserve intended user settings while replacing product-owned runtime payloads;
- exercise upgrades with and without Resolve Integration installed;
- exercise upgrades with both Direct and Upstream selected;
- exercise MCP accepted/update state across upgrade;
- add pre/post-install inventory checks and exact-version assertions;
- require clean rollback/recovery semantics for interrupted upgrades;
- complete a documented upgrade matrix before relaxing the clean-uninstall guidance.

## Automated installation/acceptance regression coverage

Add automation where practical for:

- clean install -> smoke -> uninstall -> reinstall;
- predecessor -> successor upgrade once in-place upgrade support is implemented;
- installed Direct candidate-payload verification;
- installed Upstream identity/update smoke;
- Resolve Integration install/repair/uninstall ownership;
- shortcut/icon and uninstall-registration checks;
- MCP fail-closed dependency-contract cases;
- acceptance dry-run/promotion preimage and rollback coverage.

## Documentation maintenance

Keep the root README, structured `docs/` tree and Wiki projection synchronized when release/build/update policy changes. The repository docs are the technical authority; Wiki pages should stay concise and task-oriented.
