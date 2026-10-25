const { app, BrowserWindow, ipcMain, Menu, clipboard, dialog, shell } = require('electron');
const { spawn, execFile } = require('child_process');
const crypto = require('crypto');
const path = require('path');
const os = require('os');
const fs = require('fs');
const http = require('http');
const ProductPaths = require('./ProductPaths');
const UpdateManager = require('./UpdateManager');

const HOST_MODE = String(process.env.DAVINCI_RESOLVE_AI_DIRECTOR_HOST_MODE || 'standalone').trim().toLowerCase();
if (!['standalone', 'resolve'].includes(HOST_MODE)) {
    throw new Error(`Unsupported AI Director host mode: ${HOST_MODE}`);
}

// Standalone AI Director owns one desktop-controller instance at a time.
// Resolve-host mode deliberately keeps the accepted plugin behavior unchanged;
// the Resolve-side launcher/bridge conversion is a separate later gate.
const standaloneInstanceLock = HOST_MODE === 'standalone'
    ? app.requestSingleInstanceLock()
    : true;
if (!standaloneInstanceLock) {
    app.quit();
}

let WorkflowIntegration = null;
if (HOST_MODE === 'resolve') {
    WorkflowIntegration = require('./WorkflowIntegration.node');
}

const PLUGIN_ID = 'com.aidirector.davinciresolve';

const VFX_PYTHON = ProductPaths.resolvePythonExecutable;
const VFX_HOST = ProductPaths.resolveHost;
const VFX_ROOT = ProductPaths.backendRoot;
const CUDA_RUNTIME_ROOT = ProductPaths.commonCudaRoot;
const MCP_ROOT = ProductPaths.resolveMcpRoot;
const MCP_PYTHON_ROOT = ProductPaths.resolveMcpPythonRoot;
const MCP_PYTHON = ProductPaths.resolveMcpPythonExecutable;
const MCP_LIVE_SERVER = path.join(MCP_ROOT, 'src', 'server.py');
const MCP_ADVANCED_BIN = path.join(MCP_ROOT, 'bin', 'davinci-resolve-advanced-mcp.mjs');
const MCP_ADVANCED_PACKAGE = path.join(MCP_ROOT, 'resolve-advanced', 'package.json');
const MCP_ADVANCED_NODE_MODULES = path.join(MCP_ROOT, 'resolve-advanced', 'node_modules');
const MCP_ADVANCED_SHARP_NATIVE = path.join(
    MCP_ADVANCED_NODE_MODULES,
    '@img',
    'sharp-win32-x64',
    'lib',
    'sharp-win32-x64-0.35.4.node'
);
const MCP_ADVANCED_SQLITE_NATIVE = path.join(
    MCP_ADVANCED_NODE_MODULES,
    'better-sqlite3',
    'build',
    'Release',
    'better_sqlite3.node'
);
const NODE_EXE = ProductPaths.resolveNodeExecutable;
const NPM_CLI = ProductPaths.resolveNpmCli;

const CUDA_RUNTIME_FILES = Object.freeze([
    'cudart64_13.dll',
    'cublas64_13.dll',
    'cublasLt64_13.dll'
]);

const CUDA_MINIMUM_NVIDIA_DRIVER_MAJOR = 580;
const CUDA_SUPPORTED_COMPUTE_CAPABILITIES = new Set([
    '7.5', '8.0', '8.6', '8.9', '9.0', '12.0', '12.1'
]);

const CUDA_ENVIRONMENT_KEYS = new Set([
    'CUDA_PATH',
    'CUDA_HOME',
    'CUDATOOLKIT_ROOT'
]);

const SERVER_PROFILES = Object.freeze({
    upstream: Object.freeze({
        id: 'upstream',
        label: 'Upstream',
        description: 'Updater-managed llama.cpp runtime',
        root: ProductPaths.upstreamRoot,
        exe: path.join(ProductPaths.upstreamRoot, 'llama-server.exe'),
        lazyMode: 'off',
        requiredRuntimeFiles: [
            'llama-server.exe',
            'llama-server-impl.dll',
            'llama.dll',
            'llama-common.dll',
            'ggml.dll',
            'ggml-base.dll',
            'ggml-cuda.dll',
            'mtmd.dll'
        ]
    }),
    direct: Object.freeze({
        id: 'direct',
        label: 'Direct',
        description: 'Custom AI Director llama.cpp runtime',
        root: ProductPaths.directRoot,
        exe: path.join(ProductPaths.directRoot, 'llama-server.exe'),
        lazyMode: 'on-direct',
        requiredRuntimeFiles: [
            'llama-server.exe',
            'llama-server-impl.dll',
            'llama.dll',
            'llama-common.dll',
            'ggml.dll',
            'ggml-base.dll',
            'ggml-cpu-x64.dll',
            'ggml-cpu-sse42.dll',
            'ggml-cpu-sandybridge.dll',
            'ggml-cpu-haswell.dll',
            'ggml-cpu-skylakex.dll',
            'ggml-cpu-cannonlake.dll',
            'ggml-cpu-cascadelake.dll',
            'ggml-cpu-icelake.dll',
            'ggml-cpu-alderlake.dll',
            'ggml-cuda.dll',
            'mtmd.dll'
        ]
    })
});

const USER_HOME = os.homedir();
const LM_STUDIO_MODEL_ROOTS = Object.freeze([
    path.join(USER_HOME, '.lmstudio', 'models'),
    path.join(USER_HOME, '.cache', 'lm-studio', 'models')
]);
const LM_STUDIO_CLI_CANDIDATES = Object.freeze([
    path.join(USER_HOME, '.lmstudio', 'bin', 'lms.exe'),
    path.join(USER_HOME, '.lmstudio', 'bin', 'lms'),
    'lms'
]);

const LEGACY_FLASH_MODEL_ID = 'flash-next-iq3-xxs';
const LEGACY_REJECTED_QWEN3_8B_ID = 'qwen3-8b-q8-xl';
const SETTINGS_SCHEMA_VERSION = 10;
const MIN_SUPPORTED_CONTEXT_LENGTH = 131072;
const MAX_SUPPORTED_OUTPUT_TOKENS = 32768;
const DEFAULT_TUNING_SETTINGS = Object.freeze({
    gpuLayers: null,
    cpuMoeLayers: null,
    kvCacheType: null,
    flashAttention: null,
    threads: null,
    batchThreads: null,
    batchSize: null,
    microBatchSize: null
});
const LLAMA_CPP_INFERENCE_DEFAULTS = Object.freeze({
    temperature: 0.8,
    topP: 0.95,
    topK: 40,
    minP: 0.05,
    presencePenalty: 0.0,
    repetitionPenalty: 1.0,
    promptCacheReuse: true
});
const QWEN36_PRECISE_INFERENCE_DEFAULTS = Object.freeze({
    temperature: 0.6,
    topP: 0.95,
    topK: 20,
    minP: 0.0,
    presencePenalty: 0.0,
    repetitionPenalty: 1.0,
    promptCacheReuse: true
});
const QWEN38_THINKING_INFERENCE_DEFAULTS = Object.freeze({
    temperature: 1.0,
    topP: 0.95,
    topK: 20,
    minP: 0.0,
    presencePenalty: 0.0,
    repetitionPenalty: 1.0,
    promptCacheReuse: true
});
const DEFAULT_APPEARANCE_SETTINGS = Object.freeze({
    skin: 'green'
});
const DEFAULT_FFMPEG_SETTINGS = Object.freeze({
    mode: 'disabled',
    ffmpegPath: null,
    ffprobePath: null
});
const FFMPEG_MODES = Object.freeze(new Set(['disabled', 'external']));
const FFMPEG_RECOMMENDED_URL = 'https://www.gyan.dev/ffmpeg/builds/';
const FFMPEG_PROBE_TIMEOUT_MS = 12000;
const FFMPEG_REQUIRED_FILTERS = Object.freeze([
    'silencedetect', 'bandpass', 'afade', 'aresample', 'ebur128', 'amerge', 'astats',
    'select', 'metadata', 'showinfo', 'blackdetect', 'idet', 'scale', 'pad', 'format',
    'lut3d', 'signalstats', 'crop'
]);
const FFMPEG_REQUIRED_DECODERS = Object.freeze([
    'h264', 'hevc', 'prores', 'aac', 'mp3', 'flac', 'png', 'pcm_s16le', 'pcm_s24le', 'pcm_f32le'
]);
const FFMPEG_REQUIRED_ENCODERS = Object.freeze([
    'png', 'prores_ks', 'rawvideo', 'pcm_s16le', 'pcm_s24le', 'pcm_f32le'
]);
const FFMPEG_REQUIRED_FORMATS = Object.freeze([
    'mov', 'matroska', 'mxf', 'mpegts', 'avi', 'wav', 'aiff', 'image2', 'null', 'rawvideo'
]);
const ALLOWED_SKINS = Object.freeze(new Set(['green', 'blue', 'purple', 'gray']));
const CONTEXT_OVERFLOW_POLICIES = Object.freeze(new Set(['rolling_window', 'stop_at_limit']));
const DEFAULT_CONTEXT_OVERFLOW_POLICY = 'rolling_window';
const DEFAULT_INFERENCE_SETTINGS = Object.freeze({
    // null means use the verified default profile for the selected model.
    temperature: null,
    topP: null,
    topK: null,
    minP: null,
    presencePenalty: null,
    repetitionPenalty: null,
    promptCacheReuse: true
});
const DEFAULT_PERSISTENT_SETTINGS = Object.freeze({
    schemaVersion: SETTINGS_SCHEMA_VERSION,
    setupCompleted: false,
    serverProfile: null,
    modelProfile: null,
    runtime: Object.freeze({
        contextLength: 131072,
        maxOutputTokens: 16384,
        timeoutSeconds: 43200,
        contextOverflowPolicy: DEFAULT_CONTEXT_OVERFLOW_POLICY
    }),
    tuning: DEFAULT_TUNING_SETTINGS,
    inference: DEFAULT_INFERENCE_SETTINGS,
    appearance: DEFAULT_APPEARANCE_SETTINGS,
    ffmpeg: DEFAULT_FFMPEG_SETTINGS,
    primeExecutionCache: true
});

let persistentSettings = {
    schemaVersion: SETTINGS_SCHEMA_VERSION,
    setupCompleted: false,
    serverProfile: null,
    modelProfile: null,
    runtime: {
        contextLength: DEFAULT_PERSISTENT_SETTINGS.runtime.contextLength,
        maxOutputTokens: DEFAULT_PERSISTENT_SETTINGS.runtime.maxOutputTokens,
        timeoutSeconds: DEFAULT_PERSISTENT_SETTINGS.runtime.timeoutSeconds,
        contextOverflowPolicy: DEFAULT_PERSISTENT_SETTINGS.runtime.contextOverflowPolicy
    },
    tuning: { ...DEFAULT_TUNING_SETTINGS },
    inference: { ...DEFAULT_INFERENCE_SETTINGS },
    appearance: { ...DEFAULT_APPEARANCE_SETTINGS },
    ffmpeg: { ...DEFAULT_FFMPEG_SETTINGS },
    primeExecutionCache: DEFAULT_PERSISTENT_SETTINGS.primeExecutionCache
};
let ffmpegRuntimeStatus = {
    mode: 'disabled',
    state: 'disabled',
    available: false,
    ffmpegPath: null,
    ffprobePath: null,
    ffmpegVersion: null,
    ffprobeVersion: null,
    ffmpegSha256: null,
    ffprobeSha256: null,
    capabilities: null,
    missingRequirements: [],
    error: null
};
let settingsLoadError = null;
let settingsApplyInProgress = false;
let selectedServerProfileId = 'upstream';
let modelCatalog = new Map();
let modelCatalogRefreshPromise = null;
let modelCatalogInfo = {
    roots: [...LM_STUDIO_MODEL_ROOTS],
    source: 'not-scanned',
    cliAvailable: false,
    discoveredCount: 0,
    rejectedCount: 0,
    warning: null,
    refreshedAt: null
};

function getSelectedServerProfile() {
    return SERVER_PROFILES[selectedServerProfileId] || SERVER_PROFILES.upstream;
}

function getSelectedModelProfile(settings = persistentSettings) {
    const id = String(settings?.modelProfile || '');
    return id ? (modelCatalog.get(id) || null) : null;
}

function getInferenceDefaultProfile(model = getSelectedModelProfile()) {
    if (model?.recipe === 'qwen36_moe') {
        return {
            source: 'Qwen3.6 precise-thinking recommendation',
            values: QWEN36_PRECISE_INFERENCE_DEFAULTS
        };
    }
    if (model?.recipe === 'flash_next_mtp') {
        return {
            source: 'Qwen3.8 thinking recommendation',
            values: QWEN38_THINKING_INFERENCE_DEFAULTS
        };
    }
    return {
        source: 'llama.cpp engine defaults',
        values: LLAMA_CPP_INFERENCE_DEFAULTS
    };
}

function getEffectiveInferenceSettings(settings = persistentSettings, model = getSelectedModelProfile(settings)) {
    const inference = settings?.inference || DEFAULT_INFERENCE_SETTINGS;
    const defaults = getInferenceDefaultProfile(model).values;
    return {
        temperature: inference.temperature ?? defaults.temperature,
        topP: inference.topP ?? defaults.topP,
        topK: inference.topK ?? defaults.topK,
        minP: inference.minP ?? defaults.minP,
        presencePenalty: inference.presencePenalty ?? defaults.presencePenalty,
        repetitionPenalty: inference.repetitionPenalty ?? defaults.repetitionPenalty,
        promptCacheReuse: inference.promptCacheReuse ?? defaults.promptCacheReuse
    };
}

function normalizeCatalogPath(value) {
    return String(value || '').replace(/\\/g, '/').replace(/^\/+/, '');
}

function catalogIdFromRelativePath(relativePath) {
    return `lmstudio:${normalizeCatalogPath(relativePath).toLowerCase()}`;
}

function isMultipartNonPrimary(filename) {
    const match = String(filename || '').match(/-(\d{5})-of-(\d{5})\.gguf$/i);
    return Boolean(match && match[1] !== '00001');
}

function isAuxiliaryGguf(filename) {
    const lower = String(filename || '').toLowerCase();
    return /(?:^|[-_.])(mmproj|mtp|draft)(?:[-_.]|$)/i.test(lower);
}

function parseQuantization(filename) {
    const stem = String(filename || '').replace(/-\d{5}-of-\d{5}\.gguf$/i, '').replace(/\.gguf$/i, '');
    const match = stem.match(/(?:^|[-_.])(UD[-_.]?(?:IQ|Q)[A-Za-z0-9_.]+|(?:IQ|Q)\d[A-Za-z0-9_.]*)(?=$|[-_.])/i);
    return match ? match[1].replace(/^UD[-_.]?/i, '').replace(/[.]/g, '_') : null;
}

function classifyModelFamily(relativePath, metadata = {}) {
    const haystack = `${relativePath} ${metadata.displayName || ''} ${metadata.modelKey || ''}`.toLowerCase();
    if (/qwen3[._-]?8[-_. ]*flash[-_. ]*next/.test(haystack)) return 'qwen38_flash_next';
    if (/qwen3[._-]?6[-_. ]*35b[-_. ]*a3b/.test(haystack)) return 'qwen36_35b_a3b';
    if (/qwen3[-_. ]?8b(?:[-_. ]|$)/.test(haystack)) return 'rejected_qwen3_8b';
    return 'generic';
}

function normalizeModelDisplayLabel(value, quantization = null) {
    let label = String(value || '').trim();
    if (!label) return '';

    if (quantization) {
        const escaped = String(quantization).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        label = label.replace(new RegExp(`(?:\\s*[|\\-_/]\\s*)?(?:UD\\s*)?${escaped}$`, 'i'), '').trim();
    }

    // LM Studio/publisher display names may include a trailing "UD" marker while
    // AI Director already shows the actual quantization as a separate field.
    // Keep source metadata intact and normalize only the user-facing family label.
    label = label.replace(/(?:\s*[|\-_/]\s*)?UD$/i, '').trim();
    return label.replace(/\s{2,}/g, ' ');
}

function familyLabel(family, metadata, relativePath, quantization = null) {
    if (family === 'qwen38_flash_next') return 'Qwen3.8 Flash Next';
    if (family === 'qwen36_35b_a3b') return 'Qwen3.6-35B-A3B';
    const display = normalizeModelDisplayLabel(metadata?.displayName, quantization);
    if (display) return display;
    const parts = normalizeCatalogPath(relativePath).split('/');
    const repo = parts.length >= 2 ? parts[parts.length - 2] : parts[0];
    return normalizeModelDisplayLabel(String(repo || 'Local GGUF').replace(/-GGUF$/i, '').replace(/_/g, ' '), quantization);
}

function findSiblingMtpModel(primaryPath) {
    try {
        const directory = path.dirname(primaryPath);
        const candidates = fs.readdirSync(directory, { withFileTypes: true })
            .filter((entry) => entry.isFile() && /\.gguf$/i.test(entry.name) && /(?:^|[-_.])mtp(?:[-_.]|$)/i.test(entry.name))
            .map((entry) => path.join(directory, entry.name));
        candidates.sort((a, b) => {
            const ashared = /shared/i.test(path.basename(a)) ? 0 : 1;
            const bshared = /shared/i.test(path.basename(b)) ? 0 : 1;
            return ashared - bshared || a.localeCompare(b);
        });
        return candidates[0] || null;
    } catch (_error) {
        return null;
    }
}

function metadataIndex(models) {
    const byPath = new Map();
    const byBasename = new Map();
    for (const item of Array.isArray(models) ? models : []) {
        if (!item || item.type !== 'llm') continue;
        const rel = normalizeCatalogPath(item.path);
        if (rel) byPath.set(rel.toLowerCase(), item);
        const base = path.basename(rel || String(item.modelKey || '')).toLowerCase();
        if (base && !byBasename.has(base)) byBasename.set(base, item);
    }
    return { byPath, byBasename };
}

function resolveMetadata(index, relativePath, filename) {
    const rel = normalizeCatalogPath(relativePath).toLowerCase();
    return index.byPath.get(rel) || index.byBasename.get(String(filename || '').toLowerCase()) || {};
}

function metadataText(value) {
    if (value === null || value === undefined) return null;
    if (typeof value === 'string' || typeof value === 'number') {
        const text = String(value).trim();
        return text || null;
    }
    if (typeof value === 'object') {
        for (const key of ['name', 'displayName', 'display_name', 'id', 'key', 'value']) {
            const text = metadataText(value[key]);
            if (text) return text;
        }
    }
    return null;
}

function metadataBoolean(...values) {
    for (const value of values) {
        if (value === true || value === false) return value;
    }
    return null;
}

function metadataReasoningInfo(metadata = {}) {
    const raw = metadata?.capabilities?.reasoning ?? metadata?.reasoning ?? null;
    if (!raw) return null;
    if (raw === true || raw === false) return { supported: raw, default: null, allowedOptions: [] };
    if (typeof raw !== 'object') return null;
    const allowed = Array.isArray(raw.allowed_options) ? raw.allowed_options
        : (Array.isArray(raw.allowedOptions) ? raw.allowedOptions : []);
    return {
        supported: allowed.length > 0 || Boolean(raw.default),
        default: metadataText(raw.default),
        allowedOptions: allowed.map((item) => String(item))
    };
}

function buildDiscoveredModelProfile(primaryPath, root, relativePath, metadata = {}) {
    const family = classifyModelFamily(relativePath, metadata);
    if (family === 'rejected_qwen3_8b') return { rejected: true };

    const filename = path.basename(primaryPath);
    const quantization = metadataText(metadata.quantization) || parseQuantization(filename) || null;
    const pathPublisher = normalizeCatalogPath(relativePath).split('/')[0] || null;
    const publisher = metadataText(metadata.publisher) || pathPublisher;
    const isUnsloth = String(publisher || '').toLowerCase() === 'unsloth';
    const metadataMaxContext = Number(metadata.maxContextLength || metadata.max_context_length || 0);
    const metadataToolUse = metadataBoolean(
        metadata.trainedForToolUse,
        metadata.trained_for_tool_use,
        metadata?.capabilities?.trainedForToolUse,
        metadata?.capabilities?.trained_for_tool_use
    );
    const metadataReasoning = metadataReasoningInfo(metadata);
    const label = familyLabel(family, metadata, relativePath, quantization);
    const id = catalogIdFromRelativePath(relativePath);
    const primaryExists = fs.existsSync(primaryPath);

    let profile;
    if (family === 'qwen38_flash_next') {
        const draftModel = findSiblingMtpModel(primaryPath);
        profile = {
            id,
            familyId: family,
            label,
            shortLabel: label,
            description: 'Reasoning-capable | shared MTP draft',
            alias: 'Qwen3.8-Flash-Next',
            primaryModel: primaryPath,
            draftModel,
            recipe: 'flash_next_mtp',
            recommendedContextLength: 131072,
            maxContextLength: 262144,
            contextTier: '262,144 native max context',
            directLazyMode: 'on-direct',
            supportStatus: 'tested',
            reasoningCapable: true,
            available: Boolean(primaryExists && draftModel && fs.existsSync(draftModel)),
            availabilityReason: draftModel ? null : 'Compatible MTP draft GGUF was not found beside this model.'
        };
    } else if (family === 'qwen36_35b_a3b') {
        profile = {
            id,
            familyId: family,
            label,
            shortLabel: label,
            description: 'MoE | reasoning-capable',
            alias: 'Qwen3.6-35B-A3B',
            primaryModel: primaryPath,
            draftModel: null,
            recipe: 'qwen36_moe',
            recommendedContextLength: 131072,
            maxContextLength: Math.max(131072, Math.min(metadataMaxContext || 262144, 262144)),
            contextTier: metadataMaxContext ? `${metadataMaxContext.toLocaleString()} max context` : 'Context metadata unavailable',
            directLazyMode: null,
            supportStatus: 'candidate',
            reasoningCapable: true,
            available: primaryExists,
            availabilityReason: null
        };
    } else {
        const maxContextLength = Math.max(16384, Math.min(metadataMaxContext || 131072, 262144));
        profile = {
            id,
            familyId: family,
            label,
            shortLabel: label,
            description: 'Local GGUF',
            alias: path.basename(filename, '.gguf').replace(/-\d{5}-of-\d{5}$/i, '').slice(0, 96),
            primaryModel: primaryPath,
            draftModel: null,
            recipe: 'generic_gguf',
            recommendedContextLength: Math.min(131072, maxContextLength),
            maxContextLength,
            contextTier: metadataMaxContext ? `${metadataMaxContext.toLocaleString()} metadata context` : 'Context metadata unavailable',
            directLazyMode: null,
            supportStatus: 'unvalidated',
            reasoningCapable: null,
            available: primaryExists,
            availabilityReason: null
        };
    }

    return {
        ...profile,
        quantization,
        publisher,
        isUnsloth,
        architecture: metadataText(metadata.architecture || metadata.arch),
        metadataMaxContextLength: metadataMaxContext || null,
        trainedForToolUse: metadataToolUse,
        metadataReasoning,
        modelKey: metadataText(metadata.modelKey || metadata.key),
        relativePath: normalizeCatalogPath(relativePath),
        modelRoot: root,
        filename
    };
}

function scanModelRoot(root, metadata, catalog, stats) {
    if (!root || !fs.existsSync(root)) return;
    const stack = [root];
    while (stack.length) {
        const directory = stack.pop();
        let entries;
        try {
            entries = fs.readdirSync(directory, { withFileTypes: true });
        } catch (_error) {
            continue;
        }
        for (const entry of entries) {
            const fullPath = path.join(directory, entry.name);
            if (entry.isDirectory()) {
                stack.push(fullPath);
                continue;
            }
            if (!entry.isFile() || !/\.gguf$/i.test(entry.name)) continue;
            if (isAuxiliaryGguf(entry.name) || isMultipartNonPrimary(entry.name)) continue;

            const relativePath = path.relative(root, fullPath);
            const itemMetadata = resolveMetadata(metadata, relativePath, entry.name);
            const profile = buildDiscoveredModelProfile(fullPath, root, relativePath, itemMetadata);
            if (profile.rejected) {
                stats.rejectedCount += 1;
                continue;
            }
            if (!catalog.has(profile.id)) catalog.set(profile.id, profile);
        }
    }
}

