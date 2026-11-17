'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const TOOLS = Object.freeze(['brave-search_brave_llm_context', 'brave-search_brave_web_search']);
const RAW_TOOLS = Object.freeze(['brave_llm_context', 'brave_web_search']);
function normalize(value) {
    if (value?.enabled !== undefined && typeof value.enabled !== 'boolean') throw new Error('Internet enabled must be boolean.');
    return { enabled: value?.enabled === true };
}
function scrub(env) {
    for (const key of Object.keys(env)) if (key.toUpperCase().startsWith('BRAVE_')) delete env[key];
    return env;
}
function atomicWrite(file, bytes) {
    fs.mkdirSync(path.dirname(file), { recursive: true });
    const temporary = `${file}.${crypto.randomUUID()}.tmp`;
    try {
        fs.writeFileSync(temporary, bytes, { flag: 'wx', mode: 0o600 });
        fs.renameSync(temporary, file);
    } finally { fs.rmSync(temporary, { force: true }); }
}
function verifySurface(result, enabled) {
    const expected = enabled ? [...TOOLS].sort() : [];
    const exact = (value) => Array.isArray(value) && value.length === expected.length &&
        JSON.stringify([...value].sort()) === JSON.stringify(expected);
    if (!result || result.resolve_tool_count !== 445 ||
        result.discovered_tool_count !== (enabled ? 447 : 445) ||
        result.semantic_tool_count !== (enabled ? 57 : 55) ||
        result.internet_tool_count !== expected.length ||
        !exact(result.internet_tools) || !exact(result.semantic_internet_tools)) {
        throw new Error('Internet transition tool surface did not match the reviewed exact contract.');
    }
}
class Capability {
    constructor({ paths, safeStorage, settingsPath }) {
        this.paths = paths;
        this.safeStorage = safeStorage;
        this.settingsPath = settingsPath;
    }
    credentialPath() { return path.join(path.dirname(this.settingsPath()), 'brave-credential.dpapi'); }
    status() {
        return { present: fs.existsSync(this.credentialPath()), available: this.safeStorage.isEncryptionAvailable() };
    }
    requireEncryption() {
        if (!this.safeStorage.isEncryptionAvailable() ||
            (typeof this.safeStorage.getSelectedStorageBackend === 'function' &&
             this.safeStorage.getSelectedStorageBackend() === 'basic_text')) {
            throw new Error('OS-protected credential storage is unavailable.');
        }
    }
    set(value) {
        this.requireEncryption();
        if (typeof value !== 'string' || value.length < 8 || value.length > 4096 || /[\s\x00-\x1f\x7f]/.test(value)) {
            throw new Error('Invalid credential.');
        }
        atomicWrite(this.credentialPath(), this.safeStorage.encryptString(value));
    }
    remove() { fs.rmSync(this.credentialPath(), { force: true }); }
    decrypt() {
        this.requireEncryption();
        try {
            const result = this.safeStorage.decryptString(fs.readFileSync(this.credentialPath()));
            if (typeof result !== 'string' || result.length < 8 || result.length > 4096 || /[\s\x00-\x1f\x7f]/.test(result)) throw new Error();
            return result;
        } catch (_) { throw new Error('Protected Brave credential is missing or unusable.'); }
    }
    validateProvider() {
        const root = this.paths.resolveInternetProviderRoot;
        const manifestPath = path.join(root, 'PROVIDER-MANIFEST.json');
        const realRoot = fs.realpathSync(root);
        if (fs.lstatSync(root).isSymbolicLink() || fs.lstatSync(manifestPath).isSymbolicLink()) throw new Error('Provider links are forbidden.');
        const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
        if (manifest.schema_version !== 1 || manifest.provider !== 'brave-search' || manifest.version !== '2.1.4' ||
            manifest.source_commit !== '8bcb302657b0f072612c2f3e53182ff17912013c' ||
            manifest.source_tree !== '2c6b964cb59aa51e3b3643325066fbac05f19440' || manifest.entrypoint !== 'dist/index.js' ||
            !Array.isArray(manifest.files) || !manifest.files.length) throw new Error('Unreviewed provider provenance.');
        const inventory = new Map();
        const folded = new Set();
        for (const row of manifest.files) {
            if (!row || typeof row.path !== 'string' || !/^[A-Za-z0-9@_.+\-/]+$/.test(row.path) ||
                row.path.split('/').some((p) => !p || p === '.' || p === '..' || p.endsWith('.')) ||
                row.path === 'PROVIDER-MANIFEST.json' || folded.has(row.path.toLowerCase()) ||
                !Number.isSafeInteger(row.bytes) || row.bytes < 0 || !/^[a-fA-F0-9]{64}$/.test(row.sha256)) {
                throw new Error('Invalid provider inventory.');
            }
            inventory.set(row.path, row); folded.add(row.path.toLowerCase());
        }
        // Bind the complete inventory to the independently rebuilt pinned production tree.
        // Rewriting a manifest beside tampered code cannot authorize a new runtime.
        const canonicalRows = [...inventory.values()].sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0)
            .map((row) => JSON.stringify({ path: row.path, size: row.bytes, sha256: row.sha256.toLowerCase() }) + '\n').join('');
        if (crypto.createHash('sha256').update(canonicalRows, 'utf8').digest('hex') !==
            'f8bd1c72fce849e56737258cd2396b80b227e30adfba00574b485bfdd49ebebe') {
            throw new Error('Provider inventory is not the reviewed reconstruction.');
        }
        let count = 0;
        const walk = (directory) => {
            for (const name of fs.readdirSync(directory)) {
                const file = path.join(directory, name);
                const stat = fs.lstatSync(file);
                if (stat.isSymbolicLink()) throw new Error('Provider links are forbidden.');
                const relative = path.relative(root, file).split(path.sep).join('/');
                if (stat.isDirectory()) { walk(file); continue; }
                if (!stat.isFile()) throw new Error('Provider special files are forbidden.');
                if (relative === 'PROVIDER-MANIFEST.json') continue;
                if (!fs.realpathSync(file).startsWith(realRoot + path.sep)) throw new Error('Provider escaped root.');
                const row = inventory.get(relative);
                if (!row || stat.size !== row.bytes ||
                    crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').toLowerCase() !== row.sha256.toLowerCase()) {
                    throw new Error('Provider file inventory drift.');
                }
                count++;
            }
        };
        walk(root);
        if (count !== inventory.size || !inventory.has('dist/index.js') || !inventory.has('package.json')) throw new Error('Incomplete provider inventory.');
        const pkg = JSON.parse(fs.readFileSync(path.join(root, 'package.json'), 'utf8'));
        if (pkg.version !== '2.1.4') throw new Error('Provider package version mismatch.');
        const node = this.paths.resolveNodeExecutable;
        if (!fs.statSync(node).isFile() || fs.lstatSync(node).isSymbolicLink() ||
            crypto.createHash('sha256').update(fs.readFileSync(node)).digest('hex').toUpperCase() !==
            '9A4EB5F1C29C6A2E93852EAD46B999E284A6A5CA8BAB4D4E241D587D025A52DE') {
            throw new Error('Product Node is missing or its pinned identity changed.');
        }
    }
    buildConfig() {
        const config = JSON.parse(fs.readFileSync(this.paths.resolveMcpConfig, 'utf8'));
        const entries = config.mcpServers;
        const names = ['davinci-resolve', 'davinci-resolve-full', 'davinci-resolve-advanced'];
        if (!entries || JSON.stringify(Object.keys(entries).sort()) !== JSON.stringify(names.sort())) throw new Error('Unreviewed base MCP surface.');
        for (const entry of Object.values(entries)) {
            if (!entry || typeof entry.command !== 'string' || !Array.isArray(entry.args)) throw new Error('Invalid base MCP entry.');
            entry.env = scrub({ ...(entry.env || {}) });
            entry.env.BRAVE_API_KEY = '';
            entry.env.BRAVE_API_KEY_FILE = '';
        }
        entries['brave-search'] = {
            command: this.paths.resolveNodeExecutable,
            args: [path.join(this.paths.resolveInternetProviderRoot, 'dist', 'index.js'), '--transport', 'stdio',
                '--enabled-tools', ...RAW_TOOLS],
            cwd: this.paths.resolveInternetProviderRoot,
            env: { BRAVE_API_KEY_FILE: '', BRAVE_MCP_LOG_LEVEL: 'error',
                BRAVE_MCP_ENABLED_TOOLS: RAW_TOOLS.join(' '), BRAVE_MCP_DISABLED_TOOLS: '' },
            timeout_ms: 120000
        };
        return Buffer.from(JSON.stringify(config, null, 2) + '\n', 'utf8');
    }
    prevalidate(enabled) {
        if (!enabled) return;
        this.validateProvider();
        this.decrypt(); // Verify usability; no plaintext leaves this call.
        this.buildConfig();
    }
    prepare(enabled) {
        if (!enabled) return;
        this.prevalidate(true);
        atomicWrite(this.paths.resolveInternetMcpConfig, this.buildConfig());
    }
    snapshot() {
        return fs.existsSync(this.paths.resolveInternetMcpConfig) ? fs.readFileSync(this.paths.resolveInternetMcpConfig) : null;
    }
    restore(snapshot) {
        if (snapshot === null) fs.rmSync(this.paths.resolveInternetMcpConfig, { force: true });
        else atomicWrite(this.paths.resolveInternetMcpConfig, snapshot);
    }
}
module.exports = { Capability, normalize, scrub, verifySurface, atomicWrite, TOOLS, RAW_TOOLS };
