# Privacy

This document describes the current accepted source behavior. It must be reviewed whenever networking, updates, model handling, MCP behavior, crash reporting, analytics or account features change.

## Local-first operation

AI Director's core model workflow is local. The desktop application communicates with locally managed llama.cpp-derived runtime components and the local DaVinci Resolve integration/backend on the user's machine.

The accepted source contains no third-party advertising or product-analytics telemetry upload endpoint.

The word `telemetry` may appear in code for local runtime/status information; that does not by itself indicate an external analytics service.

## Network activity

Current source-audited outbound behavior includes:

- GitHub API/release requests for supported Upstream llama.cpp update discovery and download;
- GitHub API/raw/codeload requests used by the managed davinci-resolve-mcp update/compatibility workflow;
- NPM registry access used by MCP compatibility/update tooling;
- opening the user's browser to the configured external FFmpeg download page when requested.

Source/build bootstrap also downloads explicitly pinned build inputs when a maintainer performs a source build; that is separate from ordinary model inference.

Local llama-server and backend communication uses local host/process boundaries and is not an analytics channel.

## Models

AI Director discovers local GGUF files under the supported LM Studio-compatible model roots. The LM Studio application is not required for inference. If the `lms` CLI is present, AI Director may use its local catalog metadata.

AI Director does not upload model weights as part of its normal local inference path.

## FFmpeg

AI Director does not bundle FFmpeg. If you enable external FFmpeg, the selected `ffmpeg.exe` and `ffprobe.exe` remain local executables. AI Director may open an external download page in your browser when you request it.

## User content and logs

DaVinci Resolve project/media data, prompts, generated context, settings, model metadata, logs and MCP operations can contain sensitive information. Review logs and diagnostic files before sharing them publicly.

## Future services

If a future release adds crash reporting, cloud inference, accounts, hosted telemetry or another new data transfer, this document must be updated before that release is accepted.
