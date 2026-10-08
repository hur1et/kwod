"""Durable transfer coordinator. Transport and fee quotation are trusted adapters.

No production entry point is enabled here. Signed bytes are committed before
broadcast; uncertain outcomes never authorize constructing a second payment.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import sqlite3
import time

from .payments import CHAIN_ID, PaymentError, encode, transaction, uint
from .store import worker_lock


def validate_intent(intent):
    if not isinstance(intent, dict) or set(intent) != {'request_id', 'asset', 'recipient', 'amount_units'}:
        raise PaymentError('invalid_intent')
    transaction(dict(intent, nonce=0, gas=21000, max_fee_per_gas=1, max_priority_fee_per_gas=0))
    return dict(intent, recipient=intent['recipient'].lower())


def checked_quote(intent, quote, now):
    fields = {'arguments', 'observed_at', 'eth_balance_wei', 'usdc_balance_units',
              'l1_fee_reserve_wei', 'operator_fee_reserve_wei'}
    if not isinstance(quote, dict) or set(quote) != fields:
        raise PaymentError('invalid_fee_quote')
    observed = uint(quote['observed_at'], maximum=2**63 - 1)
    if not 0 <= now - observed <= 30:
        raise PaymentError('stale_fee_quote')
    args = quote['arguments']
    tx = transaction(args)
    if {key: args[key] for key in intent} != intent:
        raise PaymentError('quote_changed_payment')
    reserve = tx['gas'] * tx['maxFeePerGas'] + uint(quote['l1_fee_reserve_wei']) + uint(quote['operator_fee_reserve_wei'])
    if uint(quote['eth_balance_wei']) < uint(reserve + tx['value']):
        raise PaymentError('insufficient_eth_for_fee_reserve')
    if intent['asset'] == 'USDC' and uint(quote['usdc_balance_units']) < int(intent['amount_units']):
        raise PaymentError('insufficient_usdc')
    return args


def verify_signed(arguments, signed, address):
    """Decode and recover the actual wire transaction before handing it to RPC."""
    from eth_account import Account
    from eth_account.typed_transactions import TypedTransaction
    from eth_utils import keccak
    from hexbytes import HexBytes
    raw = HexBytes(signed['raw_transaction'])
    if not raw or raw[0] != 2 or len(raw) > 2048:
        raise PaymentError('unexpected_transaction_encoding')
    expected = transaction(arguments)
    actual = TypedTransaction.from_bytes(raw).as_dict()
    for field in ('type', 'chainId', 'nonce', 'gas', 'maxFeePerGas', 'maxPriorityFeePerGas', 'value'):
        if actual[field] != expected[field]:
            raise PaymentError('signed_transaction_mismatch')
    if (bytes(actual['to']) != bytes.fromhex(expected['to'][2:])
            or bytes(actual['data']) != bytes.fromhex(expected['data'][2:]) or actual.get('accessList')):
        raise PaymentError('signed_transaction_mismatch')
    if Account.recover_transaction(raw).lower() != address.lower():
        raise PaymentError('wrong_transaction_signer')
    if '0x' + keccak(raw).hex() != signed['transaction_hash']:
        raise PaymentError('signed_transaction_hash_mismatch')


class PaymentRelay:
    def __init__(self, root, address, *, quote, sign, broadcast, observe,
                 enabled=False, verify=verify_signed, now=time.time):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.address = address
        self.quote, self.sign, self.broadcast, self.observe = quote, sign, broadcast, observe
        self.enabled, self.verify, self.now = enabled, verify, now
        self.db = sqlite3.connect(self.root / 'relay.sqlite', isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('CREATE TABLE IF NOT EXISTS relay_identity (id INTEGER PRIMARY KEY CHECK(id=1), address TEXT NOT NULL, chain_id INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS payments (id TEXT PRIMARY KEY, intent TEXT NOT NULL, state TEXT NOT NULL, quote TEXT, signed TEXT, observation TEXT)')
        self.db.execute('INSERT OR IGNORE INTO relay_identity VALUES (1,?,?)', (address, CHAIN_ID))
        row = self.db.execute('SELECT * FROM relay_identity WHERE id=1').fetchone()
        if row['address'] != address or row['chain_id'] != CHAIN_ID:
            self.close()
            raise PaymentError('relay_identity_mismatch')

    def close(self):
        self.db.close()

    def enqueue(self, intent):
        intent = validate_intent(intent)
        with worker_lock(self.root):
            previous = self.db.execute('SELECT intent FROM payments WHERE id=?', (intent['request_id'],)).fetchone()
            if previous:
                if previous['intent'] != encode(intent):
                    raise PaymentError('request_id_conflict')
            else:
                self.db.execute("INSERT INTO payments(id,intent,state) VALUES (?,?,'queued')", (intent['request_id'], encode(intent)))
        return self.status(intent['request_id'])

    def status(self, request_id):
        row = self.db.execute('SELECT state,observation FROM payments WHERE id=?', (request_id,)).fetchone()
        if row is None:
            raise PaymentError('unknown_request')
        return {'request_id': request_id, 'state': row['state'],
                'observation': json.loads(row['observation']) if row['observation'] else None}

    def advance(self, request_id):
        with worker_lock(self.root):
            row = self.db.execute('SELECT * FROM payments WHERE id=?', (request_id,)).fetchone()
            if row is None:
                raise PaymentError('unknown_request')
            if row['state'] in ('finalized', 'reverted', 'recovery_required'):
                return self.status(request_id)
            first = self.db.execute("SELECT id FROM payments WHERE state NOT IN ('finalized','reverted') ORDER BY rowid LIMIT 1").fetchone()
            if first['id'] != request_id:
                raise PaymentError('earlier_payment_unresolved')
            intent = json.loads(row['intent'])
            if row['state'] == 'queued':
                quote = self.quote(intent)
                checked_quote(intent, quote, self.now())
                self.db.execute("UPDATE payments SET state='prepared',quote=? WHERE id=?", (encode(quote), request_id))
            elif row['state'] in ('prepared', 'signing'):
                if not self.enabled:
                    return self.status(request_id)
                quote = json.loads(row['quote'])
                if row['state'] == 'prepared':
                    try:
                        checked_quote(intent, quote, self.now())
                    except PaymentError:
                        # No signing was attempted yet; a fresh quote is safe.
                        self.db.execute("UPDATE payments SET state='queued',quote=NULL WHERE id=?", (request_id,))
                        raise
                    self.db.execute("UPDATE payments SET state='signing' WHERE id=?", (request_id,))
                # Once signing might have happened, retain identical arguments.
                signed = self.sign({'method': 'sign_transfer', 'arguments': quote['arguments']})
                if signed.get('ok') is not True or signed.get('request_id') != request_id or signed.get('chain_id') != CHAIN_ID:
                    raise PaymentError('signer_response_invalid')
                self.verify(quote['arguments'], signed, self.address)
                self.db.execute("UPDATE payments SET state='signed',signed=? WHERE id=?", (encode(signed), request_id))
            elif row['state'] in ('signed', 'broadcast_unknown', 'submitted', 'included'):
                signed = json.loads(row['signed'])
                observed = self.observe(signed['transaction_hash'], intent, self.address)
                if observed is not None:
                    if observed.get('transaction_hash') != signed['transaction_hash']:
                        raise PaymentError('receipt_hash_mismatch')
                    state = observed.get('state')
                    if state not in ('included', 'finalized', 'reverted', 'recovery_required'):
                        raise PaymentError('invalid_receipt_state')
                    self.db.execute('UPDATE payments SET state=?,observation=? WHERE id=?', (state, encode(observed), request_id))
                elif self.enabled:
                    # Persist uncertainty before the request. A timeout, process
                    # crash or RPC rejection never frees this payment's nonce.
                    self.db.execute("UPDATE payments SET state='broadcast_unknown',observation=NULL WHERE id=?", (request_id,))
                    result = self.broadcast(signed['raw_transaction'])
                    if result != signed['transaction_hash']:
                        raise PaymentError('broadcast_hash_mismatch')
                    self.db.execute("UPDATE payments SET state='submitted' WHERE id=?", (request_id,))
            else:
                raise PaymentError('invalid_relay_state')
            return self.status(request_id)


def receipt_observation(receipt, *, transaction_hash, canonical_hash, finalized_number,
                        effect_verified, network_fee_wei=None):
    """The network adapter must verify transfer effect and canonical block hash.

    Unknown complete fees remain unknown; no missing L1/operator fee becomes zero.
    """
    if receipt is None:
        return None
    for value in (transaction_hash, canonical_hash, receipt.get('blockHash')):
        if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{64}', value):
            raise PaymentError('invalid_receipt_hash')
    def quantity(value):
        if not isinstance(value, str) or not re.fullmatch(r'0x(?:0|[1-9a-fA-F][0-9a-fA-F]{0,63})', value):
            raise PaymentError('invalid_receipt_quantity')
        return int(value, 16)
    if receipt.get('transactionHash') != transaction_hash:
        raise PaymentError('receipt_hash_mismatch')
    block = quantity(receipt.get('blockNumber'))
    if receipt.get('blockHash') != canonical_hash:
        return None
    status = quantity(receipt.get('status'))
    if status not in (0, 1):
        raise PaymentError('invalid_receipt_status')
    uint(finalized_number)
    if network_fee_wei is not None:
        uint(network_fee_wei)
    state = 'included'
    if block <= finalized_number:
        state = 'reverted' if status == 0 else ('finalized' if effect_verified is True else 'recovery_required')
    return {'transaction_hash': transaction_hash, 'block_number': block,
            'block_hash': canonical_hash, 'state': state,
            'network_fee_wei': str(network_fee_wei) if network_fee_wei is not None else None}
