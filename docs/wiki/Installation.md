# Installation

Use only the official [0.3.25 GitHub Release](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/releases/tag/0.3.25) and verify SHA-256 before running either installer.

GitHub exposes the main installer as:

`DaVinci.Resolve.AI.Director.Setup.0.3.25.exe`

and the separate Resolve Workflow Integration installer as:

`DaVinci.Resolve.AI.Director.Integration.Setup.0.3.25.exe`

The accepted build-artifact names use spaces rather than periods. GitHub canonicalized the uploaded Release filenames; `RELEASE-MANIFEST-0.3.25.json` records both identities and `SHA256SUMS-0.3.25.txt` uses the actual downloadable names.

Accepted installer SHA-256:

```text
4253D3A4201E7797BC2EF286BDAB3B1B053C578B7667FA2B80ED27205A8A4077  DaVinci.Resolve.AI.Director.Setup.0.3.25.exe
7CA2E825983BFEAC27551C1E8BFBB76F5C858B8756CF46D5ACAF21F16067F456  DaVinci.Resolve.AI.Director.Integration.Setup.0.3.25.exe
```

The main installer installs the current-user desktop application and offers default-checked choices for the Resolve Workflow Integration launcher and a desktop shortcut. If Resolve Integration is selected, Windows elevation occurs only for the separate machine-scoped child installer.

For the first public release line, uninstall the previous AI Director version before installing a newer one. If Resolve Integration is installed, uninstall its separate Windows entry too and reinstall it from the new release. In-place/dirty upgrade is not currently a supported release path.

The 0.3.25 installers are intentionally **unsigned**. Windows SmartScreen may show an unknown-publisher or unrecognized-app warning. Verify the GitHub origin and published checksum before choosing to continue.

For prerequisites, first-run steps, uninstall ownership and full verification commands, see [Installation](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/user/INSTALLATION.md) and [Release Verification](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/blob/main/docs/release/RELEASE_VERIFICATION.md) in the repository.
