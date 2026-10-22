from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
CURRENT_PATH = ROOT / "build" / "package" / "release-state.json"
MANIFEST_PATH = ROOT / "provenance" / "application" / "CANONICAL-SOURCE-MANIFEST.json"
CHECK_PATH = ROOT / "build" / "package" / "check_state.py"
VERSION_PATH = ROOT / "build" / "package" / "version_control.py"
LOCK_PATH = ROOT / "_cache" / ".builder-operation.lock"
TX_PATH = ROOT / "_cache" / ".acceptance-promotion-transaction"
TX_CREATING_PREFIX = ".acceptance-promotion-transaction.creating-"
TX_CLEANUP_PREFIX = ".acceptance-promotion-transaction.cleanup-"
CONTROL_ID = "BUILDER_ACCEPTANCE_CONTROL_V1"
PRODUCT = "DaVinci Resolve AI Director"
INTEGRATION_PRODUCT = f"{PRODUCT} Integration"
INTEGRATION_SETUP_PREFIX = f"{INTEGRATION_PRODUCT} Setup"
INTEGRATION_FILE_DESCRIPTION = "AI Director Workflow Integration Launcher"
ARTIFACT_NAMING_CONTRACT = "WINDOWS_PUBLIC_ARTIFACT_NAMES_V1"
MAIN_UNINSTALL_KEY = "91a8322d-d867-520c-abe1-ef1b53905692"
MAIN_INSTALL_METADATA_PATH = rf"Software\{MAIN_UNINSTALL_KEY}"
MAIN_UNINSTALL_PATH = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{MAIN_UNINSTALL_KEY}"
RESOLVE_UNINSTALL_KEY = "DaVinciResolveAIDirectorResolveIntegration"
RESOLVE_UNINSTALL_PATH = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{RESOLVE_UNINSTALL_KEY}"


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


def atomic_write(path: Path, data: bytes, suffix: str = ".acceptance.tmp") -> None:
    temp = path.with_name(path.name + suffix)
    require(not temp.exists(), f"Acceptance temp residue exists: {temp}")
    try:
        with temp.open("wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def semantic_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", str(value or ""))
    require(match is not None, f"Invalid semantic version: {value!r}")
    return tuple(int(x) for x in match.groups())


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


def remove_tree_verified(path: Path, label: str) -> None:
    if path.exists():
        shutil.rmtree(path)
    require(not path.exists(), f"{label} cleanup failed: {path}")


