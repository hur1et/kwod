import copy
from pathlib import Path
import tempfile
import unittest

from kwod.auth_capture import DEPLOYMENTS
from kwod.auth_capture_signing import AuthorizationJournal, plan
from kwod.payments import PaymentError
from test_auth_capture import terms

CHECKOUT = 'paymentSession_00000000-0000-0000-0000-000000000001'
PAYER = '0x' + 'ab' * 20
NOW = 1789469089


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'auth.sqlite'
        self.calls = []
        self.fail = False
        self.requirements = terms()
        self.requirements['extra']['authCaptureEscrow'] = DEPLOYMENTS['v1.0'][0]
        self.open()

    def open(self):
        self.journal = AuthorizationJournal(self.path, PAYER, self.sign, enabled=True)

    def tearDown(self):
        self.journal.close()

    def sign(self, prepared):
        self.calls.append(copy.deepcopy(prepared))
        if self.fail:
            raise RuntimeError('simulated process interruption')
        return {'fixture': prepared}

    def test_committed_signature_is_returned_unchanged_after_restart(self):
        first = self.journal.authorize(CHECKOUT, self.requirements, now=NOW)
        self.journal.close()
        self.open()
        self.assertEqual(self.journal.authorize(CHECKOUT, self.requirements, now=NOW + 5000), first)
        self.assertEqual(len(self.calls), 1)

    def test_failed_signing_retains_salt_expiry_and_terms_after_restart(self):
        self.fail = True
        with self.assertRaises(RuntimeError):
            self.journal.authorize(CHECKOUT, self.requirements, now=NOW)
        self.journal.close()
        self.open()
        self.fail = False
        self.journal.authorize(CHECKOUT, self.requirements, now=NOW + 10)
        self.assertEqual(self.calls[0], self.calls[1])

    def test_expired_uncommitted_signature_cannot_be_replaced(self):
        self.fail = True
        with self.assertRaises(RuntimeError):
            self.journal.authorize(CHECKOUT, self.requirements, now=NOW)
        self.fail = False
        with self.assertRaisesRegex(PaymentError, 'expired_no_replacement'):
            self.journal.authorize(CHECKOUT, self.requirements, now=NOW + 3600)
        self.assertEqual(len(self.calls), 1)

    def test_changed_terms_cannot_reuse_checkout(self):
        self.journal.authorize(CHECKOUT, self.requirements, now=NOW)
        self.requirements['amount'] = '20000000'
        with self.assertRaisesRegex(PaymentError, 'checkout_terms_conflict'):
            self.journal.authorize(CHECKOUT, self.requirements, now=NOW)

    def test_disabled_and_ambiguous_deployment_never_sign(self):
        with self.assertRaisesRegex(PaymentError, 'explicit_consistent_deployment_required'):
            self.journal.authorize(CHECKOUT, terms(), now=NOW)
        self.journal.enabled = False
        with self.assertRaisesRegex(PaymentError, 'signing_disabled'):
            self.journal.authorize(CHECKOUT, self.requirements, now=NOW)
        self.assertEqual(self.calls, [])

    def test_plan_binds_fee_recipient_expiry_payer_and_collector(self):
        prepared = plan(self.requirements, PAYER, NOW, '0x' + '01' * 32)
        self.assertEqual(prepared['payment_info']['payer'], PAYER)
        self.assertEqual(prepared['payment_info']['maxAmount'], 10500000)
        self.assertEqual(prepared['payment_info']['preApprovalExpiry'], NOW + 3600)
        self.assertEqual(prepared['collector'], DEPLOYMENTS['v1.0'][1])
        self.assertEqual(prepared['payment_info']['feeReceiver'], self.requirements['extra']['feeRecipient'])