function runLmsListJson() {
    return new Promise(async (resolve) => {
        const candidates = [...LM_STUDIO_CLI_CANDIDATES];
        for (const executable of candidates) {
            if (path.isAbsolute(executable) && !fs.existsSync(executable)) continue;
            let result = null;
            for (const args of [
                ['ls', '--llm', '--json', '--detailed'],
                ['ls', '--llm', '--json']
            ]) {
                result = await new Promise((done) => {
                    execFile(
                        executable,
                        args,
                        { windowsHide: true, timeout: 15000, maxBuffer: 16 * 1024 * 1024 },
                        (error, stdout) => {
                            if (error) return done(null);
                            try {
                                const parsed = JSON.parse(String(stdout || '').trim());
                                done(Array.isArray(parsed) ? parsed : null);
                            } catch (_error) {
                                done(null);
                            }
                        }
                    );
                });
                if (result) break;
            }
            if (result) return resolve({ models: result, executable });
        }
        resolve({ models: [], executable: null });
    });
}

function preferredDefaultModelId() {
    const models = [...modelCatalog.values()].filter((model) => model.available);
    const preferredFlash = models.find((model) => model.familyId === 'qwen38_flash_next' && /iq3[_-]?xxs/i.test(String(model.quantization || model.filename)));
    if (preferredFlash) return preferredFlash.id;
    const flash = models.find((model) => model.familyId === 'qwen38_flash_next');
    if (flash) return flash.id;
    const qwen36 = models.find((model) => model.familyId === 'qwen36_35b_a3b');
    if (qwen36) return qwen36.id;
    return models[0]?.id || null;
}

function appendSettingsWarning(message) {
    if (!message) return;
    if (!settingsLoadError) settingsLoadError = message;
    else if (!settingsLoadError.includes(message)) settingsLoadError += ` ${message}`;
}

function reconcilePersistentModelSelection({ persist = false } = {}) {
    let changed = false;
    let selected = String(persistentSettings.modelProfile || '');

    if (selected === LEGACY_FLASH_MODEL_ID) {
        selected = preferredDefaultModelId();
        changed = true;
    } else if (selected === LEGACY_REJECTED_QWEN3_8B_ID) {
        selected = preferredDefaultModelId();
        changed = true;
    }

    if (selected && modelCatalog.has(selected) && modelCatalog.get(selected).available) {
        if (persistentSettings.modelProfile !== selected) {
            persistentSettings.modelProfile = selected;
            changed = true;
        }
    } else {
        const fallback = preferredDefaultModelId();
        if (fallback) {
            if (selected && selected !== fallback) {
                appendSettingsWarning('The previously selected model is no longer available. AI Director selected an available detected model; review Settings before continuing if needed.');
            }
            if (persistentSettings.modelProfile !== fallback) {
                persistentSettings.modelProfile = fallback;
                changed = true;
            }
        } else {
            if (persistentSettings.modelProfile !== null) {
                persistentSettings.modelProfile = null;
                changed = true;
            }
            if (persistentSettings.setupCompleted) {
                persistentSettings.setupCompleted = false;
                changed = true;
                appendSettingsWarning('No compatible local GGUF model was found in the current user\'s LM Studio model directories.');
            }
        }
    }

    if (changed && persist) persistSettings(persistentSettings);
    return changed;
}

async function refreshModelCatalog() {
    if (modelCatalogRefreshPromise) return modelCatalogRefreshPromise;

    modelCatalogRefreshPromise = (async () => {
        const lms = await runLmsListJson();
        const index = metadataIndex(lms.models);
        const catalog = new Map();
        const stats = { rejectedCount: 0 };
        for (const root of LM_STUDIO_MODEL_ROOTS) {
            scanModelRoot(root, index, catalog, stats);
        }

        modelCatalog = catalog;
        modelCatalogInfo = {
            roots: [...LM_STUDIO_MODEL_ROOTS],
            source: lms.executable ? 'LM Studio catalog + filesystem' : 'LM Studio filesystem fallback',
            cliAvailable: Boolean(lms.executable),
            cliExecutable: lms.executable,
            discoveredCount: catalog.size,
            rejectedCount: stats.rejectedCount,
            warning: catalog.size ? null : `No primary GGUF models were found under ${LM_STUDIO_MODEL_ROOTS.join(' or ')}.`,
            refreshedAt: new Date().toISOString()
        };
        return catalog;
    })();

    try {
        return await modelCatalogRefreshPromise;
    } finally {
        modelCatalogRefreshPromise = null;
    }
}

function getSettingsFilePath() {
    // Workflow Integration plugins run inside Resolve's Electron host, so
    // app.getPath('userData') is host-defined and is not a stable product path.
    // Keep AI Director settings under the OS roaming-app-data root explicitly.
    const appDataRoot = process.platform === 'win32' && process.env.APPDATA
        ? process.env.APPDATA
        : app.getPath('appData');
    return path.join(
        appDataRoot,
        'AIDirector',
        'DaVinciResolve',
        'settings.json'
    );
}
function getLegacySettingsFilePath() {
    const appDataRoot = process.platform === 'win32' && process.env.APPDATA
        ? process.env.APPDATA
        : app.getPath('appData');
    const legacyVendor = ['State', 'OfReason'].join('');
    return path.join(
        appDataRoot,
        legacyVendor,
        'AI Director',
        'settings.json'
    );
}

function cloneSettings(settings = persistentSettings) {
    const tuning = settings?.tuning || {};
    const inference = settings?.inference || {};
    return {
        schemaVersion: SETTINGS_SCHEMA_VERSION,
        setupCompleted: Boolean(settings.setupCompleted),
        serverProfile: settings.serverProfile || null,
        modelProfile: settings.modelProfile || null,
        runtime: {
            contextLength: Number(settings.runtime?.contextLength),
            maxOutputTokens: Number(settings.runtime?.maxOutputTokens),
            timeoutSeconds: Number(settings.runtime?.timeoutSeconds),
            contextOverflowPolicy: normalizeContextOverflowPolicy(settings.runtime?.contextOverflowPolicy)
        },
        tuning: {
            gpuLayers: tuning.gpuLayers ?? null,
            cpuMoeLayers: tuning.cpuMoeLayers ?? null,
            kvCacheType: tuning.kvCacheType ?? null,
            flashAttention: tuning.flashAttention ?? null,
            threads: tuning.threads ?? null,
            batchThreads: tuning.batchThreads ?? null,
            batchSize: tuning.batchSize ?? null,
            microBatchSize: tuning.microBatchSize ?? null
        },
        inference: {
            temperature: inference.temperature ?? DEFAULT_INFERENCE_SETTINGS.temperature,
            topP: inference.topP ?? null,
            topK: inference.topK ?? null,
            minP: inference.minP ?? null,
            presencePenalty: inference.presencePenalty ?? null,
            repetitionPenalty: inference.repetitionPenalty ?? null,
            promptCacheReuse: inference.promptCacheReuse ?? DEFAULT_INFERENCE_SETTINGS.promptCacheReuse
        },
        appearance: {
            skin: ALLOWED_SKINS.has(String(settings?.appearance?.skin || '').toLowerCase())
                ? String(settings.appearance.skin).toLowerCase()
                : DEFAULT_APPEARANCE_SETTINGS.skin
        },
        ffmpeg: normalizeFfmpegConfig(settings?.ffmpeg),
        primeExecutionCache: settings.primeExecutionCache !== false
    };
}

function normalizeOptionalInteger(value, { min, max, name }) {
    if (value === null || value === undefined || value === '') return null;
    const numeric = Number(value);
    if (!Number.isInteger(numeric) || numeric < min || numeric > max) {
        throw new Error(`${name} must use the default or be an integer from ${min} through ${max}.`);
    }
    return numeric;
}

function normalizeGpuLayers(value) {
    if (value === null || value === undefined || value === '') return null;
    if (String(value).toLowerCase() === 'auto') return 'auto';
    return normalizeOptionalInteger(value, { min: 0, max: 999, name: 'GPU Offload (Layers)' });
}

function normalizeOptionalNumber(value, { min, max, name }) {
    if (value === null || value === undefined || value === '') return null;
    const numeric = Number(value);
    if (!Number.isFinite(numeric) || numeric < min || numeric > max) {
        throw new Error(`${name} must use the default or be a number from ${min} through ${max}.`);
    }
    return numeric;
}

function normalizeInference(candidate = {}) {
    const inference = candidate?.inference || {};
    const temperature = normalizeOptionalNumber(inference.temperature, { min: 0, max: 1, name: 'Temperature' });
    const topP = normalizeOptionalNumber(inference.topP, { min: 0, max: 1, name: 'Top P Sampling' });
    const topK = normalizeOptionalInteger(inference.topK, { min: 0, max: 1000, name: 'Top K Sampling' });
    const minP = normalizeOptionalNumber(inference.minP, { min: 0, max: 1, name: 'Min P Sampling' });
    const presencePenalty = normalizeOptionalNumber(inference.presencePenalty, { min: 0, max: 2, name: 'Presence Penalty' });
    const repetitionPenalty = normalizeOptionalNumber(inference.repetitionPenalty, { min: 0, max: 2, name: 'Repeat Penalty' });

    let promptCacheReuse = inference.promptCacheReuse;
    if (promptCacheReuse === '' || promptCacheReuse === undefined) {
        promptCacheReuse = DEFAULT_INFERENCE_SETTINGS.promptCacheReuse;
    }
    if (![null, true, false].includes(promptCacheReuse)) {
        throw new Error('Prompt Cache Reuse must be On or Off.');
    }

    return { temperature, topP, topK, minP, presencePenalty, repetitionPenalty, promptCacheReuse };
}

function normalizeTuning(candidate = {}) {
    const tuning = candidate?.tuning || {};
    const kvCacheType = tuning.kvCacheType || null;
    if (![null, 'q8_0', 'q4_0', 'f16'].includes(kvCacheType)) {
        throw new Error('KV Cache Quantization must use Default, Q8_0, Q4_0, or F16.');
    }

    let flashAttention = tuning.flashAttention;
    if (flashAttention === '' || flashAttention === undefined) flashAttention = null;
    if (![null, true, false].includes(flashAttention)) {
        throw new Error('Flash Attention must use AI Director default, On or Off.');
    }

    const effectiveKvCacheType = kvCacheType || 'q8_0';
    if (flashAttention === false && effectiveKvCacheType !== 'f16') {
        throw new Error(
            'Flash Attention can be turned Off only when KV Cache Quantization is F16. ' +
            'This llama.cpp build requires Flash Attention for quantized V cache (Q8_0/Q4_0).'
        );
    }

    const logicalCpuCount = Math.max(1, os.cpus().length);
    const batchSize = normalizeOptionalInteger(tuning.batchSize, { min: 32, max: 4096, name: 'Evaluation Batch Size' });
    const microBatchSize = normalizeOptionalInteger(tuning.microBatchSize, { min: 16, max: 4096, name: 'Evaluation Micro-Batch Size' });
    const effectiveBatchSize = batchSize ?? 512;
    const effectiveMicroBatchSize = microBatchSize ?? 256;
    if (effectiveMicroBatchSize > effectiveBatchSize) {
        throw new Error('Evaluation Micro-Batch Size cannot exceed Evaluation Batch Size.');
    }

    return {
        gpuLayers: normalizeGpuLayers(tuning.gpuLayers),
        cpuMoeLayers: normalizeOptionalInteger(tuning.cpuMoeLayers, { min: 0, max: 999, name: 'CPU MoE Layers' }),
        kvCacheType,
        flashAttention,
        threads: normalizeOptionalInteger(tuning.threads, { min: 1, max: logicalCpuCount, name: 'CPU Thread Pool Size' }),
        batchThreads: normalizeOptionalInteger(tuning.batchThreads, { min: 1, max: logicalCpuCount, name: 'Batch Thread Pool Size' }),
        batchSize,
        microBatchSize
    };
}

function normalizeAppearance(candidate = {}) {
    const requested = String(candidate?.appearance?.skin || DEFAULT_APPEARANCE_SETTINGS.skin).toLowerCase();
    if (!ALLOWED_SKINS.has(requested)) {
        throw new Error('Skin must be Green, Blue, Purple, or Gray.');
    }
    return { skin: requested };
}

function currentAppearance() {
    return normalizeAppearance(persistentSettings || {});
}

function setAppearanceSkin(skin) {
    try {
        const appearance = normalizeAppearance({ appearance: { skin } });
        persistentSettings = {
            ...persistentSettings,
            appearance
        };

        if (settingsApplyInProgress) {
            // Operational Apply is transactional. Persist only the appearance field
            // against the last committed on-disk settings so a skin click can never
            // commit an in-flight server/runtime candidate early.
            const settingsPath = getSettingsFilePath();
            if (fs.existsSync(settingsPath)) {
                const committed = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
                committed.schemaVersion = SETTINGS_SCHEMA_VERSION;
                committed.appearance = { ...appearance };
                persistSettings(committed);
            }
        } else {
            persistSettings(persistentSettings);
        }

        settingsLoadError = null;
        return {
            ok: true,
            appearance: { ...appearance }
        };
    } catch (error) {
        return {
            ok: false,
            error: error?.message || String(error),
            appearance: currentAppearance()
        };
    }
}

function normalizeContextOverflowPolicy(value) {
    const normalized = String(value || DEFAULT_CONTEXT_OVERFLOW_POLICY).toLowerCase();
    if (!CONTEXT_OVERFLOW_POLICIES.has(normalized)) {
        throw new Error('Context Overflow must be Rolling Window or Stop at Limit.');
    }
    return normalized;
}


function normalizeFfmpegConfig(value = {}) {
    const source = value && typeof value === 'object' ? value : {};
    const mode = String(source.mode || DEFAULT_FFMPEG_SETTINGS.mode).trim().toLowerCase();
    if (!FFMPEG_MODES.has(mode)) {
        throw new Error('External FFmpeg mode must be Locate Existing or Continue Without.');
    }
    if (mode === 'disabled') {
        return { ...DEFAULT_FFMPEG_SETTINGS };
    }

    const ffmpegPath = String(source.ffmpegPath || '').trim();
    const ffprobePath = String(source.ffprobePath || '').trim();
    if (!ffmpegPath || !ffprobePath || !path.isAbsolute(ffmpegPath) || !path.isAbsolute(ffprobePath)) {
        throw new Error('External FFmpeg requires absolute ffmpeg.exe and ffprobe.exe paths.');
    }
    if (path.basename(ffmpegPath).toLowerCase() !== 'ffmpeg.exe') {
        throw new Error('The selected FFmpeg executable must be named ffmpeg.exe.');
    }
    if (path.basename(ffprobePath).toLowerCase() !== 'ffprobe.exe') {
        throw new Error('The associated probe executable must be named ffprobe.exe.');
    }
    if (path.dirname(ffmpegPath).toLowerCase() !== path.dirname(ffprobePath).toLowerCase()) {
        throw new Error('ffmpeg.exe and ffprobe.exe must come from the same external FFmpeg bin directory.');
    }
    return {
        mode: 'external',
        ffmpegPath: path.normalize(ffmpegPath),
        ffprobePath: path.normalize(ffprobePath)
    };
}

function disabledFfmpegRuntimeStatus() {
    return {
        mode: 'disabled',
        state: 'disabled',
        available: false,
        ffmpegPath: null,
        ffprobePath: null,
        ffmpegVersion: null,
        ffprobeVersion: null,
        ffmpegSha256: null,
        ffprobeSha256: null,
        capabilities: null,
        missingRequirements: [],
        error: null
    };
}

function sha256FileAsync(filePath) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha256');
        const stream = fs.createReadStream(filePath);
        stream.on('error', reject);
        stream.on('data', (chunk) => hash.update(chunk));
        stream.on('end', () => resolve(hash.digest('hex').toUpperCase()));
    });
}

function execExternalTool(executable, args, timeout = FFMPEG_PROBE_TIMEOUT_MS) {
    return new Promise((resolve, reject) => {
        execFile(
            executable,
            args,
            {
                windowsHide: true,
                timeout,
                maxBuffer: 16 * 1024 * 1024,
                encoding: 'utf8'
            },
            (error, stdout, stderr) => {
                const combined = `${stdout || ''}\n${stderr || ''}`.trim();
                if (error) {
                    const detail = combined.split(/\r?\n/).filter(Boolean).slice(-3).join(' | ') || error.message;
                    reject(new Error(`${path.basename(executable)} ${args.join(' ')} failed: ${detail}`));
                    return;
                }
                resolve(combined);
            }
        );
    });
}

function parseFfmpegVersion(text, toolName) {
    const escaped = String(toolName).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const match = String(text || '').match(new RegExp(`${escaped} version\\s+([^\\s]+)`, 'i'));
    return match ? match[1] : null;
}

function versionMajor(version) {
    const match = String(version || '').match(/(\d+)/);
    return match ? Number(match[1]) : null;
}

function capabilityOutputHas(text, name) {
    const escaped = String(name).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const expression = new RegExp(`(^|[\\s,])${escaped}(?=[\\s,]|$)`, 'i');
    return String(text || '').split(/\r?\n/).some((line) => expression.test(line));
}

async function probeExternalFfmpegPair(value) {
    const config = normalizeFfmpegConfig(value);
    if (config.mode !== 'external') return disabledFfmpegRuntimeStatus();

    for (const [label, executable] of [['ffmpeg.exe', config.ffmpegPath], ['ffprobe.exe', config.ffprobePath]]) {
        if (!fs.existsSync(executable) || !fs.statSync(executable).isFile()) {
            throw new Error(`${label} was not found at the selected absolute path: ${executable}`);
        }
    }

    const [ffmpegVersionText, ffprobeVersionText, filtersText, decodersText, encodersText, formatsText, ffmpegSha256, ffprobeSha256] = await Promise.all([
        execExternalTool(config.ffmpegPath, ['-hide_banner', '-version']),
        execExternalTool(config.ffprobePath, ['-hide_banner', '-version']),
        execExternalTool(config.ffmpegPath, ['-hide_banner', '-filters']),
        execExternalTool(config.ffmpegPath, ['-hide_banner', '-decoders']),
        execExternalTool(config.ffmpegPath, ['-hide_banner', '-encoders']),
        execExternalTool(config.ffmpegPath, ['-hide_banner', '-formats']),
        sha256FileAsync(config.ffmpegPath),
        sha256FileAsync(config.ffprobePath)
    ]);

    const ffmpegVersion = parseFfmpegVersion(ffmpegVersionText, 'ffmpeg');
    const ffprobeVersion = parseFfmpegVersion(ffprobeVersionText, 'ffprobe');
    if (!ffmpegVersion || !ffprobeVersion) {
        throw new Error('AI Director could not identify the selected ffmpeg.exe / ffprobe.exe versions.');
    }
    const ffmpegMajor = versionMajor(ffmpegVersion);
    const ffprobeMajor = versionMajor(ffprobeVersion);
    if (ffmpegMajor !== null && ffprobeMajor !== null && ffmpegMajor !== ffprobeMajor) {
        throw new Error(`ffmpeg.exe (${ffmpegVersion}) and ffprobe.exe (${ffprobeVersion}) do not appear to be from the same major release.`);
    }

    const missingFilters = FFMPEG_REQUIRED_FILTERS.filter((name) => !capabilityOutputHas(filtersText, name));
    const missingDecoders = FFMPEG_REQUIRED_DECODERS.filter((name) => !capabilityOutputHas(decodersText, name));
    const missingEncoders = FFMPEG_REQUIRED_ENCODERS.filter((name) => !capabilityOutputHas(encodersText, name));
    const missingFormats = FFMPEG_REQUIRED_FORMATS.filter((name) => !capabilityOutputHas(formatsText, name));
    const missingRequirements = [
        ...missingFilters.map((name) => `filter:${name}`),
        ...missingDecoders.map((name) => `decoder:${name}`),
        ...missingEncoders.map((name) => `encoder:${name}`),
        ...missingFormats.map((name) => `format:${name}`)
    ];

    const capabilities = {
        metadataProbe: true,
        pcmAudioAnalysis: ['silencedetect', 'ebur128', 'astats', 'aresample'].every((name) => capabilityOutputHas(filtersText, name)),
        commonAudioDecode: ['aac', 'mp3', 'flac', 'pcm_s16le'].every((name) => capabilityOutputHas(decodersText, name)),
        commonVideoDecode: ['h264', 'hevc', 'prores'].every((name) => capabilityOutputHas(decodersText, name)),
        frameExtraction: capabilityOutputHas(encodersText, 'png') && ['scale', 'format', 'select'].every((name) => capabilityOutputHas(filtersText, name)),
        colorQc: ['lut3d', 'signalstats', 'blackdetect', 'idet'].every((name) => capabilityOutputHas(filtersText, name)),
        fullCurrentMcpSurface: missingRequirements.length === 0
    };

    if (missingRequirements.length) {
        const preview = missingRequirements.slice(0, 10).join(', ');
        const more = missingRequirements.length > 10 ? ` (+${missingRequirements.length - 10} more)` : '';
        throw new Error(
            `The selected FFmpeg pair runs, but it does not satisfy AI Director's current FFmpeg capability baseline: ${preview}${more}. ` +
            'Use the Recommended build or Continue Without FFmpeg.'
        );
    }

    return {
        mode: 'external',
        state: 'ready',
        available: true,
        ffmpegPath: config.ffmpegPath,
        ffprobePath: config.ffprobePath,
        ffmpegVersion,
        ffprobeVersion,
        ffmpegSha256,
        ffprobeSha256,
        capabilities,
        missingRequirements: [],
        error: null
    };
}

async function refreshConfiguredFfmpegStatus(config = persistentSettings?.ffmpeg) {
    let normalized;
    try {
        normalized = normalizeFfmpegConfig(config);
    } catch (error) {
        ffmpegRuntimeStatus = {
            ...disabledFfmpegRuntimeStatus(),
            mode: 'external',
            state: 'error',
            error: error?.message || String(error)
        };
        return ffmpegRuntimeStatus;
    }

    if (normalized.mode === 'disabled') {
        ffmpegRuntimeStatus = disabledFfmpegRuntimeStatus();
        return ffmpegRuntimeStatus;
    }

    try {
        ffmpegRuntimeStatus = await probeExternalFfmpegPair(normalized);
    } catch (error) {
        ffmpegRuntimeStatus = {
            mode: 'external',
            state: 'error',
            available: false,
            ffmpegPath: normalized.ffmpegPath,
            ffprobePath: normalized.ffprobePath,
            ffmpegVersion: null,
            ffprobeVersion: null,
            ffmpegSha256: null,
            ffprobeSha256: null,
            capabilities: null,
            missingRequirements: [],
            error: error?.message || String(error)
        };
    }
    return ffmpegRuntimeStatus;
}

async function locateExternalFfmpeg() {
    const selected = await dialog.showOpenDialog(mainWindow || undefined, {
        title: 'Locate Existing ffmpeg.exe',
        properties: ['openFile'],
        filters: [{ name: 'FFmpeg executable', extensions: ['exe'] }]
    });
    if (selected.canceled || !selected.filePaths?.length) {
        return { ok: false, canceled: true };
    }

    const ffmpegPath = path.normalize(selected.filePaths[0]);
    if (path.basename(ffmpegPath).toLowerCase() !== 'ffmpeg.exe') {
        return { ok: false, canceled: false, error: 'Choose ffmpeg.exe itself, not the folder or another executable.' };
    }
    const ffprobePath = path.join(path.dirname(ffmpegPath), 'ffprobe.exe');
    if (!fs.existsSync(ffprobePath)) {
        return {
            ok: false,
            canceled: false,
            error: `The selected FFmpeg directory does not contain the required sibling ffprobe.exe: ${ffprobePath}`
        };
    }

    const config = normalizeFfmpegConfig({ mode: 'external', ffmpegPath, ffprobePath });
    try {
        const status = await probeExternalFfmpegPair(config);
        return { ok: true, canceled: false, config, status };
    } catch (error) {
        return { ok: false, canceled: false, error: error?.message || String(error), config };
    }
}

