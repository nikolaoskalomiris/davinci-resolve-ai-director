# Updater and Rollback

AI Director updates the Upstream runtime and Resolve MCP through separate guarded transactions.

- **Upstream:** downloaded candidates are staged and health-checked before they replace the active runtime. Failed candidates can roll back to the previous runtime.
- **MCP:** Resolve must be available for a live read-only validation before commit. Candidates that require an unsupported dependency/runtime contract are refused before accepted files are replaced.

See the full [Updater and Rollback guide](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/user/UPDATER_AND_ROLLBACK.md).
