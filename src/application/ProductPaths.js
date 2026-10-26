const path = require('path');
const os = require('os');

function firstNonEmpty(...values) {
    for (const value of values) {
        if (typeof value === 'string' && value.trim()) return value.trim();
    }
    return null;
}

function defaultVendorRoot() {
    if (process.platform === 'win32') {
        const localAppData = firstNonEmpty(
            process.env.LOCALAPPDATA,
            path.join(os.homedir(), 'AppData', 'Local')
        );
        return path.join(localAppData, 'AIDirector');
    }
    return path.join(os.homedir(), '.local', 'share', 'AIDirector');
}

const vendorRoot = firstNonEmpty(
    process.env.AI_DIRECTOR_HOME,
    defaultVendorRoot()
);

const commonRoot = path.join(vendorRoot, 'Common');
const resolveRoot = path.join(vendorRoot, 'DaVinciResolve');
const backendRoot = path.join(resolveRoot, 'Backend');
const resolveRuntimeRoot = path.join(resolveRoot, 'Runtime');
const llamaRoot = path.join(resolveRuntimeRoot, 'Llama');
const resolveMcpRoot = firstNonEmpty(
    process.env.DAVINCI_RESOLVE_MCP_ROOT,
    process.platform === 'win32'
        ? path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'davinci-resolve-mcp')
        : process.platform === 'darwin'
            ? path.join(os.homedir(), 'Library', 'Application Support', 'davinci-resolve-mcp')
            : path.join(os.homedir(), '.local', 'share', 'davinci-resolve-mcp')
);
const resolveMcpPythonVersion = '3.11.9';
const resolveMcpPythonRoot = path.join(resolveRuntimeRoot, 'Python', 'MCP', resolveMcpPythonVersion);
const resolveNodeVersion = '24.18.0';
const resolveNodeRoot = path.join(resolveRuntimeRoot, 'Node', resolveNodeVersion);
const resolveMcpAdvancedRuntimeDefaultVersion = '4.8.20';
const resolveMcpAdvancedRuntimeBaseRoot = path.join(
    resolveRuntimeRoot,
    'MCP',
    'Advanced'
);

function resolveMcpAdvancedRuntimeRootForVersion(version) {
    const normalized = String(version || '').trim().replace(/^v/i, '');
    if (!/^\d+\.\d+\.\d+$/.test(normalized)) {
        throw new Error(`Invalid managed MCP Advanced runtime version: ${version || 'missing'}`);
    }
    return path.join(resolveMcpAdvancedRuntimeBaseRoot, normalized);
}

const resolveMcpAdvancedRuntimeVersion = resolveMcpAdvancedRuntimeDefaultVersion;
const resolveMcpAdvancedRuntimeRoot = resolveMcpAdvancedRuntimeRootForVersion(
    resolveMcpAdvancedRuntimeVersion
);
const paths = Object.freeze({
    vendorRoot,
    commonRoot,
    commonCudaRoot: path.join(commonRoot, 'Runtime', 'CUDA', '13.3'),
    runtimeStackManaged: true,
    runtimeStackId: 'CUDA13.3.1-Dual-Shared-v2',
    runtimeStackManifest: path.join(resolveRuntimeRoot, 'Stacks', 'CUDA13.3.1-Dual-Shared-v2', 'RUNTIME-STACK-MANIFEST.json'),

    resolveRoot,
    backendRoot,
    resolveHost: path.join(backendRoot, 'ResolveVFXHost.py'),
    resolveRuntime: path.join(backendRoot, 'VFXRuntime.py'),
    resolveCli: path.join(backendRoot, 'StartVFX.py'),
    resolveRuntimeConfig: path.join(backendRoot, 'config', 'vfx_runtime.json'),
    resolvePrompt: path.join(backendRoot, 'prompts', 'VFXDirector.txt'),
    resolveMcpConfig: path.join(resolveRoot, 'MCP', 'vfx_mcp.json'),
    resolveLogsRoot: path.join(resolveRoot, 'Logs'),
    resolveCacheRoot: path.join(resolveRoot, 'Cache'),
    resolveUpdatesRoot: path.join(resolveRoot, 'Updates'),
    resolveManifestsRoot: path.join(resolveRoot, 'Manifests'),

    // davinci-resolve-mcp remains separately managed per user. AI Director
    // owns the runtime dependencies and the product MCP config that points to it.
    resolveMcpRoot,
    resolveMcpPythonVersion,
    resolveMcpPythonRoot,
    resolveMcpPythonExecutable: process.platform === 'win32'
        ? path.join(resolveMcpPythonRoot, 'python.exe')
        : path.join(resolveMcpPythonRoot, 'bin', 'python'),

    // Node is product-owned for the advanced/offline MCP surface and updater
    // dependency work. It is not a machine-global prerequisite or Common payload.
    resolveNodeVersion,
    resolveNodeRoot,
    resolveNodeExecutable: process.platform === 'win32'
        ? path.join(resolveNodeRoot, 'node.exe')
        : path.join(resolveNodeRoot, 'bin', 'node'),
    resolveNpmCli: path.join(resolveNodeRoot, 'node_modules', 'npm', 'bin', 'npm-cli.js'),

    // Advanced MCP native dependencies are product-owned and version-bound to
    // the managed MCP source contract. End users do not build these modules.
    resolveMcpAdvancedRuntimeVersion,
    resolveMcpAdvancedRuntimeRoot,
    resolveMcpAdvancedRuntimeBaseRoot,
    resolveMcpAdvancedRuntimeRootForVersion,

    directRoot: path.join(llamaRoot, 'Stacks', 'CUDA13.3.1-Dual-Shared-v2', 'Direct', 'c8f321699'),

    // Upstream remains updater-owned inside the active runtime-stack boundary.
    // The updater may replace only Current after local GPU and stack compatibility validation.
    upstreamRoot: path.join(llamaRoot, 'Stacks', 'CUDA13.3.1-Dual-Shared-v2', 'Upstream', 'Current'),

    // Python 3.11.9 is a fixed AI Director runtime contract for this product.
    resolvePythonVersion: '3.11.9',
    resolvePythonRoot: path.join(resolveRuntimeRoot, 'Python', '3.11.9'),
    resolvePythonExecutable: path.join(resolveRuntimeRoot, 'Python', '3.11.9', 'python.exe')
});

module.exports = paths;