async function openRecommendedFfmpegPage() {
    await shell.openExternal(FFMPEG_RECOMMENDED_URL);
    return { ok: true, url: FFMPEG_RECOMMENDED_URL };
}

function validateSettingsCandidate(candidate, { requireProfile = true, requireModel = true } = {}) {
    const profile = String(candidate?.serverProfile || '').toLowerCase();
    const modelId = String(candidate?.modelProfile || '');
    const modelProfile = modelId ? (modelCatalog.get(modelId) || null) : null;
    const contextLength = Number(candidate?.runtime?.contextLength);
    const maxOutputTokens = Number(candidate?.runtime?.maxOutputTokens);
    const timeoutSeconds = Number(candidate?.runtime?.timeoutSeconds);
    const contextOverflowPolicy = normalizeContextOverflowPolicy(candidate?.runtime?.contextOverflowPolicy);
    const primeExecutionCache = candidate?.primeExecutionCache !== false;
    const tuning = normalizeTuning(candidate);
    const inference = normalizeInference(candidate);
    const appearance = normalizeAppearance(candidate);
    const ffmpeg = normalizeFfmpegConfig(candidate?.ffmpeg);

    if (requireProfile && !SERVER_PROFILES[profile]) {
        throw new Error('Choose an available server profile.');
    }
    if (requireModel && !modelProfile) {
        throw new Error('Choose an available detected model.');
    }
    if (requireModel && modelProfile && !modelProfile.available) {
        throw new Error(modelProfile.availabilityReason || `${modelProfile.label} is not currently usable.`);
    }

    const maxContextLength = modelProfile?.maxContextLength || 262144;
    if (maxContextLength < MIN_SUPPORTED_CONTEXT_LENGTH) {
        throw new Error(`The selected model exposes only ${maxContextLength.toLocaleString()} context tokens, below AI Director's supported minimum of ${MIN_SUPPORTED_CONTEXT_LENGTH.toLocaleString()}.`);
    }
    if (!Number.isInteger(contextLength) || contextLength < MIN_SUPPORTED_CONTEXT_LENGTH || contextLength > maxContextLength) {
        throw new Error(`Context Length must be an integer from ${MIN_SUPPORTED_CONTEXT_LENGTH.toLocaleString()} through ${maxContextLength.toLocaleString()} tokens for the selected model.`);
    }
    if (!Number.isInteger(maxOutputTokens) || maxOutputTokens < 256 || maxOutputTokens > MAX_SUPPORTED_OUTPUT_TOKENS) {
        throw new Error(`Max Output Tokens must be an integer from 256 through ${MAX_SUPPORTED_OUTPUT_TOKENS.toLocaleString()}.`);
    }
    if (maxOutputTokens >= contextLength - 4096) {
        throw new Error('Max output tokens must leave at least 4,096 tokens of context safety margin.');
    }
    if (!Number.isInteger(timeoutSeconds) || timeoutSeconds < 60 || timeoutSeconds > 604800) {
        throw new Error('Request timeout must be between 60 seconds and 7 days.');
    }

    return {
        schemaVersion: SETTINGS_SCHEMA_VERSION,
        setupCompleted: Boolean(candidate?.setupCompleted),
        serverProfile: profile || null,
        modelProfile: modelId || null,
        runtime: { contextLength, maxOutputTokens, timeoutSeconds, contextOverflowPolicy },
        tuning,
        inference,
        appearance,
        ffmpeg,
        primeExecutionCache
    };
}

function migrateSettings(raw) {
    const source = raw && typeof raw === 'object' ? { ...raw } : {};
    const sourceVersion = Number(source.schemaVersion || 1);

    if (sourceVersion <= 1 && !source.modelProfile) {
        source.modelProfile = LEGACY_FLASH_MODEL_ID;
    }
    // Schema v2 already contains the legacy fixed profile IDs. They are
    // intentionally preserved here and resolved against the live LM Studio
    // catalog after discovery, when actual file availability is known.
    if (!source.tuning || typeof source.tuning !== 'object') {
        source.tuning = { ...DEFAULT_TUNING_SETTINGS };
    }
    if (!source.appearance || typeof source.appearance !== 'object') {
        source.appearance = { ...DEFAULT_APPEARANCE_SETTINGS };
    }
    if (!source.ffmpeg || typeof source.ffmpeg !== 'object') {
        source.ffmpeg = { ...DEFAULT_FFMPEG_SETTINGS };
    }
    if (!source.runtime || typeof source.runtime !== 'object') {
        source.runtime = { ...DEFAULT_PERSISTENT_SETTINGS.runtime };
    } else {
        source.runtime = { ...source.runtime };
        if (!source.runtime.contextOverflowPolicy) {
            source.runtime.contextOverflowPolicy = DEFAULT_CONTEXT_OVERFLOW_POLICY;
        }
        // Schema v9 formalizes the supported AI Director operating envelope.
        // Earlier sub-131K / >32K values were development stress settings, not
        // supported end-user configurations. Preserve all other settings while
        // migrating only these two runtime controls into the validated envelope.
        if (sourceVersion <= 8) {
            const savedContext = Number(source.runtime.contextLength);
            if (Number.isFinite(savedContext) && savedContext < MIN_SUPPORTED_CONTEXT_LENGTH) {
                source.runtime.contextLength = MIN_SUPPORTED_CONTEXT_LENGTH;
            }
            const savedMaxOutput = Number(source.runtime.maxOutputTokens);
            if (Number.isFinite(savedMaxOutput) && savedMaxOutput > MAX_SUPPORTED_OUTPUT_TOKENS) {
                source.runtime.maxOutputTokens = MAX_SUPPORTED_OUTPUT_TOKENS;
            }
        }
    }
    if (!source.inference || typeof source.inference !== 'object') {
        source.inference = { ...DEFAULT_INFERENCE_SETTINGS };
    } else if (sourceVersion <= 5) {
        // v1.8.x introduced a fixed 0.10 temperature while every other sampler
        // remained unset. That exact untouched baseline was a product default,
        // not a user-selected model recipe. Migrate only that exact state into
        // the new model-aware default mode; preserve any real user overrides.
        const inference = source.inference;
        const untouchedV18Baseline =
            Number(inference.temperature ?? 0.1) === 0.1 &&
            inference.topP == null &&
            inference.topK == null &&
            inference.minP == null &&
            inference.presencePenalty == null &&
            inference.repetitionPenalty == null &&
            inference.promptCacheReuse == null;
        if (untouchedV18Baseline) {
            source.inference = { ...DEFAULT_INFERENCE_SETTINGS };
        } else if (inference.promptCacheReuse == null) {
            // Both installed server builds default prompt caching to enabled.
            source.inference = { ...inference, promptCacheReuse: true };
        }
    }
    source.schemaVersion = SETTINGS_SCHEMA_VERSION;
    return source;
}

function loadPersistentSettings() {
    const settingsPath = getSettingsFilePath();
    const legacySettingsPath = getLegacySettingsFilePath();
    settingsLoadError = null;

    let sourcePath = settingsPath;
    if (
        !fs.existsSync(settingsPath) &&
        legacySettingsPath !== settingsPath &&
        fs.existsSync(legacySettingsPath)
    ) {
        sourcePath = legacySettingsPath;
    }

    if (!fs.existsSync(sourcePath)) {
        persistentSettings = cloneSettings(DEFAULT_PERSISTENT_SETTINGS);
        selectedServerProfileId = 'upstream';
        return;
    }

    try {
        const parsed = JSON.parse(fs.readFileSync(sourcePath, 'utf8'));
        const sourceSchemaVersion = Number(parsed?.schemaVersion || 1);
        const sourceMissingInference = !parsed?.inference || typeof parsed.inference !== 'object';
        const raw = migrateSettings(parsed);
        const validated = validateSettingsCandidate(raw, {
            requireProfile: Boolean(raw?.setupCompleted),
            requireModel: false
        });
        validated.setupCompleted = Boolean(raw?.setupCompleted);
        if (!validated.setupCompleted) validated.serverProfile = raw?.serverProfile || null;
        persistentSettings = validated;
        selectedServerProfileId = validated.serverProfile || 'upstream';

        // Persist any successful schema normalization immediately. This keeps the
        // canonical on-disk settings file aligned with the in-memory schema even
        // when the source file was already at the canonical path. Legacy host-path
        // files remain untouched as rollback evidence.
        const persistenceMigrationNeeded =
            sourcePath !== settingsPath ||
            sourceSchemaVersion !== SETTINGS_SCHEMA_VERSION ||
            sourceMissingInference;
        if (persistenceMigrationNeeded) {
            try {
                persistSettings(persistentSettings);
            } catch (migrationError) {
                settingsLoadError = `AI Director loaded settings but could not persist the normalized schema to ${settingsPath}: ${migrationError?.message || String(migrationError)}`;
            }
        }
    } catch (error) {
        settingsLoadError = `Saved AI Director settings could not be loaded: ${error?.message || String(error)}`;
        persistentSettings = cloneSettings(DEFAULT_PERSISTENT_SETTINGS);
        selectedServerProfileId = 'upstream';
    }
}

function persistSettings(settings = persistentSettings) {
    const settingsPath = getSettingsFilePath();
    const directory = path.dirname(settingsPath);
    fs.mkdirSync(directory, { recursive: true });

    const tempPath = `${settingsPath}.tmp-${process.pid}`;
    const serialized = JSON.stringify(settings, null, 2) + '\n';
    fs.writeFileSync(tempPath, serialized, { encoding: 'utf8' });
    try {
        fs.renameSync(tempPath, settingsPath);
    } catch (error) {
        try {
            fs.copyFileSync(tempPath, settingsPath);
            fs.unlinkSync(tempPath);
        } catch (_fallbackError) {
            try { fs.unlinkSync(tempPath); } catch (_) {}
            throw error;
        }
    }
}

const LLAMA_MCP_CONFIG = ProductPaths.resolveMcpConfig;

const LLAMA_HOST = '127.0.0.1';
const LLAMA_PORT = 8091;
const LLAMA_BASE_URL = `http://${LLAMA_HOST}:${LLAMA_PORT}`;

function getCommonLaunchArgs(settings = persistentSettings) {
    const tuning = settings?.tuning || DEFAULT_TUNING_SETTINGS;
    const kvCacheType = tuning.kvCacheType || 'q8_0';
    const batchSize = tuning.batchSize || 512;
    const microBatchSize = tuning.microBatchSize || 256;
    const flashAttention = tuning.flashAttention === null || tuning.flashAttention === undefined
        ? true
        : tuning.flashAttention;

    const args = [
        '--device', 'CUDA0',
        '--parallel', '1',
        '-ctk', kvCacheType,
        '-ctv', kvCacheType,
        '-b', String(batchSize),
        '-ub', String(microBatchSize),
        '-fa', flashAttention ? 'on' : 'off',
        '--load-mode', 'none',
        '--no-warmup',
        '--jinja',
        '--mcp-servers-config', LLAMA_MCP_CONFIG,
        '--no-webui',
        '--host', LLAMA_HOST,
        '--port', String(LLAMA_PORT)
    ];

    // Blank thread controls deliberately delegate to llama.cpp:
    // --threads defaults to -1 (Auto) and --threads-batch defaults to --threads.
    if (tuning.threads !== null && tuning.threads !== undefined) {
        args.push('-t', String(tuning.threads));
    }
    if (tuning.batchThreads !== null && tuning.batchThreads !== undefined) {
        args.push('-tb', String(tuning.batchThreads));
    }
    return args;
}

function getEffectiveLazyMode(profile = getSelectedServerProfile(), model = getSelectedModelProfile()) {
    if (profile.id === 'direct' && model?.directLazyMode) {
        return model.directLazyMode;
    }
    return 'off';
}

function getModelLaunchArgs(model = getSelectedModelProfile(), settings = persistentSettings) {
    if (!model) throw new Error('No detected model is selected.');
    const tuning = settings?.tuning || DEFAULT_TUNING_SETTINGS;

    let fitMode;
    let gpuLayers;
    let cpuMoeLayers = null;
    const extra = [];

    if (model.recipe === 'flash_next_mtp') {
        fitMode = 'off';
        gpuLayers = '12';
        cpuMoeLayers = 48;
        extra.push(
            '-md', model.draftModel,
            '--spec-type', 'draft-mtp',
            '--spec-draft-n-max', '3',
            '--spec-draft-device', 'CUDA0',
            '--spec-draft-ngl', 'all',
            '--override-tensor', 'per_layer_token_embd=CPU',
            '-ctkd', 'q8_0',
            '-ctvd', 'q8_0'
        );
    } else if (model.recipe === 'qwen36_moe') {
        fitMode = 'on';
        gpuLayers = 'auto';
        extra.push('--reasoning-format', 'deepseek');
    } else if (model.recipe === 'generic_gguf') {
        fitMode = 'on';
        gpuLayers = 'auto';
    } else {
        throw new Error(`Unsupported AI Director model recipe: ${model.recipe}`);
    }

    if (tuning.gpuLayers !== null && tuning.gpuLayers !== undefined) {
        gpuLayers = String(tuning.gpuLayers);
        fitMode = tuning.gpuLayers === 'auto' ? 'on' : 'off';
    }
    if (tuning.cpuMoeLayers !== null && tuning.cpuMoeLayers !== undefined) {
        cpuMoeLayers = Number(tuning.cpuMoeLayers);
    }

    const args = [
        ...extra,
        '--fit', fitMode,
        '-ngl', gpuLayers
    ];
    if (cpuMoeLayers !== null && cpuMoeLayers > 0) {
        args.push('--n-cpu-moe', String(cpuMoeLayers));
    }
    return args;
}

function getLlamaArgs(profile = getSelectedServerProfile(), model = getSelectedModelProfile()) {
    if (!model) throw new Error('No detected model is selected.');
    const args = [
        '-m', model.primaryModel,
        '--alias', model.alias,
        ...getModelLaunchArgs(model, persistentSettings),
        ...getCommonLaunchArgs(persistentSettings),
        '-c', String(persistentSettings.runtime.contextLength),
        '--lazy-mode', getEffectiveLazyMode(profile, model)
    ];

    if (debugEnabled) {
        args.push('-lv', '4');
    }

    return args;
}

let mainWindow = null;
let resolveObj = null;
let initialized = false;

if (HOST_MODE === 'standalone' && standaloneInstanceLock) {
    app.on('second-instance', () => {
        if (!mainWindow || mainWindow.isDestroyed()) return;
        if (mainWindow.isMinimized()) mainWindow.restore();
        if (!mainWindow.isVisible()) mainWindow.show();
        mainWindow.focus();
    });
}

let serverProcess = null;
let serverOwned = false;
let serverReady = false;
let serverStartPromise = null;
// Debug is session-scoped and deliberately OFF on every AI Director launch.
// When enabled, AI Director appends `-lv 4` to its own llama-server command.
let debugEnabled = false;
let debugChangeInProgress = false;
let profileChangeInProgress = false;
let serverDesired = false;
let serverStdoutFd = null;
let serverStderrFd = null;

let backendProcess = null;
let backendReadyInfo = null;
let backendStartPromise = null;
let backendBuffer = '';
let backendPrimeInProgress = false;
let backendCachePrimed = false;
let backendPrimeError = null;
let nextRequestId = 1;
let activeChatRequestId = null;
let backendStopIntent = null;
let backendAutoRestartAttempts = 0;
let backendAutoRestartWindowStarted = 0;
let backendAutoRestartTimer = null;

const BACKEND_AUTORESTART_MAX_ATTEMPTS = 5;
const BACKEND_AUTORESTART_WINDOW_MS = 5 * 60 * 1000;
const BACKEND_AUTORESTART_BASE_DELAY_MS = 250;
const BACKEND_AUTORESTART_MAX_DELAY_MS = 30000;

let shuttingDown = false;
let cleanupStarted = false;
let updateInProgress = false;
let updateStatus = { state: 'idle', result: null, error: null };
let activeUpdatePromise = null;

const pendingBackendRequests = new Map();

// AI Director session memory is product-owned and intentionally process-local.
// It survives Python-backend restarts and model/profile changes within this app
// launch, but a full application restart starts a fresh session by default.
const SESSION_ROLLING_SOURCE_MAX_CHARS = 524288;
const SESSION_ROLLING_MIN_FULL_RECENT_TURNS = 4;
const SESSION_RECENT_USER_CHARS = 2200;
const SESSION_RECENT_ASSISTANT_CHARS = 2600;
const SESSION_ORIGIN_USER_CHARS = 4096;
const SESSION_LEDGER_TEXT_CHARS = 420;
const SESSION_TOOL_RESULT_CHARS = 1200;
const SESSION_MAX_TOOL_EVENTS_PER_TURN = 64;

let nextSessionId = 1;
let aiDirectorSession = createAIDirectorSession();
let latestContextStatus = createContextStatusBaseline();

function createContextStatusBaseline() {
    const contextWindowTokens = Number(persistentSettings?.runtime?.contextLength) || 131072;
    const maxOutputTokens = Number(persistentSettings?.runtime?.maxOutputTokens) || 16384;
    const safetyMarginTokens = 4096;
    return {
        version: 1,
        source: 'configured',
        exact: false,
        context_window_tokens: contextWindowTokens,
        max_output_tokens: maxOutputTokens,
        safety_margin_tokens: safetyMarginTokens,
        prompt_budget_tokens: Math.max(0, contextWindowTokens - maxOutputTokens - safetyMarginTokens),
        used_tokens: 0,
        used_percent: 0,
        headroom_tokens: contextWindowTokens,
        peak_used_tokens: 0,
        peak_prompt_tokens: 0,
        peak_used_percent: 0
    };
}

function normalizeContextStatus(value) {
    if (!value || typeof value !== 'object') return createContextStatusBaseline();
    const baseline = createContextStatusBaseline();
    const normalized = { ...baseline, ...value };
    for (const key of [
        'context_window_tokens', 'max_output_tokens', 'safety_margin_tokens',
        'prompt_budget_tokens', 'used_tokens', 'headroom_tokens',
        'peak_used_tokens', 'peak_prompt_tokens'
    ]) {
        const numeric = Number(normalized[key]);
        normalized[key] = Number.isFinite(numeric) ? Math.max(0, Math.trunc(numeric)) : baseline[key];
    }
    for (const key of ['used_percent', 'peak_used_percent']) {
        const numeric = Number(normalized[key]);
        normalized[key] = Number.isFinite(numeric) ? Math.max(0, numeric) : baseline[key];
    }
    return normalized;
}

function updateContextStatus(value, { notify = true } = {}) {
    latestContextStatus = normalizeContextStatus(value);
    if (notify && mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('aid:contextStatus', { ...latestContextStatus });
    }
    return latestContextStatus;
}

function resetContextStatus({ notify = true } = {}) {
    return updateContextStatus(createContextStatusBaseline(), { notify });
}

function createAIDirectorSession() {
    return {
        id: `aidir-${process.pid}-${nextSessionId++}`,
        createdAt: new Date().toISOString(),
        turns: []
    };
}

function clipSessionText(value, maxChars) {
    const text = String(value ?? '').trim();
    if (!text || text.length <= maxChars) return text;
    const omitted = text.length - maxChars;
    return `${text.slice(0, maxChars)}\n...[${omitted} chars compacted]`;
}

function sessionTurnToolSummary(turn) {
    const events = Array.isArray(turn?.tools) ? turn.tools : [];
    if (!events.length) return 'none';
    return events
        .slice(0, 24)
        .map((item) => {
            const state = item?.state === 'completed' ? 'completed' : 'started/uncertain';
            return `${String(item?.name || '?')}(${state})`;
        })
        .join(', ');
}

function sessionTurnRetentionClass(turn) {
    const classes = [];
    const events = Array.isArray(turn?.tools) ? turn.tools : [];
    const status = String(turn?.status || 'unknown').toLowerCase();
    const hasUncertainTool = events.some((item) => item?.state !== 'completed');
    if (status !== 'completed' || hasUncertainTool) classes.push('uncertain');

    const mutationPattern = /(?:^|[._:-])(set|add|create|delete|remove|update|move|insert|append|apply|enable|disable|rename|duplicate|import|write|save|archive|attach|link|unlink|replace|trim|split|grade|render|export|clear|reset)(?:$|[._:-])/i;
    const compoundReadActionPattern = /^(?:get|list|query|probe|inspect|check|validate|verify|is|has|can)(?:_|$)/i;
    const compoundReadActions = new Set(['read', 'status', 'info', 'action_help']);
    const compoundReadPairs = new Set(['project_manager.snapshot']);
    const eventIsMutation = (item) => {
        const name = String(item?.name || '');
        const args = item?.arguments && typeof item.arguments === 'object'
            ? item.arguments
            : null;
        const action = args && typeof args.action === 'string'
            ? args.action.trim()
            : '';

        // The model-facing default Resolve surface uses compound tools whose
        // operation is carried in arguments.action. Tool-name-only matching
        // misses writes such as timeline.delete_track and falsely treats every
        // render.* read as a mutation. Recognize only narrow, read-shaped action
        // names (plus explicit MCP read exceptions) as ordinary. Unknown/new
        // compound actions fail safe to mutation retention so future MCP changes
        // cannot silently lose edit history. export_* stays protected because it
        // writes external files even though MCP's execution-risk classifier calls
        // exports read-like/low-risk operations.
        if (name.startsWith('davinci-resolve_')) {
            if (!action) return true;
            const normalizedAction = action.toLowerCase();
            const toolKey = name.slice('davinci-resolve_'.length).toLowerCase();
            if (
                compoundReadActionPattern.test(normalizedAction)
                || compoundReadActions.has(normalizedAction)
                || compoundReadPairs.has(`${toolKey}.${normalizedAction}`)
            ) {
                return false;
            }
            return true;
        }

        // Granular/advanced surfaces encode the operation in the tool name.
        return mutationPattern.test(name);
    };
    if (events.some(eventIsMutation)) {
        classes.push('mutation');
    }

    const userText = String(turn?.user || '');
    const constraintPattern = /\b(?:do not|don't|never|must|keep|only|without|avoid|remember|important|prefer|agreed|decided|should not|shouldn't|required?|requirement|constraint)\b/i;
    if (constraintPattern.test(userText)) classes.push('constraint');

    return classes.length ? classes.join(',') : 'ordinary';
}
function sessionTurnCompactLedgerLine(turn, ordinal) {
    const user = clipSessionText(turn?.user || '', 900).replace(/\s+/g, ' ');
    const assistant = clipSessionText(turn?.assistant || '', 700).replace(/\s+/g, ' ');
    return [
        `COMPACT SESSION TURN ${ordinal}`,
        `Retention: ${sessionTurnRetentionClass(turn)}`,
        `Status: ${turn?.status || 'unknown'}`,
        `Runtime: profile=${turn?.profile || 'unknown'} model=${turn?.model || 'unknown'}`,
        `User: ${JSON.stringify(user)}`,
        `Outcome: ${JSON.stringify(assistant)}`,
        `Tools: ${JSON.stringify(sessionTurnToolSummary(turn))}`
    ].join('\n');
}

function sessionTurnToolDetails(turn) {
    const events = Array.isArray(turn?.tools) ? turn.tools : [];
    if (!events.length) return 'none';
    return events
        .slice(0, 12)
        .map((item, index) => {
            const state = item?.state === 'completed' ? 'completed' : 'started/uncertain';
            let args = '';
            try {
                args = JSON.stringify(item?.arguments ?? {});
            } catch (_error) {
                args = String(item?.arguments ?? '');
            }
            const result = clipSessionText(item?.resultExcerpt || '', 520).replace(/\s+/g, ' ');
            return [
                `${index + 1}. ${String(item?.name || '?')} [${state}]`,
                `args=${clipSessionText(args, 720)}`,
                result ? `result=${result}` : null
            ].filter(Boolean).join(' | ');
        })
        .join('\n');
}

