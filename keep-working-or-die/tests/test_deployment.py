import importlib.util
import json
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'deploy' / (name + '.py'))
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class DeploymentTests(unittest.TestCase):
    def test_bundle_excludes_credentials_and_runtime_data(self):
        builder = module('bundle')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / 'source'
            source.mkdir()
            for name in builder.ROOT_FILES:
                (source / name).write_text('fixture')
            for name in ('src/kwod/ok.py', 'src/kwod/.env', '.env', 'private/state.sqlite',
                         'workspace/customer.txt', 'deploy/key.pem', '.ssh/id_ed25519', 'reports/private.txt'):
                path = source / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('SECRET' if not name.endswith('.py') else '# code')
            metadata = builder.build(source, root / 'release.tar.gz')
            with tarfile.open(metadata['bundle']) as archive:
                names = archive.getnames()
                self.assertIn('src/kwod/ok.py', names)
                self.assertIn('bundle-manifest.json', names)
                self.assertNotIn('.env', names)
                self.assertNotIn('src/kwod/.env', names)
                self.assertFalse(any('private/' in x or 'workspace/' in x or '.ssh/' in x for x in names))

    def test_real_source_manifest_detects_tampering(self):
        builder, installer = module('bundle'), module('install_ubuntu')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            metadata = builder.build(ROOT, root / 'release.tar.gz')
            unpacked = root / 'unpacked'
            unpacked.mkdir()
            with tarfile.open(metadata['bundle']) as archive:
                archive.extractall(unpacked, filter='data')
            manifest = installer.verify_source(unpacked)
            self.assertIn('src/kwod/static/index.html', manifest)
            self.assertIn('deploy/kwod-work-monitor.timer', manifest)
            self.assertIn('src/kwod/work_monitor_fixture.py', manifest)
            (unpacked / 'src/kwod/cli.py').write_text('changed')
            with self.assertRaises(ValueError):
                installer.verify_source(unpacked)

    def test_manifest_traversal_is_rejected(self):
        installer = module('install_ubuntu')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'bundle-manifest.json').write_text(json.dumps({'../secret': 'abc'}))
            with self.assertRaises(ValueError):
                installer.verify_source(root)
