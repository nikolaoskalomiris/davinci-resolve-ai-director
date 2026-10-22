# Troubleshooting

Common fixes:

- **SmartScreen warning:** confirm the official GitHub release and signing status.
- **No models:** check the supported model folders and make sure the primary file is a `.gguf`.
- **Flash Next unavailable:** keep the compatible MTP draft GGUF beside the primary model.
- **FFmpeg unavailable:** select `ffmpeg.exe` and `ffprobe.exe` from the same compatible installation.
- **MCP update asks for Resolve:** open DaVinci Resolve and retry.
- **MCP compatibility refusal:** leave the accepted MCP in place and wait for a compatible update bundle.
- **Resolve launcher does nothing:** confirm AI Director is installed, then restart Resolve.
- **Upstream update rejected:** preserve the error/rollback state instead of deleting update folders.

See the full [Troubleshooting guide](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/user/TROUBLESHOOTING.md).
