# Release Legal / Attribution Checklist

This is an engineering checklist, not legal advice.

Before a public release:

- [ ] Repository root contains the intended Apache-2.0 `LICENSE`.
- [ ] First-party source files do not contain unreviewed copied/vendor code or incompatible notices.
- [ ] `THIRD_PARTY_NOTICES.md` matches the exact shipped dependency set.
- [ ] Runtime/base dependency license files remain present in the shipping inventory.
- [ ] Exact pinned davinci-resolve-mcp license is retained.
- [ ] Exact pinned llama.cpp/Unsloth runtime license/third-party notices are retained.
- [ ] CUDA redistributable DLL list is checked against the NVIDIA EULA applicable to the shipped toolkit/runtime.
- [ ] CUDA binaries are clearly excluded from the Apache-2.0 project license.
- [ ] FFmpeg remains external unless a later release deliberately takes on FFmpeg distribution compliance.
- [ ] Blackmagic/DaVinci Resolve trademarks and vendor software are not represented as project-owned.
- [ ] Signing certificate/private key/secrets are absent from the repository.
- [ ] Public release page includes exact SHA-256 checksums and signed/unsigned provenance status.
