"""Real cryptography checks; requires the isolated wallet's eth-account dependency.

Only the publicly known test key 1 is used. No wallet files or network are accessed.
"""
import copy
import pytest

pytest.importorskip('eth_account', reason='eth-account exists on Ubuntu signer, not local development environment')
from eth_account import Account
from eth_account.messages import encode_typed_data
from kwod.auth_capture import DEPLOYMENTS
from kwod.auth_capture_signing import plan, sign_plan, typed_data
from test_auth_capture import terms


def prepared():
    account = Account.from_key('0x' + '00' * 31 + '01')
    requirements = terms()
    requirements['extra']['authCaptureEscrow'] = DEPLOYMENTS['v1.0'][0]
    return account, plan(requirements, account.address, 1789469089, '0x' + '01' * 32)


def test_real_signature_recovers_only_the_test_account():
    account, value = prepared()
    payload = sign_plan(account, value)
    message = encode_typed_data(full_message=typed_data(value))
    assert Account.recover_message(message, signature=payload['payload']['signature']) == account.address
    assert payload == sign_plan(account, value)
    assert payload['payload']['authorization']['value'] == '10500000'


def test_matches_user_verified_ubuntu_regression_vector():
    # Captured from our Ubuntu selftest, NOT an independent official-client vector.
    account, value = prepared()
    assert typed_data(value)['message']['nonce'] == '0xa1a5db58c18a88bed4c88b409e6d773633c1266e0310ca65b2cc3a5adc6183c7'
    assert sign_plan(account, value)['payload']['signature'] == (
        '0x7afccf48cbddb22e8947f1f420a3291468625dd33810b52aa9c3aba7df05c40c66015a008405f5c7573095b2f52af31e96e817b657af9efd4112cae5781685851b')


def test_every_payment_term_changes_authorization_nonce():
    _, value = prepared()
    original = typed_data(value)['message']['nonce']
    for field in value['payment_info']:
        if field == 'payer':
            continue  # Deliberately payer-agnostic nonce; EIP-3009 signs from separately.
        changed = copy.deepcopy(value)
        old = changed['payment_info'][field]
        changed['payment_info'][field] = old + 1 if type(old) is int else '0x' + '98' * 20
        assert typed_data(changed)['message']['nonce'] != original, field
    changed = copy.deepcopy(value)
    changed['escrow'] = DEPLOYMENTS['v1.1'][0]
    assert typed_data(changed)['message']['nonce'] != original
