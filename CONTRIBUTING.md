# Contributing

Thank you for considering a contribution to DaVinci Resolve AI Director.

## Before opening a change

- Keep changes focused and reviewable.
- Do not commit secrets, tokens, personal machine paths, private media, project databases, model files, installer outputs, runtime caches, release-candidate binaries or local toolchain caches.
- Preserve third-party copyright/license notices.
- Do not add a dependency whose license is unknown or incompatible with the repository/release policy.
- Do not treat generated Direct/Upstream server binaries as source inputs; server payloads are built from their pinned source authorities.
- Changes that alter application/package/installer bytes must follow the project's version/build/acceptance lifecycle rather than silently modifying an accepted release.

## Build and test documentation

Read [docs/build/BUILDING.md](docs/build/BUILDING.md) before changing build controls. The public bootstrap/build path is implemented and has passed from a clean generated-state start, but it still requires the documented external Windows system toolchain. Do not describe it as zero-prerequisite. Final first-release reproducibility is established only by the post-publication Gate 6D literal fresh-clone/tag build.

User-visible behavior changes should update the relevant documentation in the same change where practical.

## License of contributions

Unless explicitly stated otherwise for a separately licensed file, contributions submitted to this repository are intended to be licensed under the repository's Apache-2.0 license.

Do not submit code that you do not have the right to license under those terms.

Third-party source retained for provenance/normalization keeps its original license and authorship.

## Security

Security-sensitive findings should follow [SECURITY.md](SECURITY.md), not a public issue containing exploit details.
