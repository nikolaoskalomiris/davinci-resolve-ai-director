# Code Signing Policy

## Goal

Public Windows release binaries should use SHA-256 Authenticode with a trusted timestamp when a trusted production signing path is available.

Signing is a distribution trust improvement, not a substitute for build provenance or checksums. If trusted signing is unavailable for a release, publishing unsigned requires an explicit maintainer decision and clear release-note/checksum disclosure.

## Preferred signer

The preferred zero-cost production path is the **SignPath Foundation OSS program**, subject to project eligibility and acceptance.

SignPath acceptance is an external dependency and does not block source development or unrelated release engineering.

## What may be signed

Only first-party release artifacts should receive the AI Director project signature:

1. the AI Director application executable;
2. the main AI Director installer;
3. the Resolve Integration installer.

Do **not** stamp the AI Director project signature onto third-party/upstream runtime DLLs or executables.

## Algorithms

- Authenticode file digest: SHA-256.
- Timestamp: trusted timestamping supplied by the signing service.
- If another CA-backed signer is used, require RFC 3161 timestamping with SHA-256.
- Do not use SHA-1 dual signing for the current release line.

## Provenance

Signing changes PE bytes. Preserve both identities:

```text
UNSIGNED_BUILD_SHA256=<deterministic build identity>
SIGNED_RELEASE_SHA256=<post-signing distribution identity>
```

Never overwrite the deterministic unsigned hash with the signed distribution hash.

## SmartScreen

Trusted signing can improve publisher reputation, but it does not guarantee that every new binary will avoid SmartScreen warnings. Self-signed certificates are development/testing tools and do not provide normal Windows publisher trust.

Unsigned releases must therefore be clearly identified and checksum-verifiable.

## User verification

Users should verify release artifacts as described in [Release Verification](docs/release/RELEASE_VERIFICATION.md).

## Product metadata versus certificate identity

The Windows PE `CompanyName` and installer `Publisher` identify the product/project. They are not the Authenticode certificate subject.

Signing configuration must be bound to the certificate actually used. Do not infer or preconfigure certificate identity from the product metadata string.