def run(args, *, env=None, timeout=180) -> tuple[int, str]:
    cp = subprocess.run(
        [str(x) for x in args],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=False,
        check=False,
        timeout=timeout,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    output = (cp.stdout or b"").decode("utf-8", errors="replace")
    return cp.returncode, output


def read_lock() -> dict | None:
    if not LOCK_PATH.exists():
        return None
    require(LOCK_PATH.is_dir(), f"Builder operation lock is not a directory: {LOCK_PATH}")
    meta_path = LOCK_PATH / "operation.json"
    require(meta_path.is_file(), f"Builder operation lock metadata missing: {meta_path}")
    return read_json(meta_path)


def validate_inherited_accept_lock(target: str) -> dict:
    require(os.environ.get("AI_DIRECTOR_INHERITED_OPERATION_LOCK") == "1", "Inherited acceptance lock flag missing")
    operation = str(os.environ.get("AI_DIRECTOR_EXPECT_OPERATION") or "")
    owner_pid = str(os.environ.get("AI_DIRECTOR_EXPECT_OPERATION_PID") or "")
    expected_target = str(os.environ.get("AI_DIRECTOR_EXPECT_TARGET_VERSION") or "")
    require(operation == "ACCEPT", "Inherited Builder operation must be ACCEPT")
    require(owner_pid, "Inherited acceptance lock owner PID missing")
    require(expected_target == target, "Inherited acceptance target mismatch")
    meta = read_lock()
    require(meta is not None, "Inherited acceptance Builder lock missing")
    require(meta.get("operation") == "ACCEPT", "Acceptance Builder lock operation mismatch")
    require(str(meta.get("pid")) == owner_pid, "Acceptance Builder lock owner PID mismatch")
    require(str(meta.get("target_version") or "") == target, "Acceptance Builder lock target mismatch")
    return meta


def remove_stale_accept_lock(owner_operation: str, owner_pid: int) -> None:
    meta = read_lock()
    if meta is None:
        return
    require(meta.get("operation") == owner_operation, "Stale Builder lock operation does not match acceptance transaction owner")
    require(int(meta.get("pid")) == owner_pid, "Stale Builder lock PID does not match acceptance transaction owner")
    require(owner_operation == "ACCEPT", "Acceptance recovery will not remove a non-ACCEPT Builder lock")
    require(not process_exists(owner_pid), "Refusing to remove an ACCEPT lock whose owner is still alive")
    remove_tree_verified(LOCK_PATH, "Stale acceptance Builder lock")


def tx_metadata() -> dict:
    meta_path = TX_PATH / "transaction.json"
    require(meta_path.is_file(), f"Acceptance transaction metadata missing: {meta_path}")
    meta = read_json(meta_path)
    require(meta.get("schema_version") == 1, "Acceptance transaction schema mismatch")
    require(meta.get("transaction_type") == "ACCEPTANCE_PROMOTION", "Acceptance transaction type mismatch")
    owner = meta.get("owner") or {}
    require(owner.get("operation") == "ACCEPT", "Acceptance transaction owner operation mismatch")
    require(int(owner.get("pid") or 0) > 0, "Acceptance transaction owner PID invalid")
    return meta


def transaction_rows(meta: dict) -> list[dict]:
    rows = meta.get("files")
    require(isinstance(rows, list) and len(rows) == 2, "Acceptance transaction file set mismatch")
    labels = {str(row.get("label") or "") for row in rows}
    require(labels == {"CURRENT.json", "CANONICAL-SOURCE-MANIFEST.json"}, "Acceptance transaction labels mismatch")
    return rows


def restore_transaction_originals(meta: dict) -> None:
    for row in transaction_rows(meta):
        path = Path(str(row.get("path") or ""))
        backup_name = str(row.get("backup_name") or "")
        require(path in {CURRENT_PATH, MANIFEST_PATH}, f"Unsafe acceptance rollback path: {path}")
        backup = TX_PATH / "originals" / backup_name
        require(backup.is_file(), f"Acceptance rollback backup missing: {backup}")
        data = backup.read_bytes()
        require(sha256_bytes(data) == str(row.get("before_sha256") or "").upper(), f"Acceptance rollback backup changed: {backup_name}")
        atomic_write(path, data, suffix=".acceptance-rollback.tmp")
    for row in transaction_rows(meta):
        path = Path(str(row["path"]))
        require(sha256(path) == str(row["before_sha256"]).upper(), f"Acceptance rollback hash mismatch: {path}")


def remove_transaction_journal() -> None:
    if not TX_PATH.exists():
        cleanup_cache_root_if_empty()
        return
    cache_root = ROOT / "_cache"
    cleanup = cache_root / f"{TX_CLEANUP_PREFIX}{os.getpid()}"
    require(not cleanup.exists(), f"Acceptance transaction cleanup path exists: {cleanup}")
    os.replace(TX_PATH, cleanup)
    require(not TX_PATH.exists(), "Acceptance transaction journal rename did not complete")
    remove_tree_verified(cleanup, "Acceptance transaction cleanup")
    cleanup_cache_root_if_empty()


def cleanup_abandoned_creating_and_cleanup() -> None:
    cache_root = ROOT / "_cache"
    if not cache_root.is_dir():
        return
    creating = sorted(p for p in cache_root.iterdir() if p.is_dir() and p.name.startswith(TX_CREATING_PREFIX))
    cleanup = sorted(p for p in cache_root.iterdir() if p.is_dir() and p.name.startswith(TX_CLEANUP_PREFIX))
    if not creating and not cleanup:
        return
    lock = read_lock()
    if lock is not None:
        operation = str(lock.get("operation") or "")
        pid = int(lock.get("pid") or 0)
        require(operation == "ACCEPT", "Acceptance transaction residue is paired with a non-ACCEPT Builder lock")
        require(not process_exists(pid), "Acceptance transaction residue is paired with a live ACCEPT operation")
        remove_tree_verified(LOCK_PATH, "Stale acceptance Builder lock")
    for path in creating:
        remove_tree_verified(path, "Acceptance transaction creating residue")
        print(f"ACCEPTANCE_TRANSACTION_CREATING_RESIDUE_REMOVED={path.name}")
    for path in cleanup:
        remove_tree_verified(path, "Acceptance transaction cleanup residue")
        print(f"ACCEPTANCE_TRANSACTION_CLEANUP_RESIDUE_REMOVED={path.name}")
    cleanup_cache_root_if_empty()


def recover_pending_acceptance_transaction() -> str:
    cleanup_abandoned_creating_and_cleanup()
    if not TX_PATH.exists():
        lock = read_lock()
        if lock is not None and str(lock.get("operation") or "") == "ACCEPT":
            pid = int(lock.get("pid") or 0)
            require(not process_exists(pid), "Refusing to remove an ACCEPT lock whose owner is still alive")
            remove_tree_verified(LOCK_PATH, "Stale acceptance Builder lock")
            cleanup_cache_root_if_empty()
            print("STALE_ACCEPT_LOCK_REMOVED=True")
            return "STALE_LOCK_REMOVED"
        return "NOT_REQUIRED"

    meta = tx_metadata()
    owner = meta["owner"]
    owner_operation = str(owner["operation"])
    owner_pid = int(owner["pid"])
    require(not process_exists(owner_pid), "Refusing to recover an acceptance transaction whose owner is still alive")

    rows = transaction_rows(meta)
    states = {}
    for row in rows:
        path = Path(str(row["path"]))
        actual = sha256(path) if path.is_file() else "MISSING"
        before = str(row["before_sha256"]).upper()
        after = str(row["after_sha256"]).upper()
        states[str(row["label"])] = "ORIGINAL" if actual == before else "PROSPECTIVE" if actual == after else "UNEXPECTED"
    print("ACCEPTANCE_TRANSACTION_LIVE_STATE=" + ",".join(f"{k}:{states[k]}" for k in sorted(states)))
    require(all(v != "UNEXPECTED" for v in states.values()), f"Acceptance transaction has unexpected live-file identity; recovery preserved: {states}")

    promotion_dir = Path(str(meta.get("promotion_dir") or ""))
    promotion_record = Path(str(meta.get("promotion_record") or ""))
    expected_record_sha = str(meta.get("promotion_record_sha256") or "").upper()
    committed_record = bool(expected_record_sha and promotion_record.is_file() and sha256(promotion_record) == expected_record_sha)

    if set(states.values()) == {"PROSPECTIVE"} and committed_record:
        print("ACCEPTANCE_TRANSACTION_RECOVERY_ACTION=FINALIZE_COMMITTED_PROMOTION")
        remove_transaction_journal()
        remove_stale_accept_lock(owner_operation, owner_pid)
        cleanup_cache_root_if_empty()
        return "FINALIZED_COMMITTED_PROMOTION"

    print("ACCEPTANCE_TRANSACTION_RECOVERY_ACTION=ROLLBACK")
    restore_transaction_originals(meta)
    staging = Path(str(meta.get("promotion_staging") or ""))
    if staging and str(staging) != ".":
        remove_tree_verified(staging, "Acceptance promotion staging")
    if promotion_dir and str(promotion_dir) != "." and promotion_dir.exists():
        remove_tree_verified(promotion_dir, "Uncommitted acceptance promotion evidence")
    remove_transaction_journal()
    remove_stale_accept_lock(owner_operation, owner_pid)
    cleanup_cache_root_if_empty()
    return "ROLLED_BACK"


def validate_builder_state() -> tuple[dict, dict, str, str]:
    require(CURRENT_PATH.is_file(), f"CURRENT missing: {CURRENT_PATH}")
    current = read_json(CURRENT_PATH)
    require(current.get("schema_version") == 5, "CURRENT schema mismatch")
    require(current.get("product") == PRODUCT, "CURRENT product mismatch")
    require(current.get("state_mode") == "TARGET_READY", "Acceptance requires Builder TARGET_READY")
    accepted = str(current.get("live_accepted_authority") or "")
    target = str(current.get("target_version") or "")
    require(semantic_version(target) > semantic_version(accepted), "Acceptance target must be greater than live accepted authority")
    require(str(current.get("stable_version") or "") == accepted, "CURRENT stable_version must equal live accepted authority before promotion")
    lifecycle = current.get("version_lifecycle") or {}
    require(lifecycle.get("acceptance_promotion") == "SEPARATE_EXPLICIT_GATE", "Acceptance promotion policy mismatch")
    require(lifecycle.get("acceptance_controller") == CONTROL_ID, "CURRENT acceptance controller binding mismatch")
    require(lifecycle.get("acceptance_requires_live_attestation") is True, "CURRENT acceptance attestation policy mismatch")
    require(current.get("acceptance_entrypoint") == "BUILD.cmd --accept", "CURRENT acceptance entrypoint mismatch")

    bindings = current.get("control_bindings") or {}
    required_controls = {
        "acceptance_control.py": Path(__file__).resolve(),
        "authoritative_build.py": ROOT / "build" / "package" / "authoritative_build.py",
        "build_installer.py": ROOT / "installer" / "build_installer.py",
        "check_state.py": ROOT / "build" / "package" / "check_state.py",
        "version_control.py": ROOT / "build" / "package" / "version_control.py",
        "BUILD.cmd": ROOT / "BUILD.cmd",
        "CHECK-STATE.cmd": ROOT / "CHECK-STATE.cmd",
        "VERSION.cmd": ROOT / "VERSION.cmd",
    }
    for rel, path in required_controls.items():
        require(path.is_file(), f"Required acceptance control missing: {rel}")
        require(str(bindings.get(rel) or "").upper() == sha256(path), f"CURRENT control binding mismatch: {rel}")
    require(current.get("build_controller_sha256") == sha256(ROOT / "build" / "package" / "authoritative_build.py"), "Build controller binding mismatch")
    require(current.get("builder_control_sha256") == sha256(ROOT / "installer" / "build_installer.py"), "Builder core binding mismatch")

    canonical = current.get("canonical_application") or {}
    require(MANIFEST_PATH.is_file(), "Canonical manifest missing")
    require(sha256(MANIFEST_PATH) == str(canonical.get("manifest_sha256") or "").upper(), "Canonical manifest binding mismatch")
    manifest = read_json(MANIFEST_PATH)
    require(manifest.get("id") == f"AI-Director-Canonical-Application-{target}-v1", "Canonical manifest id mismatch")
    require(manifest.get("version") == target, "Canonical manifest version mismatch")
    require(manifest.get("source_phase") == "TARGET_READY", "Canonical manifest is not TARGET_READY")
    return current, manifest, accepted, target


def select_candidate(current: dict, target: str, requested: str | None) -> tuple[Path, str, int]:
    policy = current.get("build_output_policy") or {}
    require(policy.get("mode") == "BUILDER_PARENT_RELATIVE_SEQUENTIAL", "Build-output policy mismatch")
    rel_root = Path(str(policy.get("relative_root") or ""))
    prefix = str(policy.get("attempt_prefix") or "")
    require(prefix == "static-build-", "Release-candidate prefix mismatch")
    require(not rel_root.is_absolute() and ".." not in rel_root.parts, "Unsafe release-candidate root")
    series_root = ROOT.parent / rel_root / target
    require(series_root.is_dir(), f"Release-candidate series missing: {series_root}")

    candidates = []
    for path in series_root.iterdir():
        if not path.is_dir() or not path.name.startswith(prefix):
            continue
        suffix = path.name[len(prefix):]
        if suffix.isdigit():
            candidates.append((int(suffix), path))
    candidates.sort()
    require(candidates, f"No completed release candidates found for {target}")

    if requested:
        match = re.fullmatch(r"static-build-(\d+)", requested)
        require(match is not None, f"Invalid candidate name: {requested!r}")
        selected = [(idx, path) for idx, path in candidates if path.name == requested]
        require(len(selected) == 1, f"Requested candidate not found: {requested}")
        index, path = selected[0]
    else:
        require(
            len(candidates) == 1,
            "Multiple completed release candidates exist; rerun with --candidate static-build-NNN to select exactly one",
        )
        index, path = candidates[0]
    return path, path.name, index


def validate_candidate(current: dict, manifest: dict, accepted: str, target: str, candidate_root: Path, candidate: str, sequence: int) -> dict:
    artifacts = candidate_root / "artifacts"
    reports = candidate_root / "reports"
    report_path = reports / f"STATIC-BUILD-REPORT-{target}.json"
    expected_setup_name = f"{PRODUCT} Setup {target}.exe"
    expected_resolve_setup_name = f"{INTEGRATION_SETUP_PREFIX} {target}.exe"
    setup = artifacts / expected_setup_name
    resolve_setup = artifacts / expected_resolve_setup_name
    for path in (artifacts, reports):
        require(path.is_dir(), f"Candidate directory missing: {path}")
    for path in (report_path, setup, resolve_setup):
        require(path.is_file(), f"Candidate evidence missing: {path}")
    acceptance_dirs = [p for p in candidate_root.iterdir() if p.is_dir() and "Acceptance-Promotion" in p.name]
    require(not acceptance_dirs, f"Candidate already contains acceptance-promotion evidence: {[p.name for p in acceptance_dirs]}")

    report = read_json(report_path)
    require(report.get("schema_version") == 1, "Static build report schema mismatch")
    require(report.get("status") == "PASS_STATIC_RELEASE_CANDIDATE_BUILD", "Static build report did not pass")
    require(report.get("target_version") == target, "Static build report target mismatch")
    require(report.get("release_candidate_attempt") == candidate, "Static build report candidate mismatch")
    require(int(report.get("release_candidate_sequence") or -1) == sequence, "Static build report sequence mismatch")
    require(report.get("live_accepted_authority") == accepted, "Static build report predecessor mismatch")
    require(report.get("live_accepted") is False, "Static build report must remain candidate-time evidence")
    require(report.get("installation_performed") is False and report.get("setup_executed") is False, "Static build report unexpectedly records installation")
    require(report.get("builder_source_mutated_by_build") is False, "Static build report records Builder mutation")
    require(report.get("build_output_bound_to_current") is False, "Static build report was bound into CURRENT")
    require(report.get("artifact_naming_contract") == ARTIFACT_NAMING_CONTRACT, "Static build report artifact naming contract mismatch")
    require(str((report.get("installer") or {}).get("artifact_name") or "") == expected_setup_name, "Static build report main Setup artifact name mismatch")
    require(str((report.get("resolve_integration") or {}).get("artifact_name") or "") == expected_resolve_setup_name, "Static build report Integration Setup artifact name mismatch")
    require(str(report.get("builder_core_sha256") or "").upper() == sha256(ROOT / "installer" / "build_installer.py"), "Static build report Builder core binding mismatch")
    require(str(report.get("build_controller_sha256") or "").upper() == sha256(ROOT / "build" / "package" / "authoritative_build.py"), "Static build report controller binding mismatch")
    require(str(report.get("canonical_source_manifest_sha256") or "").upper() == sha256(MANIFEST_PATH), "Static build report canonical manifest binding mismatch")
    app = report.get("application") or {}
    require(app.get("source_authority") == "CANONICAL", "Static build report application authority mismatch")
    require(app.get("final_asar_source_parity") is True, "Static build report final ASAR/source parity did not pass")
    require(str((report.get("installer") or {}).get("sha256") or "").upper() == sha256(setup), "Candidate main Setup hash mismatch")
    require(str((report.get("resolve_integration") or {}).get("installer_sha256") or "").upper() == sha256(resolve_setup), "Candidate Integration Setup hash mismatch")
    main_meta = (report.get("installer") or {}).get("pe_metadata") or {}
    child_meta = ((report.get("resolve_integration") or {}).get("static_audit") or {}).get("pe_metadata") or {}
    require(main_meta.get("product_name") == PRODUCT and main_meta.get("file_description") == PRODUCT, "Main Setup PE naming metadata mismatch")
    require(child_meta.get("product_name") == INTEGRATION_PRODUCT, "Integration Setup PE ProductName mismatch")
    require(child_meta.get("file_description") == INTEGRATION_FILE_DESCRIPTION, "Integration Setup PE FileDescription mismatch")

    runtime_stack = report.get("runtime_stack") or {}
    require(runtime_stack.get("construction_mode") == "SOURCE_BUILT_DIRECT_AND_UPSTREAM",
            "Static build report runtime-stack construction mode mismatch")
    require(runtime_stack.get("accepted_archive_consumed") is False,
            "Static build report unexpectedly consumed the accepted runtime-stack archive")
    direct_report_path = reports / f"DIRECT-SOURCE-BUILD-REPORT-{target}.json"
    require(direct_report_path.is_file(), f"Candidate Direct source-build report missing: {direct_report_path}")
    direct_report_sha = sha256(direct_report_path)
    require(str(runtime_stack.get("direct_build_report_sha256") or "").upper() == direct_report_sha,
            "Static build report Direct source-build report binding mismatch")
    direct_report = read_json(direct_report_path)
    require(direct_report.get("schema") == "ai-director-direct-source-build-result/v1",
            "Direct source-build report schema mismatch")
    require(direct_report.get("result") == "PASS", "Direct source-build report did not pass")
    direct_source = direct_report.get("source") or {}
    require(re.fullmatch(r"[0-9a-f]{40}", str(direct_source.get("head") or "")) is not None,
            "Direct source-build report source head is invalid")
    require(re.fullmatch(r"[0-9a-f]{40}", str(direct_source.get("tree") or "")) is not None,
            "Direct source-build report source tree is invalid")
    direct_rows = direct_report.get("shipping_files") or []
    require(len(direct_rows) == 17, "Direct source-build report shipping-file count mismatch")
    direct_names = [str(row.get("name") or "") for row in direct_rows]
    require(len(set(direct_names)) == 17 and all(direct_names),
            "Direct source-build report shipping-file names are missing or duplicated")
    for row in direct_rows:
        require(int(row.get("bytes") or -1) >= 0, f"Direct source-build report byte size invalid: {row.get('name')}")
        require(re.fullmatch(r"[0-9A-F]{64}", str(row.get("sha256") or "").upper()) is not None,
                f"Direct source-build report SHA256 invalid: {row.get('name')}")

    return {
        "root": candidate_root,
        "candidate": candidate,
        "sequence": sequence,
        "report": report,
        "report_path": report_path,
        "report_sha256": sha256(report_path),
        "direct_report": direct_report,
        "direct_report_path": direct_report_path,
        "direct_report_sha256": direct_report_sha,
        "setup": setup,
        "setup_sha256": sha256(setup),
        "resolve_setup": resolve_setup,
        "resolve_setup_sha256": sha256(resolve_setup),
    }


def registry_value(key, name):
    try:
        import winreg
        return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def norm_path(value: object) -> str:
    if value is None:
        return ""
    return os.path.normcase(os.path.normpath(str(value).strip().strip('"').rstrip("\\/")))


def validate_main_registration(target: str, install_root: Path) -> dict:
    try:
        import winreg
    except ImportError as exc:
        raise RuntimeError(f"winreg unavailable: {exc}") from exc
    access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MAIN_UNINSTALL_PATH, 0, access) as key:
        row = {
            "hive": "HKCU",
            "view": "64",
            "key": MAIN_UNINSTALL_KEY,
            "display_name": registry_value(key, "DisplayName"),
            "display_version": registry_value(key, "DisplayVersion"),
            "publisher": registry_value(key, "Publisher"),
            "uninstall_string": registry_value(key, "UninstallString"),
            "quiet_uninstall_string": registry_value(key, "QuietUninstallString"),
            "display_icon": registry_value(key, "DisplayIcon"),
        }
    require(row["display_name"] == f"{PRODUCT} {target}", f"Installed DisplayName mismatch: {row}")
    require(row["display_version"] == target, f"Installed DisplayVersion mismatch: {row}")
    require(row["publisher"] == PRODUCT, f"Installed Publisher mismatch: {row}")
    expected_uninstaller = install_root / f"Uninstall {PRODUCT}.exe"
    expected_prefix = f'"{expected_uninstaller}"'.casefold()
    uninstall = str(row.get("uninstall_string") or "")
    quiet = str(row.get("quiet_uninstall_string") or "")
    require(uninstall.casefold().startswith(expected_prefix) and "/currentuser" in uninstall.casefold(), f"Installed UninstallString mismatch: {row}")
    require(quiet.casefold().startswith(expected_prefix) and "/currentuser" in quiet.casefold() and "/s" in quiet.casefold().split(), f"Installed QuietUninstallString mismatch: {row}")
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, MAIN_INSTALL_METADATA_PATH, 0, access) as key:
        install_location = registry_value(key, "InstallLocation")
        shortcut_name = registry_value(key, "ShortcutName")
    require(norm_path(install_location) == norm_path(install_root), f"Installed InstallLocation mismatch: {install_location!r}")
    require(shortcut_name == PRODUCT, f"Installed ShortcutName mismatch: {shortcut_name!r}")
    row["install_location"] = install_location
    row["shortcut_name"] = shortcut_name
    return row


