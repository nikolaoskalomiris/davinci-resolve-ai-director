const prompt = document.getElementById('prompt');
const send = document.getElementById('send');
const conversation = document.getElementById('conversation');
const jumpToLatest = document.getElementById('jumpToLatest');
const composer = document.getElementById('composer');
const composerResizeHandle = document.getElementById('composerResizeHandle');
const profileSelect = document.getElementById('profileSelect');
const serverToggle = document.getElementById('serverToggle');
const serverStatus = document.getElementById('serverStatus');
const debugToggle = document.getElementById('debugToggle');
const debugStatus = document.getElementById('debugStatus');
const updatesButton = document.getElementById('updatesButton');
const updateIndicator = document.getElementById('updateIndicator');
const updateDialog = document.getElementById('updateDialog');
const closeUpdates = document.getElementById('closeUpdates');
const checkUpdatesButton = document.getElementById('checkUpdates');
const updateDialogStatus = document.getElementById('updateDialogStatus');
const llamaUpdateState = document.getElementById('llamaUpdateState');
const llamaInstalled = document.getElementById('llamaInstalled');
const llamaLatest = document.getElementById('llamaLatest');
const llamaBundle = document.getElementById('llamaBundle');
const llamaUpdateReason = document.getElementById('llamaUpdateReason');
const installLlama = document.getElementById('installLlama');
const mcpUpdateState = document.getElementById('mcpUpdateState');
const mcpInstalled = document.getElementById('mcpInstalled');
const mcpLatest = document.getElementById('mcpLatest');
const mcpCheckout = document.getElementById('mcpCheckout');
const mcpUpdateReason = document.getElementById('mcpUpdateReason');
const installMcp = document.getElementById('installMcp');

const settingsButton = document.getElementById('settingsButton');
const settingsDialog = document.getElementById('settingsDialog');
const settingsDialogTitle = document.getElementById('settingsDialogTitle');
const settingsDialogSubtitle = document.getElementById('settingsDialogSubtitle');
const closeSettings = document.getElementById('closeSettings');
const cancelSettings = document.getElementById('cancelSettings');
const applySettingsButton = document.getElementById('applySettings');
const settingsLoadWarning = document.getElementById('settingsLoadWarning');
const settingsProfileUpstream = document.getElementById('settingsProfileUpstream');
const settingsProfileDirect = document.getElementById('settingsProfileDirect');
const settingsProfileUpstreamAvailability = document.getElementById('settingsProfileUpstreamAvailability');
const settingsProfileDirectAvailability = document.getElementById('settingsProfileDirectAvailability');
const settingsModelSelect = document.getElementById('settingsModelSelect');
const settingsModelRefresh = document.getElementById('settingsModelRefresh');
const settingsModelDetails = document.getElementById('settingsModelDetails');
const settingsModelDiscovery = document.getElementById('settingsModelDiscovery');
const settingsContextLength = document.getElementById('settingsContextLength');
const settingsMaxOutput = document.getElementById('settingsMaxOutput');
const MIN_SUPPORTED_CONTEXT_LENGTH = 131072;
const MAX_SUPPORTED_OUTPUT_TOKENS = 32768;
const settingsTimeoutHours = document.getElementById('settingsTimeoutHours');
const settingsContextOverflowPolicy = document.getElementById('settingsContextOverflowPolicy');
const settingsFfmpegSummary = document.getElementById('settingsFfmpegSummary');
const settingsFfmpegPath = document.getElementById('settingsFfmpegPath');
const settingsFfmpegHelp = document.getElementById('settingsFfmpegHelp');
const settingsFfmpegGet = document.getElementById('settingsFfmpegGet');
const settingsFfmpegLocate = document.getElementById('settingsFfmpegLocate');
const settingsFfmpegDisable = document.getElementById('settingsFfmpegDisable');
const settingsPrimeCache = document.getElementById('settingsPrimeCache');
const settingsGpuLayers = document.getElementById('settingsGpuLayers');
const settingsCpuMoeLayers = document.getElementById('settingsCpuMoeLayers');
const settingsKvCacheType = document.getElementById('settingsKvCacheType');
const settingsKvCacheDefault = document.getElementById('settingsKvCacheDefault');
const settingsFlashAttention = document.getElementById('settingsFlashAttention');
const settingsFlashAttentionDefault = document.getElementById('settingsFlashAttentionDefault');
const settingsFlashAttentionHelp = document.getElementById('settingsFlashAttentionHelp');
const settingsThreads = document.getElementById('settingsThreads');
const settingsBatchThreads = document.getElementById('settingsBatchThreads');
const settingsBatchSize = document.getElementById('settingsBatchSize');
const settingsMicroBatchSize = document.getElementById('settingsMicroBatchSize');
const settingsResetTuning = document.getElementById('settingsResetTuning');
let settingsTemperature = null;
let settingsTemperatureDefault = null;
let settingsTopP = null;
let settingsTopPDefault = null;
let settingsTopK = null;
let settingsTopKDefault = null;
let settingsMinP = null;
let settingsMinPDefault = null;
let settingsPresencePenalty = null;
let settingsPresencePenaltyDefault = null;
let settingsRepetitionPenalty = null;
let settingsRepetitionPenaltyDefault = null;
let settingsPromptCacheReuse = null;
let settingsResetInference = null;
const advancedRangeBindings = [];
let advancedRuntimeUiReady = false;
const settingsImpact = document.getElementById('settingsImpact');
const settingsOperationStatus = document.getElementById('settingsOperationStatus');
const settingsSkinOptions = [...document.querySelectorAll('.settings-skin-option')];
const settingsAppearanceStatus = document.getElementById('settingsAppearanceStatus');

const resolveStatus = document.getElementById('resolveStatus');
const resolveDot = document.getElementById('resolveDot');

const backendStatus = document.getElementById('backendStatus');
const backendDot = document.getElementById('backendDot');

const currentPage = document.getElementById('currentPage');
const currentProject = document.getElementById('currentProject');
const modelStatus = document.getElementById('modelStatus');
const contextMeter = document.getElementById('contextMeter');
const contextMeterCircle = document.getElementById('contextMeterCircle');
const contextMeterProgress = document.getElementById('contextMeterProgress');
const contextMeterText = document.getElementById('contextMeterText');

let resolvePollInFlight = false;
let backendPollInFlight = false;
let isProcessing = false;
let backendReadyForChat = false;
let serverActionInFlight = false;
let debugActionInFlight = false;
let profileActionInFlight = false;
let settingsActionInFlight = false;
let skinActionInFlight = false;
let settingsState = null;
let settingsDraftFfmpeg = { mode: 'disabled', ffmpegPath: null, ffprobePath: null };
let settingsDraftFfmpegStatus = null;
let ffmpegActionInFlight = false;
let settingsDraftProfile = null;
let settingsDraftModel = null;
let settingsFirstRun = false;
let settingsRuntimeBusy = false;
let settingsApplyBlocked = false;
let settingsDraftSkin = 'green';
let profileSwitchAllowed = false;
const SETTINGS_RUNTIME_WAIT_MESSAGE = 'Runtime transition in progress. Apply is available when ready.';
let runToken = 0;
let activeResponse = null;
let updateBusy = false;
let latestUpdateResult = null;
let resolveReadyForMcpUpdate = false;
const MCP_UPDATE_RESOLVE_REQUIRED_MESSAGE = 'Open DaVinci Resolve to install MCP updates.';
const MCP_UPDATE_RESOLVE_REQUIRED_CARD_MESSAGE = 'Requires DaVinci Resolve.';
let contextMeterExpanded = false;
let contextMeterStatus = null;
const conversationHistory = [];
const telemetryPanelStates = new WeakMap();

const COMPOSER_MIN_HEIGHT = 86;
const COMPOSER_DEFAULT_HEIGHT = 108;
const COMPOSER_BOTTOM_RESERVED = 8;
const CONVERSATION_FOLLOW_THRESHOLD = 96;
let preferredComposerHeight = COMPOSER_DEFAULT_HEIGHT;
let renderedComposerHeight = COMPOSER_DEFAULT_HEIGHT;
let composerResizeSettleTimer = null;
let conversationFollowsLatest = true;
let composerResizeState = null;

function getComposerMaxHeight() {
    const info = document.querySelector('.info');
    const reservedTop = info
        ? info.getBoundingClientRect().bottom
        : 0;
    return Math.max(
        COMPOSER_MIN_HEIGHT,
        window.innerHeight - reservedTop - COMPOSER_BOTTOM_RESERVED
    );
}

function applyPreferredComposerHeight() {
    const maxHeight = getComposerMaxHeight();
    const nextRenderedHeight = Math.min(
        Math.max(preferredComposerHeight, COMPOSER_MIN_HEIGHT),
        maxHeight
    );

    renderedComposerHeight = nextRenderedHeight;
    composer.style.height = `${renderedComposerHeight}px`;
    document.documentElement.style.setProperty('--composer-height', `${renderedComposerHeight}px`);
}

function setPreferredComposerHeight(height) {
    const maxHeight = getComposerMaxHeight();
    preferredComposerHeight = Math.min(
        Math.max(Number(height) || COMPOSER_DEFAULT_HEIGHT, COMPOSER_MIN_HEIGHT),
        maxHeight
    );
    applyPreferredComposerHeight();
}

function scheduleComposerLayoutAfterWindowResize() {
    if (composerResizeSettleTimer !== null) {
        window.clearTimeout(composerResizeSettleTimer);
    }
    composerResizeSettleTimer = window.setTimeout(() => {
        composerResizeSettleTimer = null;
        applyPreferredComposerHeight();
    }, 180);
}

function isConversationNearBottom() {
    const remaining = conversation.scrollHeight - conversation.scrollTop - conversation.clientHeight;
    return remaining <= CONVERSATION_FOLLOW_THRESHOLD;
}

function syncConversationFollowUi() {
    if (isConversationNearBottom()) {
        conversationFollowsLatest = true;
    }
    jumpToLatest.hidden = conversationFollowsLatest;
}

function scrollConversationToLatest({ force = false } = {}) {
    if (!force && !conversationFollowsLatest) {
        syncConversationFollowUi();
        return;
    }

    conversationFollowsLatest = true;
    conversation.scrollTop = conversation.scrollHeight;
    syncConversationFollowUi();
}

function handleConversationScroll() {
    conversationFollowsLatest = isConversationNearBottom();
    syncConversationFollowUi();
}

conversation.addEventListener('scroll', handleConversationScroll, { passive: true });

jumpToLatest.addEventListener('click', () => {
    scrollConversationToLatest({ force: true });
    conversation.focus({ preventScroll: true });
});

function beginComposerResize(event) {
    if (event.button !== 0) return;
    if (updateBusy) return;

    event.preventDefault();
    composerResizeState = {
        pointerId: event.pointerId,
        startY: event.clientY,
        startHeight: composer.getBoundingClientRect().height,
    };
    composerResizeHandle.setPointerCapture(event.pointerId);
    composerResizeHandle.classList.add('active');
    document.body.classList.add('resizing-composer');
}

function updateComposerResize(event) {
    if (!composerResizeState || event.pointerId !== composerResizeState.pointerId) return;

    const delta = composerResizeState.startY - event.clientY;
    setPreferredComposerHeight(composerResizeState.startHeight + delta);
}

function endComposerResize(event) {
    if (!composerResizeState || event.pointerId !== composerResizeState.pointerId) return;

    try {
        if (composerResizeHandle.hasPointerCapture(event.pointerId)) {
            composerResizeHandle.releasePointerCapture(event.pointerId);
        }
    } catch (_) {
        // Pointer may already have been released/cancelled.
    }

    composerResizeState = null;
    composerResizeHandle.classList.remove('active');
    document.body.classList.remove('resizing-composer');
}

composerResizeHandle.addEventListener('pointerdown', beginComposerResize);
composerResizeHandle.addEventListener('pointermove', updateComposerResize);
composerResizeHandle.addEventListener('pointerup', endComposerResize);
composerResizeHandle.addEventListener('pointercancel', endComposerResize);

window.addEventListener('resize', scheduleComposerLayoutAfterWindowResize, { passive: true });

applyPreferredComposerHeight();

function setState(element, dot, text, state) {
    element.textContent = text;

    element.classList.remove(
        'connected',
        'starting',
        'stopping',
        'offline',
        'error',
        'external'
    );

    if (state) element.classList.add(state);

    if (dot) {
        dot.classList.remove(
            'connected',
            'starting',
            'stopping',
            'offline',
            'error',
            'external'
        );

        if (state) dot.classList.add(state);
    }
}

function setStatusTooltip(element, dot, text = '') {
    const tooltip = String(text || '').trim();
    if (tooltip) {
        element.title = tooltip;
        if (dot) dot.title = tooltip;
        return;
    }
    element.removeAttribute('title');
    if (dot) dot.removeAttribute('title');
}

function applyResolveStatus(status) {
    resolveReadyForMcpUpdate = Boolean(
        status?.hostMode === 'standalone'
            ? status?.resolveRunning === true
            : status?.connected === true
    );

    if (status?.hostMode === 'standalone') {
        if (status.resolveRunning === true) {
            setState(
                resolveStatus,
                resolveDot,
                'Resolve connected',
                'connected'
            );
            setStatusTooltip(
                resolveStatus,
                resolveDot,
                status?.telemetryError
                    ? `Resolve is running. Windows UI status is temporarily unavailable: ${status.telemetryError}`
                    : 'Standalone mode: DaVinci Resolve is running.'
            );
        } else {
            setState(
                resolveStatus,
                resolveDot,
                'Resolve disconnected',
                'external'
            );
            setStatusTooltip(
                resolveStatus,
                resolveDot,
                status?.error || 'Standalone mode: DaVinci Resolve is not running. Offline/Advanced capabilities remain available.'
            );
        }

        currentPage.textContent = status.currentPage || '-';
        currentProject.textContent = status.currentProject || '-';
        refreshMcpUpdateAvailability();
        return;
    }

    if (!status || !status.connected) {
        setState(
            resolveStatus,
            resolveDot,
            'Resolve bridge failed',
            'error'
        );
        setStatusTooltip(resolveStatus, resolveDot, status?.error || 'Resolve Workflow Integration is unavailable.');

        currentPage.textContent = '-';
        currentProject.textContent = '-';
        refreshMcpUpdateAvailability();
        return;
    }

    setState(
        resolveStatus,
        resolveDot,
        'Resolve connected',
        'connected'
    );
    setStatusTooltip(resolveStatus, resolveDot, '');

    currentPage.textContent = status.currentPage || '-';
    currentProject.textContent = status.currentProject || '-';
    refreshMcpUpdateAvailability();
}

function syncComposerAvailability() {
    if (isProcessing) {
        send.disabled = false;
        return;
    }
    send.disabled = updateBusy || settingsActionInFlight || !backendReadyForChat || Boolean(settingsState?.setupRequired);
}

