import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest

from kwod.payments import CHAIN_ID, USDC, Journal, PaymentError, transaction


def request(**changes):
    args = {'request_id': 'order_1', 'asset': 'USDC', 'recipient': '0x' + '12' * 20,
            'amount_units': '1234567', 'nonce': 7, 'gas': 100000,
            'max_fee_per_gas': 100, 'max_priority_fee_per_gas': 1}
    args.update(changes)
    return {'method': 'sign_transfer', 'arguments': args}


class TransactionTests(unittest.TestCase):
    def test_usdc_encoding_cannot_be_changed_to_approval_or_other_chain(self):
        tx = transaction(request()['arguments'])
        self.assertEqual(tx['chainId'], CHAIN_ID)
        self.assertEqual(tx['to'], USDC)
        self.assertEqual(tx['value'], 0)
        self.assertEqual(tx['data'], '0xa9059cbb' + ('12' * 20).zfill(64) + format(1234567, '064x'))
        for name, value in [('data', '0x095ea7b3'), ('chainId', 1), ('rpc_url', 'http://192.168.0.1')]:
            with self.subTest(name=name), self.assertRaises(PaymentError):
                transaction(request(**{name: value})['arguments'])

    def test_eth_is_plain_value_transfer(self):
        tx = transaction(request(asset='ETH', amount_units='1000000000000000')['arguments'])
        self.assertEqual(tx['value'], 1000000000000000)
        self.assertEqual(tx['data'], '0x')
        self.assertEqual(tx['to'], '0x' + '12' * 20)

    def test_rejects_ambiguous_numbers_and_invalid_addresses(self):
        for changes in ({'nonce': True}, {'nonce': -1}, {'nonce': 2**63},
                        {'gas': 21000.0}, {'gas': 1}, {'max_priority_fee_per_gas': 101},
                        {'amount_units': '1.5'}, {'amount_units': '01'}, {'amount_units': '1e6'},
                        {'amount_units': '0'}, {'amount_units': str(2**256)},
                        {'recipient': '0x' + '00' * 20}, {'recipient': 'alice.eth'},
                        {'asset': 'USDbC'}, {'request_id': '../key'}):
            with self.subTest(changes=changes), self.assertRaises(PaymentError):
                transaction(request(**changes)['arguments'])


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'journal.sqlite'
        self.calls = []
        self.journal = Journal(self.path, 'fixture-address', self.sign, enabled=True)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def sign(self, tx):
        self.calls.append(copy.deepcopy(tx))
        return {'transaction_hash': 'fixture-hash', 'raw_transaction': 'fixture-bytes'}

    def test_retry_after_restart_returns_identical_bytes_without_signing_again(self):
        result = self.journal.handle(request())
        self.journal.close()
        self.journal = Journal(self.path, 'fixture-address', self.sign, enabled=True)
        self.assertEqual(self.journal.handle(request()), result)
        self.assertEqual(len(self.calls), 1)

    def test_same_id_changed_amount_and_new_id_same_nonce_are_rejected(self):
        self.journal.handle(request())
        for changes in ({'amount_units': '2'}, {'request_id': 'order_2'}):
            with self.subTest(changes=changes), self.assertRaises(PaymentError):
                self.journal.handle(request(**changes))
        self.assertEqual(len(self.calls), 1)

    def test_observation_mode_never_invokes_signing(self):
        self.journal.enabled = False
        with self.assertRaisesRegex(PaymentError, 'signing_disabled'):
            self.journal.handle(request())
        preview = request()
        preview['method'] = 'preview_transfer'
        self.assertFalse(self.journal.handle(preview)['signed'])
        self.assertEqual(self.calls, [])
        status = self.journal.handle({'method': 'status', 'arguments': {}})
        self.assertFalse(status['signing_enabled'])
        self.assertFalse(status['broadcast_enabled'])
        self.assertNotIn('balance', status)

    def test_sign_failure_rolls_back_reservation(self):
        def fail(tx):
            raise RuntimeError('fixture-library-failure')
        self.journal.sign = fail
        with self.assertRaises(RuntimeError):
            self.journal.handle(request())
        self.journal.sign = self.sign
        self.assertTrue(self.journal.handle(request())['ok'])
        self.assertEqual(self.journal.db.execute('SELECT count(*) FROM signed').fetchone()[0], 1)

    def test_commit_failure_does_not_return_signed_bytes(self):
        db = self.journal.db

        class FailingCommit:
            def __getattr__(self, name):
                return getattr(db, name)

            def commit(self):
                raise sqlite3.OperationalError('fixture-disk-full')

        self.journal.db = FailingCommit()
        try:
            with self.assertRaises(sqlite3.OperationalError):
                self.journal.handle(request())
        finally:
            self.journal.db = db
        self.assertEqual(db.execute('SELECT count(*) FROM signed').fetchone()[0], 0)
        self.assertTrue(self.journal.handle(request())['ok'])

    def test_existing_journal_cannot_be_used_with_another_wallet(self):
        with self.assertRaisesRegex(PaymentError, 'journal_identity_mismatch'):
            Journal(self.path, 'different-address', self.sign)

    def test_no_key_export_or_arbitrary_signing_methods(self):
        for method in ('export_key', 'sign_message', 'sign_typed_data', 'shell', 'rpc'):
            with self.subTest(method=method), self.assertRaises(PaymentError):
                self.journal.handle({'method': method, 'arguments': {}})
        self.assertEqual(self.calls, [])
