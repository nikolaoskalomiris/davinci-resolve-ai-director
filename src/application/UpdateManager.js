const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const https = require('https');
const { execFile } = require('child_process');
const ProductPaths = require('./ProductPaths');

const DEFAULT_LLAMA_ROOT = ProductPaths.upstreamRoot;

const DEFAULT_MCP_ROOT = ProductPaths.resolveMcpRoot;

const LLAMA_ROOT = DEFAULT_LLAMA_ROOT;
const LLAMA_EXE = process.platform === 'win32'
    ? path.join(LLAMA_ROOT, 'llama-server.exe')
    : path.join(LLAMA_ROOT, 'llama-server');
const LLAMA_MARKER = path.join(LLAMA_ROOT, 'UNSLOTH_PREBUILT_INFO.json');
const LLAMA_REPO = 'unslothai/llama.cpp';
const LLAMA_RUNTIME_STACK_ID = ProductPaths.runtimeStackId || null;
const LLAMA_RUNTIME_STACK_MANAGED = ProductPaths.runtimeStackManaged === true && Boolean(LLAMA_RUNTIME_STACK_ID);
const LLAMA_RUNTIME_STACK_MANIFEST = ProductPaths.runtimeStackManifest || null;
const LLAMA_STACK_CUDA_RUNTIME_DLLS = Object.freeze([
    'cudart64_13.dll',
    'cublas64_13.dll',
    'cublasLt64_13.dll'
]);
const MCP_REPO = 'samuelgursky/davinci-resolve-mcp';
const MCP_NPM_PACKAGE = 'davinci-resolve-mcp';
const MCP_NPM_REGISTRY = 'https://registry.npmjs.org';
const MCP_VFX_CONFIG = ProductPaths.resolveMcpConfig;
const MCP_PYTHON_ROOT = ProductPaths.resolveMcpPythonRoot;
const MCP_PYTHON_EXE = ProductPaths.resolveMcpPythonExecutable;
const MCP_COMPATIBILITY_ROOT = path.join(ProductPaths.resolveUpdatesRoot, 'MCP', 'Compatibility');
const MCP_BACKUP_ROOT = path.join(ProductPaths.resolveUpdatesRoot, 'MCP', 'Backups');
const MCP_FAILURE_ROOT = path.join(ProductPaths.resolveUpdatesRoot, 'MCP', 'Failures');
const MCP_ACCEPTANCE_CONTRACT_ROOT = path.join(ProductPaths.resolveUpdatesRoot, 'MCP', 'Contracts');
const NODE_EXE = ProductPaths.resolveNodeExecutable;
const NPM_CLI = ProductPaths.resolveNpmCli;
const MCP_MANDATORY_ADVANCED_ROOT = ProductPaths.resolveMcpAdvancedRuntimeRoot;
const UPDATE_WORK_ROOT = path.join(ProductPaths.resolveUpdatesRoot, 'Upstream');
const RESOLVE_SCRIPT_API = process.platform === 'win32'
    ? 'C:\\ProgramData\\Blackmagic Design\\DaVinci Resolve\\Support\\Developer\\Scripting'
    : null;
const RESOLVE_SCRIPT_MODULES = RESOLVE_SCRIPT_API
    ? path.join(RESOLVE_SCRIPT_API, 'Modules')
    : null;
const RESOLVE_SCRIPT_LIB = process.platform === 'win32'
    ? 'C:\\Program Files\\Blackmagic Design\\DaVinci Resolve\\fusionscript.dll'
    : null;

const MCP_COMPATIBILITY_BUNDLES = Object.freeze({
    '4.8.20': Object.freeze({
        filename: 'AI-Director-MCP-4.8.20-Compatibility-Bundle-v1.zip',
        managedMcpVersion: '4.8.20',
        compatibilityManifestFilename: 'MCP-4.8.20-COMPATIBILITY-MANIFEST.json',
        pythonManifestFilename: 'MCP-PYTHON-IMMUTABLE-ARTIFACT-MANIFEST-4.8.20-v1.json',
        sha256: '83B6AE50D37E8B22AC697A046735E7E0BB6226B254F2CC5950047978F2EA51A1',
        compatibilityManifestSha256: 'C0687D714E9F68BEB19018BA3D7DF84817786AF73C98F2FA3A5532F67F1D4DC8',
        sourceSha256: '9ABACA8D6F559136A7516CB44FC23FB7FD9D8409E4B4FD399C6E627C909B7087',
        pythonImageSha256: 'E19635D62460EC5342993BD370AD1C910245A1290898559402FA58F82AD62F56',
        pythonManifestSha256: 'C60DC63EA0C155276EA3E3261569782161DA08440A947DEF1425E4D6ACA6DF70',
        advancedImageSha256: '1B5DF757F5952C78DD16F391A12241F95E581D64DACD128CCAB9C8F90F22DD15',
        advancedTreeSha256: 'BAC9B93C9270009E09436EF6045CA5F4778AB739271B1E64508AC36D35E1459F',
        advancedPackageSha256: '965D534783C98E5D04AFB3A613C2DB7131F7FB8B98C3C7893FA5EA6FA859E079',
        advancedLockSha256: '7A051C3787CA117B884AC93A1C39D5CA5D668B46E375F94C5EFE526DD511F4F1',
        advancedFileCount: 3969,
        sourceCommit: '6337d8cf706852854b601e3ce05d643a9366b905',
        windowsAdvancedGuidanceBaselineSha256: '653E51C16C7DDAC7217F03EBFADA66052383DA0AEEE71EF1579227384F406558',
        windowsAdvancedGuidancePatchedSha256: 'E01116148EA0ECC1583F3484300228CA25AE2DB21321C7EC8499EC3A89D45391',
        distributionCount: 41,
        compoundTools: 37,
        fullTools: 389,
        advancedTools: 18,
        mandatoryAdvancedSharpVersion: '0.35.4',
        mandatoryAdvancedBetterSqlite3Version: '11.10.0',
        mandatoryAdvancedSourceZipSha256: 'CEA9327039879583FCCAD66B8106C76AA537C0651C9615BDBD41FCF98818F882',
        ffmpegVersion: '8.1.3',
        ffmpegReleaseTag: 'autobuild-2026-09-25-15-37',
        ffmpegAsset: 'ffmpeg-n8.1.3-win64-lgpl-shared-8.1.zip',
        ffmpegUpstreamAssetSha256: 'C1E85A57CAB0CF70AE03D7E63599748ED156437B5B66863C62EB4FAC63B08E26',
        ffmpegSourceZipSha256: '4C3A9B10EE86958634C556FAD6DA74B10267748C43264EE846FAF49681668AFF'
    })
});

// Stable dependency/runtime baseline used only as the first gate for future managed MCP releases.
// Dependency equality alone is never sufficient for commit. Every candidate remains version-bound
// to a resolved GitHub commit and must also pass exact model-facing tool contracts, compatible
// granular contracts, read-only Resolve canaries, and the post-swap live health boundary.
const MCP_COMPATIBILITY_CONTRACT = Object.freeze({
    requirementsSha256: '8C5A69A398447A6ECD719256C3ABE351B125CD1D6F6E86A09112E186E073FC57',
    advancedPackageSha256: '965D534783C98E5D04AFB3A613C2DB7131F7FB8B98C3C7893FA5EA6FA859E079',
    advancedLockSha256: '7A051C3787CA117B884AC93A1C39D5CA5D668B46E375F94C5EFE526DD511F4F1',
    windowsAdvancedGuidanceBaselineSha256: '653E51C16C7DDAC7217F03EBFADA66052383DA0AEEE71EF1579227384F406558',
    windowsAdvancedGuidancePatchedSha256: 'E01116148EA0ECC1583F3484300228CA25AE2DB21321C7EC8499EC3A89D45391',
    compoundTools: 37,
    fullTools: 389,
    advancedTools: 18,
    mandatoryAdvancedSharpVersion: '0.35.4',
    mandatoryAdvancedBetterSqlite3Version: '11.10.0'
});

// AI_DIRECTOR_MCP_SEMANTIC_ENGINE_V1_1_BEGIN
// AI Director successor MCP directional semantic compatibility engine v1.1.
// Fail closed whenever the supported subset cannot prove the directional relation.
const MCP_SEMANTIC_ENGINE = (() => {
const PASS = 'PASS';
const FAIL = 'FAIL';
const REVIEW = 'REVIEW';
const ENGINE_ID = 'AI_DIRECTOR_MCP_DIRECTIONAL_SEMANTIC_ENGINE_V1_1';

const DOCUMENTARY_KEYS = new Set(['title', 'description']);
const SUPPORTED_PRIMITIVE_TYPES = new Set(['null', 'boolean', 'object', 'array', 'number', 'integer', 'string']);
const SUPPORTED_SCHEMA_KEYS = new Set([
  '$schema', 'type', 'properties', 'required', 'items', 'additionalProperties',
  'anyOf', 'enum', 'const', 'default', 'title', 'description',
  'minLength', 'maxLength', 'minItems', 'maxItems', 'minimum', 'maximum',
  'exclusiveMinimum', 'exclusiveMaximum'
]);
const ANYOF_NON_SEMANTIC_SIBLINGS = new Set(['anyOf', '$schema', 'default', 'title', 'description']);
const MULTITYPE_NON_STRUCTURAL_KEYS = new Set(['type', 'enum', 'const']);

function rank(status) {
  return status === FAIL ? 2 : status === REVIEW ? 1 : 0;
}

function mergeStatus(a, b) {
  return rank(a) >= rank(b) ? a : b;
}

function addReason(result, status, path, message) {
  result.status = mergeStatus(result.status, status);
  result.reasons.push({ status, path, message });
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function canonicalJson(value) {
  if (Array.isArray(value)) return '[' + value.map(canonicalJson).join(',') + ']';
  if (value && typeof value === 'object') {
    return '{' + Object.keys(value).sort().map((key) => JSON.stringify(key) + ':' + canonicalJson(value[key])).join(',') + '}';
  }
  return JSON.stringify(value);
}

function jsonValueEqual(a, b) {
  return canonicalJson(a) === canonicalJson(b);
}

function validateSupportedSchemaShape(schema, path, result) {
  if (!isPlainObject(schema)) {
    addReason(result, REVIEW, path, 'Schema must be a JSON object.');
    return false;
  }

  let supported = true;
  for (const key of Object.keys(schema)) {
    if (!SUPPORTED_SCHEMA_KEYS.has(key)) {
      addReason(result, REVIEW, `${path}/${key}`, `Unsupported JSON-Schema keyword: ${key}`);
      supported = false;
    }
  }

  if ('$schema' in schema && typeof schema.$schema !== 'string') {
    addReason(result, REVIEW, `${path}/$schema`, 'Schema dialect declaration must be a string.');
    supported = false;
  }

  if ('type' in schema) {
    const raw = schema.type;
    const values = typeof raw === 'string' ? [raw] : Array.isArray(raw) ? raw : null;
    if (!values || values.length === 0 || !values.every((x) => typeof x === 'string' && SUPPORTED_PRIMITIVE_TYPES.has(x))) {
      addReason(result, REVIEW, `${path}/type`, 'Unsupported or malformed JSON-Schema type declaration.');
      supported = false;
    } else if (new Set(values).size !== values.length) {
      addReason(result, REVIEW, `${path}/type`, 'Duplicate entries in a JSON-Schema type array are unsupported.');
      supported = false;
    }
  }

  if ('properties' in schema) {
    if (!isPlainObject(schema.properties)) {
      addReason(result, REVIEW, `${path}/properties`, 'properties must be a JSON object.');
      supported = false;
    } else {
      for (const [name, child] of Object.entries(schema.properties)) {
        if (!validateSupportedSchemaShape(child, `${path}/properties/${name}`, result)) supported = false;
      }
    }
  }

  if ('required' in schema) {
    const required = schema.required;
    if (!Array.isArray(required) || !required.every((x) => typeof x === 'string') || new Set(required).size !== required.length) {
      addReason(result, REVIEW, `${path}/required`, 'required must be an array of unique property-name strings.');
      supported = false;
    }
  }

  if ('items' in schema) {
    if (!isPlainObject(schema.items)) {
      addReason(result, REVIEW, `${path}/items`, 'Only object-form items schemas are supported.');
      supported = false;
    } else if (!validateSupportedSchemaShape(schema.items, `${path}/items`, result)) {
      supported = false;
    }
  }

  if ('additionalProperties' in schema) {
    const ap = schema.additionalProperties;
    if (typeof ap !== 'boolean' && !isPlainObject(ap)) {
      addReason(result, REVIEW, `${path}/additionalProperties`, 'additionalProperties must be boolean or a schema object.');
      supported = false;
    } else if (isPlainObject(ap) && !validateSupportedSchemaShape(ap, `${path}/additionalProperties`, result)) {
      supported = false;
    }
  }

  if ('anyOf' in schema) {
    const branches = schema.anyOf;
    if (!Array.isArray(branches) || branches.length === 0 || !branches.every(isPlainObject)) {
      addReason(result, REVIEW, `${path}/anyOf`, 'anyOf must contain one or more schema objects.');
      supported = false;
    } else {
      branches.forEach((child, i) => {
        if (!validateSupportedSchemaShape(child, `${path}/anyOf/${i}`, result)) supported = false;
      });
    }
  }

  if ('enum' in schema) {
    if (!Array.isArray(schema.enum) || schema.enum.length === 0) {
      addReason(result, REVIEW, `${path}/enum`, 'enum must be a non-empty array.');
      supported = false;
    } else {
      const unique = new Set(schema.enum.map(canonicalJson));
      if (unique.size !== schema.enum.length) {
        addReason(result, REVIEW, `${path}/enum`, 'Duplicate enum values are unsupported.');
        supported = false;
      }
    }
  }

  for (const key of ['minLength', 'maxLength', 'minItems', 'maxItems']) {
    if (!(key in schema)) continue;
    const value = schema[key];
    if (!Number.isInteger(value) || value < 0) {
      addReason(result, REVIEW, `${path}/${key}`, `${key} must be a non-negative integer.`);
      supported = false;
    }
  }
  for (const key of ['minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum']) {
    if (!(key in schema)) continue;
    const value = schema[key];
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      addReason(result, REVIEW, `${path}/${key}`, `${key} must be a finite number.`);
      supported = false;
    }
  }

  if ('minLength' in schema && 'maxLength' in schema && schema.minLength > schema.maxLength) {
    addReason(result, REVIEW, path, 'Contradictory string length bounds are unsupported.');
    supported = false;
  }
  if ('minItems' in schema && 'maxItems' in schema && schema.minItems > schema.maxItems) {
    addReason(result, REVIEW, path, 'Contradictory array length bounds are unsupported.');
    supported = false;
  }
  if ('minimum' in schema && 'maximum' in schema && schema.minimum > schema.maximum) {
    addReason(result, REVIEW, path, 'Contradictory numeric bounds are unsupported.');
    supported = false;
  }
  if ('exclusiveMinimum' in schema && 'exclusiveMaximum' in schema && schema.exclusiveMinimum >= schema.exclusiveMaximum) {
    addReason(result, REVIEW, path, 'Contradictory exclusive numeric bounds are unsupported.');
    supported = false;
  }

  return supported;
}

function primitiveTypes(schema) {
  const t = schema?.type;
  if (typeof t === 'string' && SUPPORTED_PRIMITIVE_TYPES.has(t)) return new Set([t]);
  if (Array.isArray(t) && t.length && t.every((x) => typeof x === 'string' && SUPPORTED_PRIMITIVE_TYPES.has(x))) return new Set(t);
  return null;
}

function typeSubset(subType, supType) {
  if (subType === supType) return true;
  return subType === 'integer' && supType === 'number';
}

function compareNumericBound(sub, sup, key, path, result) {
  if (!(key in sub) && !(key in sup)) return;
  if (key in sup && !(key in sub)) {
    addReason(result, FAIL, `${path}/${key}`, `Subset schema drops required ${key} constraint.`);
    return;
  }
  if (key in sub && !(key in sup)) return;
  const a = sub[key];
  const b = sup[key];
  if (typeof a !== 'number' || !Number.isFinite(a) || typeof b !== 'number' || !Number.isFinite(b)) {
    addReason(result, REVIEW, `${path}/${key}`, `Unsupported non-numeric ${key} value.`);
    return;
  }
  if (['minimum', 'exclusiveMinimum', 'minLength', 'minItems'].includes(key)) {
    if (a < b) addReason(result, FAIL, `${path}/${key}`, `Subset lower bound ${a} is looser than required ${b}.`);
  } else if (a > b) {
    addReason(result, FAIL, `${path}/${key}`, `Subset upper bound ${a} is looser than required ${b}.`);
  }
}

function compareValueSets(sub, sup, path, result) {
  if ('const' in sup) {
    if (!('const' in sub) || !jsonValueEqual(sub.const, sup.const)) {
      addReason(result, FAIL, `${path}/const`, 'Subset does not preserve required const value.');
    }
  }
  if ('enum' in sup) {
    const supValues = sup.enum;
    if (!('enum' in sub)) {
      addReason(result, FAIL, `${path}/enum`, 'Subset removes enum restriction and may emit/accept values outside the required set.');
    } else if (!sub.enum.every((v) => supValues.some((x) => jsonValueEqual(x, v)))) {
      addReason(result, FAIL, `${path}/enum`, 'Subset enum contains values outside required superset.');
    }
  }
}

function additionalSchema(schema) {
  return Object.prototype.hasOwnProperty.call(schema, 'additionalProperties') ? schema.additionalProperties : true;
}

function absorb(result, child) {
  result.status = mergeStatus(result.status, child.status);
  result.reasons.push(...child.reasons);
}

function compareAdditional(subAp, supAp, path, result) {
  if (subAp === false) return;
  if (supAp === true) return;
  if (supAp === false) {
    addReason(result, FAIL, path, 'Subset allows additional properties that superset forbids.');
    return;
  }
  if (subAp === true && isPlainObject(supAp)) {
    addReason(result, FAIL, path, 'Subset allows unconstrained additional properties beyond required schema.');
    return;
  }
  if (isPlainObject(subAp) && isPlainObject(supAp)) {
    absorb(result, compareSchemaSubset(subAp, supAp, path));
    return;
  }
  addReason(result, REVIEW, path, 'Unsupported additionalProperties relationship.');
}

function compareObjectSubset(sub, sup, path, result) {
  const subReqRaw = sub.required ?? [];
  const supReqRaw = sup.required ?? [];
  const subReq = new Set(subReqRaw);
  const supReq = new Set(supReqRaw);
  const missingRequired = [...supReq].filter((x) => !subReq.has(x)).sort();
  if (missingRequired.length) addReason(result, FAIL, `${path}/required`, `Subset permits omission of required properties: ${JSON.stringify(missingRequired)}`);

  const subProps = sub.properties ?? {};
  const supProps = sup.properties ?? {};
  const subAp = additionalSchema(sub);
  const supAp = additionalSchema(sup);

  for (const [name, subSchema] of Object.entries(subProps)) {
    const target = Object.prototype.hasOwnProperty.call(supProps, name) ? supProps[name] : supAp;
    if (target === false) {
      addReason(result, FAIL, `${path}/properties/${name}`, 'Subset permits a property forbidden by superset schema.');
      continue;
    }
    if (target === true) continue;
    absorb(result, compareSchemaSubset(subSchema, target, `${path}/properties/${name}`));
  }

  for (const [name, supSchema] of Object.entries(supProps)) {
    if (Object.prototype.hasOwnProperty.call(subProps, name)) continue;
    if (subAp === false) continue;
    if (subAp === true) {
      if (!jsonValueEqual(supSchema, {})) addReason(result, FAIL, `${path}/properties/${name}`, 'Subset leaves a superset-constrained property unconstrained.');
      continue;
    }
    if (isPlainObject(subAp) && isPlainObject(supSchema)) {
      absorb(result, compareSchemaSubset(subAp, supSchema, `${path}/properties/${name}`));
    } else {
      addReason(result, REVIEW, `${path}/properties/${name}`, 'Unsupported absent-property relationship.');
    }
  }
  compareAdditional(subAp, supAp, `${path}/additionalProperties`, result);
}

function compareArraySubset(sub, sup, path, result) {
  const subItems = sub.items ?? {};
  const supItems = sup.items ?? {};
  absorb(result, compareSchemaSubset(subItems, supItems, `${path}/items`));
  for (const key of ['minItems', 'maxItems']) compareNumericBound(sub, sup, key, path, result);
}

function compareStringSubset(sub, sup, path, result) {
  for (const key of ['minLength', 'maxLength']) compareNumericBound(sub, sup, key, path, result);
}

function compareNumberSubset(sub, sup, path, result) {
  for (const key of ['minimum', 'maximum', 'exclusiveMinimum', 'exclusiveMaximum']) compareNumericBound(sub, sup, key, path, result);
}

function semanticView(schema) {
  const out = {};
  for (const [k, v] of Object.entries(schema)) {
    if (!DOCUMENTARY_KEYS.has(k) && k !== 'default' && k !== '$schema') out[k] = v;
  }
  return out;
}

function hasAnyOfValidationSiblings(schema) {
  return Array.isArray(schema?.anyOf) && Object.keys(schema).some((key) => !ANYOF_NON_SEMANTIC_SIBLINGS.has(key));
}

function hasStructuralConstraints(schema) {
  return Object.keys(schema).some((key) => !DOCUMENTARY_KEYS.has(key) && key !== 'default' && key !== '$schema' && !MULTITYPE_NON_STRUCTURAL_KEYS.has(key));
}

function compareSchemaSubset(sub, sup, path = '$schema') {
  const result = { status: PASS, reasons: [] };
  const subSupported = validateSupportedSchemaShape(sub, `${path}/subset`, result);
  const supSupported = validateSupportedSchemaShape(sup, `${path}/superset`, result);
  if (!subSupported || !supSupported) return result;

  if ('$schema' in sub || '$schema' in sup) {
    if (sub.$schema !== sup.$schema) addReason(result, REVIEW, `${path}/$schema`, 'Schema dialect declaration changed.');
  }
  if (Object.prototype.hasOwnProperty.call(sub, 'default') !== Object.prototype.hasOwnProperty.call(sup, 'default') ||
      (Object.prototype.hasOwnProperty.call(sub, 'default') && !jsonValueEqual(sub.default, sup.default))) {
    addReason(result, REVIEW, `${path}/default`, 'Behavior-changing default mutation requires review.');
  }

  const subV = semanticView(sub);
  const supV = semanticView(sup);
  if (jsonValueEqual(subV, supV)) return result;
  if (Object.keys(supV).length === 0) return result;
  if (Object.keys(subV).length === 0 && Object.keys(supV).length !== 0) {
    addReason(result, FAIL, path, 'Unconstrained subset schema is not contained by constrained superset schema.');
    return result;
  }

  if (hasAnyOfValidationSiblings(subV) || hasAnyOfValidationSiblings(supV)) {
    addReason(result, REVIEW, `${path}/anyOf`, 'Changed anyOf schemas with semantic validation siblings require manual review; sibling conjunction must not be ignored.');
    return result;
  }

  const subBranches = Array.isArray(subV.anyOf) ? subV.anyOf : null;
  const supBranches = Array.isArray(supV.anyOf) ? supV.anyOf : null;
  if (subBranches !== null || supBranches !== null) {
    const sbranches = subBranches ?? [Object.fromEntries(Object.entries(subV).filter(([k]) => k !== 'anyOf'))];
    const pbranches = supBranches ?? [Object.fromEntries(Object.entries(supV).filter(([k]) => k !== 'anyOf'))];
    sbranches.forEach((sb, i) => {
      const branchResults = pbranches.map((pb) => compareSchemaSubset(sb, pb, `${path}/anyOf[${i}]`));
      if (branchResults.some((x) => x.status === PASS)) return;
      if (branchResults.every((x) => x.status === FAIL)) {
        addReason(result, FAIL, `${path}/anyOf[${i}]`, 'A subset union branch is not accepted by any superset branch.');
      } else {
        addReason(result, REVIEW, `${path}/anyOf[${i}]`, 'Union inclusion cannot be proven within engine-v1.1 semantics.');
      }
    });
    return result;
  }

  const subTypes = primitiveTypes(subV);
  const supTypes = primitiveTypes(supV);
  if (!subTypes || !supTypes) {
    addReason(result, REVIEW, `${path}/type`, 'Schemas without a simple explicit type are unsupported outside anyOf/unconstrained forms.');
    return result;
  }
  for (const st of subTypes) {
    if (![...supTypes].some((pt) => typeSubset(st, pt))) addReason(result, FAIL, `${path}/type`, `Type ${JSON.stringify(st)} is not contained by required type(s) ${JSON.stringify([...supTypes].sort())}.`);
  }

  compareValueSets(subV, supV, path, result);
  if (subTypes.size !== 1 || supTypes.size !== 1) {
    if (hasStructuralConstraints(subV) || hasStructuralConstraints(supV)) {
      addReason(result, REVIEW, `${path}/type`, 'Changed schemas involving multiple explicit types and structural constraints require manual review; constraints must not be silently ignored.');
    }
    return result;
  }

  const st = [...subTypes][0];
  const pt = [...supTypes][0];
  if (st === 'object' && pt === 'object') compareObjectSubset(subV, supV, path, result);
  else if (st === 'array' && pt === 'array') compareArraySubset(subV, supV, path, result);
  else if (st === 'string' && pt === 'string') compareStringSubset(subV, supV, path, result);
  else if (['integer', 'number'].includes(st) && ['integer', 'number'].includes(pt)) compareNumberSubset(subV, supV, path, result);
  return result;
}

function annotationChangeStatus(oldValue, newValue, path) {
  const result = { status: PASS, reasons: [] };
  if (jsonValueEqual(oldValue, newValue)) return result;
  if (!isPlainObject(oldValue) || !isPlainObject(newValue)) {
    addReason(result, REVIEW, path, 'Annotation presence/shape changed.');
    return result;
  }
  const weakening = {
    readOnlyHint: [true, false],
    idempotentHint: [true, false],
    destructiveHint: [false, true],
    openWorldHint: [false, true]
  };
  for (const [key, pair] of Object.entries(weakening)) {
    if (oldValue[key] === pair[0] && newValue[key] === pair[1]) addReason(result, FAIL, `${path}/${key}`, `Safety/behavior annotation ${key} weakened: ${pair[0]} -> ${pair[1]}.`);
  }
  if (result.status === PASS) addReason(result, REVIEW, path, 'Annotation changed and requires manual review.');
  return result;
}

function normalizeTool(row) {
  if (!row || typeof row !== 'object') return null;
  const sf = row.semanticFields || row.semantic_fields || row;
  return {
    name: row.name,
    title: sf.title ?? null,
    description: sf.description ?? null,
    inputSchema: sf.inputSchema ?? {},
    outputSchema: sf.outputSchema ?? null,
    annotations: sf.annotations ?? null,
    _meta: sf._meta ?? null
  };
}

function compareToolSets(acceptedTools, candidateTools, { allowAdditions = false, surface = 'tools' } = {}) {
  const result = { engine: ENGINE_ID, status: PASS, reasons: [], toolResults: {}, removed: [], added: [], documentaryChanges: [] };
  const accepted = new Map((acceptedTools || []).map(normalizeTool).filter((x) => x?.name).map((x) => [x.name, x]));
  const candidate = new Map((candidateTools || []).map(normalizeTool).filter((x) => x?.name).map((x) => [x.name, x]));
  result.removed = [...accepted.keys()].filter((x) => !candidate.has(x)).sort();
  result.added = [...candidate.keys()].filter((x) => !accepted.has(x)).sort();
  if (result.removed.length) addReason(result, FAIL, `$${surface}`, `Existing tool(s) removed/renamed: ${JSON.stringify(result.removed)}`);
  if (result.added.length && !allowAdditions) addReason(result, REVIEW, `$${surface}`, `New model-facing tool(s) require review: ${JSON.stringify(result.added)}`);

  for (const name of [...accepted.keys()].filter((x) => candidate.has(x)).sort()) {
    const oldTool = accepted.get(name);
    const newTool = candidate.get(name);
    const tr = { status: PASS, reasons: [] };
    absorb(tr, compareSchemaSubset(oldTool.inputSchema || {}, newTool.inputSchema || {}, `$${surface}/${name}/inputSchema`));
    if (oldTool.outputSchema == null && newTool.outputSchema == null) {
      // no-op
    } else if (oldTool.outputSchema == null && newTool.outputSchema != null) {
      addReason(tr, REVIEW, `$${surface}/${name}/outputSchema`, 'New output contract added where none existed; requires review.');
    } else if (oldTool.outputSchema != null && newTool.outputSchema == null) {
      addReason(tr, FAIL, `$${surface}/${name}/outputSchema`, 'Previously declared output contract was removed.');
    } else {
      absorb(tr, compareSchemaSubset(newTool.outputSchema, oldTool.outputSchema, `$${surface}/${name}/outputSchema`));
    }
    absorb(tr, annotationChangeStatus(oldTool.annotations, newTool.annotations, `$${surface}/${name}/annotations`));
    if (!jsonValueEqual(oldTool._meta, newTool._meta)) addReason(tr, REVIEW, `$${surface}/${name}/_meta`, 'Relevant _meta changed; engine v1.1 requires review.');
    if (!jsonValueEqual(oldTool.title, newTool.title) || !jsonValueEqual(oldTool.description, newTool.description)) {
      result.documentaryChanges.push(name);
    }
    result.toolResults[name] = tr;
    absorb(result, tr);
  }
  return result;
}

function serverInfoWithoutVersion(value) {
  if (value == null) return null;
  if (!isPlainObject(value)) return value;
  const out = {};
  for (const [key, child] of Object.entries(value)) {
    if (key !== 'version') out[key] = child;
  }
  return out;
}

function compareSurface(acceptedSurface, candidateSurface, { allowAdditions = false, surface = 'tools' } = {}) {
  const result = { engine: ENGINE_ID, status: PASS, reasons: [], toolComparison: null };
  const acceptedProtocol = acceptedSurface?.protocolVersion ?? null;
  const candidateProtocol = candidateSurface?.protocolVersion ?? null;
  if (acceptedProtocol !== candidateProtocol) addReason(result, REVIEW, `$${surface}/protocolVersion`, `MCP protocolVersion changed: ${acceptedProtocol ?? 'null'} -> ${candidateProtocol ?? 'null'}.`);
  if (!jsonValueEqual(serverInfoWithoutVersion(acceptedSurface?.serverInfo ?? null), serverInfoWithoutVersion(candidateSurface?.serverInfo ?? null))) {
    addReason(result, REVIEW, `$${surface}/serverInfo`, 'MCP serverInfo changed outside the version field; manual review required.');
  }
  if (!jsonValueEqual(acceptedSurface?.serverCapabilities ?? null, candidateSurface?.serverCapabilities ?? null)) {
    addReason(result, REVIEW, `$${surface}/serverCapabilities`, 'MCP server capabilities changed; manual review required.');
  }
  const toolComparison = compareToolSets(acceptedSurface?.tools || [], candidateSurface?.tools || [], { allowAdditions, surface });
  result.toolComparison = toolComparison;
  absorb(result, toolComparison);
  return result;
}

return Object.freeze({
  ENGINE_ID,
  PASS,
  FAIL,
  REVIEW,
  SUPPORTED_SCHEMA_KEYS: Object.freeze([...SUPPORTED_SCHEMA_KEYS].sort()),
  compareSchemaSubset,
  compareToolSets,
  compareSurface
});

})();
// AI_DIRECTOR_MCP_SEMANTIC_ENGINE_V1_1_END

