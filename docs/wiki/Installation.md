# Installation

Use only official GitHub Release assets and verify SHA-256 before running them.

The main installer is `DaVinci Resolve AI Director Setup <version>.exe`. It installs the current-user desktop application and offers default-checked choices for the Resolve Workflow Integration launcher and a desktop shortcut.

If Resolve Integration is selected, Windows elevation occurs only for the separate machine-scoped child installer. A separate `DaVinci Resolve AI Director Integration Setup <version>.exe` is also published for repair/manual installation.

For the first public release line, uninstall the previous AI Director version before installing a newer one. If Resolve Integration is installed, uninstall its separate Windows entry too and reinstall it from the new release. In-place/dirty upgrade is not currently a supported release path.

If a release is explicitly unsigned, Windows SmartScreen may warn. Verify the GitHub origin and published checksum before choosing to continue.

For prerequisites, first-run steps, uninstall ownership and full verification commands, see repository `docs/user/INSTALLATION.md` and `docs/release/RELEASE_VERIFICATION.md`.
