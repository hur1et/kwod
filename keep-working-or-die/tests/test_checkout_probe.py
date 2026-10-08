import base64
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

spec = importlib.util.spec_from_file_location('checkout_probe', Path(__file__).parents[1] / 'deploy/check_checkout.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
SESSION = 'paymentSession_00000000-0000-0000-0000-000000000001'


def header(**changes):
    body = {'x402Version': 2, 'accepts': [{'scheme': 'auth-capture', 'network': 'eip155:8453',
             'asset': probe.USDC, 'amount': '10500000', 'payTo': '0x' + '12' * 20}]}
    body.update(changes)
    return base64.b64encode(json.dumps(body).encode()).decode()


class ProbeTests(unittest.TestCase):
    def test_challenge_is_reported_without_authorization(self):
        result = probe.decode_challenge(402, header())
        self.assertTrue(result['options'][0]['base_usdc_auth_capture'])
        self.assertEqual(result['options'][0]['requirements']['amount'], '10500000')
        self.assertFalse(result['payment_authorized'])

    def test_malformed_challenges_are_rejected(self):
        for status, value in [(200, header()), (302, header()), (402, None),
                              (402, 'invalid!'), (402, header(x402Version=True)),
                              (402, header(accepts=[])), (402, 'a' * 48001)]:
            with self.subTest(status=status, value=str(value)[:20]), self.assertRaises(ValueError):
                probe.decode_challenge(status, value)

    def test_duplicate_fields_are_rejected(self):
        value = base64.b64encode(b'{"x402Version":2,"x402Version":2}').decode()
        with self.assertRaisesRegex(ValueError, 'duplicate_json_key'):
            probe.decode_challenge(402, value)

    def test_target_injection_is_rejected(self):
        for value in [SESSION + '/../../', 'https://localhost/', SESSION + '\n', SESSION + ';id']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                probe.endpoint(value)

    def test_only_one_unsigned_request_is_sent(self):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 402
        response.getheaders.return_value = [('PAYMENT-REQUIRED', header())]
        with patch.object(probe.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]), \
             patch.object(probe.socket, 'create_connection'), \
             patch.object(probe.ssl, 'create_default_context'), \
             patch.object(probe.http.client, 'HTTPSConnection', return_value=connection):
            probe.probe(SESSION)
        connection.request.assert_called_once_with('POST', probe.endpoint(SESSION), body=b'',
                                                   headers={'Accept': 'application/json'})

    def test_private_dns_answer_prevents_connection(self):
        with patch.object(probe.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('192.168.0.1', 443))]), \
             patch.object(probe.socket, 'create_connection') as connect:
            with self.assertRaisesRegex(ValueError, 'non_public_destination'):
                probe.probe(SESSION)
            connect.assert_not_called()