function sessionTurnOriginBlock(turn) {
    const assistantSummary = turn?.assistant
        ? clipSessionText(turn.assistant, SESSION_LEDGER_TEXT_CHARS)
        : `[no completed final response; status=${turn?.status || 'unknown'}]`;
    return [
        'SESSION ORIGIN',
        'TURN 1 - first user message in this AI Director session',
        `Status: ${turn?.status || 'unknown'}`,
        `Runtime: profile=${turn?.profile || 'unknown'} model=${turn?.model || 'unknown'}`,
        'User:',
        clipSessionText(turn?.user || '', SESSION_ORIGIN_USER_CHARS),
        'AI Director outcome summary:',
        assistantSummary,
        `Tool provenance summary: ${sessionTurnToolSummary(turn)}`
    ].join('\n');
}

function sessionTurnRecentBlock(turn, ordinal) {
    const assistantText = turn?.assistant
        ? clipSessionText(turn.assistant, SESSION_RECENT_ASSISTANT_CHARS)
        : `[no completed final response; status=${turn?.status || 'unknown'}]`;
    return [
        `SESSION TURN ${ordinal}`,
        `Retention: ${sessionTurnRetentionClass(turn)}`,
        `Status: ${turn?.status || 'unknown'}`,
        `Runtime: profile=${turn?.profile || 'unknown'} model=${turn?.model || 'unknown'}`,
        turn?.error ? `Error: ${clipSessionText(turn.error, SESSION_LEDGER_TEXT_CHARS)}` : null,
        'User:',
        clipSessionText(turn?.user || '', SESSION_RECENT_USER_CHARS),
        'AI Director:',
        assistantText,
        'Observed tool provenance:',
        sessionTurnToolDetails(turn)
    ].filter(Boolean).join('\n');
}

function sessionTurnLedgerLine(turn, ordinal) {
    const user = clipSessionText(turn?.user || '', SESSION_LEDGER_TEXT_CHARS).replace(/\s+/g, ' ');
    const assistant = clipSessionText(turn?.assistant || '', SESSION_LEDGER_TEXT_CHARS).replace(/\s+/g, ' ');
    return [
        `${ordinal}. status=${turn?.status || 'unknown'}`,
        `profile=${turn?.profile || 'unknown'}`,
        `model=${turn?.model || 'unknown'}`,
        `user=${JSON.stringify(user)}`,
        `final=${JSON.stringify(assistant)}`,
        `tools=${JSON.stringify(sessionTurnToolSummary(turn))}`
    ].join(' | ');
}

function sessionTurnStopAtLimitBlock(turn, ordinal) {
    const assistantText = turn?.assistant
        ? String(turn.assistant)
        : `[no completed final response; status=${turn?.status || 'unknown'}]`;
    const events = Array.isArray(turn?.tools) ? turn.tools : [];
    const toolDetails = events.length
        ? events.map((item, index) => {
            const state = item?.state === 'completed' ? 'completed' : 'started/uncertain';
            let args = '';
            try {
                args = JSON.stringify(item?.arguments ?? {});
            } catch (_error) {
                args = String(item?.arguments ?? '');
            }
            const result = String(item?.resultExcerpt || '').replace(/\s+/g, ' ').trim();
            return [
                `${index + 1}. ${String(item?.name || '?')} [${state}]`,
                `args=${args}`,
                result ? `result=${result}` : null
            ].filter(Boolean).join(' | ');
        }).join('\n')
        : 'none';
    return [
        ordinal === 1
            ? 'SESSION ORIGIN - TURN 1 - first user message in this AI Director session'
            : `TURN ${ordinal}`,
        `Status: ${turn?.status || 'unknown'}`,
        `Runtime: profile=${turn?.profile || 'unknown'} model=${turn?.model || 'unknown'}`,
        turn?.error ? `Error: ${String(turn.error)}` : null,
        'User:',
        String(turn?.user || ''),
        'AI Director:',
        assistantText,
        'Observed tool provenance:',
        toolDetails
    ].filter(Boolean).join('\n');
}

function buildStopAtLimitSessionContext(turns) {
    const header = [
        'AI DIRECTOR SESSION CONTEXT (runtime-maintained)',
        'Context Overflow policy: Stop at Limit.',
        'This is historical context from the current AI Director app session.',
        'SESSION ORIGIN / TURN 1 is the literal first user message in this session. If asked for the first message/question/turn, use TURN 1 even when it is an identity, model, or other meta question; do not reinterpret first as first substantive Resolve task.',
        'It can establish conversational references and prior AI Director activity, but it is NOT proof of current Resolve state.',
        'For current-state claims or consequential mutations, inspect/verify Resolve with the available tools.',
        'A stopped, replaced, timed-out, failed, or context-limited turn may have partially changed Resolve.',
        'Do not repeat an earlier mutation merely because it appears in this history; use it to understand what the user is referring to.',
        `Session id: ${aiDirectorSession.id}`
    ].join('\n');
    const blocks = turns.map((turn, index) => sessionTurnStopAtLimitBlock(turn, index + 1));
    return [header, ...blocks].join('\n\n');
}

function buildRollingWindowSessionContext(turns) {
    const header = [
        'AI DIRECTOR SESSION CONTEXT (runtime-maintained)',
        'Context Overflow policy: Rolling Window.',
        'This is historical context from the current AI Director app session.',
        'Semantic rolling is pressure-driven. Full turns remain model-visible until the runtime must compact older history to fit the configured context.',
        'SESSION ORIGIN below is the literal first user message in this session. It is pinned and must never be reinterpreted as the first substantive Resolve task.',
        'Retention classes identify uncertain work, likely mutations, and explicit user constraints. Compacting a turn must preserve its meaningful ledger evidence.',
        'Historical context is NOT proof of current Resolve state. For current-state claims or consequential mutations, inspect/verify Resolve with the available tools.',
        'A stopped, replaced, timed-out, failed, or context-limited turn may have partially changed Resolve. Tool entries marked started/uncertain must not be assumed completed.',
        'Do not repeat an earlier mutation merely because it appears in this history; use it to understand what the user is referring to.',
        `Session id: ${aiDirectorSession.id}`
    ].join('\n');

    const originTurn = turns[0];
    const originText = sessionTurnOriginBlock(originTurn);
    const postOriginTurns = turns.slice(1);
    const entries = postOriginTurns.map((turn, index) => ({
        ordinal: index + 2,
        turn,
        full: sessionTurnRecentBlock(turn, index + 2),
        compact: sessionTurnCompactLedgerLine(turn, index + 2),
        retention: sessionTurnRetentionClass(turn)
    }));

    const render = () => [
        header,
        originText,
        ...entries.map((entry) => entry.rendered || entry.full)
    ].join('\n\n');

    let result = render();
    if (result.length <= SESSION_ROLLING_SOURCE_MAX_CHARS) return result;

    // Extreme source-size guard only. Runtime context pressure remains the normal
    // trigger for rolling. If the process-local session itself becomes enormous,
    // compact the oldest ordinary turns first while preserving origin and recent work.
    const recentBoundary = Math.max(0, entries.length - SESSION_ROLLING_MIN_FULL_RECENT_TURNS);
    const candidates = [
        ...entries.slice(0, recentBoundary).filter((entry) => entry.retention === 'ordinary'),
        ...entries.slice(0, recentBoundary).filter((entry) => entry.retention !== 'ordinary')
    ];
    for (const entry of candidates) {
        entry.rendered = entry.compact;
        result = render();
        if (result.length <= SESSION_ROLLING_SOURCE_MAX_CHARS) return result;
    }
    // Never raw-truncate semantic session memory. If the extreme source guard
    // still cannot reduce it, pass the structured source to VFXRuntime, which
    // will either semantically compact it or fail closed.
    return result;
}

function buildAIDirectorSessionContext() {
    const turns = Array.isArray(aiDirectorSession.turns)
        ? aiDirectorSession.turns
        : [];
    if (!turns.length) return '';

    const overflowPolicy = normalizeContextOverflowPolicy(persistentSettings.runtime?.contextOverflowPolicy);
    if (overflowPolicy === 'stop_at_limit') {
        return buildStopAtLimitSessionContext(turns);
    }
    return buildRollingWindowSessionContext(turns);
}

function createPendingSessionTurn(message) {
    const model = getSelectedModelProfile();
    const profile = getSelectedServerProfile();
    return {
        sessionId: aiDirectorSession.id,
        startedAt: new Date().toISOString(),
        completedAt: null,
        status: 'active',
        integration: 'DaVinci Resolve',
        profile: profile?.id || null,
        model: model?.alias || null,
        user: String(message || '').trim(),
        assistant: '',
        rounds: 0,
        telemetry: null,
        error: null,
        tools: [],
        contextCompactions: []
    };
}

function appendSessionTurn(turn) {
    if (!turn || turn.sessionId !== aiDirectorSession.id) return;
    // Keep the process-local semantic ledger intact for the lifetime of the app session.
    // Model-visible size is governed by the structured session projection and
    // VFXRuntime semantic rolling, not by an arbitrary FIFO turn-count cap.
    aiDirectorSession.turns.push(turn);
}

function recordSessionProgress(pending, progress) {
    const turn = pending?.sessionTurn;
    if (!turn || !progress || typeof progress !== 'object') return;
    const kind = String(progress.kind || '');
    if (kind === 'context_compaction') {
        turn.contextCompactions.push({
            stage: String(progress.stage || ''),
            compactedTurns: Number(progress.compacted_turns) || 0,
            beforeTokens: Number(progress.before_tokens) || 0,
            afterTokens: Number(progress.after_tokens) || 0,
            protectedTurns: Number(progress.protected_turns) || 0
        });
        return;
    }
    if (kind !== 'tool_start' && kind !== 'tool_complete') return;

    const toolIndex = Number(progress.tool_call_index);
    let entry = turn.tools.find((item) => item.index === toolIndex);
    if (!entry) {
        if (turn.tools.length >= SESSION_MAX_TOOL_EVENTS_PER_TURN) return;
        entry = {
            index: Number.isFinite(toolIndex) ? toolIndex : turn.tools.length + 1,
            name: String(progress.tool_name || '?'),
            arguments: progress.tool_arguments && typeof progress.tool_arguments === 'object'
                ? progress.tool_arguments
                : null,
            state: 'started',
            resultExcerpt: ''
        };
        turn.tools.push(entry);
    }
    if (progress.tool_arguments && typeof progress.tool_arguments === 'object') {
        entry.arguments = progress.tool_arguments;
    }
    if (kind === 'tool_complete') {
        entry.state = 'completed';
        entry.resultExcerpt = clipSessionText(
            progress.result_excerpt || '',
            SESSION_TOOL_RESULT_CHARS
        );
    }
}

function finalizePendingSessionTurn(pending, status, details = {}) {
    if (!pending?.sessionTurn || pending.sessionCommitted) return;
    pending.sessionCommitted = true;
    const turn = pending.sessionTurn;
    turn.status = String(status || 'unknown');
    turn.completedAt = new Date().toISOString();
    turn.assistant = String(details.assistant || '').trim();
    turn.rounds = Number.isFinite(Number(details.rounds)) ? Number(details.rounds) : 0;
    turn.telemetry = details.telemetry && typeof details.telemetry === 'object'
        ? details.telemetry
        : null;
    turn.error = details.error ? String(details.error) : null;
    appendSessionTurn(turn);
}

function resetAIDirectorSession({ keepActive = false } = {}) {
    aiDirectorSession = createAIDirectorSession();
    resetContextStatus();
    if (keepActive && activeChatRequestId) {
        const pending = pendingBackendRequests.get(activeChatRequestId);
        if (pending?.sessionTurn) {
            // The already-running model request cannot unsee its old context,
            // but its eventual result becomes the first turn of the new session.
            pending.sessionTurn.sessionId = aiDirectorSession.id;
        }
    }
    return {
        ok: true,
        sessionId: aiDirectorSession.id,
        keepActive: Boolean(keepActive && activeChatRequestId)
    };
}

function settingsRuntimeTransitionActive() {
    return Boolean(
        updateInProgress ||
        debugChangeInProgress ||
        profileChangeInProgress ||
        serverStartPromise ||
        backendStartPromise ||
        backendPrimeInProgress ||
        backendAutoRestartTimer
    );
}

// Settings Apply uses a narrower lifecycle gate than the broad runtimeBusy
// signal. A healthy cache-prime on an AI Director-owned, ready llama-server is
// intentionally supersedable, matching the already-accepted main PROFILE
// switching contract. Updates, DEBUG/profile transitions, server/backend startup,
// recovery, and an unsafe/non-owned prime remain blocking.
function settingsApplyRuntimeTransitionActive() {
    return Boolean(
        updateInProgress ||
        debugChangeInProgress ||
        profileChangeInProgress ||
        serverStartPromise ||
        (serverProcess && !serverReady) ||
        backendStartPromise ||
        backendAutoRestartTimer ||
        (backendPrimeInProgress && (!serverReady || !serverOwned))
    );
}

function canSwitchServerProfileNow() {
    if (!persistentSettings.setupCompleted) return false;
    if (
        settingsApplyInProgress ||
        updateInProgress ||
        debugChangeInProgress ||
        profileChangeInProgress ||
        activeChatRequestId
    ) {
        return false;
    }
    if (serverReady && !serverOwned) return false;
    if (serverStartPromise || (serverProcess && !serverReady)) return false;
    if (backendStartPromise || backendAutoRestartTimer) return false;

    // Cache priming is intentionally supersedable. A profile change owns the
    // replacement transaction and stops the obsolete backend/server cleanly.
    return true;
}

function notifyBackendStatus(status) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('aid:backendStatus', {
            ...status,
            runtimeBusy: settingsRuntimeTransitionActive(),
            settingsApplyBlocked: settingsApplyRuntimeTransitionActive()
        });
    }
}

function notifyServerStatus(status) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        const profile = getSelectedServerProfile();
        mainWindow.webContents.send('aid:serverStatus', {
            profile: profile.id,
            profileLabel: profile.label,
            profileDescription: profile.description,
            ...status,
            runtimeBusy: settingsRuntimeTransitionActive(),
            settingsApplyBlocked: settingsApplyRuntimeTransitionActive()
        });
    }
}

const UPDATE_DIAGNOSTIC_LOG = path.join(ProductPaths.resolveLogsRoot, 'updates', 'update-progress.jsonl');
let lastUpdateDiagnosticSignature = null;

function writeUpdateDiagnostic(status) {
    if (!status || !['installing', 'done', 'error'].includes(status.state)) return;

    try {
        const signature = JSON.stringify([
            status.state || null,
            status.component || null,
            status.phase || null,
            status.message || null,
            status.error || null
        ]);
        if (signature === lastUpdateDiagnosticSignature && status.state === 'installing') return;
        lastUpdateDiagnosticSignature = signature;

        fs.mkdirSync(path.dirname(UPDATE_DIAGNOSTIC_LOG), { recursive: true });
        fs.appendFileSync(
            UPDATE_DIAGNOSTIC_LOG,
            `${JSON.stringify({
                timestamp: new Date().toISOString(),
                state: status.state || null,
                component: status.component || null,
                phase: status.phase || null,
                progress: Number.isFinite(status.progress) ? status.progress : null,
                message: status.message || null,
                error: status.error || null
            })}\n`,
            'utf8'
        );
    } catch (logError) {
        console.error('[AI Director] Failed to write update diagnostic log:', logError);
    }
}

function compactUpdateUiMessage(status) {
    if (!status || typeof status !== 'object') return '';

    if (status.state === 'done') {
        return status.result?.resolveRestartRequired
            ? 'Restart Resolve to finish.'
            : 'Update complete.';
    }

    if (status.state !== 'installing') {
        return typeof status.message === 'string' ? status.message : '';
    }

    switch (status.phase) {
        case 'download': return 'Downloading...';
        case 'verify': return 'Verifying...';
        case 'stage': return 'Staging...';
        case 'overlay': return 'Applying overlay...';
        case 'deps': return 'Preparing dependencies...';
        case 'backup': return 'Creating backup...';
        case 'swap': return 'Activating...';
        case 'health': return 'Validating...';
        case 'rollback': return 'Rolling back...';
        case 'git': return 'Updating source...';
        case 'done': return 'Finalizing...';
        default: return 'Preparing...';
    }
}

function notifyUpdateStatus(status) {
    writeUpdateDiagnostic(status);

    const uiStatus = status && typeof status === 'object'
        ? { ...status }
        : status;

    if (uiStatus && (uiStatus.state === 'installing' || uiStatus.state === 'done')) {
        uiStatus.message = compactUpdateUiMessage(status);
    }

    updateStatus = uiStatus;
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send('aid:updateStatus', uiStatus);
    }
}

async function getResolve() {
    if (!WorkflowIntegration) {
        throw new Error('Resolve Workflow Integration is unavailable in standalone host mode.');
    }

    if (resolveObj) {
        return resolveObj;
    }

    if (!initialized) {
        const success = await WorkflowIntegration.Initialize(PLUGIN_ID);

        if (!success) {
            throw new Error('WorkflowIntegration.Initialize() failed.');
        }

        initialized = true;
    }

    resolveObj = await WorkflowIntegration.GetResolve();

    if (!resolveObj) {
        throw new Error(
            'WorkflowIntegration.GetResolve() returned no Resolve object.'
        );
    }

    return resolveObj;
}

const RESOLVE_UI_STATUS_OBSERVER = app.isPackaged
    ? path.join(process.resourcesPath, 'ResolveUiStatusObserver.ps1')
    : path.join(__dirname, 'ResolveUiStatusObserver.ps1');
const STANDALONE_RESOLVE_UI_OBSERVER_INTERVAL_MS = 500;
const STANDALONE_RESOLVE_UI_OBSERVER_RETRY_MS = 5000;

let standaloneResolveObserverProcess = null;
let standaloneResolveObserverBuffer = '';
let standaloneResolveObserverStartPromise = null;
let standaloneResolveObserverNextStartAt = 0;
let standaloneResolveObserverState = {
    connected: false,
    resolvePid: null,
    currentPage: null,
    currentProject: null,
    mainWindowTitle: null,
    error: null,
    updatedAt: 0,
    source: 'windows_uia_page_switcher'
};

function currentStandaloneResolveStatus() {
    const telemetry = standaloneResolveObserverState;
    return {
        connected: telemetry.connected === true,
        hostMode: 'standalone',
        state: telemetry.connected === true ? 'resolve-connected' : 'resolve-disconnected',
        pluginId: PLUGIN_ID,
        workflowIntegration: null,
        resolveRunning: telemetry.connected === true,
        resolvePid: telemetry.resolvePid || null,
        currentPage: telemetry.connected === true ? telemetry.currentPage : null,
        currentProject: telemetry.connected === true ? telemetry.currentProject : null,
        telemetrySource: telemetry.source,
        telemetryConnected: telemetry.connected === true,
        telemetryError: telemetry.error || null,
        observerUpdatedAt: telemetry.updatedAt || null,
        mainWindowTitle: telemetry.mainWindowTitle || null
    };
}

function notifyStandaloneResolveStatus() {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    mainWindow.webContents.send('aid:resolveStatus', currentStandaloneResolveStatus());
}

function setStandaloneResolveObserverState(patch = {}, { notify = true } = {}) {
    standaloneResolveObserverState = {
        ...standaloneResolveObserverState,
        ...patch,
        updatedAt: Date.now()
    };
    if (notify) notifyStandaloneResolveStatus();
}

function handleStandaloneResolveObserverMessage(message) {
    if (!message || typeof message !== 'object') return;

    if (message.event === 'state') {
        setStandaloneResolveObserverState({
            connected: message.connected === true,
            resolvePid: Number(message.pid) || null,
            currentPage: message.connected === true && typeof message.page === 'string' && message.page.trim()
                ? message.page.trim()
                : null,
            currentProject: message.connected === true && typeof message.project === 'string' && message.project.trim()
                ? message.project.trim()
                : null,
            mainWindowTitle: typeof message.main_window_title === 'string' && message.main_window_title.trim()
                ? message.main_window_title.trim()
                : null,
            error: message.error || null,
            source: 'windows_uia_page_switcher'
        });
        return;
    }

    if (message.event === 'fatal') {
        setStandaloneResolveObserverState({
            connected: false,
            resolvePid: null,
            currentPage: null,
            currentProject: null,
            mainWindowTitle: null,
            error: message.error || 'Resolve UI status observer is unavailable.'
        });
    }
}

function handleStandaloneResolveObserverStdout(chunk) {
    standaloneResolveObserverBuffer += chunk.toString();
    while (true) {
        const newlineIndex = standaloneResolveObserverBuffer.indexOf('\n');
        if (newlineIndex === -1) break;
        const line = standaloneResolveObserverBuffer.slice(0, newlineIndex).trim();
        standaloneResolveObserverBuffer = standaloneResolveObserverBuffer.slice(newlineIndex + 1);
        if (!line) continue;
        try {
            handleStandaloneResolveObserverMessage(JSON.parse(line));
        } catch (error) {
            console.error('[AI Director] Invalid Resolve UI observer JSON:', line, error);
        }
    }
}

// Kept as a compatibility no-op because existing backend lifecycle call sites
// invoke this function. UI Automation is OS-side observation only and does not
// compete with Resolve scripting/MCP, so it does not need chat-time pausing.
function syncStandaloneResolveObserverPauseState() {}

async function ensureStandaloneResolveObserver() {
    if (HOST_MODE !== 'standalone') return false;
    if (process.platform !== 'win32') {
        setStandaloneResolveObserverState({
            connected: false,
            resolvePid: null,
            currentPage: null,
            currentProject: null,
            error: 'Standalone Resolve UI status observation is currently implemented for Windows only.'
        });
        return false;
    }

    if (standaloneResolveObserverProcess && !standaloneResolveObserverProcess.killed) return true;
    if (standaloneResolveObserverStartPromise) return standaloneResolveObserverStartPromise;
    if (Date.now() < standaloneResolveObserverNextStartAt) return false;

    standaloneResolveObserverStartPromise = Promise.resolve().then(async () => {
        if (!fs.existsSync(RESOLVE_UI_STATUS_OBSERVER)) {
            throw new Error(`Resolve UI status observer is unavailable: ${RESOLVE_UI_STATUS_OBSERVER}`);
        }

        const child = spawn(
            'powershell.exe',
            [
                '-NoProfile',
                '-NonInteractive',
                '-ExecutionPolicy', 'Bypass',
                '-File', RESOLVE_UI_STATUS_OBSERVER,
                '-IntervalMs', String(STANDALONE_RESOLVE_UI_OBSERVER_INTERVAL_MS)
            ],
            {
                cwd: app.isPackaged ? process.resourcesPath : __dirname,
                env: { ...process.env },
                windowsHide: true,
                stdio: ['ignore', 'pipe', 'pipe']
            }
        );

        standaloneResolveObserverProcess = child;
        standaloneResolveObserverBuffer = '';

        child.stdout.on('data', handleStandaloneResolveObserverStdout);
        child.stderr.on('data', (chunk) => {
            const text = chunk.toString().trim();
            if (text) console.error('[AI Director] Resolve UI observer:', text);
        });
        child.on('error', (error) => {
            if (standaloneResolveObserverProcess === child) standaloneResolveObserverProcess = null;
            standaloneResolveObserverNextStartAt = Date.now() + STANDALONE_RESOLVE_UI_OBSERVER_RETRY_MS;
            setStandaloneResolveObserverState({
                connected: false,
                resolvePid: null,
                currentPage: null,
                currentProject: null,
                mainWindowTitle: null,
                error: error?.message || String(error)
            });
        });
        child.on('exit', (code, signal) => {
            if (standaloneResolveObserverProcess === child) standaloneResolveObserverProcess = null;
            standaloneResolveObserverNextStartAt = Date.now() + STANDALONE_RESOLVE_UI_OBSERVER_RETRY_MS;
            setStandaloneResolveObserverState({
                connected: false,
                resolvePid: null,
                currentPage: null,
                currentProject: null,
                mainWindowTitle: null,
                error: shuttingDown
                    ? null
                    : `Resolve UI status observer exited (code=${code ?? 'null'}, signal=${signal ?? 'null'}).`
            });
        });

        return true;
    }).catch((error) => {
        standaloneResolveObserverNextStartAt = Date.now() + STANDALONE_RESOLVE_UI_OBSERVER_RETRY_MS;
        setStandaloneResolveObserverState({
            connected: false,
            resolvePid: null,
            currentPage: null,
            currentProject: null,
            mainWindowTitle: null,
            error: error?.message || String(error)
        });
        return false;
    }).finally(() => {
        standaloneResolveObserverStartPromise = null;
    });

    return standaloneResolveObserverStartPromise;
}

