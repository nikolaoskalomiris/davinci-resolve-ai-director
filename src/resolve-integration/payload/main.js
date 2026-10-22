const { app, dialog } = require('electron');
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const PLUGIN_ID = 'com.aidirector.davinciresolve';
const PRODUCT_NAME = 'DaVinci Resolve AI Director';
const PRODUCT_EXE = 'DaVinci Resolve AI Director.exe';
const LAUNCHED_FROM = 'resolve-workflow-integration';

function fail(message) {
    console.error(`[${PLUGIN_ID}] ${message}`);
    try {
        dialog.showErrorBox(`${PRODUCT_NAME} Resolve Integration`, message);
    } catch (_) {}
}

function resolveInstalledTarget() {
    const localAppData = String(process.env.LOCALAPPDATA || '').trim();
    if (!localAppData) {
        throw new Error('LOCALAPPDATA is unavailable. Install AI Director for the current Windows user and try again.');
    }

    const appRoot = path.join(localAppData, 'Programs', PRODUCT_NAME);
    const executable = path.join(appRoot, PRODUCT_EXE);
    if (!fs.existsSync(executable)) {
        throw new Error(`Standalone AI Director is not installed for this Windows user: ${executable}`);
    }
    const stat = fs.statSync(executable);
    if (!stat.isFile()) {
        throw new Error(`Standalone AI Director target is not a file: ${executable}`);
    }
    return { appRoot, executable };
}

function buildStandaloneEnvironment() {
    const env = { ...process.env };
    const exactStrip = new Set([
        'ELECTRON_RUN_AS_NODE',
        'ELECTRON_ENABLE_LOGGING',
        'ELECTRON_ENABLE_STACK_DUMPING',
        'NODE_OPTIONS',
        'NODE_PATH',
        'RESOLVE_SCRIPT_API',
        'RESOLVE_SCRIPT_LIB',
        'RESOLVE_SCRIPT_HOST',
        'PYTHONHOME',
        'PYTHONPATH',
        'PYTHONSTARTUP',
        'VIRTUAL_ENV',
        'CONDA_PREFIX',
        'CONDA_DEFAULT_ENV',
        'CUDA_PATH',
        'CUDA_HOME',
        'CUDATOOLKIT_ROOT'
    ]);

    for (const key of Object.keys(env)) {
        const normalized = key.toUpperCase();
        if (exactStrip.has(normalized) || normalized.startsWith('CUDA_PATH_V')) {
            delete env[key];
        }
    }

    env.DAVINCI_RESOLVE_AI_DIRECTOR_HOST_MODE = 'standalone';
    env.DAVINCI_RESOLVE_AI_DIRECTOR_LAUNCHED_FROM = LAUNCHED_FROM;
    return env;
}

function launchStandalone(target) {
    const child = spawn(target.executable, [], {
        cwd: target.appRoot,
        detached: true,
        windowsHide: false,
        stdio: 'ignore',
        env: buildStandaloneEnvironment()
    });
    child.unref();
    console.error(`[${PLUGIN_ID}] launched standalone AI Director pid=${child.pid}`);
}

app.whenReady().then(() => {
    try {
        launchStandalone(resolveInstalledTarget());
    } catch (error) {
        fail(error instanceof Error ? error.message : String(error));
    } finally {
        app.quit();
    }
});
