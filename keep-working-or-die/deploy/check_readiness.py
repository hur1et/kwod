"""Read public Base state and OpenRouter catalog. No credentials or signing."""
from datetime import datetime, timezone
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import stat
import sys
import uuid

MODEL = 'openai/gpt-6-astra'
USDC = '0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913'


class ReadinessError(ValueError):
    pass


def public_address(value):
    address = ipaddress.ip_address(value)
    if (not address.is_global or address.is_multicast or address.is_unspecified
            or getattr(address, 'ipv4_mapped', None) is not None
            or getattr(address, 'sixtofour', None) is not None
            or getattr(address, 'teredo', None) is not None):
        raise ReadinessError('non_public_network_address')
    return str(address)


def fetch(host, path, payload=None):
    if (host, path) not in (('mainnet.base.org', '/'),
                           ('openrouter.ai', '/api/v1/models/' + MODEL + '/endpoints')):
        raise ReadinessError('unsupported_destination')
    resolved = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not resolved:
        raise ReadinessError('dns_empty')
    addresses = [public_address(row[4][0]) for row in resolved]
    # Connect to the already-validated IP; TLS still validates the original host.
    # No environment proxy, redirect handling or second hostname lookup.
    connection = http.client.HTTPSConnection(host, timeout=20)
    raw = socket.create_connection((addresses[0], 443), timeout=20)
    try:
        connection.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=host)
        body = json.dumps(payload).encode() if payload is not None else None
        connection.request('POST' if body is not None else 'GET', path, body=body,
                           headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            raise ReadinessError('http_' + str(response.status))
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ReadinessError('response_too_large')
        return json.loads(data)
    finally:
        connection.close()
        raw.close()


def rpc(method, params):
    if method not in ('eth_chainId', 'eth_getBlockByNumber', 'eth_getBalance', 'eth_getCode', 'eth_call'):
        raise ReadinessError('rpc_method_refused')
    call_id = uuid.uuid4().hex
    body = fetch('mainnet.base.org', '/', {'jsonrpc': '2.0', 'id': call_id, 'method': method, 'params': params})
    if not isinstance(body, dict) or body.get('jsonrpc') != '2.0' or body.get('id') != call_id:
        raise ReadinessError('rpc_response_mismatch')
    if 'error' in body or 'result' not in body:
        raise ReadinessError('rpc_error')
    return body['result']


def quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x(?:0|[1-9a-fA-F][0-9a-fA-F]{0,63})', value):
        raise ReadinessError('invalid_hex_quantity')
    return int(value, 16)


def word(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]{64}', value):
        raise ReadinessError('invalid_contract_result')
    return int(value, 16)


def units(value, decimals):
    whole, part = divmod(value, 10**decimals)
    fractional = str(part).zfill(decimals).rstrip('0')
    return str(whole) + ('.' + fractional if fractional else '')


def observe_wallet(address, call=rpc):
    if not isinstance(address, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', address):
        raise ReadinessError('invalid_wallet_address')
    if quantity(call('eth_chainId', [])) != 8453:
        raise ReadinessError('wrong_chain')
    block = call('eth_getBlockByNumber', ['finalized', False])
    if not isinstance(block, dict):
        raise ReadinessError('missing_finalized_block')
    number, block_hash = block.get('number'), block.get('hash')
    quantity(number)
    word(block_hash)
    timestamp = quantity(block.get('timestamp'))
    age = datetime.now(timezone.utc).timestamp() - timestamp
    if not -60 <= age <= 3600:
        raise ReadinessError('stale_or_future_finalized_block')
    code = call('eth_getCode', [USDC, number])
    if not isinstance(code, str) or not re.fullmatch(r'0x(?:[0-9a-fA-F]{2})+', code):
        raise ReadinessError('usdc_contract_missing')
    decimals = word(call('eth_call', [{'to': USDC, 'data': '0x313ce567'}, number]))
    if decimals != 6:
        raise ReadinessError('unexpected_usdc_decimals')
    eth = quantity(call('eth_getBalance', [address, number]))
    usdc = word(call('eth_call', [{'to': USDC, 'data': '0x70a08231' + address[2:].lower().zfill(64)}, number]))
    checked = call('eth_getBlockByNumber', [number, False])
    if not isinstance(checked, dict) or checked.get('hash') != block_hash or checked.get('number') != number:
        raise ReadinessError('block_changed_during_read')
    return {'ok': True, 'address': address, 'chain_id': 8453, 'block_number': quantity(number),
            'block_hash': block_hash, 'block_timestamp': timestamp, 'block_tag': 'finalized',
            'source': 'https://mainnet.base.org', 'eth': units(eth, 18), 'eth_wei': str(eth),
            'usdc': units(usdc, 6), 'usdc_units': str(usdc), 'usdc_contract': USDC,
            'eur_valuation': None, 'broadcast_performed': False}


def model_summary(body):
    data = body.get('data') if isinstance(body, dict) else None
    if not isinstance(data, dict) or not isinstance(data.get('endpoints'), list):
        raise ReadinessError('invalid_model_catalog')
    if data.get('id', MODEL) != MODEL:
        raise ReadinessError('unexpected_catalog_model')
    endpoints = []
    for endpoint in data['endpoints']:
        if not isinstance(endpoint, dict):
            raise ReadinessError('invalid_endpoint_metadata')
        if endpoint.get('provider_name', '').lower() != 'openai' and endpoint.get('provider_slug') != 'openai':
            continue
        params = endpoint.get('supported_parameters')
        params = params if isinstance(params, list) and all(isinstance(p, str) for p in params) else None
        endpoints.append({'provider': 'openai', 'tools_advertised': 'tools' in params if params is not None else None,
                          'reasoning_advertised': 'reasoning' in params if params is not None else None})
    return {'ok': True, 'model': MODEL, 'openai_endpoints_found': len(endpoints),
            'endpoints': endpoints, 'catalog_only': True, 'inference_verified': False}


def main():
    path = Path('/etc/kwod-signer.json')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ReadinessError('unsafe_public_wallet_config')
        config = json.loads(stream.read(65536))
    report = {'checked_at': datetime.now(timezone.utc).isoformat(),
              'worker_started': False, 'model_calls': 0, 'transactions_sent': 0}
    for component, action in (
            ('wallet', lambda: observe_wallet(config['address'])),
            ('model_catalog', lambda: model_summary(fetch('openrouter.ai', '/api/v1/models/' + MODEL + '/endpoints')))):
        print('Pruefe ' + component + ' ...', flush=True)
        try:
            report[component] = action()
        except ReadinessError as error:
            report[component] = {'ok': False, 'error': str(error)}
        except Exception:
            report[component] = {'ok': False, 'error': 'network_or_response_error'}
    print(json.dumps(report, indent=2), flush=True)
    return 0 if all(report[name]['ok'] for name in ('wallet', 'model_catalog')) else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('{"ok":false,"error":"readiness_check_failed"}', file=sys.stderr)
        sys.exit(1)
