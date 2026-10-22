# Local Models

AI Director runs local GGUF models. It can discover models from LM Studio-compatible folders, but the LM Studio application itself is not required.

## Model folders

AI Director scans:

```text
%USERPROFILE%\.lmstudio\models
%USERPROFILE%\.cache\lm-studio\models
```

If the `lms` CLI is available, AI Director may use its local catalog metadata. Otherwise it discovers models directly from the filesystem.

Only primary `.gguf` files are shown as selectable models. Auxiliary draft/MTP/mmproj files and non-primary multipart pieces are not listed as separate primary models.

## Support levels

### Qwen3.8 Flash Next

This is the preferred tested path. A compatible MTP draft GGUF must be present beside the primary model for the Flash Next profile to be available.

### Qwen3.6-35B-A3B

AI Director includes dedicated handling for this model family, but it is treated as a candidate support path rather than the preferred tested profile.

### Other GGUF models

Other primary GGUF files may appear as **Local GGUF** models. These are not automatically validated simply because they were discovered.

Compatibility can depend on architecture, chat template, tool use, context behavior and memory requirements.

## Memory and context

RAM/VRAM needs depend on model size, quantization, context length, KV-cache settings, GPU-layer placement and other tuning choices. There is no single memory requirement that applies to every GGUF model.

If startup fails after increasing context or other tuning values, reduce those settings and retry.

## Obtaining models

Use GGUF files from a source you trust and follow the model's own license. AI Director's Apache-2.0 license does not relicense model weights.