async function stopStandaloneResolveObserver() {
    const child = standaloneResolveObserverProcess;
    standaloneResolveObserverProcess = null;
    standaloneResolveObserverBuffer = '';
    if (!child) return;

    try {
        await stopChildProcessTree(child, 3000);
    } catch (error) {
        console.error('[AI Director] Resolve UI observer cleanup failed:', error);
    }
}

async function getStandaloneResolveStatus() {
    await ensureStandaloneResolveObserver();
    return currentStandaloneResolveStatus();
}

async function getBridgeStatus() {
    if (!WorkflowIntegration) {
        return getStandaloneResolveStatus();
    }

    let moduleInfo = null;

    try {
        moduleInfo = WorkflowIntegration.GetInfo();
    } catch (error) {
        moduleInfo = { error: String(error) };
    }

    const resolve = await getResolve();
    const currentPage = await resolve.GetCurrentPage();

    let projectName = null;
    const projectManager = await resolve.GetProjectManager();

    if (projectManager) {
        const project = await projectManager.GetCurrentProject();

        if (project) {
            projectName = await project.GetName();
        }
    }

    return {
        connected: true,
        pluginId: PLUGIN_ID,
        workflowIntegration: moduleInfo,
        currentPage: currentPage || null,
        currentProject: projectName || null
    };
}

