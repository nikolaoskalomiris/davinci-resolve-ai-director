# Release Provenance

## Authority model

AI Director separates:

- source/build input authority;
- semantic target preparation;
- release-candidate build attempt;
- installed/live validation;
- explicit acceptance promotion;
- public distribution.

A build is not automatically an accepted release.

## Accepted 0.3.25 engineering authority

The accepted candidate is:

```text
version:                    0.3.25
candidate:                  static-build-001
main Setup SHA256:          4253D3A4201E7797BC2EF286BDAB3B1B053C578B7667FA2B80ED27205A8A4077
Integration Setup SHA256:   7CA2E825983BFEAC27551C1E8BFBB76F5C858B8756CF46D5ACAF21F16067F456
static build report SHA256: B4CB67B7D9AE14BFF0DF0E7A9558B6331AFDD651E9351560167437DBF23A7E42
Direct build report SHA256: EC6681903839746282133B224A8CA0F8D0876934D97D14A942D420D27C50E8F9
Upstream report SHA256:     A224969AAA3B91B406E18BC3D6DFC0B486F408EBEE9BB933ED9FC2B6D3BF51F8
source runtime report:      D3FAD1907859CB51C685912A016AFDC83B2EAC50CD880BE694F1845E5D3B09B1
source runtime archive:     46495AD261F70DEB77B63D66194C24A408E03A220E59DAA03AD4FFE89F666DA3
final application ASAR:     A68A7A1B8C2F2AAD0E79FB61C1D6780C207DF8BC06F55740991F3930746FBA15
acceptance promotion:       EA3DE64BC3B4F3C860E0AADDA4990AA62671C00BEB34A151D3C0168B95589CCA
accepted release-state:     2A6694144A4393FE5954E3A38A3CE4AEA88C2D3B641245E510720BC43E4D97F6
canonical source manifest:  E177D2FB20C9F52F4820C0A648EF21745790C0BDBB940F2FC79971050D48C80D
```

Acceptance was a separate live-attested promotion after clean installation and functional validation. The repository state is `ACCEPTED_READY`; this does not by itself mean a GitHub Release has already been published.

## Source-built runtime evidence

The release build produces independent evidence for:

- the pinned Direct source commit/tree and Direct build report;
- the reconstructed Upstream source tree and Upstream build report;
- the generated dual-server runtime-stack archive;
- the shared CUDA payload identities;
- final application/installer hashes and ASAR/source parity.

The candidate runtime-stack report records `accepted_runtime_stack_archive_consumed=false`. Historical accepted runtime bytes remain comparison/release authority and are not silently reused as normal server build inputs.

## Direct source authority

```text
repository: nikolaoskalomiris/llama-cpp-flashnext-direct
commit:     c8f321699adbd0035c8c755bdefcb4182705262b
tree:       a17cf64683bc6877e2dbc4e0b4ef8933106257fb
```

Public reproducibility must pin the immutable accepted commit/tree, not a mutable branch.

## Upstream source authority

```text
repository:              unslothai/llama.cpp
accepted source tree:    edd784f1d459cd39f2605ccf66adc0c79ef75a93
runtime source identity: b7eb4a03a1285c50ebe86c6bd2fc7a70c6f7214d
source asset SHA256:     CBD0E8C756DA5B2F46DF4DDACDED46C7733316C44D86A1A5D176FE3ADE7B0675
```

The visible historical release tag is not treated as the sole immutable source authority; the concrete source asset and reconstructed tree are bound independently.

## Installed-product updater provenance

For managed Upstream updates, the visible release tag is a display/locator identity. The transaction binds the concrete GitHub release ID, asset ID/name, reported digest and byte size, then verifies the downloaded SHA-256.

MCP updates independently bind their source/compatibility state and require a live Resolve canary before finalization.

The accepted first-release MCP seed is 4.10.4. A dependency-changing MCP candidate is intentionally refused before mutation when the accepted immutable dependency/runtime image cannot satisfy the candidate contract. Such a candidate requires a new validated compatibility bundle/runtime image rather than a hash-only override.

## Signing provenance

Signing changes PE bytes. Preserve both identities:

```text
UNSIGNED_BUILD_SHA256=<deterministic build identity>
SIGNED_RELEASE_SHA256=<post-signing distribution identity>
```

Never overwrite the deterministic unsigned build hash with a later signed hash.

A signed public release should preserve the certificate subject, chain-verification result and timestamp evidence in addition to the post-signing SHA-256.

## Public release checksums

The GitHub Release must publish SHA-256 for every distributed installer/archive. Users can verify them using [RELEASE_VERIFICATION.md](RELEASE_VERIFICATION.md).

GitHub upload itself is not proof of reproducibility. The final public source path must also be proven by Gate 6D from a literal fresh tagged checkout with no pre-existing generated inputs/toolchain, private credentials/history/continuity, accepted Builder workspace or installed-product dependency.
