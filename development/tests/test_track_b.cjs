'use strict';
// Synthetic regression only: no Electron, real credentials, model files or API requests.
const fs = require('fs'), path = require('path'), os = require('os');
const assert = require('assert/strict'), vm = require('vm'), crypto = require('crypto');
const root = path.resolve(__dirname, '../..');
const app = path.join(root, 'src/application');
const Internet = require(path.join(app, 'InternetCapability.js'));
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'aid-track-b-test-'));
let checks = 0;
function check(fn) { fn(); checks++; }
try {
    const base = path.join(temp, 'base.json');
    const server = () => ({ command: 'synthetic-python', args: ['synthetic.py'], env: { BRAVE_API_KEY: 'synthetic-ambient', PRESERVE: 'yes' } });
    fs.writeFileSync(base, JSON.stringify({ mcpServers: { 'davinci-resolve': server(), 'davinci-resolve-full': server(), 'davinci-resolve-advanced': server() } }));
    let available = true;
    const capability = new Internet.Capability({ paths: {
        resolveInternetProviderRoot: path.join(temp, 'missing-provider'),
        resolveNodeExecutable: path.join(temp, 'missing-node'), resolveMcpConfig: base,
        resolveInternetMcpConfig: path.join(temp, 'internet.json')
    }, safeStorage: {
        isEncryptionAvailable: () => available,
        encryptString: value => Buffer.from('fixture-cipher:' + Buffer.from(value).toString('base64')),
        decryptString: data => {
            const value = data.toString();
            if (!value.startsWith('fixture-cipher:')) throw Error('corrupt');
            return Buffer.from(value.slice(15), 'base64').toString();
        }
    }, settingsPath: () => path.join(temp, 'settings.json') });
    check(() => capability.prepare(false));
    check(() => assert.throws(() => capability.prevalidate(true)));
    check(() => assert.equal(capability.status().present, false));
    const synthetic = 'SYNTHETIC-TEST-NOT-A-PROVIDER-KEY';
    check(() => capability.set(synthetic));
    check(() => assert.equal(capability.decrypt(), synthetic));
    check(() => assert.ok(!fs.readFileSync(capability.credentialPath()).includes(Buffer.from(synthetic))));
    check(() => assert.equal(capability.status().present, true));
    available = false;
    check(() => assert.throws(() => capability.decrypt()));
    available = true;
    fs.writeFileSync(capability.credentialPath(), 'corrupt');
    check(() => assert.throws(() => capability.decrypt(), /missing or unusable/));
    check(() => capability.remove());
    check(() => assert.equal(capability.status().present, false));
    check(() => assert.throws(() => capability.set('short')));
    const before = fs.readFileSync(base);
    const config = JSON.parse(capability.buildConfig());
    check(() => assert.deepEqual(fs.readFileSync(base), before));
    for (const name of ['davinci-resolve', 'davinci-resolve-full', 'davinci-resolve-advanced']) {
        check(() => assert.equal(config.mcpServers[name].env.BRAVE_API_KEY, ''));
        check(() => assert.equal(config.mcpServers[name].env.BRAVE_API_KEY_FILE, ''));
        check(() => assert.equal(config.mcpServers[name].env.PRESERVE, 'yes'));
    }
    check(() => assert.equal(config.mcpServers['brave-search'].env.BRAVE_API_KEY, undefined));
    check(() => assert.ok(!JSON.stringify(config).includes(synthetic)));
    const env = { BRAVE_API_KEY: 'fixture', brave_other: 'fixture', OTHER: 'keep' };
    check(() => assert.deepEqual(Internet.scrub(env), { OTHER: 'keep' }));
    const surface = enabled => ({ resolve_tool_count: 445, discovered_tool_count: enabled ? 447 : 445,
        semantic_tool_count: enabled ? 57 : 55, internet_tool_count: enabled ? 2 : 0,
        internet_tools: enabled ? [...Internet.TOOLS] : [], semantic_internet_tools: enabled ? [...Internet.TOOLS] : [] });
    check(() => Internet.verifySurface(surface(false), false));
    check(() => Internet.verifySurface(surface(true), true));
    const wrong = surface(true); wrong.internet_tools = [...wrong.internet_tools, 'unreviewed'];
    check(() => assert.throws(() => Internet.verifySurface(wrong, true)));
    // Exercise real GGUF validation against synthetic headers only.
    const source = fs.readFileSync(path.join(app, 'main.js'), 'utf8');
    const context = { fs, path, crypto, Buffer, console, LM_STUDIO_MODEL_ROOTS: [],
        getSettingsFilePath: () => path.join(temp, 'settings.json'), InternetCapability: Internet };
    vm.createContext(context);
    const start = source.indexOf('function normalizeCatalogPath('), end = source.indexOf('function runLmsListJson(');
    check(() => assert.ok(start >= 0 && end > start));
    vm.runInContext(source.slice(start, end), context);
    const manualStart = source.indexOf('function manualModelRegistryPath('), manualEnd = source.indexOf('async function refreshModelCatalog(');
    check(() => assert.ok(manualStart >= 0 && manualEnd > manualStart));
    vm.runInContext(source.slice(manualStart, manualEnd), context);
    check(() => assert.equal(context.isAuxiliaryGguf('Qwen3.6-Native-MTP-Preserved-Q8_0.gguf'), false));
    check(() => assert.equal(context.isAuxiliaryGguf('mtp-Qwen-shared-Q8_0.gguf'), true));
    check(() => assert.equal(context.isAuxiliaryGguf('mmproj-F16.gguf'), true));
    const model = path.join(temp, 'synthetic-Q8_0.gguf');
    fs.writeFileSync(model, Buffer.from([71, 71, 85, 70, 3, 0, 0, 0]));
    check(() => assert.equal(context.inspectPrimaryModelFile(model), model));
    const split = path.join(temp, 'synthetic-00001-of-00002.gguf'); fs.copyFileSync(model, split);
    check(() => assert.throws(() => context.inspectPrimaryModelFile(split), /missing/));
    fs.copyFileSync(model, path.join(temp, 'synthetic-00002-of-00002.gguf'));
    check(() => assert.equal(context.inspectPrimaryModelFile(split), split));
    fs.writeFileSync(model, 'notgguf!');
    check(() => assert.throws(() => context.inspectPrimaryModelFile(model), /GGUF/));
    console.log(JSON.stringify({ status: 'VERIFIED_SYNTHETIC_ONLY', checks, provider_request: false, real_credentials: false, inference: false }));
} finally { fs.rmSync(temp, { recursive: true, force: true }); }