def validate_resolve_integration(target: str) -> dict:
    try:
        import winreg
    except ImportError as exc:
        raise RuntimeError(f"winreg unavailable: {exc}") from exc
    program_data = Path(os.environ.get("ProgramData", r"C:\ProgramData"))
    plugin_root = program_data / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "Workflow Integration Plugins" / "com.aidirector.davinciresolve"
    access = winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0)
    registration = None
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, RESOLVE_UNINSTALL_PATH, 0, access) as key:
            registration = {
                "hive": "HKLM",
                "view": "64",
                "key": RESOLVE_UNINSTALL_KEY,
                "display_name": registry_value(key, "DisplayName"),
                "display_version": registry_value(key, "DisplayVersion"),
                "publisher": registry_value(key, "Publisher"),
                "uninstall_string": registry_value(key, "UninstallString"),
            }
    except FileNotFoundError:
        registration = None

    if registration is None:
        require(not plugin_root.exists(), "Resolve Integration plugin exists without its HKLM uninstall registration")
        return {"installed": False, "plugin_root": str(plugin_root), "registration": None, "payload": {}}

    require(registration.get("publisher") == PRODUCT, f"Resolve Integration Publisher mismatch: {registration}")
    if str(registration.get("display_version") or "") == target:
        require(registration.get("display_name") == INTEGRATION_PRODUCT, f"Installed Integration DisplayName mismatch: {registration}")
        expected_uninstaller = plugin_root / f"Remove {INTEGRATION_PRODUCT}.exe"
        uninstall = str(registration.get("uninstall_string") or "")
        require(uninstall.casefold().startswith(f'"{expected_uninstaller}"'.casefold()), f"Installed Integration UninstallString mismatch: {registration}")
    # Resolve Integration is optional and an unchecked upgrade deliberately preserves
    # an existing accepted launcher. Its registration version therefore need not track
    # the standalone application target; payload identity is the authoritative check.
    require(plugin_root.is_dir(), f"Resolve Integration registration exists but plugin root is missing: {plugin_root}")

    descriptor = read_json(ROOT / "src" / "resolve-integration" / "RESOLVE-LAUNCHER-MANIFEST.json")
    payload = {}
    for row in descriptor.get("files") or []:
        rel = str(row.get("path") or "")
        require(rel.startswith("payload/"), f"Unexpected Resolve launcher payload path: {rel}")
        installed = plugin_root / rel[len("payload/"):]
        require(installed.is_file(), f"Installed Resolve Integration payload missing: {installed}")
        actual = sha256(installed)
        require(actual == str(row.get("sha256") or "").upper(), f"Installed Resolve Integration payload hash mismatch: {installed}")
        payload[installed.name] = actual
    return {"installed": True, "plugin_root": str(plugin_root), "registration": registration, "payload": payload}


