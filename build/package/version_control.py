from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
CURRENT_PATH = ROOT / "build" / "package" / "release-state.json"
APP_ROOT = ROOT / "src" / "application"
MANIFEST_PATH = ROOT / "provenance" / "application" / "CANONICAL-SOURCE-MANIFEST.json"
CHECK_PATH = ROOT / "build" / "package" / "check_state.py"
LOCK_PATH = ROOT / "_cache" / ".builder-operation.lock"
VERSION_TRANSACTION_PATH = ROOT / "_cache" / ".version-preparation-transaction"
VERSION_TRANSACTION_CREATING_PREFIX = ".version-preparation-transaction.creating-"
VERSION_TRANSACTION_CLEANUP_PREFIX = ".version-preparation-transaction.cleanup-"
VERSION_TRANSACTION_SCHEMA = 1


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def json_bytes(obj) -> bytes:
    return (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + f".version-{os.getpid()}.tmp")
    try:
        with temp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()



def transaction_atomic_write(path: Path, data: bytes) -> None:
    temp = path.with_name(path.name + ".version-transaction.tmp")
    require(not temp.exists(), f"Version transaction temp residue exists: {temp}")
    try:
        with temp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def parse_semver(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", str(value or ""))
    require(match is not None, f"Invalid semantic version: {value!r}")
    return tuple(int(x) for x in match.groups())


def format_semver(parts: tuple[int, int, int]) -> str:
    return ".".join(str(x) for x in parts)


def select_target(accepted: tuple[int, int, int], args) -> str | None:
    if args.patch:
        return format_semver((accepted[0], accepted[1], accepted[2] + 1))
    if args.minor:
        return format_semver((accepted[0], accepted[1] + 1, 0))
    if args.major:
        return format_semver((accepted[0] + 1, 0, 0))
    if args.version is not None:
        requested = parse_semver(args.version)
        require(requested > accepted, "Explicit target version must be greater than live accepted authority")
        return format_semver(requested)
    return None


def acquire_lock(operation: str, target: str) -> Path:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        LOCK_PATH.mkdir()
    except FileExistsError as exc:
        raise RuntimeError(f"Builder operation lock already exists: {LOCK_PATH}") from exc
    meta = {
        "schema_version": 1,
        "operation": operation,
        "target_version": target,
        "pid": os.getpid(),
    }
    try:
        (LOCK_PATH / "operation.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as original_exc:
        try:
            if LOCK_PATH.exists():
                shutil.rmtree(LOCK_PATH)
            require(not LOCK_PATH.exists(), f"Builder operation lock cleanup failed: {LOCK_PATH}")
        except Exception as cleanup_exc:
            raise RuntimeError(
                f"Builder operation lock creation failed and cleanup could not be proven: "
                f"original={original_exc!r}; cleanup={cleanup_exc!r}"
            ) from original_exc
        raise
    return LOCK_PATH


def release_lock() -> None:
    if LOCK_PATH.exists():
        shutil.rmtree(LOCK_PATH)
    require(not LOCK_PATH.exists(), f"Builder operation lock residue remains: {LOCK_PATH}")
    cache_root = ROOT / "_cache"
    try:
        if cache_root.is_dir() and not any(cache_root.iterdir()):
            cache_root.rmdir()
    except Exception:
        pass


def inherited_lock_owner() -> tuple[str, str] | None:
    inherited = os.environ.get("AI_DIRECTOR_INHERITED_OPERATION_LOCK") == "1"
    operation = str(os.environ.get("AI_DIRECTOR_EXPECT_OPERATION") or "")
    owner_pid = str(os.environ.get("AI_DIRECTOR_EXPECT_OPERATION_PID") or "")
    if not inherited:
        require(not operation and not owner_pid,
                "Builder lock expectation environment is present without inherited-lock authorization")
        return None
    require(operation in ("BUILD", "ACCEPT"), "Inherited version control requires BUILD or ACCEPT operation ownership")
    require(owner_pid, "Inherited Builder operation owner PID missing")
    require(LOCK_PATH.is_dir(), f"Inherited Builder operation lock missing: {LOCK_PATH}")
    meta_path = LOCK_PATH / "operation.json"
    require(meta_path.is_file(), f"Inherited Builder operation lock metadata missing: {meta_path}")
    meta = read_json(meta_path)
    require(meta.get("operation") == operation, "Inherited Builder operation lock operation mismatch")
    require(str(meta.get("pid")) == owner_pid, "Inherited Builder operation lock owner PID mismatch")
    return operation, owner_pid


def scan_staging(current: dict) -> list[str]:
    policy = current.get("build_output_policy") or {}
    require(policy.get("mode") == "BUILDER_PARENT_RELATIVE_SEQUENTIAL", "Build-output policy mismatch")
    rel_root = Path(str(policy.get("relative_root") or ""))
    require(not rel_root.is_absolute() and ".." not in rel_root.parts, "Unsafe build-output relative root")
    rc_root = ROOT.parent / rel_root
    stale = []
    if rc_root.exists():
        require(rc_root.is_dir(), f"Release-candidate root is not a directory: {rc_root}")
        for version_dir in rc_root.iterdir():
            if not version_dir.is_dir():
                continue
            for item in version_dir.iterdir():
                if item.name.startswith(".static-build-") and ".staging-" in item.name:
                    stale.append(str(item))
    return sorted(stale)


def validate_current_for_versioning() -> tuple[dict, tuple[int, int, int], tuple[int, int, int]]:
    require(ROOT.is_dir(), f"Builder root missing: {ROOT}")
    require(CURRENT_PATH.is_file(), f"CURRENT missing: {CURRENT_PATH}")
    require(APP_ROOT.is_dir(), f"Canonical application missing: {APP_ROOT}")
    require(MANIFEST_PATH.is_file(), f"Canonical manifest missing: {MANIFEST_PATH}")
    require(CHECK_PATH.is_file(), f"Checker missing: {CHECK_PATH}")
    require(not (ROOT / "artifacts").exists(), "Legacy builder-local artifacts directory must be absent")
    require(not (ROOT / "reports").exists(), "Legacy builder-local reports directory must be absent")
    inherited_owner = inherited_lock_owner()
    if inherited_owner is None:
        require(not LOCK_PATH.exists(), f"Builder operation lock exists: {LOCK_PATH}")

    current = read_json(CURRENT_PATH)
    require(current.get("schema_version") == 5, "CURRENT schema mismatch")
    require(current.get("product") == "DaVinci Resolve AI Director", "CURRENT product mismatch")
    require(current.get("builder_mode") == "CANONICAL_SOURCE_BUILDER", "CURRENT builder mode mismatch")
    require(current.get("application_source_authority") == "CANONICAL", "CURRENT application authority mismatch")

    lifecycle = current.get("version_lifecycle") or {}
    require(lifecycle.get("policy") == "ACCEPTED_AUTHORITY_DERIVED_V1", "Version-lifecycle policy mismatch")
    require(lifecycle.get("build_advances_accepted_authority") is False, "BUILD authority policy mismatch")
    require(lifecycle.get("failed_build_consumes_version") is False, "Failed-build version policy mismatch")
    require(lifecycle.get("acceptance_promotion") == "SEPARATE_EXPLICIT_GATE", "Acceptance promotion policy mismatch")

    accepted = parse_semver(str(current.get("live_accepted_authority") or ""))
    stable = parse_semver(str(current.get("stable_version") or ""))
    target = parse_semver(str(current.get("target_version") or ""))
    require(stable == accepted, "stable_version must equal live accepted authority")
    state = current.get("state_mode")
    require(state in ("TARGET_READY", "ACCEPTED_READY"), f"Unsupported version state: {state!r}")
    if state == "TARGET_READY":
        require(target > accepted, "TARGET_READY requires target > accepted authority")
    else:
        require(target == accepted, "ACCEPTED_READY requires target == accepted authority")

    bindings = current.get("control_bindings") or {}
    require(str(bindings.get("version_control.py") or "").upper() == sha256(Path(__file__).resolve()), "version_control.py binding mismatch")
    require(str(bindings.get("check_state.py") or "").upper() == sha256(CHECK_PATH), "check_state.py binding mismatch")
    require(str(bindings.get("VERSION.cmd") or "").upper() == sha256(ROOT / "VERSION.cmd"), "VERSION.cmd binding mismatch")

    require(not scan_staging(current), "Incomplete release-candidate staging residue exists")
    return current, accepted, target


def validate_manifest_against_tree(current: dict) -> None:
    target = str(current.get("target_version") or "")
    canonical = current.get("canonical_application") or {}
    require(sha256(MANIFEST_PATH) == str(canonical.get("manifest_sha256") or "").upper(), "Canonical manifest binding mismatch")
    manifest = read_json(MANIFEST_PATH)
    require(manifest.get("schema_version") == 2, "Canonical manifest schema mismatch")
    require(manifest.get("id") == f"AI-Director-Canonical-Application-{target}-v1", "Canonical manifest id mismatch")
    require(manifest.get("version") == target, "Canonical manifest version mismatch")
    require(manifest.get("source_phase") == current.get("state_mode"), "Canonical manifest source phase mismatch")
    rows = manifest.get("files")
    require(isinstance(rows, list) and len(rows) == 13 and manifest.get("file_count") == 13, "Canonical manifest file count mismatch")
    expected = set()
    for row in rows:
        rel = str(row.get("path") or "").replace("\\", "/")
        require(rel and not rel.startswith("/") and ".." not in Path(rel).parts, f"Unsafe canonical manifest path: {rel}")
        path = APP_ROOT / Path(rel)
        require(path.is_file(), f"Canonical source file missing: {rel}")
        require(sha256(path) == str(row.get("sha256") or "").upper(), f"Canonical source hash mismatch: {rel}")
        require(path.stat().st_size == int(row.get("bytes") or -1), f"Canonical source size mismatch: {rel}")
        expected.add(rel)
    actual = {p.relative_to(APP_ROOT).as_posix() for p in APP_ROOT.rglob("*") if p.is_file()}
    require(actual == expected, "Canonical source manifest/tree mismatch")

    package = read_json(APP_ROOT / "package.json")
    lock = read_json(APP_ROOT / "package-lock.json")
    require(package.get("version") == target, "package.json version mismatch")
    require(lock.get("version") == target, "package-lock.json version mismatch")
    require(isinstance(lock.get("packages"), dict) and isinstance(lock["packages"].get(""), dict), "package-lock root package missing")
    require(lock["packages"][""].get("version") == target, "package-lock root package version mismatch")


def prospective_payloads(current: dict, selected: str) -> dict[str, bytes]:
    package = read_json(APP_ROOT / "package.json")
    lock = read_json(APP_ROOT / "package-lock.json")
    package["version"] = selected
    lock["version"] = selected
    require(isinstance(lock.get("packages"), dict) and isinstance(lock["packages"].get(""), dict), "package-lock root package missing")
    lock["packages"][""]["version"] = selected

    package_bytes = json_bytes(package)
    lock_bytes = json_bytes(lock)
    replacements = {
        "package.json": package_bytes,
        "package-lock.json": lock_bytes,
    }

    actual = {p.relative_to(APP_ROOT).as_posix(): p for p in APP_ROOT.rglob("*") if p.is_file()}
    require(len(actual) == 13, f"Canonical source file count mismatch: {len(actual)}")
    rows = []
    for rel in sorted(actual):
        data = replacements.get(rel, actual[rel].read_bytes())
        rows.append({
            "path": rel,
            "sha256": sha256_bytes(data),
            "bytes": len(data),
        })
    manifest = {
        "schema_version": 2,
        "id": f"AI-Director-Canonical-Application-{selected}-v1",
        "product": "DaVinci Resolve AI Director",
        "version": selected,
        "source_authority": "CANONICAL",
        "source_phase": "TARGET_READY",
        "file_count": 13,
        "files": rows,
        "active_application_overlay_composition": False,
    }
    manifest_bytes = json_bytes(manifest)
    manifest_sha = sha256_bytes(manifest_bytes)

    next_current = dict(current)
    next_current["state_mode"] = "TARGET_READY"
    next_current["target_version"] = selected
    next_current["stable_version"] = str(current.get("live_accepted_authority"))
    next_current["canonical_application"] = {
        "id": f"AI-Director-Canonical-Application-{selected}-v1",
        "source_dir": "src/application",
        "manifest_path": "provenance/application/CANONICAL-SOURCE-MANIFEST.json",
        "manifest_sha256": manifest_sha,
        "file_count": 13,
    }
    next_current.pop("last_build_status", None)
    next_current.pop("build_authorized", None)
    next_current.pop("release_candidate_output_root", None)
    next_current.pop("final_stable_builder_target", None)

    return {
        "package.json": package_bytes,
        "package-lock.json": lock_bytes,
        "manifest": manifest_bytes,
        "current": json_bytes(next_current),
    }


def run_checker(expect_lock: bool) -> None:
    py = ROOT / "_toolchain" / "Python" / "3.11.9" / "python.exe"
    require(py.is_file(), f"Owned Python missing: {py}")
    env = os.environ.copy()
    if expect_lock:
        inherited_owner = inherited_lock_owner()
        if inherited_owner is None:
            env["AI_DIRECTOR_EXPECT_OPERATION"] = "VERSION"
            env["AI_DIRECTOR_EXPECT_OPERATION_PID"] = str(os.getpid())
        else:
            env["AI_DIRECTOR_EXPECT_OPERATION"] = inherited_owner[0]
            env["AI_DIRECTOR_EXPECT_OPERATION_PID"] = inherited_owner[1]
    cp = subprocess.run(
        [str(py), "-B", str(CHECK_PATH)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    output = (cp.stdout or b"").decode("utf-8", errors="replace")
    if output:
        print(output.rstrip())
    require(
        cp.returncode == 0 and "CHECK_STATE_STATUS=PASS" in output,
        f"Published CHECK-STATE failed exit={cp.returncode}",
    )



def version_transaction_file_specs() -> tuple[tuple[str, Path, str], ...]:
    return (
        ("package.json", APP_ROOT / "package.json", "package.json"),
        ("package-lock.json", APP_ROOT / "package-lock.json", "package-lock.json"),
        ("manifest", MANIFEST_PATH, "CANONICAL-SOURCE-MANIFEST.json"),
        ("current", CURRENT_PATH, "CURRENT.json"),
    )


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes

        process_query_limited_information = 0x1000
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        # ERROR_ACCESS_DENIED means the process exists but cannot be queried.
        return int(kernel32.GetLastError()) == 5

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def cleanup_cache_root_if_empty() -> None:
    cache_root = ROOT / "_cache"
    try:
        if cache_root.is_dir() and not any(cache_root.iterdir()):
            cache_root.rmdir()
    except Exception:
        pass


def read_lock_metadata() -> dict | None:
    if not LOCK_PATH.exists():
        return None
    require(LOCK_PATH.is_dir(), f"Builder operation lock path is not a directory: {LOCK_PATH}")
    meta_path = LOCK_PATH / "operation.json"
    require(meta_path.is_file(), f"Builder operation lock metadata missing: {meta_path}")
    return read_json(meta_path)


def transaction_owner(meta: dict) -> tuple[str, int]:
    owner = meta.get("owner") or {}
    operation = str(owner.get("operation") or "")
    try:
        pid = int(owner.get("pid"))
    except Exception as exc:
        raise RuntimeError("Version transaction owner PID is invalid") from exc
    require(operation in ("VERSION", "BUILD"), "Version transaction owner operation is invalid")
    require(pid > 0, "Version transaction owner PID is invalid")
    return operation, pid


def current_expected_lock_owner() -> tuple[str, int] | None:
    if os.environ.get("AI_DIRECTOR_INHERITED_OPERATION_LOCK") != "1":
        return None
    operation, owner_pid = inherited_lock_owner() or ("", "")
    return operation, int(owner_pid)


def remove_bound_stale_lock_if_safe(meta: dict) -> None:
    lock_meta = read_lock_metadata()
    if lock_meta is None:
        return

    expected = current_expected_lock_owner()
    lock_operation = str(lock_meta.get("operation") or "")
    try:
        lock_pid = int(lock_meta.get("pid"))
    except Exception as exc:
        raise RuntimeError("Builder operation lock PID is invalid") from exc

    if expected is not None:
        require(
            (lock_operation, lock_pid) == expected,
            "Active inherited Builder lock does not match recovery caller",
        )
        tx_operation, tx_pid = transaction_owner(meta)
        require(
            (tx_operation, tx_pid) != expected,
            "Refusing to recover a version transaction owned by the active Builder process",
        )
        require(
            not process_exists(tx_pid),
            "Refusing to recover while the recorded transaction owner is still alive",
        )
        return

    tx_operation, tx_pid = transaction_owner(meta)
    require(
        (lock_operation, lock_pid) == (tx_operation, tx_pid),
        "Builder lock is not owned by the interrupted version transaction",
    )
    require(
        not process_exists(tx_pid),
        "Refusing to remove Builder lock while its recorded owner is still alive",
    )

    shutil.rmtree(LOCK_PATH)
    require(not LOCK_PATH.exists(), "Unable to remove stale Builder operation lock")
    print(f"STALE_{tx_operation}_LOCK_REMOVED=True")



def cleanup_abandoned_transaction_cleanup() -> None:
    cache_root = ROOT / "_cache"
    if not cache_root.is_dir():
        return

    residues = sorted(
        p
        for p in cache_root.iterdir()
        if p.is_dir() and p.name.startswith(VERSION_TRANSACTION_CLEANUP_PREFIX)
    )
    if not residues:
        return

    lock_meta = read_lock_metadata()
    if lock_meta is not None:
        lock_operation = str(lock_meta.get("operation") or "")
        lock_pid = int(lock_meta.get("pid"))
        require(
            lock_operation in ("VERSION", "BUILD"),
            "Version-transaction cleanup residue is paired with an unrelated Builder lock",
        )
        require(
            not process_exists(lock_pid),
            "Version-transaction cleanup residue is paired with a live Builder operation",
        )
        shutil.rmtree(LOCK_PATH)
        print(f"STALE_{lock_operation}_LOCK_REMOVED=True")

    for residue in residues:
        shutil.rmtree(residue)
        print(f"VERSION_TRANSACTION_CLEANUP_RESIDUE_REMOVED={residue.name}")

    cleanup_cache_root_if_empty()


def cleanup_abandoned_transaction_creation() -> None:
    cache_root = ROOT / "_cache"
    if not cache_root.is_dir():
        return

    creating = sorted(
        p
        for p in cache_root.iterdir()
        if p.is_dir() and p.name.startswith(VERSION_TRANSACTION_CREATING_PREFIX)
    )
    if not creating:
        return

    require(
        not VERSION_TRANSACTION_PATH.exists(),
        "Both committed and creating version-transaction directories exist",
    )
    require(
        len(creating) == 1,
        f"Multiple version-transaction creation residues exist: {[p.name for p in creating]}",
    )

    stage = creating[0]
    meta_path = stage / "transaction.json"
    meta = read_json(meta_path) if meta_path.is_file() else None

    lock_meta = read_lock_metadata()
    if meta is not None:
        tx_operation, tx_pid = transaction_owner(meta)
        require(
            not process_exists(tx_pid),
            "Version-transaction creation is still owned by a live process",
        )
        if lock_meta is not None:
            require(
                str(lock_meta.get("operation") or "") == tx_operation
                and int(lock_meta.get("pid")) == tx_pid,
                "Creation residue Builder lock does not match transaction owner",
            )
            shutil.rmtree(LOCK_PATH)
            print(f"STALE_{tx_operation}_LOCK_REMOVED=True")
    elif lock_meta is not None:
        lock_operation = str(lock_meta.get("operation") or "")
        lock_pid = int(lock_meta.get("pid"))
        require(
            lock_operation in ("VERSION", "BUILD"),
            "Creation residue is paired with an unrelated Builder operation lock",
        )
        require(
            not process_exists(lock_pid),
            "Version-transaction creation residue is paired with a live Builder operation",
        )
        shutil.rmtree(LOCK_PATH)
        print(f"STALE_{lock_operation}_LOCK_REMOVED=True")

    shutil.rmtree(stage)
    print("VERSION_TRANSACTION_CREATION_RESIDUE_CLEANED=True")
    cleanup_cache_root_if_empty()


def load_version_transaction() -> dict:
    require(
        VERSION_TRANSACTION_PATH.is_dir(),
        f"Version transaction directory missing: {VERSION_TRANSACTION_PATH}",
    )
    meta_path = VERSION_TRANSACTION_PATH / "transaction.json"
    require(meta_path.is_file(), "Version transaction metadata is missing")
    meta = read_json(meta_path)
    require(meta.get("schema_version") == VERSION_TRANSACTION_SCHEMA, "Version transaction schema mismatch")
    require(meta.get("transaction_type") == "SEMVER_PREPARATION", "Version transaction type mismatch")

    rows = meta.get("files")
    require(isinstance(rows, list) and len(rows) == 4, "Version transaction file set mismatch")
    expected_paths = {
        label: path.relative_to(ROOT).as_posix()
        for label, path, _ in version_transaction_file_specs()
    }
    row_map = {}
    for row in rows:
        label = str(row.get("label") or "")
        require(label in expected_paths and label not in row_map, f"Unexpected version transaction file label: {label!r}")
        require(str(row.get("path") or "") == expected_paths[label], f"Version transaction path mismatch: {label}")
        backup_name = str(row.get("backup_name") or "")
        require(backup_name and "/" not in backup_name and "\\" not in backup_name, f"Unsafe backup name: {backup_name!r}")
        original_sha = str(row.get("original_sha256") or "").upper()
        prospective_sha = str(row.get("prospective_sha256") or "").upper()
        require(re.fullmatch(r"[0-9A-F]{64}", original_sha) is not None, f"Invalid original SHA: {label}")
        require(re.fullmatch(r"[0-9A-F]{64}", prospective_sha) is not None, f"Invalid prospective SHA: {label}")
        backup = VERSION_TRANSACTION_PATH / "originals" / backup_name
        require(backup.is_file(), f"Version transaction backup missing: {backup_name}")
        require(sha256(backup) == original_sha, f"Version transaction backup hash mismatch: {label}")
        row_map[label] = row

    require(set(row_map) == set(expected_paths), "Version transaction labels are incomplete")
    transaction_owner(meta)
    return meta


def create_version_transaction(
    current: dict,
    selected: str,
    payloads: dict[str, bytes],
) -> dict:
    require(not VERSION_TRANSACTION_PATH.exists(), "Version transaction already exists")
    cache_root = ROOT / "_cache"
    cache_root.mkdir(parents=True, exist_ok=True)

    creating = cache_root / f"{VERSION_TRANSACTION_CREATING_PREFIX}{os.getpid()}"
    require(not creating.exists(), f"Version transaction creation path already exists: {creating}")

    inherited_owner = inherited_lock_owner()
    if inherited_owner is None:
        lock_meta = read_lock_metadata()
        require(lock_meta is not None, "Standalone VERSION lock missing before transaction creation")
        require(lock_meta.get("operation") == "VERSION", "Standalone VERSION lock operation mismatch")
        require(int(lock_meta.get("pid")) == os.getpid(), "Standalone VERSION lock owner mismatch")
        owner_operation = "VERSION"
        owner_pid = os.getpid()
    else:
        owner_operation = inherited_owner[0]
        owner_pid = int(inherited_owner[1])

    payload_by_label = {
        "package.json": payloads["package.json"],
        "package-lock.json": payloads["package-lock.json"],
        "manifest": payloads["manifest"],
        "current": payloads["current"],
    }

    try:
        (creating / "originals").mkdir(parents=True)
        rows = []
        for label, path, backup_name in version_transaction_file_specs():
            original = path.read_bytes()
            prospective = payload_by_label[label]
            backup = creating / "originals" / backup_name
            atomic_write(backup, original)
            rows.append(
                {
                    "label": label,
                    "path": path.relative_to(ROOT).as_posix(),
                    "backup_name": backup_name,
                    "original_sha256": sha256_bytes(original),
                    "original_bytes": len(original),
                    "prospective_sha256": sha256_bytes(prospective),
                    "prospective_bytes": len(prospective),
                }
            )

        meta = {
            "schema_version": VERSION_TRANSACTION_SCHEMA,
            "transaction_type": "SEMVER_PREPARATION",
            "phase": "READY_FOR_COMMIT",
            "selected_target": selected,
            "accepted_authority_before": str(current.get("live_accepted_authority") or ""),
            "state_mode_before": str(current.get("state_mode") or ""),
            "target_version_before": str(current.get("target_version") or ""),
            "owner": {
                "operation": owner_operation,
                "pid": owner_pid,
            },
            "files": rows,
        }
        atomic_write(creating / "transaction.json", json_bytes(meta))
        os.replace(creating, VERSION_TRANSACTION_PATH)
        require(VERSION_TRANSACTION_PATH.is_dir(), "Version transaction journal was not committed")
        loaded = load_version_transaction()
        print("VERSION_TRANSACTION_JOURNAL=READY")
        return loaded
    except Exception as original_exc:
        try:
            if creating.exists():
                shutil.rmtree(creating)
            require(not creating.exists(), f"Version transaction creation cleanup failed: {creating}")
        except Exception as cleanup_exc:
            raise RuntimeError(
                f"Version transaction creation failed and cleanup could not be proven: "
                f"original={original_exc!r}; cleanup={cleanup_exc!r}"
            ) from original_exc
        raise



def cleanup_version_transaction_live_temps() -> None:
    removed = []
    for _, path, _ in version_transaction_file_specs():
        temp = path.with_name(path.name + ".version-transaction.tmp")
        if temp.exists():
            require(temp.is_file(), f"Version transaction temp path is not a file: {temp}")
            temp.unlink()
            removed.append(temp.relative_to(ROOT).as_posix())
    if removed:
        print("VERSION_TRANSACTION_WRITE_TEMPS_CLEANED=" + ",".join(sorted(removed)))


def version_transaction_live_states(meta: dict) -> dict[str, str]:
    row_map = {str(row.get("label")): row for row in meta["files"]}
    states = {}
    for label, path, _ in version_transaction_file_specs():
        require(path.is_file(), f"Version transaction live file missing: {path.relative_to(ROOT)}")
        live_sha = sha256(path)
        original_sha = str(row_map[label]["original_sha256"]).upper()
        prospective_sha = str(row_map[label]["prospective_sha256"]).upper()
        if live_sha == original_sha:
            states[label] = "ORIGINAL"
        elif live_sha == prospective_sha:
            states[label] = "PROSPECTIVE"
        else:
            states[label] = "UNEXPECTED"
    return states


def restore_version_transaction_originals(meta: dict) -> None:
    row_map = {str(row.get("label")): row for row in meta["files"]}
    for label, path, backup_name in version_transaction_file_specs():
        row = row_map[label]
        backup = VERSION_TRANSACTION_PATH / "originals" / backup_name
        data = backup.read_bytes()
        require(
            sha256_bytes(data) == str(row.get("original_sha256") or "").upper(),
            f"Version transaction backup changed: {label}",
        )
        transaction_atomic_write(path, data)

    states = version_transaction_live_states(meta)
    require(
        all(value == "ORIGINAL" for value in states.values()),
        f"Version transaction rollback did not restore exact originals: {states}",
    )


def remove_version_transaction_journal() -> None:
    if not VERSION_TRANSACTION_PATH.exists():
        cleanup_cache_root_if_empty()
        return

    cache_root = ROOT / "_cache"
    cleanup = cache_root / f"{VERSION_TRANSACTION_CLEANUP_PREFIX}{os.getpid()}"
    require(not cleanup.exists(), f"Version transaction cleanup path already exists: {cleanup}")
    os.replace(VERSION_TRANSACTION_PATH, cleanup)
    require(not VERSION_TRANSACTION_PATH.exists(), "Version transaction journal rename did not complete")
    shutil.rmtree(cleanup)
    require(not cleanup.exists(), "Version transaction cleanup residue remains")
    cleanup_cache_root_if_empty()


def acquire_recovery_lock_if_needed(meta: dict) -> bool:
    if os.environ.get("AI_DIRECTOR_INHERITED_OPERATION_LOCK") == "1":
        inherited_lock_owner()
        return False

    require(not LOCK_PATH.exists(), f"Unexpected Builder operation lock during recovery: {LOCK_PATH}")
    selected = str(meta.get("selected_target") or "")
    parse_semver(selected)
    acquire_lock("VERSION", selected)
    print("VERSION_TRANSACTION_RECOVERY_LOCK=ACQUIRED")
    return True


def recover_pending_version_transaction() -> str:
    cleanup_abandoned_transaction_cleanup()
    cleanup_abandoned_transaction_creation()

    if not VERSION_TRANSACTION_PATH.exists():
        return "NOT_REQUIRED"

    meta = load_version_transaction()
    cleanup_version_transaction_live_temps()
    tx_operation, tx_pid = transaction_owner(meta)

    if process_exists(tx_pid):
        expected = current_expected_lock_owner()
        require(
            expected is not None and expected != (tx_operation, tx_pid),
            "Refusing to recover a version transaction whose owner is still alive",
        )

    remove_bound_stale_lock_if_safe(meta)
    owns_recovery_lock = acquire_recovery_lock_if_needed(meta)
    recovery_lock_released = False

    try:
        states = version_transaction_live_states(meta)
        print(
            "VERSION_TRANSACTION_LIVE_STATE="
            + ",".join(f"{label}:{states[label]}" for label in sorted(states))
        )

        require(
            all(value != "UNEXPECTED" for value in states.values()),
            f"Version transaction contains an unexpected live-file identity; recovery preserved: {states}",
        )

        unique = set(states.values())

        if unique == {"PROSPECTIVE"}:
            run_checker(expect_lock=True)
            if owns_recovery_lock:
                release_lock()
                recovery_lock_released = True
            remove_version_transaction_journal()
            print("VERSION_TRANSACTION_RECOVERY=COMMIT_FINALIZED")
            return "COMMIT_FINALIZED"

        if unique == {"ORIGINAL"}:
            run_checker(expect_lock=True)
            if owns_recovery_lock:
                release_lock()
                recovery_lock_released = True
            remove_version_transaction_journal()
            print("VERSION_TRANSACTION_RECOVERY=ORIGINAL_STATE_CONFIRMED")
            return "ORIGINAL_STATE_CONFIRMED"

        restore_version_transaction_originals(meta)
        run_checker(expect_lock=True)
        if owns_recovery_lock:
            release_lock()
            recovery_lock_released = True
        remove_version_transaction_journal()
        print("VERSION_TRANSACTION_RECOVERY=ROLLBACK_RESTORED")
        return "ROLLBACK_RESTORED"

    finally:
        if owns_recovery_lock and not recovery_lock_released and LOCK_PATH.exists():
            release_lock()


def rollback_active_version_transaction() -> None:
    meta = load_version_transaction()
    restore_version_transaction_originals(meta)
    run_checker(expect_lock=True)
    remove_version_transaction_journal()
    print("VERSION_TRANSACTION_ROLLBACK=PASS_EXACT_PREPARATION_STATE_RESTORED")




def require_read_only_version_recovery_absent() -> None:
    cache_root = ROOT / "_cache"
    pending = []
    if VERSION_TRANSACTION_PATH.exists():
        pending.append(VERSION_TRANSACTION_PATH.name)
    if cache_root.is_dir():
        pending.extend(
            sorted(
                path.name
                for path in cache_root.iterdir()
                if path.is_dir()
                and (
                    path.name.startswith(VERSION_TRANSACTION_CREATING_PREFIX)
                    or path.name.startswith(VERSION_TRANSACTION_CLEANUP_PREFIX)
                )
            )
        )
    require(
        not pending,
        "Read-only VERSION operation refuses pending version recovery state: "
        + ", ".join(pending)
        + ". Run VERSION.cmd --recover-if-needed explicitly before retrying.",
    )

def status(current: dict, accepted: tuple[int, int, int], target: tuple[int, int, int]) -> int:
    print(f"LIVE_ACCEPTED_AUTHORITY={format_semver(accepted)}")
    print(f"PREPARED_TARGET_VERSION={format_semver(target)}")
    print(f"VERSION_STATE={current.get('state_mode')}")
    print(f"NEXT_PATCH={format_semver((accepted[0], accepted[1], accepted[2] + 1))}")
    print(f"NEXT_MINOR={format_semver((accepted[0], accepted[1] + 1, 0))}")
    print(f"NEXT_MAJOR={format_semver((accepted[0] + 1, 0, 0))}")
    print("BUILD_ADVANCES_ACCEPTED_AUTHORITY=False")
    print("FAILED_BUILD_CONSUMES_VERSION=False")
    print("ACCEPTANCE_PROMOTION=SEPARATE_EXPLICIT_GATE")
    print("VERSION_STATUS=PASS")
    return 0


def parse_args():
    p = argparse.ArgumentParser(description="AI Director semantic version lifecycle control.")
    p.add_argument(
        "command",
        nargs="?",
        choices=("status",),
        help="Read-only lifecycle command. 'status' shows accepted/target/next versions.",
    )
    group = p.add_mutually_exclusive_group()
    group.add_argument("--patch", action="store_true", help="Prepare next patch from live accepted authority.")
    group.add_argument("--minor", action="store_true", help="Prepare next minor from live accepted authority.")
    group.add_argument("--major", action="store_true", help="Prepare next major from live accepted authority.")
    group.add_argument("--version", metavar="X.Y.Z", help="Prepare an explicit version greater than live accepted authority.")
    p.add_argument("--apply", action="store_true", help="Apply the selected version preparation transaction.")
    p.add_argument(
        "--recover-if-needed",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    p.add_argument(
        "--retarget",
        action="store_true",
        help=(
            "Explicitly replace a different prepared TARGET_READY target. "
            "Standalone VERSION control only; never implicit through BUILD."
        ),
    )
    args = p.parse_args()
    if args.command == "status":
        if args.patch or args.minor or args.major or args.version or args.apply or args.retarget or args.recover_if_needed:
            p.error("'status' cannot be combined with a version-selection option, --apply, --retarget, or recovery mode")
    if args.recover_if_needed:
        if args.patch or args.minor or args.major or args.version or args.apply or args.retarget or args.command:
            p.error("--recover-if-needed cannot be combined with other version-control options")
    if args.retarget and not (args.patch or args.minor or args.major or args.version):
        p.error("--retarget requires --patch, --minor, --major, or --version")
    return args


def main() -> int:
    args = parse_args()
    print("AI_DIRECTOR_VERSION_LIFECYCLE_V1")
    print(f"ROOT={ROOT}")
    print("BUILD_EXECUTED=False")
    print("SETUP_EXECUTED=False")
    print("INSTALLED_PRODUCT_TOUCHED=False")

    if args.recover_if_needed:
        recovery_status = recover_pending_version_transaction()
        print(f"VERSION_TRANSACTION_RECOVERY_STATUS={recovery_status}")
        print("VERSION_TRANSACTION_RECOVERY_GATE=PASS")
        return 0

    if args.apply:
        recovery_status = recover_pending_version_transaction()
        print(f"VERSION_TRANSACTION_RECOVERY_STATUS={recovery_status}")
    else:
        require_read_only_version_recovery_absent()
        print("VERSION_TRANSACTION_RECOVERY_STATUS=NOT_RUN_READ_ONLY")

    current, accepted, current_target = validate_current_for_versioning()
    validate_manifest_against_tree(current)
    selected = select_target(accepted, args)

    inherited_owner = inherited_lock_owner()
    if inherited_owner is not None and inherited_owner[0] == "ACCEPT":
        require(
            selected is None and not args.apply and not args.retarget,
            "ACCEPT operation ownership authorizes read-only VERSION status only",
        )

    if selected is None:
        require(not args.apply, "--apply requires --patch, --minor, --major, or --version")
        return status(current, accepted, current_target)

    print(f"LIVE_ACCEPTED_AUTHORITY={format_semver(accepted)}")
    print(f"CURRENT_PREPARED_TARGET={format_semver(current_target)}")
    print(f"SELECTED_TARGET={selected}")
    print("VERSION_DERIVATION_BASE=LIVE_ACCEPTED_AUTHORITY")
    print("BUILD_RESULT_HISTORY_USED_FOR_VERSION_SELECTION=False")

    prepared_target = str(current.get("target_version") or "")
    state = str(current.get("state_mode") or "")
    different_prepared_target = state == "TARGET_READY" and selected != prepared_target

    if different_prepared_target:
        if not args.retarget:
            raise RuntimeError(
                f"Builder already has prepared target {prepared_target}; refusing to retarget to {selected}. "
                "To intentionally abandon/replace the prepared target, use standalone VERSION.cmd "
                "with the same selection plus --retarget --apply."
            )
        require(
            inherited_lock_owner() is None,
            "Explicit --retarget is allowed only from standalone VERSION control, never under BUILD orchestration",
        )
        print("RETARGET_ACKNOWLEDGED=True")
        print(f"PREVIOUS_PREPARED_TARGET={prepared_target}")
        print(f"REPLACEMENT_PREPARED_TARGET={selected}")
        print("HISTORICAL_RELEASE_CANDIDATES_PRESERVED=True")
    elif args.retarget:
        raise RuntimeError(
            "--retarget requires TARGET_READY with a selected target different from the currently prepared target"
        )

    if selected == prepared_target:
        print("VERSION_PREPARATION_STATUS=ALREADY_PREPARED")
        print("BUILDER_MUTATED=False")
        return 0

    payloads = prospective_payloads(current, selected)
    print(f"PROSPECTIVE_PACKAGE_SHA256={sha256_bytes(payloads['package.json'])}")
    print(f"PROSPECTIVE_PACKAGE_LOCK_SHA256={sha256_bytes(payloads['package-lock.json'])}")
    print(f"PROSPECTIVE_MANIFEST_SHA256={sha256_bytes(payloads['manifest'])}")
    print(f"PROSPECTIVE_CURRENT_SHA256={sha256_bytes(payloads['current'])}")

    if not args.apply:
        print("BUILDER_MUTATED=False")
        print("DRY_RUN_STATUS=PASS")
        print("APPLY_READY=True")
        return 0

    inherited_owner = inherited_lock_owner()
    owns_lock = inherited_owner is None
    lock_released = False
    commit_verified = False
    preserve_recovery = False

    if owns_lock:
        acquire_lock("VERSION", selected)

    try:
        create_version_transaction(current, selected, payloads)

        transaction_atomic_write(APP_ROOT / "package.json", payloads["package.json"])
        transaction_atomic_write(APP_ROOT / "package-lock.json", payloads["package-lock.json"])
        transaction_atomic_write(MANIFEST_PATH, payloads["manifest"])
        transaction_atomic_write(CURRENT_PATH, payloads["current"])

        run_checker(expect_lock=True)
        commit_verified = True

        # For standalone VERSION, release the operation lock before deleting the
        # journal. If the process terminates in this narrow window, the durable
        # journal can still prove/finalize the already-checked prospective state.
        if owns_lock:
            release_lock()
            lock_released = True

        remove_version_transaction_journal()

        print(f"PREPARED_TARGET_VERSION={selected}")
        print("LIVE_ACCEPTED_AUTHORITY_UNCHANGED=True")
        print("VERSION_PREPARATION_TRANSACTION=DURABLE_V1")
        print("VERSION_PREPARATION_STATUS=PASS")
        return 0

    except BaseException as exc:
        if VERSION_TRANSACTION_PATH.exists():
            if commit_verified:
                preserve_recovery = True
                print("VERSION_TRANSACTION_COMMIT_VERIFIED_CLEANUP_PENDING=True")
                print(f"VERSION_TRANSACTION_RECOVERY_PRESERVED={VERSION_TRANSACTION_PATH}")
            else:
                try:
                    rollback_active_version_transaction()
                except Exception as rollback_exc:
                    preserve_recovery = True
                    print("VERSION_TRANSACTION_ROLLBACK=ERROR")
                    print(f"VERSION_TRANSACTION_ROLLBACK_ERROR={rollback_exc}")
                    print(f"VERSION_TRANSACTION_RECOVERY_PRESERVED={VERSION_TRANSACTION_PATH}")
                    if isinstance(exc, Exception):
                        raise RuntimeError(
                            f"Version preparation failed and durable rollback also failed: {exc}; "
                            f"rollback={rollback_exc}"
                        ) from exc
        raise

    finally:
        if owns_lock and not lock_released and not preserve_recovery:
            release_lock()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("VERSION_LIFECYCLE_STATUS=ERROR")
        print(f"ERROR={exc}")
        raise SystemExit(2)
