# Updater and Rollback

AI Director treats Upstream llama.cpp and DaVinci Resolve MCP as separate update transactions.

Upstream updates are staged, hashed, preflighted and live-health tested before finalization. When the candidate fails and the previous backup is intact, AI Director restores the prior runtime.

MCP updates additionally require a live read-only Resolve canary because MCP changes can alter the Resolve-facing tool contract. A dependency-changing MCP candidate is refused before mutation if the accepted immutable dependency/runtime image cannot satisfy it; supporting that candidate requires a matching validated compatibility bundle/runtime image.

See repository `docs/user/UPDATER_AND_ROLLBACK.md` for the complete sequence and failure semantics.
