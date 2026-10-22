from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

RUNTIME_BASE_DESCRIPTOR = "RUNTIME-BASE.json"
RUNTIME_BASE_MANIFEST_NAME = "RUNTIME-BASE-MANIFEST.json"
RUNTIME_BASE_ARCHIVE_NAME = "RUNTIME-BASE.7z"
RUNTIME_BASE_INVENTORY_NAME = "SHIPPING-INVENTORY.json"

EXPECTED_RUNTIME_BASE_ID = "CUDA13-Native-Base-v3"
EXPECTED_SHIPPING_ARCHIVE_SHA256 = "921B0B02B43E15683E3A77EAE9CA6C779308A0A702BA43C5D76D73E81090654D"
EXPECTED_SHIPPING_ARCHIVE_BYTES = 94999083
EXPECTED_SHIPPING_INVENTORY_SHA256 = "3EDEB3143EC8CB38CD8D4ED8D0FD778222B4D99E23C27B2FB1CDFE866BEC9944"
EXPECTED_SHIPPING_FILE_COUNT = 15720
EXPECTED_MCP_BOOTSTRAP_PATH = "AIDirector/DaVinciResolve/Updates/MCP/Bootstrap/davinci-resolve-mcp-4.10.4-8911bd24aee7.tar.gz"
EXPECTED_MCP_BOOTSTRAP_SHA256 = "48370655E414BAAEC1D18259C5DFD53E4CA2C71C698D60C13A5CA872F7BAA0A6"
EXPECTED_MCP_COMMIT = "8911bd24aee76894238924317a461005dd013d94"
EXPECTED_RUNTIME_STACK_ID = "CUDA13.3.1-Dual-Shared-v2"
EXPECTED_RUNTIME_STACK_DESCRIPTOR_SHA256 = "872EF78E88D71E80332CEABEA685C8317F9F049669936C2C4A353B044E754E34"
EXPECTED_RUNTIME_STACK_MANIFEST_SHA256 = "AA04F057CA1B8788BB759DE23CFFD3B7CE65D6BA2F38B2D55C35A9BEF56EBA51"
EXPECTED_RUNTIME_STACK_ARCHIVE_SHA256 = "F3413EDF3D0BD76D5D5D80698261F55F766A905CAD2BEF2E26A67DEAF3548C44"

