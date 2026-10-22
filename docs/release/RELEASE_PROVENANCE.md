# Release Provenance

This document is intentionally version-specific. User installation instructions should link to the latest GitHub Release instead of copying the identities below.

## Authority model

AI Director separates:

- source/build input authority;
- semantic version preparation;
- release-candidate build;
- installed/live validation;
- explicit acceptance promotion;
- public distribution.

A successful build is not automatically an accepted or published release.

## Published 0.3.25 release

The first public release is bound to:

```text
tag:                       0.3.25
tag object:                4ef3e98394f9d252fd92c59e59bbffe221cafe9f
release source commit:     6beb84b5199aad89fb4769cad25a187cdfa060b0
release source tree:       afda74ad5c27b54e8d140bd886ce5226127cf599
GitHub Release ID:         420777066
signing state:             unsigned
accepted candidate:        static-build-001
main Setup SHA256:         4253D3A4201E7797BC2EF286BDAB3B1B053C578B7667FA2B80ED27205A8A4077
Integration Setup SHA256:  7CA2E825983BFEAC27551C1E8BFBB76F5C858B8756CF46D5ACAF21F16067F456
```

Accepted build evidence:

```text
static build report:       B4CB67B7D9AE14BFF0DF0E7A9558B6331AFDD651E9351560167437DBF23A7E42
Direct build report:       EC6681903839746282133B224A8CA0F8D0876934D97D14A942D420D27C50E8F9
Upstream build report:     A224969AAA3B91B406E18BC3D6DFC0B486F408EBEE9BB933ED9FC2B6D3BF51F8
source runtime report:     D3FAD1907859CB51C685912A016AFDC83B2EAC50CD880BE694F1845E5D3B09B1
source runtime archive:    46495AD261F70DEB77B63D66194C24A408E03A220E59DAA03AD4FFE89F666DA3
final application ASAR:    A68A7A1B8C2F2AAD0E79FB61C1D6780C207DF8BC06F55740991F3930746FBA15
acceptance promotion:      EA3DE64BC3B4F3C860E0AADDA4990AA62671C00BEB34A151D3C0168B95589CCA
accepted release-state:    2A6694144A4393FE5954E3A38A3CE4AEA88C2D3B641245E510720BC43E4D97F6
canonical source manifest: E177D2FB20C9F52F4820C0A648EF21745790C0BDBB940F2FC79971050D48C80D
```

Post-release documentation commits may advance `main`; they do not change the immutable release tag or accepted release artifacts.

## Release metadata assets

The published release currently carries:

```text
RELEASE-MANIFEST-0.3.25.json
SHA256 E00237FCF4A062E084AD994DE5943CCB32E76E8719F0C20EF2B18C5DD15D4931

SHA256SUMS-0.3.25.txt
SHA256 08FA19CE5928C713CF2EDBC87B1C9CAF63563D4DD3D84B24BED40A9B78FD6FC3
```

The manifest records both accepted local build-artifact names and the corresponding GitHub Release asset names.

## Direct source authority

```text
repository: nikolaoskalomiris/llama-cpp-flashnext-direct
commit:     c8f321699adbd0035c8c755bdefcb4182705262b
tree:       a17cf64683bc6877e2dbc4e0b4ef8933106257fb
```

Public builds pin the immutable commit/tree, not a mutable branch.

## Upstream source authority

```text
repository:              unslothai/llama.cpp
accepted source tree:    edd784f1d459cd39f2605ccf66adc0c79ef75a93
runtime source identity: b7eb4a03a1285c50ebe86c6bd2fc7a70c6f7214d
source asset SHA256:     CBD0E8C756DA5B2F46DF4DDACDED46C7733316C44D86A1A5D176FE3ADE7B0675
```

The concrete source asset and reconstructed tree are bound independently of any mutable branch name.

## Runtime and updater provenance

Release builds preserve evidence for:

- Direct and Upstream source identities;
- the source-built dual-server runtime stack;
- shared CUDA payload identities;
- packaged application/source parity;
- installer hashes and acceptance promotion.

Installed Upstream updates bind a concrete release/asset identity and checksum before staging. MCP updates use a separate compatibility transaction and require a live Resolve canary before finalization.

Dependency-changing MCP candidates are refused when the accepted immutable dependency image cannot satisfy their contract; support requires a new validated compatibility bundle rather than a hash-only override.

## Signing provenance

Signing changes PE bytes. Preserve both identities when signing is introduced:

```text
UNSIGNED_BUILD_SHA256=<deterministic build identity>
SIGNED_RELEASE_SHA256=<post-signing distribution identity>
```

Do not overwrite the deterministic unsigned build identity with a later signed hash.

## Reproducibility

Publishing installers is not, by itself, a reproducibility proof. Reproducibility validation should build the exact public release tag from a fresh checkout using only public bound inputs and the documented external toolchain prerequisites.

See [Release Verification](RELEASE_VERIFICATION.md) and [Building from Source](../build/BUILDING.md).
