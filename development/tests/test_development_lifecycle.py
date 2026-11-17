"""Read-only lifecycle regression. Uses the running Python; never builds or prepares versions."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DevelopmentLifecycle(unittest.TestCase):
    def test_checked_in_state_and_version(self):
        for relative in ('build/package/check_state.py', 'build/package/version_control.py'):
            result = subprocess.run([sys.executable, '-B', str(ROOT / relative)],
                                    capture_output=True, text=True, cwd=ROOT)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_prospective_target_keeps_authority(self):
        version = load('aid_version_fixture', 'build/package/version_control.py')
        current, accepted, target = version.validate_current_for_versioning()
        version.validate_manifest_against_tree(current)
        before = version.CURRENT_PATH.read_bytes()
        selected = version.format_semver((accepted[0], accepted[1] + 1, 0))
        payloads = version.prospective_payloads(current, selected)
        prospective = json.loads(payloads['current'])
        self.assertEqual(prospective['live_accepted_authority'], current['live_accepted_authority'])
        self.assertEqual(prospective['state_mode'], 'TARGET_READY')
        self.assertEqual(len(json.loads(payloads['manifest'])['files']), 14)
        self.assertEqual(version.CURRENT_PATH.read_bytes(), before)
        if current['state_mode'] == 'DEVELOPMENT':
            self.assertNotIn('development_source', prospective)
            self.assertEqual(prospective['development_predecessor']['status'], 'UNRELEASED')

    def test_build_refusal_has_no_recovery_or_toolchain_side_effects(self):
        build = load('aid_build_fixture', 'build/package/authoritative_build.py')
        with tempfile.TemporaryDirectory(prefix='aid-development-gate-') as directory:
            state = Path(directory) / 'release-state.json'
            state.write_text(json.dumps({'state_mode': 'DEVELOPMENT'}), encoding='utf-8')
            build.CURRENT_PATH = state
            def forbidden(*args, **kwargs):
                raise AssertionError('Recovery/toolchain/accept/build ran before development gate')
            for name in ('recover_acceptance_if_needed', 'recover_version_preparation_if_needed',
                         'validate_system_toolchain', 'accept_candidate', 'build_once',
                         'prepare_then_build', 'public_source_preflight'):
                setattr(build, name, forbidden)
            previous = sys.argv
            try:
                for args in ([], ['--accept'], ['--accept', '--dry-run'], ['--preflight'], ['--minor']):
                    sys.argv = ['authoritative_build.py', *args]
                    with self.assertRaisesRegex(RuntimeError, 'Unreleased DEVELOPMENT source'):
                        build.main()
                self.assertEqual([p.name for p in Path(directory).iterdir()], ['release-state.json'])
            finally:
                sys.argv = previous

    def test_exact_membership_and_drift_fail_closed(self):
        checker = load('aid_check_fixture', 'build/package/check_state.py')
        current = json.loads(checker.STATE_PATH.read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory(prefix='aid-manifest-gate-') as directory:
            temporary = Path(directory)
            # Minimal copy of app is small; no real settings/credentials/runtime needed.
            import shutil
            shutil.copytree(checker.APP_ROOT, temporary / 'app')
            checker.APP_ROOT = temporary / 'app'
            checker.APP_MANIFEST = temporary / 'manifest.json'
            checker.APP_MANIFEST.write_bytes((ROOT / 'provenance/application/CANONICAL-SOURCE-MANIFEST.json').read_bytes())
            checker.validate_application(current)
            extra = checker.APP_ROOT / 'unexpected.txt'
            extra.write_text('fixture', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'purity'):
                checker.validate_application(current)
            extra.unlink()
            code = checker.APP_ROOT / 'InternetCapability.js'
            code.write_bytes(code.read_bytes() + b'\n')
            with self.assertRaisesRegex(RuntimeError, 'size|hash'):
                checker.validate_application(current)


if __name__ == '__main__':
    unittest.main()
