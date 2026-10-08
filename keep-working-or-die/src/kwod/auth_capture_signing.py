"""Development-only auth-capture construction and durable signature journal.

No service entry point, HTTP transport, secret-file loading or production enablement.
Only explicitly named deployments are supported until legacy checkout compatibility
has been independently verified. Journal files must live in the isolated signer home.
"""
import json
import re
import secrets
import sqlite3

from .auth_capture import DEPLOYMENTS, address, review
from .payments import CHAIN_ID, PaymentError, USDC, encode

TYPE = ('PaymentInfo(address operator,address payer,address receiver,address token,'
        'uint120 maxAmount,uint48 preApprovalExpiry,uint48 authorizationExpiry,'
        'uint48 refundExpiry,uint16 minFeeBps,uint16 maxFeeBps,address feeReceiver,uint256 salt)')


def plan(requirements, payer, now, salt):
    checked = review(requirements, now=now)
    if not checked['deployment_explicit'] or checked['blockers']:
        raise PaymentError('explicit_consistent_deployment_required')
    if not isinstance(salt, str) or not re.fullmatch(r'0x[0-9a-f]{64}', salt):
        raise PaymentError('invalid_auth_capture_salt')
    payer = address(payer)
    extra = requirements['extra']
    escrow, collector = DEPLOYMENTS[checked['deployment']]
    info = dict(operator=checked['operator'], payer=payer, receiver=checked['recipient'],
                token=USDC, maxAmount=int(checked['amount_units']),
                preApprovalExpiry=checked['collection_expires_at'],
                authorizationExpiry=checked['capture_deadline'], refundExpiry=checked['refund_deadline'],
                minFeeBps=extra['minFeeBps'], maxFeeBps=extra['maxFeeBps'],
                feeReceiver=checked['fee_recipient'], salt=int(salt, 16))
    return dict(payment_info=info, escrow=escrow, collector=collector,
                salt=salt, accepted=json.loads(encode(requirements)))


def typed_data(prepared):
    from eth_abi import encode as abi_encode
    from eth_utils import keccak
    info = prepared['payment_info']
    types = ['bytes32', 'address', 'address', 'address', 'address', 'uint120',
             'uint48', 'uint48', 'uint48', 'uint16', 'uint16', 'address', 'uint256']
    values = [keccak(text=TYPE), info['operator'], '0x' + '00' * 20, info['receiver'],
              info['token'], info['maxAmount'], info['preApprovalExpiry'],
              info['authorizationExpiry'], info['refundExpiry'], info['minFeeBps'],
              info['maxFeeBps'], info['feeReceiver'], info['salt']]
    inner = keccak(abi_encode(types, values))
    nonce = keccak(abi_encode(['uint256', 'address', 'bytes32'], [CHAIN_ID, prepared['escrow'], inner]))
    return dict(types={
        'EIP712Domain': [{'name': n, 'type': t} for n, t in
                        [('name', 'string'), ('version', 'string'), ('chainId', 'uint256'), ('verifyingContract', 'address')]],
        'ReceiveWithAuthorization': [{'name': n, 'type': t} for n, t in
                                     [('from', 'address'), ('to', 'address'), ('value', 'uint256'),
                                      ('validAfter', 'uint256'), ('validBefore', 'uint256'), ('nonce', 'bytes32')]]},
        primaryType='ReceiveWithAuthorization',
        domain=dict(name='USD Coin', version='2', chainId=CHAIN_ID, verifyingContract=USDC),
        message={'from': info['payer'], 'to': prepared['collector'], 'value': info['maxAmount'],
                 'validAfter': 0, 'validBefore': info['preApprovalExpiry'], 'nonce': '0x' + nonce.hex()})


def sign_plan(account, prepared):
    """Internal constructor; callers must supply a reviewed, journaled plan."""
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    if account.address.lower() != prepared['payment_info']['payer']:
        raise PaymentError('wrong_auth_capture_signer')
    data = typed_data(prepared)
    message = encode_typed_data(full_message=data)
    signed = account.sign_message(message)
    if Account.recover_message(message, signature=signed.signature).lower() != account.address.lower():
        raise PaymentError('auth_capture_recovery_failed')
    authorization = dict(data['message'])
    for field in ('value', 'validAfter', 'validBefore'):
        authorization[field] = str(authorization[field])
    return {'x402Version': 2, 'accepted': prepared['accepted'], 'payload': {
        'authorization': authorization, 'salt': prepared['salt'],
        'signature': '0x' + bytes(signed.signature).hex()}}


class AuthorizationJournal:
    """Unique checkout identity prevents replacement of uncertain authorizations.

    `sign` is a trusted local adapter, never an agent-supplied function. No result
    leaves this class before its durable commit. Retrying a failed local signing
    call keeps the original salt, expiry and terms even after a process restart.
    """
    def __init__(self, path, payer, sign, *, enabled=False):
        self.payer, self.sign, self.enabled = address(payer), sign, enabled
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('CREATE TABLE IF NOT EXISTS owner(id INTEGER PRIMARY KEY CHECK(id=1),payer TEXT NOT NULL)')
        self.db.execute('INSERT OR IGNORE INTO owner VALUES(1,?)', (self.payer,))
        if self.db.execute('SELECT payer FROM owner WHERE id=1').fetchone()[0] != self.payer:
            self.db.close()
            raise PaymentError('auth_capture_journal_owner_mismatch')
        self.db.execute('CREATE TABLE IF NOT EXISTS authorizations(checkout TEXT PRIMARY KEY,terms TEXT NOT NULL,prepared TEXT NOT NULL,result TEXT)')

    def close(self):
        self.db.close()

    def authorize(self, checkout, requirements, *, now):
        if not self.enabled:
            raise PaymentError('auth_capture_signing_disabled')
        if not isinstance(checkout, str) or not re.fullmatch(r'paymentSession_[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', checkout):
            raise PaymentError('invalid_checkout_identity')
        terms = encode(requirements)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT terms,prepared,result FROM authorizations WHERE checkout=?', (checkout,)).fetchone()
            if row is None:
                prepared = plan(requirements, self.payer, now, '0x' + secrets.token_hex(32))
                self.db.execute('INSERT INTO authorizations VALUES(?,?,?,NULL)', (checkout, terms, encode(prepared)))
            else:
                if terms != row[0]:
                    raise PaymentError('checkout_terms_conflict')
                prepared = json.loads(row[1])
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        # Serialize local signing and persist the result before returning it.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            result = self.db.execute('SELECT result FROM authorizations WHERE checkout=?', (checkout,)).fetchone()[0]
            if result is None:
                # An expired unreturned authorization must not be renewed silently.
                if now >= prepared['payment_info']['preApprovalExpiry']:
                    raise PaymentError('authorization_expired_no_replacement')
                result = encode(self.sign(prepared))
                self.db.execute('UPDATE authorizations SET result=? WHERE checkout=?', (result, checkout))
            self.db.execute('COMMIT')
            return json.loads(result)
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
