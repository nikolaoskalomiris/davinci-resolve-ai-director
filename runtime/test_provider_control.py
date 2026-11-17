"""Offline regressions. Synthetic pins are patched ONLY in this test module.

Run: python -B runtime/test_provider_control.py
Actual tree: python -B runtime/test_provider_control.py --actual-input PATH --actual-output FRESH_PATH
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

spec = importlib.util.spec_from_file_location('provider_control', Path(__file__).with_name('provider_control.py'))
pc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pc)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='provider-tests-', dir=Path(__file__).resolve().parents[2])
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'input'
        self.provenance = self.base / 'provenance'
        self.root.mkdir()
        self.provenance.mkdir()
        contents = {'dist/index.js': b'fixture', 'package.json': b'{"version":"2.1.4"}',
                    'node_modules/hono/dist/middleware/cache/index.js': b'cache',
                    'Cache/keep': b'Cache', 'Logs/keep': b'Logs', 'Updates/keep': b'Updates'}
        for name, data in contents.items():
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        self.rows = {name: {'path': name, 'size': len(data), 'sha256': pc._sha(data)} for name, data in contents.items()}
        self.inventory = pc._canonical(self.rows)
        manifest = dict(pc.IDENTITY, files=[{'path': name, 'bytes': row['size'], 'sha256': row['sha256']} for name, row in sorted(self.rows.items())])
        self.manifest = (json.dumps(manifest, indent=2) + '\n').encode()
        (self.root / 'PROVIDER-MANIFEST.json').write_bytes(self.manifest)
        (self.provenance / 'PROVIDER-MANIFEST.json').write_bytes(self.manifest)
        (self.provenance / 'core-files.jsonl').write_bytes(self.inventory)
        (self.provenance / 'CONTRACT.json').write_text(json.dumps(dict(pc.IDENTITY, public_acquisition={'status': 'GAP'})), encoding='utf-8')
        index = pc._canonical({p.name: {'path': p.name, 'size': len(d := p.read_bytes()), 'sha256': pc._sha(d)} for p in self.provenance.iterdir()})
        (self.provenance / 'METADATA-FILES.jsonl').write_bytes(index)
        stack = self.enterContext(ExitStack())
        for name, value in {'METADATA_INDEX_SHA256': pc._sha(index), 'INVENTORY_SHA256': pc._sha(self.inventory),
                            'MANIFEST_SHA256': pc._sha(self.manifest), 'CORE_FILE_COUNT': len(self.rows),
                            'CORE_BYTES': sum(r['size'] for r in self.rows.values()), 'EMPTY_DIRECTORIES': ()}.items():
            stack.enter_context(mock.patch.object(pc, name, value))
        # Stage's API remains two arguments; inject fixture provenance, not bypass validation.
        original = pc.validate_provider
        stack.enter_context(mock.patch.object(pc, 'validate_provider', side_effect=lambda root, provenance_root=self.provenance: original(root, provenance_root)))

    def validate(self):
        return pc.validate_provider(self.root)

    def test_valid_copy_no_basename_exclusions(self):
        self.validate()
        out = self.base / 'output'
        pc.stage_provider(self.root, out)
        self.assertEqual(pc._walk(out)[0].keys(), pc._walk(self.root)[0].keys())
        self.assertEqual((out / 'Cache/keep').read_bytes(), b'Cache')
        self.assertEqual(list(self.base.glob('.provider-stage-*')), [])

    def test_missing_file(self):
        (self.root / 'dist/index.js').unlink()
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_extra_file(self):
        (self.root / 'extra').write_bytes(b'x')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_empty_directory(self):
        (self.root / 'extra').mkdir()
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_same_size_hash_drift(self):
        (self.root / 'dist/index.js').write_bytes(b'Fixture')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_size_drift(self):
        (self.root / 'dist/index.js').write_bytes(b'x')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_manifest_whitespace_hash_bound(self):
        (self.root / 'PROVIDER-MANIFEST.json').write_bytes(self.manifest + b' ')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_code_and_manifest_together_fail(self):
        (self.root / 'dist/index.js').write_bytes(b'changed')
        manifest = json.loads(self.manifest)
        manifest['files'][0]['sha256'] = pc._sha(b'changed')
        (self.root / 'PROVIDER-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_metadata_tamper(self):
        (self.provenance / 'CONTRACT.json').write_bytes(b'{}')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_metadata_index_tamper(self):
        (self.provenance / 'METADATA-FILES.jsonl').write_bytes(b'{}\n')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_rebound_metadata_does_not_rebind_core(self):
        manifest = json.loads(self.manifest)
        manifest['source_commit'] = '0' * 40
        (self.provenance / 'PROVIDER-MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
        index = pc._canonical({p.name: {'path': p.name, 'size': len(d := p.read_bytes()), 'sha256': pc._sha(d)} for p in self.provenance.iterdir() if p.name != 'METADATA-FILES.jsonl'})
        (self.provenance / 'METADATA-FILES.jsonl').write_bytes(index)
        with mock.patch.object(pc, 'METADATA_INDEX_SHA256', pc._sha(index)):
            with self.assertRaises(pc.ProviderError): self.validate()

    def test_unsafe_rows(self):
        for name in ['../escape', '/abs', 'C:/abs', 'a\\b', 'a//b', './x', 'a/../x', 'a.', 'a /x', 'a:stream', 'NUL', 'COM1.txt', 'a\n']:
            with self.subTest(name=name), self.assertRaises(pc.ProviderError):
                pc._validate_rows([{'path': name, 'size': 0, 'sha256': '0'*64}], 'size')

    def test_duplicate_case_directory_collision(self):
        for names in [('a', 'a'), ('a', 'A'), ('Dir/a', 'dir/b'), ('a', 'a/b')]:
            with self.subTest(names=names), self.assertRaises(pc.ProviderError):
                pc._validate_rows([{'path': n, 'size': 0, 'sha256': '0'*64} for n in names], 'size')

    def test_invalid_size_hash(self):
        for size, sha in [(True, '0'*64), (-1, '0'*64), (1.0, '0'*64), (0, 'no')]:
            with self.subTest(size=size, sha=sha), self.assertRaises(pc.ProviderError):
                pc._validate_rows([{'path': 'a', 'size': size, 'sha256': sha}], 'size')

    def test_actual_case_spelling_drift(self):
        p = self.root / 'dist/index.js'
        p.rename(self.root / 'dist/Index.js')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_hardlink(self):
        os.link(self.root / 'dist/index.js', self.base / 'outside')
        with self.assertRaises(pc.ProviderError): self.validate()

    def test_junction_and_ancestor_reparse(self):
        target = self.base / 'outside'
        target.mkdir()
        junction = self.root / 'escape'
        process = subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(junction), str(target)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        try:
            with self.assertRaises(pc.ProviderError): self.validate()
            with self.assertRaises(pc.ProviderError): pc._absolute(junction)
        finally:
            os.rmdir(junction)
        self.assertTrue(target.is_dir())

    def test_fake_special_stat_rejected(self):
        fake = mock.Mock(st_mode=0o010000, st_file_attributes=0)
        p = mock.Mock()
        p.lstat.return_value = fake
        with self.assertRaises(pc.ProviderError): pc._checked_stat(p)

    def test_missing_input(self):
        with self.assertRaisesRegex(pc.ProviderError, 'GAP'): pc.stage_provider(None, self.base / 'out')
        with self.assertRaises(FileNotFoundError): pc.validate_provider(self.base / 'missing')

    def test_existing_output_untouched(self):
        out = self.base / 'out'
        out.mkdir()
        (out / 'sentinel').write_bytes(b'keep')
        with self.assertRaises(pc.ProviderError): pc.stage_provider(self.root, out)
        self.assertEqual((out / 'sentinel').read_bytes(), b'keep')
        self.assertEqual(list(self.base.glob('.provider-stage-*')), [])

    def test_overlap(self):
        with self.assertRaises(pc.ProviderError): pc.stage_provider(self.root, self.root / 'out')

    def test_copy_failure_cleanup(self):
        original = pc._read
        calls = 0
        def failing(path):
            nonlocal calls
            if path == self.root / 'dist/index.js':
                calls += 1
                if calls == 2: raise OSError('injected copy failure')
            return original(path)
        with mock.patch.object(pc, '_read', side_effect=failing):
            with self.assertRaisesRegex(OSError, 'injected'): pc.stage_provider(self.root, self.base / 'out')
        self.assertFalse((self.base / 'out').exists())
        self.assertEqual(list(self.base.glob('.provider-stage-*')), [])
        self.validate()

    def test_promotion_failure_cleanup(self):
        with mock.patch.object(pc.os, 'rename', side_effect=OSError('promotion failure')):
            with self.assertRaises(OSError): pc.stage_provider(self.root, self.base / 'out')
        self.assertFalse((self.base / 'out').exists())
        self.assertEqual(list(self.base.glob('.provider-stage-*')), [])

    def test_destination_appears_not_replaced(self):
        out = self.base / 'out'
        original = pc.os.rename
        def race(src, dst):
            out.mkdir()
            (out / 'sentinel').write_bytes(b'keep')
            return original(src, dst)
        with mock.patch.object(pc.os, 'rename', side_effect=race):
            with self.assertRaises(OSError): pc.stage_provider(self.root, out)
        self.assertEqual((out / 'sentinel').read_bytes(), b'keep')
        self.assertEqual(list(self.base.glob('.provider-stage-*')), [])

    def test_staged_corruption_fails_before_promotion(self):
        original = pc.validate_provider
        def corrupt(root):
            if Path(root).name == 'payload':
                (Path(root) / 'dist/index.js').write_bytes(b'tamper')
            return original(root)
        with mock.patch.object(pc, 'validate_provider', side_effect=corrupt):
            with self.assertRaises(pc.ProviderError): pc.stage_provider(self.root, self.base / 'out')
        self.assertFalse((self.base / 'out').exists())
        self.assertEqual(list(self.base.glob('.provider-stage-*')), [])
        self.validate()

    def test_unrelated_staging_named_directory_preserved(self):
        other = self.base / '.provider-stage-not-owned'
        other.mkdir()
        (other / 'sentinel').write_bytes(b'keep')
        with mock.patch.object(pc.os, 'rename', side_effect=OSError('promotion failure')):
            with self.assertRaises(OSError): pc.stage_provider(self.root, self.base / 'out')
        self.assertEqual((other / 'sentinel').read_bytes(), b'keep')
        self.assertEqual(list(self.base.glob('.provider-stage-*')), [other])

    def test_cli_missing_input_reports_gap(self):
        with mock.patch('sys.stdout') as output:
            self.assertEqual(pc.main(['stage', '--output', str(self.base / 'out')]), 1)
        self.assertIn('GAP', output.write.call_args_list[0].args[0])
        self.assertFalse((self.base / 'out').exists())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--actual-input', type=Path)
    parser.add_argument('--actual-output', type=Path)
    args = parser.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProviderTests))
    if not result.wasSuccessful(): return 1
    if args.actual_input:
        if not args.actual_output: parser.error('--actual-output required for actual tree test')
        before = pc.validate_provider(args.actual_input)
        staged = pc.stage_provider(args.actual_input, args.actual_output)
        after = pc.validate_provider(args.actual_input)
        output = pc.validate_provider(args.actual_output)
        assert before == after == output
        files = pc._walk(args.actual_output)[0]
        cache = sorted(name for name in files if '/middleware/cache/' in name)
        assert len(cache) == 3, cache
        print(json.dumps({'actual_tree': staged, 'candidate_pre_post_equal': True, 'hono_cache_files': cache}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
