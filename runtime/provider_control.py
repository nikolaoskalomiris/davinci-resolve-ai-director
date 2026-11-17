"""Pinned Brave provider validation and OFFLINE staging; never acquisition or execution.

Caller must keep input/provenance/output-parent trees quiescent during operation.
This is not a sandbox against concurrent hostile filesystem mutation. Promotion
uses Windows rename's no-replace semantics; other OSes may validate, not stage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile

DEFAULT_PROVENANCE_ROOT = Path(__file__).resolve().parents[1] / 'provenance/runtime/providers/brave-search/2.1.4'
METADATA_INDEX_SHA256 = '10aa8a310b71a597a4438a44c311814af9e9059badc26ab2d9e3bee9a9464e53'
INVENTORY_SHA256 = 'f8bd1c72fce849e56737258cd2396b80b227e30adfba00574b485bfdd49ebebe'
MANIFEST_SHA256 = 'c30427caa6ddf5c71d096645fd9a78155c8dd29e529f95221dc2015b20f1773b'
CORE_FILE_COUNT = 3589
CORE_BYTES = 15914748
# Retained npm-prune empty scope directories, independently inspected; no exclusions.
EMPTY_DIRECTORIES = ('node_modules/@esbuild', 'node_modules/@nodelib', 'node_modules/@types')
IDENTITY = {'schema_version': 1, 'provider': 'brave-search', 'version': '2.1.4',
            'source_commit': '8bcb302657b0f072612c2f3e53182ff17912013c',
            'source_tree': '2c6b964cb59aa51e3b3643325066fbac05f19440', 'entrypoint': 'dist/index.js'}
GAP = 'Public acquisition GAP: no reviewed public bundle/reconstruction contract; explicit offline --input required. No download or reconstruction is implemented.'


class ProviderError(ValueError):
    """A fail-closed provider contract or filesystem gate failed."""


def _require(ok, message):
    if not ok:
        raise ProviderError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _safe_path(value):
    _require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9@_.+\-/]+', value), 'Unsafe inventory path')
    parts = value.split('/')
    for part in parts:
        _require(part not in ('', '.', '..') and not part.endswith('.') and
                 part.split('.')[0].upper() not in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))},
                 'Unsafe Windows path component')
    return value


def _checked_stat(path):
    info = path.lstat()
    _require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, 'st_file_attributes', 0) & 0x400),
             f'Links/reparse points forbidden: {path}')
    _require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), f'Special file forbidden: {path}')
    if stat.S_ISREG(info.st_mode):
        _require(info.st_nlink == 1, f'Hard links forbidden: {path}')
    return info


def _absolute(path):
    path = Path(os.path.abspath(os.fspath(path)))
    for item in [*reversed(path.parents), path]:
        _checked_stat(item)
    return path


def _read(path):
    before = _checked_stat(path)
    _require(stat.S_ISREG(before.st_mode), f'Not regular: {path}')
    with path.open('rb') as handle:
        opened = os.fstat(handle.fileno())
        _require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), 'File changed while opening')
        data = handle.read()
        after = os.fstat(handle.fileno())
    final = _checked_stat(path)
    _require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) ==
             (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns), 'File changed while reading')
    return data


def _walk(root):
    files, directories, folded = {}, set(), set()
    def visit(directory):
        for entry in directory.iterdir():
            rel = _safe_path(entry.relative_to(root).as_posix())
            key = rel.casefold()
            _require(key not in folded, f'Case collision: {rel}')
            folded.add(key)
            info = _checked_stat(entry)
            if stat.S_ISDIR(info.st_mode):
                directories.add(rel)
                visit(entry)
            else:
                files[rel] = entry
    _require(stat.S_ISDIR(_checked_stat(root).st_mode), 'Root must be directory')
    visit(root)
    return files, directories


def _parents(paths):
    return {str(parent) for name in paths for parent in Path(name).parents if str(parent) != '.'}


def _rows(raw, size_key='size'):
    rows = [json.loads(line) for line in raw.decode('utf-8').splitlines()]
    return _validate_rows(rows, size_key)


def _validate_rows(rows, size_key):
    _require(isinstance(rows, list) and rows, 'Missing inventory rows')
    result, folded, nodes = {}, set(), {}
    for row in rows:
        _require(isinstance(row, dict) and set(row) == {'path', size_key, 'sha256'}, 'Invalid inventory fields')
        name = _safe_path(row['path'])
        _require(name.casefold() not in folded, 'Duplicate/case-colliding inventory path')
        folded.add(name.casefold())
        _require(type(row[size_key]) is int and row[size_key] >= 0 and isinstance(row['sha256'], str) and
                 re.fullmatch('[a-fA-F0-9]{64}', row['sha256']), 'Invalid size/hash')
        result[name] = {'path': name, 'size': row[size_key], 'sha256': row['sha256'].lower()}
        for parent in [Path(name), *Path(name).parents]:
            text = parent.as_posix()
            _require(nodes.setdefault(text.casefold(), text) == text, 'Case-colliding inventory directory')
    _require(not (set(result) & {x.replace('\\', '/') for x in _parents(result)}), 'File/directory inventory collision')
    return result


def _canonical(rows):
    return ''.join(json.dumps(rows[name], separators=(',', ':')) + '\n' for name in sorted(rows)).encode('utf-8')


def _verify_set(root, rows, empty_directories=()):
    files, directories = _walk(root)
    _require(set(files) == set(rows), f'Full file set mismatch: missing={sorted(set(rows)-set(files))[:4]}, extra={sorted(set(files)-set(rows))[:4]}')
    _require(directories == {x.replace('\\', '/') for x in _parents(rows)} | set(empty_directories), 'Unexpected/missing directories')
    for name, row in rows.items():
        data = _read(files[name])
        _require(len(data) == row['size'] and _sha(data) == row['sha256'], f'Size/hash drift: {name}')


def _load_contract(provenance_root):
    root = _absolute(provenance_root)
    raw = _read(root / 'METADATA-FILES.jsonl')
    _require(_sha(raw) == METADATA_INDEX_SHA256, 'Unreviewed metadata index')
    rows = _rows(raw)
    rows['METADATA-FILES.jsonl'] = {'path': 'METADATA-FILES.jsonl', 'size': len(raw), 'sha256': METADATA_INDEX_SHA256}
    _verify_set(root, rows)
    contract = json.loads(_read(root / 'CONTRACT.json'))
    _require(all(contract.get(k) == v for k, v in IDENTITY.items()), 'Unreviewed provider identity')
    inventory_raw = _read(root / 'core-files.jsonl')
    inventory = _rows(inventory_raw)
    _require(len(inventory) == CORE_FILE_COUNT and sum(x['size'] for x in inventory.values()) == CORE_BYTES and
             _sha(inventory_raw) == INVENTORY_SHA256 and _canonical(inventory) == inventory_raw, 'Unreviewed core inventory')
    manifest_raw = _read(root / 'PROVIDER-MANIFEST.json')
    _require(_sha(manifest_raw) == MANIFEST_SHA256, 'Unreviewed manifest bytes')
    manifest = json.loads(manifest_raw)
    _require(all(manifest.get(k) == v for k, v in IDENTITY.items()), 'Manifest identity mismatch')
    _require(_validate_rows(manifest.get('files'), 'bytes') == inventory, 'Manifest inventory mismatch')
    _require({'dist/index.js', 'package.json'} <= set(inventory), 'Missing entry/package')
    inventory['PROVIDER-MANIFEST.json'] = {'path': 'PROVIDER-MANIFEST.json', 'size': len(manifest_raw), 'sha256': MANIFEST_SHA256}
    return inventory, contract


def validate_provider(root, provenance_root=DEFAULT_PROVENANCE_ROOT):
    """Validate exact pinned bytes/full set, including the manifest. No mutation."""
    _require(root is not None, GAP)
    rows, contract = _load_contract(provenance_root)
    root = _absolute(root)
    _verify_set(root, rows, EMPTY_DIRECTORIES)
    return {'evidence_state': 'VERIFIED', 'scope': 'OFFLINE_PROVIDER_BYTES_ONLY',
            'core_files': CORE_FILE_COUNT, 'runtime_files': len(rows), 'core_bytes': CORE_BYTES,
            'inventory_sha256': INVENTORY_SHA256, 'manifest_sha256': MANIFEST_SHA256,
            'public_acquisition': contract['public_acquisition']}


def stage_provider(input_root, output_root):
    """Validate, copy all files to owned sibling, revalidate, rename to fresh output.

    Never merge, replace an existing destination, mutate input, or clean anything
    except the temporary directory created by this operation. No runtime install.
    """
    _require(input_root is not None, GAP)
    _require(output_root is not None, 'Explicit fresh --output required')
    _require(os.name == 'nt', 'Staging requires Windows no-replace directory rename semantics')
    source = _absolute(input_root)
    output = Path(os.path.abspath(os.fspath(output_root)))
    parent = _absolute(output.parent)
    _safe_path(output.name)
    _require(not os.path.lexists(output), 'Output already exists; refusing replacement')
    _require(not output.is_relative_to(source) and not source.is_relative_to(output), 'Input/output overlap forbidden')
    result = validate_provider(source)
    files, directories = _walk(source)
    owned = Path(tempfile.mkdtemp(prefix='.provider-stage-', dir=parent))
    owned_identity = owned.stat()
    payload = owned / 'payload'
    try:
        payload.mkdir()
        for name in sorted(directories):
            (payload / name).mkdir(parents=True, exist_ok=True)
        for name in sorted(files):
            target = payload / name
            target.parent.mkdir(parents=True, exist_ok=True)
            data = _read(files[name])
            with target.open('xb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        validate_provider(payload)
        _absolute(parent)
        _require(not os.path.lexists(output), 'Output appeared during staging')
        os.rename(payload, output)  # Windows fails if destination exists; never os.replace.
        return dict(result, output=str(output), operation='OFFLINE_STAGE')
    finally:
        current = _checked_stat(owned)
        _require((current.st_dev, current.st_ino) == (owned_identity.st_dev, owned_identity.st_ino), 'Owned staging identity changed; retained for inspection')
        _walk(owned)  # Refuse cleanup if a link/reparse/special file appeared.
        shutil.rmtree(owned)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=GAP)
    parser.add_argument('action', choices=('validate', 'stage'))
    parser.add_argument('--input', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    try:
        _require(args.input is not None, GAP)
        _require(args.action == 'stage' or args.output is None, '--output only applies to stage')
        result = stage_provider(args.input, args.output) if args.action == 'stage' else validate_provider(args.input)
        print(json.dumps(result, indent=2))
        return 0
    except (ProviderError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'evidence_state': 'UNVERIFIED', 'error': str(exc), 'public_acquisition_gap': GAP}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
