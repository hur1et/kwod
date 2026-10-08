import os
from pathlib import Path
import tempfile
import unittest

from test_deployment import module


class LocalWalletSetupTests(unittest.TestCase):
    def setUp(self):
        self.wallet = module('setup_local_wallet')

    def test_repeated_write_preserves_original_and_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity = root / 'identity.json'
            self.wallet.create_once(identity, b'original-test-data')
            with self.assertRaises(FileExistsError):
                self.wallet.create_once(identity, b'replacement-test-data')
            self.assertEqual(identity.read_bytes(), b'original-test-data')
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['identity.json'])
            self.assertEqual(identity.stat().st_nlink, 1)

    def test_hard_link_and_oversized_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'secret'
            self.wallet.create_once(path, b'test-data')
            alias = root / 'alias'
            os.link(path, alias)
            with self.assertRaises(ValueError):
                self.wallet.secure_read(path)
            alias.unlink()
            path.write_bytes(b'x' * 65537)
            with self.assertRaises(ValueError):
                self.wallet.secure_read(path, os.getuid() if os.name == 'posix' else None)

    def test_failed_publication_preserves_existing_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / 'identity.json'
            target.mkdir()
            with self.assertRaises(OSError):
                self.wallet.create_once(target, b'test-data')
            self.assertTrue(target.is_dir())
            self.assertEqual(list(root.iterdir()), [target])
