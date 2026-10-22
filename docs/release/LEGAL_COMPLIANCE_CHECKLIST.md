# Release Legal / Attribution Checklist

This is an engineering checklist, not legal advice.

For each public release:

- [ ] Repository root contains the intended Apache-2.0 `LICENSE`.
- [ ] First-party source files do not contain unreviewed copied/vendor code or incompatible notices.
- [ ] `THIRD_PARTY_NOTICES.md` matches the shipped dependency set.
- [ ] Runtime/base dependency license files remain present in the shipping inventory.
- [ ] Pinned davinci-resolve-mcp license material is retained.
- [ ] Pinned llama.cpp/Unsloth license and third-party notices are retained.
- [ ] CUDA redistributable DLLs are reviewed against the applicable NVIDIA EULA.
- [ ] CUDA binaries are clearly excluded from the Apache-2.0 project license.
- [ ] FFmpeg remains external unless a future release deliberately takes on FFmpeg distribution compliance.
- [ ] Blackmagic/DaVinci Resolve trademarks and vendor software are not represented as project-owned.
- [ ] Signing certificate/private key/secrets are absent from the repository.
- [ ] Release notes identify signing status and provide exact verification/checksum information.
