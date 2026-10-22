# Release Verification

Download release artifacts only from the project's official [GitHub Releases](https://github.com/nikolaoskalomiris/davinci-resolve-ai-director/releases/latest) page.

## SHA-256

Each release provides checksum information for its distributed artifacts. In PowerShell:

```powershell
Get-FileHash -LiteralPath '.\your-downloaded-installer.exe' -Algorithm SHA256
```

Compare the result with the checksum published for the **same release asset**.

## Authenticode

If the release is signed:

```powershell
Get-AuthenticodeSignature -LiteralPath '.\your-downloaded-installer.exe' | Format-List *
```

Verify the signature status and certificate identity. Product `CompanyName`/Publisher metadata is not the same thing as an Authenticode certificate identity.

## Unsigned releases

A release may be published unsigned when that status is stated explicitly in the release notes.

Windows SmartScreen may warn about an unsigned or low-reputation binary. A warning is not proof that a file is malicious, but it should not be ignored blindly: confirm the official GitHub origin and checksum before continuing.

## Source and provenance

Version-specific source, build and artifact identities are recorded in [RELEASE_PROVENANCE.md](RELEASE_PROVENANCE.md).

A public upload alone does not prove reproducibility. Reproducibility requires a clean build from the exact public release source/tag using the documented public inputs and external prerequisites.
