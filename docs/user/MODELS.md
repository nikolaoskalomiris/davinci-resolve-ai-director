# Local Models

AI Director is built for local GGUF inference. It discovers models from LM Studio-compatible user directories but does not require the LM Studio application to own or run the inference server.

## Discovery roots

AI Director recursively scans:

```text
%USERPROFILE%\.lmstudio\models
%USERPROFILE%\.cache\lm-studio\models
```

If an `lms` CLI is available, AI Director may use its catalog metadata in addition to filesystem discovery. If it is unavailable, model discovery falls back to the filesystem.

Only `.gguf` files are considered. Auxiliary files such as MTP/draft/mmproj GGUFs are not listed as standalone primary models, and non-primary pieces of multipart GGUFs are not listed separately.

## Model support levels

Discovery is not the same thing as validation.

### Qwen3.8 Flash Next

AI Director has a dedicated `flash_next_mtp` recipe and treats this family as the preferred tested path. A compatible MTP draft GGUF must be present beside the primary model for this profile to be available.

### Qwen3.6-35B-A3B

AI Director has a dedicated MoE recipe for this family. The current source classifies it as a **candidate** support path rather than the preferred tested profile.

### Other GGUF models

Other primary GGUF files may appear as **Local GGUF** models using a generic recipe. The source marks this class **unvalidated**. A model appearing in the list is therefore not a promise that its architecture, chat template, tool use, context behavior or memory footprint has been validated by the project.

## Context and memory

The effective memory requirement depends on model size, quantization, context length, KV-cache choices, GPU-layer placement and other tuning settings. AI Director therefore does not publish a single RAM/VRAM number that is valid for every discovered GGUF.

The application exposes context and tuning controls, but values beyond what a model/runtime can support can fail at startup or exhaust system/GPU memory.

## Obtaining models

Models can come from repositories or model hosts such as Hugging Face, provided the files are compatible GGUFs and comply with their own licenses. AI Director does not imply compatibility with every model available from any host.

Keep model license terms with the model itself; the AI Director Apache-2.0 license does not relicense model weights.