function applyRuntimeBusyState(status) {
    if (typeof status?.runtimeBusy === 'boolean') {
        settingsRuntimeBusy = Boolean(status.runtimeBusy);
    }
    if (typeof status?.settingsApplyBlocked === 'boolean') {
        settingsApplyBlocked = Boolean(status.settingsApplyBlocked);
    } else if (typeof status?.runtimeBusy === 'boolean') {
        // Backward-compatible fallback for a mixed renderer/main-process launch.
        settingsApplyBlocked = settingsRuntimeBusy;
    }
    updatesButton.disabled = isProcessing || updateBusy || settingsRuntimeBusy;
    if (settingsDialog.open) {
        updateSettingsRuntimeGate(settingsRuntimeBusy, settingsApplyBlocked);
    }
}

function applyBackendStatus(status) {
    applyRuntimeBusyState(status);
    backendReadyForChat = Boolean(status && status.state === 'connected');

    if (!status) {
        setState(backendStatus, backendDot, 'Offline', 'offline');
        setStatusTooltip(backendStatus, backendDot);
        syncComposerAvailability();
        return;
    }

    if (status.state === 'connected') {
        const count = Number.isFinite(status.toolCount)
            ? status.toolCount
            : 0;

        setState(
            backendStatus,
            backendDot,
            count
                ? `Connected • ${count} Resolve tools`
                : 'Connected',
            'connected'
        );
        setStatusTooltip(backendStatus, backendDot);

        if (status.model) modelStatus.textContent = status.model;
        syncComposerAvailability();
        return;
    }

    if (status.state === 'priming') {
        setState(
            backendStatus,
            backendDot,
            'Priming execution cache...',
            'starting'
        );
        setStatusTooltip(backendStatus, backendDot);
        if (status.model) modelStatus.textContent = status.model;
        syncComposerAvailability();
        return;
    }

    if (status.state === 'cache_cold') {
        const primeError = String(status.error || '').trim();
        setState(
            backendStatus,
            backendDot,
            primeError ? 'Prime failed' : 'Execution not primed',
            primeError ? 'error' : 'starting'
        );
        setStatusTooltip(backendStatus, backendDot, primeError);
        if (status.model) modelStatus.textContent = status.model;
        syncComposerAvailability();
        return;
    }

    if (status.state === 'starting') {
        setState(backendStatus, backendDot, 'Starting...', 'starting');
        setStatusTooltip(backendStatus, backendDot);
        syncComposerAvailability();
        return;
    }

    if (status.state === 'stopping') {
        setState(backendStatus, backendDot, 'Stopping...', 'stopping');
        setStatusTooltip(backendStatus, backendDot);
        syncComposerAvailability();
        return;
    }

    if (status.state === 'error') {
        const backendError = String(status.error || '').trim();
        setState(backendStatus, backendDot, 'Backend error', 'error');
        setStatusTooltip(backendStatus, backendDot, backendError);
        syncComposerAvailability();
        return;
    }

    setState(backendStatus, backendDot, 'Offline', 'offline');
    setStatusTooltip(backendStatus, backendDot);
    syncComposerAvailability();
}

function applyProfileStatus(status, { external = false, transitional = false } = {}) {
    if (typeof status?.profileSwitchAllowed === 'boolean') {
        profileSwitchAllowed = Boolean(status.profileSwitchAllowed);
    }

    if (status?.setupRequired) {
        profileSwitchAllowed = false;
        profileSelect.value = '';
        profileSelect.disabled = true;
        profileSelect.title = 'Complete first-run setup to choose a server profile.';
        return;
    }
    const profile = status?.profile === 'direct'
        ? 'direct'
        : (status?.profile === 'upstream' ? 'upstream' : (profileSelect.value || 'upstream'));
    profileSelect.value = profile;

    if (external) {
        profileSwitchAllowed = false;
        profileSelect.disabled = true;
        profileSelect.title = 'An external llama-server is running; AI Director cannot switch its server profile.';
        return;
    }

    if (transitional || !profileSwitchAllowed) {
        profileSelect.disabled = true;
        profileSelect.title = 'Server profile unavailable until the current non-supersedable lifecycle transition finishes.';
        return;
    }

    profileSelect.disabled = updateBusy || settingsActionInFlight || isProcessing || serverActionInFlight || debugActionInFlight || profileActionInFlight;
    profileSelect.title = settingsRuntimeBusy
        ? 'Switch profile now; active cache priming will be cancelled and replaced safely.'
        : (profile === 'direct'
            ? 'Direct - custom AI Director llama.cpp runtime'
            : 'Upstream - updater-managed llama.cpp runtime');
}

function applyDebugStatus(status, { external = false, transitional = false } = {}) {
    const enabled = Boolean(status?.debug);
    debugToggle.setAttribute('aria-pressed', String(enabled));
    debugStatus.textContent = enabled ? 'On' : 'Off';
    debugStatus.classList.remove('connected', 'starting', 'stopping', 'offline', 'error', 'external');

    if (external) {
        debugToggle.disabled = true;
        debugToggle.title = 'An external llama-server is running; AI Director cannot change its DEBUG mode.';
        debugStatus.textContent = enabled ? 'On' : 'Off';
        return;
    }

    if (transitional || settingsRuntimeBusy) {
        debugToggle.disabled = true;
        debugToggle.title = 'DEBUG unavailable until the current server/backend transition finishes.';
        return;
    }

    debugToggle.disabled = updateBusy || settingsActionInFlight || isProcessing || serverActionInFlight || debugActionInFlight || profileActionInFlight;
    debugToggle.title = enabled
        ? 'Restart the AI Director llama-server without diagnostic verbosity'
        : 'Restart the AI Director llama-server with diagnostic verbosity (-lv 4)';
}

function applyServerStatus(status) {
    applyRuntimeBusyState(status);
    if (status?.modelAlias) modelStatus.textContent = status.modelAlias;
    const state = status?.state || 'offline';
    const ownership = status?.ownership || 'none';

    if (status?.setupRequired || state === 'unconfigured') {
        applyProfileStatus({ setupRequired: true });
        debugToggle.disabled = true;
        debugToggle.setAttribute('aria-pressed', 'false');
        debugStatus.textContent = 'Off';
        serverToggle.disabled = true;
        serverToggle.setAttribute('aria-pressed', 'false');
        setState(serverStatus, null, 'Setup', 'offline');
        serverToggle.title = 'Complete first-run setup to start AI Director.';
        return;
    }

    applyProfileStatus(status, {
        external: state === 'connected' && ownership === 'external',
        transitional: state === 'starting' || state === 'stopping'
    });

    if (state === 'connected') {
        if (ownership === 'external') {
            applyDebugStatus(status, { external: true });
            serverToggle.disabled = true;
            serverToggle.setAttribute('aria-pressed', 'true');
            setState(serverStatus, null, 'External', 'external');
            serverToggle.title = 'An external llama-server is running; AI Director will not terminate it.';
            return;
        }

        applyDebugStatus(status);
        serverToggle.disabled = updateBusy || settingsActionInFlight || isProcessing || serverActionInFlight || profileActionInFlight;
        debugToggle.disabled = updateBusy || settingsActionInFlight || isProcessing || serverActionInFlight || debugActionInFlight || profileActionInFlight;
        serverToggle.setAttribute('aria-pressed', 'true');
        setState(serverStatus, null, 'On', 'connected');
        serverToggle.title = 'Stop the AI Director llama-server';
        return;
    }

    if (state === 'starting') {
        applyDebugStatus(status, { transitional: true });
        serverToggle.disabled = true;
        serverToggle.setAttribute('aria-pressed', 'false');
        setState(serverStatus, null, 'Starting...', 'starting');
        return;
    }

    if (state === 'error') {
        applyDebugStatus(status);
        serverToggle.disabled = isProcessing || updateBusy || serverActionInFlight || profileActionInFlight;
        serverToggle.setAttribute('aria-pressed', 'false');
        setState(serverStatus, null, 'Error', 'error');
        serverToggle.title = status.error || 'Start AI Director server';
        return;
    }

    applyDebugStatus(status);
    serverToggle.disabled = isProcessing || updateBusy || serverActionInFlight || profileActionInFlight;
    serverToggle.setAttribute('aria-pressed', 'false');
    setState(serverStatus, null, 'Off', 'offline');
    serverToggle.title = 'Start the AI Director llama-server';
}

function getProfileState(id) {
    return settingsState?.profiles?.find((profile) => profile.id === id) || null;
}

function getModelState(id) {
    return settingsState?.models?.find((model) => model.id === id) || null;
}

function normalizeSkin(value) {
    const skin = String(value || 'green').toLowerCase();
    return ['green', 'blue', 'purple', 'gray'].includes(skin) ? skin : 'green';
}

function applySkin(value) {
    const skin = normalizeSkin(value);
    document.documentElement.dataset.skin = skin;
    return skin;
}

function persistedSkin() {
    return normalizeSkin(settingsState?.settings?.appearance?.skin || settingsState?.defaults?.appearance?.skin || 'green');
}

function syncSkinPicker() {
    const active = normalizeSkin(settingsDraftSkin);
    settingsSkinOptions.forEach((button) => {
        const selected = button.dataset.skin === active;
        button.classList.toggle('selected', selected);
        button.setAttribute('aria-checked', String(selected));
        button.disabled = skinActionInFlight;
    });
}

async function setSettingsSkin(value) {
    if (skinActionInFlight) return;

    const previousSkin = persistedSkin();
    const requestedSkin = applySkin(value);
    settingsDraftSkin = requestedSkin;
    skinActionInFlight = true;
    syncSkinPicker();
    if (settingsAppearanceStatus) settingsAppearanceStatus.textContent = 'Saving appearance…';

    try {
        const response = await window.aiDirector.setAppearanceSkin(requestedSkin);
        if (!response?.ok) {
            throw new Error(response?.error || 'Could not save the selected skin.');
        }
        settingsDraftSkin = normalizeSkin(response.appearance?.skin || requestedSkin);
        if (settingsState?.settings) {
            settingsState.settings.appearance = { skin: settingsDraftSkin };
        }
        applySkin(settingsDraftSkin);
        if (settingsAppearanceStatus) settingsAppearanceStatus.textContent = 'Changes apply immediately.';
        updateSettingsImpact();
    } catch (error) {
        settingsDraftSkin = applySkin(previousSkin);
        if (settingsAppearanceStatus) {
            settingsAppearanceStatus.textContent = error?.message || String(error);
        }
    } finally {
        skinActionInFlight = false;
        syncSkinPicker();
        updateSettingsApplyState();
    }
}

function setSettingsProfile(profileId) {
    const profile = getProfileState(profileId);
    if (!profile?.available || settingsActionInFlight) return;
    settingsDraftProfile = profileId;
    [settingsProfileUpstream, settingsProfileDirect].forEach((button) => {
        const selected = button.dataset.profile === profileId;
        button.classList.toggle('selected', selected);
        button.setAttribute('aria-checked', String(selected));
    });
    updateSettingsImpact();
}

function updateSettingsModelDetails() {
    const model = getModelState(settingsDraftModel);
    if (!model) {
        settingsModelDetails.textContent = 'No selectable GGUF model is currently detected.';
        return;
    }

    const parts = [];
    if (model.quantization) parts.push(model.quantization);
    if (model.architecture) parts.push(model.architecture);
    if (Number(model.metadataMaxContextLength) > 0) {
        parts.push(`Max context: ${Number(model.metadataMaxContextLength).toLocaleString()}`);
    }
    if (model.publisher) parts.push(`Publisher: ${model.publisher}`);
    if (model.trainedForToolUse === true) parts.push('Tool use: yes');
    else if (model.trainedForToolUse === false) parts.push('Tool use: no');
    if (model.metadataReasoning?.supported === true) {
        const suffix = model.metadataReasoning.default ? ` (${model.metadataReasoning.default})` : '';
        parts.push(`Reasoning: available${suffix}`);
    } else if (model.metadataReasoning?.supported === false) {
        parts.push('Reasoning: no');
    }
    if (!model.available && model.availabilityReason) parts.push(model.availabilityReason);
    settingsModelDetails.textContent = parts.length ? parts.join(' | ') : 'Local GGUF detected by AI Director.';
}

function renderModelOptions(selectedId = settingsDraftModel) {
    settingsModelSelect.replaceChildren();
    const models = Array.isArray(settingsState?.models) ? settingsState.models : [];
    if (!models.length) {
        const option = document.createElement('option');
        option.value = '';
        option.textContent = 'No GGUF models detected';
        settingsModelSelect.appendChild(option);
        settingsModelSelect.disabled = true;
        settingsDraftModel = null;
        updateSettingsModelDetails();
        return;
    }

    for (const model of models) {
        const option = document.createElement('option');
        option.value = model.id;
        option.disabled = !model.available;
        option.textContent = `${model.displayLabel || model.label}${model.available ? '' : ' | unavailable'}`;
        settingsModelSelect.appendChild(option);
    }

    const selected = models.find((model) => model.id === selectedId && model.available)
        || models.find((model) => model.id === settingsState?.settings?.modelProfile && model.available)
        || models.find((model) => model.id === settingsState?.defaults?.modelProfile && model.available)
        || models.find((model) => model.available)
        || null;

    settingsDraftModel = selected?.id || null;
    settingsModelSelect.value = settingsDraftModel || '';
    settingsModelSelect.disabled = settingsActionInFlight || !selected;
    if (selected) {
        settingsContextLength.min = String(MIN_SUPPORTED_CONTEXT_LENGTH);
        settingsContextLength.max = String(Math.max(MIN_SUPPORTED_CONTEXT_LENGTH, selected.maxContextLength || MIN_SUPPORTED_CONTEXT_LENGTH));
        if (Number(settingsContextLength.value) > Number(selected.maxContextLength || 131072)) {
            settingsContextLength.value = String(selected.recommendedContextLength || selected.maxContextLength || 131072);
        }
    }
    updateSettingsModelDetails();
}

function setSettingsModel(modelId) {
    const model = getModelState(modelId);
    if (!model?.available || settingsActionInFlight) return;
    settingsDraftModel = modelId;
    settingsModelSelect.value = modelId;

    if (Number(model.recommendedContextLength) > 0) {
        settingsContextLength.min = String(MIN_SUPPORTED_CONTEXT_LENGTH);
        settingsContextLength.max = String(Math.max(MIN_SUPPORTED_CONTEXT_LENGTH, model.maxContextLength || MIN_SUPPORTED_CONTEXT_LENGTH));
        if (Number(settingsContextLength.value) > Number(model.maxContextLength || 131072)) {
            settingsContextLength.value = String(model.recommendedContextLength);
        }
    }
    updateSettingsModelDetails();
    syncModelRecipeHints();
    updateSettingsImpact();
}

function formatAdvancedValue(value, digits = 0) {
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value ?? '');
    if (digits > 0) return number.toFixed(digits);
    return Math.round(number).toLocaleString();
}

