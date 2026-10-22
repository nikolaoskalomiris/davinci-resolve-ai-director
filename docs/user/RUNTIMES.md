# Direct and Upstream Runtimes

AI Director provides two llama.cpp-derived runtime profiles.

## Direct

**Direct** is the pinned product runtime.

Choose Direct when you want the runtime version validated and shipped with the AI Director release. Ordinary Upstream updates do not modify Direct.

## Upstream

**Upstream** is the independently updateable runtime.

Choose Upstream when you want the managed updater to install compatible newer Upstream runtime builds after integrity and health checks.

## Shared CUDA

Direct and Upstream share AI Director's managed CUDA runtime. Ordinary Upstream updates do not replace that shared CUDA payload.

The machine CUDA Toolkit is relevant to source builds only; installed AI Director uses its managed runtime libraries.

## Which profile should I use?

Use **Direct** as the predictable default.

Use **Upstream** if you specifically want the independently updateable runtime lane.

Both profiles use the selected local model configuration. Switching profiles does not duplicate or relicense your model files.

For source identities and build provenance, see [Release Provenance](../release/RELEASE_PROVENANCE.md). For update behavior, see [Updater and Rollback](UPDATER_AND_ROLLBACK.md).
