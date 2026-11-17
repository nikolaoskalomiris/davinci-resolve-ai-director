"""Offline fixtures only. PROVIDER_TEST_ROOT supplies a retained pinned payload.

Writes only unique Downloads fixture directories (retained for diagnosis). No
makensis/build/install/network/credentials. The actual generator and validators
run; ONLY the large accepted base archive argument gate is mocked in the render
fixture, since no archive is built or extracted. That gate is not tested here.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
PS = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
HELPER = ROOT / 'runtime/support/Install-AIDirectorInternetProvider-v1.ps1'
PAYLOAD = os.environ.get('PROVIDER_TEST_ROOT')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProviderInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = Path(tempfile.mkdtemp(prefix='AI-Director-ProviderInstaller-Test-', dir=Path.home() / 'Downloads'))
        print('RETAINED_FIXTURE=' + str(cls.work), flush=True)

    def run_helper(self, payload, product, success):
        result = subprocess.run([str(PS), '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-File', str(HELPER), '-PayloadRoot', str(payload), '-ProductRoot', str(product)],
                                capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_helper_syntax_and_bound_hash(self):
        parser = self.work / 'parse.ps1'
        parser.write_text('param([string]$Path)\n$e=$null\n[void][System.Management.Automation.Language.Parser]::ParseFile($Path,[ref]$null,[ref]$e)\nif ($e.Count) { $e; exit 1 }\n', encoding='utf-8')
        cp = subprocess.run([str(PS), '-NoProfile', '-NonInteractive', '-File', str(parser), str(HELPER)], capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        policy = load('provider_installer_policy_hash_test', ROOT / 'installer/successor_policy.py')
        self.assertEqual(digest(HELPER).upper(), policy.EXPECTED_PROVIDER_HELPER_SHA256)

    @unittest.skipUnless(PAYLOAD, 'Set PROVIDER_TEST_ROOT to explicit pinned offline payload')
    def test_seed_retain_divergence_and_bad_inputs(self):
        payload = Path(PAYLOAD)
        product = self.work / 'product'
        seeded = self.run_helper(payload, product, True)
        self.assertEqual(seeded['status'], 'VERIFIED_SEEDED')
        destination = Path(seeded['destination'])
        cache = sorted(destination.glob('**/middleware/cache/*'))
        self.assertEqual(len([p for p in cache if p.is_file()]), 3)
        before = {p.relative_to(destination).as_posix(): digest(p) for p in destination.rglob('*') if p.is_file()}
        retained = self.run_helper(payload, product, True)
        self.assertEqual(retained['status'], 'VERIFIED_RETAINED')
        self.assertEqual(before, {p.relative_to(destination).as_posix(): digest(p) for p in destination.rglob('*') if p.is_file()})
        entry = destination / 'dist/index.js'
        entry.write_bytes(b'divergent-active-runtime-fixture')
        self.run_helper(payload, product, False)
        self.assertEqual(entry.read_bytes(), b'divergent-active-runtime-fixture')
        self.assertFalse(list(destination.parent.glob('2.1.4.aidir-new-*')))

        bad = self.work / 'bad-payload'
        shutil.copytree(payload, bad)
        target = self.work / 'bad-product'
        manifest = bad / 'PROVIDER-MANIFEST.json'
        original = manifest.read_bytes()
        manifest.write_bytes(original + b' ')
        self.run_helper(bad, target, False)
        manifest.write_bytes(original)
        extra = bad / 'unexpected.js'
        extra.write_bytes(b'extra')
        self.run_helper(bad, target, False)
        extra.unlink()
        index = bad / 'dist/index.js'
        data = index.read_bytes()
        index.unlink()
        self.run_helper(bad, target, False)
        index.write_bytes(b'x' * len(data))
        self.run_helper(bad, target, False)
        index.unlink()
        os.link(payload / 'dist/index.js', index)
        try:
            self.run_helper(bad, target, False)
        finally:
            index.unlink()  # removes only this fixture-owned hardlink
        index.write_bytes(data)
        junction = bad / 'untrusted-junction'
        cp = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(junction), str(payload)], capture_output=True, text=True)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.run_helper(bad, target, False)
        self.assertFalse(target.exists(), 'Invalid payload must fail before destination mutation')

    @unittest.skipUnless(PAYLOAD, 'Set PROVIDER_TEST_ROOT to explicit pinned offline payload')
    def test_actual_generator_make_validate_and_anchor_failures(self):
        fixture = self.work / 'builder'
        fixture.mkdir()
        (fixture / 'stack-fixture.7z').write_bytes(b'not-an-archive-render-only')
        (fixture / 'child-fixture.exe').write_bytes(b'not-an-executable-render-only')
        for directory in ('installer', 'runtime', 'provenance/runtime/providers'):
            source = ROOT / directory
            shutil.copytree(source, fixture / directory)
        staged = fixture / '_inputs/Providers/brave-search/2.1.4'
        shutil.copytree(Path(PAYLOAD), staged)
        api = load('provider_actual_installer_fixture', fixture / 'installer/build_installer.py')
        policy = api._aid_successor_policy
        # Render-only stand-ins; no archive extraction, compiler or installer runs.
        for name in ('base-fixture.7z', 'stack-fixture.7z', 'child-fixture.exe'):
            (fixture / name).write_bytes(b'SYNTHETIC-RENDER-ONLY')
        kwargs = dict(runtime_stack_archive=fixture / 'stack-fixture.7z',
                      runtime_stack_marker='AIDirector/Common/RUNTIME-STACK-MANIFEST.json',
                      runtime_stack_required_targets=['AIDirector/Common/fixture.dll'],
                      runtime_stack_partial_roots=['AIDirector/Common'])
        # Authoritative build always embeds the optional Integration installer;
        # choosing not to install it is a runtime selection, not absent embedding.
        # Legacy render with no child has pre-existing unbound shortcut local.
        for optional in (True,):
            options = dict(kwargs)
            if optional:
                options.update(resolve_integration_setup=fixture / 'child-fixture.exe', resolve_integration_version='0.3.27')
            with patch.object(policy, '_assert_accepted_runtime_base'):
                text = api.make_nsis_include(fixture / 'base-fixture.7z', ROOT / 'runtime/support/Generate-AIDirectorRuntimePaths.ps1', **options)
            api.validate_nsis_include(text, **options)
            (self.work / ('render-with-integration.nsh' if optional else 'render-no-integration.nsh')).write_text(text, encoding='utf-8')
            start = text.index('aid_seed_not_required:\n')
            provider = text.index('File /oname=Install-AIDirectorInternetProvider-v1.ps1')
            self.assertGreater(provider, start)
            self.assertLess(provider, text.index('Stage 3 of 5'))
            self.assertNotIn('aidSeedCommonRuntime', text)
            for broken in (text.replace('    StrCmp $R6 "0" aid_provider_ok 0', ''),
                           text.replace('aid_provider_ok:', 'aid_provider_missing:'),
                           text.replace('File /oname=PROVIDER-MANIFEST.json ', 'File /oname=OTHER.json ', 1),
                           text.replace('File /oname=index.js ', 'File /oname=altered.js ', 1)):
                with self.assertRaises(RuntimeError):
                    api.validate_nsis_include(broken, **options)
        for broken in ('', 'aid_seed_not_required:\naid_seed_not_required:\n'):
            with self.assertRaises(RuntimeError):
                policy._transform_provider_assets(broken, fixture)
        # Existing generator defect is explicitly recorded, not patched here.
        # The provider hook itself has no optional-integration condition.
        with patch.object(policy, '_assert_accepted_runtime_base'):
            with self.assertRaisesRegex(UnboundLocalError, 'desktop_shortcut_install'):
                api.make_nsis_include(fixture / 'base-fixture.7z', ROOT / 'runtime/support/Generate-AIDirectorRuntimePaths.ps1', **kwargs)
        # Missing staged input must stop generation, not silently omit provider.
        staged.rename(staged.with_name('retained-input'))
        with self.assertRaises((RuntimeError, ValueError, OSError)):
            policy._provider_nsis_block(fixture)


if __name__ == '__main__':
    unittest.main(verbosity=2)
