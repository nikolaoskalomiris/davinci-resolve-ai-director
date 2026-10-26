from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

RUNTIME_BASE_DESCRIPTOR = "RUNTIME-BASE.json"
RUNTIME_BASE_MANIFEST_NAME = "RUNTIME-BASE-MANIFEST.json"
RUNTIME_BASE_ARCHIVE_NAME = "RUNTIME-BASE.7z"
RUNTIME_BASE_INVENTORY_NAME = "SHIPPING-INVENTORY.json"

EXPECTED_RUNTIME_BASE_ID = "CUDA13-Native-Base-v5"
EXPECTED_SHIPPING_ARCHIVE_SHA256 = "1F51536B3507C93FE72504A6B72557C70BD09D1195760996B2FB7FB8E20D8C4A"
EXPECTED_SHIPPING_ARCHIVE_BYTES = 96918486
EXPECTED_SHIPPING_INVENTORY_SHA256 = "88249F66294113A0CC31E2527DAD6CFD6BEAB4A0B79C2A78F860B7C3D9261C7C"
EXPECTED_SHIPPING_FILE_COUNT = 15790

EXPECTED_BASELINE_RUNTIME_BASE_ID = "CUDA13-Native-Base-v4"
EXPECTED_BASELINE_ARCHIVE_SHA256 = "29C50DB94D0655A997809A59F12B5AC98F2FC593746191C495FFA018D00111BC"
EXPECTED_BASELINE_INVENTORY_SHA256 = "AB8041B93FE7CDD92378BFE51E4D6D7A8C9CBB40674E11B3A8507CA40913CC83"
EXPECTED_BASELINE_FILE_COUNT = 20330

EXPECTED_ACTIVE_MCP_BASELINE_VERSION = "4.15.3"
EXPECTED_ACTIVE_MCP_BASELINE_COMMIT = "931bc2cda8fd9049982a457de9ff70836c406cd7"
EXPECTED_ACTIVE_MCP_PACKAGE_SHA256 = "C3B281B83B4016C049B0CCC6514134FF7BEAE5703C835547693C4734F99821F4"
EXPECTED_ACTIVE_MCP_SERVER_SHA256 = "787C09014DCAEF4430DBE24AA483C72331C469CBC739AA7612479A55C8BA96A0"
EXPECTED_ACTIVE_MCP_MARKER_SHA256 = "DA6B0AF2F489463DC7AC1C272B2AC2E0F2A14D33A0790989DA39F1DDAC02E52C"

EXPECTED_MCP_BOOTSTRAP_VERSION = "4.15.3"
EXPECTED_MCP_BOOTSTRAP_PATH = "AIDirector/DaVinciResolve/Updates/MCP/Bootstrap/davinci-resolve-mcp-4.15.3-931bc2cda8fd.tar.gz"
EXPECTED_MCP_BOOTSTRAP_SHA256 = "E36B8CB5EB73A3BC2099E7D48E15EA119D6D8411D890651DF17B76BFD3781D5C"
EXPECTED_MCP_BOOTSTRAP_BYTES = 6419447
EXPECTED_MCP_COMMIT = "931bc2cda8fd9049982a457de9ff70836c406cd7"

