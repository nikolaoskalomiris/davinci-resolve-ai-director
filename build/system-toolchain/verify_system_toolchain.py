#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECT_CONTRACT = ROOT / "build" / "direct" / "AI-Director-Direct-Source-Build-Contract-v1.json"
UPSTREAM_CONTRACT = ROOT / "build" / "upstream" / "AI-Director-Upstream-Source-Build-Contract-v2.json"
EXPECTED_TOOL_COUNT = 14
EXPECTED_PLATFORM = "Windows x64"
EXPECTED_MSVC_TOOLSET = "14.44.35207"
EXPECTED_WINDOWS_SDK = "10.0.26100.0"
EXPECTED_CUDA_TOOLKIT = "13.3"
EXPECTED_NVCC = "V13.3.73"
WHERE_TOOLS = ("cl.exe", "link.exe", "lib.exe", "rc.exe", "mt.exe", "cmake.exe", "ninja.exe", "nvcc.exe")
CLEAN_ENV = ("CL", "_CL_", "NVCC_PREPEND_FLAGS", "NVCC_APPEND_FLAGS", "CUDAARCHS", "CMAKE_CUDA_ARCHITECTURES")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def run(args, *, env=None, timeout=120) -> tuple[int, str]:
    cp = subprocess.run(
        [str(x) for x in args],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    return cp.returncode, cp.stdout


def normalized(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


def main() -> int:
    require(os.name == "nt", "AI Director public source build currently requires Windows.")
    machine = platform.machine().lower()
    require(machine in ("amd64", "x86_64"), f"AI Director public source build requires Windows x64; detected {platform.machine()!r}.")
    require(DIRECT_CONTRACT.is_file(), f"Direct build contract missing: {DIRECT_CONTRACT}")
    require(UPSTREAM_CONTRACT.is_file(), f"Upstream build contract missing: {UPSTREAM_CONTRACT}")

    direct = read_json(DIRECT_CONTRACT)
    upstream = read_json(UPSTREAM_CONTRACT)
    dt = direct.get("toolchain") or {}
    ut = upstream.get("toolchain") or {}

    expected_fields = {
        "platform": EXPECTED_PLATFORM,
        "msvc_toolset": EXPECTED_MSVC_TOOLSET,
        "windows_sdk": EXPECTED_WINDOWS_SDK,
        "cuda_toolkit": EXPECTED_CUDA_TOOLKIT,
        "nvcc": EXPECTED_NVCC,
    }
    for key, expected in expected_fields.items():
        require(str(dt.get(key) or "") == expected, f"Direct system-toolchain {key} mismatch.")
        require(str(ut.get(key) or "") == expected, f"Upstream system-toolchain {key} mismatch.")

    dtools = dt.get("tools") or {}
    utools = ut.get("tools") or {}
    names = sorted(dtools)
    require(names == sorted(utools), "Direct/Upstream system-toolchain tool sets differ.")
    require(len(names) == EXPECTED_TOOL_COUNT, f"Expected {EXPECTED_TOOL_COUNT} pinned system tools; found {len(names)}.")

    for name in names:
        dr = dtools[name]
        ur = utools[name]
        require(str(dr.get("path") or "") == str(ur.get("path") or ""), f"Direct/Upstream path mismatch for {name}.")
        require(str(dr.get("sha256") or "").upper() == str(ur.get("sha256") or "").upper(), f"Direct/Upstream SHA256 mismatch for {name}.")
        path = Path(str(dr.get("path") or ""))
        require(path.is_file(), f"Required external system-toolchain file missing: {name}: {path}")
        actual = sha256(path)
        expected = str(dr.get("sha256") or "").upper()
        require(actual == expected, f"External system-toolchain SHA256 mismatch for {name}: expected={expected} actual={actual}")

    denv = direct.get("environment") or {}
    uenv = upstream.get("environment") or {}
    dset = denv.get("required_set") or {}
    uset = uenv.get("required_set") or {}
    for key in ("CUDA_PATH", "CUDACXX"):
        require(str(dset.get(key) or "") == str(uset.get(key) or ""), f"Direct/Upstream required environment differs for {key}.")

    vcvars = Path(str(dtools["vcvars64.bat"]["path"]))
    expected_paths = {name: normalized(str(dtools[name]["path"])) for name in WHERE_TOOLS}
    probe = Path(tempfile.gettempdir()) / f"aid-public-system-toolchain-{os.getpid()}.cmd"
    probe.write_text(
        "@echo off\r\n"
        + f'call "{vcvars}" -vcvars_ver=14.44 >nul\r\n'
        + "if errorlevel 1 exit /b %errorlevel%\r\n"
        + "set\r\n",
        encoding="ascii",
        newline="",
    )
    try:
        rc, output = run(["cmd.exe", "/d", "/c", str(probe)], timeout=120)
    finally:
        try:
            probe.unlink()
        except FileNotFoundError:
            pass
    require(rc == 0, "vcvars64.bat -vcvars_ver=14.44 failed.")

    env = dict(os.environ)
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    for key in CLEAN_ENV:
        env.pop(key, None)
    require(str(env.get("VCToolsVersion") or "").rstrip("\\") == EXPECTED_MSVC_TOOLSET, f"vcvars resolved unexpected VCToolsVersion: {env.get('VCToolsVersion')!r}")
    require(str(env.get("WindowsSDKVersion") or "").rstrip("\\") == EXPECTED_WINDOWS_SDK, f"vcvars resolved unexpected WindowsSDKVersion: {env.get('WindowsSDKVersion')!r}")
    env["CUDA_PATH"] = str(dset["CUDA_PATH"])
    env["CUDA_HOME"] = str(dset["CUDA_PATH"])
    env["CUDA_PATH_V13_3"] = str(dset["CUDA_PATH"])
    env["CUDACXX"] = str(dset["CUDACXX"])
    cmake = Path(str(dtools["cmake.exe"]["path"]))
    ninja = Path(str(dtools["ninja.exe"]["path"]))
    nvcc = Path(str(dtools["nvcc.exe"]["path"]))
    env["PATH"] = os.pathsep.join([str(cmake.parent), str(ninja.parent), str(nvcc.parent), env.get("PATH", "")])

    for name in WHERE_TOOLS:
        rc, output = run(["where.exe", name], env=env, timeout=30)
        require(rc == 0 and output.strip(), f"where.exe failed for required tool {name}.")
        first = output.splitlines()[0].strip()
        require(normalized(first) == expected_paths[name], f"Resolved {name} path mismatch: expected={dtools[name]['path']} actual={first}")

    rc, nvcc_out = run([nvcc, "--version"], env=env, timeout=30)
    require(rc == 0 and "release 13.3" in nvcc_out and "V13.3.73" in nvcc_out, "nvcc runtime identity mismatch.")

    print("SYSTEM_TOOLCHAIN_STATUS=PASS")
    print("SYSTEM_TOOLCHAIN_MODE=EXTERNAL_MACHINE_PREREQUISITES_STRICT_HASH_AND_PATH_VALIDATION")
    print("SYSTEM_TOOLCHAIN_AUTO_INSTALL=False")
    print("SYSTEM_TOOLCHAIN_TOOL_COUNT=14")
    print("SYSTEM_TOOLCHAIN_MSVC=14.44.35207")
    print("SYSTEM_TOOLCHAIN_WINDOWS_SDK=10.0.26100.0")
    print("SYSTEM_TOOLCHAIN_CUDA=13.3")
    print("SYSTEM_TOOLCHAIN_NVCC=V13.3.73")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("SYSTEM_TOOLCHAIN_STATUS=ERROR")
        print("ERROR=" + str(exc))
        raise SystemExit(2)
