# AI Director — repository agent instructions

These instructions apply to work in this repository. They express durable rules, not the current engineering gate. Live versions, commits, release status, candidate identity, hashes and active next actions must be re-read for each relevant task.

## Authority and continuation

- This is an existing Windows/Electron/llama.cpp/MCP engineering project. Inspect the current tree and trace relevant control flow/state transitions/mutation boundaries/runtime ownership/failure recovery before designing changes.
- Published product source authority is the current public GitHub repository `nikolaoskalomiris/davinci-resolve-ai-director`, its current tracked source, current refs/tags/releases, and exact release assets/provenance. The accepted release tag and later `main` maintenance must be tracked as separate authorities. Never infer that `main` and a release tag must point to the same commit.
- The local continuity mirror is `C:\AI\SoR Continuity`. It is useful orientation, not product-source authority or canonical ChatGPT Library access. Do not mutate it. OpenHands cannot read ChatGPT Library by default; be transparent when only the local mirror was available.
- At task start, inventory the continuity directory as it exists now. Inspect its actual manifest and validator, read the manifest-declared current members and journal head, and validate local coherence if the validator is read-only. Do not assume a bootstrap filename. A validator pass cannot establish current GitHub/Drive freshness.
- Verify this checkout by `git rev-parse --show-toplevel`, `git remote -v`, branch, HEAD/tree, and clean/dirty/untracked path identity. Do not infer that a generated per-conversation workspace is this repository.
- The Google Drive mirror is operator-maintained secondary material. Do not modify it; assume it can be stale.

## Canonical machine locations and boundaries

- Long-lived clean working clone: `C:\AI\davinci-resolve-ai-director`.
- Frozen accepted/reference Builder: `C:\AI\AI-Director-Builder`; do not mutate unless explicitly reopened by the user.
- Retained release-candidate evidence: `C:\AI\AI-Director-Release-Candidates`; preserve existing contents.
- Disposable development and test work: unique directories under `%USERPROFILE%\Downloads` unless the user explicitly changes the topology.
- Local continuity mirror: `C:\AI\SoR Continuity`; read-only and secondary.
- The local OpenHands backend runs as the signed-in user and can be highly privileged. Do not run it elevated. Configured access to `C:\AI`, `%USERPROFILE%\Downloads`, `%LOCALAPPDATA%`, `%APPDATA%`, `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins`, or `%USERPROFILE%\.lmstudio\models` does not imply blanket authorization to change everything there. OS ACLs still apply.
- Keep model files under `%USERPROFILE%\.lmstudio\models` read-only. Do not bypass a ProgramData ACL denial by elevating; report the limitation and request authorization if a machine-scoped write is necessary.

## Mutation and release safety

- Default to read-only inspection. Before consequential mutation, identify exact current behavior, durable invariants, threat/failure model, smallest planned changed-path set, rollback/recovery, and test/acceptance evidence.
- Prototype risky changes in a disposable Downloads workspace. Verify inputs and hashes before mutation, stop at the first failed gate, preserve evidence/rollback material, then verify exact post-change state and path set.
- No commit, push, PR, release publication, tag movement, accepted-authority change, semantic-version preparation, installer promotion or installed-runtime mutation without explicit user authorization for that action. Never retag/rewrite accepted history to absorb maintenance changes.
- Do not declare a behavior accepted unless the exact candidate was exercised and the evidence proves it. User-operated GUI/install/inference gates can only be claimed PASS when the user ran them or direct evidence proves them.
- Never weaken fail-closed compatibility, hash/provenance binding, update transactionality, rollback, explicit tool authorization, runtime ownership or active-runtime mutation protection without an explicit product-policy change and independent validation.
- Do not mutate Google Drive.

## Engineering/tooling discipline

- Prefer Python for diagnostics, mutation, packaging and orchestration; use repository-owned Python where applicable, `-B`, and `PYTHONDONTWRITEBYTECODE=1`. Use explicit argv arrays, separately captured stdout/stderr, immediate return-code checks, explicit UTF-8 and exact pre/post hashes.
- Keep PowerShell 5.1 thin. Avoid durable reliance on `$LASTEXITCODE`, native stderr interactions with `$ErrorActionPreference='Stop'`, scalar/array shape assumptions, brittle collection binder behavior, implicit conversions, default BOM/encoding, nested quoting, and trimming `git status --porcelain` when status columns matter. Prefer `git diff --name-only` plus `git ls-files --others --exclude-standard` for path identity.
- Use platform-aware path joining. A forward slash in a Windows drive path is not proof of a Linux process; verify runtime/path behavior before concluding a path defect.
- Do not infer success from console text. Validate return codes and expected output/state. Preserve temporary evidence before packaging or cleanup. Do not extract arbitrary installer formats with a generic archive tool.
- Validate runner syntax, anchors, forbidden operations, exact mutation scope, argument handling, fail-closed paths and evidence output before delivery.

## Secret and privacy rules

- The user never sends a real provider/API key through ChatGPT. Secrets are entered locally through the product's intended protected credential path. Never persist secret plaintext in source, prompts, Memory, continuity, evidence, settings, generated config, logs, diagnostics or command lines.
- Keep environment exposure least-privilege across Electron, backend, server parent, provider child and unrelated/Resolve children. Do not claim isolation without direct evidence.
- Optional provider/network capability must not silently change a local-only default or auto-authorize arbitrary tools. Review current provider source, package, license, terms, pricing/privacy and retention conditions before shipping external integration behavior.

## Current state discipline

Do not store active gates, release versions, hashes, commits, candidate names or “next actions” as permanent repository-agent facts. For every substantive task, derive them from current continuity evidence and independently refresh the live public repository/tag/release state. If sources conflict, state the conflict and follow the higher-authority direct evidence; do not silently reconcile.