EXPECTED_ADVANCED_ROOT = "AIDirector/DaVinciResolve/Runtime/MCP/Advanced/4.15.3"
EXPECTED_ADVANCED_PAYLOAD_MANIFEST_SHA256 = "093DB2168F3FAD4FD14915BADE393183DAA5FF4B3A4C6BF0C6856597A916A09D"
EXPECTED_ADVANCED_MANDATORY_MANIFEST_SHA256 = "5F6A6CE58F7D8B9F96A2FC4FBDDE42E26A8E6538B4D590C1980700656C9AF9BD"
EXPECTED_ADVANCED_PROVENANCE_SHA256 = "165AC34CC84ACEEFCF8125E4832A80D850ECEA1FB90B986300DEA77616DA990C"
EXPECTED_ADVANCED_NATIVE_REPRO_SHA256 = "94ACAD418CB1698029EF69955FD2EBCAD503177DEAC2CBC633B7B3DF64B590F1"
EXPECTED_ADVANCED_LICENSE_INVENTORY_SHA256 = "22F1B0E06BFB32773837594C6EBB202E64CD6EA6E0C1A9913427D0BADFEB51B8"
EXPECTED_ADVANCED_NODE_TREE_SHA256 = "A456900C27BA316C974D40290F117AFD61D2C30D0DFC6F0EC3DE2AFA85CB4964"
EXPECTED_ADVANCED_NODE_FILES = 4602
EXPECTED_ADVANCED_NODE_BYTES = 58626067
EXPECTED_ADVANCED_IMAGE_FILES = 4609

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
        raise RuntimeError("runtime-base v5 inventory identity mismatch")
    if integer_field(obj, "file_count", "inventory file count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base v5 inventory file count mismatch")
    rows = obj.get("files")
    if not isinstance(rows, list) or len(rows) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base v5 inventory rows mismatch")

    seen = {}
    for row in rows:
        rel = safe_rel(row.get("path"), "inventory file").as_posix()
        key = rel.casefold()
        if key in seen:
            raise RuntimeError(f"duplicate inventory path: {rel}")
        digest = str(row.get("sha256") or "").upper()
        if not re.fullmatch(r"[0-9A-F]{64}", digest):
            raise RuntimeError(f"bad inventory SHA-256: {rel}")
        integer_field(row, "bytes", f"inventory bytes {rel}", 0)
        seen[key] = {"path": rel, "sha256": digest, "bytes": int(row.get("bytes"))}

    required_hashes = {
        "davinci-resolve-mcp/package.json": EXPECTED_ACTIVE_MCP_PACKAGE_SHA256,
        "davinci-resolve-mcp/src/server.py": EXPECTED_ACTIVE_MCP_SERVER_SHA256,
        "davinci-resolve-mcp/.davinci-resolve-mcp-managed.json": EXPECTED_ACTIVE_MCP_MARKER_SHA256,
        EXPECTED_MCP_BOOTSTRAP_PATH: EXPECTED_MCP_BOOTSTRAP_SHA256,
        f"{EXPECTED_ADVANCED_ROOT}/PAYLOAD-SHA256.json": EXPECTED_ADVANCED_PAYLOAD_MANIFEST_SHA256,
        f"{EXPECTED_ADVANCED_ROOT}/ADVANCED-NODE-MANDATORY-DEPENDENCY-IMAGE-MANIFEST.json": EXPECTED_ADVANCED_MANDATORY_MANIFEST_SHA256,
        f"{EXPECTED_ADVANCED_ROOT}/ADVANCED-NODE-DEPENDENCY-IMAGE-PROVENANCE.json": EXPECTED_ADVANCED_PROVENANCE_SHA256,
        f"{EXPECTED_ADVANCED_ROOT}/NATIVE-REPRODUCIBILITY.json": EXPECTED_ADVANCED_NATIVE_REPRO_SHA256,
        f"{EXPECTED_ADVANCED_ROOT}/THIRD-PARTY-PACKAGES-4.15.3.json": EXPECTED_ADVANCED_LICENSE_INVENTORY_SHA256,
    }
    for rel, expected in required_hashes.items():
        row = seen.get(rel.casefold())
        if not row or row["sha256"] != expected:
            raise RuntimeError(f"runtime-base v5 required payload hash mismatch: {rel}")

    seed = seen[EXPECTED_MCP_BOOTSTRAP_PATH.casefold()]
    if seed["bytes"] != EXPECTED_MCP_BOOTSTRAP_BYTES:
        raise RuntimeError("runtime-base v5 MCP seed byte count mismatch")

    advanced_prefix = (EXPECTED_ADVANCED_ROOT + "/").casefold()
    advanced_files = sum(1 for key in seen if key.startswith(advanced_prefix))
    if advanced_files != EXPECTED_ADVANCED_IMAGE_FILES:
        raise RuntimeError(
            f"runtime-base v5 Advanced 4.15.3 file count mismatch expected={EXPECTED_ADVANCED_IMAGE_FILES} actual={advanced_files}"
        )

    if not any(key.startswith("aidirector/davinciresolve/runtime/mcp/advanced/4.8.20/") for key in seen):
        raise RuntimeError("runtime-base v5 does not retain predecessor Advanced 4.8.20 image")
    old_seed = seen.get("aidirector/davinciresolve/updates/mcp/bootstrap/davinci-resolve-mcp-4.10.4-8911bd24aee7.tar.gz")
    if old_seed and old_seed["sha256"] != "48370655E414BAAEC1D18259C5DFD53E4CA2C71C698D60C13A5CA872F7BAA0A6":
        raise RuntimeError("runtime-base v5 retained historical 4.10.4 bootstrap seed has unexpected bytes")

    forbidden_roots = (
        "aidirector/common/runtime/cuda/12.8/",
        "aidirector/davinciresolve/runtime/llama/direct/",
        "aidirector/davinciresolve/runtime/llama/upstream/",
    )
    if "aidirector/common/manifests/cuda-12.8.json" in seen:
        raise RuntimeError("v4 inventory contains retired CUDA 12.8 manifest")
    if any(any(path.startswith(prefix) for prefix in forbidden_roots) for path in seen):
        raise RuntimeError("v4 inventory contains retired legacy runtime roots")
    if any("4.8.22" in path for path in seen):
        raise RuntimeError("v4 inventory contains stale 4.8.22 versioned state")


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != 4 or manifest.get("runtime_base_id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("active runtime-base v5 manifest identity mismatch")
    if manifest.get("payload_role") != "ACTIVE_RUNTIME_BASE":
        raise RuntimeError("active runtime-base v5 manifest role mismatch")
    leaked = sorted(FORBIDDEN_ACTIVE_METADATA.intersection(manifest))
    if leaked:
        raise RuntimeError(f"historical runtime-base metadata remains active: {leaked}")
    if integer_field(manifest, "expected_shipping_file_count", "manifest file count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base v5 manifest file count mismatch")

    baseline = manifest.get("baseline_runtime_inheritance") or {}
    if (
        baseline.get("runtime_base_id") != EXPECTED_BASELINE_RUNTIME_BASE_ID
        or str(baseline.get("shipping_archive_sha256") or "").upper() != EXPECTED_BASELINE_ARCHIVE_SHA256
        or str(baseline.get("shipping_inventory_sha256") or "").upper() != EXPECTED_BASELINE_INVENTORY_SHA256
        or int(baseline.get("file_count") or -1) != EXPECTED_BASELINE_FILE_COUNT
        or baseline.get("preservation_mode") != "AUTHORIZED_REPLACEMENT_ROOTS_ONLY"
        or baseline.get("authorized_replacement_roots") != [
            "davinci-resolve-mcp/",
            "AIDirector/DaVinciResolve/Manifests/",
        ]
    ):
        raise RuntimeError("runtime-base v5 baseline inheritance metadata mismatch")

    active = manifest.get("installed_managed_mcp_baseline") or {}
    if (
        active.get("version") != EXPECTED_ACTIVE_MCP_BASELINE_VERSION
        or active.get("commit") != EXPECTED_ACTIVE_MCP_BASELINE_COMMIT
        or str(active.get("package_json_sha256") or "").upper() != EXPECTED_ACTIVE_MCP_PACKAGE_SHA256
        or str(active.get("server_sha256_after_registered_overlays") or "").upper() != EXPECTED_ACTIVE_MCP_SERVER_SHA256
        or str(active.get("managed_marker_sha256") or "").upper() != EXPECTED_ACTIVE_MCP_MARKER_SHA256
        or active.get("installer_activation") is not False
        or active.get("first_start_overlay_mutation_required") is not False
    ):
        raise RuntimeError("runtime-base v5 active MCP baseline metadata mismatch")

    seed = manifest.get("bundled_mcp_seed") or {}
    if (
        seed.get("version") != EXPECTED_MCP_BOOTSTRAP_VERSION
        or seed.get("commit") != EXPECTED_MCP_COMMIT
        or seed.get("path") != EXPECTED_MCP_BOOTSTRAP_PATH
        or str(seed.get("sha256") or "").upper() != EXPECTED_MCP_BOOTSTRAP_SHA256
        or int(seed.get("bytes") or -1) != EXPECTED_MCP_BOOTSTRAP_BYTES
    ):
        raise RuntimeError("runtime-base v5 MCP 4.15.3 seed metadata mismatch")

    advanced = manifest.get("bundled_advanced_dependency_image") or {}
    checks = {
        "version": EXPECTED_MCP_BOOTSTRAP_VERSION,
        "root": EXPECTED_ADVANCED_ROOT,
        "source_image_zip_sha256": "FE8163322E864CD0F216D3ABF13B7C3F0BA988747BEB9C83D4B8EF1D31C13EF0",
        "payload_manifest_sha256": EXPECTED_ADVANCED_PAYLOAD_MANIFEST_SHA256,
        "mandatory_manifest_sha256": EXPECTED_ADVANCED_MANDATORY_MANIFEST_SHA256,
        "provenance_sha256": EXPECTED_ADVANCED_PROVENANCE_SHA256,
        "native_reproducibility_sha256": EXPECTED_ADVANCED_NATIVE_REPRO_SHA256,
        "third_party_inventory_sha256": EXPECTED_ADVANCED_LICENSE_INVENTORY_SHA256,
        "node_modules_tree_sha256": EXPECTED_ADVANCED_NODE_TREE_SHA256,
    }
    for key, expected in checks.items():
        value = advanced.get(key)
        if isinstance(expected, str) and key.endswith("sha256"):
            value = str(value or "").upper()
        if value != expected:
            raise RuntimeError(f"runtime-base v5 Advanced image metadata mismatch: {key}")
    if int(advanced.get("node_modules_file_count") or -1) != EXPECTED_ADVANCED_NODE_FILES:
        raise RuntimeError("runtime-base v5 Advanced node_modules file count mismatch")
    if int(advanced.get("node_modules_bytes") or -1) != EXPECTED_ADVANCED_NODE_BYTES:
        raise RuntimeError("runtime-base v5 Advanced node_modules bytes mismatch")
    if int(advanced.get("image_file_count") or -1) != EXPECTED_ADVANCED_IMAGE_FILES:
        raise RuntimeError("runtime-base v5 Advanced image file count mismatch")

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

    semantics = manifest.get("clean_install_semantics") or {}
    required_false = (
        "active_managed_mcp_swap_during_installer",
        "active_python_swap_during_installer",
        "active_manifest_rewrite_during_installer",
        "active_mcp_overlay_mutation_on_first_start",
        "vfx_mcp_config_rewrite_during_installer",
    )
    if semantics.get("mode") != "PREVALIDATED_ACTIVE_MCP_BASELINE":
        raise RuntimeError("runtime-base v5 clean-install semantics mode mismatch")
    for key in required_false:
        if semantics.get(key) is not False:
            raise RuntimeError(f"runtime-base v5 clean-install semantics must keep {key}=false")
    if semantics.get("historical_4_10_4_versioned_provenance_retained") is not True:
        raise RuntimeError("runtime-base v5 historical predecessor provenance retention mismatch")

    if str(manifest.get("shipping_archive_sha256") or "").upper() != EXPECTED_SHIPPING_ARCHIVE_SHA256:
        raise RuntimeError("runtime-base v5 manifest archive mismatch")
    if str(manifest.get("shipping_inventory_sha256") or "").upper() != EXPECTED_SHIPPING_INVENTORY_SHA256:
        raise RuntimeError("runtime-base v5 manifest inventory mismatch")
    if integer_field(manifest, "shipping_archive_bytes", "manifest archive bytes", 1) != EXPECTED_SHIPPING_ARCHIVE_BYTES:
        raise RuntimeError("runtime-base v5 manifest archive size mismatch")
    if integer_field(manifest, "inventory_file_count", "manifest inventory count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base v5 manifest inventory count mismatch")
    if manifest.get("archive_filter") != "BCJ":
        raise RuntimeError("runtime-base v5 manifest filter mismatch")
    if manifest.get("shipping_inventory_source_runtime_base_id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("runtime-base v5 manifest inventory source mismatch")


def validate_candidate(candidate, current, builder_sha):
    del builder_sha
    descriptor = candidate["descriptor"]
    root = candidate["root"]
    metadata_root = candidate.get("metadata_root") or root

    if descriptor.get("schema_version") != 4 or descriptor.get("runtime_base_id") != EXPECTED_RUNTIME_BASE_ID:
        raise RuntimeError("active runtime-base v5 descriptor identity mismatch")
    if descriptor.get("kind") != "runtime-base" or descriptor.get("payload_role") != "ACTIVE_RUNTIME_BASE":
        raise RuntimeError("active runtime-base v5 descriptor role mismatch")
    leaked = sorted(FORBIDDEN_ACTIVE_METADATA.intersection(descriptor))
    if leaked:
        raise RuntimeError(f"historical runtime-base metadata remains active: {leaked}")
    if descriptor.get("files") not in ([], None):
        raise RuntimeError("runtime-base may not carry application replacements")
    if descriptor.get("installed_managed_mcp_baseline_version") != EXPECTED_ACTIVE_MCP_BASELINE_VERSION:
        raise RuntimeError("runtime-base v5 installed baseline version mismatch")
    if descriptor.get("bundled_mcp_version") != EXPECTED_MCP_BOOTSTRAP_VERSION or descriptor.get("bundled_mcp_commit") != EXPECTED_MCP_COMMIT:
        raise RuntimeError("runtime-base v5 bundled MCP identity mismatch")
    if descriptor.get("bundled_advanced_version") != EXPECTED_MCP_BOOTSTRAP_VERSION:
        raise RuntimeError("runtime-base v5 bundled Advanced version mismatch")
    if descriptor.get("archive_filter") != "BCJ" or descriptor.get("nsis7z_full_parity_required") is not True:
        raise RuntimeError("runtime-base v5 archive/parity contract mismatch")

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
        raise RuntimeError("runtime-base v5 descriptor archive mismatch")
    if str(descriptor.get("shipping_inventory_sha256") or "").upper() != EXPECTED_SHIPPING_INVENTORY_SHA256:
        raise RuntimeError("runtime-base v5 descriptor inventory mismatch")
    if integer_field(descriptor, "shipping_archive_bytes", "descriptor archive bytes", 1) != EXPECTED_SHIPPING_ARCHIVE_BYTES:
        raise RuntimeError("runtime-base v5 descriptor archive size mismatch")
    if integer_field(descriptor, "inventory_file_count", "descriptor inventory count", 0) != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("runtime-base v5 descriptor inventory count mismatch")

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
        raise RuntimeError("CURRENT active runtime-base v5 identity mismatch")
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
        raise RuntimeError("CURRENT active runtime-base v5 archive binding mismatch")
    if str(entry.get("runtime_base_manifest_sha256") or "").upper() != sha256(metadata_root / RUNTIME_BASE_MANIFEST_NAME):
        raise RuntimeError("CURRENT active runtime-base v5 manifest binding mismatch")
    if str(entry.get("inventory_sha256") or "").upper() != EXPECTED_SHIPPING_INVENTORY_SHA256:
        raise RuntimeError("CURRENT active runtime-base v5 inventory binding mismatch")
    if entry.get("archive_filter") != "BCJ" or entry.get("inventory_file_count") != EXPECTED_SHIPPING_FILE_COUNT:
        raise RuntimeError("CURRENT active runtime-base v5 parity metadata mismatch")
    result["descriptor"] = descriptor
    return result
