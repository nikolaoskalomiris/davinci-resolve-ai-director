# Direct and Upstream Runtimes

AI Director ships two llama.cpp-derived server profiles that intentionally have different ownership and update policies.

## Direct

**Direct** is the pinned product runtime lane.

Current source authority:

- repository: `nikolaoskalomiris/llama-cpp-flashnext-direct`;
- accepted immutable commit: `c8f321699adbd0035c8c755bdefcb4182705262b`;
- accepted tree: `a17cf64683bc6877e2dbc4e0b4ef8933106257fb`.

The installed runtime identifies Direct as the custom AI Director llama.cpp runtime. Ordinary Upstream updates do not modify it.

## Upstream

**Upstream** is the independently updateable runtime lane.

The accepted 0.3.25 source identity is reconstructed from the Unsloth llama.cpp source authority and is bound to:

- repository: `unslothai/llama.cpp`;
- accepted reconstructed source tree: `edd784f1d459cd39f2605ccf66adc0c79ef75a93`;
- accepted runtime source identity: `b7eb4a03a1285c50ebe86c6bd2fc7a70c6f7214d`.

The installed Upstream root is transactionally replaceable by the managed updater after compatibility, integrity and live-health checks.

## Shared CUDA

Direct and Upstream share the product's CUDA 13.3.1 runtime lane. Ordinary Upstream updates must not replace the shared CUDA payload.

The current shared payload contains the NVIDIA redistributable runtime libraries required by the accepted stack, including `cudart64_13.dll`, `cublas64_13.dll` and `cublasLt64_13.dll`.

For source builds, those shipping DLLs are extracted from pinned official NVIDIA CUDA 13.3.1 redistributable archives. They are not copied from the machine CUDA Toolkit; the Toolkit is an external compiler/inspection prerequisite.

## Source builds versus installed-product updates

These are separate paths:

- **Source build:** constructs both Direct and Upstream server shipping sets from pinned source authorities, then assembles a candidate runtime stack with shared CUDA.
- **Installed-product Upstream update:** downloads a compatible Upstream runtime release asset, verifies its concrete release/asset identity and SHA-256, stages and preflights it, then swaps only the Upstream lane.

Historical accepted Direct/Upstream server binaries may be retained for release comparison/provenance, but they are not normal clean-build inputs.

## Choosing a profile

Use Direct when you want the pinned product runtime behavior. Use Upstream when you want the updater-managed runtime line and its independent update path.

Changing profiles does not relicense or duplicate your model files; both profiles operate against the selected local model configuration.
