# Contributing

Thank you for considering a contribution to DaVinci Resolve AI Director.

## Before opening a change

- Keep changes focused and reviewable.
- Do not commit secrets, tokens, personal machine paths, private media, project databases, model files, installer outputs, runtime caches, release-candidate binaries or local toolchain caches.
- Preserve third-party copyright and license notices.
- Do not add a dependency whose license is unknown or incompatible with the repository policy.
- Do not treat generated Direct/Upstream server binaries as source inputs; those payloads are built from pinned source authorities.
- Changes that alter application, runtime, package or installer bytes must follow the project's version/build/acceptance lifecycle rather than silently changing accepted release authority.
- Update user-facing documentation when behavior or requirements change.

## Build and test documentation

Read [docs/build/BUILDING.md](docs/build/BUILDING.md) before changing build controls. The project bootstrap manages its own downloaded tools and inputs, but the documented Windows compiler/CUDA toolchain remains an external prerequisite.

Reproducibility claims require a clean public source/tag checkout using only public inputs plus the documented external prerequisites.

## License of contributions

Unless explicitly stated otherwise for a separately licensed file, contributions submitted to this repository are intended to be licensed under the repository's Apache-2.0 license.

Do not submit code that you do not have the right to license under those terms. Third-party source retained for provenance or normalization keeps its original license and authorship.

## Security

Security-sensitive findings should follow [SECURITY.md](SECURITY.md), not a public issue containing exploit details.
