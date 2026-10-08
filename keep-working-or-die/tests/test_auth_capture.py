import copy
import unittest
from kwod.auth_capture import DEPLOYMENTS, review
from kwod.payments import PaymentError, USDC


def terms():
    return dict(scheme='auth-capture', network='eip155:8453', asset=USDC, amount='10500000',
                payTo='0x' + '12' * 20, maxTimeoutSeconds=3600,
                extra=dict(assetTransferMethod='eip3009', captureAuthorizer='0x' + '34' * 20,
                           captureDeadline=1821005089, refundDeadline=1821005089,
                           feeRecipient='0x' + '56' * 20, minFeeBps=100, maxFeeBps=100,
                           name='USD Coin', version='2', tokenCollector=DEPLOYMENTS['v1.0'][1]))


class AuthCaptureTests(unittest.TestCase):
    def test_observed_legacy_collector_is_not_silently_signed_as_new_deployment(self):
        result = review(terms(), now=1789469089)
        self.assertEqual(result['blockers'], ['collector_conflicts_with_resolved_escrow'])
        self.assertFalse(result['signing_enabled'])
        self.assertEqual(result['collection_expires_at'], 1789472689)
        self.assertEqual(result['possible_hold_seconds_from_now'], 31536000)
        self.assertEqual(result['fee_max_units_at_full_capture'], '105000')

    def test_explicit_matching_deployment_resolves_but_never_enables_signing(self):
        value = terms()
        value['extra']['authCaptureEscrow'] = DEPLOYMENTS['v1.0'][0]
        result = review(value, now=1789469089)
        self.assertEqual(result['blockers'], [])
        self.assertFalse(result['signing_enabled'])

    def test_unknown_methods_domains_fields_and_expiries_fail_closed(self):
        edits = [('network', 'eip155:1'), ('amount', '1.5'), ('amount', str(2**120)),
                 ('maxTimeoutSeconds', True), ('extra.version', '1'),
                 ('extra.captureDeadline', 10), ('extra.minFeeBps', 101),
                 ('extra.assetTransferMethod', 'permit2'), ('extra.skill', 'https://example.com'),
                 ('extra.authCaptureEscrow', '0x' + '78' * 20)]
        for field, value in edits:
            candidate = copy.deepcopy(terms())
            target = candidate
            if field.startswith('extra.'):
                target = candidate['extra']
                field = field.split('.')[1]
            target[field] = value
            with self.subTest(field=field), self.assertRaises(PaymentError):
                review(candidate, now=1789469089)
