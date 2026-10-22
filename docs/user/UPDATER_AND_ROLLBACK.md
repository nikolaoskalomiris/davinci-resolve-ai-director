# Updater and Rollback

AI Director manages **Upstream runtime updates** and **DaVinci Resolve MCP updates** as separate transactions.

## Upstream updates

Before replacing the active Upstream runtime, AI Director:

1. identifies and verifies the update candidate;
2. downloads and stages it;
3. checks compatibility and executable/runtime health;
4. keeps the previous runtime as rollback evidence;
5. activates the candidate only after validation succeeds.

If validation fails and the previous runtime is intact, AI Director restores the previous runtime.

Direct and shared CUDA are not replaced by an ordinary Upstream update.

## MCP updates

MCP updates use a separate transaction because they can change the Resolve-facing tool contract.

DaVinci Resolve must be available during MCP installation so AI Director can run a live read-only validation before commit.

If the candidate changes its dependency/runtime contract and the currently validated compatibility image cannot satisfy it, AI Director refuses the update **before replacing the accepted MCP**.

That refusal is a safety result, not necessarily a product failure.

## If an update fails

- Read and preserve the reported error.
- Do not delete backup, rejected-candidate or transaction directories as a first response.
- If automatic rollback succeeds, continue using the restored runtime.
- If rollback itself fails, stop further update attempts until the installed state has been inspected.

See [Troubleshooting](TROUBLESHOOTING.md).
