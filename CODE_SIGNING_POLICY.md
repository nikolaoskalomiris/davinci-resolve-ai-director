# Code signing policy

## Goal

Public Windows release binaries should use SHA-256 Authenticode with a trusted timestamp when a trusted production signing path is available.

Signing improves distribution trust. It does not replace reproducible build evidence, release provenance, or checksums. A release may remain unsigned when no accepted trusted signing path is available, provided that the maintainer makes that decision explicitly and the release clearly states its signing status.

Release `0.3.25` is intentionally unsigned. SignPath Foundation is being evaluated for future GitHub releases and is not a requirement for the current release or for unrelated release engineering.

## SignPath Foundation

The preferred zero-cost production signing path is the SignPath Foundation Open Source program, subject to project eligibility and acceptance.

**Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).**

If the project is accepted, signing requests must use the approved SignPath project configuration, verifiable build origin, artifact restrictions, and manual approval workflow. The project will not treat SignPath acceptance as permission to sign arbitrary local binaries.

## Team roles

The current project signing team is:

- **Authors:** [@nikolaoskalomiris](https://github.com/nikolaoskalomiris)
- **Reviewers:** [@nikolaoskalomiris](https://github.com/nikolaoskalomiris)
- **Approvers:** [@nikolaoskalomiris](https://github.com/nikolaoskalomiris)

Changes proposed by contributors without direct commit access require review before merge. Every signing request requires manual approval by an Approver.

All team members participating in repository or signing access must use multi-factor authentication for GitHub and SignPath.

## What may be signed

The initial SignPath scope is intentionally narrow.

The project may request signatures for first-party distribution artifacts whose origin can be verified from the public source and approved build configuration. The initial intended artifacts are:

1. the main AI Director installer
2. the Resolve Integration installer

Additional first-party PE artifacts may be added only after their build origin and metadata are covered by the approved SignPath artifact configuration.

The AI Director project signature must not be applied indiscriminately to upstream or vendor binaries.

## Third-party and upstream boundary

AI Director distributions contain third-party and upstream components. Those components retain their own licenses, notices, and publisher identities.

The project signature is not applied to NVIDIA CUDA redistributables, Electron or Chromium components, Node.js, Python, upstream llama.cpp binaries, MCP dependencies, or other vendor/upstream binaries unless SignPath explicitly approves a signing scope that is consistent with its Open Source conditions.

The Direct runtime is maintained as a visible public fork and has its own source provenance. Whether any Direct runtime executable is eligible for the project certificate must be agreed with SignPath before such a binary is added to the signing scope.

Unsigned upstream binaries may be included inside a signed first-party installer where SignPath policy and the applicable third-party licenses permit this.

## Privacy

The project privacy policy is [PRIVACY.md](PRIVACY.md). AI Director is designed for local operation. External network activity used for update checks, managed dependency updates, and user-requested downloads is described there.

Third-party components and licenses are documented in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Artifact metadata

For any artifact signed through SignPath, the approved artifact configuration must enforce the project name `DaVinci Resolve AI Director` in product-name metadata. Product and file version metadata covered by the signing configuration must use the same release version within each build.

Upstream and vendor binaries that are outside the project signing scope must not inherit the AI Director project signature or project metadata restrictions.

## Algorithms and timestamps

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

A production signature must be traceable to the approved source repository, source revision, build configuration, and signing request. Local ad hoc signing is not an accepted production path.

## SmartScreen

Trusted signing can improve publisher reputation, but it does not guarantee that every new binary will avoid SmartScreen warnings. Self-signed certificates are development and testing tools and do not provide normal Windows publisher trust.

Unsigned releases must therefore be clearly identified and checksum-verifiable.

## User verification

Users should verify release artifacts as described in [Release Verification](docs/release/RELEASE_VERIFICATION.md).

## Product metadata and certificate identity

The Windows PE `CompanyName` and installer `Publisher` identify the product or project. They are not the Authenticode certificate subject.

Signing configuration must be bound to the certificate actually used. Do not infer or preconfigure certificate identity from the product metadata string.
