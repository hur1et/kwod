"""Offline review of Coinbase auth-capture terms. No signature or network API.

Deployment addresses follow x402/specs/schemes/auth-capture/scheme_auth_capture_evm.md.
This review is not approval, merchant authentication, or a payment implementation.
"""
from datetime import datetime, timezone
import re

from .payments import PaymentError, USDC, uint

DEPLOYMENTS = {
    'v1.0': ('0xBdEA0D1bcC5966192B070Fdf62aB4EF5b4420cff', '0x0E3dF9510de65469C4518D7843919c0b8C7A7757'),
    'v1.1': ('0xf96815976523E00e65Be8f34cA5e64b4f41EB19c', '0x8612dfdc421f80336cd14E8EF9cb1E765dB5ab88'),
}


def address(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', value) or int(value[2:], 16) == 0:
        raise PaymentError('invalid_auth_capture_address')
    return value.lower()


def review(requirements, *, now):
    """Report terms; ambiguous legacy collectors block deployment resolution.

    Deliberately excludes arbitrary extensions, typed data and linked skills.
    No generated output is suitable for submission as a payment authorization.
    """
    uint(now, maximum=2**48 - 1)
    fields = {'scheme', 'network', 'asset', 'amount', 'payTo', 'maxTimeoutSeconds', 'extra'}
    if not isinstance(requirements, dict) or set(requirements) != fields:
        raise PaymentError('unsupported_auth_capture_fields')
    if requirements['scheme'] != 'auth-capture' or requirements['network'] != 'eip155:8453':
        raise PaymentError('unsupported_auth_capture_scheme_or_network')
    if address(requirements['asset']) != USDC.lower():
        raise PaymentError('unsupported_auth_capture_asset')
    amount = requirements['amount']
    if not isinstance(amount, str) or not re.fullmatch(r'[1-9][0-9]{0,36}', amount):
        raise PaymentError('invalid_auth_capture_amount')
    amount = uint(int(amount), maximum=2**120 - 1, minimum=1)
    recipient = address(requirements['payTo'])
    timeout = uint(requirements['maxTimeoutSeconds'], maximum=2**48 - 1, minimum=1)
    expires = uint(now + timeout, maximum=2**48 - 1)
    extra = requirements['extra']
    required = {'assetTransferMethod', 'captureAuthorizer', 'captureDeadline', 'feeRecipient',
                'maxFeeBps', 'minFeeBps', 'name', 'refundDeadline', 'version'}
    if not isinstance(extra, dict) or not required <= set(extra) or set(extra) - required - {'tokenCollector', 'authCaptureEscrow'}:
        raise PaymentError('unsupported_auth_capture_extra')
    if (extra['assetTransferMethod'], extra['name'], extra['version']) != ('eip3009', 'USD Coin', '2'):
        raise PaymentError('unsupported_auth_capture_token_domain')
    operator, fee_recipient = address(extra['captureAuthorizer']), address(extra['feeRecipient'])
    capture = uint(extra['captureDeadline'], maximum=2**48 - 1)
    refund = uint(extra['refundDeadline'], maximum=2**48 - 1)
    if not expires <= capture <= refund:
        raise PaymentError('invalid_auth_capture_expiry_order')
    low = uint(extra['minFeeBps'], maximum=10000)
    high = uint(extra['maxFeeBps'], maximum=10000)
    if low > high:
        raise PaymentError('invalid_auth_capture_fee_bounds')
    escrow = address(extra.get('authCaptureEscrow', DEPLOYMENTS['v1.1'][0]))
    deployment = next((name for name, pair in DEPLOYMENTS.items() if pair[0].lower() == escrow), None)
    if deployment is None:
        raise PaymentError('unknown_auth_capture_escrow')
    collector = DEPLOYMENTS[deployment][1].lower()
    blockers = []
    if 'tokenCollector' in extra and address(extra['tokenCollector']) != collector:
        blockers.append('collector_conflicts_with_resolved_escrow')
    return {'review_only': True, 'signing_enabled': False, 'deployment': deployment,
            'deployment_explicit': 'authCaptureEscrow' in extra, 'blockers': blockers,
            'amount_units': str(amount), 'recipient': recipient, 'operator': operator,
            'fee_recipient': fee_recipient, 'fee_min_units_at_full_capture': str(amount * low // 10000),
            'fee_max_units_at_full_capture': str(amount * high // 10000),
            'collection_expires_at': expires, 'capture_deadline': capture, 'refund_deadline': refund,
            'capture_deadline_utc': datetime.fromtimestamp(capture, timezone.utc).isoformat(),
            'possible_hold_seconds_from_now': capture - now,
            'compute_credit_verified': False}