def path_from_localappdata(relative: str) -> Path:
    raw_base = str(os.environ.get("LOCALAPPDATA") or "")
    require(raw_base, "LOCALAPPDATA is unavailable")
    base = Path(raw_base)
    rel = Path(str(relative).replace("/", os.sep))
    require(not rel.is_absolute() and ".." not in rel.parts, f"Unsafe installed-runtime path: {relative}")
    return base / rel


def server_version(server: Path, shared_cuda: Path) -> str:
    require(server.is_file(), f"Managed llama-server missing: {server}")
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(server.parent), str(shared_cuda), str(system_root / "System32"), str(system_root)])
    rc, output = run([server, "--version"], env=env, timeout=30)
    require(rc == 0, f"Managed llama-server --version failed: {server}: {output}")
    flat = " | ".join(line.strip() for line in output.splitlines() if line.strip())
    require(flat, f"Managed llama-server --version returned no identity: {server}")
    return flat


def validate_runtime(current: dict, candidate_info: dict) -> dict:
    stack_id = str((current.get("active_runtime_stack") or {}).get("id") or "")
    require(stack_id, "Active runtime stack id missing")
    manifest_path = ROOT / "provenance" / "runtime" / "runtime-stack" / "RUNTIME-STACK-MANIFEST.json"
    require(manifest_path.is_file(), f"Runtime stack source manifest missing: {manifest_path}")
    stack = read_json(manifest_path)
    require(stack.get("runtime_stack_id") == stack_id, "Runtime stack source-manifest identity mismatch")

    cuda_rel = str((stack.get("cuda") or {}).get("install_root") or "")
    direct_rel = str((stack.get("direct") or {}).get("install_root") or "")
    upstream_rel = str((stack.get("upstream") or {}).get("install_root") or "")
    shared_cuda = path_from_localappdata(cuda_rel)
    direct_root = path_from_localappdata(direct_rel)
    upstream_root = path_from_localappdata(upstream_rel)
    require(shared_cuda.is_dir(), f"Shared CUDA root missing: {shared_cuda}")
    require(direct_root.is_dir(), f"Direct runtime root missing: {direct_root}")
    require(upstream_root.is_dir(), f"Upstream runtime root missing: {upstream_root}")

    expected_targets = {str(row.get("target") or "").replace("\\", "/"): str(row.get("sha256") or "").upper() for row in (stack.get("payload_files") or [])}
    verified_fixed = {}
    for name in ("cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll"):
        path = shared_cuda / name
        target = f"{cuda_rel.rstrip('/')}/{name}"
        require(path.is_file(), f"Shared CUDA file missing: {path}")
        require(target in expected_targets, f"Shared CUDA target missing from runtime-stack source manifest: {target}")
        actual = sha256(path)
        require(actual == expected_targets[target], f"Installed shared CUDA hash mismatch: {path}")
        verified_fixed[target] = actual

    direct_report = candidate_info.get("direct_report") or {}
    direct_rows = direct_report.get("shipping_files") or []
    require(len(direct_rows) == 17, "Selected candidate Direct shipping-file count mismatch")
    expected_direct = {str(row.get("name") or ""): str(row.get("sha256") or "").upper() for row in direct_rows}
    require(len(expected_direct) == 17 and all(expected_direct),
            "Selected candidate Direct shipping-file names are missing or duplicated")
    installed_direct_names = {p.name for p in direct_root.iterdir() if p.is_file()}
    require(installed_direct_names == set(expected_direct),
            "Installed Direct payload file-set does not match selected candidate")
    verified_direct = {}
    for name, expected in sorted(expected_direct.items()):
        path = direct_root / name
        actual = sha256(path)
        require(actual == expected, f"Installed Direct payload hash mismatch: {path}")
        verified_direct[name] = actual

    direct_server = direct_root / "llama-server.exe"
    direct_target = f"{direct_rel.rstrip('/')}/llama-server.exe"
    require(direct_target in expected_targets, "Direct llama-server target missing from runtime-stack source manifest")
    verified_fixed[direct_target] = verified_direct["llama-server.exe"]

    upstream_marker = upstream_root / "UNSLOTH_PREBUILT_INFO.json"
    require(upstream_marker.is_file(), f"Upstream runtime marker missing: {upstream_marker}")
    marker = read_json(upstream_marker)
    require(marker.get("bundle_profile") == "cuda13-portable", "Upstream bundle profile mismatch")
    require(marker.get("runtime_line") == str(stack.get("runtime_line") or ""), "Upstream runtime line mismatch")
    require(str(marker.get("toolkit_line") or "") == str(stack.get("toolkit_line") or ""), "Upstream toolkit line mismatch")
    upstream_server = upstream_root / "llama-server.exe"

    return {
        "runtime_stack_id": stack_id,
        "runtime_line": stack.get("runtime_line"),
        "toolkit_line": stack.get("toolkit_line"),
        "toolkit_version": stack.get("toolkit_version"),
        "shared_cuda_root": str(shared_cuda),
        "fixed_payload_hashes": verified_fixed,
        "direct_root": str(direct_root),
        "direct_candidate_report": str(candidate_info.get("direct_report_path") or ""),
        "direct_candidate_report_sha256": str(candidate_info.get("direct_report_sha256") or ""),
        "direct_payload_hashes": verified_direct,
        "direct_runtime_identity": server_version(direct_server, shared_cuda),
        "upstream_root": str(upstream_root),
        "upstream_marker_sha256": sha256(upstream_marker),
        "upstream_marker_identity": {
            "upstream_tag": marker.get("upstream_tag"),
            "requested_source_ref": marker.get("requested_source_ref"),
            "source_commit": marker.get("source_commit"),
            "bundle_profile": marker.get("bundle_profile"),
            "runtime_line": marker.get("runtime_line"),
            "toolkit_line": marker.get("toolkit_line"),
        },
        "upstream_runtime_identity": server_version(upstream_server, shared_cuda),
    }


