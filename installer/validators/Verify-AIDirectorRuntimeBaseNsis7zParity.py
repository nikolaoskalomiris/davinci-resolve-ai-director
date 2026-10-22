from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def require(cond, msg):
    if not cond:
        raise RuntimeError(msg)


def normalize_rel(value: str) -> str:
    return str(value).replace("\\", "/").lstrip("./").strip("/")


def inventory_rows(path: Path):
    obj = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = obj.get("files") if isinstance(obj, dict) else None
    require(isinstance(rows, list), "Inventory files list missing.")
    out = []
    for row in rows:
        rel = row.get("path") or row.get("relative_path")
        digest = row.get("sha256")
        size = row.get("bytes", row.get("size"))
        if isinstance(rel, str) and isinstance(digest, str) and len(digest) == 64:
            out.append({"path": normalize_rel(rel), "sha256": digest.upper(), "bytes": int(size)})
    expected_count = obj.get("file_count")
    require(isinstance(expected_count, int) and expected_count > 0, "Inventory file_count missing or invalid.")
    dedup = {r["path"].casefold(): r for r in out}
    require(len(dedup) == expected_count, f"Expected {expected_count} inventory files; found {len(dedup)}")
    return list(dedup.values()), expected_count


def run(args, cwd=None, timeout=1800):
    cp = subprocess.run([str(x) for x in args], cwd=str(cwd) if cwd else None,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, encoding="utf-8", errors="replace", timeout=timeout)
    require(cp.returncode == 0, f"Command failed exit={cp.returncode}: {args}\n{cp.stdout[-8000:]}")
    return cp.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", required=True)
    ap.add_argument("--inventory", required=True)
    ap.add_argument("--makensis", required=True)
    ap.add_argument("--nsis7z", required=True)
    ap.add_argument("--expected-archive-sha256")
    args = ap.parse_args()

    archive = Path(args.archive).resolve()
    inventory = Path(args.inventory).resolve()
    makensis = Path(args.makensis).resolve()
    plugin = Path(args.nsis7z).resolve()
    require(archive.is_file(), f"Archive missing: {archive}")
    require(inventory.is_file(), f"Inventory missing: {inventory}")
    require(makensis.is_file(), f"makensis missing: {makensis}")
    require(plugin.is_file(), f"Nsis7z missing: {plugin}")
    if args.expected_archive_sha256:
        require(sha256(archive) == args.expected_archive_sha256.upper(), "Archive hash mismatch.")

    rows, expected_count = inventory_rows(inventory)
    temp = Path(tempfile.mkdtemp(prefix="AI-Director-RuntimeBase-Nsis7z-Parity-"))
    try:
        out = temp / "out"
        nsi = temp / "probe.nsi"
        exe = temp / "probe.exe"
        script = "\n".join([
            "Unicode true",
            "RequestExecutionLevel user",
            "SilentInstall silent",
            "AutoCloseWindow true",
            'Name "AI Director Runtime Base Nsis7z Parity"',
            f'OutFile "{exe}"',
            'InstallDir "$TEMP\\AI-Director-RuntimeBase-Nsis7z-Parity"',
            f'!addplugindir /x86-unicode "{plugin.parent}"',
            "",
            "Section",
            f'  RMDir /r "{out}"',
            f'  CreateDirectory "{out}"',
            f'  SetOutPath "{out}"',
            f'  Nsis7z::Extract "{archive}"',
            "  Pop $R0",
            "  SetOutPath $R0",
            "  SetErrorLevel 0",
            "SectionEnd",
            "",
        ])
        nsi.write_text(script, encoding="utf-8", newline="\n")
        run([makensis, "/V2", nsi], cwd=temp, timeout=120)
        run([exe], cwd=temp, timeout=1800)

        missing = []
        mismatched = []
        for i, row in enumerate(rows, 1):
            p = out / Path(*row["path"].split("/"))
            if not p.is_file():
                missing.append(row["path"])
            elif p.stat().st_size != row["bytes"] or sha256(p) != row["sha256"]:
                mismatched.append(row["path"])
            if i % 1000 == 0 or i == len(rows):
                print(f"NSIS7Z_RUNTIME_BASE_PARITY_PROGRESS={i}/{len(rows)}", flush=True)
        actual_count = sum(1 for p in out.rglob("*") if p.is_file())
        require(actual_count == expected_count, f"Extracted file count={actual_count}; expected={expected_count}")
        require(not missing, f"Nsis7z missing files: {missing[:20]}")
        require(not mismatched, f"Nsis7z mismatched files: {mismatched[:20]}")
        print(f"NSIS7Z_RUNTIME_BASE_FILE_COUNT={expected_count}")
        print("NSIS7Z_RUNTIME_BASE_MISSING_COUNT=0")
        print("NSIS7Z_RUNTIME_BASE_MISMATCH_COUNT=0")
        print("NSIS7Z_RUNTIME_BASE_PARITY=PASS")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    main()