FORBIDDEN_ACTIVE_METADATA = {
    "required_builder_sha256",
    "base_stable_version",
    "target_version",
    "parent_runtime_base_id",
    "source_06H_Q_report_sha256",
    "parent_runtime_base",
    "mcp_seed_promotion",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def safe_rel(value: str, label: str) -> Path:
    text = str(value or "").replace("\\", "/").strip()
    path = Path(text)
    if (not text or path.is_absolute() or re.match(r"^[A-Za-z]:", text)
            or any(part in ("", ".", "..") for part in path.parts)):
        raise RuntimeError(f"{label} unsafe path: {text!r}")
    return Path(*path.parts)

def integer_field(obj: dict, key: str, label: str, minimum: int | None = None) -> int:
    if key not in obj or obj.get(key) is None or isinstance(obj.get(key), bool):
        raise RuntimeError(f"{label} missing/invalid")
    try:
        value = int(obj.get(key))
    except Exception as exc:
        raise RuntimeError(f"{label} invalid") from exc
    if minimum is not None and value < minimum:
        raise RuntimeError(f"{label} invalid")
    return value

def assert_hash(label: str, path: Path, expected: str) -> str:
    expected = str(expected or "").upper()
    if not re.fullmatch(r"[0-9A-F]{64}", expected):
        raise RuntimeError(f"{label} invalid expected SHA-256")
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{label} hash mismatch Expected={expected} Actual={actual} Path={path}")
    return actual

def validate_inventory(obj: dict) -> None:
    if obj.get("schema_version") != 1 or obj.get("runtime_base_id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("runtime-base v3 inventory identity mismatch")
    if integer_field(obj, "file_count", "inventory file count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base v3 inventory file count mismatch")
    rows = obj.get("files")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base v3 inventory rows mismatch")
    seen = set()
    bootstrap_hash = None
    arm64_required = {
        "pip/_vendor/distlib/t64-arm.exe",
        "pip/_vendor/distlib/w64-arm.exe",
        "setuptools/cli-arm64.exe",
        "setuptools/gui-arm64.exe",
    }
    arm64_seen = set()
    for row in rows:
        rel = safe_rel(row.get("path"), "inventory file").as_posix()
        key = rel.lower()
        if key in seen:
            raise RuntimeError(f"duplicate inventory path: {rel}")
        seen.add(key)
        digest = str(row.get("sha256") or "").upper()
        if not re.fullmatch(r"[0-9A-F]{64}", digest):
            raise RuntimeError(f"bad inventory SHA-256: {rel}")
        integer_field(row, "bytes", f"inventory bytes {rel}", 0)
        if key == EXPECTED_MCP_BOOTSTRAP_PATH.lower():
            bootstrap_hash = digest
        for suffix in arm64_required:
            if key.endswith(suffix):
                arm64_seen.add(suffix)
    forbidden_roots = (
        "aidirector/common/runtime/cuda/12.8/",
        "aidirector/davinciresolve/runtime/llama/direct/",
        "aidirector/davinciresolve/runtime/llama/upstream/",
    )
    if "aidirector/common/manifests/cuda-12.8.json" in seen:
        raise RuntimeError("v3 inventory contains retired CUDA 12.8 manifest")
    if any(any(path.startswith(prefix) for prefix in forbidden_roots) for path in seen):
        raise RuntimeError("v3 inventory contains retired legacy runtime roots")
    if any("4.8.22" in path for path in seen):
        raise RuntimeError("v3 inventory contains stale 4.8.22 versioned state")
    if bootstrap_hash != EXPECTED_MCP_BOOTSTRAP_SHA256:
        raise RuntimeError("MCP 4.10.4 bootstrap missing/mismatch")
    if arm64_seen != arm64_required:
        raise RuntimeError(f"ARM64 launcher parity incomplete: {sorted(arm64_required - arm64_seen)}")

def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != 2 or manifest.get("runtime_base_id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("active runtime-base manifest identity mismatch")
    if manifest.get("payload_role") != "ACTIVE_RUNTIME_BASE":
        raise RuntimeError("active runtime-base manifest role mismatch")
    leaked = sorted(FORBIDDEN_ACTIVE_METADATA.intersection(manifest))
    if leaked:
        raise RuntimeError(f"historical runtime-base metadata remains active: {leaked}")
    if integer_field(manifest, "expected_shipping_file_count", "manifest file count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base manifest file count mismatch")
    seed = manifest.get("bundled_mcp_seed") or {}
    if (seed.get("version") != "4.10.4"
            or seed.get("commit") != EXPECTED_MCP_COMMIT
            or seed.get("path") != EXPECTED_MCP_BOOTSTRAP_PATH
            or str(seed.get("sha256") or "").upper() != EXPECTED_MCP_BOOTSTRAP_SHA256):
        raise RuntimeError("bundled MCP 4.10.4 seed metadata mismatch")
    dependency = manifest.get("runtime_stack_dependency") or {}
    expected_dependency = {
        "id": EXPECTED_RUNTIME_STACK_ID,
        "descriptor_sha256": EXPECTED_RUNTIME_STACK_DESCRIPTOR_SHA256,
        "manifest_sha256": EXPECTED_RUNTIME_STACK_MANIFEST_SHA256,
        "archive_sha256": EXPECTED_RUNTIME_STACK_ARCHIVE_SHA256,
    }
    for key, expected in expected_dependency.items():
        observed = str(dependency.get(key) or "")
        if key.endswith("sha256"):
            observed = observed.upper()
        if observed != expected:
            raise RuntimeError(f"runtime-stack dependency mismatch: {key}")
    if dependency.get("mutation_authorized") is not False:
        raise RuntimeError("runtime-stack mutation must remain false")
    if str(manifest.get("shipping_archive_sha256") or "").upper() != EXPECTED_SHIPPING_ARCHIVE_SHA256:
        raise RuntimeError("runtime-base manifest archive mismatch")
    if str(manifest.get("shipping_inventory_sha256") or "").upper() != EXPECTED_SHIPPING_INVENTORY_SHA256:
        raise RuntimeError("runtime-base manifest inventory mismatch")
    if integer_field(manifest, "shipping_archive_bytes", "manifest archive bytes", 1) != EXPECTED_SHIPPING_ARCHIVE_BYTES:
        raise RuntimeError("runtime-base manifest archive size mismatch")
    if integer_field(manifest, "inventory_file_count", "manifest inventory count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base manifest inventory count mismatch")
    if manifest.get("archive_filter") != "BCJ":
        raise RuntimeError("runtime-base manifest filter mismatch")
    if manifest.get("shipping_inventory_source_runtime_base_id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("runtime-base manifest inventory source mismatch")

def validate_candidate(candidate, current, builder_sha):
    del builder_sha  # Active runtime payload identity is not coupled to a historical builder hash.
    descriptor = candidate["descriptor"]
    root = candidate["root"]
    metadata_root = candidate.get("metadata_root") or root
    if descriptor.get("schema_version") != 2 or descriptor.get("runtime_base_id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("active runtime-base descriptor identity mismatch")
    if descriptor.get("kind") != "runtime-base" or descriptor.get("payload_role") != "ACTIVE_RUNTIME_BASE":
        raise RuntimeError("active runtime-base descriptor role mismatch")
    leaked = sorted(FORBIDDEN_ACTIVE_METADATA.intersection(descriptor))
    if leaked:
        raise RuntimeError(f"historical runtime-base metadata remains active: {leaked}")
    if descriptor.get("files") not in ([], None):
        raise RuntimeError("runtime-base may not carry application replacements")
    if descriptor.get("bundled_mcp_version") != "4.10.4" or descriptor.get("bundled_mcp_commit") != EXPECTED_MCP_COMMIT:
        raise RuntimeError("runtime-base bundled MCP identity mismatch")
    if descriptor.get("archive_filter") != "BCJ" or descriptor.get("nsis7z_full_parity_required") is not True:
        raise RuntimeError("runtime-base archive/parity contract mismatch")
    specs = [
        ("runtime_base_manifest", RUNTIME_BASE_MANIFEST_NAME, "runtime_base_manifest_sha256"),
        ("shipping_archive", RUNTIME_BASE_ARCHIVE_NAME, "shipping_archive_sha256"),
        ("shipping_inventory", RUNTIME_BASE_INVENTORY_NAME, "shipping_inventory_sha256"),
    ]
    paths = {}
    for key, required_name, hash_key in specs:
        rel = safe_rel(descriptor.get(key) or required_name, key)
        if rel.as_posix() != required_name:
            raise RuntimeError(f"{key} must be {required_name}")
        base = root if key == "shipping_archive" else metadata_root
        path = base / rel
        expected = str(descriptor.get(hash_key) or "").upper()
        assert_hash(key, path, expected)
        paths[key] = path
    if str(descriptor.get("shipping_archive_sha256") or "").upper() != EXPECTED_SHIPPING_ARCHIVE_SHA256:
        raise RuntimeError("runtime-base descriptor archive mismatch")
    if str(descriptor.get("shipping_inventory_sha256") or "").upper() != EXPECTED_SHIPPING_INVENTORY_SHA256:
        raise RuntimeError("runtime-base descriptor inventory mismatch")
    if integer_field(descriptor, "shipping_archive_bytes", "descriptor archive bytes", 1) != EXPECTED_SHIPPING_ARCHIVE_BYTES:
        raise RuntimeError("runtime-base descriptor archive size mismatch")
    if integer_field(descriptor, "inventory_file_count", "descriptor inventory count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base descriptor inventory count mismatch")
    manifest = load_json(paths["runtime_base_manifest"])
    validate_manifest(manifest)
    validate_inventory(load_json(paths["shipping_inventory"]))
    return {
        "id": EXPECTED_RUNTIME_BASE_ID,
        "root": root,
        "archive_path": paths["shipping_archive"],
        "manifest_path": paths["runtime_base_manifest"],
        "inventory_path": paths["shipping_inventory"],
    }

def load_active(builder, current):
    entry = current.get("active_runtime_base")
    if not isinstance(entry, dict) or entry.get("id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("CURRENT active runtime-base v3 identity mismatch")
    root = builder / "_inputs" / "Runtime-Bases" / EXPECTED_RUNTIME_BASE_ID
    metadata_root = builder / "provenance" / "runtime" / "runtime-base"
    descriptor_path = metadata_root / RUNTIME_BASE_DESCRIPTOR
    assert_hash("active runtime-base descriptor", descriptor_path, entry.get("manifest_sha256"))
    descriptor = load_json(descriptor_path)
    candidate = {
        "root": root,
        "metadata_root": metadata_root,
        "descriptor": descriptor,
        "descriptor_path": descriptor_path,
        "descriptor_sha256": sha256(descriptor_path),
    }
    result = validate_candidate(candidate, current, sha256(builder / "installer" / "build_installer.py"))
    if str(entry.get("archive_sha256") or "").upper() != EXPECTED_SHIPPING_ARCHIVE_SHA256:
        raise RuntimeError("CURRENT active runtime-base v3 archive binding mismatch")
    if str(entry.get("runtime_base_manifest_sha256") or "").upper() != sha256(metadata_root / RUNTIME_BASE_MANIFEST_NAME):
        raise RuntimeError("CURRENT active runtime-base v3 manifest binding mismatch")
    if str(entry.get("inventory_sha256") or "").upper() != EXPECTED_SHIPPING_INVENTORY_SHA256:
        raise RuntimeError("CURRENT active runtime-base v3 inventory binding mismatch")
    if entry.get("archive_filter") != "BCJ" or entry.get("inventory_file_count") != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("CURRENT active runtime-base v3 parity metadata mismatch")
    result["descriptor"] = descriptor
    return result