def validate_installed_candidate(candidate_info: dict, target: str, current: dict) -> dict:
    raw_local_app_data = str(os.environ.get("LOCALAPPDATA") or "")
    require(raw_local_app_data, "LOCALAPPDATA is unavailable")
    local_app_data = Path(raw_local_app_data)
    install_root = local_app_data / "Programs" / PRODUCT
    exe = install_root / f"{PRODUCT}.exe"
    asar = install_root / "resources" / "app.asar"
    require(exe.is_file(), f"Installed application executable missing: {exe}")
    require(asar.is_file(), f"Installed app.asar missing: {asar}")
    report_app = candidate_info["report"].get("application") or {}
    exe_sha = sha256(exe)
    asar_sha = sha256(asar)
    require(exe_sha == str(report_app.get("exe_sha256") or "").upper(), "Installed application EXE does not match selected candidate")
    require(asar_sha == str(report_app.get("asar_sha256") or "").upper(), "Installed app.asar does not match selected candidate")
    registration = validate_main_registration(target, install_root)
    resolve = validate_resolve_integration(target)
    runtime = validate_runtime(current, candidate_info)
    return {
        "install_root": str(install_root),
        "application_exe": str(exe),
        "application_exe_sha256": exe_sha,
        "application_asar": str(asar),
        "application_asar_sha256": asar_sha,
        "uninstall_registration": registration,
        "resolve_integration": resolve,
        "runtime": runtime,
    }


