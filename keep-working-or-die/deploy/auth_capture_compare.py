"""Compare official Node client output against Python using public test key 1."""
import json
import re
from pathlib import Path
import socket
import subprocess
import sys
from kwod.auth_capture import DEPLOYMENTS
from kwod.auth_capture_signing import plan, sign_plan, typed_data
from kwod.payments import USDC


def payload_differences(expected, actual, path='payload'):
    """Compare all fields; only EVM address letter case is representation-only.

    Missing fields, extra fields, number types, nonces and signatures remain exact.
    Values are safe to print here only because this runner uses a public test key.
    """
    if isinstance(expected, dict) and isinstance(actual, dict):
        differences = []
        for key in sorted(set(expected) | set(actual)):
            field = path + '.' + key
            if key not in expected or key not in actual:
                differences.append({'field': field, 'expected_present': key in expected,
                                    'actual_present': key in actual})
            else:
                differences.extend(payload_differences(expected[key], actual[key], field))
        return differences
    if path in ('payload.authorization.from', 'payload.authorization.to'):
        if (isinstance(expected, str) and isinstance(actual, str)
                and re.fullmatch(r'0x[0-9a-fA-F]{40}', expected)
                and re.fullmatch(r'0x[0-9a-fA-F]{40}', actual)
                and expected.lower() == actual.lower()):
            return []
    if type(expected) is type(actual) and expected == actual:
        return []
    return [{'field': path, 'expected': expected, 'actual': actual}]


def main():
    from eth_account import Account
    for family in (socket.AF_INET, socket.AF_INET6):
        try:
            sock = socket.socket(family, socket.SOCK_STREAM)
        except OSError:
            continue
        sock.close()
        raise RuntimeError('Network isolation missing')
    requirements = dict(scheme='auth-capture', network='eip155:8453', asset=USDC,
        amount='10500000', payTo='0x' + '12' * 20, maxTimeoutSeconds=3600,
        extra=dict(assetTransferMethod='eip3009', captureAuthorizer='0x' + '34' * 20,
                   captureDeadline=1821005089, refundDeadline=1821005089,
                   feeRecipient='0x' + '56' * 20, minFeeBps=100, maxFeeBps=100,
                   name='USD Coin', version='2', tokenCollector=DEPLOYMENTS['v1.0'][1]))
    process = subprocess.run(['/opt/kwod-wallet/node/bin/node', str(Path(sys.argv[1]) / 'compare.mjs'),
                              json.dumps(requirements)], capture_output=True, text=True, timeout=60)
    if process.returncode:
        # Isolated test process: stderr contains only package/test diagnostics.
        print(process.stderr[-4000:], file=sys.stderr)
        raise RuntimeError('Official client test failed')
    observations = json.loads(process.stdout)
    if len(observations) != 2:
        raise RuntimeError('Missing official client result')
    account = Account.from_key('0x' + '00' * 31 + '01')
    reports = []
    for observation in observations:
        payload = observation['payload']
        auth = payload['authorization']
        matches = []
        comparisons = []
        for deployment, (escrow, collector) in DEPLOYMENTS.items():
            # Offline comparison only. Never change a live checkout's accepted terms.
            candidate = json.loads(json.dumps(requirements))
            candidate['extra']['authCaptureEscrow'] = escrow
            candidate['extra']['tokenCollector'] = collector
            now = int(auth['validBefore']) - requirements['maxTimeoutSeconds']
            prepared = plan(candidate, account.address, now, payload['salt'])
            own = sign_plan(account, prepared)['payload']
            differences = payload_differences(own, payload)
            comparisons.append({'deployment': deployment, 'differences': differences})
            if not differences:
                if typed_data(prepared)['message']['nonce'].lower() != observation['captured']['message']['nonce'].lower():
                    raise RuntimeError('Captured typed data differs from payload')
                matches.append(deployment)
        if len(matches) != 1:
            reports.append({'client_version': observation['version'], 'matched': False,
                            'comparisons': comparisons})
            continue
        reports.append({'client_version': observation['version'], 'deployment': matches[0],
                        'matched': True,
                        'nonce_and_signature_match': True,
                        'legacy_collector_hint_honored': auth['to'].lower() == requirements['extra']['tokenCollector'].lower()})
    passed = all(report['matched'] for report in reports)
    print(json.dumps({'official_client_comparison': 'passed' if passed else 'failed', 'clients': reports,
                      'test_key_only': True, 'signing_network_used': False,
                      'checkout_backend_verified': False, 'payment_authorized': False, 'worker_started': False}))
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
