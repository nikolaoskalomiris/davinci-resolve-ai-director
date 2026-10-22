# Troubleshooting

Common checks:

- SmartScreen warning: verify the official GitHub origin and SHA-256 first.
- No models: check the two supported LM Studio-compatible model roots and use primary GGUF files.
- Qwen3.8 Flash Next unavailable: place the compatible MTP draft GGUF beside the primary model.
- FFmpeg unavailable: select matching `ffmpeg.exe` / `ffprobe.exe` from the same directory.
- MCP update asks for Resolve: open DaVinci Resolve so the mandatory live canary can run.
- MCP update reports dependency/runtime contract drift: this can be an intentional fail-closed refusal; accepted MCP stays active until a matching validated compatibility bundle/runtime image exists.
- Resolve launcher does nothing: confirm the standalone app is installed for the current user and restart Resolve after integration changes.
- Upstream update rejected: preserve backup/rejected state; a safe rollback is an expected failure-handling path, not evidence that accepted runtime authority changed.
- Source build starts with no `_inputs` or `_toolchain`: that is valid; plain `BUILD.cmd` bootstraps project-owned/downloaded inputs before validating the external compiler/toolkit prerequisites.

See [Troubleshooting](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/user/TROUBLESHOOTING.md) in the repository for detailed guidance.