function relabelSettingsField(control, labelText) {
    if (!control) return;
    const field = control.closest('label') || control.parentElement;
    if (!field) return;

    const preferred = [...field.querySelectorAll('span, strong, .label, .field-label, .settings-label')]
        .find((node) => node !== control && !node.contains(control) && node.textContent.trim());
    if (preferred) {
        preferred.textContent = labelText;
        return;
    }

    const textNode = [...field.childNodes]
        .find((node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim());
    if (textNode) textNode.textContent = `${labelText} `;
}

function addAdvancedRuntimeStyles() {
    if (document.getElementById('sorAdvancedRuntimeStyles')) return;
    const style = document.createElement('style');
    style.id = 'sorAdvancedRuntimeStyles';
    style.textContent = `
        .aid-range-shell { margin-top: 7px; }
        .aid-range-head, .aid-range-bounds, .aid-inference-head {
            display: flex; align-items: center; justify-content: space-between; gap: 10px;
        }
        .aid-range-head { font-size: 12px; margin-bottom: 4px; }
        .aid-range-value { font-variant-numeric: tabular-nums; opacity: .9; }
        .aid-range-default { opacity: .55; }
        .aid-range-input { width: 100%; margin: 0; }
        .aid-range-input.aid-is-default { filter: grayscale(1); opacity: .55; }
        .aid-range-bounds { font-size: 10px; opacity: .55; margin-top: 1px; }
        .aid-default-button, .aid-inference-reset {
            border: 0; background: transparent; color: inherit; opacity: .72;
            padding: 0; cursor: pointer; font: inherit; text-decoration: underline;
        }
        .aid-default-button:hover, .aid-inference-reset:hover { opacity: 1; }
        .aid-inference-panel {
            grid-column: 1 / -1; margin-top: 10px; padding: 12px;
            border: 1px solid rgba(127,127,127,.28); border-radius: 8px;
        }
        .aid-inference-title { font-weight: 600; }
        .aid-inference-copy { margin: 3px 0 10px; font-size: 11px; opacity: .68; line-height: 1.35; }
        .aid-inference-grid {
            display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px;
        }
        .aid-inference-field { min-width: 0; }
        .aid-inference-default-line { display:flex; align-items:center; gap:6px; margin-top:4px; font-size:10px; opacity:.7; }
        .aid-inference-select { width: 100%; margin-top: 7px; }
        .aid-prime-help { display:block; margin-top:4px; font-size:10px; opacity:.62; line-height:1.3; }
        @media (max-width: 760px) { .aid-inference-grid { grid-template-columns: 1fr; } }
    `;
    document.head.appendChild(style);
}

function selectedModelRecipeDefaults() {
    const model = getModelState(settingsDraftModel);
    if (model?.recipe === 'flash_next_mtp') {
        return { gpuLayers: 12, cpuMoeLayers: 48 };
    }
    return { gpuLayers: 'Auto', cpuMoeLayers: 'Off' };
}

function selectedModelInferenceDefaults() {
    const model = getModelState(settingsDraftModel);
    const defaults = model?.inferenceDefaults;
    return {
        temperature: Number(defaults?.temperature ?? 0.8),
        topP: Number(defaults?.topP ?? 0.95),
        topK: Number(defaults?.topK ?? 40),
        minP: Number(defaults?.minP ?? 0.05),
        presencePenalty: Number(defaults?.presencePenalty ?? 0),
        repetitionPenalty: Number(defaults?.repetitionPenalty ?? 1),
        promptCacheReuse: defaults?.promptCacheReuse !== false
    };
}

function detectedLogicalCpuCount() {
    const fromMain = Number(settingsState?.host?.logicalCpuCount || 0);
    const fromRenderer = Number(navigator.hardwareConcurrency || 0);
    return Math.max(1, Number.isFinite(fromMain) && fromMain > 0 ? fromMain : (fromRenderer || 1));
}

function createOptionalRangeBinding(control, {
    min,
    max,
    step = 1,
    defaultValue,
    defaultLabel = null,
    format = (value) => formatAdvancedValue(value)
}) {
    if (!control || control.dataset.aiDirectorRangeEnhanced === 'true') return null;
    control.dataset.aiDirectorRangeEnhanced = 'true';
    control.style.display = 'none';

    const shell = document.createElement('div');
    shell.className = 'aid-range-shell';
    shell.innerHTML = `
        <div class="aid-range-head">
            <span class="aid-range-value"></span>
            <button class="aid-default-button" type="button">Use Default</button>
        </div>
        <input class="aid-range-input" type="range">
        <div class="aid-range-bounds"><span class="aid-min"></span><span class="aid-max"></span></div>
    `;
    control.insertAdjacentElement('afterend', shell);
    const range = shell.querySelector('.aid-range-input');
    const valueNode = shell.querySelector('.aid-range-value');
    const minNode = shell.querySelector('.aid-min');
    const maxNode = shell.querySelector('.aid-max');
    const defaultButton = shell.querySelector('.aid-default-button');

    const resolve = (value) => typeof value === 'function' ? value() : value;
    const sync = () => {
        const resolvedMin = Number(resolve(min));
        const baseMax = Number(resolve(max));
        const resolvedDefault = Number(resolve(defaultValue));
        const isDefault = control.value.trim() === '';
        const explicit = Number(control.value);
        const effective = isDefault ? resolvedDefault : explicit;
        const resolvedMax = Math.max(baseMax, !isDefault && Number.isFinite(explicit) ? explicit : baseMax);
        range.min = String(resolvedMin);
        range.max = String(resolvedMax);
        range.step = String(step);
        range.value = String(Math.min(resolvedMax, Math.max(resolvedMin, Number.isFinite(effective) ? effective : resolvedDefault)));
        range.classList.toggle('aid-is-default', isDefault);
        valueNode.classList.toggle('aid-range-default', isDefault);
        const label = isDefault && defaultLabel !== null ? resolve(defaultLabel) : null;
        valueNode.textContent = label || format(range.value);
        minNode.textContent = format(resolvedMin);
        maxNode.textContent = format(resolvedMax);
    };

    range.addEventListener('input', () => {
        control.value = range.value;
        sync();
        control.dispatchEvent(new Event('input', { bubbles: true }));
    });
    defaultButton.addEventListener('click', (event) => {
        event.preventDefault();
        control.value = '';
        sync();
        control.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const binding = { control, range, sync };
    advancedRangeBindings.push(binding);
    sync();
    return binding;
}


function createGpuLayerRangeBinding(control) {
    if (!control || control.dataset.aiDirectorRangeEnhanced === 'true') return null;
    control.dataset.aiDirectorRangeEnhanced = 'true';
    control.style.display = 'none';

    const shell = document.createElement('div');
    shell.className = 'aid-range-shell';
    shell.innerHTML = `
        <div class="aid-range-head">
            <span class="aid-range-value"></span>
            <button class="aid-default-button" type="button">Use Default</button>
        </div>
        <input class="aid-range-input" type="range" min="-1" max="999" step="1">
        <div class="aid-range-bounds"><span>Auto</span><span>999</span></div>
    `;
    control.insertAdjacentElement('afterend', shell);

    const range = shell.querySelector('.aid-range-input');
    const valueNode = shell.querySelector('.aid-range-value');
    const defaultButton = shell.querySelector('.aid-default-button');

    const sync = () => {
        const defaults = selectedModelRecipeDefaults();
        const raw = control.value.trim();
        const isDefault = raw === '';
        let sliderValue;
        let text;

        if (isDefault) {
            if (defaults.gpuLayers === 'Auto') {
                sliderValue = -1;
                text = 'Default: Auto';
            } else {
                sliderValue = Number(defaults.gpuLayers);
                text = `Default: ${defaults.gpuLayers}`;
            }
        } else if (raw.toLowerCase() === 'auto') {
            sliderValue = -1;
            text = 'Auto';
        } else {
            sliderValue = Number(raw);
            text = sliderValue === 0 ? '0 (CPU only)' : String(Math.round(sliderValue));
        }

        if (!Number.isFinite(sliderValue)) sliderValue = -1;
        range.value = String(Math.max(-1, Math.min(999, sliderValue)));
        range.classList.toggle('aid-is-default', isDefault);
        valueNode.classList.toggle('aid-range-default', isDefault);
        valueNode.textContent = text;
    };

    range.addEventListener('input', () => {
        const value = Number(range.value);
        control.value = value < 0 ? 'auto' : String(Math.round(value));
        sync();
        control.dispatchEvent(new Event('input', { bubbles: true }));
    });
    defaultButton.addEventListener('click', (event) => {
        event.preventDefault();
        control.value = '';
        sync();
        control.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const binding = { control, range, sync };
    advancedRangeBindings.push(binding);
    sync();
    return binding;
}

function createCpuMoeRangeBinding(control) {
    if (!control || control.dataset.aiDirectorRangeEnhanced === 'true') return null;
    control.dataset.aiDirectorRangeEnhanced = 'true';
    control.style.display = 'none';

    const shell = document.createElement('div');
    shell.className = 'aid-range-shell';
    shell.innerHTML = `
        <div class="aid-range-head">
            <span class="aid-range-value"></span>
            <button class="aid-default-button" type="button">Use Default</button>
        </div>
        <input class="aid-range-input" type="range" min="0" max="999" step="1">
        <div class="aid-range-bounds"><span>0 / Off</span><span>999</span></div>
    `;
    control.insertAdjacentElement('afterend', shell);

    const range = shell.querySelector('.aid-range-input');
    const valueNode = shell.querySelector('.aid-range-value');
    const defaultButton = shell.querySelector('.aid-default-button');

    const sync = () => {
        const defaults = selectedModelRecipeDefaults();
        const raw = control.value.trim();
        const isDefault = raw === '';
        const defaultValue = defaults.cpuMoeLayers === 'Off' ? 0 : Number(defaults.cpuMoeLayers);
        const explicit = Number(raw);
        const value = isDefault ? defaultValue : explicit;
        range.value = String(Math.max(0, Math.min(999, Number.isFinite(value) ? value : 0)));
        range.classList.toggle('aid-is-default', isDefault);
        valueNode.classList.toggle('aid-range-default', isDefault);

        if (isDefault) {
            valueNode.textContent = defaultValue === 0 ? 'Default: Off' : `Default: ${defaultValue}`;
        } else {
            valueNode.textContent = Number(range.value) === 0 ? 'Off' : String(Math.round(Number(range.value)));
        }
    };

    range.addEventListener('input', () => {
        control.value = String(Math.round(Number(range.value)));
        sync();
        control.dispatchEvent(new Event('input', { bubbles: true }));
    });
    defaultButton.addEventListener('click', (event) => {
        event.preventDefault();
        control.value = '';
        sync();
        control.dispatchEvent(new Event('input', { bubbles: true }));
    });

    const binding = { control, range, sync };
    advancedRangeBindings.push(binding);
    sync();
    return binding;
}

function syncKvFlashControls() {
    const kvIsDefault = Boolean(settingsKvCacheDefault?.checked);
    const flashIsDefault = Boolean(settingsFlashAttentionDefault?.checked);

    if (kvIsDefault) settingsKvCacheType.value = 'q8_0';
    settingsKvCacheType.disabled = kvIsDefault || settingsActionInFlight;

    if (flashIsDefault) settingsFlashAttention.value = 'on';
    settingsFlashAttention.disabled = flashIsDefault || settingsActionInFlight;

    const effectiveKv = kvIsDefault ? 'q8_0' : settingsKvCacheType.value;
    const offOption = [...settingsFlashAttention.options].find((option) => option.value === 'off');
    const flashOffAllowed = effectiveKv === 'f16';
    if (offOption) offOption.disabled = !flashOffAllowed;

    // Do not leave the form in an impossible state if the user selects Flash Off
    // with F16 and then moves KV cache back to a quantized format.
    if (!flashOffAllowed && !flashIsDefault && settingsFlashAttention.value === 'off') {
        settingsFlashAttention.value = 'on';
    }

    if (settingsFlashAttentionHelp) {
        settingsFlashAttentionHelp.textContent = effectiveKv === 'f16'
            ? 'Default: On. Off is available with F16 KV cache.'
            : 'Default: On. Off requires F16 KV cache.';
    }
}

function syncAdvancedRangeBindings() {
    for (const binding of advancedRangeBindings) binding.sync();
}

function ensureAdvancedRuntimeControls() {
    if (advancedRuntimeUiReady) return;
    advancedRuntimeUiReady = true;
    addAdvancedRuntimeStyles();

    relabelSettingsField(settingsGpuLayers, 'GPU Offload (Layers)');
    relabelSettingsField(settingsCpuMoeLayers, 'CPU MoE Layers');
    relabelSettingsField(settingsKvCacheType, 'KV Cache Quantization');
    relabelSettingsField(settingsFlashAttention, 'Flash Attention');
    relabelSettingsField(settingsThreads, 'CPU Thread Pool Size');
    relabelSettingsField(settingsBatchThreads, 'Batch Thread Pool Size');
    relabelSettingsField(settingsBatchSize, 'Evaluation Batch Size');
    relabelSettingsField(settingsMicroBatchSize, 'Evaluation Micro-Batch Size');
    relabelSettingsField(settingsPrimeCache, 'Prime Execution Prefix on Server Start');

    createGpuLayerRangeBinding(settingsGpuLayers);
    createCpuMoeRangeBinding(settingsCpuMoeLayers);

    createOptionalRangeBinding(settingsThreads, {
        min: 1,
        max: () => detectedLogicalCpuCount(),
        defaultValue: () => detectedLogicalCpuCount(),
        defaultLabel: 'Auto'
    });
    createOptionalRangeBinding(settingsBatchThreads, {
        min: 1,
        max: () => detectedLogicalCpuCount(),
        defaultValue: () => {
            const threads = Number(settingsThreads.value);
            return settingsThreads.value.trim() === '' || !Number.isFinite(threads)
                ? detectedLogicalCpuCount()
                : threads;
        },
        defaultLabel: 'Auto'
    });
    createOptionalRangeBinding(settingsBatchSize, {
        min: 32, max: 4096, step: 32, defaultValue: 512
    });
    createOptionalRangeBinding(settingsMicroBatchSize, {
        min: 16,
        max: () => {
            const batch = settingsBatchSize.value.trim() === '' ? 512 : Number(settingsBatchSize.value);
            return Math.max(16, Math.min(4096, Number.isFinite(batch) ? batch : 512));
        },
        step: 16,
        defaultValue: () => Math.min(256, settingsBatchSize.value.trim() === '' ? 512 : Number(settingsBatchSize.value) || 512)
    });

    const anchor = settingsMicroBatchSize?.closest('label') || settingsMicroBatchSize?.parentElement;
    if (!anchor?.parentElement) return;

    const panel = document.createElement('div');
    panel.id = 'settingsInferencePanel';
    panel.className = 'aid-inference-panel';
    panel.innerHTML = `
        <div class="aid-inference-head">
            <span class="aid-inference-title">Inference &amp; Sampling</span>
            <button id="settingsResetInference" class="aid-inference-reset" type="button">Reset Inference</button>
        </div>
        <div class="aid-inference-copy">Defaults follow verified model guidance when available; other models use llama.cpp defaults.</div>
        <div class="aid-inference-grid">
            <div class="aid-inference-field">
                <div class="aid-range-head"><span>Temperature</span><output id="settingsTemperatureValue"></output></div>
                <input id="settingsTemperature" class="aid-range-input" type="range" min="0" max="1" step="0.05">
                <div class="aid-range-bounds"><span>0</span><span>1</span></div>
                <label class="aid-inference-default-line"><input id="settingsTemperatureDefault" type="checkbox"> Use Default</label>
            </div>
            <div class="aid-inference-field">
                <div class="aid-range-head"><span>Top P Sampling</span><output id="settingsTopPValue"></output></div>
                <input id="settingsTopP" class="aid-range-input" type="range" min="0" max="1" step="0.01">
                <div class="aid-range-bounds"><span>0</span><span>1</span></div>
                <label class="aid-inference-default-line"><input id="settingsTopPDefault" type="checkbox"> Use Default</label>
            </div>
            <div class="aid-inference-field">
                <div class="aid-range-head"><span>Top K Sampling</span><output id="settingsTopKValue"></output></div>
                <input id="settingsTopK" class="aid-range-input" type="range" min="0" max="200" step="1">
                <div class="aid-range-bounds"><span>0</span><span>200</span></div>
                <label class="aid-inference-default-line"><input id="settingsTopKDefault" type="checkbox"> Use Default</label>
            </div>
            <div class="aid-inference-field">
                <div class="aid-range-head"><span>Min P Sampling</span><output id="settingsMinPValue"></output></div>
                <input id="settingsMinP" class="aid-range-input" type="range" min="0" max="1" step="0.01">
                <div class="aid-range-bounds"><span>0</span><span>1</span></div>
                <label class="aid-inference-default-line"><input id="settingsMinPDefault" type="checkbox"> Use Default</label>
            </div>
            <div class="aid-inference-field">
                <div class="aid-range-head"><span>Presence Penalty</span><output id="settingsPresencePenaltyValue"></output></div>
                <input id="settingsPresencePenalty" class="aid-range-input" type="range" min="0" max="2" step="0.05">
                <div class="aid-range-bounds"><span>0</span><span>2</span></div>
                <label class="aid-inference-default-line"><input id="settingsPresencePenaltyDefault" type="checkbox"> Use Default</label>
            </div>
            <div class="aid-inference-field">
                <div class="aid-range-head"><span>Repeat Penalty</span><output id="settingsRepetitionPenaltyValue"></output></div>
                <input id="settingsRepetitionPenalty" class="aid-range-input" type="range" min="0" max="2" step="0.05">
                <div class="aid-range-bounds"><span>0</span><span>2</span></div>
                <label class="aid-inference-default-line"><input id="settingsRepetitionPenaltyDefault" type="checkbox"> Use Default</label>
            </div>
            <label class="aid-inference-field">
                <div class="aid-range-head"><span>Prompt Cache Reuse</span></div>
                <select id="settingsPromptCacheReuse" class="aid-inference-select">
                    <option value="on">On</option>
                    <option value="off">Off</option>
                </select>
            </label>
        </div>
    `;
    anchor.insertAdjacentElement('afterend', panel);

    settingsTemperature = panel.querySelector('#settingsTemperature');
    settingsTemperatureDefault = panel.querySelector('#settingsTemperatureDefault');
    settingsTopP = panel.querySelector('#settingsTopP');
    settingsTopPDefault = panel.querySelector('#settingsTopPDefault');
    settingsTopK = panel.querySelector('#settingsTopK');
    settingsTopKDefault = panel.querySelector('#settingsTopKDefault');
    settingsMinP = panel.querySelector('#settingsMinP');
    settingsMinPDefault = panel.querySelector('#settingsMinPDefault');
    settingsPresencePenalty = panel.querySelector('#settingsPresencePenalty');
    settingsPresencePenaltyDefault = panel.querySelector('#settingsPresencePenaltyDefault');
    settingsRepetitionPenalty = panel.querySelector('#settingsRepetitionPenalty');
    settingsRepetitionPenaltyDefault = panel.querySelector('#settingsRepetitionPenaltyDefault');
    settingsPromptCacheReuse = panel.querySelector('#settingsPromptCacheReuse');
    settingsResetInference = panel.querySelector('#settingsResetInference');

    const temperatureValue = panel.querySelector('#settingsTemperatureValue');
    const topPValue = panel.querySelector('#settingsTopPValue');
    const topKValue = panel.querySelector('#settingsTopKValue');
    const minPValue = panel.querySelector('#settingsMinPValue');
    const presencePenaltyValue = panel.querySelector('#settingsPresencePenaltyValue');
    const repetitionPenaltyValue = panel.querySelector('#settingsRepetitionPenaltyValue');

    const syncSampler = (control, defaultControl, output, defaultValue, formatter) => {
        if (defaultControl.checked) control.value = String(defaultValue);
        control.disabled = defaultControl.checked;
        control.classList.toggle('aid-is-default', defaultControl.checked);
        output.classList.toggle('aid-range-default', defaultControl.checked);
        output.textContent = formatter(control.value);
    };

    const syncInferenceUi = () => {
        const defaults = selectedModelInferenceDefaults();
        syncSampler(settingsTemperature, settingsTemperatureDefault, temperatureValue, defaults.temperature, (value) => Number(value).toFixed(2));
        syncSampler(settingsTopP, settingsTopPDefault, topPValue, defaults.topP, (value) => Number(value).toFixed(2));
        syncSampler(settingsTopK, settingsTopKDefault, topKValue, defaults.topK, (value) => String(Math.round(Number(value))));
        syncSampler(settingsMinP, settingsMinPDefault, minPValue, defaults.minP, (value) => Number(value).toFixed(2));
        syncSampler(settingsPresencePenalty, settingsPresencePenaltyDefault, presencePenaltyValue, defaults.presencePenalty, (value) => Number(value).toFixed(2));
        syncSampler(settingsRepetitionPenalty, settingsRepetitionPenaltyDefault, repetitionPenaltyValue, defaults.repetitionPenalty, (value) => Number(value).toFixed(2));
    };
    panel.syncInferenceUi = syncInferenceUi;

    [settingsTemperature, settingsTopP, settingsTopK, settingsMinP, settingsPresencePenalty, settingsRepetitionPenalty, settingsPromptCacheReuse].forEach((control) => {
        control.addEventListener('input', () => { syncInferenceUi(); updateSettingsImpact(); });
        control.addEventListener('change', () => { syncInferenceUi(); updateSettingsImpact(); });
    });
    [settingsTemperatureDefault, settingsTopPDefault, settingsTopKDefault, settingsMinPDefault, settingsPresencePenaltyDefault, settingsRepetitionPenaltyDefault].forEach((control) => {
        control.addEventListener('change', () => { syncInferenceUi(); updateSettingsImpact(); });
    });
    settingsResetInference.addEventListener('click', () => {
        if (settingsActionInFlight) return;
        settingsTemperatureDefault.checked = true;
        settingsTopPDefault.checked = true;
        settingsTopKDefault.checked = true;
        settingsMinPDefault.checked = true;
        settingsPresencePenaltyDefault.checked = true;
        settingsRepetitionPenaltyDefault.checked = true;
        settingsPromptCacheReuse.value = selectedModelInferenceDefaults().promptCacheReuse ? 'on' : 'off';
        syncInferenceUi();
        updateSettingsImpact();
    });
    syncInferenceUi();
}

function syncModelRecipeHints() {
    const defaults = selectedModelRecipeDefaults();
    settingsGpuLayers.placeholder = defaults.gpuLayers === 'Auto'
        ? 'Auto'
        : String(defaults.gpuLayers);
    settingsCpuMoeLayers.placeholder = defaults.cpuMoeLayers === 'Off'
        ? '0'
        : String(defaults.cpuMoeLayers);
    settingsThreads.placeholder = 'Auto';
    settingsBatchThreads.placeholder = 'Auto';
    settingsBatchSize.placeholder = '512';
    settingsMicroBatchSize.placeholder = '256';
    settingsResetTuning.textContent = 'Reset Load Overrides';
    syncAdvancedRangeBindings();
    syncKvFlashControls();
    document.getElementById('settingsInferencePanel')?.syncInferenceUi?.();
}


function normalizeFfmpegDraft(value = {}) {
    const mode = String(value?.mode || 'disabled').toLowerCase() === 'external' ? 'external' : 'disabled';
    if (mode === 'disabled') return { mode: 'disabled', ffmpegPath: null, ffprobePath: null };
    return {
        mode: 'external',
        ffmpegPath: String(value?.ffmpegPath || ''),
        ffprobePath: String(value?.ffprobePath || '')
    };
}

function renderFfmpegDraft() {
    const config = normalizeFfmpegDraft(settingsDraftFfmpeg);
    const status = settingsDraftFfmpegStatus;
    if (config.mode === 'disabled') {
        settingsFfmpegSummary.textContent = 'Continue Without FFmpeg';
        settingsFfmpegPath.textContent = 'AI Director core and Resolve-native features remain available without FFmpeg.';
        settingsFfmpegHelp.textContent = 'Optional FFmpeg-backed media analysis/QC actions remain unavailable until you locate a validated external pair.';
    } else if (status?.state === 'ready' && status?.available) {
        const version = status.ffmpegVersion || 'validated';
        settingsFfmpegSummary.textContent = `External FFmpeg ready · ${version}`;
        settingsFfmpegPath.textContent = config.ffmpegPath;
        settingsFfmpegHelp.textContent = 'ffmpeg.exe and ffprobe.exe passed AI Director identity and capability validation. Apply to make this pair available only to AI Director child processes.';
    } else if (status?.state === 'error') {
        settingsFfmpegSummary.textContent = 'External FFmpeg needs attention';
        settingsFfmpegPath.textContent = status.error || config.ffmpegPath || 'The saved external FFmpeg pair could not be validated.';
        settingsFfmpegHelp.textContent = 'Locate a working pair again, choose the Recommended build, or Continue Without FFmpeg.';
    } else {
        settingsFfmpegSummary.textContent = 'External FFmpeg selected';
        settingsFfmpegPath.textContent = config.ffmpegPath || 'Validation pending';
        settingsFfmpegHelp.textContent = 'Apply will revalidate the selected absolute ffmpeg.exe + ffprobe.exe pair before any runtime change.';
    }
    const disabled = settingsActionInFlight || ffmpegActionInFlight;
    settingsFfmpegGet.disabled = disabled;
    settingsFfmpegLocate.disabled = disabled;
    settingsFfmpegDisable.disabled = disabled || config.mode === 'disabled';
}

function readSettingsForm() {
    const hours = Number(settingsTimeoutHours.value);
    const optionalNumber = (element) => element.value.trim() === '' ? null : Number(element.value);
    let gpuLayers = settingsGpuLayers.value.trim();
    if (!gpuLayers) gpuLayers = null;
    else if (gpuLayers.toLowerCase() !== 'auto') gpuLayers = Number(gpuLayers);

    const flashValue = settingsFlashAttention.value;
    const flashAttention = settingsFlashAttentionDefault?.checked
        ? null
        : (flashValue === 'on' ? true : (flashValue === 'off' ? false : null));
    const kvCacheType = settingsKvCacheDefault?.checked
        ? null
        : (settingsKvCacheType.value || null);

    ensureAdvancedRuntimeControls();
    const promptCacheValue = settingsPromptCacheReuse?.value || 'on';
    const promptCacheReuse = promptCacheValue !== 'off';

    return {
        schemaVersion: 10,
        setupCompleted: true,
        serverProfile: settingsDraftProfile,
        modelProfile: settingsDraftModel,
        runtime: {
            contextLength: Number(settingsContextLength.value),
            maxOutputTokens: Number(settingsMaxOutput.value),
            timeoutSeconds: Math.round(hours * 3600),
            contextOverflowPolicy: settingsContextOverflowPolicy?.value || 'rolling_window'
        },
        tuning: {
            gpuLayers,
            cpuMoeLayers: optionalNumber(settingsCpuMoeLayers),
            kvCacheType,
            flashAttention,
            threads: optionalNumber(settingsThreads),
            batchThreads: optionalNumber(settingsBatchThreads),
            batchSize: optionalNumber(settingsBatchSize),
            microBatchSize: optionalNumber(settingsMicroBatchSize)
        },
        inference: {
            temperature: settingsTemperatureDefault?.checked ? null : Number(settingsTemperature?.value ?? 0.8),
            topP: settingsTopPDefault?.checked ? null : Number(settingsTopP?.value ?? 0.95),
            topK: settingsTopKDefault?.checked ? null : Number(settingsTopK?.value ?? 40),
            minP: settingsMinPDefault?.checked ? null : Number(settingsMinP?.value ?? 0.05),
            presencePenalty: settingsPresencePenaltyDefault?.checked ? null : Number(settingsPresencePenalty?.value ?? 0),
            repetitionPenalty: settingsRepetitionPenaltyDefault?.checked ? null : Number(settingsRepetitionPenalty?.value ?? 1),
            promptCacheReuse
        },
        appearance: { skin: normalizeSkin(settingsDraftSkin) },
        ffmpeg: normalizeFfmpegDraft(settingsDraftFfmpeg),
        primeExecutionCache: settingsPrimeCache.checked
    };
}

function describeSettingsImpact(base, next) {
    if (!base || settingsState?.setupRequired) {
        return next.primeExecutionCache
            ? 'AI Director will validate these settings, start the selected server and backend, then prime the execution prefix.'
            : 'AI Director will validate these settings and start the selected server and backend. Execution-prefix priming is disabled.';
    }

    const serverRunning = settingsState?.server?.state === 'connected' &&
        settingsState?.server?.ownership === 'owned';
    const fullServerChange =
        base.serverProfile !== next.serverProfile ||
        base.modelProfile !== next.modelProfile ||
        base.runtime.contextLength !== next.runtime.contextLength ||
        JSON.stringify(base.tuning || {}) !== JSON.stringify(next.tuning || {});

    if (fullServerChange) {
        if (!serverRunning) {
            return 'Saves these load settings for the next server start. No running process will be restarted.';
        }
        return next.primeExecutionCache
            ? 'Restarts llama-server and the Python backend, then primes the execution prefix.'
            : 'Restarts llama-server and the Python backend. Execution-prefix priming is disabled.';
    }

    if (JSON.stringify(normalizeFfmpegDraft(base.ffmpeg)) !== JSON.stringify(normalizeFfmpegDraft(next.ffmpeg))) {
        if (!serverRunning) {
            return 'Saves the external FFmpeg choice for the next backend start. llama-server is unaffected.';
        }
        return 'Restarts only the Python backend so AI Director can apply the external FFmpeg boundary. llama-server stays loaded.';
    }

    if (base.runtime.maxOutputTokens !== next.runtime.maxOutputTokens) {
        if (!serverRunning) {
            return 'Saves this runtime setting for the next backend start.';
        }
        return next.primeExecutionCache
            ? 'Restarts only the Python backend, then primes the execution prefix. llama-server stays loaded.'
            : 'Restarts only the Python backend. llama-server stays loaded and priming is disabled.';
    }

    if (
        base.runtime.timeoutSeconds !== next.runtime.timeoutSeconds ||
        base.runtime.contextOverflowPolicy !== next.runtime.contextOverflowPolicy ||
        JSON.stringify(base.inference || {}) !== JSON.stringify(next.inference || {})
    ) {
        if (!serverRunning) {
            return 'Saves these request settings for the next backend start.';
        }
        return 'Restarts only the Python backend. llama-server stays loaded and the existing execution-prefix cache is preserved when available.';
    }

    if (!base.primeExecutionCache && next.primeExecutionCache) {
        return serverRunning
            ? 'Primes the execution prefix on the current server without reloading the model.'
            : 'Enables execution-prefix priming for the next server start.';
    }

    if (base.primeExecutionCache && !next.primeExecutionCache) {
        return serverRunning
            ? 'Disables future automatic priming. The current server and any existing execution-prefix cache remain in place.'
            : 'Disables execution-prefix priming for the next server start.';
    }

    return 'No runtime restart is required.';
}

function comparableSettings(settings) {
    const source = settings || {};
    const tuning = source.tuning || {};
    const inference = source.inference || {};
    return {
        serverProfile: source.serverProfile || null,
        modelProfile: source.modelProfile || null,
        runtime: {
            contextLength: Number(source.runtime?.contextLength),
            maxOutputTokens: Number(source.runtime?.maxOutputTokens),
            timeoutSeconds: Number(source.runtime?.timeoutSeconds),
            contextOverflowPolicy: source.runtime?.contextOverflowPolicy || 'rolling_window'
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
            temperature: inference.temperature ?? null,
            topP: inference.topP ?? null,
            topK: inference.topK ?? null,
            minP: inference.minP ?? null,
            presencePenalty: inference.presencePenalty ?? null,
            repetitionPenalty: inference.repetitionPenalty ?? null,
            promptCacheReuse: inference.promptCacheReuse !== false
        },
        ffmpeg: normalizeFfmpegDraft(source.ffmpeg),
        primeExecutionCache: source.primeExecutionCache !== false
    };
}

function settingsFormIsDirty() {
    if (settingsFirstRun) return true;
    if (!settingsState?.settings) return false;
    return JSON.stringify(comparableSettings(readSettingsForm())) !==
        JSON.stringify(comparableSettings(settingsState.settings));
}

function updateSettingsApplyState() {
    const dirty = settingsFormIsDirty();
    applySettingsButton.disabled = settingsActionInFlight || settingsApplyBlocked || (!settingsFirstRun && !dirty);
}

function updateSettingsImpact() {
    if (!settingsState) return;
    const next = readSettingsForm();
    const model = getModelState(next.modelProfile);
    const modelPrefix = model ? `${model.shortLabel || model.label} - ` : '';
    settingsImpact.textContent = modelPrefix + describeSettingsImpact(settingsState.settings, next);
    updateSettingsApplyState();
}

function applyProfileAvailability(profile, button, stateNode) {
    const available = Boolean(profile?.available);
    button.disabled = !available || settingsActionInFlight;
    button.classList.toggle('unavailable', !available);
    stateNode.textContent = available ? 'Available' : 'Unavailable';
    stateNode.classList.toggle('available', available);
}


function currentSettingsRuntimeMessage(state = settingsState) {
    const serverState = state?.server?.state;
    const backendState = state?.backend?.state;

    if (serverState === 'starting') return 'Starting llama-server…';
    if (backendState === 'starting') return 'Starting AI Director backend…';
    if (backendState === 'priming') return 'Priming execution prefix…';
    if (backendState === 'cache_cold') {
        return String(state?.backend?.error || '').trim() || 'Execution cache not primed.';
    }
    if (backendState === 'error') {
        return String(state?.backend?.error || '').trim() || 'Backend error.';
    }
    if (state?.runtimeBusy || state?.busy) return SETTINGS_RUNTIME_WAIT_MESSAGE;
    return '';
}

function updateSettingsRuntimeGate(
    runtimeBusy = settingsRuntimeBusy,
    applyBlocked = settingsApplyBlocked
) {
    settingsRuntimeBusy = Boolean(runtimeBusy);
    settingsApplyBlocked = Boolean(applyBlocked);
    if (!settingsDialog.open && !settingsState) return;

    updateSettingsApplyState();
    // Rescan remains protected by the broad runtime gate. Only Apply gains the
    // narrower supersedable-prime behavior.
    settingsModelRefresh.disabled = settingsActionInFlight || settingsRuntimeBusy;
    renderFfmpegDraft();

    if (!settingsApplyBlocked && settingsOperationStatus.textContent === SETTINGS_RUNTIME_WAIT_MESSAGE) {
        settingsOperationStatus.textContent = '';
    }
}

function populateSettingsDialog(state, { firstRun = false } = {}) {
    ensureAdvancedRuntimeControls();
    settingsState = state;
    settingsRuntimeBusy = Boolean(state?.runtimeBusy || state?.busy);
    settingsApplyBlocked = Boolean(
        state?.settingsApplyBlocked ?? state?.runtimeBusy ?? state?.busy
    );
    settingsFirstRun = firstRun || Boolean(state?.setupRequired);
    const source = state?.setupRequired ? state.defaults : state.settings;
    settingsDraftProfile = state?.setupRequired ? null : source?.serverProfile;
    settingsDraftModel = source?.modelProfile || state?.defaults?.modelProfile || null;
    settingsDraftSkin = normalizeSkin(source?.appearance?.skin || state?.defaults?.appearance?.skin || 'green');
    settingsDraftFfmpeg = normalizeFfmpegDraft(source?.ffmpeg);
    settingsDraftFfmpegStatus = state?.ffmpegRuntime || null;
    applySkin(settingsDraftSkin);
    syncSkinPicker();

    settingsDialogTitle.textContent = settingsFirstRun ? 'Welcome to AI Director' : 'AI Director Settings';
    settingsDialogSubtitle.textContent = settingsFirstRun
        ? 'Choose a server and detected LM Studio model before anything is loaded.'
        : 'Server, model and runtime preferences are remembered for future launches.';
    closeSettings.hidden = settingsFirstRun;
    cancelSettings.hidden = settingsFirstRun;
    applySettingsButton.textContent = settingsFirstRun ? 'Start AI Director' : 'Apply';

    settingsLoadWarning.hidden = !state?.loadError;
    settingsLoadWarning.textContent = state?.loadError || '';

    const upstream = state?.profiles?.find((profile) => profile.id === 'upstream');
    const direct = state?.profiles?.find((profile) => profile.id === 'direct');
    applyProfileAvailability(upstream, settingsProfileUpstream, settingsProfileUpstreamAvailability);
    applyProfileAvailability(direct, settingsProfileDirect, settingsProfileDirectAvailability);

    settingsContextLength.min = String(MIN_SUPPORTED_CONTEXT_LENGTH);
    settingsContextLength.value = String(Math.max(MIN_SUPPORTED_CONTEXT_LENGTH, Number(source?.runtime?.contextLength) || MIN_SUPPORTED_CONTEXT_LENGTH));
    renderModelOptions(settingsDraftModel);
    settingsModelDiscovery.textContent = state?.modelDiscovery
        ? `${state.modelDiscovery.source} | ${state.modelDiscovery.discoveredCount ?? 0} selectable GGUFs`
        : 'LM Studio model discovery has not run yet.';
    const selectedModel = getModelState(settingsDraftModel);
    settingsContextLength.max = String(Math.max(MIN_SUPPORTED_CONTEXT_LENGTH, selectedModel?.maxContextLength || MIN_SUPPORTED_CONTEXT_LENGTH));
    settingsMaxOutput.max = String(MAX_SUPPORTED_OUTPUT_TOKENS);
    settingsMaxOutput.value = String(Math.min(MAX_SUPPORTED_OUTPUT_TOKENS, Number(source?.runtime?.maxOutputTokens) || 16384));
    settingsTimeoutHours.value = String((Number(source?.runtime?.timeoutSeconds || 43200) / 3600).toFixed(2).replace(/\.00$/, ''));
    if (settingsContextOverflowPolicy) {
        settingsContextOverflowPolicy.value = source?.runtime?.contextOverflowPolicy || 'rolling_window';
    }
    const tuning = source?.tuning || {};
    settingsGpuLayers.value = tuning.gpuLayers ?? '';
    settingsCpuMoeLayers.value = tuning.cpuMoeLayers ?? '';
    settingsKvCacheDefault.checked = tuning.kvCacheType === null || tuning.kvCacheType === undefined;
    settingsKvCacheType.value = tuning.kvCacheType ?? 'q8_0';
    settingsFlashAttentionDefault.checked = tuning.flashAttention === null || tuning.flashAttention === undefined;
    settingsFlashAttention.value = tuning.flashAttention === false ? 'off' : 'on';
    settingsThreads.value = tuning.threads ?? '';
    settingsBatchThreads.value = tuning.batchThreads ?? '';
    settingsBatchSize.value = tuning.batchSize ?? '';
    settingsMicroBatchSize.value = tuning.microBatchSize ?? '';
    const inference = source?.inference || {};
    const inferenceDefaults = selectedModelInferenceDefaults();
    settingsTemperature.value = String(inference.temperature ?? inferenceDefaults.temperature);
    settingsTemperatureDefault.checked = inference.temperature === null || inference.temperature === undefined;
    settingsTopP.value = String(inference.topP ?? inferenceDefaults.topP);
    settingsTopPDefault.checked = inference.topP === null || inference.topP === undefined;
    settingsTopK.value = String(inference.topK ?? inferenceDefaults.topK);
    settingsTopKDefault.checked = inference.topK === null || inference.topK === undefined;
    settingsMinP.value = String(inference.minP ?? inferenceDefaults.minP);
    settingsMinPDefault.checked = inference.minP === null || inference.minP === undefined;
    settingsPresencePenalty.value = String(inference.presencePenalty ?? inferenceDefaults.presencePenalty);
    settingsPresencePenaltyDefault.checked = inference.presencePenalty === null || inference.presencePenalty === undefined;
    settingsRepetitionPenalty.value = String(inference.repetitionPenalty ?? inferenceDefaults.repetitionPenalty);
    settingsRepetitionPenaltyDefault.checked = inference.repetitionPenalty === null || inference.repetitionPenalty === undefined;
    settingsPromptCacheReuse.value = (inference.promptCacheReuse ?? inferenceDefaults.promptCacheReuse) ? 'on' : 'off';
    document.getElementById('settingsInferencePanel')?.syncInferenceUi?.();
    settingsPrimeCache.checked = source?.primeExecutionCache !== false;
    renderFfmpegDraft();
    syncModelRecipeHints();
    settingsOperationStatus.textContent = currentSettingsRuntimeMessage(state);

    [settingsProfileUpstream, settingsProfileDirect].forEach((button) => {
        const selected = button.dataset.profile === settingsDraftProfile;
        button.classList.toggle('selected', selected);
        button.setAttribute('aria-checked', String(selected));
    });
    updateSettingsImpact();
    updateSettingsRuntimeGate(settingsRuntimeBusy, settingsApplyBlocked);
}

async function openSettingsDialog({ firstRun = false } = {}) {
    // Settings is an inspectable/dismissible view even while an already-submitted
    // Apply transaction is bringing llama-server/backend to stable ready. Unsafe
    // controls inside the dialog remain gated by settingsActionInFlight.
    if (isProcessing || updateBusy) return;
    const state = await window.aiDirector.getSettingsState();
    populateSettingsDialog(state, { firstRun });
    if (!settingsDialog.open) settingsDialog.showModal();
}

function updateSettingsOperationStatus(kind, status) {
    if (!settingsDialog.open) return;

    if (kind === 'server') {
        if (status?.state === 'starting') {
            settingsOperationStatus.textContent = 'Starting llama-server…';
            return;
        }
        if (status?.state === 'offline' && settingsActionInFlight) {
            settingsOperationStatus.textContent = 'Applying load settings…';
            return;
        }
    }

    if (kind === 'backend') {
        if (status?.state === 'starting') {
            settingsOperationStatus.textContent = 'Starting AI Director backend…';
            return;
        }
        if (status?.state === 'priming') {
            settingsOperationStatus.textContent = 'Priming execution prefix…';
            return;
        }
        if (status?.state === 'cache_cold' &&
            status?.runtimeBusy !== true &&
            !settingsActionInFlight) {
            settingsOperationStatus.textContent =
                String(status?.error || '').trim() || 'Execution cache not primed.';
            return;
        }
        if (status?.state === 'error' &&
            status?.runtimeBusy !== true &&
            !settingsActionInFlight) {
            settingsOperationStatus.textContent =
                String(status?.error || '').trim() || 'Backend error.';
            return;
        }
        if (status?.state === 'connected' &&
            status?.runtimeBusy !== true &&
            !settingsActionInFlight) {
            settingsOperationStatus.textContent = '';
        }
    }
}

async function applySettingsFromDialog() {
    if (settingsActionInFlight) return;
    if (settingsApplyBlocked) {
        settingsOperationStatus.textContent = SETTINGS_RUNTIME_WAIT_MESSAGE;
        return;
    }

    const candidate = readSettingsForm();
    if (!candidate.serverProfile) {
        settingsOperationStatus.textContent = 'Choose a server profile first.';
        return;
    }
    if (!candidate.modelProfile) {
        settingsOperationStatus.textContent = 'Choose a model profile first.';
        return;
    }

    const wasFirstRun = settingsFirstRun;
    let applySucceeded = false;

    settingsActionInFlight = true;
    settingsOperationStatus.textContent = wasFirstRun ? 'Validating settings…' : 'Applying settings…';
    applySettingsButton.disabled = true;

    // First-run Welcome is only the setup surface. Once the locally-valid Start
    // request is submitted, dismiss it immediately while startup/priming continues.
    // If the settings transaction itself fails, the catch path reopens Welcome.
    if (wasFirstRun && settingsDialog.open) {
        settingsDialog.close();
    }
    // Cancel/X/Escape are view-dismiss actions, not transaction cancellation.
    // Keep them usable for configured installations while Apply/startup continues.
    cancelSettings.disabled = false;
    // X is a view-dismiss action, not a transaction cancel. Keep it usable for
    // configured installations while Apply/server startup continues in main.
    closeSettings.disabled = false;
    settingsButton.disabled = updateBusy || isProcessing;
    settingsModelSelect.disabled = true;
    settingsModelRefresh.disabled = true;
    syncComposerAvailability();

    try {
        const result = await window.aiDirector.applySettings(candidate);
        if (!result?.ok) throw new Error(result?.error || 'Settings could not be applied.');

        settingsState = await window.aiDirector.getSettingsState();
        settingsRuntimeBusy = Boolean(settingsState?.runtimeBusy || settingsState?.busy);
        settingsApplyBlocked = Boolean(
            settingsState?.settingsApplyBlocked ?? settingsState?.runtimeBusy ?? settingsState?.busy
        );
        applySucceeded = true;

        await refreshServerStatus();
        await refreshBackendStatus();
    } catch (error) {
        const message = error?.message || String(error);
        const state = await window.aiDirector.getSettingsState();
        populateSettingsDialog(state, { firstRun: wasFirstRun });
        if (wasFirstRun && !applySucceeded && !settingsDialog.open) {
            settingsDialog.showModal();
        }
        settingsOperationStatus.textContent = message;
    } finally {
        settingsActionInFlight = false;
        updateSettingsApplyState();
        cancelSettings.disabled = false;
        closeSettings.disabled = false;
        settingsButton.disabled = updateBusy || isProcessing;

        if (applySucceeded && !wasFirstRun && settingsDialog.open && settingsState) {
            populateSettingsDialog(settingsState, { firstRun: false });
            const runtimeMessage = currentSettingsRuntimeMessage(settingsState);
            settingsOperationStatus.textContent = runtimeMessage || 'Settings applied.';
        } else if (!applySucceeded && settingsDialog.open && settingsState) {
            applyProfileAvailability(getProfileState('upstream'), settingsProfileUpstream, settingsProfileUpstreamAvailability);
            applyProfileAvailability(getProfileState('direct'), settingsProfileDirect, settingsProfileDirectAvailability);
            renderModelOptions(settingsDraftModel);
            settingsModelRefresh.disabled = settingsActionInFlight || settingsRuntimeBusy;
            updateSettingsRuntimeGate(settingsRuntimeBusy, settingsApplyBlocked);
        }

        syncComposerAvailability();
    }
}

async function refreshResolveStatus() {
    // Resolve bridge calls may touch Resolve's native bridge. Do not poll while
    // inference is active; that keeps the Electron main process free to process
    // menus, context menus, and cancellation.
    if (isProcessing || resolvePollInFlight) return;

    resolvePollInFlight = true;

    try {
        const status = await window.aiDirector.getBridgeStatus();
        applyResolveStatus(status);
    } catch (error) {
        applyResolveStatus({
            connected: false,
            error: error?.message || String(error)
        });
    } finally {
        resolvePollInFlight = false;
    }
}

async function refreshBackendStatus() {
    if (backendPollInFlight) return;

    backendPollInFlight = true;

    try {
        const status = await window.aiDirector.getBackendStatus();
        applyBackendStatus(status);
    } catch (error) {
        applyBackendStatus({
            state: 'error',
            error: error?.message || String(error)
        });
    } finally {
        backendPollInFlight = false;
    }
}

async function refreshServerStatus() {
    try {
        const status = await window.aiDirector.getServerStatus();
        applyServerStatus(status);
    } catch (error) {
        applyServerStatus({
            state: 'error',
            error: error?.message || String(error)
        });
    }
}

function setUpdateState(node, label, state) {
    node.textContent = label;
    node.classList.remove('available', 'current', 'busy', 'error', 'neutral');
    node.classList.add(state || 'neutral');
}

function updateProgressStateLabel(status) {
    switch (String(status?.phase || '').toLowerCase()) {
        case 'download': return 'Downloading...';
        case 'verify': return 'Verifying...';
        case 'stage': return 'Staging...';
        case 'overlay': return 'Installing...';
        case 'deps': return 'Preparing...';
        case 'backup': return 'Installing...';
        case 'swap': return 'Installing...';
        case 'health': return 'Validating...';
        case 'rollback': return 'Rolling back...';
        case 'git': return 'Updating...';
        case 'done': return 'Finalizing...';
        default: return 'Preparing...';
    }
}

function refreshMcpUpdateAvailability() {
    const mcp = latestUpdateResult?.mcp || null;
    if (!mcp) {
        installMcp.disabled = true;
        return;
    }

    const updateAvailable = Boolean(mcp.updateAvailable);
    const installAvailable = Boolean(mcp.installAvailable);
    const normalReason = updateAvailable
        ? (installAvailable
            ? 'Ready to install. Keep DaVinci Resolve open.'
            : (mcp.installReason || 'Update needs review.'))
        : (mcp.installReason || 'Already current.');

    mcpUpdateReason.textContent = updateAvailable && installAvailable && !resolveReadyForMcpUpdate
        ? MCP_UPDATE_RESOLVE_REQUIRED_CARD_MESSAGE
        : normalReason;
    installMcp.title = updateAvailable && installAvailable && !resolveReadyForMcpUpdate
        ? 'Open DaVinci Resolve to install this update.'
        : 'Install the available DaVinci Resolve MCP update.';

    installMcp.disabled =
        isProcessing ||
        updateBusy ||
        !updateAvailable ||
        !installAvailable ||
        !resolveReadyForMcpUpdate;
}

function applyUpdateResult(result) {
    latestUpdateResult = result || null;
    const llama = result?.llama || null;
    const mcp = result?.mcp || null;

    if (llama) {
        llamaInstalled.textContent = llama.installedVersion || 'Unknown';
        llamaLatest.textContent = llama.latestVersion || 'Unknown';
        llamaBundle.textContent = llama.markerFound
            ? (llama.marker?.bundleProfile || llama.matchedAsset?.name || 'Detected')
            : 'Unmanaged / unknown';
        llamaUpdateReason.textContent = llama.updateAvailable
            ? (llama.installAvailable
                ? 'Ready to install. Resolve can stay closed.'
                : (llama.installReason || 'Update needs review.'))
            : (llama.installReason || 'Already current.');

        if (llama.updateAvailable) {
            setUpdateState(
                llamaUpdateState,
                llama.installAvailable ? 'Update available' : 'Update needs review',
                llama.installAvailable ? 'available' : 'neutral'
            );
        } else if (llama.installedVersion && llama.latestVersion) {
            setUpdateState(llamaUpdateState, 'Current', 'current');
        } else {
            setUpdateState(llamaUpdateState, 'Unknown', 'neutral');
        }

        installLlama.disabled = isProcessing || updateBusy || !llama.installAvailable || !llama.updateAvailable;
    } else {
        installLlama.disabled = true;
    }

    if (mcp) {
        mcpInstalled.textContent = mcp.installedVersion || 'Unknown';
        mcpLatest.textContent = mcp.latestVersion || 'Unknown';
        mcpCheckout.textContent = mcp.managed ? 'Managed' : (mcp.dirty ? 'Modified' : (mcp.origin ? 'Clean' : 'Unavailable'));
        mcpUpdateReason.textContent = mcp.updateAvailable
            ? (mcp.installReason || 'Update available.')
            : (mcp.installReason || 'Already current.');

        if (mcp.updateAvailable) {
            setUpdateState(
                mcpUpdateState,
                mcp.installAvailable ? 'Update available' : 'Update needs review',
                mcp.installAvailable ? 'available' : 'neutral'
            );
        } else if (mcp.installedVersion && mcp.latestVersion) {
            setUpdateState(mcpUpdateState, 'Current', 'current');
        } else {
            setUpdateState(mcpUpdateState, 'Unknown', 'neutral');
        }

        refreshMcpUpdateAvailability();
    } else {
        installMcp.disabled = true;
    }

    const anyAvailable = Boolean(
        (llama?.updateAvailable && llama?.installAvailable) ||
        (mcp?.updateAvailable && mcp?.installAvailable)
    );
    updateIndicator.classList.toggle('visible', anyAvailable);
}

function applyUpdateProgress(status) {
    if (!status) return;

    updateBusy = status.state === 'checking' || status.state === 'installing';
    checkUpdatesButton.disabled = updateBusy || isProcessing;
    updatesButton.disabled = isProcessing || updateBusy || settingsRuntimeBusy;
    prompt.disabled = updateBusy && !isProcessing;
    serverToggle.disabled = updateBusy || settingsActionInFlight || isProcessing || serverActionInFlight || profileActionInFlight;
    profileSelect.disabled = updateBusy || !profileSwitchAllowed || settingsActionInFlight || isProcessing || serverActionInFlight || debugActionInFlight || profileActionInFlight;
    closeUpdates.disabled = updateBusy;
    settingsButton.disabled = updateBusy || isProcessing;
    installLlama.disabled = updateBusy || isProcessing || !(latestUpdateResult?.llama?.updateAvailable && latestUpdateResult?.llama?.installAvailable);
    installMcp.disabled = updateBusy || isProcessing || !resolveReadyForMcpUpdate || !(latestUpdateResult?.mcp?.updateAvailable && latestUpdateResult?.mcp?.installAvailable);

    if (status.state === 'checking') {
        updateDialogStatus.textContent = 'Checking GitHub releases...';
        setUpdateState(llamaUpdateState, 'Checking...', 'busy');
        setUpdateState(mcpUpdateState, 'Checking...', 'busy');
        return;
    }

    if (status.state === 'installing') {
        const pct = Number.isFinite(status.progress) ? ` ${status.progress}%` : '';
        const stateLabel = updateProgressStateLabel(status);
        updateDialogStatus.textContent = status.message || `Installing update...${pct}`;
        if (status.component === 'llama') {
            setUpdateState(llamaUpdateState, stateLabel, 'busy');
        } else if (status.component === 'mcp') {
            setUpdateState(mcpUpdateState, stateLabel, 'busy');
        }
        return;
    }

    if (status.state === 'done') {
        const result = status.result || null;
        updateDialogStatus.textContent = result?.resolveRestartRequired
            ? (result.restartMessage || 'Update completed. Restart DaVinci Resolve to finish the update.')
            : (result?.restartMessage || status.message || 'Update completed.');
        if (result?.check) applyUpdateResult(result.check);
        return;
    }

    if (status.state === 'error') {
        if (latestUpdateResult) applyUpdateResult(latestUpdateResult);
        if (status.result?.rolledBack === true) {
            if (status.component === 'llama') {
                setUpdateState(llamaUpdateState, 'Rolled back', 'error');
                llamaUpdateReason.textContent = 'Previous version restored.';
            } else if (status.component === 'mcp') {
                setUpdateState(mcpUpdateState, 'Rolled back', 'error');
                mcpUpdateReason.textContent = 'Previous version restored.';
            }
        }
        updateDialogStatus.textContent = status.error || 'Update operation failed.';
    }
}

async function openUpdateDialog() {
    if (isProcessing || updateBusy || settingsRuntimeBusy) return;
    if (!updateDialog.open) updateDialog.showModal();
    await checkForUpdates();
}

async function checkForUpdates() {
    if (isProcessing || updateBusy || settingsRuntimeBusy) return;
    updateDialogStatus.textContent = 'Checking GitHub releases...';
    checkUpdatesButton.disabled = true;
    try {
        const response = await window.aiDirector.checkUpdates();
        if (!response?.ok) {
            updateDialogStatus.textContent = response?.error || 'Update check failed.';
            return;
        }
        applyUpdateResult(response.result);
        updateDialogStatus.textContent = `Checked ${new Date(response.result.checkedAt).toLocaleTimeString()}`;
    } catch (error) {
        updateDialogStatus.textContent = error?.message || String(error);
    } finally {
        checkUpdatesButton.disabled = isProcessing || updateBusy;
    }
}

async function installComponent(component) {
    if (isProcessing || updateBusy || settingsRuntimeBusy) return;
    if (component === 'mcp' && !resolveReadyForMcpUpdate) {
        updateDialogStatus.textContent = MCP_UPDATE_RESOLVE_REQUIRED_MESSAGE;
        refreshMcpUpdateAvailability();
        return;
    }
    updateBusy = true;
    applyUpdateProgress({ state: 'installing', component, progress: 0, message: 'Preparing update...' });
    try {
        const response = await window.aiDirector.installUpdate(component);
        if (!response?.ok) {
            updateDialogStatus.textContent = response?.error || 'Update was not installed.';
        } else {
            updateDialogStatus.textContent = response.resolveRestartRequired
                ? (response.restartMessage || 'Update completed. Restart DaVinci Resolve to finish the update.')
                : (response.restartMessage || response.message || 'Update completed.');
            if (response.check) applyUpdateResult(response.check);
        }
    } catch (error) {
        updateDialogStatus.textContent = error?.message || String(error);
    } finally {
        updateBusy = false;
        const status = await window.aiDirector.getUpdateStatus();
        if (status) applyUpdateProgress(status);
        await refreshServerStatus();
        await refreshBackendStatus();
    }
}

function clearChat() {
    if (isProcessing && activeResponse?.wrapper) {
        const nodes = Array.from(conversation.children);
        const activeNodeIndex = nodes.indexOf(activeResponse.wrapper);
        const activeIndex = conversationHistory.indexOf(activeResponse.entry);

        // During inference retain only the newest user bubble and the active
        // response bubble. The active user entry is immediately before the
        // active response in the renderer's message order.
        if (activeNodeIndex >= 0 && activeIndex >= 0) {
            const userNode = activeNodeIndex > 0
                ? nodes[activeNodeIndex - 1]
                : null;
            const userIndex = activeIndex > 0 && conversationHistory[activeIndex - 1]?.role === 'user'
                ? activeIndex - 1
                : activeIndex;

            const keepNodes = [];
            if (userNode?.classList.contains('user')) keepNodes.push(userNode);
            keepNodes.push(activeResponse.wrapper);

            const keepEntries = conversationHistory.slice(userIndex, activeIndex + 1);
            conversationHistory.length = 0;
            conversationHistory.push(...keepEntries);

            nodes.forEach((node) => {
                if (!keepNodes.includes(node)) node.remove();
            });
            scrollConversationToLatest({ force: true });
            return;
        }
    }

    // When idle there is no active inference to preserve, so the entire
    // conversation is cleared.
    conversationHistory.length = 0;
    conversation.replaceChildren();
    conversationFollowsLatest = true;
    syncConversationFollowUi();
}

function addMessage(role, text) {
    const entry = { role, text: String(text ?? '') };
    conversationHistory.push(entry);

    const wrapper = document.createElement('div');
    wrapper.className = 'message ' + role;

    const roleNode = document.createElement('div');
    roleNode.className = 'role';
    roleNode.textContent = role === 'user' ? 'You' : 'AI Director';

    const content = document.createElement('div');
    content.className = 'content';

    if (role === 'assistant') {
        content.innerHTML = window.aiDirectorRenderMarkdown(entry.text);
    } else {
        content.textContent = entry.text;
    }

    wrapper.appendChild(roleNode);
    wrapper.appendChild(content);
    conversation.appendChild(wrapper);

    // A new user request intentionally returns the conversation to the live
    // edge. Assistant/telemetry updates follow only while the user has not
    // deliberately scrolled away from the bottom.
    scrollConversationToLatest({ force: role === 'user' });

    return { wrapper, content, entry };
}

function updateAssistantMessage(message, text) {
    if (!message) return;

    const value = String(text ?? '');
    message.entry.text = value;
    message.content.innerHTML = window.aiDirectorRenderMarkdown(value);
    scrollConversationToLatest();
}

function updateAssistantPlainMessage(message, text) {
    if (!message) return;

    const value = String(text ?? '');
    message.entry.text = value;
    message.content.textContent = value;
    scrollConversationToLatest();
}

function formatDuration(ms) {
    const totalSeconds = Math.max(0, Math.round((Number(ms) || 0) / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return minutes > 0
        ? `${minutes}m ${String(seconds).padStart(2, '0')}s`
        : `${seconds}s`;
}

function formatTokenCount(value) {
    const count = Math.max(0, Number(value) || 0);
    if (count >= 1000000) return `${(count / 1000000).toFixed(2)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(count >= 10000 ? 1 : 2)}K`;
    return String(Math.round(count));
}

function normalizedContextMeterStatus(status) {
    if (!status || typeof status !== 'object') return null;
    const total = Number(status.context_window_tokens);
    const used = Number(status.used_tokens);
    const percent = Number(status.used_percent);
    if (!Number.isFinite(total) || total <= 0 || !Number.isFinite(used)) return null;
    return {
        ...status,
        context_window_tokens: Math.max(1, Math.trunc(total)),
        used_tokens: Math.max(0, Math.trunc(used)),
        used_percent: Number.isFinite(percent)
            ? Math.max(0, Math.min(100, percent))
            : Math.max(0, Math.min(100, (used / total) * 100))
    };
}

function renderContextMeter() {
    if (!contextMeter || !contextMeterProgress || !contextMeterText || !contextMeterCircle) return;
    const status = contextMeterStatus || {
        context_window_tokens: Number(settingsState?.settings?.runtime?.contextLength) || 131072,
        used_tokens: 0,
        used_percent: 0
    };
    const used = Math.max(0, Number(status.used_tokens) || 0);
    const total = Math.max(1, Number(status.context_window_tokens) || 131072);
    const percent = Math.max(0, Math.min(100, Number(status.used_percent) || 0));
    const usedText = formatTokenCount(used);
    const totalText = formatTokenCount(total);
    const percentText = `${percent.toFixed(1)}%`;
    contextMeterProgress.setAttribute('stroke-dashoffset', String(100 - percent));
    contextMeter.title = `${usedText} / ${totalText} used`;
    contextMeter.setAttribute('aria-label', `Context usage ${usedText} of ${totalText}, ${percentText}`);
    contextMeter.setAttribute('aria-expanded', String(contextMeterExpanded));
    contextMeterCircle.hidden = contextMeterExpanded;
    contextMeterText.hidden = !contextMeterExpanded;
    contextMeterText.textContent = `${usedText} / ${totalText} - ${percentText}`;
}

function applyContextMeterStatus(status) {
    const normalized = normalizedContextMeterStatus(status);
    if (!normalized) return;
    // The visible meter represents authoritative context usage. Conservative
    // projections remain available to overflow/admission logic but do not
    // masquerade as exact usage in the user-facing meter. A configured baseline
    // is accepted so Clear Chat and context-setting changes can reset the display.
    if (normalized.exact === true || normalized.source === 'configured' || !contextMeterStatus) {
        contextMeterStatus = normalized;
        renderContextMeter();
    }
}

function formatRate(value) {
    const rate = Number(value);
    if (!Number.isFinite(rate) || rate <= 0) return '-';
    return `${rate.toFixed(rate >= 10 ? 1 : 2)} tok/s`;
}

function ensureTelemetry(message, token) {
    if (!message) return null;
    if (message.telemetry) return message.telemetry;

    const panel = document.createElement('div');
    panel.className = 'request-telemetry active';

    const top = document.createElement('div');
    top.className = 'telemetry-top';

    const phase = document.createElement('span');
    phase.className = 'telemetry-phase';
    phase.textContent = 'Starting';

    const elapsed = document.createElement('span');
    elapsed.className = 'telemetry-elapsed';
    elapsed.textContent = '0s';

    top.appendChild(phase);
    top.appendChild(elapsed);

    const track = document.createElement('div');
    track.className = 'telemetry-track indeterminate';
    const fill = document.createElement('div');
    fill.className = 'telemetry-fill';
    track.appendChild(fill);

    const detail = document.createElement('div');
    detail.className = 'telemetry-detail';
    detail.textContent = 'Preparing request…';

    const details = document.createElement('div');
    details.className = 'telemetry-details';
    details.hidden = true;

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'telemetry-toggle';
    toggle.textContent = 'Details';
    toggle.hidden = true;
    toggle.addEventListener('click', () => {
        details.hidden = !details.hidden;
        toggle.textContent = details.hidden ? 'Details' : 'Hide details';
    });

    panel.appendChild(top);
    panel.appendChild(track);
    panel.appendChild(detail);
    panel.appendChild(toggle);
    panel.appendChild(details);
    message.wrapper.appendChild(panel);

    const state = {
        token,
        panel,
        phase,
        elapsed,
        track,
        fill,
        detail,
        toggle,
        details,
        startedAt: performance.now(),
        lastProgress: null,
        summary: null,
        timer: null,
        finished: false
    };
    state.timer = window.setInterval(() => {
        if (!message.telemetry || message.telemetry !== state) return;
        if (!panel.classList.contains('active')) return;
        elapsed.textContent = formatDuration(performance.now() - state.startedAt);
    }, 500);

    telemetryPanelStates.set(panel, state);
    message.telemetry = state;
    return state;
}

function setTelemetryIndeterminate(state) {
    if (!state) return;
    state.track.classList.add('indeterminate');
    state.fill.style.width = '';
}

function setTelemetryProgress(state, percent) {
    if (!state) return;
    const value = Math.max(0, Math.min(100, Number(percent) || 0));
    state.track.classList.remove('indeterminate');
    state.fill.style.width = `${value}%`;
}

function telemetrySummaryRows(summary) {
    if (!summary) return [];
    const cachePercent = summary.cache_reuse_percent == null
        ? NaN
        : Number(summary.cache_reuse_percent);
    const rows = [
        ['Total time', formatDuration(summary.elapsed_ms)],
        ['Model calls', String(summary.model_calls ?? 0)],
        ['Tool calls', String(summary.tool_calls ?? 0)],
        ['Prompt tokens', formatTokenCount(summary.prompt_tokens)],
        ['Cached prompt', `${formatTokenCount(summary.cached_prompt_tokens)}${Number.isFinite(cachePercent) ? ` (${cachePercent.toFixed(1)}%)` : ''}`],
        ['Evaluated prompt', formatTokenCount(summary.evaluated_prompt_tokens)],
        ['Generated tokens', formatTokenCount(summary.completion_tokens)],
        ['Total tokens', formatTokenCount(summary.total_tokens)],
        ['Prompt speed', formatRate(summary.prompt_tokens_per_second)],
        ['Generation speed', formatRate(summary.generation_tokens_per_second)]
    ];
    const rollingCompactions = Number(summary.context_compactions);
    const compactedTurns = Number(summary.context_compacted_turns);
    if (Number.isFinite(rollingCompactions) && rollingCompactions > 0) {
        rows.push(['Rolling compactions', String(Math.trunc(rollingCompactions))]);
    }
    if (Number.isFinite(compactedTurns) && compactedTurns > 0) {
        rows.push(['Turns compacted', String(Math.trunc(compactedTurns))]);
    }
    const context = summary.context && typeof summary.context === 'object'
        ? summary.context
        : null;
    if (context) {
        const used = Number(context.used_tokens);
        const total = Number(context.context_window_tokens);
        const percent = Number(context.used_percent);
        const headroom = Number(context.headroom_tokens);
        const outputReserve = Number(context.max_output_tokens);
        const safetyReserve = Number(context.safety_margin_tokens);
        const exact = context.exact === true;
        if (Number.isFinite(used) && Number.isFinite(total) && total > 0) {
            rows.push([
                exact ? 'Context used' : 'Context projected',
                `${formatTokenCount(used)} / ${formatTokenCount(total)}${Number.isFinite(percent) ? ` - ${percent.toFixed(1)}%` : ''}`
            ]);
        }
        if (Number.isFinite(headroom)) rows.push(['Context headroom', formatTokenCount(headroom)]);
        if (Number.isFinite(outputReserve)) rows.push(['Output reserve', formatTokenCount(outputReserve)]);
        if (Number.isFinite(safetyReserve)) rows.push(['Safety reserve', formatTokenCount(safetyReserve)]);
        rows.push(['Context source', exact ? 'llama-server usage' : String(context.source || 'projection')]);
    }
    return rows;
}

function renderTelemetryDetails(state, summary) {
    if (!state || !summary) return;
    const rows = telemetrySummaryRows(summary);

    state.details.replaceChildren(...rows.map(([label, value]) => {
        const row = document.createElement('div');
        row.className = 'telemetry-detail-row';
        const key = document.createElement('span');
        key.textContent = label;
        const val = document.createElement('span');
        val.textContent = value;
        row.appendChild(key);
        row.appendChild(val);
        return row;
    }));
}

function escapeMarkdownTableCell(value) {
    return String(value ?? '')
        .replace(/\\/g, '\\\\')
        .replace(/\|/g, '\\|')
        .replace(/\r?\n/g, ' ');
}

function getTelemetryMarkdown(summary) {
    const rows = telemetrySummaryRows(summary);
    if (!rows.length) return '';
    return [
        '### Details',
        '',
        '| Metric | Value |',
        '| --- | ---: |',
        ...rows.map(([label, value]) =>
            `| ${escapeMarkdownTableCell(label)} | ${escapeMarkdownTableCell(value)} |`
        )
    ].join('\n');
}

function telemetryMarkdownForContextTarget(target) {
    const panel = target?.closest?.('.request-telemetry');
    if (!panel) return '';
    const state = telemetryPanelStates.get(panel);
    return getTelemetryMarkdown(state?.summary || null);
}

function applyTelemetryProgress(message, payload, token) {
    if (!message || token !== runToken) return;
    const existingState = message.telemetry;
    if (existingState?.finished) return;
    const progress = payload?.progress;
    if (!progress || typeof progress !== 'object') return;
    const state = ensureTelemetry(message, token);
    state.lastProgress = progress;
    state.elapsed.textContent = formatDuration(progress.elapsed_ms);

    switch (progress.kind) {
        case 'phase':
            state.phase.textContent = progress.label || 'Working';
            state.detail.textContent = progress.round
                ? `Execution round ${progress.round}`
                : 'Working…';
            setTelemetryIndeterminate(state);
            break;
        case 'model_call_start':
            state.phase.textContent = progress.role === 'planner' ? 'Planning' : 'Model processing';
            state.detail.textContent = progress.role === 'planner'
                ? `Model call ${progress.call_index} · planner`
                : `Model call ${progress.call_index}${progress.round ? ` · round ${progress.round}` : ''}`;
            setTelemetryIndeterminate(state);
            break;
        case 'prompt_progress': {
            const percent = Number(progress.percent);
            state.phase.textContent = progress.role === 'planner' ? 'Planning · prompt' : 'Prompt processing';
            if (Number.isFinite(percent)) setTelemetryProgress(state, percent);
            const total = formatTokenCount(progress.total);
            const processed = formatTokenCount(progress.processed);
            const cached = formatTokenCount(progress.cache);
            state.detail.textContent = `${processed} / ${total} prompt tokens · ${Number.isFinite(percent) ? `${percent.toFixed(1)}%` : 'processing'} · cached ${cached}`;
            break;
        }
        case 'generation_start':
            state.phase.textContent = progress.role === 'planner' ? 'Planning · generating' : 'Generating';
            state.detail.textContent = progress.role === 'planner'
                ? 'Generating tool plan…'
                : `Model call ${progress.call_index}${progress.round ? ` · round ${progress.round}` : ''}`;
            setTelemetryIndeterminate(state);
            break;
        case 'tool_start':
            state.phase.textContent = 'Resolve tool';
            state.detail.textContent = `${progress.tool_name || 'Tool'}${progress.round_total > 1 ? ` · ${progress.round_position}/${progress.round_total} this round` : ''}`;
            setTelemetryIndeterminate(state);
            break;
        case 'tool_complete':
            state.phase.textContent = 'Resolve tool complete';
            state.detail.textContent = progress.tool_name || 'Tool completed';
            setTelemetryIndeterminate(state);
            break;
        case 'model_call_complete':
            state.summary = progress.summary || state.summary;
            if (state.summary) renderTelemetryDetails(state, state.summary);
            break;
        case 'complete':
            state.summary = progress.summary || state.summary;
            break;
        default:
            break;
    }
    scrollConversationToLatest();
}

function finishTelemetry(message, summary, status = 'completed') {
    const state = message?.telemetry;
    if (!state) return;
    state.finished = true;
    if (state.timer) {
        clearInterval(state.timer);
        state.timer = null;
    }
    state.panel.classList.remove('active');
    state.panel.classList.add(status);
    state.summary = summary || state.summary;
    if (status === 'completed' && state.summary && message.entry) {
        message.entry.telemetry = { ...state.summary };
    }
    const elapsedMs = state.summary?.elapsed_ms ?? (performance.now() - state.startedAt);
    state.elapsed.textContent = formatDuration(elapsedMs);
    state.track.classList.remove('indeterminate');
    state.fill.style.width = status === 'completed' ? '100%' : '0%';

    if (status === 'completed' && state.summary) {
        state.phase.textContent = 'Completed';
        state.detail.textContent = `${formatDuration(state.summary.elapsed_ms)} · ${formatTokenCount(state.summary.total_tokens)} tokens · ${state.summary.model_calls ?? 0} model calls · ${state.summary.tool_calls ?? 0} tools`;
        renderTelemetryDetails(state, state.summary);
        state.toggle.hidden = false;
    } else if (status === 'replaced') {
        state.phase.textContent = 'Replaced';
        state.detail.textContent = `Response replaced after ${formatDuration(elapsedMs)}`;
        state.toggle.hidden = true;
    } else if (status === 'stopped') {
        state.phase.textContent = 'Stopped';
        state.detail.textContent = `Stopped after ${formatDuration(elapsedMs)}`;
        state.toggle.hidden = true;
    } else {
        state.phase.textContent = 'Error';
        state.detail.textContent = `Ended after ${formatDuration(elapsedMs)}`;
        state.toggle.hidden = true;
    }

    scrollConversationToLatest();
}

function getConversationMarkdown() {
    return conversationHistory
        .map((entry) => {
            const speaker = entry.role === 'user' ? 'You' : 'AI Director';
            return `${speaker}\n\n${entry.text}`;
        })
        .join('\n\n');
}

function hasConversationSelection() {
    const selection = window.getSelection();
    return Boolean(selection && selection.toString());
}

function setProcessing(value) {
    isProcessing = value;

    // The composer intentionally stays writable during inference. This is what
    // makes the Follow up flow useful: Enter with non-empty text replaces the
    // current request; Enter with an empty field stops it.
    prompt.disabled = updateBusy && !value;
    prompt.placeholder = value
        ? 'Follow up...'
        : 'Type a DaVinci Resolve instruction...';

    send.textContent = value ? 'Stop' : 'Send';
    send.classList.toggle('stop', value);
    send.setAttribute('aria-label', value ? 'Stop current response' : 'Send instruction');
    send.title = value ? 'Stop the current response' : 'Send instruction';
    updatesButton.disabled = value || updateBusy || settingsRuntimeBusy;
    profileSelect.disabled = value || updateBusy || !profileSwitchAllowed || serverActionInFlight || debugActionInFlight || profileActionInFlight;
    checkUpdatesButton.disabled = value || updateBusy;
    installLlama.disabled = value || updateBusy || !(latestUpdateResult?.llama?.updateAvailable && latestUpdateResult?.llama?.installAvailable);
    installMcp.disabled = value || updateBusy || !resolveReadyForMcpUpdate || !(latestUpdateResult?.mcp?.updateAvailable && latestUpdateResult?.mcp?.installAvailable);
    syncComposerAvailability();
}

function isUserStopResponse(response) {
    return Boolean(response?.stopped);
}

function isUserStopError(error) {
    return error?.message === 'VFX request stopped by user.';
}

async function executePrompt(text, token, responseMessage) {
    try {
        await refreshBackendStatus();

        const response = await window.aiDirector.chat(text, String(token));

        if (token !== runToken) return;

        if (isUserStopResponse(response)) {
            updateAssistantPlainMessage(
                responseMessage,
                'Response stopped by user.'
            );
            finishTelemetry(responseMessage, null, 'stopped');
            return;
        }

        if (!response || !response.ok) {
            throw new Error(
                response?.error || 'VFX backend request failed.'
            );
        }

        const result = response.result;
        updateAssistantMessage(
            responseMessage,
            result?.final_message ||
            'The backend returned no final message.'
        );
        finishTelemetry(responseMessage, result?.telemetry || null, 'completed');

        await refreshResolveStatus();
        await refreshBackendStatus();
    } catch (error) {
        if (token !== runToken) return;

        if (isUserStopError(error)) {
            updateAssistantPlainMessage(
                responseMessage,
                'Response stopped by user.'
            );
            finishTelemetry(responseMessage, null, 'stopped');
            return;
        }

        updateAssistantPlainMessage(
            responseMessage,
            `Backend error: ${error?.message || String(error)}`
        );
        finishTelemetry(responseMessage, null, 'error');
        await refreshBackendStatus();
    } finally {
        if (token !== runToken) return;

        activeResponse = null;
        setProcessing(false);
        prompt.focus();
        await refreshServerStatus();
    }
}

async function submitPrompt() {
    const text = prompt.value.trim();
    if (!isProcessing && !backendReadyForChat) {
        return;
    }
    if (!text) {
        if (isProcessing) {
            await stopPrompt();
        }
        return;
    }

    if (isProcessing) {
        return replacePrompt(text);
    }

    const token = ++runToken;
    prompt.value = '';

    addMessage('user', text);
    const responseMessage = addMessage('assistant', 'Working...');
    activeResponse = responseMessage;
    ensureTelemetry(responseMessage, token);

    setProcessing(true);
    await executePrompt(text, token, responseMessage);
}

async function replacePrompt(text) {
    if (!isProcessing) {
        return submitPrompt();
    }

    const token = ++runToken;
    const previousResponse = activeResponse;

    if (previousResponse) {
        updateAssistantPlainMessage(previousResponse, 'Response replaced.');
        finishTelemetry(previousResponse, null, 'replaced');
    }

    prompt.value = '';
    addMessage('user', text);
    const responseMessage = addMessage('assistant', 'Working...');
    activeResponse = responseMessage;
    ensureTelemetry(responseMessage, token);

    setProcessing(true);

    try {
        const stopResult = await window.aiDirector.stopChat({ restart: true, reason: 'replaced' });

        if (token !== runToken) return;

        if (!stopResult?.ok) {
            throw new Error(
                stopResult?.error ||
                'Could not replace the active VFX request.'
            );
        }

        await executePrompt(text, token, responseMessage);
    } catch (error) {
        if (token !== runToken) return;

        updateAssistantPlainMessage(
            responseMessage,
            `Backend error: ${error?.message || String(error)}`
        );
        finishTelemetry(responseMessage, null, 'error');
        activeResponse = null;
        setProcessing(false);
        prompt.focus();
        await refreshServerStatus();
    }
}

async function stopPrompt() {
    if (!isProcessing) return;

    runToken += 1;

    const stoppedResponse = activeResponse;
    if (stoppedResponse) {
        updateAssistantPlainMessage(
            stoppedResponse,
            'Response stopped by user.'
        );
        finishTelemetry(stoppedResponse, null, 'stopped');
    }

    activeResponse = null;
    send.disabled = true;
    send.textContent = 'Stopping...';

    try {
        await window.aiDirector.stopChat({ restart: true, reason: 'stopped' });
    } catch (error) {
        console.error('[AI Director] Stop failed:', error);
    } finally {
        setProcessing(false);
        prompt.focus();
        await refreshServerStatus();
        await refreshBackendStatus();
    }
}

async function changeServerProfile() {
    if (profileActionInFlight || updateBusy || !profileSwitchAllowed || isProcessing || serverActionInFlight || debugActionInFlight) {
        await refreshServerStatus();
        return;
    }

    profileActionInFlight = true;
    profileSelect.disabled = true;

    try {
        const next = profileSelect.value;
        const result = await window.aiDirector.setServerProfile(next);

        if (!result?.ok) {
            throw new Error(result?.error || 'Could not change server profile.');
        }
    } catch (error) {
        console.error('[AI Director] Server profile change failed:', error);
    } finally {
        profileActionInFlight = false;
        settingsState = await window.aiDirector.getSettingsState();
        await refreshServerStatus();
        await refreshBackendStatus();
    }
}

async function toggleDebug() {
    if (debugActionInFlight || updateBusy || settingsRuntimeBusy || isProcessing || serverActionInFlight || profileActionInFlight) return;

    debugActionInFlight = true;
    applyDebugStatus({ debug: debugToggle.getAttribute('aria-pressed') === 'true' }, { transitional: true });

    try {
        const status = await window.aiDirector.getServerStatus();
        const next = !(status?.debug === true);
        const result = await window.aiDirector.setDebugMode(next);

        if (!result?.ok) {
            throw new Error(result?.error || 'Could not change DEBUG mode.');
        }
    } catch (error) {
        console.error('[AI Director] DEBUG toggle failed:', error);
    } finally {
        debugActionInFlight = false;
        await refreshServerStatus();
        await refreshBackendStatus();
    }
}

async function toggleServer() {
    if (serverActionInFlight || profileActionInFlight) return;

    serverActionInFlight = true;
    serverToggle.disabled = true;

    try {
        const status = await window.aiDirector.getServerStatus();

        if (status?.state === 'connected') {
            if (status.ownership === 'external') {
                return;
            }
            applyServerStatus({ state: 'starting' });
            await window.aiDirector.stopServer();
        } else {
            applyServerStatus({ state: 'starting' });
            await window.aiDirector.startServer();
        }
    } catch (error) {
        applyServerStatus({
            state: 'error',
            error: error?.message || String(error)
        });
    } finally {
        serverActionInFlight = false;
        await refreshServerStatus();
        await refreshBackendStatus();
    }
}

settingsButton.addEventListener('click', () => openSettingsDialog());
settingsProfileUpstream.addEventListener('click', () => setSettingsProfile('upstream'));
settingsProfileDirect.addEventListener('click', () => setSettingsProfile('direct'));
settingsSkinOptions.forEach((button) => {
    button.addEventListener('click', () => { void setSettingsSkin(button.dataset.skin); });
});
settingsModelSelect.addEventListener('change', () => setSettingsModel(settingsModelSelect.value));
settingsModelRefresh.addEventListener('click', async () => {
    if (settingsActionInFlight || settingsRuntimeBusy || isProcessing) return;
    const previousSelection = settingsDraftModel;
    settingsModelRefresh.disabled = true;
    settingsModelDiscovery.textContent = 'Scanning LM Studio models...';
    try {
        settingsState = await window.aiDirector.rescanModels();
        settingsRuntimeBusy = Boolean(settingsState?.runtimeBusy || settingsState?.busy);
        renderModelOptions(previousSelection);
        const discovery = settingsState?.modelDiscovery;
        settingsModelDiscovery.textContent = discovery
            ? `${discovery.source} | ${discovery.discoveredCount ?? 0} selectable GGUFs`
            : 'LM Studio model discovery completed.';
        updateSettingsImpact();
    } catch (error) {
        settingsModelDiscovery.textContent = error?.message || String(error);
    } finally {
        settingsModelRefresh.disabled = settingsActionInFlight || settingsRuntimeBusy;
    }
});

settingsFfmpegGet.addEventListener('click', async () => {
    if (settingsActionInFlight || ffmpegActionInFlight) return;
    ffmpegActionInFlight = true;
    renderFfmpegDraft();
    try {
        const result = await window.aiDirector.openRecommendedFfmpeg();
        if (!result?.ok) throw new Error(result?.error || 'Could not open the recommended FFmpeg provider page.');
        settingsFfmpegHelp.textContent = 'Opened the recommended Windows FFmpeg provider page. Download/install it yourself, then use Locate Existing; AI Director does not download it.';
    } catch (error) {
        settingsFfmpegHelp.textContent = error?.message || String(error);
    } finally {
        ffmpegActionInFlight = false;
        renderFfmpegDraft();
    }
});

settingsFfmpegLocate.addEventListener('click', async () => {
    if (settingsActionInFlight || ffmpegActionInFlight) return;
    ffmpegActionInFlight = true;
    let failureMessage = null;
    renderFfmpegDraft();
    settingsFfmpegSummary.textContent = 'Validating selected FFmpeg…';
    settingsFfmpegHelp.textContent = 'Checking ffmpeg.exe, sibling ffprobe.exe, versions, hashes and the current AI Director capability baseline.';
    try {
        const result = await window.aiDirector.locateExternalFfmpeg();
        if (result?.canceled) return;
        if (!result?.ok) throw new Error(result?.error || 'The selected FFmpeg pair could not be validated.');
        settingsDraftFfmpeg = normalizeFfmpegDraft(result.config);
        settingsDraftFfmpegStatus = result.status || null;
        updateSettingsImpact();
    } catch (error) {
        failureMessage = error?.message || String(error);
    } finally {
        ffmpegActionInFlight = false;
        renderFfmpegDraft();
        if (failureMessage) {
            settingsFfmpegSummary.textContent = 'External FFmpeg was not accepted';
            settingsFfmpegHelp.textContent = failureMessage;
        }
        updateSettingsApplyState();
    }
});

settingsFfmpegDisable.addEventListener('click', () => {
    if (settingsActionInFlight || ffmpegActionInFlight) return;
    settingsDraftFfmpeg = { mode: 'disabled', ffmpegPath: null, ffprobePath: null };
    settingsDraftFfmpegStatus = { state: 'disabled', available: false };
    renderFfmpegDraft();
    updateSettingsImpact();
});

ensureAdvancedRuntimeControls();

[
    settingsContextLength,
    settingsMaxOutput,
    settingsTimeoutHours,
    settingsPrimeCache,
    settingsGpuLayers,
    settingsCpuMoeLayers,
    settingsKvCacheType,
    settingsKvCacheDefault,
    settingsFlashAttention,
    settingsFlashAttentionDefault,
    settingsThreads,
    settingsBatchThreads,
    settingsBatchSize,
    settingsMicroBatchSize
].forEach((control) => {
    control.addEventListener('input', () => {
        syncKvFlashControls();
        updateSettingsImpact();
    });
    control.addEventListener('change', () => {
        syncKvFlashControls();
        updateSettingsImpact();
    });
});
settingsResetTuning.addEventListener('click', () => {
    if (settingsActionInFlight) return;
    settingsGpuLayers.value = '';
    settingsCpuMoeLayers.value = '';
    settingsKvCacheDefault.checked = true;
    settingsKvCacheType.value = 'q8_0';
    settingsFlashAttentionDefault.checked = true;
    settingsFlashAttention.value = 'on';
    settingsThreads.value = '';
    settingsBatchThreads.value = '';
    settingsBatchSize.value = '';
    settingsMicroBatchSize.value = '';
    syncModelRecipeHints();
    updateSettingsImpact();
});
applySettingsButton.addEventListener('click', applySettingsFromDialog);
cancelSettings.addEventListener('click', () => {
    if (!settingsFirstRun) {
        settingsDialog.close();
    }
});
closeSettings.addEventListener('click', () => {
    if (!settingsFirstRun) {
        settingsDialog.close();
    }
});
settingsDialog.addEventListener('cancel', (event) => {
    if (settingsFirstRun) {
        event.preventDefault();
        return;
    }
});

send.addEventListener('click', () => {
    if (isProcessing) {
        stopPrompt();
    } else {
        submitPrompt();
    }
});

profileSelect.addEventListener('change', changeServerProfile);
serverToggle.addEventListener('click', toggleServer);
debugToggle.addEventListener('click', toggleDebug);

prompt.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();

        if (isProcessing && prompt.value.trim()) {
            replacePrompt(prompt.value.trim());
            return;
        }

        submitPrompt();
    }
});

prompt.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    prompt.focus();
    window.aiDirector.showInputContextMenu();
});

conversation.addEventListener('contextmenu', (event) => {
    event.preventDefault();
    const telemetryMarkdown = telemetryMarkdownForContextTarget(event.target);
    window.aiDirector.showChatContextMenu(
        getConversationMarkdown(),
        {
            hasSelection: hasConversationSelection(),
            processing: isProcessing,
            canClear: conversationHistory.length > 0,
            telemetryMarkdown
        }
    );
});

contextMeter?.addEventListener('click', () => {
    contextMeterExpanded = !contextMeterExpanded;
    renderContextMeter();
});

updatesButton.addEventListener('click', openUpdateDialog);
closeUpdates.addEventListener('click', () => {
    if (!updateBusy) updateDialog.close();
});
updateDialog.addEventListener('cancel', (event) => {
    if (updateBusy) event.preventDefault();
});
checkUpdatesButton.addEventListener('click', checkForUpdates);
installLlama.addEventListener('click', () => installComponent('llama'));
installMcp.addEventListener('click', () => installComponent('mcp'));

window.aiDirector.onChatClear(async () => {
    try {
        await window.aiDirector.clearSession({ keepActive: isProcessing });
    } catch (error) {
        console.error('[AI Director] Session clear failed:', error);
    }
    clearChat();
});

window.aiDirector.onUpdateStatus((status) => {
    applyUpdateProgress(status);
});

window.aiDirector.onChatProgress((payload) => {
    const clientRequestId = String(payload?.clientRequestId || '');
    if (!clientRequestId || clientRequestId !== String(runToken)) return;
    if (!isProcessing || !activeResponse) return;
    applyTelemetryProgress(activeResponse, payload, runToken);
});

window.aiDirector.onContextStatus((status) => {
    applyContextMeterStatus(status);
});

window.aiDirector.onResolveStatus((status) => {
    applyResolveStatus(status);
});

window.aiDirector.onBackendStatus((status) => {
    applyBackendStatus(status);
    updateSettingsOperationStatus('backend', status);
    if (settingsDialog.open && typeof status?.runtimeBusy === 'boolean') {
        updateSettingsRuntimeGate(
            status.runtimeBusy,
            typeof status?.settingsApplyBlocked === 'boolean'
                ? status.settingsApplyBlocked
                : status.runtimeBusy
        );
    }
});

window.aiDirector.onServerStatus((status) => {
    applyServerStatus(status);
    updateSettingsOperationStatus('server', status);
    if (settingsDialog.open && typeof status?.runtimeBusy === 'boolean') {
        updateSettingsRuntimeGate(
            status.runtimeBusy,
            typeof status?.settingsApplyBlocked === 'boolean'
                ? status.settingsApplyBlocked
                : status.runtimeBusy
        );
    }
});

async function initialize() {
    modelStatus.textContent = 'Detecting model...';

    settingsState = await window.aiDirector.getSettingsState();
    applySkin(settingsState?.settings?.appearance?.skin || settingsState?.defaults?.appearance?.skin || 'green');
    settingsRuntimeBusy = Boolean(settingsState?.runtimeBusy || settingsState?.busy);
    settingsApplyBlocked = Boolean(
        settingsState?.settingsApplyBlocked ?? settingsState?.runtimeBusy ?? settingsState?.busy
    );
    try {
        applyContextMeterStatus(await window.aiDirector.getContextStatus());
    } catch (error) {
        console.error('[AI Director] Context status initialization failed:', error);
        renderContextMeter();
    }
    await refreshResolveStatus();
    await refreshBackendStatus();
    await refreshServerStatus();
    const updateStatus = await window.aiDirector.getUpdateStatus();
    applyUpdateProgress(updateStatus);

    if (settingsState?.setupRequired) {
        await openSettingsDialog({ firstRun: true });
    }
}

initialize();

setInterval(refreshResolveStatus, 1500);
setInterval(refreshBackendStatus, 1000);
setInterval(refreshServerStatus, 1000);