def prospective_state(current: dict, manifest: dict, target: str) -> tuple[bytes, bytes]:
    accepted_manifest = dict(manifest)
    accepted_manifest["source_phase"] = "ACCEPTED_READY"
    manifest_bytes = json_bytes(accepted_manifest)

    accepted_current = dict(current)
    accepted_current["state_mode"] = "ACCEPTED_READY"
    accepted_current["live_accepted_authority"] = target
    accepted_current["stable_version"] = target
    accepted_current["target_version"] = target
    canonical = dict(accepted_current.get("canonical_application") or {})
    canonical["manifest_sha256"] = sha256_bytes(manifest_bytes)
    accepted_current["canonical_application"] = canonical
    current_bytes = json_bytes(accepted_current)
    return current_bytes, manifest_bytes


def run_post_promotion_checks(target: str) -> tuple[str, str]:
    env = dict(os.environ)
    py = ROOT / "_toolchain" / "Python" / "3.11.9" / "python.exe"
    require(py.is_file(), f"Owned Python missing: {py}")
    rc, check_output = run([py, "-B", CHECK_PATH], env=env, timeout=300)
    if check_output:
        print(check_output.rstrip())
    require(rc == 0 and "CHECK_STATE_STATUS=PASS" in check_output, f"CHECK-STATE failed after acceptance: exit={rc}")
    require(f"LIVE_ACCEPTED_AUTHORITY={target}" in check_output, "CHECK-STATE accepted authority mismatch after acceptance")
    require(f"TARGET_VERSION={target}" in check_output, "CHECK-STATE target mismatch after acceptance")
    require("VERSION_STATE=ACCEPTED_READY" in check_output, "CHECK-STATE did not report ACCEPTED_READY")

    rc, status_output = run([py, "-B", VERSION_PATH, "status"], env=env, timeout=120)
    if status_output:
        print(status_output.rstrip())
    require(rc == 0 and "VERSION_STATUS=PASS" in status_output, f"VERSION status failed after acceptance: exit={rc}")
    require(f"LIVE_ACCEPTED_AUTHORITY={target}" in status_output, "VERSION status accepted authority mismatch after acceptance")
    require(f"PREPARED_TARGET_VERSION={target}" in status_output, "VERSION status target mismatch after acceptance")
    require("VERSION_STATE=ACCEPTED_READY" in status_output, "VERSION status did not report ACCEPTED_READY")
    return check_output, status_output


def create_transaction(current_bytes_after: bytes, manifest_bytes_after: bytes, current: dict, accepted: str, target: str, candidate_info: dict) -> dict:
    cache_root = ROOT / "_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    require(not TX_PATH.exists(), f"Acceptance transaction already exists: {TX_PATH}")
    token = uuid.uuid4().hex
    creating = cache_root / f"{TX_CREATING_PREFIX}{token}"
    require(not creating.exists(), f"Acceptance transaction creation residue exists: {creating}")
    creating.mkdir()
    try:
        originals = creating / "originals"
        originals.mkdir()
        specs = (
            ("CURRENT.json", CURRENT_PATH, "CURRENT.json", current_bytes_after),
            ("CANONICAL-SOURCE-MANIFEST.json", MANIFEST_PATH, "CANONICAL-SOURCE-MANIFEST.json", manifest_bytes_after),
        )
        rows = []
        for label, path, backup_name, after_bytes in specs:
            original = path.read_bytes()
            backup = originals / backup_name
            backup.write_bytes(original)
            require(backup.read_bytes() == original, f"Acceptance rollback backup verification failed: {backup}")
            rows.append({
                "label": label,
                "path": str(path),
                "backup_name": backup_name,
                "before_sha256": sha256_bytes(original),
                "after_sha256": sha256_bytes(after_bytes),
            })

        sequence = int(candidate_info["sequence"])
        promotion_dir = candidate_info["root"] / f"AI-Director-RC{sequence}-Acceptance-Promotion-v1"
        promotion_record = promotion_dir / f"ACCEPTANCE-PROMOTION-{target}.json"
        promotion_staging = promotion_dir.with_name("." + promotion_dir.name + f".staging-{token}")
        require(not promotion_dir.exists(), f"Acceptance promotion directory already exists: {promotion_dir}")
        require(not promotion_staging.exists(), f"Acceptance promotion staging already exists: {promotion_staging}")
        owner_pid = int(os.environ.get("AI_DIRECTOR_EXPECT_OPERATION_PID") or 0)
        meta = {
            "schema_version": 1,
            "transaction_type": "ACCEPTANCE_PROMOTION",
            "controller": CONTROL_ID,
            "owner": {"operation": "ACCEPT", "pid": owner_pid},
            "predecessor": accepted,
            "target_version": target,
            "candidate": candidate_info["candidate"],
            "candidate_sequence": sequence,
            "promotion_dir": str(promotion_dir),
            "promotion_record": str(promotion_record),
            "promotion_staging": str(promotion_staging),
            "promotion_record_sha256": None,
            "files": rows,
        }
        (creating / "transaction.json").write_bytes(json_bytes(meta))
        os.replace(creating, TX_PATH)
        require(TX_PATH.is_dir(), "Acceptance transaction commit did not complete")
        return meta
    finally:
        if creating.exists():
            remove_tree_verified(creating, "Acceptance transaction creating residue")


