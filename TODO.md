# Post-First-Release TODO

This file tracks deliberately deferred engineering work that is **not a blocker for the first public release unless new evidence explicitly reopens it**.

## MCP 4.14.4 compatibility bundle

Priority: high.

The accepted first-release MCP seed is `4.10.4`. MCP `4.14.4` was correctly refused before mutation because its `resolve-advanced` dependency/runtime contract no longer matches the accepted immutable Advanced Node dependency image.

Post-release work:

- build a new version-bound compatibility bundle for the selected MCP successor;
- produce and provenance-bind a new immutable Advanced Node dependency image that satisfies the candidate `package.json` / `package-lock.json` semantics;
- update any companion Python/runtime image only when the candidate contract requires it;
- keep the current fail-closed behavior: never authorize a dependency-changing candidate by weakening hash/lockfile checks;
- validate staging, source/runtime identities, the full MCP tool surface, mandatory read-only Resolve canary, commit and rollback;
- review the 4.14.x security/correctness changes before promotion, including argument/command handling changes around `conform.relink_scalefix`;
- only after the new bundle is accepted should the bundled/accepted MCP authority advance from 4.10.4.

Pinned 4.14.4 identity observed during first-release engineering:

```text
repository:           samuelgursky/davinci-resolve-mcp
tag:                  v4.14.4
annotated tag object: 096a72bf6c520aa97e728a9c1407726d3baef1e1
commit:               a07f594bc7357092432e812190909b615ef41a59
```

## Supported in-place upgrade path

The first public release documentation requires uninstalling the previous AI Director version before installing a newer one.

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
- accepted predecessor -> successor upgrade once upgrade support is implemented;
- installed Direct 17/17 candidate-payload verification;
- installed Upstream identity/update smoke;
- Resolve Integration install/repair/uninstall ownership;
- shortcut/icon and uninstall-registration checks;
- MCP fail-closed dependency-contract cases;
- acceptance dry-run/promotion preimage and rollback coverage.

## Documentation maintenance

Keep the root README, structured `docs/` tree and Wiki projection synchronized when release/build/update policy changes. The structured repository docs are the technical authority; Wiki pages should remain concise navigational/tutorial projections.
