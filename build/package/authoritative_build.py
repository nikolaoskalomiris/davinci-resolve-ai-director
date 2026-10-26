from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import traceback
import urllib.request
import zipfile
import sys
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
CORE_PATH = ROOT / "installer" / "build_installer.py"
CURRENT_PATH = ROOT / "build" / "package" / "release-state.json"
ACCEPTANCE_CONTROL_PATH = ROOT / "build" / "package" / "acceptance_control.py"
SYSTEM_TOOLCHAIN_VERIFY_PATH = ROOT / "build" / "system-toolchain" / "verify_system_toolchain.py"

def _load_build_context() -> dict:
    obj = json.loads(CURRENT_PATH.read_text(encoding="utf-8-sig"))
    canonical = obj.get("canonical_application") or {}
    runtime_base = obj.get("active_runtime_base") or {}
    runtime_stack = obj.get("active_runtime_stack") or {}
    return {
        "target_version": str(obj.get("target_version") or ""),
        "accepted_version": str(obj.get("live_accepted_authority") or ""),
        "canonical_manifest_sha256": str(canonical.get("manifest_sha256") or "").upper(),
        "runtime_base_id": str(runtime_base.get("id") or ""),
        "runtime_stack_id": str(runtime_stack.get("id") or ""),
    }

_BUILD_CONTEXT = _load_build_context()
TARGET_VERSION = _BUILD_CONTEXT["target_version"]
PREDECESSOR_VERSION = _BUILD_CONTEXT["accepted_version"]
RUNTIME_BASE_ID = _BUILD_CONTEXT["runtime_base_id"]
RUNTIME_STACK_ID = _BUILD_CONTEXT["runtime_stack_id"]
CANONICAL_MANIFEST_SHA256 = _BUILD_CONTEXT["canonical_manifest_sha256"]

SHARED_CUDA_REDIST = {
    "cudart_archive": {
        "path": "_inputs/Shared-CUDA/CUDA13.3.1/Archives/cuda_cudart-windows-x86_64-13.3.29-archive.zip",
        "bytes": 2589792,
        "sha256": "1FEB7DD266813FFE8DBC24E115183A5AC35A4795C8D34ACA0DF85AB616B64D9C",
        "members": {
            "cudart64_13.dll": {
                "archive_path": "cuda_cudart-windows-x86_64-13.3.29-archive/bin/x64/cudart64_13.dll",
                "bytes": 551024,
                "sha256": "B00CA6F53699120DA815BF3E06E2E4285FAE2F201235B883DCBB50EEC51E2A2A",
            },
        },
    },
    "cublas_archive": {
        "path": "_inputs/Shared-CUDA/CUDA13.3.1/Archives/libcublas-windows-x86_64-13.6.0.2-archive.zip",
        "bytes": 393706755,
        "sha256": "62E9FA30560C8F0A28E0CDCF9D6FC1FED347BCFAB8847239B9AE1FDC1D86408A",
        "members": {
            "cublas64_13.dll": {
                "archive_path": "libcublas-windows-x86_64-13.6.0.2-archive/bin/x64/cublas64_13.dll",
                "bytes": 52697712,
                "sha256": "8C6BAC24474AF29627EC96500025A5D410A1B7E8FFA00E1FE13B1781FC6B3DDC",
            },
            "cublasLt64_13.dll": {
                "archive_path": "libcublas-windows-x86_64-13.6.0.2-archive/bin/x64/cublasLt64_13.dll",
                "bytes": 463655536,
                "sha256": "E323ABD89E0F03C1DB91A09D7AEB1928DE08E1F86192CC713B335FEFE3E368A9",
            },
        },
    },
}

