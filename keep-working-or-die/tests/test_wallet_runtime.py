import unittest

from test_deployment import module


class WalletRuntimeTests(unittest.TestCase):
    def test_release_selection_stays_on_lts_24_and_orders_numerically(self):
        installer = module('install_wallet_runtime')
        rows = [{'version': v, 'lts': lts} for v, lts in (
            ('v25.0.0', True), ('v24.9.0', 'Krypton'), ('v24.10.0', 'Krypton'),
            ('v24.99.0', False), ('v24.100.0/evil', True))]
        self.assertEqual(installer.select_release(rows), 'v24.10.0')
        with self.assertRaises(ValueError):
            installer.select_release([{'version': 'v22.23.2', 'lts': True}])

    def test_checksum_requires_exact_unique_filename(self):
        installer = module('install_wallet_runtime')
        name = 'node-v24.10.0-linux-x64.tar.xz'
        line = 'a' * 64 + '  ' + name
        self.assertEqual(installer.expected_hash(line, name), 'a' * 64)
        for text in (line + '.sig', line + '\n' + line, 'bad  ' + name):
            with self.subTest(text=text), self.assertRaises(ValueError):
                installer.expected_hash(text, name)
