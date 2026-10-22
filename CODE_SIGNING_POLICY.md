# Code Signing Policy

## Goal

Public Windows release binaries should use SHA-256 Authenticode with a trusted timestamp when a trusted production signing path is available.

Signing is not allowed to block unrelated release engineering. If trusted signing is unavailable when the remaining release gates are complete, an unsigned public release requires an explicit maintainer decision and clear unsigned/SmartScreen/checksum disclosure.

## Preferred signer

The preferred zero-cost production path is the **SignPath Foundation OSS program**, conditional on project eligibility and acceptance.

Initial SignPath acceptance is an external dependency and is non-blocking.

## Files that may receive the AI Director project signature

Only first-party release artifacts:

1. the AI Director application executable;
2. `DaVinci Resolve AI Director Setup <version>.exe`;
3. `DaVinci Resolve AI Director Integration Setup <version>.exe`.

Do **not** stamp the AI Director project signature onto third-party/upstream runtime DLLs or executables.

## Algorithms

- Authenticode file digest: SHA-256.
- Timestamp: SignPath-managed timestamping when using SignPath.
- If another trusted CA-backed signer is used later, require RFC 3161 timestamping with SHA-256.
- Do not use SHA-1 dual signing for the current release line.

## Provenance

Signing changes PE bytes. Preserve both identities:

```text
UNSIGNED_BUILD_SHA256=<deterministic build identity>
SIGNED_RELEASE_SHA256=<post-signing distribution identity>
```

Never overwrite the deterministic unsigned hash with the signed hash.

## SmartScreen

Microsoft documents SmartScreen reputation as depending on both publisher/signing reputation and file-hash reputation. An unsigned file starts without transferable publisher reputation; a self-signed certificate behaves like no trusted signature for SmartScreen. Even a newly signed binary may still be reported as unrecognized until reputation develops.

Therefore:

- a trusted signature is valuable but is not a guarantee that every first download will be warning-free;
- unsigned public releases must be explicitly labeled and checksum-verifiable;
- self-signed certificates are development/testing only.

## User verification

```powershell
Get-AuthenticodeSignature -LiteralPath '.\DaVinci Resolve AI Director Setup X.Y.Z.exe' | Format-List *
Get-FileHash -LiteralPath '.\DaVinci Resolve AI Director Setup X.Y.Z.exe' -Algorithm SHA256
```

See [docs/release/RELEASE_VERIFICATION.md](docs/release/RELEASE_VERIFICATION.md).

## Windows publisher metadata versus certificate identity

The deterministic unsigned Windows PE metadata uses **DaVinci Resolve AI Director** as the project-publisher identity (`CompanyName` / installer `Publisher`). This is product metadata and is not a claim that a legal entity with that name owns the signing certificate.

The Authenticode signer identity is a separate trust boundary and must come from the certificate actually used for signing. Do not preconfigure electron-builder `publisherName` from the project-publisher string; bind it only after the production certificate subject has been observed from a signed artifact.
