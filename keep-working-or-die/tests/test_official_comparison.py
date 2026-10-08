import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('official_comparison', Path(__file__).parents[1] / 'deploy/auth_capture_compare.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.payload = {'authorization': {'from': '0x' + 'ab' * 20, 'to': '0x' + 'cd' * 20,
                                          'value': '10500000', 'validAfter': '0',
                                          'validBefore': '1789472689', 'nonce': '0x' + '01' * 32},
                        'salt': '0x' + '02' * 32, 'signature': '0x' + '03' * 65}

    def test_address_case_is_same_address(self):
        actual = copy.deepcopy(self.payload)
        actual['authorization']['from'] = '0x' + 'AB' * 20
        actual['authorization']['to'] = '0x' + 'CD' * 20
        self.assertEqual(comparison.payload_differences(self.payload, actual), [])

    def test_real_differences_are_identified_and_never_ignored(self):
        for field, replacement in [('from', '0x' + 'ff' * 20), ('value', '1'),
                                   ('value', 10500000), ('validAfter', '1'),
                                   ('validBefore', '1789472690'), ('nonce', '0x' + '99' * 32)]:
            actual = copy.deepcopy(self.payload)
            actual['authorization'][field] = replacement
            with self.subTest(field=field):
                differences = comparison.payload_differences(self.payload, actual)
                self.assertEqual(differences[0]['field'], 'payload.authorization.' + field)
        for field in ('salt', 'signature'):
            actual = copy.deepcopy(self.payload)
            actual[field] = 'changed'
            self.assertTrue(comparison.payload_differences(self.payload, actual))

    def test_missing_and_extra_fields_fail(self):
        actual = copy.deepcopy(self.payload)
        del actual['salt']
        actual['unexpected'] = 'anything'
        self.assertEqual(len(comparison.payload_differences(self.payload, actual)), 2)
