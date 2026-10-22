# Release Verification

Verify both the download source and the file identity before running a release artifact.

## SHA-256

In PowerShell:

```powershell
Get-FileHash -LiteralPath '.\DaVinci Resolve AI Director Setup X.Y.Z.exe' -Algorithm SHA256
Get-FileHash -LiteralPath '.\DaVinci Resolve AI Director Integration Setup X.Y.Z.exe' -Algorithm SHA256
```

Compare each hash with the value published for the exact GitHub Release asset. A hash from another version or an engineering report is not a substitute.

## Authenticode

If the release is signed:

```powershell
Get-AuthenticodeSignature -LiteralPath '.\DaVinci Resolve AI Director Setup X.Y.Z.exe' | Format-List *
```

Verify the actual certificate identity and signature status. Do not infer the certificate subject from the product's PE `CompanyName`/Publisher metadata; those are separate identities.

## Unsigned releases

An unsigned release is acceptable only when the maintainer explicitly labels it unsigned and publishes the exact SHA-256/provenance.

Windows SmartScreen may warn on unsigned binaries. Microsoft documents that unsigned files start with no transferable publisher reputation, while self-signed certificates behave like unsigned files for SmartScreen reputation. Even a newly signed binary can still receive an "unrecognized app" warning until reputation develops.

A SmartScreen warning is therefore not proof that a file is malicious, but it is also not something to ignore blindly. Verify the GitHub origin and SHA-256 first.

## Deterministic unsigned versus signed hashes

If signing is applied after the deterministic build, the signed file is expected to have a different SHA-256. Release provenance should preserve both:

```text
UNSIGNED_BUILD_SHA256=...
SIGNED_RELEASE_SHA256=...
```

## Source/provenance verification

The public source repository should expose the Direct and Upstream source-build contracts and provenance records used for the tag. Those records identify the immutable source inputs used to construct the server payloads.

A public release is not considered reproducible merely because its installers are attached to GitHub; the tagged source must also pass the documented clean-build procedure.
