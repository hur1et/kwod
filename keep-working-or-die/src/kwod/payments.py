"""Local signing boundary. No RPC, HTTP, shell execution or key export API."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import socket
import sqlite3
import stat
import struct

CHAIN_ID = 8453
USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'
SOCKET = '/run/kwod-signer/payment.sock'


class PaymentError(ValueError):
    pass


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def uint(value, maximum=2**256 - 1, minimum=0):
    if type(value) is not int or not minimum <= value <= maximum:
        raise PaymentError('invalid_integer')
    return value


def transaction(args):
    fields = {'request_id', 'asset', 'recipient', 'amount_units', 'nonce', 'gas',
              'max_fee_per_gas', 'max_priority_fee_per_gas'}
    if not isinstance(args, dict) or set(args) != fields:
        raise PaymentError('invalid_fields')
    if not isinstance(args['request_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', args['request_id']):
        raise PaymentError('invalid_request_id')
    recipient = args['recipient']
    if not isinstance(recipient, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', recipient) or int(recipient[2:], 16) == 0:
        raise PaymentError('invalid_recipient')
    amount = args['amount_units']
    if not isinstance(amount, str) or not re.fullmatch(r'[1-9][0-9]{0,77}', amount):
        raise PaymentError('invalid_amount_units')
    amount = uint(int(amount), minimum=1)
    asset = args['asset']
    if asset not in ('ETH', 'USDC'):
        raise PaymentError('unsupported_asset')
    tx = {'type': 2, 'chainId': CHAIN_ID,
          'nonce': uint(args['nonce'], maximum=2**63 - 1),
          'gas': uint(args['gas'], maximum=2**64 - 1, minimum=21000),
          'maxFeePerGas': uint(args['max_fee_per_gas'], minimum=1),
          'maxPriorityFeePerGas': uint(args['max_priority_fee_per_gas']),
          'to': recipient.lower(), 'value': amount if asset == 'ETH' else 0, 'data': '0x'}
    if tx['maxPriorityFeePerGas'] > tx['maxFeePerGas']:
        raise PaymentError('priority_fee_exceeds_maximum')
    uint(tx['gas'] * tx['maxFeePerGas'] + tx['value'])
    if asset == 'USDC':
        tx['to'] = USDC
        tx['data'] = '0xa9059cbb' + recipient[2:].lower().zfill(64) + format(amount, '064x')
    return tx


class Journal:
    def __init__(self, path, address, sign, *, enabled=False, enforce_safeguards=False):
        self.address, self.sign, self.enabled = address, sign, enabled
        self.enforce_safeguards = enforce_safeguards
        self.db = sqlite3.connect(path, isolation_level=None, timeout=10)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA journal_mode=DELETE')
        self.db.execute('CREATE TABLE IF NOT EXISTS identity (id INTEGER PRIMARY KEY CHECK(id=1), address TEXT NOT NULL, chain INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS signed (request_id TEXT PRIMARY KEY, nonce INTEGER UNIQUE NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL)')
        self.db.execute('INSERT OR IGNORE INTO identity VALUES (1,?,?)', (address, CHAIN_ID))
        if self.db.execute('SELECT address,chain FROM identity').fetchall() != [(address, CHAIN_ID)]:
            self.db.close()
            raise PaymentError('journal_identity_mismatch')

    def close(self):
        self.db.close()

    def handle(self, request):
        if not isinstance(request, dict) or set(request) != {'method', 'arguments'}:
            raise PaymentError('invalid_request')
        method, args = request['method'], request['arguments']
        if method == 'status' and args == {}:
            return {'ok': True, 'component': 'wallet_signer', 'address': self.address,
                    'chain_id': CHAIN_ID, 'signing_enabled': self.enabled, 'broadcast_enabled': False,
                    'signed_transactions': self.db.execute('SELECT count(*) FROM signed').fetchone()[0]}
        if method not in ('preview_transfer', 'sign_transfer'):
            raise PaymentError('unsupported_method')
        tx = transaction(args)
        if method == 'preview_transfer':
            return {'ok': True, 'transaction': tx, 'signed': False,
                    'balance_checked': False, 'network_fee_checked': False}
        if not self.enabled:
            raise PaymentError('signing_disabled')
        if self.enforce_safeguards:
            # This standalone signer also runs with Python -I, outside kwod imports.
            for marker in ('STOP', 'WATCHDOG_PAUSE'):
                try: Path('/etc/kwod-safety', marker).lstat()
                except FileNotFoundError: continue
                except OSError: raise PaymentError('safety_state_unavailable') from None
                raise PaymentError('safety_paused')
            try:
                receipt = read_checked('/etc/kwod-s54/profile.json', 0, 0o644)
                if receipt.get('level')!='S5.4' or receipt.get('payments') is not True:
                    raise PaymentError('payment_gateway_not_provisioned')
                with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                    conn.settimeout(10); conn.connect('/run/kwod-watchdog/control.sock')
                    conn.sendall((encode({'kind':'payment_attempt','arguments':args})+'\n').encode())
                    with conn.makefile('rb') as stream: verdict=json.loads(stream.readline(4097))
                if verdict.get('decision')!='ALLOW': raise PaymentError('payment_watchdog_blocked')
            except (OSError,ValueError,TypeError,AttributeError):
                raise PaymentError('payment_gateway_not_provisioned') from None
        payload = encode(tx)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            previous = self.db.execute('SELECT payload,result FROM signed WHERE request_id=?', (args['request_id'],)).fetchone()
            if previous:
                if previous[0] != payload:
                    raise PaymentError('request_id_conflict')
                result = json.loads(previous[1])
            else:
                if self.db.execute('SELECT 1 FROM signed WHERE nonce=?', (tx['nonce'],)).fetchone():
                    raise PaymentError('nonce_already_signed')
                # No network operation occurs here. Commit the exact signed bytes
                # before returning them, so retries never create a fresh payment.
                signed = self.sign(tx)
                result = {'ok': True, 'request_id': args['request_id'], 'chain_id': CHAIN_ID,
                          'transaction_hash': signed['transaction_hash'],
                          'raw_transaction': signed['raw_transaction'], 'broadcast': False}
                self.db.execute('INSERT INTO signed VALUES (?,?,?,?)',
                                (args['request_id'], tx['nonce'], payload, encode(result)))
            self.db.commit()
            return result
        except BaseException:
            self.db.rollback()
            raise


def read_checked(path, uid, mode):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode:
            raise PaymentError('unsafe_file')
        data = stream.read(65537)
        if len(data) > 65536:
            raise PaymentError('oversized_file')
        return json.loads(data)


def sign_function(account):
    from eth_utils import to_checksum_address

    def sign(tx):
        signed = account.sign_transaction(dict(tx, to=to_checksum_address(tx['to'])))
        return {'raw_transaction': '0x' + bytes(signed.raw_transaction).hex(),
                'transaction_hash': '0x' + bytes(signed.hash).hex()}
    return sign


def serve():
    import fcntl
    import resource
    from eth_account import Account
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            probe = socket.socket(family, socket.SOCK_STREAM)
        except OSError:
            pass
        else:
            probe.close()
            raise PaymentError('ip_socket_isolation_missing')
    home = Path('/var/lib/kwod-signer')
    info = home.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise PaymentError('unsafe_home')
    settings = read_checked('/etc/kwod-signer.json', 0, 0o644)
    if set(settings) != {'address', 'runtime_uid', 'signing_enabled'} or type(settings['signing_enabled']) is not bool:
        raise PaymentError('invalid_settings')
    uint(settings['runtime_uid'], maximum=2**32 - 1, minimum=1)
    identity = read_checked(home / 'identity.json', os.getuid(), 0o600)
    account = Account.from_key(identity['private_key'])
    if account.address != settings['address'] or account.address != identity['address']:
        raise PaymentError('identity_mismatch')
    # A second process must never unlink the active service's socket.
    lock_fd = os.open(home / 'signer.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        dbpath = home / 'payments.sqlite'
        if dbpath.exists() or dbpath.is_symlink():
            info = dbpath.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o600:
                raise PaymentError('unsafe_journal')
        journal = Journal(dbpath, account.address, sign_function(account), enabled=settings['signing_enabled'], enforce_safeguards=True)
        try:
            path = Path(SOCKET)
            if path.exists() or path.is_symlink():
                info = path.lstat()
                if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                    raise PaymentError('unsafe_socket')
                path.unlink()
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
                server.bind(SOCKET)
                os.chmod(SOCKET, 0o660)
                server.listen(8)
                while True:
                    connection, _ = server.accept()
                    with connection:
                        connection.settimeout(5)
                        _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                        if uid not in (0, settings['runtime_uid']):
                            continue
                        try:
                            with connection.makefile('rb') as reader:
                                line = reader.readline(8193)
                            if len(line) > 8192 or not line.endswith(b'\n'):
                                raise PaymentError('invalid_frame')
                            result = journal.handle(json.loads(line))
                        except PaymentError as error:
                            result = {'ok': False, 'error': str(error)}
                        except Exception:
                            # Never expose library exceptions, key material or traces.
                            result = {'ok': False, 'error': 'request_failed'}
                        try:
                            connection.sendall((encode(result) + '\n').encode())
                        except OSError:
                            pass
        finally:
            journal.close()


def status_client():
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(10)
        connection.connect(SOCKET)
        connection.sendall(b'{"method":"status","arguments":{}}\n')
        with connection.makefile('rb') as reader:
            result = json.loads(reader.readline(8193))
    if result.get('ok') is not True or result.get('signing_enabled') is not False:
        raise PaymentError('expected_observation_mode')
    print(encode(result))


def selftest():
    """Exercise real signing with a public test key, without RPC or real wallet."""
    from eth_account import Account
    import tempfile
    account = Account.from_key(bytes.fromhex('00' * 31 + '01'))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'test.sqlite'
        journal = Journal(path, account.address, sign_function(account), enabled=True)
        request = {'method': 'sign_transfer', 'arguments': {
            'request_id': 'selftest', 'asset': 'USDC', 'recipient': '0x' + '11' * 20,
            'amount_units': '1', 'nonce': 0, 'gas': 100000,
            'max_fee_per_gas': 100, 'max_priority_fee_per_gas': 1}}
        result = journal.handle(request)
        journal.close()
        if Account.recover_transaction(result['raw_transaction']) != account.address:
            raise PaymentError('signature_recovery_failed')
        journal = Journal(path, account.address, lambda tx: (_ for _ in ()).throw(RuntimeError()), enabled=True)
        try:
            if journal.handle(request) != result:
                raise PaymentError('replay_failed')
        finally:
            journal.close()
    print('{"signer_selftest":"passed","network_used":false}')


if __name__ == '__main__':
    import sys
    try:
        {'serve': serve, 'status': status_client, 'selftest': selftest}[sys.argv[1]]()
    except Exception:
        print('{"ok":false,"error":"signer_operation_failed"}', file=sys.stderr)
        sys.exit(1)
