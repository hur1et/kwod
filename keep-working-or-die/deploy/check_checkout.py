"""Request an unsigned x402 challenge. No keys, wallet SDK or payment retry."""
import base64
import hashlib
import http.client
import ipaddress
import json
import re
import socket
import ssl
import sys

HOST = 'api.cdp.coinbase.com'
USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'


def endpoint(session):
    if not isinstance(session, str) or not re.fullmatch(
            r'paymentSession_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', session):
        raise ValueError('invalid_session')
    return '/platform/v2/payment-sessions/' + session + '/authorizations/x402'


def decode_challenge(status, header):
    if status != 402:
        raise ValueError('unexpected_http_status_' + str(status))
    if not isinstance(header, str) or not 1 <= len(header) <= 48000:
        raise ValueError('missing_or_oversized_payment_required')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate_json_key')
            result[key] = value
        return result
    data = base64.b64decode(header, validate=True)
    body = json.loads(data, object_pairs_hook=unique)
    if not isinstance(body, dict) or type(body.get('x402Version')) is not int or body['x402Version'] != 2:
        raise ValueError('unsupported_x402_version')
    accepts = body.get('accepts')
    if not isinstance(accepts, list) or not 1 <= len(accepts) <= 16:
        raise ValueError('invalid_payment_options')
    options = []
    for option in accepts:
        if not isinstance(option, dict):
            raise ValueError('invalid_payment_option')
        amount = option.get('amount')
        if not isinstance(amount, str) or not re.fullmatch(r'[1-9][0-9]{0,77}', amount) or int(amount) >= 2**256:
            raise ValueError('invalid_payment_amount')
        match = (option.get('scheme') == 'auth-capture' and option.get('network') == 'eip155:8453'
                 and isinstance(option.get('asset'), str) and option['asset'].lower() == USDC.lower())
        # Requirements are untrusted remote data, never passed to a signer here.
        options.append({'base_usdc_auth_capture': match, 'requirements': option})
    return {'ok': True, 'challenge_sha256': hashlib.sha256(data).hexdigest(),
            'options': options, 'extensions': body.get('extensions'),
            'payment_authorized': False, 'signatures_created': 0,
            'transactions_sent': 0, 'worker_started': False}


def probe(session):
    path = endpoint(session)
    rows = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
    addresses = []
    for row in rows:
        address = ipaddress.ip_address(row[4][0])
        if (not address.is_global or address.is_multicast
                or getattr(address, 'ipv4_mapped', None) is not None
                or getattr(address, 'sixtofour', None) is not None
                or getattr(address, 'teredo', None) is not None):
            raise ValueError('non_public_destination')
        addresses.append(str(address))
    if not addresses:
        raise ValueError('dns_empty')
    connection = http.client.HTTPSConnection(HOST, timeout=20)
    raw = socket.create_connection((addresses[0], 443), timeout=20)
    try:
        connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=HOST)
        # Exactly one unsigned request. No cookies, auth, signature or redirects.
        connection.request('POST', path, body=b'', headers={'Accept': 'application/json'})
        response = connection.getresponse()
        headers = response.getheaders()
        required = [v for k, v in headers if k.lower() == 'payment-required']
        if len(required) > 1:
            raise ValueError('duplicate_payment_required_header')
        return decode_challenge(response.status, required[0] if required else None)
    finally:
        connection.close()
        raw.close()


if __name__ == '__main__':
    try:
        print(json.dumps(probe(sys.argv[1]), indent=2, ensure_ascii=True, allow_nan=False))
    except Exception as error:
        # Never echo remote bodies, local environment or credential material.
        known = str(error) if type(error) is ValueError and re.fullmatch('[a-z0-9_]+', str(error)) else 'network_or_response_error'
        print(json.dumps({'ok': False, 'error': known, 'payment_authorized': False}))
        sys.exit(1)
