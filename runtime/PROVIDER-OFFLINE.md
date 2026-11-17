# Brave provider offline prototype

## Scope and status

VERIFIED: offline byte validation and fresh-output staging only. This module neither acquires nor executes the provider. No build, installer, lifecycle controller, Node, npm, credentials or provider API is involved. This is not LIVE_ACCEPTED product/install behavior.

The public acquisition route remains an explicit UNVERIFIED gap. No reviewed public bundle URL/size/hash acquisition contract or implemented public source reconstruction exists here. There is no invented download URL, automatic fallback, runtime package install, or silent use of a Downloads recovery path. Missing explicit input fails with the gap message.

## API and CLI

```python
validate_provider(root, provenance_root=DEFAULT_PROVENANCE_ROOT)
stage_provider(input_root, output_root)
```

`DEFAULT_PROVENANCE_ROOT` is repository-relative `provenance/runtime/providers/brave-search/2.1.4`, not the canonical working clone or a machine-specific Downloads path. An alternate provenance root must satisfy the same independently hardcoded metadata pin. `stage_provider` intentionally has exactly two arguments.

```text
python -B runtime/provider_control.py validate --input EXPLICIT_LOCAL_TREE
python -B runtime/provider_control.py stage --input EXPLICIT_LOCAL_TREE --output FRESH_OUTPUT
python -B runtime/test_provider_control.py
python -B runtime/test_provider_control.py --actual-input EXPLICIT_LOCAL_TREE --actual-output FRESH_OUTPUT
```

Success returns/prints structured evidence. CLI failure returns 1; argument syntax failure returns 2. No mutation occurs before complete input validation. Output parent must already exist. Existing output, overlap, unsafe names, links/reparse points in ancestors or tree, hardlinks, special files, case collisions, missing/extra files, extra directories and byte/hash drift fail closed. There are no basename exclusions, including Cache, Logs or Updates.

Staging copies to an exclusively created sibling operation directory, flushes each file, revalidates that complete payload and promotes by Windows no-replace directory rename. Never merge or replace an existing output. Failed copy/validation/promotion removes only the operation-owned staging tree; unrelated state is preserved. A suspicious changed staging identity or link causes cleanup refusal and retained evidence instead of traversal. No output rollback is needed because existing outputs are never modified. Other platforms may validate; staging deliberately refuses platforms without the tested Windows rename contract.

Caller must keep input, provenance and output-parent trees quiescent. This is not protection against a malicious process concurrently replacing filesystem ancestors, an OS sandbox, a durable power-loss transaction, installed-runtime ownership arbitration or an installer hook. Do not use this fresh-output staging API as active-runtime replacement.

## Independent pins and provenance

- 3,589 core files, 15,914,748 core bytes; runtime has 3,590 files including the manifest.
- Core JSONL digest: `f8bd1c72fce849e56737258cd2396b80b227e30adfba00574b485bfdd49ebebe`.
- Exact manifest digest: `c30427caa6ddf5c71d096645fd9a78155c8dd29e529f95221dc2015b20f1773b`.
- Metadata index digest: `10aa8a310b71a597a4438a44c311814af9e9059badc26ab2d9e3bee9a9464e53`.

The module hard-pins all three identities plus count, bytes, source commit/tree/version and entrypoint. Rewriting a manifest beside changed code cannot authorize another tree. `METADATA-FILES.jsonl` binds all 106 other provenance files (107 total), including the contract, manifest, inventory, source package/lock/LICENSE, registry metadata and supplemental license copies. Original source and retained recovery metadata bytes are preserved. Historical absolute toolchain paths in recovery provenance are evidence only and never operational inputs. Its recorded historical test results were not rerun by this module.

The file inventory algorithm excludes directories by definition, not by directory name: sorted POSIX paths, compact UTF-8 JSONL records with key order path,size,sha256, lowercase hashes and LF termination. Inspection also found three legitimate empty pruned scope directories: `node_modules/@esbuild`, `node_modules/@nodelib`, `node_modules/@types`. These are independently pinned in code, required and copied. No unexpected directory is allowed.

Provider source is MIT; see `upstream/LICENSE` and `licenses/PROVIDER-LICENSE`. The 96 production package roots and license evidence are in `packages-and-licenses.json` and `licenses/`; original runtime licenses remain in the exact core inventory. This is not legal advice or shipping approval of Brave service terms, pricing, privacy or retention. Retained registry artifacts do not eliminate the documented 104 upstream lock integrity/resolved omissions. Two retained cache reconstructions do not establish historical B2 artifact identity or complete public reproducibility.

## Executed prototype gates

VERIFIED: 27 tiny synthetic regression tests passed, including invalid inventory paths/fields, duplicate/case collisions, missing/extra/changed bytes, manifest-plus-code tampering, metadata binding, hardlink and actual Windows junction rejection, copy/promotion/staged-corruption failures, destination races, unrelated staging preservation and missing-input gap reporting. Synthetic pins are patched only within tests; production pins remain unchanged.

VERIFIED: actual repaired 3,589-file candidate validated, copied to fresh isolated output, and input/output independently revalidated. Exact core and manifest hashes held before and after; actual candidate was not modified. All three Hono cache files survived:

- `node_modules/hono/dist/cjs/middleware/cache/index.js`
- `node_modules/hono/dist/middleware/cache/index.js`
- `node_modules/hono/dist/types/middleware/cache/index.d.ts`

Evidence is retained in the isolated integration workspace's `provider-offline-evidence/TEST-RESULT.json`, with staged tree at `provider-offline-evidence/staged-provider`. The initial overly strict directory check failed on the three inspected empty scope directories; it was corrected with exact pins, not exclusions or inventory rebasing. An initial provenance import stopped on an incorrect assumed upstream package path; inspection located the commit-named upstream directory before continuing. Neither diagnostic failure changed the candidate.

DEFERRED: public reconstruction/acquisition implementation, build/installer join, installed ownership/rollback, application config/STDIO tests and live GUI/service acceptance. These tests do not authorize or imply those gates. Canonical checkout, local continuity mirror, Builder and installed runtime remain untouched by this work.
