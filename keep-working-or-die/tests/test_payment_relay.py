"""Crash recovery tests using transport doubles; no keys, RPC or spending."""
import copy
from pathlib import Path
import tempfile
import unittest

from kwod.payment_relay import PaymentRelay, receipt_observation
from kwod.payments import PaymentError

HASH = '0x' + 'ab' * 32
BLOCK = '0x' + 'cd' * 32
ADDRESS = '0x' + '12' * 20


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = 100
        self.signs, self.broadcasts = [], []
        self.fail_sign = self.fail_broadcast = False
        self.observation = None
        self.intent = dict(request_id='order_1', asset='USDC', recipient=ADDRESS, amount_units='1')
        self.open()

    def open(self):
        self.relay = PaymentRelay(Path(self.temp.name), ADDRESS, quote=self.quote,
                                  sign=self.sign, broadcast=self.broadcast,
                                  observe=lambda *args: self.observation,
                                  verify=lambda *args: None, enabled=True, now=lambda: self.clock)

    def tearDown(self):
        self.relay.close()

    def quote(self, intent):
        return dict(arguments=dict(intent, nonce=7, gas=100000, max_fee_per_gas=100,
                                   max_priority_fee_per_gas=1), observed_at=self.clock,
                    eth_balance_wei=10000001, usdc_balance_units=1,
                    l1_fee_reserve_wei=1, operator_fee_reserve_wei=0)

    def sign(self, request):
        self.signs.append(copy.deepcopy(request))
        if self.fail_sign:
            raise TimeoutError()
        return dict(ok=True, request_id='order_1', chain_id=8453,
                    transaction_hash=HASH, raw_transaction='fixture-bytes')

    def broadcast(self, raw):
        self.broadcasts.append(raw)
        if self.fail_broadcast:
            raise TimeoutError()
        return HASH

    def advance(self):
        return self.relay.advance('order_1')['state']

    def prepare(self):
        self.relay.enqueue(self.intent)
        self.assertEqual(self.advance(), 'prepared')

    def test_unknown_signing_retries_identical_arguments_after_restart(self):
        self.prepare()
        self.fail_sign = True
        with self.assertRaises(TimeoutError):
            self.advance()
        self.relay.close()
        self.clock += 100
        self.open()
        self.fail_sign = False
        self.assertEqual(self.advance(), 'signed')
        self.assertEqual(self.signs[0], self.signs[1])

    def test_unknown_broadcast_reuses_bytes_and_finality_stops_retry(self):
        self.prepare()
        self.advance()
        self.fail_broadcast = True
        with self.assertRaises(TimeoutError):
            self.advance()
        self.assertEqual(self.relay.status('order_1')['state'], 'broadcast_unknown')
        self.relay.close()
        self.open()
        self.fail_broadcast = False
        self.assertEqual(self.advance(), 'submitted')
        self.assertEqual(self.broadcasts, ['fixture-bytes'] * 2)
        self.assertEqual(len(self.signs), 1)
        self.observation = dict(transaction_hash=HASH, state='finalized')
        self.assertEqual(self.advance(), 'finalized')
        self.advance()
        self.assertEqual(len(self.broadcasts), 2)

    def test_disabled_mode_never_signs(self):
        self.relay.enabled = False
        self.prepare()
        self.assertEqual(self.advance(), 'prepared')
        self.assertEqual(self.signs, [])

    def test_stale_unsigned_quote_can_be_replaced(self):
        self.prepare()
        self.clock += 31
        with self.assertRaisesRegex(PaymentError, 'stale_fee_quote'):
            self.advance()
        self.assertEqual(self.advance(), 'prepared')
        self.assertEqual(self.signs, [])

    def test_id_conflict_and_unresolved_payment_block_second_payment(self):
        self.prepare()
        with self.assertRaisesRegex(PaymentError, 'request_id_conflict'):
            self.relay.enqueue(dict(self.intent, amount_units='2'))
        self.relay.enqueue(dict(self.intent, request_id='order_2'))
        with self.assertRaisesRegex(PaymentError, 'earlier_payment_unresolved'):
            self.relay.advance('order_2')


class ReceiptTests(unittest.TestCase):
    def observe(self, **changes):
        args = dict(receipt=dict(transactionHash=HASH, blockHash=BLOCK, blockNumber='0xa', status='0x1'),
                    transaction_hash=HASH, canonical_hash=BLOCK, finalized_number=10, effect_verified=True)
        args.update(changes)
        return receipt_observation(**args)

    def test_finality_and_effect_are_both_required(self):
        self.assertEqual(self.observe(finalized_number=9)['state'], 'included')
        self.assertEqual(self.observe(effect_verified=False)['state'], 'recovery_required')
        self.assertEqual(self.observe()['state'], 'finalized')
        self.assertIsNone(self.observe()['network_fee_wei'])
        self.assertIsNone(self.observe(canonical_hash=HASH))

    def test_missing_canonical_hash_is_never_final(self):
        with self.assertRaisesRegex(PaymentError, 'invalid_receipt_hash'):
            self.observe(canonical_hash=None)
