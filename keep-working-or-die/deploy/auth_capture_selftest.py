"""Offline crypto/recovery test. Public test key 1 only; no wallet file reads."""
import copy
import json
from pathlib import Path
import socket
import tempfile

from eth_account import Account
from eth_account.messages import encode_typed_data
from kwod.auth_capture import DEPLOYMENTS
from kwod.auth_capture_signing import AuthorizationJournal, plan, sign_plan, typed_data
from kwod.payments import PaymentError, USDC


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def main():
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            sock = socket.socket(family, socket.SOCK_STREAM)
        except OSError:
            pass
        else:
            sock.close()
            raise RuntimeError('Network isolation missing')
    account = Account.from_key('0x' + '00' * 31 + '01')
    require(account.address == '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf', 'Wrong test identity')
    now = 1789469089
    requirements = dict(scheme='auth-capture', network='eip155:8453', asset=USDC,
        amount='10500000', payTo='0x' + '12' * 20, maxTimeoutSeconds=3600,
        extra=dict(assetTransferMethod='eip3009', captureAuthorizer='0x' + '34' * 20,
                   captureDeadline=1821005089, refundDeadline=1821005089,
                   feeRecipient='0x' + '56' * 20, minFeeBps=100, maxFeeBps=100,
                   name='USD Coin', version='2', tokenCollector=DEPLOYMENTS['v1.0'][1],
                   authCaptureEscrow=DEPLOYMENTS['v1.0'][0]))
    prepared = plan(requirements, account.address, now, '0x' + '01' * 32)
    data = typed_data(prepared)
    result = sign_plan(account, prepared)
    recovered = Account.recover_message(encode_typed_data(full_message=data),
                                        signature=result['payload']['signature'])
    require(recovered == account.address, 'Signature recovery failed')
    require(result == sign_plan(account, prepared), 'Non-deterministic signature')
    mutations = 0
    for field in prepared['payment_info']:
        if field == 'payer':
            continue
        changed = copy.deepcopy(prepared)
        old = changed['payment_info'][field]
        changed['payment_info'][field] = old + 1 if type(old) is int else '0x' + '98' * 20
        require(typed_data(changed)['message']['nonce'] != data['message']['nonce'], 'Unbound term: ' + field)
        mutations += 1
    changed = copy.deepcopy(prepared)
    changed['escrow'] = DEPLOYMENTS['v1.1'][0]
    require(typed_data(changed)['message']['nonce'] != data['message']['nonce'], 'Unbound deployment')
    changed = copy.deepcopy(data)
    changed['message']['from'] = '0x' + '78' * 20
    require(Account.recover_message(encode_typed_data(full_message=changed),
            signature=result['payload']['signature']) != account.address, 'Unbound payer')
    checkout = 'paymentSession_00000000-0000-0000-0000-000000000001'
    with tempfile.TemporaryDirectory() as directory:
        db = Path(directory) / 'test.sqlite'
        attempted = []
        def interrupted(value):
            attempted.append(sign_plan(account, value))
            raise RuntimeError('simulated interruption after local signature')
        journal = AuthorizationJournal(db, account.address, interrupted, enabled=True)
        try:
            journal.authorize(checkout, requirements, now=now)
        except RuntimeError as error:
            require(str(error).startswith('simulated interruption'), 'Unexpected failure')
        else:
            raise RuntimeError('Missing simulated interruption')
        journal.close()
        journal = AuthorizationJournal(db, account.address, lambda value: sign_plan(account, value), enabled=True)
        restored = journal.authorize(checkout, requirements, now=now + 1)
        require(restored == attempted[0], 'Restart changed authorization')
        journal.close()
        def forbidden(value):
            raise RuntimeError('Committed result was signed again')
        journal = AuthorizationJournal(db, account.address, forbidden, enabled=True)
        require(journal.authorize(checkout, requirements, now=now + 7200) == restored, 'Replay changed result')
        altered = copy.deepcopy(requirements)
        altered['amount'] = '1'
        try:
            journal.authorize(checkout, altered, now=now + 2)
        except PaymentError as error:
            require(str(error) == 'checkout_terms_conflict', 'Wrong conflict error')
        else:
            raise RuntimeError('Checkout accepted altered terms')
        journal.close()
    print(json.dumps({'auth_capture_crypto_selftest': 'passed', 'network_used': False,
                      'key_source': 'public_test_key_1', 'payment_term_mutations_checked': mutations,
                      'restart_replay': 'passed', 'test_nonce': data['message']['nonce'],
                      'test_signature': result['payload']['signature'],
                      'production_key_read': False, 'payment_authorized': False, 'worker_started': False}))


if __name__ == '__main__':
    main()
