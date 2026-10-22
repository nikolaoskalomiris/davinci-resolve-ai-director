# FFmpeg

FFmpeg is an external optional dependency. It is **not bundled** into AI Director's managed runtime.

AI Director can run with FFmpeg disabled, but FFmpeg-backed media operations are unavailable in that mode. Configure FFmpeg if you want the full offline media feature set.

## Configure an existing FFmpeg installation

In AI Director Settings, select an external FFmpeg installation. The current source requires:

- an absolute path to `ffmpeg.exe`;
- an absolute path to `ffprobe.exe`;
- both executables to come from the same directory.

AI Director probes the selected pair before enabling it. The probe checks that both executables run, that their versions can be identified and are from the same major release, and that the FFmpeg build exposes the filters/decoders/encoders/formats required by the application.

AI Director also records SHA-256 identities for the selected executables in the runtime status it passes to its managed backend.

## Recommended download page

The current application can open:

`https://www.gyan.dev/ffmpeg/builds/`

This is an external website and FFmpeg remains separately licensed. You may instead select a compatible FFmpeg/FFprobe pair already present on your machine.

## Licensing

FFmpeg's own project states that FFmpeg is normally licensed under LGPL 2.1-or-later, while enabling certain optional GPL-covered parts makes the resulting FFmpeg build GPL 2-or-later. Follow the license of the exact third-party build you download.

See [../../THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).