EXPECTED = {
    "node_version": "v24.18.0",
    "npm_version": "11.16.0",
    "electron_builder_version": "26.15.3",
    "electron_archive": "5475DC725D50C9CEE12C0D56E1FD093C3BAD75E9DFAFD9753FDDC3A085532A37",
    "electron_exe": "1048609FFA3A543291F71AD6CBD976858821F7A13FB50FF14F8DC2DD8A99C128",
    "sevenzip_archive": "BE071F15BD6DA2F78FE81C6DDEF2009B0C4D8A51F36B780CB806C7E6DF95E1B3",
    "nsis_archive": "9877DF902530F96357D13A7A31AE2B9DF67F48B11FFC9A1700A7C961574EC5FA",
    "nsis_resources_archive": "593A9A92EF958321293AC6A2EE61E64BF1BD543142A5BD6B3D310709CC924103",
    "canonical_makensis": "E277B7378931B74392015F5AD6B1D744DCD8A347BAA4480350A75EBEAB8D8E3D",
    "runtime_base_archive": "7AD5B820B68F8CC949B6FF656D7FC0977858E9CBFF41EC241EC5F913317AC46F",
    "runtime_stack_archive": "F3413EDF3D0BD76D5D5D80698261F55F766A905CAD2BEF2E26A67DEAF3548C44",
    "runtime_path_generator": "73404AF0C1CD248821D298107A4485D42FB1D8DD9FCABF78AB358703D26DC066",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()

def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

def require(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)

def semantic_version(value: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", str(value or ""))
    require(match is not None, f"Invalid semantic version: {value!r}")
    return tuple(int(x) for x in match.groups())

def acquire_operation_lock(operation: str, target_version: str) -> Path:
    lock = ROOT / "_cache" / ".builder-operation.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise RuntimeError(f"Builder operation lock already exists: {lock}") from exc
    metadata = {
        "schema_version": 1,
        "operation": operation,
        "target_version": target_version,
        "pid": os.getpid(),
    }
    try:
        (lock / "operation.json").write_text(
            json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as original_exc:
        try:
            if lock.exists():
                shutil.rmtree(lock)
            require(not lock.exists(), f"Builder operation lock cleanup failed: {lock}")
        except Exception as cleanup_exc:
            raise RuntimeError(
                f"Builder operation lock creation failed and cleanup could not be proven: "
                f"original={original_exc!r}; cleanup={cleanup_exc!r}"
            ) from original_exc
        raise
    return lock

def release_operation_lock(lock: Path) -> None:
    if lock.exists():
        shutil.rmtree(lock)
    require(not lock.exists(), f"Builder operation lock residue remains: {lock}")
    cache_root = ROOT / "_cache"
    try:
        if cache_root.is_dir() and not any(cache_root.iterdir()):
            cache_root.rmdir()
    except Exception:
        pass


def read_operation_lock(lock: Path) -> dict:
    require(lock.is_dir(), f"Builder operation lock missing: {lock}")
    meta_path = lock / "operation.json"
    require(meta_path.is_file(), f"Builder operation lock metadata missing: {meta_path}")
    return read_json(meta_path)


def validate_inherited_operation_lock(expected_target: str | None = None) -> Path:
    require(os.environ.get("AI_DIRECTOR_INHERITED_OPERATION_LOCK") == "1",
            "Inherited Builder operation lock flag missing")
    expected_operation = str(os.environ.get("AI_DIRECTOR_EXPECT_OPERATION") or "")
    expected_pid = str(os.environ.get("AI_DIRECTOR_EXPECT_OPERATION_PID") or "")
    require(expected_operation == "BUILD", "Inherited Builder operation must be BUILD")
    require(expected_pid, "Inherited Builder operation owner PID missing")
    lock = ROOT / "_cache" / ".builder-operation.lock"
    meta = read_operation_lock(lock)
    require(meta.get("operation") == expected_operation, "Inherited Builder operation lock operation mismatch")
    require(str(meta.get("pid")) == expected_pid, "Inherited Builder operation lock owner PID mismatch")
    if expected_target is not None:
        require(str(meta.get("target_version") or "") == expected_target,
                "Inherited Builder operation lock target mismatch")
    return lock


def update_operation_lock_target(lock: Path, target_version: str) -> None:
    meta = read_operation_lock(lock)
    require(meta.get("operation") == "BUILD", "Builder operation lock operation changed during handoff")
    require(str(meta.get("pid")) == str(os.getpid()), "Builder operation lock owner changed during handoff")
    meta["target_version"] = target_version
    meta_path = lock / "operation.json"
    temp_path = lock / f"operation.json.{os.getpid()}.tmp"
    try:
        temp_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
        os.replace(temp_path, meta_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def inherited_operation_env(target_version: str | None = None, operation: str = "BUILD") -> dict:
    require(operation in ("BUILD", "ACCEPT"), f"Unsupported inherited Builder operation: {operation}")
    env = os.environ.copy()
    env["AI_DIRECTOR_INHERITED_OPERATION_LOCK"] = "1"
    env["AI_DIRECTOR_EXPECT_OPERATION"] = operation
    env["AI_DIRECTOR_EXPECT_OPERATION_PID"] = str(os.getpid())
    if target_version is not None:
        env["AI_DIRECTOR_EXPECT_TARGET_VERSION"] = target_version
    else:
        env.pop("AI_DIRECTOR_EXPECT_TARGET_VERSION", None)
    return env


def owned_python() -> Path:
    py = ROOT / "_toolchain" / "Python" / "3.11.9" / "python.exe"
    require(py.is_file(), f"Owned Python missing: {py}")
    return py


def _run_streamed(cmd, *, cwd=None, env=None, log=None):
    command = [str(x) for x in cmd]
    log_handle = None
    output_parts: list[str] = []
    try:
        if log is not None:
            log_path = Path(log)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_handle = log_path.open("w", encoding="utf-8", newline="\n")
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
        )
        assert process.stdout is not None
        for line in process.stdout:
            output_parts.append(line)
            print(line, end="", flush=True)
            if log_handle is not None:
                log_handle.write(line)
                log_handle.flush()
        returncode = process.wait()
    finally:
        if log_handle is not None:
            log_handle.close()
    return returncode, "".join(output_parts)


def run_control_child(cmd: list[Path | str], env: dict) -> str:
    returncode, output = _run_streamed(cmd, cwd=ROOT, env=env)
    require(returncode == 0, f"Child control process failed exit={returncode}: {' '.join(str(x) for x in cmd)}")
    return output



def recover_acceptance_if_needed() -> None:
    py = owned_python()
    require(ACCEPTANCE_CONTROL_PATH.is_file(), f"Acceptance control missing: {ACCEPTANCE_CONTROL_PATH}")
    env = os.environ.copy()
    output = run_control_child(
        [py, "-B", ACCEPTANCE_CONTROL_PATH, "--recover-if-needed"],
        env,
    )
    require(
        "ACCEPTANCE_TRANSACTION_RECOVERY_GATE=PASS" in output,
        "Acceptance transaction recovery preflight did not report PASS",
    )


def recover_version_preparation_if_needed() -> None:
    py = owned_python()
    env = os.environ.copy()
    output = run_control_child(
        [py, "-B", ROOT / "build" / "package" / "version_control.py", "--recover-if-needed"],
        env,
    )
    require(
        "VERSION_TRANSACTION_RECOVERY_GATE=PASS" in output,
        "Version transaction recovery preflight did not report PASS",
    )


def require_accept_dry_run_recovery_absent() -> None:
    cache_root = ROOT / "_cache"
    pending = []
    version_tx = cache_root / ".version-preparation-transaction"
    acceptance_tx = cache_root / ".acceptance-promotion-transaction"
    for path in (version_tx, acceptance_tx):
        if path.exists():
            pending.append(path.name)
    if cache_root.is_dir():
        for path in cache_root.iterdir():
            if not path.is_dir():
                continue
            name = path.name
            if (
                name.startswith(".version-preparation-transaction.creating-")
                or name.startswith(".version-preparation-transaction.cleanup-")
                or name.startswith(".acceptance-promotion-transaction.creating-")
                or name.startswith(".acceptance-promotion-transaction.cleanup-")
            ):
                pending.append(name)
    require(
        not pending,
        "BUILD --accept --dry-run refuses pending recovery state: "
        + ", ".join(sorted(pending))
        + ". Run the explicit recovery control before retrying the dry-run.",
    )


def parse_selected_target(output: str) -> str:
    values = [line.split("=", 1)[1].strip() for line in output.splitlines() if line.startswith("SELECTED_TARGET=")]
    require(len(values) == 1 and values[0], "Version control did not emit exactly one SELECTED_TARGET")
    return values[0]

def assert_hash(label: str, path: Path, expected: str):
    require(path.is_file(), f"{label} missing: {path}")
    actual = sha256(path)
    require(actual == str(expected).upper(), f"{label} hash mismatch Expected={expected} Actual={actual} Path={path}")
    return actual

def _rmtree_onerror(func, path, _exc_info):
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    func(path)


def remove_tree_strict(path: Path, label: str, attempts: int = 8) -> None:
    last_exc = None
    for attempt in range(attempts):
        if not path.exists():
            return
        try:
            shutil.rmtree(path, onerror=_rmtree_onerror)
            if not path.exists():
                return
        except OSError as exc:
            last_exc = exc
        time.sleep(0.15 * (attempt + 1))
    raise RuntimeError(f"{label} cleanup failed after {attempts} attempts: {path}: {last_exc!r}")

def run(cmd, *, cwd=None, env=None, log=None, ok=(0,)):
    returncode, output = _run_streamed(cmd, cwd=cwd, env=env, log=log)
    if returncode not in ok:
        raise RuntimeError(
            f"Command failed exit={returncode}: {' '.join(str(x) for x in cmd)}\n" + output[-8000:]
        )
    class Result:
        pass
    result = Result()
    result.returncode = returncode
    result.stdout = output
    return result

def load_core():
    spec = importlib.util.spec_from_file_location("aidirector_builder_core", CORE_PATH)
    require(spec is not None and spec.loader is not None, f"Unable to load builder core: {CORE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def validate_current_prebuild(current: dict, controller_sha: str, *, public_checked_out_build: bool = False):
    require(current.get("schema_version") == 5, "CURRENT schema must be 5")
    require(current.get("product") == "DaVinci Resolve AI Director", "CURRENT product mismatch")
    require(current.get("build_controller_mode") == "STATIC_RELEASE_CANDIDATE_EXTERNAL_OUTPUT", "CURRENT build-controller mode mismatch")

    versioning = current.get("version_lifecycle") or {}
    require(versioning.get("policy") == "ACCEPTED_AUTHORITY_DERIVED_V1", "CURRENT version-lifecycle policy mismatch")
    require(versioning.get("build_advances_accepted_authority") is False, "BUILD must not advance accepted authority")
    require(versioning.get("failed_build_consumes_version") is False, "Failed builds must not consume versions")
    require(versioning.get("acceptance_promotion") == "SEPARATE_EXPLICIT_GATE", "Acceptance promotion policy mismatch")

    policy = current.get("build_output_policy") or {}
    require(policy.get("mode") == "BUILDER_PARENT_RELATIVE_SEQUENTIAL", "CURRENT build-output policy mode mismatch")
    require(policy.get("relative_root") == "AI-Director-Release-Candidates", "CURRENT build-output relative root mismatch")
    require(policy.get("attempt_prefix") == "static-build-", "CURRENT build-output attempt prefix mismatch")
    rel_root = Path(str(policy.get("relative_root") or ""))
    require(not rel_root.is_absolute() and ".." not in rel_root.parts, "CURRENT build-output relative root is unsafe")

    require("release_candidate_output_root" not in current, "Absolute release-candidate output binding must not exist")
    require("final_stable_builder_target" not in current, "Machine-specific stable promotion target must not exist")
    require("last_build_status" not in current, "Build-result/status bookkeeping must not be bound into CURRENT")
    require("build_authorized" not in current, "Obsolete build_authorized field remains")

    accepted = semantic_version(str(current.get("live_accepted_authority") or ""))
    stable = semantic_version(str(current.get("stable_version") or ""))
    target = semantic_version(str(current.get("target_version") or ""))
    require(stable == accepted, "CURRENT stable_version must equal live accepted authority")
    if public_checked_out_build:
        require(current.get("state_mode") == "ACCEPTED_READY", "Plain public build requires ACCEPTED_READY checked-out release state")
        require(target == accepted, "Plain public checked-out build requires target == accepted authority")
    else:
        require(current.get("state_mode") == "TARGET_READY", "Maintainer build requires TARGET_READY state")
        require(target > accepted, "Prepared target must be greater than live accepted authority")
    require(str(current.get("target_version")) == TARGET_VERSION, "Build context target drift")
    require(str(current.get("live_accepted_authority")) == PREDECESSOR_VERSION, "Build context accepted-authority drift")

    require(current.get("builder_mode") == "CANONICAL_SOURCE_BUILDER", "CURRENT builder_mode mismatch")
    require(current.get("application_source_authority") == "CANONICAL", "Application source authority is not canonical")
    require(current.get("builder_control_sha256") == sha256(CORE_PATH), "CURRENT builder core binding mismatch")
    require(current.get("build_controller_sha256") == controller_sha, "CURRENT build controller binding mismatch")

    for forbidden in ("ordered_overlays", "runtime_stack_application_targets", "immutable_base", "accepted_reference", "baseline_contract", "baseline_verification"):
        require(forbidden not in current, f"Obsolete layered/history field remains in CURRENT: {forbidden}")

    canonical = current.get("canonical_application") or {}
    require(canonical.get("id") == f"AI-Director-Canonical-Application-{TARGET_VERSION}-v1", "Canonical application identity mismatch")
    require(str(canonical.get("manifest_sha256") or "").upper() == CANONICAL_MANIFEST_SHA256, "Canonical manifest binding mismatch")
    require(int(canonical.get("file_count") or 0) == 13, "Canonical application file count mismatch")
    require(canonical.get("source_dir") == "src/application", "Canonical source_dir mismatch")

    require((current.get("active_runtime_base") or {}).get("id") == RUNTIME_BASE_ID, "CURRENT active runtime-base mismatch")
    require((current.get("active_runtime_stack") or {}).get("id") == RUNTIME_STACK_ID, "CURRENT active runtime-stack mismatch")

    require(not (ROOT / "artifacts").exists(), "Legacy builder-local artifacts directory must be absent")
    require(not (ROOT / "reports").exists(), "Legacy builder-local reports directory must be absent")





def toolchain():
    node = ROOT / "_toolchain" / "Node" / "24.18.0" / "node.exe"
    npm_cli = ROOT / "_toolchain" / "Node" / "24.18.0" / "node_modules" / "npm" / "bin" / "npm-cli.js"
    for path in (node, npm_cli):
        require(path.is_file(), f"Owned Node toolchain file missing: {path}")
    require(run([node, "--version"]).stdout.strip() == EXPECTED["node_version"], "Owned Node version mismatch")
    require(run([node, npm_cli, "--version"]).stdout.strip() == EXPECTED["npm_version"], "Owned npm version mismatch")
    return node, npm_cli

def archives():
    root = ROOT / "_toolchain" / "Archives"
    result = {
        "electron": root / "electron-v36.3.2-win32-x64.zip",
        "sevenzip": root / "7zip-win-x64.tar.gz",
        "nsis": root / "nsis-3.0.4.1.7z",
        "nsis_resources": root / "nsis-resources-3.4.1.7z",
    }
    for key, path in result.items():
        assert_hash(f"owned {key} archive", path, EXPECTED[key + "_archive"])
    return result

def extract_electron(archive: Path, dest: Path):
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest)
    assert_hash("extracted electron.exe", dest / "electron.exe", EXPECTED["electron_exe"])
    require((dest / "resources").is_dir() and (dest / "locales").is_dir(), "Pinned Electron extraction incomplete")

def extract_sevenzip(archive: Path, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(dest)
    hits = [p for p in dest.rglob("7za.exe") if p.is_file()]
    require(len(hits) == 1, f"Expected one 7za.exe; found {len(hits)}")
    return hits[0]

def extract_nsis_toolchain(archive_map: dict, root: Path):
    seven = extract_sevenzip(archive_map["sevenzip"], root / "sevenzip")
    nsis = root / "electron-builder-cache" / "nsis" / "nsis-3.0.4.1"
    resources = root / "electron-builder-cache" / "nsis" / "nsis-resources-3.4.1"
    nsis.mkdir(parents=True, exist_ok=True)
    resources.mkdir(parents=True, exist_ok=True)
    run([seven, "x", archive_map["nsis"], f"-o{nsis}", "-y"])
    run([seven, "x", archive_map["nsis_resources"], f"-o{resources}", "-y"])
    makensis = nsis / "Bin" / "makensis.exe"
    assert_hash("canonical makensis", makensis, EXPECTED["canonical_makensis"])
    plugin = resources / "plugins" / "x86-unicode" / "nsis7z.dll"
    if not plugin.is_file():
        hits = [p for p in resources.rglob("nsis7z.dll") if p.is_file() and "x86-unicode" in str(p.parent).lower()]
        require(len(hits) == 1, "Canonical x86-unicode Nsis7z.dll missing")
        plugin = hits[0]
    return seven, makensis, plugin, root / "electron-builder-cache"

def runtime_base(current: dict, core_sha: str):
    root = ROOT / "_inputs" / "Runtime-Bases" / RUNTIME_BASE_ID
    metadata_root = ROOT / "provenance" / "runtime" / "runtime-base"
    descriptor_path = metadata_root / "RUNTIME-BASE.json"
    descriptor = read_json(descriptor_path)
    candidate = {
        "root": root,
        "metadata_root": metadata_root,
        "descriptor": descriptor,
        "descriptor_path": descriptor_path,
        "descriptor_sha256": sha256(descriptor_path),
    }
    control_path = ROOT / "runtime" / "runtime_base_control.py"
    spec = importlib.util.spec_from_file_location("aidirector_runtime_base_control", control_path)
    require(spec is not None and spec.loader is not None, f"Unable to load runtime-base control: {control_path}")
    runtime_base_control = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runtime_base_control)
    result = runtime_base_control.validate_candidate(candidate, current, core_sha)
    assert_hash("runtime base archive", result["archive_path"], EXPECTED["runtime_base_archive"])
    require(result["archive_path"].stat().st_size == 108500102, "Runtime-base v5 BCJ archive byte size mismatch")
    return result, descriptor_path, descriptor


def _download_public_upstream_source(contract: dict, destination: Path, log: Path):
    pub = contract["public_source_acquisition"]
    asset_id = int(pub["asset_id"])
    url = f"https://api.github.com/repos/unslothai/llama.cpp/releases/assets/{asset_id}"
    headers = {
        "Accept": "application/octet-stream",
        "User-Agent": "AI-Director-Canonical-Builder",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    req = urllib.request.Request(url, headers=headers)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=180) as response, destination.open("wb") as out:
        while True:
            block = response.read(4 * 1024 * 1024)
            if not block:
                break
            out.write(block)
    require(destination.stat().st_size == int(pub["asset_size"]), "Upstream public source asset size mismatch")
    require(sha256(destination) == str(pub["asset_sha256"]).upper(), "Upstream public source asset SHA256 mismatch")
    log.write_text(f"URL={url}\nASSET_ID={asset_id}\nSHA256={sha256(destination)}\n", encoding="utf-8", newline="\n")


def _acquire_direct_source(contract: dict, destination: Path, log: Path):
    sa = contract["source_authority"]
    repository = str(sa["repository"])
    accepted_commit = str(sa["accepted_commit"])
    accepted_tree = str(sa["accepted_tree"])
    git = shutil.which("git.exe") or shutil.which("git")
    require(git, "Git is required to acquire the pinned Direct source repository")
    url = f"https://github.com/{repository}.git"
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    run([git, "clone", "--filter=blob:none", "--no-checkout", url, destination], env=env, log=log)
    run([git, "-C", destination, "checkout", "--detach", accepted_commit], env=env, log=log.with_name("direct-checkout.log"))
    head = run([git, "-C", destination, "rev-parse", "HEAD"], env=env).stdout.strip()
    tree = run([git, "-C", destination, "rev-parse", "HEAD^{tree}"], env=env).stdout.strip()
    status = run([git, "-C", destination, "status", "--porcelain=v1", "--untracked-files=all"], env=env).stdout.strip()
    require(head == accepted_commit, f"Direct acquired HEAD mismatch: {head}")
    require(tree == accepted_tree, f"Direct acquired tree mismatch: {tree}")
    require(status == "", f"Direct acquired checkout is dirty: {status}")


def _validate_shared_cuda_redist_archives() -> dict[str, Path]:
    archives = {}
    expected_members = {}
    for archive_id, spec in SHARED_CUDA_REDIST.items():
        path = ROOT / Path(str(spec["path"]))
        assert_hash(f"shared CUDA {archive_id}", path, str(spec["sha256"]))
        require(path.stat().st_size == int(spec["bytes"]), f"Shared CUDA archive byte-size mismatch: {path}")
        archives[archive_id] = path
        with zipfile.ZipFile(path, "r") as zf:
            names = set(zf.namelist())
            for shipping_name, member in spec["members"].items():
                archive_path = str(member["archive_path"])
                require(archive_path in names, f"Shared CUDA archive member missing: {archive_path}")
                info = zf.getinfo(archive_path)
                require(info.file_size == int(member["bytes"]), f"Shared CUDA member byte-size mismatch: {shipping_name}")
                require(shipping_name not in expected_members, f"Duplicate shared CUDA shipping member: {shipping_name}")
                expected_members[shipping_name] = str(member["sha256"]).upper()
    require(set(expected_members) == {"cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll"}, "Shared CUDA redistributable member set mismatch")
    return archives


def _prepare_shared_cuda(manifest: dict, destination: Path):
    archives = _validate_shared_cuda_redist_archives()
    manifest_expected = {}
    for row in manifest["payload_files"]:
        source = str(row.get("source") or "")
        if source.startswith("payload/cuda/"):
            manifest_expected[Path(source).name] = str(row.get("sha256") or "").upper()
    require(set(manifest_expected) == {"cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll"}, "Shared CUDA manifest contract mismatch")

    destination.mkdir(parents=True, exist_ok=False)
    extracted = set()
    for archive_id, spec in SHARED_CUDA_REDIST.items():
        with zipfile.ZipFile(archives[archive_id], "r") as zf:
            for shipping_name, member in spec["members"].items():
                require(manifest_expected[shipping_name] == str(member["sha256"]).upper(), f"Shared CUDA accepted manifest/input identity mismatch: {shipping_name}")
                target = destination / shipping_name
                with zf.open(str(member["archive_path"]), "r") as source, target.open("wb") as out:
                    shutil.copyfileobj(source, out, length=4 * 1024 * 1024)
                require(target.stat().st_size == int(member["bytes"]), f"Extracted shared CUDA byte-size mismatch: {shipping_name}")
                require(sha256(target) == str(member["sha256"]).upper(), f"Extracted shared CUDA SHA256 mismatch: {shipping_name}")
                extracted.add(shipping_name)
    require(extracted == set(manifest_expected), "Extracted shared CUDA shipping set mismatch")
    return destination


def _tree_hashes(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha256(p) for p in root.rglob("*") if p.is_file()}


def build_source_runtime_stack(seven: Path, work: Path, logs: Path):
    # The accepted 0.3.24 runtime-stack archive is comparison/release authority only.
    # It is never extracted or consumed by this source-build path.
    accepted_manifest_path = ROOT / "provenance" / "runtime" / "runtime-stack" / "RUNTIME-STACK-MANIFEST.json"
    assert_hash("accepted runtime-stack manifest contract", accepted_manifest_path, "AA04F057CA1B8788BB759DE23CFFD3B7CE65D6BA2F38B2D55C35A9BEF56EBA51")
    template = read_json(accepted_manifest_path)
    require(template.get("runtime_stack_id") == RUNTIME_STACK_ID, "Runtime-stack manifest id mismatch")

    direct_contract_path = ROOT / "build" / "direct" / "AI-Director-Direct-Source-Build-Contract-v1.json"
    upstream_contract_path = ROOT / "build" / "upstream" / "AI-Director-Upstream-Source-Build-Contract-v2.json"
    direct_contract = read_json(direct_contract_path)
    upstream_contract = read_json(upstream_contract_path)
    require(sha256(direct_contract_path) == "A9AB28E0E6068F161206CE98425378337609A822D6DDD18A813803969352F8BC", "Direct source-build contract drift")
    require(sha256(upstream_contract_path) == "4E1B55ED7A95153D9BF3368C34FF5BAC98D994395E7369D924E7E668D5B0F1AA", "Upstream source-build contract drift")

    source_root = work / "server-source"
    source_root.mkdir()
    direct_source = source_root / "direct"
    _acquire_direct_source(direct_contract, direct_source, logs / "direct-source-acquire.log")

    upstream_archive = source_root / "upstream-source.tar.gz"
    _download_public_upstream_source(upstream_contract, upstream_archive, logs / "upstream-source-acquire.log")
    upstream_source = source_root / "upstream"
    py = owned_python()
    reconstruct = ROOT / "build" / "upstream" / "reconstruct_source.py"
    run([py, reconstruct, "--source-archive", upstream_archive, "--output", upstream_source], log=logs / "upstream-reconstruct.log")

    shared_cuda = _prepare_shared_cuda(template, work / "shared-cuda")

    direct_out = work / "direct-source-build"
    direct_work = work / "direct-source-work"
    direct_builder = ROOT / "build" / "direct" / "build_direct.py"
    direct_process_temp = work / "direct-process-temp"
    direct_process_temp.mkdir()
    direct_env = os.environ.copy()
    for key in ("TEMP", "TMP", "TMPDIR"):
        direct_env[key] = str(direct_process_temp)
    print(f"DIRECT_PROCESS_TEMP={direct_process_temp}")
    run([py, direct_builder, "--source-root", direct_source, "--work-root", direct_work, "--output-root", direct_out, "--jobs", "3"], env=direct_env, log=logs / "direct-source-build.log")
    direct_shipping = direct_out / "shipping"
    direct_report = direct_out / "AI-Director-Direct-Source-Build-Result-v1.json"
    require(direct_shipping.is_dir() and direct_report.is_file(), "Direct source-build output incomplete")

    upstream_out = work / "upstream-source-build"
    upstream_builder = ROOT / "build" / "upstream" / "build_upstream.py"
    upstream_process_temp = work / "upstream-process-temp"
    upstream_process_temp.mkdir()
    upstream_env = os.environ.copy()
    for key in ("TEMP", "TMP", "TMPDIR"):
        upstream_env[key] = str(upstream_process_temp)
    print(f"UPSTREAM_PROCESS_TEMP={upstream_process_temp}")
    run([py, upstream_builder, "--source-root", upstream_source, "--shared-cuda-root", shared_cuda, "--output-root", upstream_out, "--jobs", "3"], env=upstream_env, log=logs / "upstream-source-build.log")
    upstream_candidate = upstream_out / "candidate"
    upstream_report = upstream_out / "AI-Director-Upstream-Source-Build-v1.json"
    require(upstream_candidate.is_dir() and upstream_report.is_file(), "Upstream source-build output incomplete")

    manifest = json.loads(json.dumps(template))
    stage = work / "source-runtime-stack-stage"
    stage.mkdir()
    for row in manifest["payload_files"]:
        source_rel = str(row.get("source") or "").replace("\\", "/")
        name = Path(source_rel).name
        if source_rel.startswith("payload/cuda/"):
            source = shared_cuda / name
        elif source_rel.startswith("payload/direct/"):
            source = direct_shipping / name
        elif source_rel.startswith("payload/upstream/"):
            source = upstream_candidate / name
        else:
            raise RuntimeError(f"Unsupported runtime-stack payload source: {source_rel}")
        require(source.is_file(), f"Source-built runtime-stack payload missing: {source_rel}")
        target_rel = str(row.get("target") or "").replace("\\", "/")
        require(target_rel and not target_rel.startswith("/") and ".." not in Path(target_rel).parts, f"Unsafe runtime-stack target: {target_rel}")
        target = stage / Path(target_rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        row["sha256"] = sha256(target)

    manifest["candidate_build"] = {
        "construction_mode": "SOURCE_BUILT_DIRECT_AND_UPSTREAM",
        "accepted_runtime_stack_archive_consumed": False,
        "accepted_runtime_stack_archive_reference_sha256": EXPECTED["runtime_stack_archive"],
        "direct_contract_sha256": sha256(direct_contract_path),
        "direct_build_report_sha256": sha256(direct_report),
        "upstream_contract_sha256": sha256(upstream_contract_path),
        "upstream_build_report_sha256": sha256(upstream_report),
    }
    marker = str(manifest["install_marker"])
    manifest_path = stage / Path(marker)
    write_json(manifest_path, manifest)
    for rel in manifest["required_install_targets"]:
        require((stage / Path(str(rel))).is_file(), f"Generated runtime-stack required target missing: {rel}")

    generated = work / "source-runtime-stack"
    generated.mkdir()
    archive_path = generated / "RUNTIME-STACK.7z"
    run([seven, "a", "-t7z", "-mx=9", "-mmt=on", archive_path, "*"], cwd=stage, log=logs / "runtime-stack-archive.log")
    require(archive_path.is_file() and archive_path.stat().st_size > 0, "Generated runtime-stack archive missing")

    verify = work / "source-runtime-stack-verify"
    verify.mkdir()
    run([seven, "x", archive_path, f"-o{verify}", "-y"], log=logs / "runtime-stack-extract-verify.log")
    require(_tree_hashes(stage) == _tree_hashes(verify), "Generated runtime-stack archive extraction parity mismatch")

    report = {
        "schema_version": 1,
        "id": "AI-Director-Source-Built-Runtime-Stack-v1",
        "result": "PASS",
        "runtime_stack_id": RUNTIME_STACK_ID,
        "construction_mode": "SOURCE_BUILT_DIRECT_AND_UPSTREAM",
        "accepted_runtime_stack_archive_consumed": False,
        "accepted_runtime_stack_archive_reference_sha256": EXPECTED["runtime_stack_archive"],
        "manifest_sha256": sha256(manifest_path),
        "archive_sha256": sha256(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "direct": {"source_commit": direct_contract["source_authority"]["accepted_commit"], "source_tree": direct_contract["source_authority"]["accepted_tree"], "build_report_sha256": sha256(direct_report)},
        "upstream": {"source_tree": upstream_contract["authority"]["accepted_source_tree"], "build_report_sha256": sha256(upstream_report)},
        "shared_cuda": {name: sha256(shared_cuda / name) for name in ("cudart64_13.dll", "cublas64_13.dll", "cublasLt64_13.dll")},
    }
    report_path = generated / "AI-Director-Source-Built-Runtime-Stack-v1.json"
    write_json(report_path, report)
    partial_roots = [
        str(manifest["cuda"]["install_root"]),
        str(manifest["direct"]["install_root"]),
        str(manifest["upstream"]["install_root"]),
        str(Path(marker).parent).replace("\\", "/"),
    ]
    print("SOURCE_BUILT_RUNTIME_STACK=PASS")
    print("DIRECT_SOURCE_BUILD=PASS")
    print("UPSTREAM_SOURCE_BUILD=PASS")
    print("ACCEPTED_RUNTIME_STACK_ARCHIVE_CONSUMED=NO")
    print(f"SOURCE_RUNTIME_STACK_SHA256={sha256(archive_path)}")
    return {
        "id": RUNTIME_STACK_ID,
        "archive_path": archive_path,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "report_path": report_path,
        "direct_report_path": direct_report,
        "upstream_report_path": upstream_report,
    }, marker, list(manifest["required_install_targets"]), partial_roots


def set_version(project: Path, version: str):
    package = project / "package.json"
    lock = project / "package-lock.json"
    pobj = read_json(package)
    pobj["version"] = version
    write_json(package, pobj)
    lobj = read_json(lock)
    lobj["version"] = version
    packages = lobj.get("packages")
    if isinstance(packages, dict) and isinstance(packages.get(""), dict):
        packages[""]["version"] = version
    write_json(lock, lobj)

def prepare_project(api, current: dict, root: Path, logs: Path):
    node, npm_cli = toolchain()
    app_source = ROOT / "src" / "application"
    manifest_path = ROOT / "provenance" / "application" / "CANONICAL-SOURCE-MANIFEST.json"
    assert_hash("canonical source manifest", manifest_path, CANONICAL_MANIFEST_SHA256)
    manifest = read_json(manifest_path)
    require(
        manifest.get("schema_version") == 2
        and manifest.get("id") == f"AI-Director-Canonical-Application-{TARGET_VERSION}-v1"
        and manifest.get("version") == TARGET_VERSION,
        "Canonical source manifest identity/version mismatch",
    )
    rows = manifest.get("files")
    require(isinstance(rows, list) and len(rows) == 13 and manifest.get("file_count") == 13, "Canonical source manifest count mismatch")
    expected_paths = set()
    for row in rows:
        rel = str(row.get("path") or "").replace("\\", "/")
        require(rel and not rel.startswith("/") and ".." not in Path(rel).parts, f"Unsafe canonical source path: {rel}")
        path = app_source / Path(rel)
        require(path.is_file(), f"Canonical source file missing: {rel}")
        require(sha256(path) == str(row.get("sha256") or "").upper(), f"Canonical source hash mismatch: {rel}")
        require(path.stat().st_size == int(row.get("bytes") or -1), f"Canonical source size mismatch: {rel}")
        expected_paths.add(rel)
    actual_paths = {
        p.relative_to(app_source).as_posix()
        for p in app_source.rglob("*")
        if p.is_file()
    }
    require(actual_paths == expected_paths, "Canonical source manifest/tree path set mismatch")

    project = root / "project"
    shutil.copytree(app_source, project)
    env = os.environ.copy()
    env["npm_config_cache"] = str(root / "npm-cache")
    env["npm_config_audit"] = "false"
    env["npm_config_fund"] = "false"
    env["npm_config_update_notifier"] = "false"
    env["npm_config_prefer_online"] = "true"
    env["TEMP"] = str(root / "npm-tmp")
    env["TMP"] = str(root / "npm-tmp")
    env["TMPDIR"] = str(root / "npm-tmp")
    Path(env["TEMP"]).mkdir(parents=True, exist_ok=True)
    env["PATH"] = str(node.parent) + ";" + env.get("PATH", "")
    run([node, npm_cli, "ci", "--ignore-scripts", "--no-audit", "--no-fund"], cwd=project, env=env, log=logs / "npm-ci.log")
    eb_pkg = project / "node_modules" / "electron-builder" / "package.json"
    eb_cli = project / "node_modules" / "electron-builder" / "out" / "cli" / "cli.js"
    require(str(read_json(eb_pkg).get("version") or "") == EXPECTED["electron_builder_version"] and eb_cli.is_file(), "Fresh npm ci did not resolve electron-builder 26.15.3")
    branding = api.load_active_branding(ROOT, current)
    require(branding is not None and branding.get("id") == "AI-Director-Brand-v3", "Brand-v3 shell-stable icon authority is not active")
    branding_build = project / "build"
    api.copy_branding_build_assets(branding, branding_build)
    return node, eb_cli, project, env, [], [], branding, branding_build


def dir_build(api, node: Path, eb_cli: Path, project: Path, env: dict, archive_map: dict, root: Path, log: Path):
    electron_dist = root / "electron-dist"
    extract_electron(archive_map["electron"], electron_dist)
    config = project / "electron-builder.authoritative-dir.config.cjs"
    config.write_text(
        'const path = require("path");\n'
        'const pkg = require("./package.json");\n'
        'const electronDist = path.resolve(process.env.AI_DIRECTOR_OWNED_ELECTRON_DIST);\n'
        'module.exports = {\n'
        '  ...pkg.build,\n'
        '  electronVersion: "36.3.2",\n'
        '  electronDist,\n'
        '  directories: { output: "dist", buildResources: "build" },\n'
        '  win: { ...(pkg.build.win || {}), icon: "build/icon.ico" },\n'
        '};\n',
        encoding="ascii", newline="\n"
    )
    eb_env = env.copy()
    eb_env["AI_DIRECTOR_OWNED_ELECTRON_DIST"] = str(electron_dist)
    eb_env["ELECTRON_BUILDER_CACHE"] = str(root / "eb-dir-cache")
    eb_env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"
    eb_env["ELECTRON_SKIP_BINARY_DOWNLOAD"] = "1"
    eb_env["TEMP"] = str(root / "eb-dir-tmp")
    eb_env["TMP"] = str(root / "eb-dir-tmp")
    eb_env["TMPDIR"] = str(root / "eb-dir-tmp")
    Path(eb_env["TEMP"]).mkdir(parents=True, exist_ok=True)
    system_root = eb_env.get("SystemRoot") or eb_env.get("WINDIR") or r"C:\Windows"
    eb_env["PATH"] = ";".join([str(node.parent), str(Path(system_root)/"System32"/"WindowsPowerShell"/"v1.0"), str(Path(system_root)/"System32"), system_root])
    run([node, eb_cli, "--win", "--x64", "--dir", "--projectDir", project, "--config", config, "--publish", "never"], cwd=project, env=eb_env, log=log)
    pre = project / "dist" / "win-unpacked"
    exe = pre / "DaVinci Resolve AI Director.exe"
    asar = pre / "resources" / "app.asar"
    observer = pre / "resources" / "ResolveUiStatusObserver.ps1"
    for p in (exe, asar, observer):
        require(p.is_file(), f"Temporary win-unpacked output missing: {p}")
    app_pe_metadata = api.validate_pe_project_metadata(
        exe,
        target_version=TARGET_VERSION,
        product_name="DaVinci Resolve AI Director",
        file_description="DaVinci Resolve AI Director",
    )
    fv, pv = app_pe_metadata["file_version"], app_pe_metadata["product_version"]

    asar_candidates = list((project / "node_modules" / "@electron" / "asar" / "bin").glob("asar.*"))
    require(bool(asar_candidates), "@electron/asar CLI missing after fresh npm ci")
    extracted = root / "asar-verify"
    run([node, asar_candidates[0], "extract", asar, extracted], log=root / "logs" / "asar-extract.log")

    canonical_package = read_json(ROOT / "src" / "application" / "package.json")
    packaged_pkg = read_json(extracted / "package.json")
    for key in ("name", "version", "description", "main", "private"):
        require(packaged_pkg.get(key) == canonical_package.get(key), f"Packaged package.json semantic mismatch: {key}")
    require(packaged_pkg.get("version") == TARGET_VERSION, f"Packaged ASAR version mismatch: {packaged_pkg.get('version')}")

    build_files = canonical_package.get("build", {}).get("files")
    require(isinstance(build_files, list) and build_files, "Canonical package build.files missing")
    expected_packaged = {str(x).replace("\\", "/") for x in build_files}
    actual_packaged = {
        p.relative_to(extracted).as_posix()
        for p in extracted.rglob("*")
        if p.is_file()
    }
    require(actual_packaged == expected_packaged, f"Packaged ASAR file set mismatch Expected={sorted(expected_packaged)} Actual={sorted(actual_packaged)}")
    for rel in sorted(expected_packaged - {"package.json"}):
        src = project / Path(rel)
        dst = extracted / Path(rel)
        require(src.is_file() and dst.is_file() and sha256(src) == sha256(dst), f"Packaged canonical application file mismatch: {rel}")

    observer_source = project / "ResolveUiStatusObserver.ps1"
    require(observer_source.is_file() and sha256(observer_source) == sha256(observer), "Packaged ResolveUiStatusObserver.ps1 byte mismatch")
    print("FINAL_ASAR_SOURCE_PARITY=PASS")
    print(f"FINAL_ASAR_SHA256={sha256(asar)}")
    return pre, config, electron_dist


def make_include(api, runtime_base_obj, stack, marker, required_targets, partial_roots, generator: Path, child: Path, branding, branding_build: Path):
    text = api.make_nsis_include(
        runtime_base_obj["archive_path"],
        generator,
        resolve_integration_setup=child,
        resolve_integration_version=TARGET_VERSION,
        branding=branding,
        branding_build_dir=branding_build,
        runtime_stack_archive=stack["archive_path"],
        runtime_stack_marker=marker,
        runtime_stack_required_targets=required_targets,
        runtime_stack_partial_roots=partial_roots,
    )
    api.validate_nsis_include(
        text,
        resolve_integration_setup=child,
        resolve_integration_version=TARGET_VERSION,
        branding=branding,
        runtime_stack_archive=stack["archive_path"],
        runtime_stack_marker=marker,
        runtime_stack_required_targets=required_targets,
        runtime_stack_partial_roots=partial_roots,
    )
    for token in ("RETIREMENT-MANIFEST.json", "Invoke-AIDirectorLegacyRuntimeRetirement-v1.ps1", "AI-Director-Legacy-Runtime-Retirement.json"):
        require(token not in text, f"Generated NSIS contains forbidden retirement token: {token}")
    return text

def static_pe(path: Path):
    require(path.is_file() and path.stat().st_size >= 4096, f"Expected PE output missing/small: {path}")
    with path.open("rb") as f:
        head = f.read(4096)
    require(head[:2] == b"MZ", f"Output is not MZ PE: {path}")
    peoff = int.from_bytes(head[0x3C:0x40], "little")
    with path.open("rb") as f:
        f.seek(peoff)
        sig = f.read(4)
    require(sig == b"PE\0\0", f"Output PE signature invalid: {path}")

def _build_once_unlocked(*, public_checked_out_build: bool = False) -> int:
    controller_sha = sha256(Path(__file__).resolve())
    current_sha_before = sha256(CURRENT_PATH)
    current = read_json(CURRENT_PATH)
    validate_current_prebuild(current, controller_sha, public_checked_out_build=public_checked_out_build)

    policy = current.get("build_output_policy") or {}
    rel_root = Path(str(policy.get("relative_root") or ""))
    prefix = str(policy.get("attempt_prefix") or "")
    require(policy.get("mode") == "BUILDER_PARENT_RELATIVE_SEQUENTIAL", "CURRENT build-output policy mode mismatch")
    require(not rel_root.is_absolute() and ".." not in rel_root.parts, "CURRENT build-output relative root is unsafe")
    require(prefix == "static-build-", "CURRENT build-output attempt prefix mismatch")

    series_root = ROOT.parent / rel_root / TARGET_VERSION
    completed_indexes = []
    stale_staging = []
    if series_root.exists():
        require(series_root.is_dir(), f"Release-candidate series root is not a directory: {series_root}")
        for item in series_root.iterdir():
            name = item.name
            if name.startswith("." + prefix) and ".staging-" in name:
                stale_staging.append(str(item))
                continue
            if name.startswith(prefix):
                suffix = name[len(prefix):]
                if suffix.isdigit() and item.is_dir():
                    completed_indexes.append(int(suffix))
    require(not stale_staging, f"Stale release-candidate staging directories exist: {sorted(stale_staging)}")
    attempt_index = (max(completed_indexes) + 1) if completed_indexes else 1
    require(attempt_index <= 999999, "Release-candidate sequential attempt limit exceeded")
    attempt_name = f"{prefix}{attempt_index:03d}"
    output_root = series_root / attempt_name
    require(not output_root.exists(), f"Sequential release-candidate output collision: {output_root}")

    core_sha = sha256(CORE_PATH)
    api = load_core()
    work = Path(tempfile.mkdtemp(prefix=f"AI-Director-{TARGET_VERSION}-StaticBuild-"))
    # AI_DIRECTOR_BUILD_TEMP_CONTAINMENT_V1: the one permitted top-level Temp entry is `work`.
    # Every generic descendant process inherits a fallback inside that workspace; phase-specific
    # Direct/Upstream/npm/electron-builder roots remain unchanged and take precedence.
    inherited_process_temp = {k: os.environ.get(k) for k in ('TEMP','TMP','TMPDIR')}
    inherited_tempfile_tempdir = tempfile.tempdir
    process_temp = work / 'process-temp'
    process_temp.mkdir()
    for k in ('TEMP','TMP','TMPDIR'):
        os.environ[k] = str(process_temp)
    tempfile.tempdir = str(process_temp)
    print(f"BUILD_WORK_ROOT={work}", flush=True)
    print(f"BUILD_PROCESS_TEMP={process_temp}", flush=True)
    output_stage = series_root / f".{attempt_name}.staging-{os.getpid()}"
    require(not output_stage.exists(), f"Release-candidate staging path already exists: {output_stage}")
    output_committed = False

    try:
        logs = work / "logs"
        archive_map = archives()
        seven, makensis, _, eb_cache = extract_nsis_toolchain(archive_map, work / "pinned-tools")
        base, descriptor_path, descriptor = runtime_base(current, core_sha)
        print("BUILD_STAGE=SOURCE_RUNTIME_STACK_BEGIN", flush=True)
        stack, marker, required_targets, partial_roots = build_source_runtime_stack(seven, work, logs)
        print("BUILD_STAGE=SOURCE_RUNTIME_STACK_END", flush=True)
        generator = ROOT / "runtime" / "support" / "Generate-AIDirectorRuntimePaths.ps1"
        assert_hash("runtime path generator", generator, EXPECTED["runtime_path_generator"])

        print("BUILD_STAGE=APPLICATION_PACKAGING_BEGIN", flush=True)
        node, eb_cli, project, env, _overlays, _stack_targets, branding, branding_build = prepare_project(
            api, current, work, logs
        )
        require(_overlays == [] and _stack_targets == [],
                "Canonical build unexpectedly reported layered application composition")

        prepackaged, _, electron_dist = dir_build(
            api, node, eb_cli, project, env, archive_map, work, logs / "electron-builder-dir.log"
        )

        launcher = api.load_active_resolve_launcher(ROOT, current)
        require(launcher is not None, "Active Resolve launcher is required")
        original_find = api.find_makensis
        api.find_makensis = lambda _builder: makensis
        try:
            child_log = logs / "resolve-launcher-makensis.log"
            child = api.build_resolve_launcher_installer(
                ROOT, work, launcher, TARGET_VERSION, branding=branding, log=child_log
            )
            child_audit = api.static_audit_resolve_launcher_installer(
                child, launcher, work, target_version=TARGET_VERSION, makensis_log=child_log
            )
        finally:
            api.find_makensis = original_find
        static_pe(child)

        include = make_include(
            api, base, stack, marker, required_targets, partial_roots,
            generator, child, branding, branding_build
        )
        include_path = work / "installer.nsh"
        include_path.write_text(include, encoding="utf-8", newline="\n")

        config = project / "electron-builder.authoritative-nsis.config.cjs"
        config.write_text(
            'const path = require("path");\n'
            'const pkg = require("./package.json");\n'
            'module.exports = {\n'
            '  ...pkg.build,\n'
            '  electronVersion: "36.3.2",\n'
            '  electronDist: path.resolve(process.env.AI_DIRECTOR_OWNED_ELECTRON_DIST),\n'
            '  directories: { output: "installer-dist", buildResources: "build" },\n'
            '  win: { ...(pkg.build.win || {}), icon: "build/icon.ico" },\n'
            '  nsis: { ...(pkg.build.nsis || {}), include: path.resolve(process.env.AI_DIRECTOR_NSIS_INCLUDE) },\n'
            '};\n',
            encoding="ascii", newline="\n"
        )

        eb_env = env.copy()
        eb_env["AI_DIRECTOR_OWNED_ELECTRON_DIST"] = str(electron_dist)
        eb_env["AI_DIRECTOR_NSIS_INCLUDE"] = str(include_path)
        eb_env["ELECTRON_BUILDER_7ZIP_PATH"] = str(seven)
        eb_env["ELECTRON_BUILDER_CACHE"] = str(eb_cache)
        eb_env["CSC_IDENTITY_AUTO_DISCOVERY"] = "false"
        eb_env["ELECTRON_SKIP_BINARY_DOWNLOAD"] = "1"
        eb_env["ELECTRON_BUILDER_7Z_FILTER"] = "BCJ"
        eb_env["TEMP"] = str(work / "eb-nsis-tmp")
        eb_env["TMP"] = str(work / "eb-nsis-tmp")
        eb_env["TMPDIR"] = str(work / "eb-nsis-tmp")
        Path(eb_env["TEMP"]).mkdir(parents=True, exist_ok=True)
        system_root = eb_env.get("SystemRoot") or eb_env.get("WINDIR") or r"C:\Windows"
        eb_env["PATH"] = ";".join([
            str(node.parent),
            str(Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0"),
            str(Path(system_root) / "System32"),
            system_root,
        ])

        print(f"OWNED_SEVENZIP_EXECUTABLE={seven}")
        print("OWNED_SEVENZIP_BINDING_MODE=ELECTRON_BUILDER_26_15_3_DIRECT_PATH")

        run(
            [
                node, eb_cli, "--win", "nsis", "--x64", "--prepackaged", prepackaged,
                "--projectDir", project, "--config", config, "--publish", "never"
            ],
            cwd=project,
            env=eb_env,
            log=logs / "electron-builder-nsis.log",
        )

        expected_main_setup_name = f"DaVinci Resolve AI Director Setup {TARGET_VERSION}.exe"
        expected_integration_setup_name = f"{api.AI_DIRECTOR_INTEGRATION_SETUP_PREFIX} {TARGET_VERSION}.exe"
        setup = project / "installer-dist" / expected_main_setup_name
        require(child.name == expected_integration_setup_name, f"Resolve Integration artifact name mismatch: {child.name!r}")
        static_pe(setup)
        print("BUILD_STAGE=APPLICATION_PACKAGING_END", flush=True)

        base_offset = api.exact_stream_offset(setup, base["archive_path"])
        stack_offset = api.exact_stream_offset(setup, stack["archive_path"])
        child_offset = api.exact_stream_offset(setup, child)
        require(len({base_offset, stack_offset, child_offset}) == 3,
                "Embedded exact payload stream offsets unexpectedly collide")

        asar = prepackaged / "resources" / "app.asar"
        exe = prepackaged / "DaVinci Resolve AI Director.exe"
        app_pe_metadata = api.validate_pe_project_metadata(
            exe,
            target_version=TARGET_VERSION,
            product_name="DaVinci Resolve AI Director",
            file_description="DaVinci Resolve AI Director",
        )
        fv, pv = app_pe_metadata["file_version"], app_pe_metadata["product_version"]
        setup_pe_metadata = api.validate_pe_project_metadata(
            setup,
            target_version=TARGET_VERSION,
            product_name="DaVinci Resolve AI Director",
            file_description="DaVinci Resolve AI Director",
        )

        source_root = ROOT / "src" / "application"
        source_main_sha = sha256(source_root / "main.js")
        source_update_sha = sha256(source_root / "UpdateManager.js")

        report_obj = {
            "schema_version": 1,
            "status": "PASS_STATIC_RELEASE_CANDIDATE_BUILD",
            "target_version": TARGET_VERSION,
            "build_intent": ("PUBLIC_CHECKED_OUT_VERSION_REPRODUCTION" if public_checked_out_build else "MAINTAINER_PREPARED_TARGET"),
            "source_release_state": current.get("state_mode"),
            "release_candidate_attempt": attempt_name,
            "release_candidate_sequence": attempt_index,
            "live_accepted_authority": PREDECESSOR_VERSION,
            "live_accepted": False,
            "installation_performed": False,
            "setup_executed": False,
            "builder_source_mutated_by_build": False,
            "build_output_bound_to_current": False,
            "builder_core_sha256": core_sha,
            "build_controller_sha256": controller_sha,
            "canonical_source_manifest_sha256": CANONICAL_MANIFEST_SHA256,
            "artifact_naming_contract": "WINDOWS_PUBLIC_ARTIFACT_NAMES_V1",
            "owned_toolchain": {
                "sevenzip_binding_mode": "ELECTRON_BUILDER_26_15_3_DIRECT_PATH",
                "sevenzip_archive_sha256": EXPECTED["sevenzip_archive"],
            },
            "application": {
                "exe_sha256": sha256(exe),
                "asar_sha256": sha256(asar),
                "file_version": fv,
                "product_version": pv,
                "pe_metadata": app_pe_metadata,
                "source_authority": "CANONICAL",
                "active_overlay_count": 0,
                "runtime_stack_application_composition_active": False,
                "final_asar_source_parity": True,
                "canonical_main_js_sha256": source_main_sha,
                "canonical_update_manager_sha256": source_update_sha,
            },
            "runtime_base": {
                "id": RUNTIME_BASE_ID,
                "descriptor_sha256": sha256(descriptor_path),
                "runtime_base_manifest_sha256": sha256(base["manifest_path"]),
                "archive_sha256": sha256(base["archive_path"]),
                "archive_bytes": base["archive_path"].stat().st_size,
                "exact_stream_offset": base_offset,
                "inventory_sha256": sha256(base["inventory_path"]),
                "inventory_file_count": int((current.get("active_runtime_base") or {}).get("inventory_file_count") or 0),
                "archive_filter": "BCJ",
                "bundled_mcp_seed": "4.15.3",
            },
            "runtime_stack": {
                "id": RUNTIME_STACK_ID,
                "construction_mode": "SOURCE_BUILT_DIRECT_AND_UPSTREAM",
                "accepted_archive_consumed": False,
                "accepted_archive_reference_sha256": EXPECTED["runtime_stack_archive"],
                "generated_manifest_sha256": sha256(stack["manifest_path"]),
                "generated_archive_sha256": sha256(stack["archive_path"]),
                "generated_archive_bytes": stack["archive_path"].stat().st_size,
                "source_build_report_sha256": sha256(stack["report_path"]),
                "direct_build_report_sha256": sha256(stack["direct_report_path"]),
                "upstream_build_report_sha256": sha256(stack["upstream_report_path"]),
                "exact_stream_offset": stack_offset,
                "application_composition_active": False,
            },
            "resolve_integration": {
                "artifact_name": expected_integration_setup_name,
                "installer_sha256": sha256(child),
                "exact_stream_offset": child_offset,
                "static_audit": child_audit,
                "setup_executed": False,
            },
            "installer": {
                "artifact_name": expected_main_setup_name,
                "sha256": sha256(setup),
                "bytes": setup.stat().st_size,
                "pe_metadata": setup_pe_metadata,
                "setup_executed": False,
            },
            "remaining_live_gate": {
                "outer_window_ring": "LIVE_TEST_REQUIRED",
                "dirty_upgrade": "LIVE_TEST_REQUIRED",
                "clean_install": "LIVE_TEST_REQUIRED",
                "mcp_model_behavior": "LIVE_TEST_REQUIRED",
            },
        }

        series_root.mkdir(parents=True, exist_ok=True)
        # Recheck stale state immediately before claiming the next attempt.
        concurrent_stale = sorted(
            str(p) for p in series_root.iterdir()
            if p.name.startswith("." + prefix) and ".staging-" in p.name
        )
        require(not concurrent_stale, f"Stale/concurrent release-candidate staging directories exist: {concurrent_stale}")
        require(not output_root.exists(), f"Sequential release-candidate output collision before commit: {output_root}")
        output_stage.mkdir(parents=False, exist_ok=False)
        stage_artifacts = output_stage / "artifacts"
        stage_reports = output_stage / "reports"
        stage_artifacts.mkdir()
        stage_reports.mkdir()

        staged_setup = stage_artifacts / expected_main_setup_name
        staged_child = stage_artifacts / expected_integration_setup_name
        staged_report = stage_reports / f"STATIC-BUILD-REPORT-{TARGET_VERSION}.json"
        staged_stack_report = stage_reports / f"SOURCE-RUNTIME-STACK-BUILD-REPORT-{TARGET_VERSION}.json"
        staged_direct_report = stage_reports / f"DIRECT-SOURCE-BUILD-REPORT-{TARGET_VERSION}.json"
        staged_upstream_report = stage_reports / f"UPSTREAM-SOURCE-BUILD-REPORT-{TARGET_VERSION}.json"

        shutil.copy2(setup, staged_setup)
        shutil.copy2(child, staged_child)
        shutil.copy2(stack["report_path"], staged_stack_report)
        shutil.copy2(stack["direct_report_path"], staged_direct_report)
        shutil.copy2(stack["upstream_report_path"], staged_upstream_report)
        write_json(staged_report, report_obj)

        assert_hash("release-candidate installer", staged_setup, report_obj["installer"]["sha256"])
        assert_hash(
            "release-candidate Resolve Integration installer",
            staged_child,
            report_obj["resolve_integration"]["installer_sha256"],
        )
        report_sha = sha256(staged_report)
        stack_report_sha = sha256(staged_stack_report)
        direct_report_sha = sha256(staged_direct_report)
        upstream_report_sha = sha256(staged_upstream_report)

        require(sha256(CURRENT_PATH) == current_sha_before,
                "Build unexpectedly mutated CURRENT.json before output commit")
        require(not (ROOT / "artifacts").exists() and not (ROOT / "reports").exists(),
                "Legacy builder-local output directories reappeared during build")

        os.replace(output_stage, output_root)
        output_committed = True

        require(sha256(CURRENT_PATH) == current_sha_before,
                "Build unexpectedly mutated CURRENT.json after output commit")
        require(not (ROOT / "artifacts").exists() and not (ROOT / "reports").exists(),
                "Legacy builder-local output directories reappeared after build")

        final_setup = output_root / "artifacts" / staged_setup.name
        final_child = output_root / "artifacts" / staged_child.name
        final_report = output_root / "reports" / staged_report.name
        final_stack_report = output_root / "reports" / staged_stack_report.name
        final_direct_report = output_root / "reports" / staged_direct_report.name
        final_upstream_report = output_root / "reports" / staged_upstream_report.name
        assert_hash("committed release-candidate installer", final_setup, report_obj["installer"]["sha256"])
        assert_hash(
            "committed release-candidate Resolve Integration installer",
            final_child,
            report_obj["resolve_integration"]["installer_sha256"],
        )
        assert_hash("committed static build report", final_report, report_sha)
        assert_hash("committed source runtime-stack report", final_stack_report, stack_report_sha)
        assert_hash("committed Direct source-build report", final_direct_report, direct_report_sha)
        assert_hash("committed Upstream source-build report", final_upstream_report, upstream_report_sha)

        print("STATUS=PASS_STATIC_RELEASE_CANDIDATE_BUILD")
        print("BUILD_INTENT=" + ("PUBLIC_CHECKED_OUT_VERSION_REPRODUCTION" if public_checked_out_build else "MAINTAINER_PREPARED_TARGET"))
        print("RELEASE_STATE_MUTATED_BY_PLAIN_BUILD=False")
        print(f"RELEASE_CANDIDATE_SERIES_ROOT={series_root}")
        print(f"RELEASE_CANDIDATE_ATTEMPT={attempt_name}")
        print(f"RELEASE_CANDIDATE_SEQUENCE={attempt_index}")
        print(f"RELEASE_CANDIDATE_OUTPUT={output_root}")
        print(f"INSTALLER={final_setup}")
        print(f"INSTALLER_SHA256={sha256(final_setup)}")
        print(f"RESOLVE_INTEGRATION_INSTALLER={final_child}")
        print(f"RESOLVE_INTEGRATION_SHA256={sha256(final_child)}")
        print(f"REPORT={final_report}")
        print(f"REPORT_SHA256={report_sha}")
        print(f"SOURCE_RUNTIME_STACK_REPORT={final_stack_report}")
        print(f"SOURCE_RUNTIME_STACK_REPORT_SHA256={stack_report_sha}")
        print(f"DIRECT_SOURCE_BUILD_REPORT={final_direct_report}")
        print(f"DIRECT_SOURCE_BUILD_REPORT_SHA256={direct_report_sha}")
        print(f"UPSTREAM_SOURCE_BUILD_REPORT={final_upstream_report}")
        print(f"UPSTREAM_SOURCE_BUILD_REPORT_SHA256={upstream_report_sha}")
        print(f"FINAL_ASAR_SHA256={sha256(asar)}")
        print("FINAL_ASAR_SOURCE_PARITY=PASS")
        print("BUILDER_LOCAL_ARTIFACTS_DIRECTORY_EXISTS=False")
        print("BUILDER_LOCAL_REPORTS_DIRECTORY_EXISTS=False")
        print("BUILD_OUTPUT_BOUND_TO_CURRENT=False")
        print("CURRENT_MUTATED_BY_BUILD=False")
        print("SETUP_EXECUTED=False")
        print("INSTALLATION_PERFORMED=False")
        print("LIVE_ACCEPTED=False")
        return 0

    except Exception as original_exc:
        try:
            if output_stage.exists():
                shutil.rmtree(output_stage)
            require(not output_stage.exists(), f"Failed-build staging cleanup could not be proven: {output_stage}")
            if output_committed and output_root.exists():
                shutil.rmtree(output_root)
            if output_committed:
                require(not output_root.exists(), f"Failed-build committed-output cleanup could not be proven: {output_root}")
            try:
                if series_root.exists() and not any(series_root.iterdir()):
                    series_root.rmdir()
                rc_root = ROOT.parent / rel_root
                if rc_root.exists() and rc_root.is_dir() and not any(rc_root.iterdir()):
                    rc_root.rmdir()
            except OSError:
                pass
        except Exception as cleanup_exc:
            raise RuntimeError(
                f"Build failed and failed-build output cleanup could not be proven: "
                f"original={original_exc!r}; cleanup={cleanup_exc!r}"
            ) from original_exc
        raise
    finally:
        active_exc = sys.exc_info()[1]
        try:
            try:
                if work.exists():
                    remove_tree_strict(work, "Build temp")
                require(not work.exists(), f"Build temp cleanup failed: {work}")
                print("BUILD_TEMP_REMOVED=True")
            except Exception as cleanup_exc:
                print("BUILD_TEMP_REMOVED=False")
                print(f"BUILD_TEMP_CLEANUP_ERROR={cleanup_exc}")
                if active_exc is None:
                    raise
        finally:
            tempfile.tempdir = inherited_tempfile_tempdir
            for k, value in inherited_process_temp.items():
                if value is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = value
            print("BUILD_PROCESS_TEMP_RESTORED=True")



def build_once(*, public_checked_out_build: bool = False) -> int:
    inherited = os.environ.get("AI_DIRECTOR_INHERITED_OPERATION_LOCK") == "1"
    if inherited:
        expected_target = str(os.environ.get("AI_DIRECTOR_EXPECT_TARGET_VERSION") or "")
        require(expected_target, "Inherited BUILD target expectation missing")
        validate_inherited_operation_lock(expected_target)
        current = read_json(CURRENT_PATH)
        require(str(current.get("target_version") or "") == expected_target,
                "Inherited BUILD target differs from CURRENT target")
        print("BUILD_OPERATION_LOCK=INHERITED_SERIALIZED_PARENT")
        return _build_once_unlocked(public_checked_out_build=public_checked_out_build)

    current = read_json(CURRENT_PATH)
    target = str(current.get("target_version") or "")
    lock = acquire_operation_lock("BUILD", target)
    try:
        return _build_once_unlocked(public_checked_out_build=public_checked_out_build)
    finally:
        release_operation_lock(lock)


def validate_system_toolchain() -> str:
    require(SYSTEM_TOOLCHAIN_VERIFY_PATH.is_file(), f"System-toolchain verifier missing: {SYSTEM_TOOLCHAIN_VERIFY_PATH}")
    py = owned_python()
    output = run_control_child([py, "-B", SYSTEM_TOOLCHAIN_VERIFY_PATH], os.environ.copy())
    require("SYSTEM_TOOLCHAIN_STATUS=PASS" in output, "External system-toolchain prerequisite validation did not pass")
    return output


def public_source_preflight() -> int:
    current = read_json(CURRENT_PATH)
    require(current.get("schema_version") == 5, "release-state schema mismatch")
    require(current.get("product") == "DaVinci Resolve AI Director", "release-state product mismatch")
    require(current.get("repository_mode") == "PUBLIC_SOURCE_REPOSITORY_V1", "Public repository mode mismatch")
    py = owned_python()
    toolchain()
    archives()
    validate_system_toolchain()
    core_sha = sha256(CORE_PATH)
    load_core()
    rb, _descriptor_path, _descriptor = runtime_base(current, core_sha)
    _validate_shared_cuda_redist_archives()
    check = run_control_child([py, "-B", ROOT / "build" / "package" / "check_state.py"], os.environ.copy())
    require("CHECK_STATE_STATUS=PASS" in check, "Public CHECK-STATE preflight did not pass")
    print("PUBLIC_BUILD_PREFLIGHT=PASS")
    print(f"PUBLIC_PREFLIGHT_TARGET={current.get('target_version')}")
    print(f"PUBLIC_PREFLIGHT_STATE={current.get('state_mode')}")
    print("PUBLIC_PLAIN_BUILD_SEMANTICS=CHECKED_OUT_VERSION_NONMUTATING")
    public_state = read_json(ROOT / "build" / "package" / "public-repository-state.json")
    target_publication_pending = (
        current.get("state_mode") == "TARGET_READY"
        and public_state.get("runtime_base_public_url_bound") is False
    )
    if target_publication_pending:
        print("PUBLIC_PLAIN_BUILD_ELIGIBLE=False_TARGET_RUNTIME_BASE_PUBLICATION_PENDING")
        print("LOCAL_TARGET_READY_BUILD_ELIGIBLE=True")
    else:
        print("PUBLIC_PLAIN_BUILD_ELIGIBLE=True")
        print("LOCAL_TARGET_READY_BUILD_ELIGIBLE=True")
    print(f"PUBLIC_PLAIN_BUILD_TARGET={current.get('target_version')}")
    print("PUBLIC_PLAIN_BUILD_RELEASE_STATE_MUTATION=False")
    print(f"RUNTIME_BASE_ARCHIVE={rb['archive_path']}")
    print("SHARED_CUDA_BOOTSTRAP_SOURCE=NVIDIA_OFFICIAL_REDIST_13.3.1")
    print("SHARED_CUDA_ARCHIVE_INPUTS=PASS")
    print("BUILD_EXECUTED=False")
    print("SETUP_EXECUTED=False")
    print("INSTALLED_PRODUCT_TOUCHED=False")
    return 0

def parse_args():
    parser = argparse.ArgumentParser(description="AI Director authoritative static Builder.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--patch", action="store_true", help="Prepare the next patch from accepted authority, then build.")
    group.add_argument("--minor", action="store_true", help="Prepare the next minor from accepted authority, then build.")
    group.add_argument("--major", action="store_true", help="Prepare the next major from accepted authority, then build.")
    group.add_argument("--version", metavar="X.Y.Z", help="Prepare an explicit semantic version, then build.")
    group.add_argument("--accept", action="store_true", help="Run the separate explicit acceptance gate for an installed release candidate.")
    group.add_argument("--preflight", action="store_true", help="Validate public-source repository inputs without building or mutating release state.")
    parser.add_argument("--candidate", metavar="static-build-NNN", help="Select a release candidate for --accept when multiple candidates exist.")
    parser.add_argument("--dry-run", action="store_true", help="With --accept, run all mechanical acceptance checks without attestation or mutation.")
    args = parser.parse_args()
    if not args.accept and (args.candidate is not None or args.dry_run):
        parser.error("--candidate and --dry-run are valid only with --accept")
    return args


def version_args_from_args(args) -> list[str]:
    if args.patch:
        return ["--patch"]
    if args.minor:
        return ["--minor"]
    if args.major:
        return ["--major"]
    if args.version is not None:
        return ["--version", args.version]
    return []


def prepare_then_build(version_args: list[str]) -> int:
    lock = acquire_operation_lock("BUILD", "UNRESOLVED")
    try:
        initial = read_json(CURRENT_PATH)
        accepted_before = str(initial.get("live_accepted_authority") or "")
        py = owned_python()
        inherited_env = inherited_operation_env()
        version_output = run_control_child(
            [py, "-B", ROOT / "build" / "package" / "version_control.py", *version_args, "--apply"],
            inherited_env,
        )
        selected = parse_selected_target(version_output)
        prepared = read_json(CURRENT_PATH)
        require(str(prepared.get("live_accepted_authority") or "") == accepted_before,
                "Version preparation unexpectedly changed accepted authority")
        require(prepared.get("state_mode") == "TARGET_READY",
                "Version preparation did not leave Builder TARGET_READY")
        require(str(prepared.get("target_version") or "") == selected,
                "Version preparation result does not match SELECTED_TARGET")

        update_operation_lock_target(lock, selected)
        child_env = inherited_operation_env(selected)
        print(f"SERIALIZED_BUILD_TARGET={selected}")
        print(f"SERIALIZED_LOCK_OWNER_PID={os.getpid()}")
        print("PREPARE_BUILD_LOCK_RELEASE_BETWEEN_PHASES=False")
        print("FRESH_BUILD_PROCESS_REQUIRED=True")
        run_control_child([py, "-B", Path(__file__).resolve()], child_env)
        return 0
    finally:
        release_operation_lock(lock)


def accept_candidate(candidate: str | None, dry_run: bool) -> int:
    require(ACCEPTANCE_CONTROL_PATH.is_file(), f"Acceptance control missing: {ACCEPTANCE_CONTROL_PATH}")
    current = read_json(CURRENT_PATH)
    require(current.get("state_mode") == "TARGET_READY", "BUILD --accept requires a prepared TARGET_READY version")
    target = str(current.get("target_version") or "")
    semantic_version(target)
    lock = acquire_operation_lock("ACCEPT", target)
    try:
        py = owned_python()
        env = inherited_operation_env(target, operation="ACCEPT")
        command = [py, "-B", ACCEPTANCE_CONTROL_PATH, "--dry-run" if dry_run else "--apply"]
        if candidate is not None:
            command.extend(["--candidate", candidate])
        print(f"SERIALIZED_ACCEPT_TARGET={target}")
        print(f"SERIALIZED_LOCK_OWNER_PID={os.getpid()}")
        print("ACCEPTANCE_GATE_SEPARATE_FROM_BUILD=True")
        output = run_control_child(command, env)
        require(
            ("ACCEPTANCE_DRY_RUN_STATUS=PASS" in output if dry_run else "ACCEPTANCE_PROMOTION_STATUS=PASS" in output),
            "Acceptance control did not report the expected PASS terminal status",
        )
        return 0
    finally:
        release_operation_lock(lock)


def main() -> int:
    args = parse_args()

    if args.preflight:
        return public_source_preflight()

    if args.accept and args.dry_run:
        require_accept_dry_run_recovery_absent()
        return accept_candidate(args.candidate, True)

    recover_acceptance_if_needed()
    recover_version_preparation_if_needed()
    if args.accept:
        return accept_candidate(args.candidate, False)

    version_args = version_args_from_args(args)
    validate_system_toolchain()
    if not version_args:
        current = read_json(CURRENT_PATH)
        if current.get("state_mode") == "ACCEPTED_READY":
            print("PUBLIC_PLAIN_BUILD=CHECKED_OUT_VERSION_NONMUTATING")
            print(f"PUBLIC_PLAIN_BUILD_TARGET={current.get('target_version')}")
            print("PUBLIC_PLAIN_BUILD_VERSION_PREPARATION=False")
            print("PUBLIC_PLAIN_BUILD_ACCEPTANCE=False")
            return build_once(public_checked_out_build=True)
        return build_once()
    return prepare_then_build(version_args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("STATUS=ERROR")
        print(traceback.format_exc())
        raise SystemExit(2)
