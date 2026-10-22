# Direct and Upstream Runtimes

**Direct** is the pinned product runtime lane. Ordinary Upstream updates never replace it.

**Upstream** is the independently managed llama.cpp-derived lane. Its updater verifies concrete release/asset identity, SHA-256 and live runtime health before final commit.

Both lanes share the product's CUDA runtime boundary but have separate source/provenance identities. Clean source builds construct both server lanes from source; shipping shared-CUDA DLLs are extracted from pinned official NVIDIA redistributable archives.

See repository `docs/user/RUNTIMES.md` for the exact source identities and ownership rules.