def update_transaction_meta(meta: dict) -> None:
    atomic_write(TX_PATH / "transaction.json", json_bytes(meta), suffix=".acceptance-tx.tmp")


def _visible_console_input(prompt: str) -> str:
    if os.name != "nt":
        return input(prompt)

    # The serialized Builder parent deliberately captures this process's stdout.
    # Spawn one dedicated console window for the operator attestation instead of
    # trying to tunnel terminal UI through that pipe.
    import base64
    import tempfile

    response_dir = ROOT / "_cache"
    response_dir.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    response_path = response_dir / f".acceptance-visible-input-{os.getpid()}-{token}.txt"
    require(not response_path.exists(), f"Acceptance response file already exists: {response_path}")

    prompt_b64 = base64.b64encode(prompt.encode("utf-8")).decode("ascii")
    path_b64 = base64.b64encode(str(response_path).encode("utf-8")).decode("ascii")
    ps_script = rf'''$ErrorActionPreference = "Stop"
$Host.UI.RawUI.WindowTitle = "AI Director Acceptance"
Clear-Host
$PromptText = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("{prompt_b64}"))
$ResponsePath = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String("{path_b64}"))
Write-Host $PromptText -NoNewline
$Value = Read-Host
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($ResponsePath, [string]$Value, $Utf8NoBom)
'''
    encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    require(powershell.is_file(), f"Windows PowerShell missing: {powershell}")

    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    cp = subprocess.run(
        [str(powershell), "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        cwd=str(ROOT),
        stdin=None,
        stdout=None,
        stderr=None,
        check=False,
        close_fds=True,
        creationflags=flags,
    )
    try:
        require(cp.returncode == 0, f"Visible acceptance console exited with code {cp.returncode}")
        require(response_path.is_file(), "Visible acceptance console did not commit an operator response")
        return response_path.read_text(encoding="utf-8-sig").rstrip("\r\n")
    finally:
        if response_path.exists():
            response_path.unlink()

def interactive_attestation(target: str, candidate: str) -> dict:
    require(sys.stdin is not None and sys.stdin.isatty(), "Acceptance requires an interactive terminal for live-test attestation")
    phrase = f"ACCEPT {target} {candidate}"
    scope = "I personally completed live testing appropriate to this exact installed candidate, including installation/upgrade and application/runtime smoke testing, and I accept it as the new engineering authority."
    print("LIVE_ACCEPTANCE_ATTESTATION_REQUIRED=True")
    print(f"ATTESTATION_SCOPE={scope}")
    print(f"TYPE_EXACTLY={phrase}")
    visible_prompt = (
        "\r\n=== AI DIRECTOR LIVE ACCEPTANCE ===\r\n"
        + scope
        + "\r\n\r\nTYPE EXACTLY:\r\n"
        + phrase
        + "\r\n\r\nAcceptance phrase: "
    )
    entered = _visible_console_input(visible_prompt).strip()
    require(entered == phrase, "Acceptance attestation phrase did not match; no promotion was performed")
    return {
        "status": "PASS_OPERATOR_ATTESTED",
        "method": "INTERACTIVE_EXACT_PHRASE_VISIBLE_CONSOLE",
        "attestation_scope": "INSTALL_OR_UPGRADE_PLUS_APPLICATION_RUNTIME_SMOKE_AND_CANDIDATE_APPROPRIATE_LIVE_TESTS",
        "attested_by": getpass.getuser(),
        "attested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def apply_acceptance(requested_candidate: str | None, dry_run: bool) -> int:
    current, manifest, accepted, target = validate_builder_state()
    validate_inherited_accept_lock(target)
    candidate_root, candidate, sequence = select_candidate(current, target, requested_candidate)
    candidate_info = validate_candidate(current, manifest, accepted, target, candidate_root, candidate, sequence)
    installed = validate_installed_candidate(candidate_info, target, current)
    current_after, manifest_after = prospective_state(current, manifest, target)

    print(f"ACCEPTANCE_CONTROLLER={CONTROL_ID}")
    print(f"LIVE_ACCEPTED_AUTHORITY_BEFORE={accepted}")
    print(f"TARGET_VERSION={target}")
    print(f"SELECTED_CANDIDATE={candidate}")
    print(f"CANDIDATE_REPORT_SHA256={candidate_info['report_sha256']}")
    print(f"INSTALLER_SHA256={candidate_info['setup_sha256']}")
    print(f"INSTALLED_EXE_SHA256={installed['application_exe_sha256']}")
    print(f"INSTALLED_ASAR_SHA256={installed['application_asar_sha256']}")
    print(f"RESOLVE_INTEGRATION_INSTALLED={installed['resolve_integration']['installed']}")
    print(f"UPSTREAM_RUNTIME_IDENTITY={installed['runtime']['upstream_runtime_identity']}")
    print(f"DIRECT_RUNTIME_IDENTITY={installed['runtime']['direct_runtime_identity']}")
    print(f"PROSPECTIVE_CURRENT_SHA256={sha256_bytes(current_after)}")
    print(f"PROSPECTIVE_MANIFEST_SHA256={sha256_bytes(manifest_after)}")
    print("MECHANICAL_ACCEPTANCE_PREFLIGHT=PASS")

    if dry_run:
        print("LIVE_ACCEPTANCE_ATTESTATION_REQUIRED=YES_ON_APPLY")
        print("BUILDER_MUTATED=False")
        print("ACCEPTANCE_DRY_RUN_STATUS=PASS")
        return 0

    attestation = interactive_attestation(target, candidate)
    meta = create_transaction(current_after, manifest_after, current, accepted, target, candidate_info)
    mutation_started = False
    try:
        mutation_started = True
        atomic_write(MANIFEST_PATH, manifest_after)
        atomic_write(CURRENT_PATH, current_after)
        require(sha256(MANIFEST_PATH) == sha256_bytes(manifest_after), "Accepted canonical manifest post-write mismatch")
        require(sha256(CURRENT_PATH) == sha256_bytes(current_after), "Accepted CURRENT post-write mismatch")

        run_post_promotion_checks(target)

        record = {
            "schema_version": 2,
            "record_type": "ACCEPTANCE_PROMOTION",
            "product": PRODUCT,
            "version": target,
            "candidate": candidate,
            "candidate_sequence": sequence,
            "promotion_timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": "PASS_ACCEPTANCE_PROMOTION",
            "controller": {
                "id": CONTROL_ID,
                "sha256": sha256(Path(__file__).resolve()),
                "entrypoint": "BUILD.cmd --accept",
            },
            "authority": {
                "before": accepted,
                "after": target,
                "current_state_after": "ACCEPTED_READY",
                "promotion_executed": True,
            },
            "lifecycle": {
                "policy": "ACCEPTED_AUTHORITY_DERIVED_V1",
                "build_advances_accepted_authority": False,
                "acceptance_promotion": "SEPARATE_EXPLICIT_GATE",
                "acceptance_controller": CONTROL_ID,
                "candidate_binding_location": "EXTERNAL_PROMOTION_EVIDENCE_NOT_CURRENT_JSON",
                "static_build_report_remains_candidate_time_evidence": True,
            },
            "candidate_evidence": {
                "root": str(candidate_root),
                "static_report": str(candidate_info["report_path"]),
                "static_report_sha256": candidate_info["report_sha256"],
                "direct_source_build_report": str(candidate_info["direct_report_path"]),
                "direct_source_build_report_sha256": candidate_info["direct_report_sha256"],
                "main_setup": str(candidate_info["setup"]),
                "main_setup_sha256": candidate_info["setup_sha256"],
                "resolve_integration_setup": str(candidate_info["resolve_setup"]),
                "resolve_integration_setup_sha256": candidate_info["resolve_setup_sha256"],
            },
            "installed_identity": installed,
            "live_acceptance_attestation": attestation,
            "builder_state": {
                "current_sha256_before": next(row["before_sha256"] for row in meta["files"] if row["label"] == "CURRENT.json"),
                "current_sha256_after": sha256_bytes(current_after),
                "canonical_manifest_sha256_before": next(row["before_sha256"] for row in meta["files"] if row["label"] == "CANONICAL-SOURCE-MANIFEST.json"),
                "canonical_manifest_sha256_after": sha256_bytes(manifest_after),
                "build_installer_sha256": sha256(ROOT / "installer" / "build_installer.py"),
                "authoritative_build_sha256": sha256(ROOT / "build" / "package" / "authoritative_build.py"),
                "acceptance_control_sha256": sha256(Path(__file__).resolve()),
                "check_state_sha256": sha256(ROOT / "build" / "package" / "check_state.py"),
                "version_control_sha256": sha256(ROOT / "build" / "package" / "version_control.py"),
            },
            "scope": {
                "build_executed": False,
                "setup_executed": False,
                "uninstall_executed": False,
                "installed_product_touched": False,
                "application_source_bytes_changed": False,
                "runtime_payload_changed": False,
                "resolve_payload_changed": False,
                "google_drive_mutated": False,
                "continuity_mutated": False,
            },
        }
        record_bytes = json_bytes(record)
        record_sha = sha256_bytes(record_bytes)
        meta["promotion_record_sha256"] = record_sha
        update_transaction_meta(meta)

        promotion_dir = Path(meta["promotion_dir"])
        promotion_record = Path(meta["promotion_record"])
        promotion_staging = Path(meta["promotion_staging"])
        promotion_staging.mkdir(parents=False, exist_ok=False)
        staged_record = promotion_staging / promotion_record.name
        staged_record.write_bytes(record_bytes)
        require(sha256(staged_record) == record_sha, "Staged acceptance promotion record hash mismatch")
        os.replace(promotion_staging, promotion_dir)
        require(promotion_record.is_file() and sha256(promotion_record) == record_sha, "Committed acceptance promotion record mismatch")

        remove_transaction_journal()

        print(f"PROMOTION_RECORD={promotion_record}|SHA256={record_sha}|BYTES={len(record_bytes)}")
        print(f"CURRENT_SHA256={sha256(CURRENT_PATH)}")
        print(f"CANONICAL_MANIFEST_SHA256={sha256(MANIFEST_PATH)}")
        print(f"LIVE_ACCEPTED_AUTHORITY={target}")
        print(f"TARGET_VERSION={target}")
        print("VERSION_STATE=ACCEPTED_READY")
        print("BUILD_EXECUTED=NO")
        print("SETUP_EXECUTED=NO")
        print("UNINSTALL_EXECUTED=NO")
        print("GOOGLE_DRIVE_MUTATION=NO")
        print("CONTINUITY_MUTATION=NO")
        print("ACCEPTANCE_PROMOTION_STATUS=PASS")
        return 0
    except BaseException as original_exc:
        rollback_error = None
        try:
            if TX_PATH.exists():
                rollback_meta = tx_metadata()
                if mutation_started:
                    restore_transaction_originals(rollback_meta)
                staging = Path(str(rollback_meta.get("promotion_staging") or ""))
                promotion_dir = Path(str(rollback_meta.get("promotion_dir") or ""))
                if staging and str(staging) != ".":
                    remove_tree_verified(staging, "Acceptance promotion staging")
                if promotion_dir and str(promotion_dir) != "." and promotion_dir.exists():
                    remove_tree_verified(promotion_dir, "Acceptance promotion directory")
                remove_transaction_journal()
            print("ACCEPTANCE_PROMOTION_ROLLBACK=PASS")
        except BaseException as exc:
            rollback_error = exc
            print("ACCEPTANCE_PROMOTION_ROLLBACK=FAILED")
            print(f"ROLLBACK_ERROR={exc}")
        if rollback_error is not None:
            raise RuntimeError(f"Acceptance promotion failed and rollback could not be proven: original={original_exc!r}; rollback={rollback_error!r}") from original_exc
        raise


def parse_args():
    p = argparse.ArgumentParser(description="AI Director Builder-owned acceptance promotion control.")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Run mechanical checks, obtain live-test attestation, and promote the selected candidate.")
    mode.add_argument("--dry-run", action="store_true", help="Run all mechanical acceptance checks without attestation or mutation.")
    mode.add_argument("--recover-if-needed", action="store_true", help="Recover or finalize an interrupted acceptance transaction, if any.")
    p.add_argument("--candidate", metavar="static-build-NNN", help="Select a completed release candidate when more than one exists.")
    args = p.parse_args()
    if args.recover_if_needed and args.candidate:
        p.error("--candidate cannot be combined with --recover-if-needed")
    return args


def main() -> int:
    args = parse_args()
    print("AI_DIRECTOR_ACCEPTANCE_CONTROL_V1")
    print(f"ROOT={ROOT}")
    print("BUILD_EXECUTED=False")
    print("SETUP_EXECUTED=False")
    print("UNINSTALL_EXECUTED=False")
    print("INSTALLED_PRODUCT_TOUCHED=False")

    if args.recover_if_needed:
        status = recover_pending_acceptance_transaction()
        print(f"ACCEPTANCE_TRANSACTION_RECOVERY_STATUS={status}")
        print("ACCEPTANCE_TRANSACTION_RECOVERY_GATE=PASS")
        return 0

    require(not TX_PATH.exists(), f"Acceptance transaction exists; run recovery first: {TX_PATH}")
    return apply_acceptance(args.candidate, args.dry_run)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("ACCEPTANCE_CONTROL_STATUS=ERROR")
        print(f"ERROR={exc}")
        raise SystemExit(2)