function execFileAsync(file, args, options = {}) {
    return new Promise((resolve, reject) => {
        execFile(file, args, options, (error, stdout, stderr) => {
            if (error) {
                error.stdout = stdout;
                error.stderr = stderr;
                reject(error);
                return;
            }
            resolve({ stdout: stdout || '', stderr: stderr || '' });
        });
    });
}

async function execProductNpm(args, options = {}) {
    if (!fs.existsSync(NODE_EXE)) {
        throw new Error(`Product-owned Node runtime is missing: ${NODE_EXE}`);
    }
    if (!fs.existsSync(NPM_CLI)) {
        throw new Error(`Product-owned npm CLI is missing: ${NPM_CLI}`);
    }
    return execFileAsync(NODE_EXE, [NPM_CLI, ...args], options);
}

function httpRequest(url, { timeoutMs = 15000, headers = {} } = {}) {
    return new Promise((resolve, reject) => {
        const request = https.get(
            url,
            {
                headers: {
                    'User-Agent': 'DaVinci-Resolve-AI-Director',
                    Accept: 'application/vnd.github+json',
                    ...headers
                }
            },
            (response) => {
                if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
                    response.resume();
                    httpRequest(new URL(response.headers.location, url).toString(), {
                        timeoutMs,
                        headers
                    }).then(resolve, reject);
                    return;
                }

                const chunks = [];
                response.on('data', (chunk) => chunks.push(chunk));
                response.on('end', () => {
                    const body = Buffer.concat(chunks);
                    if (response.statusCode !== 200) {
                        reject(new Error(`HTTP ${response.statusCode} from ${url}: ${body.toString('utf8').slice(0, 500)}`));
                        return;
                    }
                    resolve(body);
                });
            }
        );

        request.setTimeout(timeoutMs, () => {
            request.destroy(new Error(`Request timed out: ${url}`));
        });
        request.on('error', reject);
    });
}

async function getJson(url) {
    const body = await httpRequest(url);
    try {
        return JSON.parse(body.toString('utf8'));
    } catch (error) {
        throw new Error(`GitHub returned invalid JSON for ${url}: ${error.message}`);
    }
}

async function downloadFile(url, destination, onProgress) {
    await fs.promises.mkdir(path.dirname(destination), { recursive: true });

    return new Promise((resolve, reject) => {
        const requestUrl = new URL(url);

        const request = https.get(
            requestUrl,
            {
                headers: {
                    'User-Agent': 'DaVinci-Resolve-AI-Director',
                    Accept: '*/*'
                }
            },
            (response) => {
                if (response.statusCode >= 300 && response.statusCode < 400 && response.headers.location) {
                    response.resume();
                    downloadFile(new URL(response.headers.location, requestUrl).toString(), destination, onProgress)
                        .then(resolve, reject);
                    return;
                }

                if (response.statusCode !== 200) {
                    response.resume();
                    reject(new Error(`HTTP ${response.statusCode} downloading ${url}`));
                    return;
                }

                const total = Number(response.headers['content-length']) || null;
                let received = 0;
                const file = fs.createWriteStream(destination);
                let settled = false;

                const fail = (error) => {
                    if (settled) return;
                    settled = true;
                    file.destroy();
                    try { fs.unlinkSync(destination); } catch (_error) {}
                    reject(error);
                };

                response.on('data', (chunk) => {
                    received += chunk.length;
                    if (typeof onProgress === 'function') {
                        onProgress({ received, total });
                    }
                });

                response.on('error', fail);
                file.on('error', fail);
                file.on('finish', () => {
                    if (settled) return;
                    settled = true;
                    file.close(() => resolve());
                });

                response.pipe(file);
            }
        );

        request.setTimeout(120000, () => {
            request.destroy(new Error(`Download timed out: ${url}`));
        });
        request.on('error', reject);
    });
}

function sha256File(filePath) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha256');
        const stream = fs.createReadStream(filePath);
        stream.on('error', reject);
        stream.on('data', (chunk) => hash.update(chunk));
        stream.on('end', () => resolve(hash.digest('hex')));
    });
}

function sha256Buffer(value) {
    return crypto.createHash('sha256').update(value).digest('hex').toUpperCase();
}


async function sha256Tree(root) {
    const rows = [];

    async function walk(current) {
        const entries = await fs.promises.readdir(current, { withFileTypes: true });
        entries.sort((a, b) => a.name.localeCompare(b.name));

        for (const entry of entries) {
            const full = path.join(current, entry.name);
            if (entry.isDirectory()) {
                await walk(full);
                continue;
            }
            if (!entry.isFile()) continue;

            const relative = path.relative(root, full).split(path.sep).join('/');
            const hash = (await sha256File(full)).toUpperCase();
            rows.push(`${relative}|${hash}`);
        }
    }

    await walk(root);
    rows.sort();
    return crypto.createHash('sha256').update(rows.join('\n'), 'utf8').digest('hex').toUpperCase();
}

function writeJsonFile(filePath, value) {
    fs.mkdirSync(path.dirname(filePath), { recursive: true });
    fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function verifyPayloadManifest(root, label = 'payload') {
    const manifestPath = path.join(root, 'PAYLOAD-SHA256.json');
    const manifest = readJsonFile(manifestPath);
    if (!manifest || !Array.isArray(manifest.files)) {
        throw new Error(`${label} PAYLOAD-SHA256.json is missing or invalid.`);
    }

    for (const entry of manifest.files) {
        if (!entry || typeof entry.path !== 'string' || typeof entry.sha256 !== 'string') {
            throw new Error(`${label} payload manifest contains an invalid entry.`);
        }

        const filePath = path.join(root, ...entry.path.split('/'));
        if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
            throw new Error(`${label} payload file is missing: ${entry.path}`);
        }

        const actualHash = (await sha256File(filePath)).toUpperCase();
        if (actualHash !== entry.sha256.toUpperCase()) {
            throw new Error(`${label} payload SHA-256 mismatch: ${entry.path}`);
        }

        if (Number.isFinite(Number(entry.size)) && fs.statSync(filePath).size !== Number(entry.size)) {
            throw new Error(`${label} payload size mismatch: ${entry.path}`);
        }
    }

    return manifest;
}

function mcpCompatibilitySpec(version) {
    const normalized = normalizeMcpSemver(version);
    return normalized ? MCP_COMPATIBILITY_BUNDLES[normalized] || null : null;
}

function mcpCompatibilityBundlePath(spec) {
    return path.join(MCP_COMPATIBILITY_ROOT, spec.filename);
}

async function inspectMcpCompatibilityBundle(version) {
    const normalized = normalizeMcpSemver(version);
    const spec = mcpCompatibilitySpec(normalized);

    if (!normalized || !spec) {
        return {
            available: false,
            version: normalized,
            reason: `No validated AI Director MCP compatibility bundle is registered for ${version || 'this release'}.`
        };
    }

    if (process.platform !== 'win32') {
        return {
            available: false,
            version: normalized,
            reason: `The registered ${normalized} compatibility bundle is Windows-specific.`
        };
    }

    const bundlePath = mcpCompatibilityBundlePath(spec);
    if (!fs.existsSync(bundlePath)) {
        return {
            available: false,
            version: normalized,
            bundlePath,
            reason: `Validated MCP ${normalized} compatibility bundle is not installed: ${bundlePath}`
        };
    }

    const actualHash = (await sha256File(bundlePath)).toUpperCase();
    if (actualHash !== spec.sha256) {
        return {
            available: false,
            version: normalized,
            bundlePath,
            reason: `MCP ${normalized} compatibility bundle SHA-256 mismatch.`
        };
    }

    return {
        available: true,
        version: normalized,
        bundlePath,
        bundleSha256: actualHash,
        spec
    };
}

