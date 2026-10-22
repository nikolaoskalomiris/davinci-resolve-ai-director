# Updater and Rollback

AI Director treats Upstream llama.cpp updates and DaVinci Resolve MCP updates as separate transaction domains.

## Upstream llama.cpp update flow

An Upstream update is not committed merely because a download succeeded.

The current implementation:

1. performs a visible update check and binds a concrete candidate identity;
2. re-queries the release at install time and refuses to continue if the release ID, asset ID, asset name, digest or size changed;
3. requires a verifiable SHA-256 digest for the selected asset;
4. downloads and hashes the asset;
5. extracts it into a staging area and validates runtime-stack compatibility;
6. executes the staged `llama-server` binary before activation;
7. moves the previous Upstream runtime to a backup location and activates the staged candidate;
8. verifies local identity/config integrity;
9. starts the Upstream profile, waits for the server/backend to become healthy and primes the execution cache;
10. runs a read-only Resolve canary when Resolve is available;
11. restores the user's previous selected profile/stopped state when appropriate;
12. finalizes the update only after the live-health gate succeeds.

If live validation fails, AI Director attempts to restore the previous Upstream runtime. It refuses an unsafe rollback when the required backup evidence is missing.

## MCP update flow

MCP updates are separate because they can change the Resolve-facing tool contract.

The MCP update path stages source, Python/runtime state and manifests independently. A live read-only Resolve canary is mandatory before final commit, so Resolve must be available for MCP installation.

A successful MCP finalization records the accepted live-health state. If validation fails, rollback restores the previous MCP source, Python runtime and manifest state when the complete backup set is available.

### Dependency/runtime compatibility boundary

MCP source version alone is not sufficient authority for installation. AI Director also validates the dependency/runtime contract, including the accepted immutable dependency images.

If a candidate changes that contract and the currently accepted dependency image cannot satisfy it, the updater **refuses the update before replacing accepted files**. The accepted MCP remains active.

Supporting such a candidate requires a new version-bound, validated compatibility bundle/runtime image. Do not bypass this boundary by editing hashes or ignoring `package-lock.json`/dependency drift.

The accepted first-release MCP seed is 4.10.4. MCP 4.14.4 is an example of a dependency-changing candidate that is intentionally withheld until a matching compatibility bundle/runtime image is validated.

## What updates do not change

An ordinary Upstream update must not replace:

- Direct;
- the shared CUDA runtime lane;
- AI Director application source;
- the user's `vfx_mcp.json` configuration.

The update implementation verifies that the managed configuration hash is preserved across the Upstream transaction.

## If an update fails

Do not manually delete update/backup directories as a first response. Preserve the diagnostic state and use the application's reported error plus [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

If automatic rollback itself reports failure, stop further update attempts until the installed runtime state has been inspected. A failed recovery is materially different from a candidate that was safely rejected and rolled back.