function httpHealthCheck(timeoutMs = 2000) {
    return new Promise((resolve) => {
        const request = http.get(`${LLAMA_BASE_URL}/health`, (response) => {
            response.resume();
            response.on('end', () => {
                resolve(response.statusCode === 200);
            });
        });

        request.setTimeout(timeoutMs, () => {
            request.destroy();
            resolve(false);
        });

        request.on('error', () => resolve(false));
    });
}

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function queryNvidiaCudaCompatibility() {
    if (process.platform !== 'win32') {
        return Promise.resolve({ ok: true, platformBypass: true });
    }

    const systemRoot = process.env.SystemRoot || process.env.WINDIR || 'C:\\Windows';
    const nvidiaSmi = path.join(systemRoot, 'System32', 'nvidia-smi.exe');

    return new Promise((resolve) => {
        execFile(
            nvidiaSmi,
            ['--query-gpu=name,driver_version,compute_cap', '--format=csv,noheader,nounits'],
            { windowsHide: true, timeout: 5000, maxBuffer: 32768 },
            (error, stdout, stderr) => {
                if (error) {
                    const detail = String(stderr || error.message || 'unknown NVIDIA driver query error').trim();
                    resolve({
                        ok: false,
                        error: `AI Director CUDA 13.3 requires NVIDIA driver ${CUDA_MINIMUM_NVIDIA_DRIVER_MAJOR} or newer and a supported NVIDIA GPU. Driver query failed: ${detail}`
                    });
                    return;
                }

                const rows = String(stdout || '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
                const observed = [];
                let compatible = null;

                for (const row of rows) {
                    const fields = row.split(',').map((part) => part.trim());
                    if (fields.length < 3) continue;
                    const driverVersion = fields[1];
                    const driverMajor = Number.parseInt(driverVersion.split('.')[0], 10);
                    const capabilityValue = Number.parseFloat(fields[2]);
                    const computeCapability = Number.isFinite(capabilityValue) ? capabilityValue.toFixed(1) : fields[2];
                    const item = { name: fields[0], driverVersion, driverMajor, computeCapability };
                    observed.push(item);
                    if (
                        Number.isInteger(driverMajor) &&
                        driverMajor >= CUDA_MINIMUM_NVIDIA_DRIVER_MAJOR &&
                        CUDA_SUPPORTED_COMPUTE_CAPABILITIES.has(computeCapability)
                    ) {
                        compatible = item;
                        break;
                    }
                }

                if (!compatible) {
                    const summary = observed.length
                        ? observed.map((item) => `${item.name} driver=${item.driverVersion} compute=${item.computeCapability}`).join('; ')
                        : 'no NVIDIA GPU rows returned';
                    resolve({
                        ok: false,
                        error: `AI Director CUDA 13.3 requires NVIDIA driver ${CUDA_MINIMUM_NVIDIA_DRIVER_MAJOR}+ and compute capability 7.5/8.0/8.6/8.9/9.0/12.0/12.1. Detected: ${summary}`
                    });
                    return;
                }

                resolve({ ok: true, ...compatible });
            }
        );
    });
}

function requiredServerRuntimeFilesPresent(profile = getSelectedServerProfile()) {
    const runtimeFiles = profile.requiredRuntimeFiles.map((file) =>
        path.join(profile.root, file)
    );
    const cudaRuntimeFiles = CUDA_RUNTIME_FILES.map((file) =>
        path.join(CUDA_RUNTIME_ROOT, file)
    );

    return [
        ...runtimeFiles,
        ...cudaRuntimeFiles,
        LLAMA_MCP_CONFIG,
        VFX_PYTHON,
        VFX_HOST,
        MCP_PYTHON,
        path.join(MCP_PYTHON_ROOT, 'python311.zip'),
        path.join(MCP_PYTHON_ROOT, 'python311._pth'),
        path.join(MCP_PYTHON_ROOT, 'Lib', 'site-packages', 'mcp'),
        path.join(MCP_PYTHON_ROOT, 'Lib', 'site-packages', 'pywin32_system32'),
        MCP_LIVE_SERVER,
        MCP_ADVANCED_BIN,
        MCP_ADVANCED_PACKAGE,
        MCP_ADVANCED_NODE_MODULES,
        MCP_ADVANCED_SHARP_NATIVE,
        MCP_ADVANCED_SQLITE_NATIVE,
        NODE_EXE,
        NPM_CLI
    ].every((file) => fs.existsSync(file));
}

const MCP_CHILD_ENVIRONMENT_KEYS = new Set([
    'PATH',
    'NODE_PATH',
    'NODE_OPTIONS',
    'PYTHONHOME',
    'PYTHONPATH',
    'PYTHONSTARTUP',
    'VIRTUAL_ENV',
    'CONDA_PREFIX',
    'CONDA_DEFAULT_ENV'
]);

function systemRuntimePathEntries() {
    if (process.platform !== 'win32') return ['/usr/bin', '/bin'];
    const systemRoot = process.env.SystemRoot || process.env.WINDIR || 'C:\\Windows';
    return [
        path.join(systemRoot, 'System32'),
        path.join(systemRoot, 'System32', 'WindowsPowerShell', 'v1.0'),
        path.join(systemRoot, 'System32', 'wbem'),
        systemRoot
    ];
}

function buildServerEnvironment(profile = getSelectedServerProfile()) {
    const env = { ...process.env };

    for (const key of Object.keys(env)) {
        const normalized = key.toUpperCase();
        if (
            MCP_CHILD_ENVIRONMENT_KEYS.has(normalized) ||
            CUDA_ENVIRONMENT_KEYS.has(normalized) ||
            normalized.startsWith('CUDA_PATH_V')
        ) {
            delete env[key];
        }
    }

    const serverPathEntries = [
        CUDA_RUNTIME_ROOT,
        profile.root,
        ProductPaths.resolveNodeRoot,
        MCP_PYTHON_ROOT,
        ...systemRuntimePathEntries()
    ].filter((entry) => entry);

    const configured = normalizeFfmpegConfig(persistentSettings?.ffmpeg);
    const statusMatchesConfig = Boolean(
        configured.mode === 'external' &&
        ffmpegRuntimeStatus?.available &&
        ffmpegRuntimeStatus?.state === 'ready' &&
        String(ffmpegRuntimeStatus.ffmpegPath || '').toLowerCase() === String(configured.ffmpegPath || '').toLowerCase() &&
        String(ffmpegRuntimeStatus.ffprobePath || '').toLowerCase() === String(configured.ffprobePath || '').toLowerCase()
    );

    const ffmpegDirectories = statusMatchesConfig
        ? [...new Set([path.dirname(configured.ffmpegPath), path.dirname(configured.ffprobePath)])]
        : [];
    env.PATH = [...ffmpegDirectories, ...serverPathEntries].join(path.delimiter);
    env.AI_DIRECTOR_FFMPEG_MODE = statusMatchesConfig ? 'external' : 'disabled';
    env.AI_DIRECTOR_FFMPEG_AVAILABLE = statusMatchesConfig ? 'true' : 'false';
    if (statusMatchesConfig) {
        env.AI_DIRECTOR_FFMPEG_EXE = configured.ffmpegPath;
        env.AI_DIRECTOR_FFPROBE_EXE = configured.ffprobePath;
        env.AI_DIRECTOR_FFMPEG_SHA256 = ffmpegRuntimeStatus.ffmpegSha256 || '';
        env.AI_DIRECTOR_FFPROBE_SHA256 = ffmpegRuntimeStatus.ffprobeSha256 || '';
    } else {
        delete env.AI_DIRECTOR_FFMPEG_EXE;
        delete env.AI_DIRECTOR_FFPROBE_EXE;
        delete env.AI_DIRECTOR_FFMPEG_SHA256;
        delete env.AI_DIRECTOR_FFPROBE_SHA256;
    }

    return env;
}

function ffmpegFreeInheritedPathEntries(env = process.env) {
    let rawPath = '';
    for (const [key, value] of Object.entries(env || {})) {
        if (key.toUpperCase() === 'PATH') {
            rawPath = String(value || '');
            break;
        }
    }
    const seen = new Set();
    const clean = [];
    for (const rawEntry of rawPath.split(path.delimiter)) {
        const entry = String(rawEntry || '').trim().replace(/^"|"$/g, '');
        if (!entry) continue;
        const key = process.platform === 'win32' ? entry.toLowerCase() : entry;
        if (seen.has(key)) continue;
        seen.add(key);
        let containsFfmpeg = false;
        if (process.platform === 'win32') {
            try {
                containsFfmpeg = fs.existsSync(path.join(entry, 'ffmpeg.exe')) || fs.existsSync(path.join(entry, 'ffprobe.exe'));
            } catch (_) {}
        }
        if (!containsFfmpeg) clean.push(entry);
    }
    return clean;
}

function buildBackendEnvironment() {
    const env = { ...process.env };
    const cleanPathEntries = ffmpegFreeInheritedPathEntries(env);
    for (const key of Object.keys(env)) {
        if (key.toUpperCase() === 'PATH') delete env[key];
    }

    const configured = normalizeFfmpegConfig(persistentSettings?.ffmpeg);
    const statusMatchesConfig = Boolean(
        configured.mode === 'external' &&
        ffmpegRuntimeStatus?.available &&
        ffmpegRuntimeStatus?.state === 'ready' &&
        String(ffmpegRuntimeStatus.ffmpegPath || '').toLowerCase() === String(configured.ffmpegPath || '').toLowerCase() &&
        String(ffmpegRuntimeStatus.ffprobePath || '').toLowerCase() === String(configured.ffprobePath || '').toLowerCase()
    );

    const ffmpegDirectories = statusMatchesConfig
        ? [...new Set([path.dirname(configured.ffmpegPath), path.dirname(configured.ffprobePath)])]
        : [];
    env.PATH = [...ffmpegDirectories, ...cleanPathEntries].join(path.delimiter);
    env.AI_DIRECTOR_FFMPEG_MODE = statusMatchesConfig ? 'external' : 'disabled';
    env.AI_DIRECTOR_FFMPEG_AVAILABLE = statusMatchesConfig ? 'true' : 'false';
    if (statusMatchesConfig) {
        env.AI_DIRECTOR_FFMPEG_EXE = configured.ffmpegPath;
        env.AI_DIRECTOR_FFPROBE_EXE = configured.ffprobePath;
        env.AI_DIRECTOR_FFMPEG_SHA256 = ffmpegRuntimeStatus.ffmpegSha256 || '';
        env.AI_DIRECTOR_FFPROBE_SHA256 = ffmpegRuntimeStatus.ffprobeSha256 || '';
    } else {
        delete env.AI_DIRECTOR_FFMPEG_EXE;
        delete env.AI_DIRECTOR_FFPROBE_EXE;
        delete env.AI_DIRECTOR_FFMPEG_SHA256;
        delete env.AI_DIRECTOR_FFPROBE_SHA256;
    }
    return env;
}

function requiredModelFilesPresent(model = getSelectedModelProfile()) {
    if (!model || !model.primaryModel || !model.available) return false;
    const required = [model.primaryModel];
    if (model.draftModel) required.push(model.draftModel);
    return required.every((file) => file && fs.existsSync(file));
}

function requiredServerFilesPresent(
    profile = getSelectedServerProfile(),
    model = getSelectedModelProfile()
) {
    return requiredServerRuntimeFilesPresent(profile) && requiredModelFilesPresent(model);
}

function inspectListeningLlamaProcess() {
    if (process.platform !== 'win32') {
        return Promise.resolve({
            ok: false,
            error: 'AI Director can only verify llama-server ownership on Windows.'
        });
    }

    const command = [
        '$c = Get-NetTCPConnection -LocalPort ' + String(LLAMA_PORT) + ' -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1;',
        'if ($null -eq $c) { exit 2 }',
        '$p = Get-CimInstance Win32_Process -Filter "ProcessId = $($c.OwningProcess)" | Select-Object -First 1 ProcessId,ParentProcessId,ExecutablePath,CommandLine;',
        'if ($null -eq $p) { exit 3 }',
        '$p | ConvertTo-Json -Compress'
    ].join(' ');

    return new Promise((resolve) => {
        execFile(
            'powershell.exe',
            ['-NoProfile', '-NonInteractive', '-Command', command],
            { windowsHide: true, timeout: 5000, maxBuffer: 32768 },
            (error, stdout) => {
                if (error) {
                    resolve({
                        ok: false,
                        error: `Could not inspect the listener on port ${LLAMA_PORT}.`
                    });
                    return;
                }

                try {
                    const info = JSON.parse(String(stdout || '').trim());
                    resolve({ ok: true, info });
                } catch (_error) {
                    resolve({
                        ok: false,
                        error: 'The listener identity probe returned invalid data.'
                    });
                }
            }
        );
    });
}

function normalizeProcessText(value) {
    return String(value || '')
        .replace(/\\/g, '/')
        .replace(/"/g, '')
        .toLowerCase();
}

function launchOptionValue(args, flag) {
    const index = args.indexOf(flag);
    return index >= 0 && index + 1 < args.length ? String(args[index + 1]) : null;
}

async function verifyExistingLlamaServer(
    profile = getSelectedServerProfile(),
    model = getSelectedModelProfile()
) {
    const inspected = await inspectListeningLlamaProcess();
    if (!inspected.ok) {
        return inspected;
    }

    if (!model) {
        return { ok: false, error: 'No detected model is selected.' };
    }

    const info = inspected.info || {};
    const executablePath = normalizeProcessText(info.ExecutablePath);
    const commandLine = normalizeProcessText(info.CommandLine);
    const expectedExecutable = normalizeProcessText(profile.exe);
    const expectedModel = normalizeProcessText(model.primaryModel);
    const expectedMcpConfig = normalizeProcessText(LLAMA_MCP_CONFIG);

    if (executablePath !== expectedExecutable) {
        return {
            ok: false,
            error: `Port ${LLAMA_PORT} is served by an unexpected executable: ${info.ExecutablePath || '(unknown)'}.`
        };
    }

    const requiredArguments = [
        expectedModel,
        expectedMcpConfig,
        `--alias ${normalizeProcessText(model.alias)}`,
        '--load-mode none',
        `-c ${String(persistentSettings.runtime.contextLength)}`,
        `--lazy-mode ${getEffectiveLazyMode(profile, model)}`,
        `--port ${String(LLAMA_PORT)}`
    ];

    if (model.draftModel) {
        requiredArguments.push(
            normalizeProcessText(model.draftModel),
            '--spec-type draft-mtp'
        );
    }

    const modelArgs = getModelLaunchArgs(model, persistentSettings);
    const commonArgs = getCommonLaunchArgs(persistentSettings);
    for (const flag of ['--fit', '-ngl', '--n-cpu-moe', '--reasoning-format']) {
        const value = launchOptionValue(modelArgs, flag);
        if (value !== null) requiredArguments.push(`${flag} ${normalizeProcessText(value)}`);
    }
    for (const flag of ['-ctk', '-ctv', '-b', '-ub', '-fa', '-t', '-tb']) {
        const value = launchOptionValue(commonArgs, flag);
        if (value !== null) requiredArguments.push(`${flag} ${normalizeProcessText(value)}`);
    }

    const missing = requiredArguments.filter((value) => !commandLine.includes(value));
    if (missing.length) {
        return {
            ok: false,
            error: `Port ${LLAMA_PORT} is served by llama-server, but its live command line does not match AI Director's configured server/model/MCP/context recipe.`
        };
    }

    return {
        ok: true,
        pid: Number(info.ProcessId),
        parentPid: Number(info.ParentProcessId),
        executablePath: info.ExecutablePath || null,
        commandLine: info.CommandLine || null
    };
}

function getServerStatus() {
    const profile = getSelectedServerProfile();
    const model = getSelectedModelProfile();
    const profileState = {
        profile: persistentSettings.setupCompleted ? profile.id : null,
        profileLabel: persistentSettings.setupCompleted ? profile.label : 'Not configured',
        profileDescription: persistentSettings.setupCompleted ? profile.description : 'Complete first-run setup to start AI Director',
        modelProfile: model?.id || null,
        modelLabel: model?.label || 'No detected model',
        modelAlias: model?.alias || 'No model',
        modelDescription: model?.description || 'Open Settings and rescan LM Studio models.',
        setupRequired: !persistentSettings.setupCompleted,
        settingsApplying: settingsApplyInProgress,
        profileSwitchAllowed: canSwitchServerProfileNow(),
        runtimeSettings: { ...persistentSettings.runtime },
        tuningSettings: { ...(persistentSettings.tuning || DEFAULT_TUNING_SETTINGS) },
        primeExecutionCache: persistentSettings.primeExecutionCache
    };

    if (!persistentSettings.setupCompleted) {
        return {
            ...profileState,
            state: 'unconfigured',
            ownership: 'none',
            endpoint: LLAMA_BASE_URL,
            desired: false,
            debug: debugEnabled,
            error: settingsLoadError
        };
    }

    if (serverReady) {
        return {
            ...profileState,
            state: 'connected',
            ownership: serverOwned ? 'owned' : 'external',
            endpoint: LLAMA_BASE_URL,
            desired: serverDesired,
            debug: debugEnabled
        };
    }

    if (serverProcess || serverStartPromise) {
        return {
            ...profileState,
            state: 'starting',
            ownership: serverOwned ? 'owned' : 'unknown',
            endpoint: LLAMA_BASE_URL,
            desired: serverDesired,
            debug: debugEnabled
        };
    }

    return {
        ...profileState,
        state: 'offline',
        ownership: 'none',
        endpoint: LLAMA_BASE_URL,
        desired: serverDesired,
        debug: debugEnabled
    };
}

async function waitForServerReady(timeoutMs = 180000) {
    const deadline = Date.now() + timeoutMs;

    while (Date.now() < deadline) {
        if (await httpHealthCheck(2500)) {
            serverReady = true;
            notifyServerStatus(getServerStatus());
            return true;
        }

        await sleep(500);
    }

    return false;
}

function stopChildProcessTree(child, timeoutMs = 5000) {
    if (!child || child.killed || !child.pid) {
        return Promise.resolve();
    }

    return new Promise((resolve) => {
        let settled = false;
        const finish = () => {
            if (settled) return;
            settled = true;
            resolve();
        };

        child.once('exit', finish);

        if (process.platform === 'win32') {
            execFile(
                'taskkill',
                ['/PID', String(child.pid), '/T', '/F'],
                { windowsHide: true },
                () => {}
            );
        } else {
            try {
                child.kill('SIGTERM');
            } catch (_error) {
                finish();
            }
        }

        setTimeout(() => {
            if (!settled) {
                try {
                    if (!child.killed) child.kill();
                } catch (_error) {
                    // Process may already have exited.
                }
                finish();
            }
        }, timeoutMs);
    });
}

async function ensureLlamaServer() {
    const profile = getSelectedServerProfile();

    if (!serverDesired) {
        throw new Error('AI Director server is stopped.');
    }

    if (serverReady && (serverProcess || !serverOwned)) {
        return getServerStatus();
    }

    if (await httpHealthCheck()) {
        const verified = await verifyExistingLlamaServer(profile);
        if (!verified.ok) {
            const error = new Error(verified.error || 'AI Director could not verify the llama-server already listening on port 8091.');
            notifyServerStatus({
                state: 'error',
                ownership: 'none',
                endpoint: LLAMA_BASE_URL,
                desired: serverDesired,
                debug: debugEnabled,
                error: error.message
            });
            throw error;
        }

        serverProcess = null;
        serverOwned = false;
        serverReady = true;
        notifyServerStatus(getServerStatus());
        return getServerStatus();
    }

    if (serverStartPromise) {
        return serverStartPromise;
    }

    if (!requiredServerFilesPresent(profile)) {
        const selectedModel = getSelectedModelProfile();
        const error = new Error(
            `AI Director ${profile.label} / ${selectedModel?.label || 'no selected model'} prerequisites are missing (runtime files, required model files, MCP config, Python host, or host script).`
        );
        notifyServerStatus({
            state: 'error',
            ownership: 'none',
            endpoint: LLAMA_BASE_URL,
            desired: serverDesired,
            debug: debugEnabled,
            error: error.message
        });
        throw error;
    }

    let mcpLaunchCompatibility;
    try {
        mcpLaunchCompatibility = UpdateManager.ensureResolveLaunchCompatibility({
            mcpRoot: MCP_ROOT
        });
    } catch (error) {
        const compatibilityError = new Error(
            `AI Director MCP launch compatibility check failed: ${error?.message || String(error)}`
        );
        notifyServerStatus({
            state: 'error',
            ownership: 'none',
            endpoint: LLAMA_BASE_URL,
            desired: serverDesired,
            debug: debugEnabled,
            error: compatibilityError.message
        });
        throw compatibilityError;
    }
    if (mcpLaunchCompatibility?.changed) {
        console.log(
            `[AI Director] Applied MCP Resolve launch compatibility for ${mcpLaunchCompatibility.version}: ` +
            `${mcpLaunchCompatibility.beforeHash} -> ${mcpLaunchCompatibility.afterHash}`
        );
    }

    const cudaCompatibility = await queryNvidiaCudaCompatibility();
    if (!cudaCompatibility.ok) {
        const error = new Error(cudaCompatibility.error || 'AI Director CUDA compatibility check failed.');
        notifyServerStatus({
            state: 'error',
            ownership: 'none',
            endpoint: LLAMA_BASE_URL,
            desired: serverDesired,
            debug: debugEnabled,
            error: error.message
        });
        throw error;
    }

    notifyServerStatus({
        state: 'starting',
        ownership: 'owned',
        endpoint: LLAMA_BASE_URL,
        desired: serverDesired,
        debug: debugEnabled
    });

    serverStartPromise = new Promise((resolve, reject) => {
        let child;

        try {
            const logDir = path.join(ProductPaths.resolveLogsRoot, 'llama');
            fs.mkdirSync(logDir, { recursive: true });

            // Use already-open numeric file descriptors for child stdio.
            // Passing a freshly-created fs.WriteStream can race its async
            // open() and leave spawn() without a usable descriptor on Windows.
            serverStdoutFd = fs.openSync(
                path.join(logDir, 'llama-server.stdout.log'),
                'a'
            );
            serverStderrFd = fs.openSync(
                path.join(logDir, 'llama-server.stderr.log'),
                'a'
            );

            child = spawn(profile.exe, getLlamaArgs(profile), {
                cwd: profile.root,
                windowsHide: true,
                stdio: ['ignore', serverStdoutFd, serverStderrFd],
                env: buildServerEnvironment(profile)
            });

            // The child owns duplicated handles; the parent no longer needs
            // to keep these descriptors open.
            fs.closeSync(serverStdoutFd);
            fs.closeSync(serverStderrFd);
            serverStdoutFd = null;
            serverStderrFd = null;
        } catch (error) {
            if (serverStdoutFd !== null) {
                try { fs.closeSync(serverStdoutFd); } catch (_error) {}
                serverStdoutFd = null;
            }
            if (serverStderrFd !== null) {
                try { fs.closeSync(serverStderrFd); } catch (_error) {}
                serverStderrFd = null;
            }
            reject(error);
            return;
        }

        serverProcess = child;
        serverOwned = true;
        serverReady = false;

        child.once('error', (error) => {
            console.error('[AI Director] llama-server process error:', error);
            serverProcess = null;
            serverOwned = false;
            serverReady = false;
            notifyServerStatus({
                state: 'error',
                ownership: 'none',
                endpoint: LLAMA_BASE_URL,
                desired: serverDesired,
                debug: debugEnabled,
                error: error instanceof Error ? error.message : String(error)
            });
            reject(error);
        });

        child.once('exit', (code, signal) => {
            console.log('[AI Director] llama-server exited:', code, signal);
            serverProcess = null;
            serverReady = false;


            if (serverOwned) {
                serverOwned = false;
            }

            notifyServerStatus({
                state: 'offline',
                ownership: 'none',
                endpoint: LLAMA_BASE_URL,
                desired: serverDesired,
                debug: debugEnabled
            });

            if (!shuttingDown && serverDesired) {
                backendReadyInfo = null;
                notifyBackendStatus({ state: 'offline' });
            }
        });

        waitForServerReady()
            .then((ready) => {
                if (!ready) {
                    const error = new Error(
                        'llama-server did not become ready within 180 seconds.'
                    );

                    notifyServerStatus({
                        state: 'error',
                        ownership: 'owned',
                        endpoint: LLAMA_BASE_URL,
                        desired: serverDesired,
                        error: error.message
                    });

                    stopChildProcessTree(child).finally(() => reject(error));
                    return;
                }

                resolve(getServerStatus());
            })
            .catch(reject);
    }).finally(() => {
        serverStartPromise = null;
    });

    return serverStartPromise;
}

function rejectPendingBackendRequests(error) {
    for (const pending of pendingBackendRequests.values()) {
        clearTimeout(pending.timeout);
        if (pending.operation === 'chat') {
            finalizePendingSessionTurn(pending, 'error', {
                error: error instanceof Error ? error.message : String(error)
            });
        }
        pending.reject(error);
    }

    pendingBackendRequests.clear();
    activeChatRequestId = null;
    syncStandaloneResolveObserverPauseState();
}

function handleBackendMessage(message) {
    if (!message || typeof message !== 'object') return;

    if (message.event === 'progress') {
        const pending = message.id
            ? pendingBackendRequests.get(message.id)
            : null;

        if (pending?.operation === 'chat') {
            recordSessionProgress(pending, message.progress);
        }
        if (message.progress?.kind === 'context_status') {
            updateContextStatus(message.progress.context);
        }

        if (
            pending?.operation === 'chat' &&
            mainWindow &&
            !mainWindow.isDestroyed()
        ) {
            mainWindow.webContents.send('aid:chatProgress', {
                requestId: message.id,
                clientRequestId: pending.clientRequestId || null,
                progress: message.progress && typeof message.progress === 'object'
                    ? message.progress
                    : {}
            });
        }

        return;
    }

    if (message.event === 'ready') {
        backendReadyInfo = message;

        notifyBackendStatus({
            state: backendCachePrimed ? 'connected' : 'cache_cold',
            model: message.model || null,
            endpoint: message.endpoint || null,
            toolCount: Number.isFinite(message.tool_count)
                ? message.tool_count
                : 0
        });

        return;
    }

    if (message.id && pendingBackendRequests.has(message.id)) {
        const pending = pendingBackendRequests.get(message.id);
        pendingBackendRequests.delete(message.id);
        clearTimeout(pending.timeout);

        if (pending.operation === 'chat') {
            const result = message?.result && typeof message.result === 'object'
                ? message.result
                : null;
            if (message.ok && result) {
                finalizePendingSessionTurn(pending, 'completed', {
                    assistant: result.final_message || '',
                    rounds: result.rounds || 0,
                    telemetry: result.telemetry || null
                });
            } else {
                finalizePendingSessionTurn(pending, 'error', {
                    error: message?.error || 'VFX backend request failed.'
                });
            }
        }

        if (pending.operation === 'chat' && activeChatRequestId === message.id) {
            activeChatRequestId = null;
    syncStandaloneResolveObserverPauseState();
        }

        pending.resolve(message);
    }
}

function handleBackendStdout(chunk) {
    backendBuffer += chunk.toString();

    while (true) {
        const newlineIndex = backendBuffer.indexOf('\n');
        if (newlineIndex === -1) break;

        const line = backendBuffer.slice(0, newlineIndex).trim();
        backendBuffer = backendBuffer.slice(newlineIndex + 1);

        if (!line) continue;

        try {
            handleBackendMessage(JSON.parse(line));
        } catch (error) {
            console.error('[AI Director] Invalid backend JSON:', line, error);
        }
    }
}

async function startBackendHost() {
    if (backendAutoRestartTimer) {
        clearTimeout(backendAutoRestartTimer);
        backendAutoRestartTimer = null;
    }

    if (!serverDesired) {
        throw new Error('AI Director server is stopped.');
    }

    if (backendProcess && backendReadyInfo) {
        return backendReadyInfo;
    }

    if (backendStartPromise) {
        return backendStartPromise;
    }

    await ensureLlamaServer();
    const selectedModel = getSelectedModelProfile();
    if (!selectedModel) {
        throw new Error('No detected model is selected for the Python backend.');
    }

    const effectiveInference = getEffectiveInferenceSettings(persistentSettings, selectedModel);
    notifyBackendStatus({ state: 'starting' });

    backendStartPromise = new Promise((resolve, reject) => {
        let child;
        let readyTimer = null;
        let settled = false;

        const finishReady = (error, info) => {
            if (settled) return;
            settled = true;
            if (readyTimer) clearTimeout(readyTimer);
            if (!error && backendAutoRestartTimer) {
                clearTimeout(backendAutoRestartTimer);
                backendAutoRestartTimer = null;
            }
            error ? reject(error) : resolve(info);
        };

        try {
            child = spawn(VFX_PYTHON, ['-u', VFX_HOST], {
                cwd: VFX_ROOT,
                windowsHide: true,
                stdio: ['pipe', 'pipe', 'pipe'],
                env: {
                    ...buildBackendEnvironment(),
                    AI_DIRECTOR_HOME: ProductPaths.vendorRoot,
                    DAVINCI_RESOLVE_AI_DIRECTOR_ROOT: ProductPaths.resolveRoot,
                    DAVINCI_RESOLVE_AI_DIRECTOR_BACKEND_ROOT: ProductPaths.backendRoot,
                    DAVINCI_RESOLVE_AI_DIRECTOR_MCP_CONFIG: ProductPaths.resolveMcpConfig,
                    AI_DIRECTOR_COMMON_ROOT: ProductPaths.commonRoot,
                    FIRSTGAME_VFX_MODEL: selectedModel.alias,
                    FIRSTGAME_VFX_CONTEXT_LENGTH: String(persistentSettings.runtime.contextLength),
                    FIRSTGAME_VFX_MAX_OUTPUT_TOKENS: String(persistentSettings.runtime.maxOutputTokens),
                    FIRSTGAME_VFX_TIMEOUT_SECONDS: String(persistentSettings.runtime.timeoutSeconds),
                    FIRSTGAME_VFX_CONTEXT_OVERFLOW_POLICY: normalizeContextOverflowPolicy(persistentSettings.runtime.contextOverflowPolicy),
                    FIRSTGAME_VFX_TEMPERATURE: String(effectiveInference.temperature),
                    FIRSTGAME_VFX_TOP_P: String(effectiveInference.topP),
                    FIRSTGAME_VFX_TOP_K: String(effectiveInference.topK),
                    FIRSTGAME_VFX_MIN_P: String(effectiveInference.minP),
                    FIRSTGAME_VFX_PRESENCE_PENALTY: String(effectiveInference.presencePenalty),
                    FIRSTGAME_VFX_REPETITION_PENALTY: String(effectiveInference.repetitionPenalty),
                    FIRSTGAME_VFX_CACHE_PROMPT: effectiveInference.promptCacheReuse ? 'true' : 'false'

                }
            });
        } catch (error) {
            finishReady(error);
            return;
        }

        backendProcess = child;
        backendReadyInfo = null;
        backendBuffer = '';

        child.stdout.on('data', handleBackendStdout);

        child.stderr.on('data', (chunk) => {
            console.error('[AI Director backend]', chunk.toString().trimEnd());
        });

        child.once('error', (error) => {
            console.error('[AI Director] Backend process error:', error);
            notifyBackendStatus({
                state: 'error',
                error: error instanceof Error ? error.message : String(error)
            });
            finishReady(error);
        });

        child.once('exit', (code, signal) => {
            const error = new Error(
                `VFX host exited (code=${code}, signal=${signal || 'none'}).`
            );

            console.log('[AI Director] Backend host exited:', code, signal);

            // The execution cache belongs to llama-server, not to the Python
            // bridge. Preserve readiness across an unexpected bridge crash only
            // when we can prove the exact same AI Director-owned server process
            // survived and the cache had already been fully primed.
            const cacheWasReady = Boolean(
                backendCachePrimed &&
                !backendPrimeInProgress &&
                serverReady &&
                serverOwned &&
                serverProcess &&
                Number.isInteger(serverProcess.pid)
            );
            const serverPidAtBackendExit = cacheWasReady
                ? serverProcess.pid
                : null;

            backendProcess = null;
            backendReadyInfo = null;
            backendBuffer = '';
            backendPrimeInProgress = false;
            backendCachePrimed = false;

            notifyBackendStatus({ state: 'offline' });
            rejectPendingBackendRequests(error);
            finishReady(error);

            const intentionalStop = backendStopIntent;
            if (intentionalStop) {
                return;
            }

            if (!shuttingDown && serverDesired && !cleanupStarted) {
                const now = Date.now();
                if (!backendAutoRestartWindowStarted || now - backendAutoRestartWindowStarted > BACKEND_AUTORESTART_WINDOW_MS) {
                    backendAutoRestartWindowStarted = now;
                    backendAutoRestartAttempts = 0;
                }

                if (backendAutoRestartAttempts >= BACKEND_AUTORESTART_MAX_ATTEMPTS) {
                    notifyBackendStatus({
                        state: 'error',
                        error: `VFX host crashed repeatedly; automatic restart was stopped after ${BACKEND_AUTORESTART_MAX_ATTEMPTS} attempts.`
                    });
                    return;
                }

                backendAutoRestartAttempts += 1;
                const delay = Math.min(
                    BACKEND_AUTORESTART_MAX_DELAY_MS,
                    BACKEND_AUTORESTART_BASE_DELAY_MS * (2 ** (backendAutoRestartAttempts - 1))
                );

                backendAutoRestartTimer = setTimeout(() => {
                    backendAutoRestartTimer = null;
                    if (!backendProcess && serverDesired && !shuttingDown && !cleanupStarted) {
                        startBackendHost()
                            .then(async () => {
                                const sameOwnedServer = Boolean(
                                    cacheWasReady &&
                                    serverReady &&
                                    serverOwned &&
                                    serverProcess &&
                                    serverProcess.pid === serverPidAtBackendExit
                                );

                                if (sameOwnedServer) {
                                    markBackendReadyWithoutPrime();
                                    return;
                                }

                                // If the server instance changed, the previous
                                // cache cannot be trusted. Rebuild readiness using
                                // the normal configured prime policy instead.
                                await ensureExecutionCacheReady();
                            })
                            .catch((restartError) => {
                                console.error(
                                    '[AI Director] Backend automatic restart failed:',
                                    restartError
                                );
                                notifyBackendStatus({
                                    state: 'error',
                                    error: restartError instanceof Error
                                        ? restartError.message
                                        : String(restartError)
                                });
                            });
                    }
                }, delay);
            }
        });

        readyTimer = setTimeout(() => {
            const error = new Error(
                'VFX host did not become ready within 60 seconds.'
            );
            finishReady(error);
            stopChildProcessTree(child).catch(() => {});
        }, 60000);

        const originalMessageHandler = handleBackendMessage;
        void originalMessageHandler;

        const readyPoll = setInterval(() => {
            if (backendReadyInfo) {
                clearInterval(readyPoll);
                finishReady(null, backendReadyInfo);
            } else if (!backendProcess) {
                clearInterval(readyPoll);
            }
        }, 50);

        // Ensure the interval cannot outlive the startup wait.
        setTimeout(() => clearInterval(readyPoll), 60000);
    }).finally(() => {
        backendStartPromise = null;
    });

    return backendStartPromise;
}

function postLlamaJson(pathname, payload, timeoutMs = 30000) {
    return new Promise((resolve, reject) => {
        const body = Buffer.from(JSON.stringify(payload), 'utf8');
        const request = http.request({
            hostname: LLAMA_HOST,
            port: LLAMA_PORT,
            path: pathname,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': body.length
            }
        }, (response) => {
            let text = '';
            response.setEncoding('utf8');
            response.on('data', (chunk) => { text += chunk; });
            response.on('end', () => {
                if (response.statusCode < 200 || response.statusCode >= 300) {
                    reject(new Error(`llama ${pathname} returned HTTP ${response.statusCode}: ${text.slice(0, 500)}`));
                    return;
                }
                try {
                    const parsed = JSON.parse(text);
                    if (parsed && typeof parsed === 'object' && parsed.error) {
                        reject(new Error(`llama ${pathname} returned an error: ${parsed.error}`));
                        return;
                    }
                    resolve(parsed);
                } catch (error) {
                    reject(new Error(`Could not parse llama ${pathname} response: ${error.message}`));
                }
            });
        });
        request.setTimeout(timeoutMs, () => request.destroy(new Error(`llama ${pathname} timed out.`)));
        request.on('error', reject);
        request.write(body);
        request.end();
    });
}

function parseToolJsonText(value) {
    if (typeof value !== 'string') return null;
    const text = value.trim();
    if (!text || (text[0] !== '{' && text[0] !== '[')) return null;
    try {
        return JSON.parse(text);
    } catch (_error) {
        return null;
    }
}

function walkToolResponse(value, visit) {
    const decoded = parseToolJsonText(value);
    if (decoded !== null) {
        walkToolResponse(decoded, visit);
        return;
    }
    visit(value);
    if (Array.isArray(value)) {
        for (const item of value) walkToolResponse(item, visit);
        return;
    }
    if (value && typeof value === 'object') {
        for (const item of Object.values(value)) walkToolResponse(item, visit);
    }
}

function toolResponseError(response) {
    let found = null;
    walkToolResponse(response, (value) => {
        if (found || !value || typeof value !== 'object' || Array.isArray(value)) return;
        if (typeof value.error === 'string' && value.error.trim()) {
            found = value.error.trim();
            return;
        }
        const operation = value._operation;
        if (operation && typeof operation === 'object') {
            const status = String(operation.status || '').toLowerCase();
            if (['failed', 'blocked', 'contradiction'].includes(status)) {
                found = `operation status ${status}`;
            }
        }
    });
    return found;
}

function toolResponseHasKey(response, key) {
    let found = false;
    walkToolResponse(response, (value) => {
        if (!found && value && typeof value === 'object' && !Array.isArray(value) &&
            Object.prototype.hasOwnProperty.call(value, key)) {
            found = true;
        }
    });
    return found;
}

function toolResponseValue(response, key) {
    let found;
    walkToolResponse(response, (value) => {
        if (found !== undefined || !value || typeof value !== 'object' || Array.isArray(value)) return;
        if (Object.prototype.hasOwnProperty.call(value, key)) {
            found = value[key];
        }
    });
    return found;
}

function resolveStatusAllowsManagedUpdate(status) {
    return Boolean(
        status?.hostMode === 'standalone'
            ? status?.resolveRunning === true
            : status?.connected === true
    );
}

async function resolveAvailableForManagedUpdate() {
    try {
        return resolveStatusAllowsManagedUpdate(await getBridgeStatus());
    } catch (_error) {
        return false;
    }
}

async function runReadOnlyResolveUpdateCanary() {
    const response = await postLlamaJson('/tools', {
        tool: 'davinci-resolve_resolve_control',
        params: { action: 'get_page' }
    }, 60000);
    if (!response || typeof response !== 'object') {
        throw new Error('Read-only Resolve update canary returned no structured response.');
    }
    const embeddedError = toolResponseError(response);
    if (embeddedError) {
        throw new Error(`Read-only Resolve update canary failed: ${embeddedError}`);
    }
    if (!toolResponseHasKey(response, 'page')) {
        throw new Error('Read-only Resolve update canary returned no page field.');
    }
    return {
        tool: 'davinci-resolve_resolve_control',
        action: 'get_page',
        pageFieldPresent: true,
        ok: true
    };
}

function sendBackendRequest(operation, payload = {}, metadata = {}) {
    return startBackendHost().then((ready) => {
        if (!ready || !backendProcess || !backendProcess.stdin.writable) {
            throw new Error('VFX backend host is not available.');
        }

        const id = `resolve-${nextRequestId++}`;
        const request = {
            id,
            op: operation,
            ...payload
        };
        const sessionTurn = operation === 'chat'
            ? createPendingSessionTurn(payload?.message)
            : null;

        if (operation === 'chat') {
            request.session_context = buildAIDirectorSessionContext();
            activeChatRequestId = id;
            syncStandaloneResolveObserverPauseState();
        }

        return new Promise((resolve, reject) => {
            const requestTimeoutMs = Math.max(
                60000,
                (persistentSettings.runtime.timeoutSeconds + 300) * 1000
            );
            const timeout = setTimeout(() => {
                const pending = pendingBackendRequests.get(id);
                if (operation === 'chat') {
                    finalizePendingSessionTurn(
                        pending,
                        'timeout',
                        { error: 'VFX backend request timed out.' }
                    );
                }
                pendingBackendRequests.delete(id);

                if (operation === 'chat' && activeChatRequestId === id) {
                    activeChatRequestId = null;
    syncStandaloneResolveObserverPauseState();
                }

                reject(new Error('VFX backend request timed out.'));
            }, requestTimeoutMs);

            pendingBackendRequests.set(id, {
                resolve,
                reject,
                timeout,
                operation,
                clientRequestId: metadata.clientRequestId || null,
                sessionTurn,
                sessionCommitted: false
            });

            try {
                backendProcess.stdin.write(JSON.stringify(request) + '\n');
            } catch (error) {
                clearTimeout(timeout);
                const pending = pendingBackendRequests.get(id);
                if (operation === 'chat') {
                    finalizePendingSessionTurn(pending, 'error', {
                        error: error instanceof Error ? error.message : String(error)
                    });
                }
                pendingBackendRequests.delete(id);

                if (operation === 'chat' && activeChatRequestId === id) {
                    activeChatRequestId = null;
    syncStandaloneResolveObserverPauseState();
                }

                reject(error);
            }
        });
    });
}

function markBackendReadyWithoutPrime() {
    backendPrimeInProgress = false;
    backendCachePrimed = true;
    backendPrimeError = null;
    if (backendProcess && backendReadyInfo) {
        notifyBackendStatus({
            state: 'connected',
            model: backendReadyInfo.model || null,
            endpoint: backendReadyInfo.endpoint || null,
            toolCount: Number.isFinite(backendReadyInfo.tool_count)
                ? backendReadyInfo.tool_count
                : 0
        });
    }
}

async function ensureExecutionCacheReady() {
    if (persistentSettings.primeExecutionCache) {
        return await primeBackendExecutionCache();
    }
    markBackendReadyWithoutPrime();
    return { skipped: true, reason: 'Execution-cache priming is disabled in settings.' };
}

async function primeBackendExecutionCache() {
    if (!backendProcess || !backendReadyInfo) {
        throw new Error('VFX backend host is not ready for execution-cache priming.');
    }

    backendPrimeInProgress = true;
    backendCachePrimed = false;
    backendPrimeError = null;
    notifyBackendStatus({
        state: 'priming',
        model: backendReadyInfo.model || null,
        endpoint: backendReadyInfo.endpoint || null,
        toolCount: Number.isFinite(backendReadyInfo.tool_count)
            ? backendReadyInfo.tool_count
            : 0
    });

    try {
        const response = await sendBackendRequest('prime');
        if (!response || !response.ok) {
            throw new Error(
                response?.error || 'Execution-cache priming failed.'
            );
        }
        backendCachePrimed = true;
        backendPrimeError = null;
        return response.result || {};
    } catch (error) {
        backendCachePrimed = false;
        backendPrimeError = `Execution cache prime failed: ${error?.message || String(error)}`;
        const interruptedByLifecycle = Boolean(
            shuttingDown ||
            profileChangeInProgress ||
            backendStopIntent ||
            !serverDesired
        );
        if (!interruptedByLifecycle) {
            notifyBackendStatus({
                state: 'error',
                error: backendPrimeError
            });
        }
        throw error;
    } finally {
        backendPrimeInProgress = false;
        if (backendCachePrimed && backendProcess && backendReadyInfo) {
            notifyBackendStatus({
                state: 'connected',
                model: backendReadyInfo.model || null,
                endpoint: backendReadyInfo.endpoint || null,
                toolCount: Number.isFinite(backendReadyInfo.tool_count)
                    ? backendReadyInfo.tool_count
                    : 0
            });
        }
    }
}

async function stopBackendHost({ restart = false, preserveExecutionCache = false } = {}) {
    const child = backendProcess;
    const cacheWasReady = Boolean(preserveExecutionCache && backendCachePrimed && serverReady);

    if (!child) {
        backendReadyInfo = null;
        backendPrimeInProgress = false;
        notifyBackendStatus({ state: 'offline' });
        return;
    }

    backendStopIntent = restart ? 'restart' : 'stop';
    backendAutoRestartAttempts = 0;
    backendAutoRestartWindowStarted = 0;
    if (backendAutoRestartTimer) {
        clearTimeout(backendAutoRestartTimer);
        backendAutoRestartTimer = null;
    }

    backendReadyInfo = null;
    backendPrimeInProgress = false;
    rejectPendingBackendRequests(
        new Error('VFX request stopped by user.')
    );

    notifyBackendStatus({
        state: 'stopping'
    });

    await stopChildProcessTree(child, 5000);

    backendProcess = null;
    backendBuffer = '';
    notifyBackendStatus({ state: 'offline' });

    try {
        if (restart && !shuttingDown && serverDesired) {
            await startBackendHost();
            if (cacheWasReady) {
                markBackendReadyWithoutPrime();
            }
        }
    } catch (error) {
        console.error('[AI Director] Backend restart failed:', error);
        throw error;
    } finally {
        backendStopIntent = null;
    }
}

async function stopServer({ internal = false } = {}) {
    if (settingsApplyInProgress && !internal) {
        throw new Error('Server control is unavailable while settings are being applied.');
    }
    if (profileChangeInProgress && !internal) {
        throw new Error('Server control is unavailable while the server profile is changing.');
    }

    if (updateInProgress && !internal) {
        throw new Error('Server control is unavailable during an update.');
    }

    serverDesired = false;
    backendCachePrimed = false;

    await stopBackendHost({ restart: false });

    if (!serverProcess) {
        serverReady = false;
        notifyServerStatus(getServerStatus());
        return { ok: true, state: 'offline' };
    }

    if (!serverOwned) {
        serverDesired = false;
        notifyServerStatus({
            state: 'connected',
            ownership: 'external',
            endpoint: LLAMA_BASE_URL,
            desired: false,
            debug: debugEnabled,
            error: 'Server is owned by an external process and was not stopped.'
        });

        return {
            ok: false,
            state: 'connected',
            ownership: 'external',
            error: 'The running llama-server is external to AI Director, so it was left running.'
        };
    }

    const child = serverProcess;
    await stopChildProcessTree(child, 10000);

    serverProcess = null;
    serverOwned = false;
    serverReady = false;

    notifyServerStatus({
        state: 'offline',
        ownership: 'none',
        endpoint: LLAMA_BASE_URL,
        desired: false
    });

    return { ok: true, state: 'offline' };
}

async function startServer({ internal = false } = {}) {
    if (!persistentSettings.setupCompleted) {
        throw new Error('Complete AI Director setup before starting the server.');
    }
    if (settingsApplyInProgress && !internal) {
        throw new Error('Server control is unavailable while settings are being applied.');
    }
    if (profileChangeInProgress && !internal) {
        throw new Error('Server control is unavailable while the server profile is changing.');
    }

    if (updateInProgress && !internal) {
        throw new Error('Server control is unavailable during an update.');
    }

    serverDesired = true;
    backendCachePrimed = false;

    const server = await ensureLlamaServer();
    await startBackendHost();
    const cachePrime = await ensureExecutionCacheReady();

    notifyServerStatus(server);
    return {
        ok: true,
        server: getServerStatus(),
        backend: getBackendStatus(),
        cachePrime
    };
}

async function setServerProfile(profileId) {
    if (!persistentSettings.setupCompleted) {
        return { ok: false, error: 'Complete first-run setup before changing profiles.', server: getServerStatus() };
    }
    if (settingsApplyInProgress) {
        return { ok: false, error: 'Server profile cannot be changed while settings are being applied.', server: getServerStatus() };
    }
    const nextId = String(profileId || '').toLowerCase();
    const nextProfile = SERVER_PROFILES[nextId];

    if (!nextProfile) {
        return {
            ok: false,
            error: `Unknown server profile: ${profileId}`,
            server: getServerStatus()
        };
    }

    if (profileChangeInProgress) {
        return {
            ok: false,
            error: 'Server profile is already changing.',
            server: getServerStatus()
        };
    }

    if (activeChatRequestId) {
        return {
            ok: false,
            error: 'Server profile cannot be changed while a response is running.',
            server: getServerStatus()
        };
    }

    if (updateInProgress) {
        return {
            ok: false,
            error: 'Server profile cannot be changed during an update.',
            server: getServerStatus()
        };
    }

    if (debugChangeInProgress) {
        return {
            ok: false,
            error: 'Server profile cannot be changed while DEBUG mode is changing.',
            server: getServerStatus()
        };
    }

    if (backendStartPromise || backendAutoRestartTimer) {
        return {
            ok: false,
            error: 'Server profile cannot be changed until the current backend startup or recovery transition finishes.',
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    }

    if (backendPrimeInProgress && (!serverReady || !serverOwned)) {
        return {
            ok: false,
            error: 'Server profile cannot supersede cache priming unless the current llama-server is ready and owned by AI Director.',
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    }

    if (serverReady && !serverOwned) {
        return {
            ok: false,
            error: 'The running llama-server is externally owned; AI Director cannot switch its profile.',
            server: getServerStatus()
        };
    }

    if (serverStartPromise || (serverProcess && !serverReady)) {
        return {
            ok: false,
            error: 'Server profile cannot be changed while the AI Director server is starting.',
            server: getServerStatus()
        };
    }

    const selectedModel = getSelectedModelProfile();
    if (!requiredServerFilesPresent(nextProfile, selectedModel)) {
        return {
            ok: false,
            error: `${nextProfile.label} / ${selectedModel?.label || 'no selected model'} prerequisites are unavailable on this system.`,
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    }

    if (nextId === selectedServerProfileId) {
        return {
            ok: true,
            changed: false,
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    }

    const previousId = selectedServerProfileId;
    const previousSettings = cloneSettings(persistentSettings);
    const wasRunning = Boolean(serverReady && serverOwned);
    profileChangeInProgress = true;

    try {
        if (wasRunning) {
            const stopped = await stopServer({ internal: true });
            if (!stopped.ok) {
                throw new Error(stopped.error || 'AI Director could not stop its llama-server for profile switching.');
            }
        } else if (backendProcess) {
            await stopBackendHost({ restart: false });
        }

        selectedServerProfileId = nextId;
        notifyServerStatus(getServerStatus());

        if (wasRunning) {
            if (shuttingDown) {
                throw new Error('DaVinci Resolve is shutting down; server profile restart was cancelled.');
            }

            // A profile transaction owns only the non-supersedable portion of
            // replacement: stop the old stack, start the requested llama-server,
            // and bring the Python backend to ready. Cache priming is deliberately
            // outside that transaction so the user may change PROFILE again while
            // the new profile is priming.
            serverDesired = true;
            backendCachePrimed = false;
            await ensureLlamaServer();
            await startBackendHost();
        }

        persistentSettings.serverProfile = nextId;
        persistentSettings.setupCompleted = true;
        persistSettings(persistentSettings);

        // Commit the profile transaction before priming. This preserves rollback
        // for real server/backend startup failures but prevents a many-minute cache
        // prime from holding PROFILE disabled. JavaScript runs this synchronously
        // through the prime launch, so there is no interleaving window here.
        profileChangeInProgress = false;
        notifyServerStatus(getServerStatus());

        if (wasRunning) {
            void ensureExecutionCacheReady().catch((primeError) => {
                const interruptedByLifecycle = Boolean(
                    shuttingDown ||
                    profileChangeInProgress ||
                    backendStopIntent ||
                    !serverDesired
                );
                if (!interruptedByLifecycle) {
                    console.error('[AI Director] Profile-switch cache prime failed:', primeError);
                }
            });
        }

        return {
            ok: true,
            changed: true,
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    } catch (error) {
        selectedServerProfileId = previousId;
        persistentSettings = previousSettings;

        if (wasRunning && !shuttingDown && !serverReady) {
            try {
                serverDesired = true;
                await startServer({ internal: true });
            } catch (restoreError) {
                console.error('[AI Director] Failed to restore llama-server after profile change error:', restoreError);
            }
        }

        const message = error instanceof Error ? error.message : String(error);
        notifyServerStatus({
            ...getServerStatus(),
            state: serverReady ? 'connected' : 'error',
            error: message
        });

        return {
            ok: false,
            error: message,
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    } finally {
        profileChangeInProgress = false;
    }
}

function getSettingsState() {
    const profileStates = Object.values(SERVER_PROFILES).map((profile) => ({
        id: profile.id,
        label: profile.label,
        description: profile.description,
        available: requiredServerRuntimeFilesPresent(profile)
    }));

    const rank = { tested: 0, candidate: 1, unvalidated: 2 };
    const modelStates = [...modelCatalog.values()]
        .sort((a, b) => {
            const status = (rank[a.supportStatus] ?? 9) - (rank[b.supportStatus] ?? 9);
            if (status) return status;
            const family = String(a.label).localeCompare(String(b.label));
            if (family) return family;
            return String(a.quantization || a.filename).localeCompare(String(b.quantization || b.filename));
        })
        .map((model) => {
            const inferenceProfile = getInferenceDefaultProfile(model);
            return {
            id: model.id,
            familyId: model.familyId,
            label: model.label,
            shortLabel: model.shortLabel,
            displayLabel: model.quantization ? `${model.label} | ${model.quantization}` : model.label,
            description: model.description,
            alias: model.alias,
            recipe: model.recipe,
            quantization: model.quantization,
            publisher: model.publisher,
            isUnsloth: model.isUnsloth,
            architecture: model.architecture,
            metadataMaxContextLength: model.metadataMaxContextLength,
            trainedForToolUse: model.trainedForToolUse,
            metadataReasoning: model.metadataReasoning,
            reasoningCapable: model.reasoningCapable,
            supportStatus: model.supportStatus,
            recommendedContextLength: model.recommendedContextLength,
            maxContextLength: model.maxContextLength,
            contextTier: model.contextTier,
            relativePath: model.relativePath,
            available: requiredModelFilesPresent(model),
            availabilityReason: model.availabilityReason,
            inferenceDefaults: { ...inferenceProfile.values },
            inferenceDefaultSource: inferenceProfile.source
        };
        });

    const defaults = cloneSettings(DEFAULT_PERSISTENT_SETTINGS);
    defaults.modelProfile = preferredDefaultModelId();

    const visibleSettings = cloneSettings(persistentSettings);
    if (profileChangeInProgress) {
        visibleSettings.serverProfile = selectedServerProfileId;
    }

    return {
        setupRequired: !persistentSettings.setupCompleted,
        loadError: settingsLoadError,
        settingsFilePath: getSettingsFilePath(),
        legacySettingsFilePath: getLegacySettingsFilePath(),
        settings: visibleSettings,
        defaults,
        ffmpegRuntime: { ...ffmpegRuntimeStatus, capabilities: ffmpegRuntimeStatus?.capabilities ? { ...ffmpegRuntimeStatus.capabilities } : null },
        profiles: profileStates,
        models: modelStates,
        modelDiscovery: { ...modelCatalogInfo },
        busy: settingsApplyInProgress,
        runtimeBusy: settingsRuntimeTransitionActive(),
        settingsApplyBlocked: settingsApplyRuntimeTransitionActive(),
        server: getServerStatus(),
        backend: getBackendStatus(),
        host: {
            logicalCpuCount: Math.max(1, os.cpus().length)
        }
    };
}

function settingsImpact(previous, candidate) {
    if (!previous.setupCompleted) return 'full_server';
    if (
        previous.serverProfile !== candidate.serverProfile ||
        previous.modelProfile !== candidate.modelProfile ||
        previous.runtime.contextLength !== candidate.runtime.contextLength ||
        JSON.stringify(previous.tuning || {}) !== JSON.stringify(candidate.tuning || {}) ||
        JSON.stringify(previous.ffmpeg || DEFAULT_FFMPEG_SETTINGS) !== JSON.stringify(candidate.ffmpeg || DEFAULT_FFMPEG_SETTINGS)
    ) return 'full_server';
    if (previous.runtime.maxOutputTokens !== candidate.runtime.maxOutputTokens) return 'backend_reprime';
    if (
        previous.runtime.timeoutSeconds !== candidate.runtime.timeoutSeconds ||
        previous.runtime.contextOverflowPolicy !== candidate.runtime.contextOverflowPolicy ||
        JSON.stringify(previous.inference || DEFAULT_INFERENCE_SETTINGS) !== JSON.stringify(candidate.inference || DEFAULT_INFERENCE_SETTINGS)
    ) return 'backend_only';
    if (!previous.primeExecutionCache && candidate.primeExecutionCache) return 'prime_only';
    return 'none';
}

function adoptOperationalCandidate(candidate) {
    // Appearance has its own immediate-persistence transaction. Operational Apply
    // must never overwrite a skin chosen while server/backend work is in flight.
    const contextConfigurationChanged = Boolean(
        Number(persistentSettings?.runtime?.contextLength) !== Number(candidate?.runtime?.contextLength) ||
        Number(persistentSettings?.runtime?.maxOutputTokens) !== Number(candidate?.runtime?.maxOutputTokens)
    );
    candidate.appearance = currentAppearance();
    persistentSettings = candidate;
    if (contextConfigurationChanged) {
        // The previous exact llama-server usage belongs to the old context window.
        // Reset immediately to the newly configured window so the renderer never
        // presents stale 131K/262K telemetry while a replacement runtime starts.
        resetContextStatus();
    }
}

async function applyPersistentSettings(candidateInput) {
    // Apply against the already-discovered catalog. Settings opens from cached
    // discovery state and explicit Rescan Models owns model discovery; starting
    // a hidden LM Studio scan here can hold the modal in an in-flight state and
    // create a race with server/backend lifecycle transitions.
    if (settingsApplyInProgress) {
        return { ok: false, error: 'Settings are already being applied.', state: getSettingsState() };
    }
    if (activeChatRequestId) {
        return { ok: false, error: 'Settings cannot be changed while a response is running.', state: getSettingsState() };
    }
    if (settingsApplyRuntimeTransitionActive()) {
        return {
            ok: false,
            error: 'Settings cannot be changed until the current non-supersedable server/backend transition finishes.',
            state: getSettingsState()
        };
    }
    if (serverReady && !serverOwned) {
        return { ok: false, error: 'The running llama-server is externally owned; settings cannot reconfigure it.', state: getSettingsState() };
    }

    let candidate;
    try {
        candidate = validateSettingsCandidate({
            ...candidateInput,
            setupCompleted: true
        });
    } catch (error) {
        return { ok: false, error: error?.message || String(error), state: getSettingsState() };
    }

    const profile = SERVER_PROFILES[candidate.serverProfile];
    const model = modelCatalog.get(candidate.modelProfile) || null;
    if (!requiredServerRuntimeFilesPresent(profile)) {
        return {
            ok: false,
            error: `${profile.label} server prerequisites are unavailable on this system.`,
            state: getSettingsState()
        };
    }
    if (!requiredModelFilesPresent(model)) {
        return {
            ok: false,
            error: `${model.label} model files are unavailable on this system.`,
            state: getSettingsState()
        };
    }

    let candidateFfmpegStatus;
    try {
        candidateFfmpegStatus = candidate.ffmpeg.mode === 'external'
            ? await probeExternalFfmpegPair(candidate.ffmpeg)
            : disabledFfmpegRuntimeStatus();
    } catch (error) {
        return {
            ok: false,
            error: `External FFmpeg validation failed: ${error?.message || String(error)}`,
            state: getSettingsState()
        };
    }

    const previous = cloneSettings(persistentSettings);
    const previousFfmpegRuntimeStatus = {
        ...ffmpegRuntimeStatus,
        capabilities: ffmpegRuntimeStatus?.capabilities ? { ...ffmpegRuntimeStatus.capabilities } : null,
        missingRequirements: [...(ffmpegRuntimeStatus?.missingRequirements || [])]
    };
    const previousProfileId = selectedServerProfileId;
    const previousServerDesired = serverDesired;
    const wasRunning = Boolean(serverReady && serverOwned);
    const wasConfigured = Boolean(previous.setupCompleted);
    const wasPriming = Boolean(backendPrimeInProgress);
    const impact = settingsImpact(previous, candidate);
    settingsApplyInProgress = true;
    let primeAfterCommit = false;

    const restorePrevious = async () => {
        try {
            if (serverProcess && serverOwned) {
                await stopServer({ internal: true });
            } else if (backendProcess) {
                await stopBackendHost({ restart: false });
            }
        } catch (stopError) {
            console.error('[AI Director] Failed to stop partial settings state during rollback:', stopError);
        }

        const appearance = currentAppearance();
        persistentSettings = { ...previous, appearance };
        ffmpegRuntimeStatus = previousFfmpegRuntimeStatus;
        resetContextStatus();
        selectedServerProfileId = previousProfileId;
        serverDesired = previousServerDesired;

        if (wasRunning && wasConfigured && !shuttingDown) {
            try {
                serverDesired = true;
                await startServer({ internal: true });
            } catch (restoreError) {
                console.error('[AI Director] Failed to restore previous settings runtime:', restoreError);
            }
        }
    };

    try {
        ffmpegRuntimeStatus = candidateFfmpegStatus;
        // First-run setup always starts the selected profile. Normal settings
        // changes respect an intentionally stopped server and simply persist.
        if (!wasConfigured) {
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            serverDesired = true;
            backendCachePrimed = false;

            // First-run setup uses the same commit boundary as a full-server
            // settings change: establish the selected llama-server and Python
            // backend first, persist the validated configuration, release the
            // settings transaction, then launch optional cache priming.
            await ensureLlamaServer();
            await startBackendHost();
            if (candidate.primeExecutionCache) primeAfterCommit = true;
            else markBackendReadyWithoutPrime();
        } else if (!wasRunning) {
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            serverDesired = previousServerDesired;
        } else if (impact === 'full_server') {
            const stopped = await stopServer({ internal: true });
            if (!stopped.ok) throw new Error(stopped.error || 'Could not stop the current server.');
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            serverDesired = true;
            backendCachePrimed = false;

            // Settings owns only the non-supersedable portion of the restart:
            // bring the requested llama-server and Python backend to stable ready.
            // Cache priming is launched after the settings transaction commits so
            // the modal and PROFILE controls do not remain locked for minutes.
            await ensureLlamaServer();
            await startBackendHost();
            if (candidate.primeExecutionCache) primeAfterCommit = true;
            else markBackendReadyWithoutPrime();
        } else if (impact === 'backend_reprime') {
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            await stopBackendHost({ restart: false });
            await startBackendHost();
            if (candidate.primeExecutionCache) primeAfterCommit = true;
            else markBackendReadyWithoutPrime();
        } else if (impact === 'backend_only') {
            const preserveCache = Boolean(backendCachePrimed && serverReady);
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            await stopBackendHost({ restart: false });
            await startBackendHost();
            if (preserveCache) markBackendReadyWithoutPrime();
            else if (candidate.primeExecutionCache) primeAfterCommit = true;
            else markBackendReadyWithoutPrime();
        } else if (impact === 'prime_only') {
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            primeAfterCommit = true;
        } else if (wasPriming && !candidate.primeExecutionCache) {
            // Disabling priming while a prime is active must supersede that work,
            // not merely flip the persisted flag while the old backend continues
            // evaluating the obsolete prefix. Restart only the backend and mark
            // the new state ready without another prime.
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            await stopBackendHost({ restart: false });
            await startBackendHost();
            markBackendReadyWithoutPrime();
        } else {
            adoptOperationalCandidate(candidate);
            selectedServerProfileId = candidate.serverProfile;
            if (!candidate.primeExecutionCache && backendProcess && backendReadyInfo) {
                markBackendReadyWithoutPrime();
            }
        }

        persistSettings(persistentSettings);
        settingsLoadError = null;
        notifyServerStatus(getServerStatus());
        return {
            ok: true,
            impact,
            state: getSettingsState()
        };
    } catch (error) {
        // A failed settings transaction must never launch a deferred prime for
        // the partially-applied candidate after rollback restores the old state.
        primeAfterCommit = false;
        await restorePrevious();
        const message = error?.message || String(error);
        notifyServerStatus({ ...getServerStatus(), error: message });
        return { ok: false, error: message, state: getSettingsState() };
    } finally {
        settingsApplyInProgress = false;
        notifyServerStatus(getServerStatus());

        // Start cache priming only after the Settings transaction has released its
        // exclusive lifecycle gate. primeBackendExecutionCache marks priming active
        // synchronously before its first await, so there is no renderer-visible gap
        // where a conflicting action can slip between commit and prime startup.
        if (primeAfterCommit && !shuttingDown && serverDesired && serverReady && serverOwned) {
            void ensureExecutionCacheReady().catch((primeError) => {
                const interruptedByLifecycle = Boolean(
                    shuttingDown ||
                    settingsApplyInProgress ||
                    profileChangeInProgress ||
                    backendStopIntent ||
                    !serverDesired
                );
                if (!interruptedByLifecycle) {
                    console.error('[AI Director] Settings cache prime failed:', primeError);
                }
            });
        }
    }
}

async function setDebugMode(enabled) {
    const next = Boolean(enabled);

    if (settingsApplyInProgress) {
        return {
            ok: false,
            error: 'DEBUG mode cannot be changed while settings are being applied.'
        };
    }

    if (debugChangeInProgress) {
        return {
            ok: false,
            error: 'Debug mode is already changing.'
        };
    }

    if (profileChangeInProgress) {
        return {
            ok: false,
            error: 'Debug mode cannot be changed while the server profile is changing.'
        };
    }

    if (activeChatRequestId) {
        return {
            ok: false,
            error: 'Debug mode cannot be changed while a response is running.'
        };
    }

    if (updateInProgress) {
        return {
            ok: false,
            error: 'Debug mode cannot be changed during an update.'
        };
    }

    if (backendStartPromise || backendPrimeInProgress || backendAutoRestartTimer) {
        return {
            ok: false,
            error: 'DEBUG cannot be changed until the current backend startup, cache-prime, or recovery transition finishes.'
        };
    }

    if (next === debugEnabled) {
        return {
            ok: true,
            changed: false,
            debug: debugEnabled,
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    }

    // An external llama-server is outside AI Director's lifecycle and cannot
    // be restarted with a different verbosity setting.
    if (serverReady && !serverOwned) {
        return {
            ok: false,
            error: 'The running llama-server is externally owned; AI Director cannot change its DEBUG mode.'
        };
    }

    // Do not race a normal server start/stop transition. The renderer disables
    // the control during these states too; this is the main-process backstop.
    if (serverStartPromise || (serverProcess && !serverReady)) {
        return {
            ok: false,
            error: 'DEBUG cannot be changed while the AI Director server is starting.'
        };
    }

    const wasRunning = Boolean(serverReady && serverOwned);
    const previous = debugEnabled;
    debugChangeInProgress = true;

    try {
        // Change the desired launch mode first. If restart fails, restore the
        // previous mode and make a best effort to bring the server back exactly
        // as it was.
        debugEnabled = next;

        if (wasRunning) {
            const stopped = await stopServer({ internal: true });
            if (!stopped.ok) {
                throw new Error(stopped.error || 'AI Director could not stop its llama-server for DEBUG restart.');
            }

            if (shuttingDown) {
                throw new Error('DaVinci Resolve is shutting down; DEBUG restart was cancelled.');
            }

            serverDesired = true;
            await startServer({ internal: true });
        }

        notifyServerStatus(getServerStatus());
        return {
            ok: true,
            changed: true,
            debug: debugEnabled,
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    } catch (error) {
        debugEnabled = previous;

        // Restore the previous launch mode if the controlled restart failed.
        if (wasRunning && !shuttingDown && !serverReady) {
            try {
                serverDesired = true;
                await startServer({ internal: true });
            } catch (restoreError) {
                console.error('[AI Director] Failed to restore llama-server after DEBUG change error:', restoreError);
            }
        }

        const message = error instanceof Error ? error.message : String(error);
        notifyServerStatus({
            state: serverReady ? 'connected' : 'error',
            ownership: serverReady && serverOwned ? 'owned' : 'none',
            endpoint: LLAMA_BASE_URL,
            desired: serverDesired,
            debug: debugEnabled,
            error: message
        });

        return {
            ok: false,
            error: message,
            debug: debugEnabled,
            server: getServerStatus(),
            backend: getBackendStatus()
        };
    } finally {
        debugChangeInProgress = false;
    }
}

async function checkUpdates() {
    if (profileChangeInProgress) {
        return {
            ok: false,
            error: 'Updates are unavailable while the server profile is changing.'
        };
    }

    if (activeChatRequestId) {
        return {
            ok: false,
            error: 'Updates are unavailable while a response is running.'
        };
    }

    if (updateInProgress) {
        return {
            ok: false,
            error: 'An update is already in progress.'
        };
    }

    if (settingsApplyInProgress || debugChangeInProgress || serverStartPromise || backendStartPromise || backendPrimeInProgress || backendAutoRestartTimer) {
        return {
            ok: false,
            error: 'Updates are unavailable until the current server/backend transition finishes.'
        };
    }

    notifyUpdateStatus({
        state: 'checking',
        result: null,
        error: null
    });

    try {
        const result = await UpdateManager.checkAll();
        notifyUpdateStatus({
            state: 'idle',
            result,
            error: null
        });
        return { ok: true, result };
    } catch (error) {
        notifyUpdateStatus({
            state: 'error',
            result: null,
            error: error instanceof Error ? error.message : String(error)
        });
        return {
            ok: false,
            error: error instanceof Error ? error.message : String(error)
        };
    }
}

async function installUpdate(component) {
    if (profileChangeInProgress) return { ok: false, error: 'Updates are unavailable while the server profile is changing.' };
    if (activeChatRequestId) return { ok: false, error: 'Updates are unavailable while a response is running.' };
    if (updateInProgress) return { ok: false, error: 'An update is already in progress.' };
    if (settingsApplyInProgress || debugChangeInProgress || serverStartPromise || backendStartPromise || backendPrimeInProgress || backendAutoRestartTimer) {
        return { ok: false, error: 'Updates cannot be installed until the current server/backend transition finishes.' };
    }
    if (component !== 'llama' && component !== 'mcp') return { ok: false, error: `Unknown update component: ${component}` };
    if (serverReady && !serverOwned) {
        return { ok: false, error: 'The llama-server is externally owned. Stop that server first, then retry the update.' };
    }

    const checkedComponentStatus = updateStatus?.result?.[component] || null;
    const checkedCandidateIdentity = checkedComponentStatus?.candidateIdentity || null;
    if (!checkedComponentStatus || checkedComponentStatus.updateAvailable !== true || !checkedCandidateIdentity) {
        return { ok: false, error: 'Refresh Updates before installing so the exact release identity is bound to this transaction.' };
    }

    if (component === 'mcp' && !(await resolveAvailableForManagedUpdate())) {
        return { ok: false, error: 'Open DaVinci Resolve to install MCP updates.' };
    }

    updateInProgress = true;
    const restartServer = Boolean(serverReady && serverOwned);
    const preUpdateServerDesired = serverDesired;
    const preUpdateProfileId = selectedServerProfileId;
    const preUpdateBackend = getBackendStatus();
    const preUpdateToolCount = Number.isFinite(preUpdateBackend?.toolCount) ? preUpdateBackend.toolCount : null;

    activeUpdatePromise = (async () => {
        let result = null;
        let activationAttempted = false;

        const scheduleExecutionCachePrimeAfterRecovery = () => {
            setTimeout(() => {
                if (shuttingDown || !serverDesired || updateInProgress) return;
                void ensureExecutionCacheReady().catch((primeError) => {
                    console.error('[AI Director] Deferred execution-cache prime after update recovery failed:', primeError);
                });
            }, 0);
        };

        const restorePreActivationOperation = async () => {
            selectedServerProfileId = preUpdateProfileId;
            if (!restartServer || shuttingDown || serverReady) return;
            serverDesired = true;
            await ensureLlamaServer();
            await startBackendHost();
            notifyServerStatus(getServerStatus());
            scheduleExecutionCachePrimeAfterRecovery();
        };

        try {
            notifyUpdateStatus({ state: 'installing', component, progress: 0, message: `Preparing ${component === 'llama' ? 'llama.cpp' : 'DaVinci Resolve MCP'} update...`, result: null, error: null });

            if (restartServer || backendProcess) await stopServer({ internal: true });

            const onProgress = (progress) => {
                if (String(progress?.phase || '').toLowerCase() === 'swap') activationAttempted = true;
                notifyUpdateStatus({ state: 'installing', component, ...progress, result: null, error: null });
            };
            result = component === 'llama'
                ? await UpdateManager.installLlamaUpdate({ onProgress, expectedCandidate: checkedCandidateIdentity })
                : await UpdateManager.installMcpUpdate({ onProgress, expectedCandidate: checkedCandidateIdentity });

            if (!result.ok) {
                await restorePreActivationOperation();
                {
                    const failureMessage = result.error || 'Update was not installed.';
                    notifyUpdateStatus({ state: 'error', component, message: failureMessage, result, error: failureMessage });
                }
                return result;
            }

            let runtimeHealth = {
                validated: false,
                reason: 'Runtime health validation has not completed.'
            };

            // Every installed runtime update is health-gated immediately, even when
            // AI Director was stopped before the update. A stopped pre-update state
            // is restored after the candidate passes. This prevents a latent broken
            // runtime from being committed merely because the user updated while idle.
            if (result.updated) {
                // MCP is validated on the user's selected profile because it is common
                // to every llama runtime. An Upstream llama.cpp update must instead be
                // booted on the Upstream profile itself; validating it by restarting an
                // untouched Direct profile would be a false positive.
                const healthProfileId = component === 'llama' ? 'upstream' : preUpdateProfileId;
                const temporaryProfileSwitch = healthProfileId !== preUpdateProfileId;

                notifyUpdateStatus({
                    state: 'installing', component, phase: 'health', progress: 97,
                    message: component === 'llama'
                        ? 'Validating updated Upstream: start server -> backend ready -> prime cache...'
                        : 'Validating updated MCP: start server -> backend ready -> prime cache...',
                    result: null, error: null
                });

                try {
                    selectedServerProfileId = healthProfileId;
                    serverDesired = true;
                    const started = await startServer({ internal: true });
                    const backend = started?.backend || getBackendStatus();

                    if (!serverReady || !serverOwned) throw new Error('Updated llama-server did not reach owned/ready state.');
                    if (!backendProcess || !backendReadyInfo || backend?.state !== 'connected') {
                        throw new Error(`Updated VFX backend did not reach connected state (state=${backend?.state || 'unknown'}).`);
                    }
                    if (!backendCachePrimed) throw new Error('Updated VFX backend did not complete the execution-cache health gate.');

                    const expectedToolCount = Number.isFinite(result.expectedBackendToolCount) ? result.expectedBackendToolCount : preUpdateToolCount;
                    if (Number.isFinite(expectedToolCount) && backend.toolCount !== expectedToolCount) {
                        throw new Error(`Updated backend tool inventory mismatch. Expected ${expectedToolCount}, actual ${backend.toolCount}.`);
                    }

                    const localIdentity = await UpdateManager.verifyInstalledUpdate(result);
                    let functionalCanary = null;
                    if (component === 'mcp') {
                        // MCP updates can change Resolve-facing tool contracts, so a live
                        // Resolve canary is mandatory and Resolve closing mid-transaction
                        // must reject the provisional update.
                        functionalCanary = await runReadOnlyResolveUpdateCanary();
                    } else if (await resolveAvailableForManagedUpdate()) {
                        // Upstream llama.cpp updates do not require Resolve to be open, but
                        // when it is available this is a useful end-to-end compatibility gate.
                        functionalCanary = await runReadOnlyResolveUpdateCanary();
                    } else {
                        functionalCanary = {
                            tool: 'davinci-resolve_resolve_control',
                            action: 'get_page',
                            ok: true,
                            skipped: true,
                            required: false,
                            reason: 'resolve-not-running'
                        };
                    }

                    let restoredProfileHealth = null;
                    if (temporaryProfileSwitch && restartServer) {
                        notifyUpdateStatus({
                            state: 'installing', component, phase: 'health', progress: 98,
                            message: `Updated Upstream runtime passed. Restoring ${SERVER_PROFILES[preUpdateProfileId]?.label || preUpdateProfileId} profile and priming it...`,
                            result: null, error: null
                        });

                        await stopServer({ internal: true });
                        selectedServerProfileId = preUpdateProfileId;
                        serverDesired = true;
                        const restoredStart = await startServer({ internal: true });
                        const restoredBackend = restoredStart?.backend || getBackendStatus();

                        if (!serverReady || !serverOwned || !backendProcess || !backendReadyInfo || restoredBackend?.state !== 'connected' || !backendCachePrimed) {
                            throw new Error(`The updated Upstream runtime passed, but AI Director could not restore and prime the previous ${preUpdateProfileId} profile.`);
                        }
                        if (Number.isFinite(preUpdateToolCount) && restoredBackend.toolCount !== preUpdateToolCount) {
                            throw new Error(`Restored ${preUpdateProfileId} profile tool inventory mismatch. Expected ${preUpdateToolCount}, actual ${restoredBackend.toolCount}.`);
                        }
                        restoredProfileHealth = {
                            profile: preUpdateProfileId,
                            backendReady: true,
                            cachePrimed: true,
                            toolCount: restoredBackend.toolCount
                        };
                    }

                    if (!restartServer) {
                        // The candidate has passed a real temporary live health gate.
                        // Restore the exact pre-update stopped state rather than leaving
                        // a server running solely because an update was validated.
                        if (serverProcess || backendProcess || serverReady) {
                            await stopServer({ internal: true });
                        }
                        selectedServerProfileId = preUpdateProfileId;
                        serverDesired = preUpdateServerDesired;
                        restoredProfileHealth = {
                            profile: preUpdateProfileId,
                            restoredStoppedState: true,
                            serverDesired: Boolean(preUpdateServerDesired)
                        };
                    }

                    const finalized = await UpdateManager.finalizeInstalledUpdate(result);
                    runtimeHealth = {
                        validated: true,
                        validatedProfile: healthProfileId,
                        serverReady: true,
                        backendReady: true,
                        cachePrimed: true,
                        toolCount: backend.toolCount,
                        expectedToolCount,
                        localIdentity,
                        functionalCanary,
                        restoredProfileHealth,
                        finalized
                    };
                } catch (healthError) {
                    const healthMessage = healthError instanceof Error ? healthError.message : String(healthError);
                    notifyUpdateStatus({
                        state: 'installing', component, phase: 'rollback', progress: 99,
                        message: `Updated runtime failed the live health gate; restoring ${result.fromVersion || 'the previous version'} and the prior server profile...`,
                        result: null, error: null
                    });

                    try {
                        if (serverProcess || backendProcess || serverReady) await stopServer({ internal: true });
                        selectedServerProfileId = preUpdateProfileId;
                        const rollback = await UpdateManager.rollbackInstalledUpdate(result, { onProgress });

                        if (restartServer) {
                            serverDesired = true;
                            const restoredStart = await startServer({ internal: true });
                            const restoredBackend = restoredStart?.backend || getBackendStatus();
                            if (!serverReady || !serverOwned || !backendProcess || !backendReadyInfo || restoredBackend?.state !== 'connected' || !backendCachePrimed) {
                                throw new Error('Previous AI Director runtime/profile was restored on disk but failed its restart/prime health gate.');
                            }
                            if (Number.isFinite(preUpdateToolCount) && restoredBackend.toolCount !== preUpdateToolCount) {
                                throw new Error(`Restored backend tool inventory mismatch. Expected ${preUpdateToolCount}, actual ${restoredBackend.toolCount}.`);
                            }
                        } else {
                            selectedServerProfileId = preUpdateProfileId;
                            serverDesired = preUpdateServerDesired;
                        }

                        const message = `Update rejected by live runtime health validation and rolled back to ${result.fromVersion || 'the previous version'}: ${healthMessage}`;
                        notifyUpdateStatus({
                            state: 'error', component,
                            result: { ...result, ok: false, rolledBack: true, rollback, runtimeHealth: { validated: false, error: healthMessage } },
                            error: message
                        });
                        return { ok: false, component, updated: false, rolledBack: true, error: message, rollback };
                    } catch (rollbackError) {
                        const rollbackMessage = rollbackError instanceof Error ? rollbackError.message : String(rollbackError);
                        throw new Error(`${healthMessage} Automatic rollback/recovery also failed: ${rollbackMessage}`);
                    }
                } finally {
                    if (!serverReady) selectedServerProfileId = preUpdateProfileId;
                }
            }

            // Remote status is a UI refresh after local commit. A temporary GitHub
            // failure here must never roll back a runtime that has already started,
            // reached backend-ready, primed, and passed local identity verification.
            let refreshed = null;
            let refreshWarning = null;
            try {
                refreshed = await UpdateManager.checkAll();
            } catch (refreshError) {
                refreshWarning = refreshError instanceof Error ? refreshError.message : String(refreshError);
                console.error('[AI Director] Update completed but final remote status refresh failed:', refreshError);
            }

            const resolveRestartRequired = Boolean(result.resolveRestartRequired);
            const restartMessage = resolveRestartRequired
                ? (result.restartMessage || 'Update completed. Restart DaVinci Resolve to finish the update.')
                : (restartServer
                    ? (component === 'llama' && preUpdateProfileId !== 'upstream'
                        ? `Update completed. Updated Upstream runtime initialized and primed; ${SERVER_PROFILES[preUpdateProfileId]?.label || preUpdateProfileId} profile was restored and primed.`
                        : 'Update completed. Updated runtime initialized, VFX backend became ready, and execution-cache priming completed.')
                    : 'Update completed. The candidate runtime passed a temporary live health gate and AI Director was returned to its pre-update stopped state.');

            const finalResult = { ...result, check: refreshed, refreshWarning, runtimeHealth, resolveRestartRequired, restartMessage };
            notifyUpdateStatus({ state: 'done', component, progress: 100, message: restartMessage, result: finalResult, error: null });
            return finalResult;
        } catch (error) {
            selectedServerProfileId = preUpdateProfileId;
            if (restartServer && !shuttingDown && !serverReady) {
                try {
                    if (activationAttempted) {
                        // Once activation was attempted, keep the full synchronous
                        // restart/backend/cache health gate before releasing the update.
                        serverDesired = true;
                        await startServer({ internal: true });
                    } else {
                        // Pre-activation failures (for example network/download/check
                        // failures) only need minimum operation restored synchronously.
                        // Cache priming resumes after updateInProgress is released.
                        await restorePreActivationOperation();
                    }
                } catch (restartError) {
                    console.error('[AI Director] Failed to restore runtime after update error:', restartError);
                }
            }
            const message = error instanceof Error ? error.message : String(error);
            notifyUpdateStatus({ state: 'error', component, message, result: result ? { ...result, ok: false } : null, error: message });
            return { ok: false, error: message };
        } finally {
            updateInProgress = false;
            activeUpdatePromise = null;
        }
    })();

    return activeUpdatePromise;
}

function getBackendStatus() {
    if (backendProcess && backendReadyInfo && backendPrimeInProgress) {
        return {
            state: 'priming',
            model: backendReadyInfo.model || null,
            endpoint: backendReadyInfo.endpoint || null,
            toolCount: Number.isFinite(backendReadyInfo.tool_count)
                ? backendReadyInfo.tool_count
                : 0
        };
    }

    if (backendProcess && backendReadyInfo && !backendCachePrimed) {
        return {
            state: 'cache_cold',
            model: backendReadyInfo.model || null,
            endpoint: backendReadyInfo.endpoint || null,
            toolCount: Number.isFinite(backendReadyInfo.tool_count)
                ? backendReadyInfo.tool_count
                : 0,
            error: backendPrimeError
        };
    }

    if (backendProcess && backendReadyInfo) {
        return {
            state: 'connected',
            model: backendReadyInfo.model || null,
            endpoint: backendReadyInfo.endpoint || null,
            toolCount: Number.isFinite(backendReadyInfo.tool_count)
                ? backendReadyInfo.tool_count
                : 0
        };
    }

    if (backendProcess || backendStartPromise) {
        return { state: 'starting' };
    }

    return { state: 'offline' };
}

async function stopActiveChat({ restart = true, reason = 'stopped' } = {}) {
    if (!activeChatRequestId) {
        return { ok: true, stopped: false };
    }

    const requestId = activeChatRequestId;
    const pending = pendingBackendRequests.get(requestId);
    const status = reason === 'replaced' ? 'replaced' : 'stopped';
    finalizePendingSessionTurn(pending, status);

    activeChatRequestId = null;
    syncStandaloneResolveObserverPauseState();
    await stopBackendHost({
        restart,
        // User Stop / replace restarts only the Python host. The owned
        // llama-server process remains alive, so its validated execution
        // prefix cache remains valid and must not be marked cold.
        preserveExecutionCache: restart
    });

    return {
        ok: true,
        stopped: true
    };
}

ipcMain.handle('aid:getBridgeStatus', async () => {
    try {
        return await getBridgeStatus();
    } catch (error) {
        return {
            connected: false,
            error: error instanceof Error ? error.message : String(error)
        };
    }
});

ipcMain.handle('aid:getBackendStatus', async () => ({
    ...getBackendStatus(),
    runtimeBusy: settingsRuntimeTransitionActive(),
    settingsApplyBlocked: settingsApplyRuntimeTransitionActive()
}));
ipcMain.handle('aid:getContextStatus', async () => ({ ...latestContextStatus }));
ipcMain.handle('aid:getServerStatus', async () => ({
    ...getServerStatus(),
    runtimeBusy: settingsRuntimeTransitionActive(),
    settingsApplyBlocked: settingsApplyRuntimeTransitionActive()
}));
ipcMain.handle('aid:getSettingsState', async () => {
    // Reuse an already-running initial/explicit model scan, but never start a
    // fresh scan just because the Settings cog was clicked.
    if (modelCatalogRefreshPromise) {
        await modelCatalogRefreshPromise;
    }
    return getSettingsState();
});
ipcMain.handle('aid:rescanModels', async () => {
    await refreshModelCatalog();
    reconcilePersistentModelSelection({ persist: Boolean(persistentSettings.setupCompleted) });
    return getSettingsState();
});
ipcMain.handle('aid:applySettings', async (_event, candidate) => applyPersistentSettings(candidate || {}));
ipcMain.handle('aid:locateExternalFfmpeg', async () => locateExternalFfmpeg());
ipcMain.handle('aid:openRecommendedFfmpeg', async () => openRecommendedFfmpegPage());
ipcMain.handle('aid:setAppearanceSkin', async (_event, skin) => setAppearanceSkin(skin));
ipcMain.handle('aid:getServerProfile', async () => getServerStatus());
ipcMain.handle('aid:setServerProfile', async (_event, profileId) => setServerProfile(profileId));
ipcMain.handle('aid:setDebugMode', async (_event, enabled) => setDebugMode(enabled));
ipcMain.handle('aid:getUpdateStatus', async () => updateStatus);
ipcMain.handle('aid:checkUpdates', async () => checkUpdates());
ipcMain.handle('aid:installUpdate', async (_event, component) => installUpdate(component));

ipcMain.handle('aid:startServer', async () => {
    try {
        return await startServer();
    } catch (error) {
        return {
            ok: false,
            error: error instanceof Error ? error.message : String(error)
        };
    }
});

ipcMain.handle('aid:stopServer', async () => {
    try {
        return await stopServer();
    } catch (error) {
        return {
            ok: false,
            error: error instanceof Error ? error.message : String(error)
        };
    }
});

ipcMain.handle('aid:chat', async (_event, message, clientRequestId = null) => {
    try {
        return await sendBackendRequest(
            'chat',
            { message },
            { clientRequestId: String(clientRequestId || '') || null }
        );
    } catch (error) {
        const stopped = error?.message === 'VFX request stopped by user.';

        if (stopped) {
            return {
                ok: true,
                stopped: true
            };
        }

        return {
            ok: false,
            stopped: false,
            error: error instanceof Error ? error.message : String(error)
        };
    }
});

ipcMain.handle('aid:stopChat', async (_event, options = {}) => {
    try {
        const restart = options?.restart !== false;
        const reason = options?.reason === 'replaced' ? 'replaced' : 'stopped';
        return await stopActiveChat({ restart, reason });
    } catch (error) {
        return {
            ok: false,
            error: error instanceof Error ? error.message : String(error)
        };
    }
});

ipcMain.handle('aid:clearSession', async (_event, options = {}) => (
    resetAIDirectorSession({ keepActive: Boolean(options?.keepActive) })
));

ipcMain.handle('aid:showChatContextMenu', (event, markdown, options = {}) => {
    const window = BrowserWindow.fromWebContents(event.sender);

    if (!window) return;

    const hasSelection = Boolean(options?.hasSelection);
    const processing = Boolean(options?.processing);
    const telemetryMarkdown = typeof options?.telemetryMarkdown === 'string'
        ? options.telemetryMarkdown
        : '';
    const menu = Menu.buildFromTemplate([
        {
            label: 'Copy Discussion (Markdown)',
            enabled: typeof markdown === 'string' && markdown.length > 0,
            click: () => {
                clipboard.writeText(typeof markdown === 'string' ? markdown : '');
            }
        },
        {
            label: 'Copy Details (Markdown)',
            visible: telemetryMarkdown.length > 0,
            enabled: telemetryMarkdown.length > 0,
            click: () => {
                clipboard.writeText(telemetryMarkdown);
            }
        },
        {
            label: 'Copy Selected Text',
            enabled: hasSelection,
            role: 'copy'
        },
        {
            type: 'separator'
        },
        {
            label: processing ? 'Clear Chat (Keep Active)' : 'Clear Chat',
            enabled: Boolean(options?.canClear),
            click: () => {
                event.sender.send('aid:clearChat');
            }
        },
        {
            type: 'separator'
        },
        {
            label: 'Select All',
            role: 'selectAll'
        }
    ]);

    menu.popup({ window });
});

ipcMain.handle('aid:showInputContextMenu', (event) => {
    const window = BrowserWindow.fromWebContents(event.sender);

    if (!window) return;

    const menu = Menu.buildFromTemplate([
        { label: 'Undo', role: 'undo' },
        { label: 'Redo', role: 'redo' },
        { type: 'separator' },
        { label: 'Cut', role: 'cut' },
        { label: 'Copy', role: 'copy' },
        { label: 'Paste', role: 'paste' },
        { type: 'separator' },
        { label: 'Select All', role: 'selectAll' }
    ]);

    menu.popup({ window });
});

async function cleanupResolveInterface() {
    if (cleanupStarted) return;
    cleanupStarted = true;
    // A provisional update owns the commit/rollback boundary. Shutdown is deferred
    // until its live health gate either finalizes or rolls back; there is no file-only
    // success path that can bypass runtime acceptance.
    serverDesired = false;

    if (activeUpdatePromise) {
        try {
            await activeUpdatePromise;
        } catch (error) {
            console.error('[AI Director] Update cleanup wait failed:', error);
        }
    }

    shuttingDown = true;
    serverDesired = false;

    try {
        await stopStandaloneResolveObserver();
    } catch (error) {
        console.error('[AI Director] Resolve observer cleanup failed:', error);
    }

    try {
        await stopBackendHost({ restart: false });
    } catch (error) {
        console.error('[AI Director] Backend cleanup failed:', error);
    }

    if (serverProcess && serverOwned) {
        try {
            await stopChildProcessTree(serverProcess, 10000);
        } catch (error) {
            console.error('[AI Director] Server cleanup failed:', error);
        }
    }

    serverProcess = null;
    serverOwned = false;
    serverReady = false;

    if (!initialized) return;

    try {
        WorkflowIntegration.CleanUp();
    } catch (error) {
        console.error('WorkflowIntegration cleanup failed:', error);
    }

    initialized = false;
    resolveObj = null;
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 760,
        height: 820,
        minWidth: 560,
        minHeight: 600,
        backgroundColor: '#171717',
        title: 'AI Director',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js')
        }
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    mainWindow.loadFile(path.join(__dirname, 'index.html'));
}

app.whenReady().then(async () => {
    if (!standaloneInstanceLock) return;

    await refreshModelCatalog();
    // Persisted completed settings may reference a discovered local model.
    // Load them only after the LM Studio catalog is available.
    loadPersistentSettings();
    createWindow();

    await refreshConfiguredFfmpegStatus();

    try {
        await Promise.resolve(modelCatalog);
        reconcilePersistentModelSelection({ persist: Boolean(persistentSettings.setupCompleted) });
    } catch (error) {
        appendSettingsWarning(`LM Studio model discovery failed: ${error?.message || String(error)}`);
        persistentSettings.setupCompleted = false;
    }

    serverDesired = Boolean(persistentSettings.setupCompleted);

    // First run, missing-model recovery, and rejected-model migration start
    // nothing until the user confirms a detected server/model combination.
    if (!persistentSettings.setupCompleted) {
        notifyServerStatus(getServerStatus());
        return;
    }

    // Do not make Electron startup wait for model loading. The plugin window
    // is already visible while the selected llama-server initializes.
    startServer().catch((error) => {
        if (!serverDesired || profileChangeInProgress || shuttingDown) {
            return;
        }
        console.error('[AI Director] Automatic server startup failed:', error);
        notifyServerStatus({
            state: 'error',
            ownership: 'none',
            endpoint: LLAMA_BASE_URL,
            desired: serverDesired,
            error: error instanceof Error ? error.message : String(error)
        });
    });
});

app.on('before-quit', (event) => {
    if (cleanupStarted) return;

    event.preventDefault();

    cleanupResolveInterface().finally(() => {
        app.quit();
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
