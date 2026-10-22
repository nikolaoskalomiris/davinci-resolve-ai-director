# FFmpeg

FFmpeg is optional and is **not bundled** with AI Director.

AI Director can run without it, but FFmpeg-backed media operations will be unavailable.

## Configure FFmpeg

In AI Director Settings, select a compatible FFmpeg installation.

AI Director expects:

- `ffmpeg.exe` and `ffprobe.exe`;
- both executables in the same directory;
- both executables to run successfully and expose the capabilities AI Director needs.

The application validates the pair before enabling it.

## Getting FFmpeg

AI Director can open:

`https://www.gyan.dev/ffmpeg/builds/`

This is an external website. You may instead use another compatible FFmpeg/FFprobe pair already installed on your machine.

## Licensing

FFmpeg is separately licensed. Follow the license terms of the exact build you use.

See [Third-Party Components and Notices](../../THIRD_PARTY_NOTICES.md).