const MCP_RUNTIME_ENVIRONMENT_KEYS = new Set([
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
    return [path.join(systemRoot, 'System32'), systemRoot];
}

function mcpPythonEnvironment(runtimeRoot, aafProbePython = null) {
    const env = { ...process.env };

    for (const key of Object.keys(env)) {
        if (MCP_RUNTIME_ENVIRONMENT_KEYS.has(key.toUpperCase())) {
            delete env[key];
        }
    }

    Object.assign(env, {
        PYTHONHOME: runtimeRoot,
        PYTHONPATH: '',
        PYTHONNOUSERSITE: '1',
        PYTHONDONTWRITEBYTECODE: '1',
        PIP_NO_INDEX: '1',
        PIP_DISABLE_PIP_VERSION_CHECK: '1',
        PIP_CONFIG_FILE: process.platform === 'win32' ? 'NUL' : '/dev/null',
        PATH: [
            runtimeRoot,
            ProductPaths.resolveNodeRoot,
            ...systemRuntimePathEntries()
        ].filter((entry) => entry).join(path.delimiter)
    });

    if (RESOLVE_SCRIPT_API) env.RESOLVE_SCRIPT_API = RESOLVE_SCRIPT_API;
    if (RESOLVE_SCRIPT_LIB) env.RESOLVE_SCRIPT_LIB = RESOLVE_SCRIPT_LIB;
    if (aafProbePython) env.AAF_PROBE_PYTHON = aafProbePython;
    return env;
}

function writeMcpPythonPth(runtimeRoot, managedMcpRoot) {
    if (process.platform !== 'win32' || !RESOLVE_SCRIPT_MODULES) {
        throw new Error('The validated MCP compatibility bundle currently supports Windows only.');
    }

    const pthPath = path.join(runtimeRoot, 'python311._pth');
    const lines = [
        'python311.zip',
        '.',
        'Lib\\site-packages',
        'Lib\\site-packages\\win32',
        'Lib\\site-packages\\win32\\lib',
        'Lib\\site-packages\\pythonwin',
        'Lib\\site-packages\\pywin32_system32',
        managedMcpRoot,
        RESOLVE_SCRIPT_MODULES
    ];
    fs.writeFileSync(pthPath, `${lines.join('\r\n')}\r\n`, 'utf8');
}

async function assertExactDistributionInventory(pythonExe, runtimeRoot, artifactManifest) {
    const expectedRows = Array.isArray(artifactManifest?.packages) ? artifactManifest.packages : [];
    if (expectedRows.length !== Number(artifactManifest?.expected_distribution_count || expectedRows.length)) {
        throw new Error('MCP Python artifact manifest distribution count is inconsistent.');
    }

    const inventoryCode = [
        'import importlib.metadata as md, json',
        'rows=[]',
        'for d in md.distributions():',
        '    n=d.metadata.get("Name")',
        '    if n: rows.append({"name":n,"version":d.version})',
        'print(json.dumps(rows))'
    ].join('\n');

    const result = await execFileAsync(pythonExe, ['-c', inventoryCode], {
        windowsHide: true,
        timeout: 120000,
        encoding: 'utf8',
        env: mcpPythonEnvironment(runtimeRoot)
    });

    let actualRows;
    try {
        actualRows = JSON.parse(result.stdout.trim());
    } catch (error) {
        throw new Error(`Could not parse staged MCP Python inventory: ${error.message}`);
    }

    const normalize = (value) => String(value || '').trim().toLowerCase().replace(/_/g, '-');
    const expected = new Map(expectedRows.map((row) => [normalize(row.name), String(row.version)]));
    const actual = new Map(actualRows.map((row) => [normalize(row.name), String(row.version)]));

    if (expected.size !== actual.size) {
        throw new Error(`MCP Python distribution count mismatch. Expected ${expected.size}, actual ${actual.size}.`);
    }

    for (const [name, version] of expected.entries()) {
        if (actual.get(name) !== version) {
            throw new Error(`MCP Python distribution mismatch for ${name}: expected ${version}, actual ${actual.get(name) || 'missing'}.`);
        }
    }
}

async function buildMcpPythonRuntimeFromImage({
    imageRoot,
    stageRoot,
    stagedMcpRoot,
    spec
}) {
    await verifyPayloadManifest(imageRoot, 'MCP Python image');

    const manifestPath = path.join(imageRoot, spec.pythonManifestFilename);
    const manifestHash = (await sha256File(manifestPath)).toUpperCase();
    if (manifestHash !== spec.pythonManifestSha256) {
        throw new Error('MCP Python image artifact manifest SHA-256 mismatch.');
    }

    const artifactManifest = readJsonFile(manifestPath);
    if (!artifactManifest ||
        artifactManifest.managed_mcp_version !== spec.managedMcpVersion ||
        artifactManifest.source_commit !== spec.sourceCommit ||
        Number(artifactManifest.expected_distribution_count) !== spec.distributionCount ||
        !Array.isArray(artifactManifest.packages) ||
        artifactManifest.packages.length !== spec.distributionCount) {
        throw new Error('MCP Python image artifact manifest identity mismatch.');
    }

    await fs.promises.rm(stageRoot, { recursive: true, force: true });
    await fs.promises.mkdir(stageRoot, { recursive: true });

    const pythonArchive = path.join(imageRoot, 'artifacts', artifactManifest.python.filename);
    const pythonArchiveHash = (await sha256File(pythonArchive)).toUpperCase();
    if (pythonArchiveHash !== String(artifactManifest.python.sha256).toUpperCase()) {
        throw new Error('Embedded CPython archive SHA-256 mismatch.');
    }

    await extractArchive(pythonArchive, stageRoot);

    const sitePackages = path.join(stageRoot, 'Lib', 'site-packages');
    await fs.promises.mkdir(sitePackages, { recursive: true });

    const pipRow = artifactManifest.packages.find((row) => row.name === 'pip');
    if (!pipRow) {
        throw new Error('MCP Python image does not contain the pinned pip wheel.');
    }

    const wheelRoot = path.join(imageRoot, 'artifacts', 'wheels');
    const pipWheel = path.join(wheelRoot, pipRow.filename);
    if ((await sha256File(pipWheel)).toUpperCase() !== String(pipRow.sha256).toUpperCase()) {
        throw new Error('Pinned pip wheel SHA-256 mismatch.');
    }
    await extractArchive(pipWheel, sitePackages);

    writeMcpPythonPth(stageRoot, stagedMcpRoot);

    const otherWheels = [];
    for (const row of artifactManifest.packages) {
        const wheelPath = path.join(wheelRoot, row.filename);
        const actualHash = (await sha256File(wheelPath)).toUpperCase();
        if (actualHash !== String(row.sha256).toUpperCase()) {
            throw new Error(`MCP Python wheel SHA-256 mismatch: ${row.filename}`);
        }
        if (row.name !== 'pip') otherWheels.push(wheelPath);
    }

    const pythonExe = process.platform === 'win32'
        ? path.join(stageRoot, 'python.exe')
        : path.join(stageRoot, 'bin', 'python');

    await execFileAsync(
        pythonExe,
        [
            '-m', 'pip', 'install',
            '--no-index',
            '--no-deps',
            '--disable-pip-version-check',
            '--no-compile',
            '--no-warn-script-location',
            '--upgrade',
            '--target', sitePackages,
            ...otherWheels
        ],
        {
            windowsHide: true,
            timeout: 600000,
            encoding: 'utf8',
            env: mcpPythonEnvironment(stageRoot)
        }
    );

    await assertExactDistributionInventory(pythonExe, stageRoot, artifactManifest);

    const importResult = await execFileAsync(
        pythonExe,
        ['-c', 'import aaf2, mcp, win32api, DaVinciResolveScript; print("MCP_RUNTIME_IMPORTS_OK")'],
        {
            windowsHide: true,
            timeout: 120000,
            encoding: 'utf8',
            env: mcpPythonEnvironment(stageRoot)
        }
    );
    if (!importResult.stdout.includes('MCP_RUNTIME_IMPORTS_OK')) {
        throw new Error('Staged MCP Python import verification failed.');
    }

    return {
        pythonExe,
        artifactManifest,
        manifestPath
    };
}

async function countFilesRecursive(root) {
    let count = 0;

    async function walk(current) {
        const entries = await fs.promises.readdir(current, { withFileTypes: true });
        for (const entry of entries) {
            const full = path.join(current, entry.name);
            if (entry.isDirectory()) {
                await walk(full);
            } else if (entry.isFile()) {
                count += 1;
            }
        }
    }

    await walk(root);
    return count;
}

const WINDOWS_ADVANCED_GUIDANCE_RELATIVE_PATH = path.join(
    'resolve-advanced',
    'server',
    'capabilities.mjs'
);

function buildWindowsAdvancedGuidanceOverlayFunctions() {
    const oldFunction = `export function capabilities() {
  const ff = hasFfmpeg() && hasFfprobe();
  return {
    core: 'always available (pure-JS): drp, drt, drx, offline_ref, editorial, fusion, audio_plan, conform(core)',
    optional: {
      ffmpeg: { available: ff, enables: 'audio (split/trim/convert)', install: 'brew install ffmpeg / apt install ffmpeg' },
      sharp: { available: hasSharp(), enables: 'conform.verify (frame compare)', install: 'npm i sharp' },
      'better-sqlite3': { available: hasBetterSqlite3(), enables: 'fairlight live-project-DB path (zip path needs none)', install: 'npm i better-sqlite3' },
    },
  };
}
`;
    const newFunction = `export function capabilities() {
  const ff = hasFfmpeg() && hasFfprobe();
  const ffmpegInstall =
    process.platform === 'win32'
      ? 'choco install ffmpeg'
      : process.platform === 'darwin'
        ? 'brew install ffmpeg'
        : 'apt install ffmpeg';
  const optional = {
    ffmpeg: { available: ff, enables: 'audio (split/trim/convert)', install: ffmpegInstall },
    sharp: { available: hasSharp(), enables: 'conform.verify (frame compare)', install: 'npm i sharp' },
    'better-sqlite3': { available: hasBetterSqlite3(), enables: 'fairlight live-project-DB path (zip path needs none)', install: 'npm i better-sqlite3' },
  };
  const coreTotal = 8;
  const optionalTotal = Object.keys(optional).length;
  const optionalAvailable = Object.values(optional).filter((item) => item.available).length;
  const operationalTotal = coreTotal + optionalAvailable;
  const total = coreTotal + optionalTotal;

  return {
    core: 'always available (pure-JS): drp, drt, drx, offline_ref, editorial, fusion, audio_plan, conform(core)',
    optional,
    summary: {
      core_total: coreTotal,
      optional_available: optionalAvailable,
      optional_total: optionalTotal,
      operational_total: operationalTotal,
      total,
      display: \`\${operationalTotal}/\${total} capabilities operational\`,
    },
  };
}
`;
    return { oldFunction, newFunction };
}

async function applyWindowsAdvancedGuidanceOverlay({ stagedMcpRoot, spec }) {
    if (process.platform !== 'win32') {
        throw new Error('The registered Windows Advanced guidance overlay is Windows-specific.');
    }

    const target = path.join(stagedMcpRoot, WINDOWS_ADVANCED_GUIDANCE_RELATIVE_PATH);
    if (!fs.existsSync(target)) {
        throw new Error(`Advanced capabilities overlay target is missing: ${target}`);
    }

    const beforeHash = (await sha256File(target)).toUpperCase();
    if (beforeHash === spec.windowsAdvancedGuidancePatchedSha256) {
        return { target, beforeHash, afterHash: beforeHash, changed: false };
    }
    if (beforeHash !== spec.windowsAdvancedGuidanceBaselineSha256) {
        throw new Error(
            `Advanced capabilities overlay baseline mismatch. Expected ${spec.windowsAdvancedGuidanceBaselineSha256}, actual ${beforeHash}.`
        );
    }

    const { oldFunction, newFunction } = buildWindowsAdvancedGuidanceOverlayFunctions();

    let text = fs.readFileSync(target, 'utf8');
    const functionMatches = text.split(oldFunction).length - 1;
    if (functionMatches !== 1) {
        throw new Error(
            `Advanced capabilities overlay transform identity mismatch (capabilitiesFunction=${functionMatches}).`
        );
    }

    text = text.replace(oldFunction, newFunction);
    fs.writeFileSync(target, text, 'utf8');

    const afterHash = (await sha256File(target)).toUpperCase();
    if (afterHash !== spec.windowsAdvancedGuidancePatchedSha256) {
        throw new Error(
            `Advanced capabilities overlay result mismatch. Expected ${spec.windowsAdvancedGuidancePatchedSha256}, actual ${afterHash}.`
        );
    }

    return { target, beforeHash, afterHash, changed: true };
}

async function installAdvancedNodeImage({
    imageRoot,
    stagedMcpRoot,
    spec
}) {
    // The image ZIP itself is SHA-pinned by the compatibility bundle and every
    // extracted file is independently SHA/size verified here. Do not make an
    // aggregate tree hash a cross-tool activation invariant: the v1 packager
    // computed that provenance hash with PowerShell path/sort canonicalization,
    // while Node uses a different canonical ordering. The bytes are already
    // protected by the immutable image SHA plus PAYLOAD-SHA256.json.
    await verifyPayloadManifest(imageRoot, 'Advanced Node image');

    const manifestPath = path.join(imageRoot, 'ADVANCED-NODE-DEPENDENCY-IMAGE-MANIFEST.json');
    const manifest = readJsonFile(manifestPath);
    if (!manifest ||
        manifest.managed_mcp_version !== spec.managedMcpVersion ||
        manifest.source_commit !== spec.sourceCommit ||
        String(manifest.package_json_sha256).toUpperCase() !== spec.advancedPackageSha256 ||
        String(manifest.package_lock_sha256).toUpperCase() !== spec.advancedLockSha256 ||
        Number(manifest.node_modules_file_count) !== spec.advancedFileCount) {
        throw new Error('Advanced Node image manifest identity mismatch.');
    }

    const packageJsonPath = path.join(imageRoot, 'package.json');
    const packageLockPath = path.join(imageRoot, 'package-lock.json');

    if ((await sha256File(packageJsonPath)).toUpperCase() !== spec.advancedPackageSha256) {
        throw new Error('Advanced Node package.json SHA-256 mismatch.');
    }
    if ((await sha256File(packageLockPath)).toUpperCase() !== spec.advancedLockSha256) {
        throw new Error('Advanced Node package-lock.json SHA-256 mismatch.');
    }

    const nodeModulesRoot = path.join(imageRoot, 'node_modules');
    const actualFileCount = await countFilesRecursive(nodeModulesRoot);
    if (actualFileCount !== spec.advancedFileCount) {
        throw new Error(
            `Advanced Node node_modules file-count mismatch. Expected ${spec.advancedFileCount}, actual ${actualFileCount}.`
        );
    }

    const advancedRoot = path.join(stagedMcpRoot, 'resolve-advanced');
    await fs.promises.rm(path.join(advancedRoot, 'node_modules'), { recursive: true, force: true });
    fs.cpSync(nodeModulesRoot, path.join(advancedRoot, 'node_modules'), { recursive: true, force: true });

    fs.copyFileSync(packageLockPath, path.join(advancedRoot, 'package-lock.json'));

    return { manifest, manifestPath };
}

async function installMandatoryAdvancedNodeImage({
    stagedMcpRoot,
    spec
}) {
    await verifyPayloadManifest(MCP_MANDATORY_ADVANCED_ROOT, 'mandatory Advanced Node image');

    const manifestPath = path.join(
        MCP_MANDATORY_ADVANCED_ROOT,
        'ADVANCED-NODE-MANDATORY-DEPENDENCY-IMAGE-MANIFEST.json'
    );
    const manifest = readJsonFile(manifestPath);

    const expectedPackageSha = String(spec.advancedPackageSha256 || MCP_COMPATIBILITY_CONTRACT.advancedPackageSha256).toUpperCase();
    const expectedLockSha = String(spec.advancedLockSha256 || MCP_COMPATIBILITY_CONTRACT.advancedLockSha256).toUpperCase();
    const expectedSharp = String(spec.mandatoryAdvancedSharpVersion || MCP_COMPATIBILITY_CONTRACT.mandatoryAdvancedSharpVersion);
    const expectedSqlite = String(spec.mandatoryAdvancedBetterSqlite3Version || MCP_COMPATIBILITY_CONTRACT.mandatoryAdvancedBetterSqlite3Version);

    if (!manifest ||
        manifest.product_node_version !== `v${ProductPaths.resolveNodeVersion}` ||
        String(manifest.package_json_sha256).toUpperCase() !== expectedPackageSha ||
        String(manifest.package_lock_sha256).toUpperCase() !== expectedLockSha ||
        String(manifest?.mandatory?.sharp) !== expectedSharp ||
        String(manifest?.mandatory?.better_sqlite3) !== expectedSqlite ||
        Number(manifest.advanced_tool_count) !== MCP_COMPATIBILITY_CONTRACT.advancedTools) {
        throw new Error(
            `Mandatory Advanced Node dependency contract mismatch (expected exactly ${MCP_COMPATIBILITY_CONTRACT.advancedTools} Advanced tools).`
        );
    }

    const packageJsonPath = path.join(MCP_MANDATORY_ADVANCED_ROOT, 'package.json');
    const packageLockPath = path.join(MCP_MANDATORY_ADVANCED_ROOT, 'package-lock.json');
    const nodeModulesRoot = path.join(MCP_MANDATORY_ADVANCED_ROOT, 'node_modules');

    if ((await sha256File(packageJsonPath)).toUpperCase() !== expectedPackageSha ||
        (await sha256File(packageLockPath)).toUpperCase() !== expectedLockSha) {
        throw new Error('Mandatory Advanced Node package identity mismatch.');
    }

    const actualFileCount = await countFilesRecursive(nodeModulesRoot);
    if (actualFileCount !== Number(manifest.node_modules_file_count)) {
        throw new Error(
            `Mandatory Advanced Node file-count mismatch. Expected ${manifest.node_modules_file_count}, actual ${actualFileCount}.`
        );
    }

    const advancedRoot = path.join(stagedMcpRoot, 'resolve-advanced');
    await fs.promises.rm(path.join(advancedRoot, 'node_modules'), { recursive: true, force: true });
    fs.cpSync(nodeModulesRoot, path.join(advancedRoot, 'node_modules'), { recursive: true, force: true });
    fs.copyFileSync(packageLockPath, path.join(advancedRoot, 'package-lock.json'));

    return { manifest, manifestPath };
}

function buildMcpCompatibilityProbeCode({
    expectedCompound = MCP_COMPATIBILITY_CONTRACT.compoundTools,
    expectedFull = MCP_COMPATIBILITY_CONTRACT.fullTools,
    expectedAdvanced = MCP_COMPATIBILITY_CONTRACT.advancedTools
} = {}) {
    expectedCompound = Number(expectedCompound);
    expectedFull = Number(expectedFull);
    expectedAdvanced = Number(expectedAdvanced);
    if (!Number.isInteger(expectedCompound) || expectedCompound <= 0 ||
        !Number.isInteger(expectedFull) || expectedFull <= 0 ||
        !Number.isInteger(expectedAdvanced) || expectedAdvanced <= 0) {
        throw new Error('Invalid MCP compatibility probe tool-count contract.');
    }
    return [
        'import asyncio, hashlib, json, os, sys',
        'from mcp import ClientSession, StdioServerParameters',
        'from mcp.client.stdio import stdio_client',
        '',
        'server, node, advanced = sys.argv[1], sys.argv[2], sys.argv[3]',
        '',
        'def json_from_text(value):',
        '    if not isinstance(value, str): return None',
        '    text=value.strip()',
        '    if not text or text[0] not in "[{": return None',
        '    try: return json.loads(text)',
        '    except Exception: return None',
        '',
        'def find_caps(value):',
        '    decoded=json_from_text(value)',
        '    if decoded is not None:',
        '        hit=find_caps(decoded)',
        '        if hit is not None: return hit',
        '    if isinstance(value, dict):',
        '        if all(k in value for k in ("ffmpeg","sharp","better-sqlite3")): return value',
        '        for v in value.values():',
        '            hit=find_caps(v)',
        '            if hit is not None: return hit',
        '    if isinstance(value, list):',
        '        for v in value:',
        '            hit=find_caps(v)',
        '            if hit is not None: return hit',
        '    return None',
        '',
        'def result_candidates(result):',
        '    out=[]',
        '    for attr in ("structured_content","structuredContent"):',
        '        value=getattr(result,attr,None)',
        '        if value is not None: out.append(value)',
        '    for block in getattr(result,"content",[]) or []:',
        '        text=getattr(block,"text",None)',
        '        if text: out.append(text)',
        '        elif isinstance(block,str): out.append(block)',
        '    if hasattr(result,"model_dump"):',
        '        try: out.append(result.model_dump(mode="json"))',
        '        except Exception: pass',
        '    return out',
        '',
        'def canonical_json(value):',
        '    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True,default=str)',
        '',
        'def normalize_nullable_input_schema(value,path,nullable_paths):',
        '    if isinstance(value,list):',
        '        return [normalize_nullable_input_schema(v,f"{path}[{i}]",nullable_paths) for i,v in enumerate(value)]',
        '    if not isinstance(value,dict): return value',
        '    source={k:normalize_nullable_input_schema(v,f"{path}.{k}",nullable_paths) for k,v in value.items()}',
        '    if "default" not in source or source.get("default") is not None: return source',
        '    any_of=source.get("anyOf")',
        '    if isinstance(any_of,list) and len(any_of)==2:',
        '        null_indexes=[i for i,row in enumerate(any_of) if isinstance(row,dict) and row.get("type")=="null" and len(row)==1]',
        '        if len(null_indexes)==1:',
        '            other=any_of[1-null_indexes[0]]',
        '            if isinstance(other,dict):',
        '                flattened={k:v for k,v in source.items() if k!="anyOf"}',
        '                if not any(k in flattened for k in other):',
        '                    flattened.update(other)',
        '                    nullable_paths.append(path)',
        '                    return flattened',
        '    types=source.get("type")',
        '    if isinstance(types,list) and len(types)==2 and types.count("null")==1:',
        '        non_null=[v for v in types if v!="null"]',
        '        if len(non_null)==1:',
        '            source["type"]=non_null[0]',
        '            nullable_paths.append(path)',
        '    return source',
        '',
        'def tool_contract(t):',
        '    if hasattr(t,"model_dump"):',
        '        try: data=t.model_dump(mode="json")',
        '        except Exception: data={}',
        '        try: alias_data=t.model_dump(mode="json",by_alias=True)',
        '        except Exception: alias_data=dict(data)',
        '    else: data={}; alias_data={}',
        '    if not isinstance(data,dict): data={}',
        '    if not isinstance(alias_data,dict): alias_data={}',
        '    name=getattr(t,"name",None) or alias_data.get("name") or data.get("name")',
        '    fingerprint_data=json.loads(json.dumps(data))',
        '    fingerprint_data.pop("name",None)',
        '    fingerprint_data.pop("description",None)',
        '    canonical=canonical_json(fingerprint_data)',
        '    compat_data=json.loads(json.dumps(fingerprint_data))',
        '    nullable_paths=[]',
        '    input_schema=compat_data.get("inputSchema")',
        '    if isinstance(input_schema,dict): compat_data["inputSchema"]=normalize_nullable_input_schema(input_schema,"inputSchema",nullable_paths)',
        '    compat_canonical=canonical_json(compat_data)',
        '    semantic={"title":alias_data.get("title"),"description":alias_data.get("description"),"inputSchema":alias_data.get("inputSchema") or {},"outputSchema":alias_data.get("outputSchema"),"annotations":alias_data.get("annotations"),"_meta":alias_data.get("_meta")}',
        '    return {"name":name,"fingerprint":hashlib.sha256(canonical.encode("utf-8")).hexdigest().upper(),"compatFingerprint":hashlib.sha256(compat_canonical.encode("utf-8")).hexdigest().upper(),"nullablePaths":sorted(set(nullable_paths)),"semanticFields":semantic}',
        '',
        'def walk_value(value):',
        '    decoded=json_from_text(value)',
        '    if decoded is not None:',
        '        yield from walk_value(decoded)',
        '        return',
        '    yield value',
        '    if isinstance(value,dict):',
        '        for v in value.values(): yield from walk_value(v)',
        '    elif isinstance(value,list):',
        '        for v in value: yield from walk_value(v)',
        '',
        'def result_error_message(result):',
        '    if bool(getattr(result,"isError",False) or getattr(result,"is_error",False)): return "MCP CallToolResult.isError"',
        '    for candidate in result_candidates(result):',
        '        for value in walk_value(candidate):',
        '            if not isinstance(value,dict): continue',
        '            err=value.get("error")',
        '            if isinstance(err,str) and err.strip(): return err.strip()',
        '            op=value.get("_operation")',
        '            if isinstance(op,dict) and str(op.get("status") or "").lower() in ("failed","blocked","contradiction"):',
        '                return "operation status " + str(op.get("status"))',
        '    return None',
        '',
        'def result_has_key(result,key):',
        '    for candidate in result_candidates(result):',
        '        for value in walk_value(candidate):',
        '            if isinstance(value,dict) and key in value: return True',
        '    return False',
        '',
        'async def python_surface(mode, expected, exact, run_canary=False):',
        '    args=[server] + (["--full"] if mode == "full" else [])',
        '    params=StdioServerParameters(command=sys.executable,args=args,env=dict(os.environ))',
        '    async with stdio_client(params) as (r,w):',
        '        async with ClientSession(r,w) as s:',
        '            init=await asyncio.wait_for(s.initialize(),timeout=30)',
        '            tools=await asyncio.wait_for(s.list_tools(),timeout=120)',
        '            contracts=[tool_contract(t) for t in tools.tools]',
        '            count=len(contracts)',
        '            if exact and count != expected: raise SystemExit(20)',
        '            if not exact and count < expected: raise SystemExit(21)',
        '            canary=None',
        '            if run_canary:',
        '                names={x["name"] for x in contracts}',
        '                if "resolve_control" not in names: raise SystemExit(24)',
        '                result=await asyncio.wait_for(s.call_tool("resolve_control",{"action":"get_page"}),timeout=60)',
        '                err=result_error_message(result)',
        '                if err: raise RuntimeError("resolve_control.get_page failed: " + err)',
        '                if not result_has_key(result,"page"): raise RuntimeError("resolve_control.get_page returned no page field")',
        '                canary={"tool":"resolve_control","action":"get_page","ok":True,"page_field_present":True}',
        '            try: init_data=init.model_dump(mode="json",by_alias=True)',
        '            except Exception: init_data={}',
        '            print(json.dumps({"surface":mode,"version":getattr(getattr(init,"serverInfo",None),"version",None),"protocolVersion":init_data.get("protocolVersion") if isinstance(init_data,dict) else None,"serverInfo":init_data.get("serverInfo") if isinstance(init_data,dict) else None,"serverCapabilities":init_data.get("capabilities") if isinstance(init_data,dict) else None,"count":count,"tools":contracts,"canary":canary}))',
        '',
        'async def advanced_surface(expected):',
        '    env=dict(os.environ)',
        '    env["AAF_PROBE_PYTHON"]=sys.executable',
        '    params=StdioServerParameters(command=node,args=[advanced],env=env)',
        '    async with stdio_client(params) as (r,w):',
        '        async with ClientSession(r,w) as s:',
        '            init=await asyncio.wait_for(s.initialize(),timeout=30)',
        '            tools=await asyncio.wait_for(s.list_tools(),timeout=120)',
        '            contracts=[tool_contract(t) for t in tools.tools]',
        '            count=len(contracts)',
        '            if count != expected: raise SystemExit(22)',
        '            result=await asyncio.wait_for(s.call_tool("capabilities",{"action":"get"}),timeout=60)',
        '            err=result_error_message(result)',
        '            if err: raise RuntimeError("advanced capabilities failed: " + err)',
        '            caps=None',
        '            for candidate in result_candidates(result):',
        '                caps=find_caps(candidate)',
        '                if caps is not None: break',
        '            if caps is None: raise SystemExit(26)',
        '            bad=[]',
        '            ff=caps.get("ffmpeg")',
        '            if not isinstance(ff,dict) or ff.get("available") is not False: bad.append("ffmpeg(expected unavailable)")',
        '            for key in ("sharp","better-sqlite3"):',
        '                item=caps.get(key)',
        '                if not isinstance(item,dict) or item.get("available") is not True: bad.append(key)',
        '            if bad: raise SystemExit(27)',
        '            try: init_data=init.model_dump(mode="json",by_alias=True)',
        '            except Exception: init_data={}',
        '            print(json.dumps({"surface":"advanced","version":getattr(getattr(init,"serverInfo",None),"version",None),"protocolVersion":init_data.get("protocolVersion") if isinstance(init_data,dict) else None,"serverInfo":init_data.get("serverInfo") if isinstance(init_data,dict) else None,"serverCapabilities":init_data.get("capabilities") if isinstance(init_data,dict) else None,"count":count,"tools":contracts,"capabilities":caps}))',
        '',
        'async def main():',
        `    await python_surface("compound", ${expectedCompound}, True, True)`,
        `    await python_surface("full", ${expectedFull}, False, False)`,
        `    await advanced_surface(${expectedAdvanced})`,
        'asyncio.run(main())',
        'print("MCP_COMPATIBILITY_STDIO_PASS")'
    ].join('\n');
}

function summarizeMcpSemanticReasons(result, limit = 8) {
    const rows = Array.isArray(result?.reasons) ? result.reasons : [];
    if (!rows.length) return 'none';
    return rows.slice(0, limit).map((row) => {
        const status = String(row?.status || 'REVIEW');
        const pathText = String(row?.path || '$');
        const message = String(row?.message || 'semantic compatibility review required');
        return `${status}:${pathText}:${message}`;
    }).join(' | ');
}

function enforceMcpSemanticSurface(surface, acceptedSurface, candidateSurface, { allowAdditions = false } = {}) {
    const result = MCP_SEMANTIC_ENGINE.compareSurface(
        acceptedSurface,
        candidateSurface,
        { allowAdditions, surface }
    );
    candidateSurface.semanticCompatibility = result;
    if (result.status === MCP_SEMANTIC_ENGINE.FAIL) {
        throw new Error(
            `MCP ${surface} semantic contract is incompatible. ${summarizeMcpSemanticReasons(result)}`
        );
    }
    if (result.status === MCP_SEMANTIC_ENGINE.REVIEW) {
        throw new Error(
            `COMPATIBILITY_UNKNOWN: MCP ${surface} semantic compatibility requires manual review. ${summarizeMcpSemanticReasons(result)}`
        );
    }
    return result;
}

async function validateStagedMcpCompatibility({
    workRoot,
    pythonExe,
    pythonRoot,
    stagedMcpRoot,
    spec,
    acceptedSurfaceContract = null
}) {
    const expectedCompound = Number(spec.compoundTools || MCP_COMPATIBILITY_CONTRACT.compoundTools);
    const expectedFull = Number(spec.fullTools || MCP_COMPATIBILITY_CONTRACT.fullTools);
    const expectedAdvanced = Number(spec.advancedTools || MCP_COMPATIBILITY_CONTRACT.advancedTools);

    const probePath = path.join(workRoot, 'mcp-compatibility-probe.py');
    const probeCode = buildMcpCompatibilityProbeCode({
        expectedCompound,
        expectedFull,
        expectedAdvanced
    });

    fs.writeFileSync(probePath, probeCode, 'utf8');

    const result = await execFileAsync(
        pythonExe,
        [
            probePath,
            path.join(stagedMcpRoot, 'src', 'server.py'),
            NODE_EXE,
            path.join(stagedMcpRoot, 'bin', 'davinci-resolve-advanced-mcp.mjs')
        ],
        {
            cwd: workRoot,
            windowsHide: true,
            timeout: 300000,
            encoding: 'utf8',
            maxBuffer: 32 * 1024 * 1024,
            env: mcpPythonEnvironment(pythonRoot, pythonExe)
        }
    );

    if (!result.stdout.includes('MCP_COMPATIBILITY_STDIO_PASS')) {
        throw new Error('MCP compatibility stdio verification did not complete.');
    }

    const surfaces = {};
    for (const line of result.stdout.split(/\r?\n/)) {
        const text = line.trim();
        if (!text.startsWith('{')) continue;
        try {
            const row = JSON.parse(text);
            if (row && typeof row.surface === 'string' && Number.isFinite(Number(row.count))) {
                surfaces[row.surface] = { ...row, count: Number(row.count) };
            }
        } catch (_error) {}
    }
    if (!surfaces.compound || !surfaces.full || !surfaces.advanced) {
        throw new Error('MCP compatibility probe did not report all required surfaces.');
    }
    if (surfaces.compound.count !== expectedCompound || surfaces.advanced.count !== expectedAdvanced || surfaces.full.count < expectedFull) {
        throw new Error(`MCP surface count contract failed (compound=${surfaces.compound.count}/${expectedCompound}, full=${surfaces.full.count}/${expectedFull}+, advanced=${surfaces.advanced.count}/${expectedAdvanced}).`);
    }
    if (!surfaces.compound.canary?.ok) {
        throw new Error('MCP read-only Resolve canary resolve_control.get_page did not pass.');
    }

    if (acceptedSurfaceContract && typeof acceptedSurfaceContract === 'object') {
        enforceMcpSemanticSurface(
            'compound',
            acceptedSurfaceContract.compound,
            surfaces.compound,
            { allowAdditions: false }
        );
        enforceMcpSemanticSurface(
            'advanced',
            acceptedSurfaceContract.advanced,
            surfaces.advanced,
            { allowAdditions: false }
        );
        // Full/granular aliases are internal: additions are allowed, but every
        // existing accepted API must remain directionally schema-compatible.
        enforceMcpSemanticSurface(
            'full',
            acceptedSurfaceContract.full,
            surfaces.full,
            { allowAdditions: true }
        );
    }

    return { surfaces, stdout: result.stdout, stderr: result.stderr };
}

async function snapshotManifestFiles(backupStateRoot, manifestPaths) {
    await fs.promises.mkdir(backupStateRoot, { recursive: true });
    const rows = [];
    for (const manifestPath of manifestPaths) {
        const existed = fs.existsSync(manifestPath);
        const backupPath = path.join(backupStateRoot, path.basename(manifestPath));
        if (existed) fs.copyFileSync(manifestPath, backupPath);
        rows.push({ path: manifestPath, existed, backupPath });
    }
    writeJsonFile(path.join(backupStateRoot, 'manifest-backup-state.json'), rows);
    return rows;
}

async function restoreManifestFiles(rows) {
    for (const row of rows) {
        if (row.existed) {
            fs.mkdirSync(path.dirname(row.path), { recursive: true });
            fs.copyFileSync(row.backupPath, row.path);
        } else {
            await fs.promises.rm(row.path, { force: true });
        }
    }
}

function llamaStackExecutionEnvironment(runtimeRoot = LLAMA_ROOT) {
    const env = { ...process.env };
    for (const key of Object.keys(env)) {
        const normalized = key.toUpperCase();
        if (normalized === 'PATH' || normalized === 'CUDA_PATH' || normalized === 'CUDA_HOME' || normalized === 'CUDATOOLKIT_ROOT' || normalized.startsWith('CUDA_PATH_V')) {
            delete env[key];
        }
    }
    const systemRoot = process.env.SystemRoot || process.env.WINDIR || 'C:\\Windows';
    env.PATH = [
        ProductPaths.commonCudaRoot,
        runtimeRoot,
        path.join(systemRoot, 'System32'),
        systemRoot
    ].filter(Boolean).join(path.delimiter);
    return env;
}

function readLlamaRuntimeStackManifest() {
    if (!LLAMA_RUNTIME_STACK_MANAGED) return null;
    if (!LLAMA_RUNTIME_STACK_MANIFEST || !fs.existsSync(LLAMA_RUNTIME_STACK_MANIFEST)) {
        throw new Error(`AI Director runtime-stack manifest is missing: ${LLAMA_RUNTIME_STACK_MANIFEST || 'not configured'}`);
    }
    const manifest = readJsonFile(LLAMA_RUNTIME_STACK_MANIFEST);
    if (!manifest || manifest.runtime_stack_id !== LLAMA_RUNTIME_STACK_ID) {
        throw new Error('AI Director runtime-stack manifest identity mismatch.');
    }
    const policy = manifest.upstream?.update_policy;
    if (manifest.runtime_line !== 'cuda13' || manifest.toolkit_line !== '13.3' || !policy || policy.enabled !== true) {
        throw new Error('AI Director runtime-stack Upstream update policy is missing or incompatible.');
    }
    if (policy.repository !== LLAMA_REPO || policy.bundle_profile !== 'cuda13-portable' || policy.runtime_line !== 'cuda13' || policy.toolkit_line !== '13.3') {
        throw new Error('AI Director runtime-stack Upstream update policy identity mismatch.');
    }
    if (policy.compatibility_scope !== 'LOCAL_GPU_AND_STACK_CONTRACT' || policy.shared_cuda_root !== 'AIDirector/Common/Runtime/CUDA/13.3') {
        throw new Error('AI Director runtime-stack Upstream compatibility/shared-CUDA policy mismatch.');
    }
    const driverPolicy = manifest.driver_policy;
    if (!driverPolicy || driverPolicy.vendor !== 'nvidia' || driverPolicy.platform !== 'windows' || Number(driverPolicy.minimum_driver_major) !== 580 || driverPolicy.compatibility_basis !== 'CUDA_13_MINOR_VERSION_COMPATIBILITY') {
        throw new Error('AI Director runtime-stack NVIDIA driver policy identity mismatch.');
    }
    return manifest;
}

function smTokenForComputeCapability(value) {
    const number = Number.parseFloat(String(value || '').trim());
    if (!Number.isFinite(number)) return null;
    return number.toFixed(1).replace('.', '');
}

function smListSupportsComputeCapability(values, capability) {
    const token = smTokenForComputeCapability(capability);
    if (!token || !Array.isArray(values)) return false;
    const normalized = new Set(values.map((item) => String(item).trim().toLowerCase()));
    return normalized.has(token) || normalized.has(`${token}a`);
}

async function queryLocalNvidiaRuntimeAuthority() {
    if (process.platform !== 'win32') {
        throw new Error('CUDA13 runtime-stack compatibility is currently defined for Windows only.');
    }
    const systemRoot = process.env.SystemRoot || process.env.WINDIR || 'C:\\Windows';
    const nvidiaSmi = path.join(systemRoot, 'System32', 'nvidia-smi.exe');
    const result = await execFileAsync(
        nvidiaSmi,
        ['--query-gpu=name,driver_version,compute_cap', '--format=csv,noheader,nounits'],
        { windowsHide: true, timeout: 5000, encoding: 'utf8' }
    );
    const rows = String(result.stdout || '').split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
    const parsed = rows.map((row) => {
        const fields = row.split(',').map((part) => part.trim());
        const driverVersion = fields[1] || '';
        return {
            name: fields[0] || 'NVIDIA GPU',
            driverVersion,
            driverMajor: Number.parseInt(driverVersion.split('.')[0], 10),
            computeCapability: fields[2] || ''
        };
    }).filter((item) => item.computeCapability);
    if (!parsed.length) {
        throw new Error('NVIDIA driver query returned no GPU compute-capability rows.');
    }
    return parsed;
}

async function validateLlamaRuntimeStackCompatibility(runtimeRoot) {
    if (!LLAMA_RUNTIME_STACK_MANAGED) return null;
    const manifest = readLlamaRuntimeStackManifest();
    const policy = manifest.upstream.update_policy;
    const markerPath = path.join(runtimeRoot, 'UNSLOTH_PREBUILT_INFO.json');
    const marker = readJsonFile(markerPath);
    if (!marker) {
        throw new Error(`Upstream runtime candidate is missing a readable UNSLOTH_PREBUILT_INFO.json: ${markerPath}`);
    }
    if (marker.platform !== 'windows-x64-cuda' || marker.bundle_profile !== policy.bundle_profile || marker.runtime_line !== policy.runtime_line || marker.toolkit_line !== policy.toolkit_line) {
        throw new Error('Upstream runtime candidate does not match the active CUDA13 stack bundle profile/runtime/toolkit contract.');
    }
    for (const dll of LLAMA_STACK_CUDA_RUNTIME_DLLS) {
        if (fs.existsSync(path.join(runtimeRoot, dll))) {
            throw new Error(`Upstream runtime candidate bundles ${dll}; AI Director requires the product-owned shared CUDA runtime.`);
        }
    }
    const driverFloor = Number(manifest.driver_policy?.minimum_driver_major || 0);
    const stackSms = manifest.gpu_policy?.supported_sms;
    const candidateSms = marker.supported_sms;
    const authorities = await queryLocalNvidiaRuntimeAuthority();
    const compatible = authorities.find((item) => (
        Number.isInteger(item.driverMajor) &&
        item.driverMajor >= driverFloor &&
        smListSupportsComputeCapability(stackSms, item.computeCapability) &&
        smListSupportsComputeCapability(candidateSms, item.computeCapability)
    ));
    if (!compatible) {
        const observed = authorities.map((item) => `${item.name} driver=${item.driverVersion} compute=${item.computeCapability}`).join('; ');
        throw new Error(`Upstream runtime candidate is not compatible with the local GPU and active runtime stack. Required driver major >= ${driverFloor}. Detected: ${observed}`);
    }
    return { manifest, marker, authority: compatible };
}

function parseMarker() {
    try {
        if (!fs.existsSync(LLAMA_MARKER)) return null;
        const text = fs.readFileSync(LLAMA_MARKER, 'utf8');
        const marker = JSON.parse(text);
        return marker && typeof marker === 'object' ? marker : null;
    } catch (_error) {
        return null;
    }
}

async function llamaBinaryVersion() {
    if (!fs.existsSync(LLAMA_EXE)) return null;
    try {
        const result = await execFileAsync(
            LLAMA_EXE,
            ['--version'],
            {
                windowsHide: true,
                timeout: 20000,
                encoding: 'utf8',
                env: llamaStackExecutionEnvironment(LLAMA_ROOT)
            }
        );
        const output = `${result.stdout}\n${result.stderr}`;
        const build = output.match(/version:[^\r\n]*\bbuild\s+(\d+)\b/i)?.[1]
            || output.match(/version:\s*(\d+)\b(?!\.)/i)?.[1];
        return build ? `b${build}` : output.trim().split(/\r?\n/)[0] || null;
    } catch (_error) {
        return null;
    }
}

function baseBuild(tag) {
    const match = String(tag || '').match(/(?:^|\b)b(\d+)/i);
    return match ? Number(match[1]) : null;
}

function parseReleaseVersion(value) {
    const text = String(value || '').trim();
    if (!text) return null;

    const build = text.match(/(?:^|\b)b(\d+)\b/i);
    if (build) {
        return { kind: 'build', parts: [Number(build[1])] };
    }

    const semver = text.match(/(?:^|[^0-9])(\d+)(?:\.(\d+))(?:\.(\d+))(?:$|[^0-9])/);
    if (semver) {
        return {
            kind: 'semver',
            parts: [Number(semver[1]), Number(semver[2]), Number(semver[3])]
        };
    }

    return null;
}

function normalizeMcpSemver(value) {
    const text = String(value || '').trim().replace(/^v/i, '');
    return /^\d+\.\d+\.\d+$/.test(text) ? text : null;
}

function compareReleaseTags(current, latest) {
    if (!current || !latest) return null;

    const currentSemver = normalizeMcpSemver(current);
    const latestSemver = normalizeMcpSemver(latest);
    if (currentSemver && latestSemver) {
        if (currentSemver === latestSemver) return 0;
        const left = parseReleaseVersion(currentSemver);
        const right = parseReleaseVersion(latestSemver);
        if (!left || !right) return null;
        for (let index = 0; index < Math.max(left.parts.length, right.parts.length); index += 1) {
            const a = left.parts[index] || 0;
            const b = right.parts[index] || 0;
            if (a < b) return -1;
            if (a > b) return 1;
        }
        return 0;
    }

    if (String(current) === String(latest)) return 0;

    const left = parseReleaseVersion(current);
    const right = parseReleaseVersion(latest);
    if (!left || !right || left.kind !== right.kind) return null;

    for (let index = 0; index < Math.max(left.parts.length, right.parts.length); index += 1) {
        const a = left.parts[index] || 0;
        const b = right.parts[index] || 0;
        if (a < b) return -1;
        if (a > b) return 1;
    }

    return 0;
}

function deriveLlamaAsset(marker, latestRelease) {
    if (!marker || !latestRelease || !Array.isArray(latestRelease.assets)) return null;

    const oldTags = [marker.release_tag, marker.tag]
        .filter((value) => typeof value === 'string' && value.trim())
        .sort((a, b) => b.length - a.length);

    for (const oldTag of oldTags) {
        if (typeof marker.asset === 'string' && marker.asset.includes(oldTag)) {
            const candidateName = marker.asset.replace(oldTag, latestRelease.tag_name);
            const exact = (latestRelease.assets || []).find((asset) => asset.name === candidateName);
            if (exact) {
                return {
                    asset: exact,
                    reason: `same recorded Unsloth asset family (${marker.asset})`
                };
            }
        }
    }

    const profile = marker.bundle_profile || marker.runtime_line;
    if (typeof profile === 'string' && profile) {
        const platformToken = process.platform === 'win32'
            ? 'windows'
            : process.platform === 'darwin'
                ? 'macos'
                : 'linux';
        const archToken = process.arch === 'x64'
            ? 'x64'
            : process.arch === 'arm64'
                ? 'arm64'
                : process.arch;

        const candidates = (latestRelease.assets || []).filter((asset) => {
            const name = String(asset.name || '').toLowerCase();
            return name.includes(`-${platformToken}-${archToken}-`) &&
                name.includes(String(profile).toLowerCase()) &&
                /\.zip$|\.tar\.gz$/i.test(name);
        });

        if (candidates.length === 1) {
            return {
                asset: candidates[0],
                reason: `recorded Unsloth bundle profile (${profile})`
            };
        }
    }

    return null;
}

async function checkLlamaUpdates({ force = false } = {}) {
    const marker = parseMarker();
    if (LLAMA_RUNTIME_STACK_MANAGED) {
        await validateLlamaRuntimeStackCompatibility(LLAMA_ROOT);
    }
    const binaryVersion = await llamaBinaryVersion();
    const installedVersion = marker?.upstream_tag || marker?.resolved_source_ref || marker?.release_tag || marker?.tag || binaryVersion || null;
    const latest = await getJson(`https://api.github.com/repos/${LLAMA_REPO}/releases/latest`);
    const latestVersion = latest?.tag_name || null;

    const comparison = compareReleaseTags(installedVersion, latestVersion);
    const updateAvailable = comparison === -1;
    const assetChoice = updateAvailable
        ? deriveLlamaAsset(marker, latest)
        : null;

    let installAvailable = false;
    let installReason = 'No newer build is available.';

    if (updateAvailable) {
        if (!marker) {
            installReason = 'Unsloth prebuilt marker not found; refusing to guess the installed bundle variant.';
        } else if (!assetChoice) {
            installReason = 'The installed Unsloth bundle variant could not be matched safely to the latest release.';
        } else if (!assetChoice.asset?.browser_download_url) {
            installReason = 'The matching release asset has no downloadable URL.';
        } else if (!latest?.id || !assetChoice.asset?.id) {
            installReason = 'The matching GitHub release/asset identity is incomplete; refusing an unbound install.';
        } else {
            const digest = String(assetChoice.asset.digest || '');
            if (!digest.toLowerCase().startsWith('sha256:')) {
                installReason = 'The matching release asset did not provide a GitHub SHA-256 digest; refusing an unverified install.';
            } else {
                installAvailable = true;
                installReason = 'Safe install candidate identified.';
            }
        }
    }

    return {
        component: 'llama',
        repo: LLAMA_REPO,
        platform: process.platform,
        arch: process.arch,
        installedVersion,
        binaryVersion,
        latestVersion,
        updateAvailable,
        installAvailable,
        installReason,
        markerFound: Boolean(marker),
        marker: marker
            ? {
                asset: marker.asset || null,
                installKind: marker.install_kind || null,
                bundleProfile: marker.bundle_profile || null,
                backend: marker.llama_backend || marker.backend || null
            }
            : null,
        matchedAsset: assetChoice
            ? {
                name: assetChoice.asset.name,
                size: assetChoice.asset.size || null,
                digest: assetChoice.asset.digest || null,
                reason: assetChoice.reason
            }
            : null,
        // Git refs/tags are mutable and are not transaction provenance authority.
        // Bind the visible update transaction to the concrete GitHub release and
        // release asset identities plus digest/size; tag_name remains display/version
        // ordering metadata only.
        candidateIdentity: assetChoice ? {
            version: latestVersion,
            releaseId: latest?.id || null,
            assetId: assetChoice.asset.id || null,
            assetName: assetChoice.asset.name,
            assetSize: assetChoice.asset.size || null,
            assetDigest: assetChoice.asset.digest || null
        } : null,
        releaseUrl: latest?.html_url || `https://github.com/${LLAMA_REPO}/releases`
    };
}

function mcpAcceptanceContractPath(version) {
    const normalized = normalizeMcpSemver(version);
    return normalized ? path.join(MCP_ACCEPTANCE_CONTRACT_ROOT, `MCP-COMPATIBILITY-CONTRACT-${normalized}.json`) : null;
}

function readMcpAcceptanceContract(version) {
    const contractPath = mcpAcceptanceContractPath(version);
    if (!contractPath || !fs.existsSync(contractPath)) return null;
    const contract = readJsonFile(contractPath);
    if (!contract || contract.managed_mcp_version !== normalizeMcpSemver(version)) return null;
    return { ...contract, contractPath };
}

function nodeEngineCompatibility(engineRange) {
    const range = String(engineRange || '').trim();
    if (!range) {
        return { known: false, compatible: false, reason: 'MCP package does not declare engines.node.' };
    }
    const semverPath = path.join(ProductPaths.resolveNodeRoot, 'node_modules', 'npm', 'node_modules', 'semver');
    let semver;
    try {
        semver = require(semverPath);
    } catch (error) {
        return { known: false, compatible: false, reason: `Product npm semver evaluator is unavailable: ${error.message}` };
    }
    try {
        const validRange = semver.validRange(range);
        if (!validRange) return { known: false, compatible: false, reason: `Unrecognized Node engine range: ${range}` };
        const compatible = semver.satisfies(ProductPaths.resolveNodeVersion, validRange, { includePrerelease: true });
        return {
            known: true,
            compatible,
            range,
            productNodeVersion: ProductPaths.resolveNodeVersion,
            reason: compatible
                ? `Product Node ${ProductPaths.resolveNodeVersion} satisfies ${range}.`
                : `Product Node ${ProductPaths.resolveNodeVersion} does not satisfy ${range}.`
        };
    } catch (error) {
        return { known: false, compatible: false, reason: `Could not evaluate Node engine range ${range}: ${error.message}` };
    }
}

function stableCandidateIdentity(value) {
    if (!value || typeof value !== 'object') return null;
    const ordered = {
        version: value.version || null,
        sourceCommit: value.sourceCommit || null,
        enginesNode: value.enginesNode || null,
        requirementsSha256: value.requirementsSha256 || null,
        advancedPackageSha256: value.advancedPackageSha256 || null,
        advancedLockSha256: value.advancedLockSha256 || null,
        sourcePackageSha256: value.sourcePackageSha256 || null,
        capabilitiesSha256: value.capabilitiesSha256 || null,
        versionContractSha256: value.versionContractSha256 || null,
        sourceAddressing: value.sourceAddressing || null,
        commitArchiveSha256: value.commitArchiveSha256 || null,
        sourceArchiveSha256: value.sourceArchiveSha256 || null
    };
    return JSON.stringify(ordered);
}

function stableJsonContractValue(value) {
    if (Array.isArray(value)) return value.map(stableJsonContractValue);
    if (value && typeof value === 'object') {
        const out = {};
        for (const key of Object.keys(value).sort()) {
            out[key] = stableJsonContractValue(value[key]);
        }
        return out;
    }
    return value;
}

function advancedRuntimeDependencyContract(packageJson) {
    const source = packageJson && typeof packageJson === 'object' ? packageJson : {};
    return JSON.stringify(stableJsonContractValue({
        name: source.name || null,
        type: Object.prototype.hasOwnProperty.call(source, 'type') ? source.type : null,
        main: source.main || null,
        exports: source.exports || null,
        imports: source.imports || null,
        bin: source.bin || null,
        engines: source.engines || {},
        dependencies: source.dependencies || {},
        optionalDependencies: source.optionalDependencies || {},
        peerDependencies: source.peerDependencies || {},
        os: source.os || null,
        cpu: source.cpu || null,
        libc: source.libc || null
    }));
}

async function inspectAdvancedRuntimeDependencyContract(candidatePackage) {
    const acceptedPackagePath = path.join(MCP_MANDATORY_ADVANCED_ROOT, 'package.json');
    if (!fs.existsSync(acceptedPackagePath)) {
        return {
            known: false,
            compatible: false,
            reason: 'Accepted product-owned Advanced dependency package.json is missing.'
        };
    }

    const acceptedPackageSha256 = (await sha256File(acceptedPackagePath)).toUpperCase();
    if (acceptedPackageSha256 !== MCP_COMPATIBILITY_CONTRACT.advancedPackageSha256) {
        return {
            known: false,
            compatible: false,
            reason: 'Accepted product-owned Advanced dependency package.json failed its pinned SHA-256 contract.'
        };
    }

    const acceptedPackage = readJsonFile(acceptedPackagePath);
    if (!acceptedPackage || !candidatePackage || typeof candidatePackage !== 'object') {
        return {
            known: false,
            compatible: false,
            reason: 'Advanced runtime dependency package metadata could not be parsed.'
        };
    }

    const acceptedIdentity = advancedRuntimeDependencyContract(acceptedPackage);
    const candidateIdentity = advancedRuntimeDependencyContract(candidatePackage);
    const compatible = acceptedIdentity === candidateIdentity;
    return {
        known: true,
        compatible,
        acceptedIdentity,
        candidateIdentity,
        reason: compatible
            ? 'Advanced runtime dependency semantics match the accepted immutable dependency image.'
            : 'resolve-advanced runtime dependency semantics differ from the accepted immutable dependency image.'
    };
}

async function resolveGithubTagCommit(repo, version) {
    const normalized = normalizeMcpSemver(version);
    if (!normalized) throw new Error(`Invalid release version: ${version}`);
    const tag = `v${normalized}`;
    const ref = await getJson(`https://api.github.com/repos/${repo}/git/ref/tags/${tag}`);
    let objectType = ref?.object?.type || null;
    let objectSha = ref?.object?.sha || null;
    if (!objectType || !objectSha) throw new Error(`GitHub tag ${tag} did not expose an object identity.`);
    if (objectType === 'tag') {
        const annotated = await getJson(`https://api.github.com/repos/${repo}/git/tags/${objectSha}`);
        objectType = annotated?.object?.type || null;
        objectSha = annotated?.object?.sha || null;
    }
    if (objectType !== 'commit' || !/^[0-9a-f]{40}$/i.test(String(objectSha || ''))) {
        throw new Error(`GitHub tag ${tag} did not resolve to a commit.`);
    }
    return String(objectSha).toLowerCase();
}

async function inspectMcpReleaseContract(version) {
    const normalized = normalizeMcpSemver(version);
    if (!normalized) {
        return { available: false, version: null, reason: `Invalid MCP release version: ${version || 'unknown'}.` };
    }

    try {
        const tag = `v${normalized}`;
        // Resolve the tag once, then read every descriptor through that immutable
        // 40-character commit. A moved tag can never mix descriptor bytes and
        // source identity inside one checked candidate.
        const sourceCommit = await resolveGithubTagCommit(MCP_REPO, normalized);
        const base = `https://raw.githubusercontent.com/${MCP_REPO}/${sourceCommit}`;
        const [rootPackageBody, requirementsBody, advancedPackageBody, advancedLockBody, capabilitiesBody] = await Promise.all([
            httpRequest(`${base}/package.json`),
            httpRequest(`${base}/requirements.txt`),
            httpRequest(`${base}/resolve-advanced/package.json`),
            httpRequest(`${base}/resolve-advanced/package-lock.json`),
            httpRequest(`${base}/resolve-advanced/server/capabilities.mjs`)
        ]);

        let rootPackage;
        let advancedPackage;
        try { rootPackage = JSON.parse(rootPackageBody.toString('utf8')); }
        catch (error) { throw new Error(`package.json parse failed: ${error.message}`); }
        try { advancedPackage = JSON.parse(advancedPackageBody.toString('utf8')); }
        catch (error) { throw new Error(`resolve-advanced/package.json parse failed: ${error.message}`); }

        if (rootPackage?.name !== MCP_NPM_PACKAGE || rootPackage?.version !== normalized) {
            throw new Error(`GitHub ${tag} package identity does not match ${MCP_NPM_PACKAGE}@${normalized}.`);
        }

        const nodeEngine = nodeEngineCompatibility(rootPackage?.engines?.node);
        const advancedRuntime = await inspectAdvancedRuntimeDependencyContract(advancedPackage);

        const descriptors = {
            sourcePackageSha256: sha256Buffer(rootPackageBody),
            requirementsSha256: sha256Buffer(requirementsBody),
            advancedPackageSha256: sha256Buffer(advancedPackageBody),
            advancedLockSha256: sha256Buffer(advancedLockBody),
            capabilitiesSha256: sha256Buffer(capabilitiesBody)
        };
        const changed = [];
        if (descriptors.requirementsSha256 !== MCP_COMPATIBILITY_CONTRACT.requirementsSha256) changed.push('requirements.txt');
        if (!advancedRuntime.known || !advancedRuntime.compatible) changed.push(advancedRuntime.reason);
        if (descriptors.advancedLockSha256 !== MCP_COMPATIBILITY_CONTRACT.advancedLockSha256) changed.push('resolve-advanced/package-lock.json');
        if (!nodeEngine.known || !nodeEngine.compatible) changed.push(nodeEngine.reason);

        if (changed.length) {
            return {
                available: false,
                version: normalized,
                sourceCommit,
                descriptors,
                reason: `MCP ${normalized} changes the validated dependency/runtime contract (${changed.join(', ')}). The accepted MCP remains active; no files will be replaced.`
            };
        }

        const versionContract = readMcpAcceptanceContract(normalized);
        let versionContractSha256 = null;
        if (versionContract) {
            versionContractSha256 = (await sha256File(versionContract.contractPath)).toUpperCase();
            const contractDescriptors = versionContract.descriptors || {};
            const contractMismatch = [];
            if (String(versionContract.github_source_commit || '').toLowerCase() !== sourceCommit) contractMismatch.push('source commit');
            if (String(versionContract.node_engine || '') !== String(rootPackage?.engines?.node || '')) contractMismatch.push('node engine');
            if (String(versionContract.source_download_mode || '') !== 'commit-addressed') contractMismatch.push('source download mode');
            if (String(contractDescriptors.source_package_json_sha256 || '').toUpperCase() !== descriptors.sourcePackageSha256) contractMismatch.push('source package');
            if (String(contractDescriptors.requirements_sha256 || '').toUpperCase() !== descriptors.requirementsSha256) contractMismatch.push('requirements');
            if (String(contractDescriptors.advanced_package_sha256 || '').toUpperCase() !== descriptors.advancedPackageSha256) contractMismatch.push('advanced package');
            if (String(contractDescriptors.advanced_lock_sha256 || '').toUpperCase() !== descriptors.advancedLockSha256) contractMismatch.push('advanced lock');
            if (String(contractDescriptors.capabilities_sha256 || '').toUpperCase() !== descriptors.capabilitiesSha256) contractMismatch.push('capabilities');
            if (contractMismatch.length) {
                return {
                    available: false,
                    version: normalized,
                    sourceCommit,
                    descriptors,
                    reason: `Version-bound MCP ${normalized} acceptance contract no longer matches GitHub (${contractMismatch.join(', ')}). The accepted MCP remains active.`
                };
            }
        }

        const candidateIdentity = {
            version: normalized,
            sourceCommit,
            enginesNode: rootPackage?.engines?.node || null,
            sourcePackageSha256: descriptors.sourcePackageSha256,
            requirementsSha256: descriptors.requirementsSha256,
            advancedPackageSha256: descriptors.advancedPackageSha256,
            advancedLockSha256: descriptors.advancedLockSha256,
            capabilitiesSha256: descriptors.capabilitiesSha256,
            versionContractSha256,
            sourceAddressing: 'commit',
            commitArchiveSha256: versionContract?.commit_archive_sha256 || null
        };

        return {
            available: true,
            version: normalized,
            sourceCommit,
            descriptors,
            rootPackage: {
                version: rootPackage.version,
                enginesNode: rootPackage?.engines?.node || null
            },
            nodeEngine,
            versionContract,
            versionContractSha256,
            candidateIdentity,
            requiresGeneratedVersionContract: !versionContract,
            applyWindowsGuidanceOverlay: descriptors.capabilitiesSha256 === MCP_COMPATIBILITY_CONTRACT.windowsAdvancedGuidanceBaselineSha256,
            reason: versionContract
                ? `MCP ${normalized} matches its pinned version-bound contract and will still undergo schema/canary/live validation before commit.`
                : `MCP ${normalized} matches the runtime dependency baseline. A version-bound candidate contract will be generated only after strict schema/canary validation; activation remains fail-closed.`
        };
    } catch (error) {
        return {
            available: false,
            version: normalized,
            reason: `Could not validate MCP ${normalized} against the managed compatibility contract: ${error.message}`
        };
    }
}

async function git(args, options = {}) {
    return execFileAsync('git', args, {
        cwd: options.cwd || MCP_ROOT,
        windowsHide: true,
        timeout: options.timeout || 30000,
        encoding: 'utf8'
    });
}

const MCP_ROOT = DEFAULT_MCP_ROOT;

async function mcpGitState() {
    if (!fs.existsSync(path.join(MCP_ROOT, '.git'))) {
        return {
            available: false,
            reason: 'The installed DaVinci Resolve MCP is not a Git checkout.'
        };
    }

    try {
        const [status, tag, head, remote] = await Promise.all([
            git(['status', '--porcelain=v1', '--untracked-files=all']),
            git(['describe', '--tags', '--abbrev=0', '--match', 'v[0-9]*']).catch(() => ({ stdout: '' })),
            git(['rev-parse', 'HEAD']),
            git(['remote', 'get-url', 'origin'])
        ]);

        return {
            available: true,
            dirty: Boolean(status.stdout.trim()),
            currentTag: tag.stdout.trim() || null,
            head: head.stdout.trim(),
            origin: remote.stdout.trim(),
            dirtyFiles: status.stdout.trim()
                ? status.stdout.trim().split(/\r?\n/).slice(0, 20)
                : []
        };
    } catch (error) {
        return {
            available: false,
            reason: `Could not inspect the MCP Git checkout: ${error.message}`
        };
    }
}

function parseJsonText(text) {
    if (typeof text !== 'string') return null;
    const normalized = text.charCodeAt(0) === 0xFEFF ? text.slice(1) : text;
    const parsed = JSON.parse(normalized);
    return parsed && typeof parsed === 'object' ? parsed : null;
}

function readJsonFile(filePath) {
    try {
        if (!fs.existsSync(filePath)) return null;
        return parseJsonText(fs.readFileSync(filePath, 'utf8'));
    } catch (_error) {
        return null;
    }
}

function readManagedMcpVersion() {
    const marker = readJsonFile(path.join(MCP_ROOT, '.davinci-resolve-mcp-managed.json'));
    const packageJson = readJsonFile(path.join(MCP_ROOT, 'package.json'));
    const candidates = [
        marker?.managed ? marker.version : null,
        packageJson?.name === MCP_NPM_PACKAGE ? packageJson.version : null
    ];

    for (const value of candidates) {
        if (typeof value === 'string' && /^\d+\.\d+\.\d+$/.test(value.trim())) {
            return value.trim();
        }
    }

    return null;
}

function mcpManagedState() {
    const marker = readJsonFile(path.join(MCP_ROOT, '.davinci-resolve-mcp-managed.json'));
    const packageJson = readJsonFile(path.join(MCP_ROOT, 'package.json'));
    const managed = Boolean(marker?.managed && marker.name === MCP_NPM_PACKAGE);
    const packageVersion = packageJson?.name === MCP_NPM_PACKAGE && typeof packageJson.version === 'string'
        ? packageJson.version.trim()
        : null;

    return {
        managed,
        markerVersion: managed && typeof marker.version === 'string' ? marker.version.trim() : null,
        packageVersion,
        installedVersion: readManagedMcpVersion()
    };
}

async function getMcpNpmPackage(version) {
    if (!version) return null;

    // GitHub release tags use the leading `v` (e.g. v4.7.10), while npm
    // package versions are stored without it (4.7.10). The npm registry does
    // not expose a `/package/v4.7.10` endpoint; fetch the package packument
    // once and resolve the exact version from its `versions` map.
    const npmVersion = String(version).trim().replace(/^v/i, '');
    if (!/^\d+\.\d+\.\d+$/.test(npmVersion)) {
        throw new Error(`Invalid npm package version requested: ${version}`);
    }

    let metadata;
    try {
        metadata = await getJson(`${MCP_NPM_REGISTRY}/${MCP_NPM_PACKAGE}`);
    } catch (error) {
        throw new Error(`npm registry metadata lookup failed for ${MCP_NPM_PACKAGE}@${npmVersion}: ${error.message}`);
    }

    const release = metadata?.versions?.[npmVersion];
    if (!release || typeof release !== 'object') {
        throw new Error(`npm registry does not contain ${MCP_NPM_PACKAGE}@${npmVersion}.`);
    }

    const dist = release?.dist;
    if (!dist || typeof dist.tarball !== 'string' || !dist.tarball) {
        throw new Error(`npm registry did not provide a tarball for ${MCP_NPM_PACKAGE}@${npmVersion}.`);
    }

    const integrity = typeof dist.integrity === 'string' ? dist.integrity.trim() : '';
    if (!/^sha512-[A-Za-z0-9+/]+=*$/.test(integrity)) {
        throw new Error(`npm registry did not provide a verifiable SHA-512 integrity value for ${MCP_NPM_PACKAGE}@${npmVersion}.`);
    }

    if (release.name !== MCP_NPM_PACKAGE || release.version !== npmVersion) {
        throw new Error(`npm registry returned an unexpected package identity for ${MCP_NPM_PACKAGE}@${npmVersion}.`);
    }

    return {
        name: release.name,
        version: release.version,
        tarball: dist.tarball,
        integrity
    };
}

async function sha512File(filePath) {
    return new Promise((resolve, reject) => {
        const hash = crypto.createHash('sha512');
        const stream = fs.createReadStream(filePath);
        stream.on('error', reject);
        stream.on('data', (chunk) => hash.update(chunk));
        stream.on('end', () => resolve(hash.digest('base64')));
    });
}

function parseNpmIntegrity(value) {
    const text = String(value || '').trim();
    return text.startsWith('sha512-') ? text.slice('sha512-'.length) : null;
}

function findMcpPackageRoot(extractedRoot, expectedVersion) {
    const matches = [];

    function walk(current, depth) {
        if (depth > 4) return;
        let entries;
        try {
            entries = fs.readdirSync(current, { withFileTypes: true });
        } catch (_error) {
            return;
        }

        for (const entry of entries) {
            const full = path.join(current, entry.name);
            if (!entry.isDirectory()) continue;
            if (entry.name === 'node_modules' || entry.name === 'venv') continue;

            const packageJsonPath = path.join(full, 'package.json');
            if (fs.existsSync(packageJsonPath)) {
                const packageJson = readJsonFile(packageJsonPath);
                const versionMatches = !expectedVersion || packageJson?.version === expectedVersion;
                if (packageJson?.name === MCP_NPM_PACKAGE && versionMatches && fs.existsSync(path.join(full, 'install.py'))) {
                    matches.push(full);
                }
            }

            walk(full, depth + 1);
        }
    }

    const rootPackage = readJsonFile(path.join(extractedRoot, 'package.json'));
    if (rootPackage?.name === MCP_NPM_PACKAGE &&
        (!expectedVersion || rootPackage.version === expectedVersion) &&
        fs.existsSync(path.join(extractedRoot, 'install.py'))) {
        matches.push(extractedRoot);
    }

    walk(extractedRoot, 0);

    const unique = [...new Set(matches.map((item) => path.resolve(item)))];
    if (unique.length !== 1) {
        throw new Error(
            unique.length === 0
                ? `The MCP package archive did not contain the expected ${MCP_NPM_PACKAGE}@${expectedVersion} package root.`
                : `The MCP package archive contained multiple matching package roots; refusing to guess.`
        );
    }

    return unique[0];
}

async function installManagedMcpCompatibilityUpdate(status, { onProgress } = {}) {
    const targetVersion = normalizeMcpSemver(status.latestVersion);
    const compatibility = await inspectMcpCompatibilityBundle(targetVersion);

    if (!targetVersion || !compatibility.available) {
        throw new Error(compatibility.reason || 'No validated MCP compatibility bundle is available.');
    }

    const spec = compatibility.spec;
    const stamp = `${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const workRoot = path.join(ProductPaths.resolveUpdatesRoot, 'MCP', `compat-${targetVersion}-${stamp}`);
    const bundleRoot = path.join(workRoot, 'bundle');
    const sourceExtractRoot = path.join(workRoot, 'source-extracted');
    const pythonImageRoot = path.join(workRoot, 'python-image');
    const advancedImageRoot = path.join(workRoot, 'advanced-image');

    const stagedMcpRoot = `${MCP_ROOT}.aidir-new-${stamp}`;
    const stagedPythonRoot = `${MCP_PYTHON_ROOT}.aidir-new-${stamp}`;
    const backupMcpRoot = `${MCP_ROOT}.aidir-backup-${stamp}`;
    const backupPythonRoot = `${MCP_PYTHON_ROOT}.aidir-backup-${stamp}`;
    const backupStateRoot = path.join(MCP_BACKUP_ROOT, `mcp-${status.installedVersion || 'unknown'}-to-${targetVersion}-${stamp}`);

    const beforeConfigHash = fs.existsSync(MCP_VFX_CONFIG)
        ? await sha256File(MCP_VFX_CONFIG)
        : null;

    const runtimeManifestPath = path.join(ProductPaths.resolveManifestsRoot, 'MCP-PYTHON-RUNTIME-MANIFEST.json');
    const compatibilityManifestInstallPath = path.join(ProductPaths.resolveManifestsRoot, `MCP-COMPATIBILITY-${targetVersion}.json`);
    const pythonArtifactManifestInstallPath = path.join(ProductPaths.resolveManifestsRoot, `MCP-PYTHON-IMMUTABLE-ARTIFACT-MANIFEST-${targetVersion}.json`);
    const advancedManifestInstallPath = path.join(ProductPaths.resolveManifestsRoot, `MCP-ADVANCED-NODE-DEPENDENCY-IMAGE-${targetVersion}.json`);
    const mandatoryAdvancedManifestInstallPath = path.join(
        ProductPaths.resolveManifestsRoot,
        `MCP-ADVANCED-NODE-MANDATORY-DEPENDENCY-IMAGE-${targetVersion}.json`
    );
    const updateStatePath = path.join(ProductPaths.resolveManifestsRoot, 'MCP-UPDATE-STATE.json');

    const manifestPaths = [
        runtimeManifestPath,
        compatibilityManifestInstallPath,
        pythonArtifactManifestInstallPath,
        advancedManifestInstallPath,
        mandatoryAdvancedManifestInstallPath,
        updateStatePath
    ];

    let manifestBackupRows = [];
    let sourceActivated = false;
    let pythonActivated = false;

    await fs.promises.mkdir(workRoot, { recursive: true });

    try {
        onProgress?.({ phase: 'verify', progress: 5, message: `Verifying AI Director MCP ${targetVersion} compatibility bundle...` });

        const bundleHash = (await sha256File(compatibility.bundlePath)).toUpperCase();
        if (bundleHash !== spec.sha256) {
            throw new Error('Compatibility bundle SHA-256 verification failed.');
        }

        await extractArchive(compatibility.bundlePath, bundleRoot);
        await verifyPayloadManifest(bundleRoot, 'MCP compatibility bundle');

        const compatibilityManifestPath = path.join(bundleRoot, spec.compatibilityManifestFilename);
        if ((await sha256File(compatibilityManifestPath)).toUpperCase() !== spec.compatibilityManifestSha256) {
            throw new Error('Compatibility manifest SHA-256 mismatch.');
        }

        const compatibilityManifest = readJsonFile(compatibilityManifestPath);
        if (!compatibilityManifest ||
            compatibilityManifest.managed_mcp_version !== targetVersion ||
            compatibilityManifest.github_source_commit !== spec.sourceCommit ||
            compatibilityManifest.status !== 'CANDIDATE_COMPATIBILITY_BUNDLE_NOT_INSTALLED') {
            throw new Error('Compatibility manifest identity mismatch.');
        }

        const sourceTarball = path.join(bundleRoot, compatibilityManifest.npm_source.filename);
        if ((await sha256File(sourceTarball)).toUpperCase() !== spec.sourceSha256) {
            throw new Error('Compatibility source tarball SHA-256 mismatch.');
        }

        const pythonImageZip = path.join(bundleRoot, compatibilityManifest.python_image.filename);
        const advancedImageZip = path.join(bundleRoot, compatibilityManifest.advanced_node_image.filename);

        if ((await sha256File(pythonImageZip)).toUpperCase() !== spec.pythonImageSha256) {
            throw new Error('Compatibility Python image SHA-256 mismatch.');
        }
        if ((await sha256File(advancedImageZip)).toUpperCase() !== spec.advancedImageSha256) {
            throw new Error('Compatibility Advanced Node image SHA-256 mismatch.');
        }

        onProgress?.({ phase: 'stage', progress: 20, message: `Staging MCP ${targetVersion} source package...` });

        await extractArchive(sourceTarball, sourceExtractRoot);
        const packageRoot = findMcpPackageRoot(sourceExtractRoot, targetVersion);

        await fs.promises.rm(stagedMcpRoot, { recursive: true, force: true });
        await fs.promises.mkdir(stagedMcpRoot, { recursive: true });
        fs.cpSync(packageRoot, stagedMcpRoot, { recursive: true, force: true });

        const sourcePackage = readJsonFile(path.join(stagedMcpRoot, 'package.json'));
        if (sourcePackage?.name !== MCP_NPM_PACKAGE || sourcePackage.version !== targetVersion) {
            throw new Error('Staged MCP source package identity mismatch.');
        }

        const currentLogs = path.join(MCP_ROOT, 'logs');
        if (fs.existsSync(currentLogs)) {
            fs.cpSync(currentLogs, path.join(stagedMcpRoot, 'logs'), { recursive: true, force: true });
        }

        fs.copyFileSync(path.join(bundleRoot, 'requirements.txt'), path.join(stagedMcpRoot, 'requirements.txt'));
        fs.copyFileSync(
            path.join(bundleRoot, 'resolve-advanced-package-lock.json'),
            path.join(stagedMcpRoot, 'resolve-advanced', 'package-lock.json')
        );

        onProgress?.({ phase: 'overlay', progress: 32, message: 'Applying AI Director Windows Advanced guidance overlay...' });
        const productOverlay = await applyWindowsAdvancedGuidanceOverlay({
            stagedMcpRoot,
            spec
        });

        writeJsonFile(path.join(stagedMcpRoot, '.davinci-resolve-mcp-managed.json'), {
            name: MCP_NPM_PACKAGE,
            version: targetVersion,
            managed: true,
            sourceCommit: spec.sourceCommit,
            compatibilityBundleSha256: spec.sha256,
            productOverlay: {
                advancedWindowsGuidanceSha256: productOverlay.afterHash
            },
            updatedAt: new Date().toISOString()
        });

        onProgress?.({ phase: 'deps', progress: 40, message: 'Staging immutable MCP Python dependency image...' });

        await extractArchive(pythonImageZip, pythonImageRoot);
        const pythonStage = await buildMcpPythonRuntimeFromImage({
            imageRoot: pythonImageRoot,
            stageRoot: stagedPythonRoot,
            stagedMcpRoot,
            spec
        });

        onProgress?.({ phase: 'deps', progress: 60, message: 'Staging immutable Resolve Advanced Node dependency image...' });

        await extractArchive(advancedImageZip, advancedImageRoot);
        const advancedStage = await installAdvancedNodeImage({
            imageRoot: advancedImageRoot,
            stagedMcpRoot,
            spec
        });

        onProgress?.({ phase: 'deps', progress: 66, message: 'Applying mandatory product-owned Advanced native dependencies...' });
        const mandatoryAdvancedStage = await installMandatoryAdvancedNodeImage({
            stagedMcpRoot,
            spec
        });

        onProgress?.({ phase: 'verify', progress: 72, message: 'Verifying staged MCP 37/389/18 surfaces, required Advanced dependencies, and optional capability state...' });

        await validateStagedMcpCompatibility({
            workRoot,
            pythonExe: pythonStage.pythonExe,
            pythonRoot: stagedPythonRoot,
            stagedMcpRoot,
            spec
        });

        if (beforeConfigHash !== (fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null)) {
            throw new Error('vfx_mcp.json changed during MCP staging.');
        }

        onProgress?.({ phase: 'backup', progress: 80, message: 'Backing up current MCP source, Python runtime, and manifest state...' });

        await fs.promises.rm(backupMcpRoot, { recursive: true, force: true });
        await fs.promises.rm(backupPythonRoot, { recursive: true, force: true });
        manifestBackupRows = await snapshotManifestFiles(backupStateRoot, manifestPaths);

        onProgress?.({ phase: 'swap', progress: 86, message: `Activating MCP ${targetVersion} compatibility unit...` });

        if (fs.existsSync(MCP_ROOT)) {
            await fs.promises.rename(MCP_ROOT, backupMcpRoot);
        }
        await fs.promises.rename(stagedMcpRoot, MCP_ROOT);
        sourceActivated = true;

        if (fs.existsSync(MCP_PYTHON_ROOT)) {
            await fs.promises.rename(MCP_PYTHON_ROOT, backupPythonRoot);
        }

        // The staged runtime was validated against the staged source path.
        // Rewrite only the path contract before moving it to the stable product root.
        writeMcpPythonPth(stagedPythonRoot, MCP_ROOT);
        await fs.promises.rename(stagedPythonRoot, MCP_PYTHON_ROOT);
        pythonActivated = true;

        const activePackage = readJsonFile(path.join(MCP_ROOT, 'package.json'));
        const activeMarker = readJsonFile(path.join(MCP_ROOT, '.davinci-resolve-mcp-managed.json'));
        if (activePackage?.version !== targetVersion ||
            activeMarker?.version !== targetVersion ||
            activeMarker?.managed !== true ||
            activeMarker?.compatibilityBundleSha256 !== spec.sha256 ||
            activeMarker?.productOverlay?.advancedWindowsGuidanceSha256 !== spec.windowsAdvancedGuidancePatchedSha256) {
            throw new Error('MCP post-activation source identity verification failed.');
        }

        const activeGuidancePath = path.join(MCP_ROOT, WINDOWS_ADVANCED_GUIDANCE_RELATIVE_PATH);
        if ((await sha256File(activeGuidancePath)).toUpperCase() !== spec.windowsAdvancedGuidancePatchedSha256) {
            throw new Error('AI Director Windows Advanced guidance overlay hash mismatch after activation.');
        }

        await assertExactDistributionInventory(
            MCP_PYTHON_EXE,
            MCP_PYTHON_ROOT,
            pythonStage.artifactManifest
        );

        await validateStagedMcpCompatibility({
            workRoot,
            pythonExe: MCP_PYTHON_EXE,
            pythonRoot: MCP_PYTHON_ROOT,
            stagedMcpRoot: MCP_ROOT,
            spec
        });

        const afterConfigHash = fs.existsSync(MCP_VFX_CONFIG)
            ? await sha256File(MCP_VFX_CONFIG)
            : null;
        if (beforeConfigHash !== afterConfigHash) {
            throw new Error('vfx_mcp.json integrity check failed after MCP compatibility activation.');
        }

        fs.mkdirSync(ProductPaths.resolveManifestsRoot, { recursive: true });
        fs.copyFileSync(compatibilityManifestPath, compatibilityManifestInstallPath);
        fs.copyFileSync(pythonStage.manifestPath, pythonArtifactManifestInstallPath);
        fs.copyFileSync(advancedStage.manifestPath, advancedManifestInstallPath);
        fs.copyFileSync(mandatoryAdvancedStage.manifestPath, mandatoryAdvancedManifestInstallPath);

        writeJsonFile(runtimeManifestPath, {
            schema_version: 3,
            component: 'DaVinci Resolve AI Director product-owned MCP Python runtime',
            ownership: 'DaVinciResolveAIDirector',
            python_version: ProductPaths.resolveMcpPythonVersion,
            mcp_version: targetVersion,
            runtime_root: path.relative(ProductPaths.resolveRoot, MCP_PYTHON_ROOT),
            image_source: 'version-bound immutable MCP compatibility bundle',
            compatibility_bundle: {
                filename: spec.filename,
                sha256: spec.sha256,
                source_commit: spec.sourceCommit,
                python_image_sha256: spec.pythonImageSha256,
                python_artifact_manifest_sha256: spec.pythonManifestSha256,
                advanced_node_image_sha256: spec.advancedImageSha256,
                product_overlay_advanced_windows_guidance_sha256: spec.windowsAdvancedGuidancePatchedSha256
            },
            distribution_count: spec.distributionCount,
            system_python_required: false,
            runtime_pip_required: false,
            legacy_mcp_venv_required: false,
            activation_network_required: false
        });

        writeJsonFile(updateStatePath, {
            schema_version: 1,
            installed_at: new Date().toISOString(),
            from_version: status.installedVersion,
            to_version: targetVersion,
            source_commit: spec.sourceCommit,
            compatibility_bundle_sha256: spec.sha256,
            product_overlay: {
                advanced_windows_guidance_sha256: spec.windowsAdvancedGuidancePatchedSha256
            },
            source_backup_root: backupMcpRoot,
            python_backup_root: backupPythonRoot,
            manifest_backup_root: backupStateRoot,
            vfx_mcp_sha256: afterConfigHash,
            expected_tools: {
                compound: spec.compoundTools,
                full: spec.fullTools,
                advanced: spec.advancedTools,
                discovered_authorized: 444,
                model_facing_semantic: 55
            }
        });

        onProgress?.({ phase: 'health', progress: 96, message: `MCP ${targetVersion} activated; validating restarted AI Director runtime and cache prime...` });

        return {
            ok: true,
            component: 'mcp',
            updated: true,
            fromVersion: status.installedVersion,
            toVersion: targetVersion,
            installMode: 'managed-compatibility-bundle',
            compatibilityBundleSha256: spec.sha256,
            productOverlaySha256: spec.windowsAdvancedGuidancePatchedSha256,
            resolveRestartRequired: false,
            backupRoot: backupStateRoot,
            sourceBackupRoot: backupMcpRoot,
            pythonBackupRoot: backupPythonRoot,
            previousVfxConfigSha256: beforeConfigHash,
            expectedBackendToolCount: 444,
            provisionalUntilRuntimeHealth: true
        };
    } catch (error) {
        onProgress?.({ phase: 'rollback', progress: 92, message: 'MCP compatibility update failed; restoring previous source and Python runtime...' });

        let rollbackError = null;
        try {
            if (pythonActivated && fs.existsSync(backupPythonRoot)) {
                const failedPythonRoot = `${MCP_PYTHON_ROOT}.aidir-failed-${stamp}`;
                if (fs.existsSync(MCP_PYTHON_ROOT)) {
                    await fs.promises.rename(MCP_PYTHON_ROOT, failedPythonRoot);
                }
                await fs.promises.rename(backupPythonRoot, MCP_PYTHON_ROOT);
            } else if (fs.existsSync(backupPythonRoot) && !fs.existsSync(MCP_PYTHON_ROOT)) {
                await fs.promises.rename(backupPythonRoot, MCP_PYTHON_ROOT);
            }

            if (sourceActivated && fs.existsSync(backupMcpRoot)) {
                const failedMcpRoot = `${MCP_ROOT}.aidir-failed-${stamp}`;
                if (fs.existsSync(MCP_ROOT)) {
                    await fs.promises.rename(MCP_ROOT, failedMcpRoot);
                }
                await fs.promises.rename(backupMcpRoot, MCP_ROOT);
            } else if (fs.existsSync(backupMcpRoot) && !fs.existsSync(MCP_ROOT)) {
                await fs.promises.rename(backupMcpRoot, MCP_ROOT);
            }

            if (manifestBackupRows.length) {
                await restoreManifestFiles(manifestBackupRows);
            }

            const restoredConfigHash = fs.existsSync(MCP_VFX_CONFIG)
                ? await sha256File(MCP_VFX_CONFIG)
                : null;
            if (beforeConfigHash !== restoredConfigHash) {
                throw new Error('vfx_mcp.json was not restored to its pre-update hash.');
            }
        } catch (restoreError) {
            rollbackError = restoreError;
        }

        if (rollbackError) {
            throw new Error(
                `${error instanceof Error ? error.message : String(error)} Rollback also failed: ${rollbackError.message}`
            );
        }
        throw error;
    } finally {
        await fs.promises.rm(workRoot, { recursive: true, force: true }).catch(() => {});
        await fs.promises.rm(stagedMcpRoot, { recursive: true, force: true }).catch(() => {});
        await fs.promises.rm(stagedPythonRoot, { recursive: true, force: true }).catch(() => {});
    }
}

async function installManagedMcpCompatibleRelease(status, { onProgress } = {}) {
    const targetVersion = normalizeMcpSemver(status.latestVersion);
    const releaseContract = status.releaseContract;
    if (!targetVersion || !releaseContract?.available) {
        throw new Error(releaseContract.reason || 'The MCP release does not match the validated managed contract.');
    }

    const stamp = `${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const workRoot = path.join(ProductPaths.resolveUpdatesRoot, 'MCP', `compatible-${targetVersion}-${stamp}`);
    const archivePath = path.join(workRoot, `davinci-resolve-mcp-${targetVersion}-${releaseContract.sourceCommit.slice(0, 12)}.tar.gz`);
    const sourceExtractRoot = path.join(workRoot, 'source-extracted');
    const stagedMcpRoot = `${MCP_ROOT}.aidir-new-${stamp}`;
    const stagedPythonRoot = `${MCP_PYTHON_ROOT}.aidir-new-${stamp}`;
    const backupMcpRoot = `${MCP_ROOT}.aidir-backup-${stamp}`;
    const backupPythonRoot = `${MCP_PYTHON_ROOT}.aidir-backup-${stamp}`;
    const backupStateRoot = path.join(MCP_BACKUP_ROOT, `mcp-${status.installedVersion || 'unknown'}-to-${targetVersion}-${stamp}`);

    const beforeConfigHash = fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null;
    const runtimeManifestPath = path.join(ProductPaths.resolveManifestsRoot, 'MCP-PYTHON-RUNTIME-MANIFEST.json');
    const compatibilityManifestInstallPath = path.join(ProductPaths.resolveManifestsRoot, `MCP-COMPATIBILITY-${targetVersion}.json`);
    const strictContractInstallPath = path.join(ProductPaths.resolveManifestsRoot, `MCP-COMPATIBILITY-CONTRACT-${targetVersion}.json`);
    const dependencyReuseRecordPath = path.join(ProductPaths.resolveManifestsRoot, `MCP-DEPENDENCY-REUSE-${targetVersion}.json`);
    const updateStatePath = path.join(ProductPaths.resolveManifestsRoot, 'MCP-UPDATE-STATE.json');
    const manifestPaths = [runtimeManifestPath, compatibilityManifestInstallPath, strictContractInstallPath, dependencyReuseRecordPath, updateStatePath];

    let manifestBackupRows = [];
    let sourceActivated = false;
    let pythonActivated = false;
    let failurePhase = 'preflight';
    let transactionPrepared = false;

    const preserveFailureEvidence = async (error, rollbackStatus) => {
        let failureRoot = null;
        let evidenceWriteError = null;
        try {
            failureRoot = path.join(
                MCP_FAILURE_ROOT,
                `mcp-${status.installedVersion || 'unknown'}-to-${targetVersion}-${stamp}`
            );
            await fs.promises.mkdir(failureRoot, { recursive: true });

            const errorStdout = typeof error?.stdout === 'string' ? error.stdout : '';
            const errorStderr = typeof error?.stderr === 'string' ? error.stderr : '';
            if (errorStdout) fs.writeFileSync(path.join(failureRoot, 'ERROR.stdout.txt'), errorStdout, 'utf8');
            if (errorStderr) fs.writeFileSync(path.join(failureRoot, 'ERROR.stderr.txt'), errorStderr, 'utf8');

            writeJsonFile(path.join(failureRoot, 'MCP-UPDATE-FAILURE.json'), {
                schema_version: 1,
                status: 'MCP_UPDATE_FAILED_EVIDENCE_PRESERVED',
                captured_at: new Date().toISOString(),
                from_version: status.installedVersion || null,
                target_version: targetVersion,
                source_commit: releaseContract.sourceCommit,
                failure_phase: failurePhase,
                error: error instanceof Error ? error.message : String(error),
                stack: error instanceof Error ? error.stack || null : null,
                source_activated: sourceActivated,
                python_activated: pythonActivated,
                manifest_backup_started: manifestBackupRows.length > 0,
                rollback: rollbackStatus,
                paths: {
                    work_root: workRoot,
                    staged_mcp_root: stagedMcpRoot,
                    staged_python_root: stagedPythonRoot,
                    backup_mcp_root: backupMcpRoot,
                    backup_python_root: backupPythonRoot,
                    backup_state_root: backupStateRoot
                },
                candidate_identity: releaseContract.candidateIdentity || null,
                before_vfx_mcp_sha256: beforeConfigHash
            });
        } catch (evidenceError) {
            evidenceWriteError = evidenceError instanceof Error ? evidenceError.message : String(evidenceError);
        }
        return { failureRoot, evidenceWriteError };
    };

    await fs.promises.mkdir(workRoot, { recursive: true });
    try {
        failurePhase = 'download';
        onProgress?.({ phase: 'download', progress: 5, message: `Downloading MCP ${targetVersion} source pinned to ${releaseContract.sourceCommit.slice(0, 12)}...` });
        await downloadFile(
            `https://codeload.github.com/${MCP_REPO}/tar.gz/${releaseContract.sourceCommit}`,
            archivePath,
            ({ received, total }) => {
                const progress = total ? 5 + Math.round((received / total) * 15) : 10;
                onProgress?.({ phase: 'download', progress, message: `Downloading MCP ${targetVersion} source by immutable commit...` });
            }
        );

        failurePhase = 'source-stage';
        onProgress?.({ phase: 'stage', progress: 22, message: `Staging MCP ${targetVersion} source...` });
        const archiveSha256 = (await sha256File(archivePath)).toUpperCase();
        const pinnedCommitArchiveSha = String(
            releaseContract.versionContract?.commit_archive_sha256 || ''
        ).toUpperCase();
        if (pinnedCommitArchiveSha && archiveSha256 !== pinnedCommitArchiveSha) {
            throw new Error(`MCP ${targetVersion} commit-addressed source archive SHA-256 mismatch against its version-bound contract.`);
        }
        await extractArchive(archivePath, sourceExtractRoot);
        const packageRoot = findMcpPackageRoot(sourceExtractRoot, targetVersion);

        const descriptorFiles = {
            sourcePackage: path.join(packageRoot, 'package.json'),
            requirements: path.join(packageRoot, 'requirements.txt'),
            advancedPackage: path.join(packageRoot, 'resolve-advanced', 'package.json'),
            advancedLock: path.join(packageRoot, 'resolve-advanced', 'package-lock.json'),
            capabilities: path.join(packageRoot, WINDOWS_ADVANCED_GUIDANCE_RELATIVE_PATH)
        };
        const descriptorHashes = {
            sourcePackageSha256: (await sha256File(descriptorFiles.sourcePackage)).toUpperCase(),
            requirementsSha256: (await sha256File(descriptorFiles.requirements)).toUpperCase(),
            advancedPackageSha256: (await sha256File(descriptorFiles.advancedPackage)).toUpperCase(),
            advancedLockSha256: (await sha256File(descriptorFiles.advancedLock)).toUpperCase(),
            capabilitiesSha256: (await sha256File(descriptorFiles.capabilities)).toUpperCase()
        };
        for (const key of ['sourcePackageSha256', 'requirementsSha256', 'advancedPackageSha256', 'advancedLockSha256', 'capabilitiesSha256']) {
            if (descriptorHashes[key] !== releaseContract.descriptors[key]) {
                throw new Error(`MCP ${targetVersion} descriptor changed between update check and staging (${key}).`);
            }
        }

        await fs.promises.rm(stagedMcpRoot, { recursive: true, force: true });
        await fs.promises.mkdir(stagedMcpRoot, { recursive: true });
        fs.cpSync(packageRoot, stagedMcpRoot, { recursive: true, force: true });

        let productOverlay = { changed: false, afterHash: descriptorHashes.capabilitiesSha256 };
        if (releaseContract.applyWindowsGuidanceOverlay) {
            productOverlay = await applyWindowsAdvancedGuidanceOverlay({
                stagedMcpRoot,
                spec: {
                    windowsAdvancedGuidanceBaselineSha256: MCP_COMPATIBILITY_CONTRACT.windowsAdvancedGuidanceBaselineSha256,
                    windowsAdvancedGuidancePatchedSha256: MCP_COMPATIBILITY_CONTRACT.windowsAdvancedGuidancePatchedSha256
                }
            });
        }

        writeJsonFile(path.join(stagedMcpRoot, '.davinci-resolve-mcp-managed.json'), {
            name: MCP_NPM_PACKAGE,
            version: targetVersion,
            managed: true,
            sourceCommit: releaseContract.sourceCommit,
            compatibilityMode: 'descriptor-compatible-release',
            dependencyContract: {
                requirementsSha256: MCP_COMPATIBILITY_CONTRACT.requirementsSha256,
                advancedPackageSha256: MCP_COMPATIBILITY_CONTRACT.advancedPackageSha256,
                advancedLockSha256: MCP_COMPATIBILITY_CONTRACT.advancedLockSha256
            },
            productOverlay: productOverlay.changed ? { advancedWindowsGuidanceSha256: productOverlay.afterHash } : null,
            updatedAt: new Date().toISOString()
        });

        failurePhase = 'python-stage';
        onProgress?.({ phase: 'deps', progress: 40, message: 'Cloning the accepted product-owned MCP Python runtime into staging...' });
        if (!fs.existsSync(MCP_PYTHON_EXE)) throw new Error('Accepted product-owned MCP Python runtime is missing.');
        await fs.promises.rm(stagedPythonRoot, { recursive: true, force: true });
        fs.cpSync(MCP_PYTHON_ROOT, stagedPythonRoot, { recursive: true, force: true });
        writeMcpPythonPth(stagedPythonRoot, stagedMcpRoot);
        const stagedPythonExe = process.platform === 'win32' ? path.join(stagedPythonRoot, 'python.exe') : path.join(stagedPythonRoot, 'bin', 'python');

        failurePhase = 'advanced-dependency-stage';
        onProgress?.({ phase: 'deps', progress: 58, message: 'Applying accepted product-owned mandatory Advanced dependencies...' });
        const compatibilitySpec = {
            advancedPackageSha256: MCP_COMPATIBILITY_CONTRACT.advancedPackageSha256,
            advancedLockSha256: MCP_COMPATIBILITY_CONTRACT.advancedLockSha256,
            mandatoryAdvancedSharpVersion: MCP_COMPATIBILITY_CONTRACT.mandatoryAdvancedSharpVersion,
            mandatoryAdvancedBetterSqlite3Version: MCP_COMPATIBILITY_CONTRACT.mandatoryAdvancedBetterSqlite3Version,
            compoundTools: MCP_COMPATIBILITY_CONTRACT.compoundTools,
            fullTools: MCP_COMPATIBILITY_CONTRACT.fullTools,
            advancedTools: MCP_COMPATIBILITY_CONTRACT.advancedTools
        };
        const mandatoryAdvancedStage = await installMandatoryAdvancedNodeImage({ stagedMcpRoot, spec: compatibilitySpec });

        failurePhase = 'accepted-runtime-validation';
        onProgress?.({ phase: 'verify', progress: 66, message: 'Snapshotting accepted MCP tool semantics for compatibility comparison...' });
        const acceptedValidation = await validateStagedMcpCompatibility({
            workRoot,
            pythonExe: MCP_PYTHON_EXE,
            pythonRoot: MCP_PYTHON_ROOT,
            stagedMcpRoot: MCP_ROOT,
            spec: compatibilitySpec
        });
        const acceptedSurfaceContract = {
            compound: acceptedValidation.surfaces.compound,
            full: acceptedValidation.surfaces.full,
            advanced: acceptedValidation.surfaces.advanced
        };

        failurePhase = 'candidate-runtime-validation';
        onProgress?.({ phase: 'verify', progress: 70, message: 'Validating candidate MCP surfaces, accepted tool semantics, required Advanced dependencies, and optional capability state before activation...' });
        const preSwapValidation = await validateStagedMcpCompatibility({
            workRoot,
            pythonExe: stagedPythonExe,
            pythonRoot: stagedPythonRoot,
            stagedMcpRoot,
            spec: compatibilitySpec,
            acceptedSurfaceContract
        });

        if (beforeConfigHash !== (fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null)) {
            throw new Error('vfx_mcp.json changed during pre-activation MCP staging.');
        }

        failurePhase = 'candidate-contract-materialization';
        const candidateContractPath = path.join(workRoot, `MCP-CANDIDATE-CONTRACT-${targetVersion}.json`);
        writeJsonFile(candidateContractPath, {
            schema_version: 1,
            status: 'PRE_SWAP_VALIDATED_PENDING_LIVE_HEALTH',
            managed_mcp_version: targetVersion,
            github_tag: `v${targetVersion}`,
            github_source_commit: releaseContract.sourceCommit,
            source_archive_sha256: archiveSha256,
            version_bound_base_contract: releaseContract.versionContract ? {
                path: releaseContract.versionContract.contractPath,
                sha256: releaseContract.versionContractSha256
            } : null,
            node_engine: releaseContract.nodeEngine,
            descriptors: descriptorHashes,
            semantic_engine: MCP_SEMANTIC_ENGINE.ENGINE_ID,
            accepted_surface_contract: acceptedSurfaceContract,
            candidate_surface_contract: {
                compound: preSwapValidation.surfaces.compound.tools,
                full: preSwapValidation.surfaces.full.tools,
                advanced: preSwapValidation.surfaces.advanced.tools
            },
            fixed_model_facing_surface: { compound: 37, advanced: 18, total: 55 },
            full_surface_policy: 'existing tool contracts directionally schema-compatible; additions allowed internally only',
            read_only_canary: preSwapValidation.surfaces.compound.canary,
            advanced_capabilities: preSwapValidation.surfaces.advanced.capabilities
        });
        const candidateContractSha256 = (await sha256File(candidateContractPath)).toUpperCase();

        failurePhase = 'backup';
        onProgress?.({ phase: 'backup', progress: 80, message: 'Backing up the accepted MCP source, Python runtime, and manifests...' });
        await fs.promises.rm(backupMcpRoot, { recursive: true, force: true });
        await fs.promises.rm(backupPythonRoot, { recursive: true, force: true });
        manifestBackupRows = await snapshotManifestFiles(backupStateRoot, manifestPaths);

        failurePhase = 'swap';
        onProgress?.({ phase: 'swap', progress: 86, message: `Activating pre-validated MCP ${targetVersion}...` });
        if (fs.existsSync(MCP_ROOT)) await fs.promises.rename(MCP_ROOT, backupMcpRoot);
        await fs.promises.rename(stagedMcpRoot, MCP_ROOT);
        sourceActivated = true;
        if (fs.existsSync(MCP_PYTHON_ROOT)) await fs.promises.rename(MCP_PYTHON_ROOT, backupPythonRoot);
        writeMcpPythonPth(stagedPythonRoot, MCP_ROOT);
        await fs.promises.rename(stagedPythonRoot, MCP_PYTHON_ROOT);
        pythonActivated = true;

        const activePackage = readJsonFile(path.join(MCP_ROOT, 'package.json'));
        const activeMarker = readJsonFile(path.join(MCP_ROOT, '.davinci-resolve-mcp-managed.json'));
        if (activePackage?.version !== targetVersion || activeMarker?.version !== targetVersion || activeMarker?.sourceCommit !== releaseContract.sourceCommit) {
            throw new Error('MCP post-activation source identity verification failed.');
        }

        failurePhase = 'post-swap-validation';
        const postSwapValidation = await validateStagedMcpCompatibility({
            workRoot,
            pythonExe: MCP_PYTHON_EXE,
            pythonRoot: MCP_PYTHON_ROOT,
            stagedMcpRoot: MCP_ROOT,
            spec: compatibilitySpec,
            acceptedSurfaceContract
        });
        const afterConfigHash = fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null;
        if (beforeConfigHash !== afterConfigHash) throw new Error('vfx_mcp.json integrity check failed after MCP activation.');

        failurePhase = 'manifest-commit';
        fs.mkdirSync(ProductPaths.resolveManifestsRoot, { recursive: true });
        fs.copyFileSync(candidateContractPath, strictContractInstallPath);
        const sourceMandatoryManifestHash = (await sha256File(mandatoryAdvancedStage.manifestPath)).toUpperCase();
        const sourceMandatoryManifest = readJsonFile(mandatoryAdvancedStage.manifestPath);
        writeJsonFile(dependencyReuseRecordPath, {
            schema_version: 1,
            status: 'ACTIVE_IMMUTABLE_DEPENDENCY_REUSE',
            managed_mcp_version: targetVersion,
            github_source_commit: releaseContract.sourceCommit,
            source_dependency_image: {
                managed_mcp_version: sourceMandatoryManifest?.managed_mcp_version || '4.8.20',
                source_commit: sourceMandatoryManifest?.source_commit || null,
                manifest_path: mandatoryAdvancedStage.manifestPath,
                manifest_sha256: sourceMandatoryManifestHash,
                package_json_sha256: MCP_COMPATIBILITY_CONTRACT.advancedPackageSha256,
                package_lock_sha256: MCP_COMPATIBILITY_CONTRACT.advancedLockSha256
            },
            validated_against_candidate: true,
            candidate_descriptors: descriptorHashes,
            version_bound_contract: {
                preinstalled: Boolean(releaseContract.versionContract),
                contract_sha256: releaseContract.versionContractSha256 || null,
                strict_candidate_contract_sha256: candidateContractSha256,
                generated_source_archive_sha256: archiveSha256
            },
            pre_swap_validation: {
                compound: preSwapValidation.surfaces.compound.count,
                full: preSwapValidation.surfaces.full.count,
                advanced: preSwapValidation.surfaces.advanced.count,
                resolve_control_get_page: Boolean(preSwapValidation.surfaces.compound.canary?.ok)
            }
        });

        writeJsonFile(compatibilityManifestInstallPath, {
            schema_version: 2,
            status: 'ACTIVE_STRICT_VERSION_BOUND_COMPATIBILITY_CONTRACT',
            component: 'DaVinci Resolve MCP managed compatibility record',
            managed_mcp_version: targetVersion,
            github_tag: `v${targetVersion}`,
            github_source_commit: releaseContract.sourceCommit,
            source_archive_sha256: (await sha256File(archivePath)).toUpperCase(),
            dependency_contract: { ...MCP_COMPATIBILITY_CONTRACT },
            candidate_descriptors: descriptorHashes,
            version_bound_contract: {
                preinstalled: Boolean(releaseContract.versionContract),
                contract_sha256: releaseContract.versionContractSha256 || null,
                strict_candidate_contract_sha256: candidateContractSha256,
                source_archive_sha256: archiveSha256
            },
            accepted_surfaces: acceptedValidation.surfaces,
            pre_swap_surfaces: preSwapValidation.surfaces,
            post_swap_surfaces: postSwapValidation.surfaces,
            product_overlay_sha256: productOverlay.changed ? productOverlay.afterHash : null
        });
        writeJsonFile(runtimeManifestPath, {
            schema_version: 4,
            component: 'DaVinci Resolve AI Director product-owned MCP Python runtime',
            ownership: 'DaVinciResolveAIDirector',
            python_version: ProductPaths.resolveMcpPythonVersion,
            mcp_version: targetVersion,
            runtime_root: path.relative(ProductPaths.resolveRoot, MCP_PYTHON_ROOT),
            image_source: 'reused accepted immutable Python dependency contract after exact requirements match',
            dependency_reuse_record: path.basename(dependencyReuseRecordPath),
            source_commit: releaseContract.sourceCommit,
            dependency_contract: {
                requirements_sha256: MCP_COMPATIBILITY_CONTRACT.requirementsSha256,
                network_required_for_activation: false,
                system_python_required: false
            }
        });
        writeJsonFile(updateStatePath, {
            schema_version: 2,
            installed_at: new Date().toISOString(),
            from_version: status.installedVersion,
            to_version: targetVersion,
            source_commit: releaseContract.sourceCommit,
            candidate_identity: releaseContract.candidateIdentity,
            strict_candidate_contract_sha256: candidateContractSha256,
            install_mode: 'managed-compatible-release',
            source_backup_root: backupMcpRoot,
            python_backup_root: backupPythonRoot,
            manifest_backup_root: backupStateRoot,
            vfx_mcp_sha256: afterConfigHash,
            expected_tools: {
                compound: postSwapValidation.surfaces.compound.count,
                full: postSwapValidation.surfaces.full.count,
                advanced: postSwapValidation.surfaces.advanced.count,
                discovered_authorized: postSwapValidation.surfaces.compound.count + postSwapValidation.surfaces.full.count + postSwapValidation.surfaces.advanced.count
            }
        });

        failurePhase = 'provisional-complete';
        transactionPrepared = true;
        return {
            ok: true,
            component: 'mcp',
            updated: true,
            fromVersion: status.installedVersion,
            toVersion: targetVersion,
            sourceCommit: releaseContract.sourceCommit,
            candidateIdentity: releaseContract.candidateIdentity,
            strictCandidateContractSha256: candidateContractSha256,
            installMode: 'managed-compatible-release',
            productOverlaySha256: productOverlay.changed ? productOverlay.afterHash : null,
            resolveRestartRequired: false,
            backupRoot: backupStateRoot,
            sourceBackupRoot: backupMcpRoot,
            pythonBackupRoot: backupPythonRoot,
            previousVfxConfigSha256: beforeConfigHash,
            expectedBackendToolCount: postSwapValidation.surfaces.compound.count + postSwapValidation.surfaces.full.count + postSwapValidation.surfaces.advanced.count,
            provisionalUntilRuntimeHealth: true
        };
    } catch (error) {
        const rollbackRequired = Boolean(
            sourceActivated ||
            pythonActivated ||
            manifestBackupRows.length ||
            fs.existsSync(backupMcpRoot) ||
            fs.existsSync(backupPythonRoot)
        );

        let rollbackStatus = {
            required: rollbackRequired,
            attempted: false,
            passed: !rollbackRequired,
            error: null
        };

        if (!rollbackRequired) {
            onProgress?.({
                phase: 'rejected',
                progress: 92,
                message: `MCP ${targetVersion} rejected before activation during ${failurePhase}; accepted ${status.installedVersion || 'runtime'} remains unchanged.`
            });
        } else {
            onProgress?.({
                phase: 'rollback',
                progress: 92,
                message: `MCP ${targetVersion} failed during ${failurePhase}; restoring the accepted runtime...`
            });

            rollbackStatus.attempted = true;
            try {
                if (pythonActivated && fs.existsSync(backupPythonRoot)) {
                    const failedPythonRoot = `${MCP_PYTHON_ROOT}.aidir-failed-${stamp}`;
                    if (fs.existsSync(failedPythonRoot)) {
                        throw new Error(`Rollback diagnostic Python root already exists: ${failedPythonRoot}`);
                    }
                    if (fs.existsSync(MCP_PYTHON_ROOT)) {
                        await fs.promises.rename(MCP_PYTHON_ROOT, failedPythonRoot);
                    }
                    await fs.promises.rename(backupPythonRoot, MCP_PYTHON_ROOT);
                } else if (fs.existsSync(backupPythonRoot) && !fs.existsSync(MCP_PYTHON_ROOT)) {
                    await fs.promises.rename(backupPythonRoot, MCP_PYTHON_ROOT);
                }

                if (sourceActivated && fs.existsSync(backupMcpRoot)) {
                    const failedMcpRoot = `${MCP_ROOT}.aidir-failed-${stamp}`;
                    if (fs.existsSync(failedMcpRoot)) {
                        throw new Error(`Rollback diagnostic MCP root already exists: ${failedMcpRoot}`);
                    }
                    if (fs.existsSync(MCP_ROOT)) {
                        await fs.promises.rename(MCP_ROOT, failedMcpRoot);
                    }
                    await fs.promises.rename(backupMcpRoot, MCP_ROOT);
                } else if (fs.existsSync(backupMcpRoot) && !fs.existsSync(MCP_ROOT)) {
                    await fs.promises.rename(backupMcpRoot, MCP_ROOT);
                }

                if (manifestBackupRows.length) await restoreManifestFiles(manifestBackupRows);

                const restoredConfigHash = fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null;
                if (beforeConfigHash !== restoredConfigHash) {
                    throw new Error('vfx_mcp.json was not restored to its pre-update hash.');
                }

                const restoredPackage = readJsonFile(path.join(MCP_ROOT, 'package.json'));
                const restoredMarker = readJsonFile(path.join(MCP_ROOT, '.davinci-resolve-mcp-managed.json'));
                const expectedVersion = normalizeMcpSemver(status.installedVersion);
                if (expectedVersion &&
                    (restoredPackage?.version !== expectedVersion || restoredMarker?.version !== expectedVersion)) {
                    throw new Error(
                        `Accepted MCP identity was not restored (expected ${expectedVersion}, package=${restoredPackage?.version || 'missing'}, marker=${restoredMarker?.version || 'missing'}).`
                    );
                }
                if (!fs.existsSync(MCP_PYTHON_EXE)) {
                    throw new Error('Accepted MCP Python runtime was not restored.');
                }

                rollbackStatus.passed = true;
            } catch (restoreError) {
                rollbackStatus.passed = false;
                rollbackStatus.error = restoreError instanceof Error ? restoreError.message : String(restoreError);
            }
        }

        const evidence = await preserveFailureEvidence(error, rollbackStatus);
        const originalMessage = error instanceof Error ? error.message : String(error);
        const evidenceSuffix = evidence.failureRoot
            ? ` Diagnostic evidence preserved at ${evidence.failureRoot}.`
            : evidence.evidenceWriteError
                ? ` Diagnostic evidence write also failed: ${evidence.evidenceWriteError}.`
                : '';

        if (rollbackStatus.required && !rollbackStatus.passed) {
            throw new Error(
                `${originalMessage} Rollback also failed: ${rollbackStatus.error}.${evidenceSuffix}`
            );
        }

        throw new Error(
            `${originalMessage} Failure phase: ${failurePhase}.${evidenceSuffix}`
        );
    } finally {
        if (transactionPrepared) {
            await fs.promises.rm(workRoot, { recursive: true, force: true }).catch(() => {});
            await fs.promises.rm(stagedMcpRoot, { recursive: true, force: true }).catch(() => {});
            await fs.promises.rm(stagedPythonRoot, { recursive: true, force: true }).catch(() => {});
        }
    }
}

async function checkMcpUpdates() {
    const managedState = mcpManagedState();
    const local = managedState.managed
        ? { available: true, managed: true, currentTag: managedState.installedVersion, dirty: false, origin: null, dirtyFiles: [] }
        : await mcpGitState();

    const latest = await getJson(`https://api.github.com/repos/${MCP_REPO}/releases/latest`);
    const latestVersion = latest?.tag_name || null;
    const installedVersion = managedState.installedVersion || local.currentTag || null;
    const comparison = compareReleaseTags(installedVersion, latestVersion);
    const updateAvailable = comparison === -1;
    let installAvailable = false;
    let installReason = 'No newer release is available.';
    let installMode = managedState.managed ? 'managed-package' : (local.available ? 'git-fast-forward' : 'unavailable');
    let releaseContract = null;
    let candidateIdentity = null;

    if (updateAvailable) {
        if (managedState.managed) {
            const compatibility = await inspectMcpCompatibilityBundle(latestVersion);
            if (compatibility.available) {
                installAvailable = true;
                installMode = 'managed-compatibility-bundle';
                candidateIdentity = {
                    version: compatibility.version,
                    sourceCommit: compatibility.spec.sourceCommit,
                    enginesNode: null,
                    sourcePackageSha256: null,
                    requirementsSha256: MCP_COMPATIBILITY_CONTRACT.requirementsSha256,
                    advancedPackageSha256: compatibility.spec.advancedPackageSha256,
                    advancedLockSha256: compatibility.spec.advancedLockSha256,
                    capabilitiesSha256: compatibility.spec.windowsAdvancedGuidancePatchedSha256,
                    versionContractSha256: compatibility.spec.sha256,
                    sourceArchiveSha256: compatibility.spec.sourceSha256
                };
                installReason = `Validated AI Director compatibility bundle is installed for MCP ${compatibility.version}; source, Python, and Advanced dependencies will update as one transaction.`;
            } else {
                releaseContract = await inspectMcpReleaseContract(latestVersion);
                if (releaseContract.available) {
                    installAvailable = true;
                    installMode = 'managed-compatible-release';
                    candidateIdentity = releaseContract.candidateIdentity;
                    installReason = `${releaseContract.reason} The candidate must pass exact model-facing schema contracts, the read-only Resolve canary, and post-swap live health before commit.`;
                } else {
                    installAvailable = false;
                    installMode = 'contract-review-required';
                    installReason = releaseContract.reason;
                }
            }
        } else {
            installAvailable = false;
            installMode = 'legacy-source-blocked';
            installReason = 'Legacy Git-based MCP source updates are disabled because they cannot atomically bind source, Python, and Advanced dependency images. Migrate to the managed package before updating.';
        }
    }

    return {
        component: 'mcp',
        repo: MCP_REPO,
        root: MCP_ROOT,
        installedVersion,
        latestVersion,
        updateAvailable,
        installAvailable,
        installReason,
        installMode,
        managed: managedState.managed,
        packageVersion: managedState.packageVersion || null,
        compatibilityBundle: mcpCompatibilitySpec(latestVersion)
            ? {
                filename: mcpCompatibilitySpec(latestVersion).filename,
                sha256: mcpCompatibilitySpec(latestVersion).sha256
            }
            : null,
        candidateIdentity,
        releaseContract: installMode === 'managed-compatible-release' ? releaseContract : null,
        compatibilityPolicy: installMode === 'managed-compatible-release'
            ? { mode: 'strict-version-bound-runtime-validation', versionIndependentEngine: true, modelFacingSurfaceFixed: true }
            : null,
        dirty: Boolean(local.dirty),
        dirtyFiles: local.dirtyFiles || [],
        origin: local.origin || null,
        releaseUrl: latest?.html_url || `https://github.com/${MCP_REPO}/releases`
    };
}

async function checkAll() {
    const [llama, mcp] = await Promise.all([
        checkLlamaUpdates(),
        checkMcpUpdates()
    ]);
    return {
        checkedAt: new Date().toISOString(),
        llama,
        mcp
    };
}

function parseSha256Digest(digest) {
    const value = String(digest || '').trim().toLowerCase();
    return value.startsWith('sha256:') ? value.slice(7) : null;
}

async function extractArchive(archivePath, destination) {
    await fs.promises.mkdir(destination, { recursive: true });

    try {
        await execFileAsync('tar', ['-xf', archivePath, '-C', destination], {
            windowsHide: true,
            timeout: 120000,
            encoding: 'utf8'
        });
        return;
    } catch (tarError) {
        if (process.platform !== 'win32' || !/\.zip$/i.test(archivePath)) {
            throw new Error(`Could not extract ${path.basename(archivePath)}: ${tarError.message}`);
        }

        const psCommand = [
            '$ErrorActionPreference = "Stop";',
            'Expand-Archive -LiteralPath $env:AIDIR_ARCHIVE -DestinationPath $env:AIDIR_DEST -Force'
        ].join(' ');

        try {
            await execFileAsync(
                'powershell.exe',
                ['-NoProfile', '-NonInteractive', '-Command', psCommand],
                {
                    windowsHide: true,
                    timeout: 120000,
                    encoding: 'utf8',
                    env: {
                        ...process.env,
                        AIDIR_ARCHIVE: archivePath,
                        AIDIR_DEST: destination
                    }
                }
            );
        } catch (psError) {
            throw new Error(`Could not extract ${path.basename(archivePath)}: ${psError.message}`);
        }
    }
}

function findRuntimeRoot(extractedRoot) {
    const binaryName = process.platform === 'win32' ? 'llama-server.exe' : 'llama-server';
    const matches = [];

    function walk(current, depth) {
        if (depth > 4) return;
        let entries;
        try {
            entries = fs.readdirSync(current, { withFileTypes: true });
        } catch (_error) {
            return;
        }
        for (const entry of entries) {
            const full = path.join(current, entry.name);
            if (entry.isFile() && entry.name === binaryName) {
                matches.push(path.dirname(full));
            } else if (entry.isDirectory() && entry.name !== 'node_modules') {
                walk(full, depth + 1);
            }
        }
    }

    walk(extractedRoot, 0);

    if (matches.length !== 1) {
        throw new Error(
            matches.length === 0
                ? `The update archive did not contain ${binaryName}.`
                : `The update archive contained multiple ${binaryName} binaries; refusing to guess.`
        );
    }

    return matches[0];
}

async function installLlamaUpdate({ onProgress, expectedCandidate = null } = {}) {
    const status = await checkLlamaUpdates();
    const expectedIdentity = expectedCandidate ? JSON.stringify(expectedCandidate) : null;
    const actualIdentity = status.candidateIdentity ? JSON.stringify(status.candidateIdentity) : null;
    if (!expectedIdentity || expectedIdentity !== actualIdentity) {
        return { ok: false, component: 'llama', updated: false, error: 'The llama.cpp release identity changed or was not bound to the visible update check. Refresh Updates and retry; no files were changed.' };
    }

    if (!status.updateAvailable) {
        return { ok: true, component: 'llama', updated: false, message: 'llama.cpp is already current.' };
    }

    if (!status.installAvailable) {
        return { ok: false, component: 'llama', updated: false, error: status.installReason };
    }

    const latest = await getJson(`https://api.github.com/repos/${LLAMA_REPO}/releases/latest`);
    const asset = (latest.assets || []).find((item) => item.name === status.matchedAsset?.name);
    if (!asset) {
        throw new Error('The previously identified llama.cpp release asset disappeared during the install check.');
    }
    if (latest.tag_name !== expectedCandidate.version ||
        Number(latest.id || 0) !== Number(expectedCandidate.releaseId || 0) ||
        Number(asset.id || 0) !== Number(expectedCandidate.assetId || 0) ||
        asset.name !== expectedCandidate.assetName ||
        String(asset.digest || '') !== String(expectedCandidate.assetDigest || '') ||
        Number(asset.size || 0) !== Number(expectedCandidate.assetSize || 0)) {
        throw new Error('The llama.cpp release/asset identity changed after the visible update check; refresh Updates before installing.');
    }

    const expectedSha = parseSha256Digest(asset.digest);
    if (!expectedSha) {
        throw new Error('The selected llama.cpp asset has no verifiable SHA-256 digest.');
    }

    const stamp = `${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;
    const workRoot = path.join(UPDATE_WORK_ROOT, `llama-${stamp}`);
    const archivePath = path.join(workRoot, asset.name);
    const extractRoot = path.join(workRoot, 'extracted');
    const newRoot = `${LLAMA_ROOT}.aidir-new-${stamp}`;
    const backupRoot = `${LLAMA_ROOT}.aidir-backup-${stamp}`;
    const preservedConfig = fs.existsSync(MCP_VFX_CONFIG)
        ? fs.readFileSync(MCP_VFX_CONFIG)
        : null;
    const preservedConfigHash = preservedConfig ? crypto.createHash('sha256').update(preservedConfig).digest('hex') : null;
    const preservedLogs = fs.existsSync(path.join(LLAMA_ROOT, 'logs'))
        ? path.join(workRoot, 'logs-preserved')
        : null;

    await fs.promises.mkdir(workRoot, { recursive: true });

    try {
        onProgress?.({ phase: 'download', progress: 0, message: `Downloading ${asset.name}` });
        await downloadFile(asset.browser_download_url, archivePath, ({ received, total }) => {
            const progress = total ? Math.round((received / total) * 60) : 0;
            onProgress?.({ phase: 'download', progress, message: `Downloading ${asset.name}` });
        });

        onProgress?.({ phase: 'verify', progress: 62, message: 'Verifying downloaded llama.cpp package...' });
        const actualSha = await sha256File(archivePath);
        if (actualSha !== expectedSha) {
            throw new Error(`SHA-256 verification failed for ${asset.name}.`);
        }

        await extractArchive(archivePath, extractRoot);
        const runtimeRoot = findRuntimeRoot(extractRoot);
        if (LLAMA_RUNTIME_STACK_MANAGED) {
            await validateLlamaRuntimeStackCompatibility(runtimeRoot);
        }

        onProgress?.({ phase: 'stage', progress: 78, message: 'Staging llama.cpp runtime...' });
        await fs.promises.rm(newRoot, { recursive: true, force: true });
        await fs.promises.mkdir(newRoot, { recursive: true });
        fs.cpSync(runtimeRoot, newRoot, { recursive: true, force: true });

        const archiveConfig = path.join(newRoot, 'vfx_mcp.json');
        if (fs.existsSync(archiveConfig)) fs.rmSync(archiveConfig, { force: true });

        if (preservedLogs) {
            fs.cpSync(path.join(LLAMA_ROOT, 'logs'), preservedLogs, { recursive: true, force: true });
            fs.cpSync(preservedLogs, path.join(newRoot, 'logs'), { recursive: true, force: true });
        }

        const stagedExe = process.platform === 'win32'
            ? path.join(newRoot, 'llama-server.exe')
            : path.join(newRoot, 'llama-server');
        if (!fs.existsSync(stagedExe)) {
            throw new Error('Staged llama.cpp runtime does not contain the expected server binary.');
        }

        // Never replace the accepted Upstream runtime until the candidate binary
        // proves that its executable/DLL closure can start on this machine. The
        // full model/backend/cache health gate still runs after activation and
        // automatically rolls back on any integration failure.
        onProgress?.({ phase: 'verify', progress: 84, message: 'Preflighting staged llama.cpp executable before activation...' });
        const stagedVersion = await execFileAsync(stagedExe, ['--version'], {
            cwd: newRoot,
            windowsHide: true,
            timeout: 20000,
            encoding: 'utf8',
            env: llamaStackExecutionEnvironment(newRoot)
        });
        if (!(`${stagedVersion.stdout}\n${stagedVersion.stderr}`).trim()) {
            throw new Error('Staged llama.cpp candidate could not execute before activation.');
        }

        onProgress?.({ phase: 'swap', progress: 86, message: 'Replacing llama.cpp runtime...' });
        if (fs.existsSync(LLAMA_ROOT)) {
            await fs.promises.rm(backupRoot, { recursive: true, force: true });
            await fs.promises.rename(LLAMA_ROOT, backupRoot);
        }
        await fs.promises.rename(newRoot, LLAMA_ROOT);

        const postConfigHash = fs.existsSync(MCP_VFX_CONFIG)
            ? await sha256File(MCP_VFX_CONFIG)
            : null;
        if (preservedConfigHash !== postConfigHash) {
            throw new Error('vfx_mcp.json integrity check failed after llama.cpp update; rolling back.');
        }

        onProgress?.({ phase: 'verify', progress: 94, message: 'Checking updated llama.cpp binary...' });
        const version = await execFileAsync(
            process.platform === 'win32' ? path.join(LLAMA_ROOT, 'llama-server.exe') : path.join(LLAMA_ROOT, 'llama-server'),
            ['--version'],
            {
                windowsHide: true,
                timeout: 20000,
                encoding: 'utf8',
                env: llamaStackExecutionEnvironment(LLAMA_ROOT)
            }
        );
        if (!(`${version.stdout}\n${version.stderr}`).trim()) {
            throw new Error('Updated llama.cpp binary returned no version output.');
        }

        onProgress?.({ phase: 'health', progress: 96, message: `llama.cpp ${latest.tag_name} activated; validating the updated Upstream runtime before final commit...` });
        return {
            ok: true,
            component: 'llama',
            updated: true,
            fromVersion: status.installedVersion,
            toVersion: latest.tag_name,
            asset: asset.name,
            candidateIdentity: status.candidateIdentity,
            backupRoot,
            previousVfxConfigSha256: preservedConfigHash,
            provisionalUntilRuntimeHealth: true
        };
    } catch (error) {
        let rollbackError = null;
        try {
            if (fs.existsSync(LLAMA_ROOT) && fs.existsSync(backupRoot)) {
                const failedRoot = `${LLAMA_ROOT}.aidir-failed-${stamp}`;
                if (fs.existsSync(failedRoot)) {
                    throw new Error(`llama.cpp rollback diagnostic root already exists: ${failedRoot}`);
                }
                await fs.promises.rename(LLAMA_ROOT, failedRoot);
                await fs.promises.rename(backupRoot, LLAMA_ROOT);
            } else if (fs.existsSync(backupRoot) && !fs.existsSync(LLAMA_ROOT)) {
                await fs.promises.rename(backupRoot, LLAMA_ROOT);
            }

            const restoredVersion = localLlamaInstalledVersion();
            if (status.installedVersion && restoredVersion !== status.installedVersion) {
                throw new Error(`llama.cpp rollback identity mismatch. Expected ${status.installedVersion}, actual ${restoredVersion || 'unknown'}.`);
            }
            const restoredConfigHash = fs.existsSync(MCP_VFX_CONFIG)
                ? await sha256File(MCP_VFX_CONFIG)
                : null;
            if (preservedConfigHash !== restoredConfigHash) {
                throw new Error('vfx_mcp.json was not restored during llama.cpp rollback.');
            }
        } catch (restoreError) {
            rollbackError = restoreError;
        }

        if (rollbackError) {
            throw new Error(
                `${error instanceof Error ? error.message : String(error)} Rollback also failed: ${rollbackError.message}`
            );
        }
        throw error;
    } finally {
        await fs.promises.rm(workRoot, { recursive: true, force: true }).catch(() => {});
        await fs.promises.rm(newRoot, { recursive: true, force: true }).catch(() => {});
    }
}

async function installMcpUpdate({ onProgress, expectedCandidate = null } = {}) {
    const status = await checkMcpUpdates();
    if (!expectedCandidate || stableCandidateIdentity(status.candidateIdentity) !== stableCandidateIdentity(expectedCandidate)) {
        return { ok: false, component: 'mcp', updated: false, error: 'The MCP release identity changed or was not bound to the visible update check. Refresh Updates and retry; no files were changed.' };
    }

    if (!status.updateAvailable) {
        return { ok: true, component: 'mcp', updated: false, message: 'DaVinci Resolve MCP is already current.' };
    }

    if (!status.installAvailable) {
        return { ok: false, component: 'mcp', updated: false, error: status.installReason };
    }

    if (status.installMode === 'managed-compatibility-bundle') {
        return installManagedMcpCompatibilityUpdate(status, { onProgress });
    }
    if (status.installMode === 'managed-compatible-release') {
        return installManagedMcpCompatibleRelease(status, { onProgress });
    }

    if (status.managed) {
        return {
            ok: false,
            component: 'mcp',
            updated: false,
            error: 'Managed MCP updates require a validated AI Director compatibility bundle.'
        };
    }

    const beforeConfigHash = fs.existsSync(MCP_VFX_CONFIG)
        ? await sha256File(MCP_VFX_CONFIG)
        : null;
    const beforeHead = (await git(['rev-parse', 'HEAD'], { cwd: MCP_ROOT })).stdout.trim();
    let merged = false;

    try {
        onProgress?.({ phase: 'git', progress: 20, message: `Fetching ${MCP_REPO} tags...` });
        await git(['fetch', '--tags', '--prune', 'origin'], { cwd: MCP_ROOT, timeout: 120000 });

        const latestTag = status.latestVersion;
        if (!latestTag) throw new Error('GitHub did not provide the latest MCP release tag.');

        await git(['merge-base', '--is-ancestor', 'HEAD', latestTag], {
            cwd: MCP_ROOT,
            timeout: 30000
        }).catch((error) => {
            throw new Error(`MCP update is not a safe fast-forward from the current checkout: ${error.stderr || error.message}`);
        });

        onProgress?.({ phase: 'git', progress: 55, message: `Applying ${latestTag} with fast-forward only...` });
        await git(['merge', '--ff-only', latestTag], { cwd: MCP_ROOT, timeout: 120000 });
        merged = true;

        const venvPython = process.platform === 'win32'
            ? path.join(MCP_ROOT, 'venv', 'Scripts', 'python.exe')
            : path.join(MCP_ROOT, 'venv', 'bin', 'python');

        const requirementsPath = path.join(MCP_ROOT, 'requirements.txt');
        if (fs.existsSync(venvPython) && fs.existsSync(requirementsPath)) {
            onProgress?.({ phase: 'deps', progress: 70, message: 'Refreshing MCP Python dependencies...' });
            await execFileAsync(venvPython, ['-m', 'pip', 'install', '-r', requirementsPath], {
                cwd: MCP_ROOT,
                windowsHide: true,
                timeout: 600000,
                encoding: 'utf8'
            });
        }

        const advancedRoot = path.join(MCP_ROOT, 'resolve-advanced');
        const packageLock = path.join(advancedRoot, 'package-lock.json');
        const packageJson = path.join(advancedRoot, 'package.json');
        if (fs.existsSync(packageLock) && fs.existsSync(packageJson)) {
            onProgress?.({ phase: 'deps', progress: 82, message: 'Refreshing Resolve Advanced dependencies...' });
            try {
                await execProductNpm(['ci', '--omit=dev', '--omit=optional', '--no-audit', '--no-fund'], {
                    cwd: advancedRoot,
                    windowsHide: true,
                    timeout: 600000,
                    encoding: 'utf8'
                });
            } catch (error) {
                throw new Error(`Resolve Advanced dependency refresh failed: ${error.stderr || error.message}`);
            }
        }

        const afterConfigHash = fs.existsSync(MCP_VFX_CONFIG)
            ? await sha256File(MCP_VFX_CONFIG)
            : null;
        if (beforeConfigHash !== afterConfigHash) {
            throw new Error('vfx_mcp.json integrity check failed after MCP update.');
        }

        const newState = await mcpGitState();
        onProgress?.({ phase: 'done', progress: 100, message: `DaVinci Resolve MCP updated to ${latestTag}.` });

        return {
            ok: true,
            component: 'mcp',
            updated: true,
            fromVersion: status.installedVersion,
            toVersion: latestTag,
            head: newState.head,
            resolveRestartRequired: false,
            installMode: 'git-fast-forward'
        };
    } catch (error) {
        if (merged) {
            onProgress?.({ phase: 'rollback', progress: 88, message: 'Update verification failed; restoring the previous MCP revision...' });
            try {
                await git(['reset', '--hard', beforeHead], { cwd: MCP_ROOT, timeout: 120000 });
            } catch (rollbackError) {
                throw new Error(
                    `${error instanceof Error ? error.message : String(error)} Rollback also failed: ${rollbackError.stderr || rollbackError.message}`
                );
            }
        }
        throw error;
    }
}


function localLlamaInstalledVersion() {
    const marker = parseMarker();
    return marker?.upstream_tag || marker?.resolved_source_ref || marker?.release_tag || marker?.tag || null;
}

async function verifyInstalledUpdate(result) {
    if (!result || result.ok !== true || result.updated !== true) {
        throw new Error('Cannot verify an update result that was not installed successfully.');
    }

    if (result.component === 'llama') {
        const installedVersion = localLlamaInstalledVersion();
        if (!installedVersion || installedVersion !== result.toVersion) {
            throw new Error(`Updated llama.cpp local identity mismatch. Expected ${result.toVersion}, actual ${installedVersion || 'unknown'}.`);
        }
        if (!fs.existsSync(LLAMA_EXE)) {
            throw new Error('Updated llama.cpp executable is missing after runtime restart.');
        }
        const version = await llamaBinaryVersion();
        if (!version) {
            throw new Error('Updated llama.cpp binary did not report a local version after runtime restart.');
        }
        const configHash = fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null;
        if (result.previousVfxConfigSha256 !== undefined && configHash !== result.previousVfxConfigSha256) {
            throw new Error('vfx_mcp.json changed across the llama.cpp runtime-health gate.');
        }
        return { component: 'llama', installedVersion, binaryVersion: version };
    }

    if (result.component === 'mcp') {
        const marker = readJsonFile(path.join(MCP_ROOT, '.davinci-resolve-mcp-managed.json'));
        const packageJson = readJsonFile(path.join(MCP_ROOT, 'package.json'));
        if (!marker || !packageJson || marker.managed !== true || marker.version !== result.toVersion || packageJson.version !== result.toVersion) {
            throw new Error(`Updated MCP local identity mismatch. Expected ${result.toVersion}.`);
        }
        if (result.compatibilityBundleSha256 && marker.compatibilityBundleSha256 !== result.compatibilityBundleSha256) {
            throw new Error('Updated MCP compatibility-bundle identity mismatch after runtime restart.');
        }
        if (result.sourceCommit && marker.sourceCommit !== result.sourceCommit) {
            throw new Error('Updated MCP source-commit identity mismatch after runtime restart.');
        }
        if (result.productOverlaySha256) {
            const guidancePath = path.join(MCP_ROOT, WINDOWS_ADVANCED_GUIDANCE_RELATIVE_PATH);
            if (!fs.existsSync(guidancePath) ||
                (await sha256File(guidancePath)).toUpperCase() !== result.productOverlaySha256) {
                throw new Error('Updated MCP AI Director Windows Advanced guidance overlay is missing or mismatched after runtime restart.');
            }
        }
        if (!fs.existsSync(MCP_PYTHON_EXE)) {
            throw new Error('Updated MCP Python runtime is missing after runtime restart.');
        }
        const configHash = fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null;
        if (result.previousVfxConfigSha256 !== undefined && configHash !== result.previousVfxConfigSha256) {
            throw new Error('vfx_mcp.json changed across the MCP runtime-health gate.');
        }
        return { component: 'mcp', installedVersion: marker.version, compatibilityBundleSha256: marker.compatibilityBundleSha256 || null };
    }

    throw new Error(`Unsupported update component for local verification: ${result.component}`);
}

async function finalizeInstalledUpdate(result) {
    const verified = await verifyInstalledUpdate(result);
    if (result.component === 'mcp' && ['managed-compatibility-bundle', 'managed-compatible-release'].includes(result.installMode)) {
        const updateStatePath = path.join(ProductPaths.resolveManifestsRoot, 'MCP-UPDATE-STATE.json');
        const state = readJsonFile(updateStatePath);
        if (!state || state.to_version !== result.toVersion) {
            throw new Error('MCP update-state manifest is missing or does not match the provisional transaction.');
        }
        state.runtime_health = {
            status: 'LIVE_HEALTH_ACCEPTED',
            validated_at: new Date().toISOString(),
            backend_ready: true,
            execution_cache_primed: true,
            functional_read_only_canary: true
        };
        writeJsonFile(updateStatePath, state);
        const strictContractPath = path.join(ProductPaths.resolveManifestsRoot, `MCP-COMPATIBILITY-CONTRACT-${result.toVersion}.json`);
        const strictContract = readJsonFile(strictContractPath);
        if (!strictContract || (result.strictCandidateContractSha256 && (await sha256File(strictContractPath)).toUpperCase() !== result.strictCandidateContractSha256)) {
            throw new Error('Strict MCP candidate contract is missing or changed before finalization.');
        }
        strictContract.status = 'LIVE_ACCEPTED';
        strictContract.live_health = state.runtime_health;
        strictContract.accepted_at = new Date().toISOString();
        writeJsonFile(strictContractPath, strictContract);
    }
    return { ...verified, finalized: true, finalizedAt: new Date().toISOString() };
}

async function rollbackInstalledUpdate(result, { onProgress } = {}) {
    if (!result || result.ok !== true || result.updated !== true) {
        throw new Error('Cannot roll back an update result that was not installed successfully.');
    }

    const stamp = `${Date.now()}-${crypto.randomBytes(4).toString('hex')}`;

    if (result.component === 'llama') {
        const backupRoot = result.backupRoot;
        if (!backupRoot || !fs.existsSync(backupRoot)) {
            throw new Error('Previous llama.cpp runtime backup is unavailable; refusing an unsafe rollback.');
        }
        onProgress?.({ phase: 'rollback', progress: 97, message: `Runtime health failed; restoring llama.cpp ${result.fromVersion || 'previous version'}...` });
        const rejectedRoot = `${LLAMA_ROOT}.aidir-rejected-${stamp}`;
        let activeMoved = false;
        let backupActivated = false;
        try {
            if (fs.existsSync(LLAMA_ROOT)) {
                await fs.promises.rename(LLAMA_ROOT, rejectedRoot);
                activeMoved = true;
            }
            await fs.promises.rename(backupRoot, LLAMA_ROOT);
            backupActivated = true;
            const restored = localLlamaInstalledVersion();
            if (result.fromVersion && restored !== result.fromVersion) {
                throw new Error(`Restored llama.cpp identity mismatch. Expected ${result.fromVersion}, actual ${restored || 'unknown'}.`);
            }
            const configHash = fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null;
            if (result.previousVfxConfigSha256 !== undefined && configHash !== result.previousVfxConfigSha256) {
                throw new Error('vfx_mcp.json changed while restoring the previous llama.cpp runtime.');
            }
            return { ok: true, component: 'llama', restoredVersion: restored, rejectedRoot };
        } catch (error) {
            let repairError = null;
            try {
                if (backupActivated && fs.existsSync(LLAMA_ROOT) && !fs.existsSync(backupRoot)) {
                    await fs.promises.rename(LLAMA_ROOT, backupRoot);
                }
                if (activeMoved && fs.existsSync(rejectedRoot) && !fs.existsSync(LLAMA_ROOT)) {
                    await fs.promises.rename(rejectedRoot, LLAMA_ROOT);
                }
            } catch (restoreError) {
                repairError = restoreError;
            }
            if (repairError) {
                throw new Error(
                    `${error instanceof Error ? error.message : String(error)} Rollback repair also failed: ${repairError.message}`
                );
            }
            throw error;
        }
    }

    if (result.component === 'mcp' && ['managed-compatibility-bundle', 'managed-compatible-release'].includes(result.installMode)) {
        const sourceBackupRoot = result.sourceBackupRoot;
        const pythonBackupRoot = result.pythonBackupRoot;
        const manifestBackupRoot = result.backupRoot;
        const manifestStatePath = manifestBackupRoot ? path.join(manifestBackupRoot, 'manifest-backup-state.json') : null;
        if (!sourceBackupRoot || !fs.existsSync(sourceBackupRoot)) {
            throw new Error('Previous MCP source backup is unavailable; refusing an unsafe rollback.');
        }
        if (!pythonBackupRoot || !fs.existsSync(pythonBackupRoot)) {
            throw new Error('Previous MCP Python backup is unavailable; refusing an unsafe rollback.');
        }
        const manifestRows = manifestStatePath ? readJsonFile(manifestStatePath) : null;
        if (!Array.isArray(manifestRows)) {
            throw new Error('Previous MCP manifest backup state is unavailable; refusing an unsafe rollback.');
        }
        onProgress?.({ phase: 'rollback', progress: 97, message: `Runtime health failed; restoring MCP ${result.fromVersion || 'previous version'} source, Python, and manifests...` });

        const rejectedMcpRoot = `${MCP_ROOT}.aidir-rejected-${stamp}`;
        const rejectedPythonRoot = `${MCP_PYTHON_ROOT}.aidir-rejected-${stamp}`;
        let activeSourceMoved = false;
        let activePythonMoved = false;
        let backupSourceActivated = false;
        let backupPythonActivated = false;
        try {
            if (fs.existsSync(MCP_ROOT)) {
                await fs.promises.rename(MCP_ROOT, rejectedMcpRoot);
                activeSourceMoved = true;
            }
            if (fs.existsSync(MCP_PYTHON_ROOT)) {
                await fs.promises.rename(MCP_PYTHON_ROOT, rejectedPythonRoot);
                activePythonMoved = true;
            }
            await fs.promises.rename(sourceBackupRoot, MCP_ROOT);
            backupSourceActivated = true;
            await fs.promises.rename(pythonBackupRoot, MCP_PYTHON_ROOT);
            backupPythonActivated = true;
            await restoreManifestFiles(manifestRows);

            const restoredMarker = readJsonFile(path.join(MCP_ROOT, '.davinci-resolve-mcp-managed.json'));
            const restoredPackage = readJsonFile(path.join(MCP_ROOT, 'package.json'));
            if (!restoredMarker || !restoredPackage || restoredMarker.version !== result.fromVersion || restoredPackage.version !== result.fromVersion) {
                throw new Error(`Restored MCP identity mismatch. Expected ${result.fromVersion}.`);
            }
            const configHash = fs.existsSync(MCP_VFX_CONFIG) ? await sha256File(MCP_VFX_CONFIG) : null;
            if (result.previousVfxConfigSha256 !== undefined && configHash !== result.previousVfxConfigSha256) {
                throw new Error('vfx_mcp.json changed while restoring the previous MCP compatibility unit.');
            }
            return { ok: true, component: 'mcp', restoredVersion: result.fromVersion, rejectedMcpRoot, rejectedPythonRoot };
        } catch (error) {
            let repairError = null;
            try {
                if (backupPythonActivated && fs.existsSync(MCP_PYTHON_ROOT) && !fs.existsSync(pythonBackupRoot)) {
                    await fs.promises.rename(MCP_PYTHON_ROOT, pythonBackupRoot);
                }
                if (backupSourceActivated && fs.existsSync(MCP_ROOT) && !fs.existsSync(sourceBackupRoot)) {
                    await fs.promises.rename(MCP_ROOT, sourceBackupRoot);
                }
                if (activePythonMoved && fs.existsSync(rejectedPythonRoot) && !fs.existsSync(MCP_PYTHON_ROOT)) {
                    await fs.promises.rename(rejectedPythonRoot, MCP_PYTHON_ROOT);
                }
                if (activeSourceMoved && fs.existsSync(rejectedMcpRoot) && !fs.existsSync(MCP_ROOT)) {
                    await fs.promises.rename(rejectedMcpRoot, MCP_ROOT);
                }
            } catch (restoreError) {
                repairError = restoreError;
            }
            if (repairError) {
                throw new Error(
                    `${error instanceof Error ? error.message : String(error)} Rollback repair also failed: ${repairError.message}`
                );
            }
            throw error;
        }
    }

    throw new Error(`Unsupported update transaction for rollback: ${result.component || 'unknown'}`);
}

module.exports = {
    parseJsonText,
    readJsonFile,
    verifyPayloadManifest,
    buildMcpCompatibilityProbeCode,
    buildWindowsAdvancedGuidanceOverlayFunctions,
    LLAMA_ROOT,
    MCP_ROOT,
    checkAll,
    checkLlamaUpdates,
    checkMcpUpdates,
    installLlamaUpdate,
    installMcpUpdate,
    verifyInstalledUpdate,
    finalizeInstalledUpdate,
    rollbackInstalledUpdate
};
