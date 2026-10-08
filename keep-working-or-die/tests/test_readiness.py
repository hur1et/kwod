from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from test_deployment import module


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.check = module('check_readiness')
        self.address = '0x' + '12' * 20
        self.block = {'number': '0x123', 'hash': '0x' + 'ab' * 32,
                      'timestamp': hex(int(datetime.now(timezone.utc).timestamp()) - 900)}
        self.calls = []

    def rpc(self, method, params):
        self.calls.append((method, params))
        if method == 'eth_chainId':
            return '0x2105'
        if method == 'eth_getBlockByNumber':
            return self.block.copy()
        if method == 'eth_getCode':
            return '0x6001'
        if method == 'eth_getBalance':
            return hex(1234567890123456789)
        if method == 'eth_call':
            value = 6 if params[0]['data'] == '0x313ce567' else 1234567
            return '0x' + format(value, '064x')
        raise AssertionError(method)

    def test_exact_units_and_same_block_for_all_balance_reads(self):
        result = self.check.observe_wallet(self.address, self.rpc)
        self.assertEqual(result['eth'], '1.234567890123456789')
        self.assertEqual(result['usdc'], '1.234567')
        self.assertIsNone(result['eur_valuation'])
        self.assertFalse(result['broadcast_performed'])
        for method, params in self.calls:
            if method in ('eth_getCode', 'eth_getBalance', 'eth_call'):
                self.assertEqual(params[-1], self.block['number'])

    def test_wrong_chain_never_reads_balances(self):
        calls = []
        def wrong(method, params):
            calls.append(method)
            return '0x1'
        with self.assertRaisesRegex(self.check.ReadinessError, 'wrong_chain'):
            self.check.observe_wallet(self.address, wrong)
        self.assertEqual(calls, ['eth_chainId'])

    def test_block_change_and_bad_token_decimals_invalidate_observation(self):
        def changed(method, params):
            result = self.rpc(method, params)
            if method == 'eth_getBlockByNumber' and params[0] != 'finalized':
                result['hash'] = '0x' + 'cd' * 32
            return result
        with self.assertRaisesRegex(self.check.ReadinessError, 'block_changed'):
            self.check.observe_wallet(self.address, changed)
        def decimals(method, params):
            if method == 'eth_call' and params[0]['data'] == '0x313ce567':
                return '0x' + format(18, '064x')
            return self.rpc(method, params)
        with self.assertRaisesRegex(self.check.ReadinessError, 'unexpected_usdc_decimals'):
            self.check.observe_wallet(self.address, decimals)

    def test_old_block_and_rpc_failure_are_not_reported_as_zero(self):
        self.block['timestamp'] = '0x1'
        with self.assertRaisesRegex(self.check.ReadinessError, 'stale_or_future'):
            self.check.observe_wallet(self.address, self.rpc)
        with patch.object(self.check, 'fetch', return_value={'jsonrpc': '2.0', 'id': 'different', 'result': '0x0'}):
            with self.assertRaises(self.check.ReadinessError):
                self.check.rpc('eth_getBalance', [])

    def test_private_local_transition_and_multicast_addresses_are_rejected(self):
        for ip in ('127.0.0.1', '192.168.0.118', '10.1.2.3', '172.16.1.1', '169.254.169.254',
                   '100.64.1.1', '::1', 'fe80::1', 'fc00::1', '::ffff:8.8.8.8', '224.0.0.1',
                   '2002:0808:0808::1'):
            with self.subTest(ip=ip), self.assertRaises(self.check.ReadinessError):
                self.check.public_address(ip)
        self.assertEqual(self.check.public_address('8.8.8.8'), '8.8.8.8')

    def test_wrong_destinations_and_broadcast_methods_never_connect(self):
        with patch.object(self.check.socket, 'getaddrinfo') as dns:
            for host, path in (('192.168.0.118', '/'), ('openrouter.ai', '/api/v1/responses'),
                               ('mainnet.base.org', '/other')):
                with self.assertRaises(self.check.ReadinessError):
                    self.check.fetch(host, path)
            dns.assert_not_called()
        with patch.object(self.check, 'fetch') as fetch:
            with self.assertRaises(self.check.ReadinessError):
                self.check.rpc('eth_sendRawTransaction', ['0x00'])
            fetch.assert_not_called()

    def test_catalog_never_claims_actual_model_access(self):
        result = self.check.model_summary({'data': {'id': self.check.MODEL, 'endpoints': [
            {'provider_name': 'OpenAI', 'supported_parameters': ['tools', 'reasoning']},
            {'provider_name': 'Other', 'supported_parameters': ['tools']}]}})
        self.assertEqual(result['openai_endpoints_found'], 1)
        self.assertTrue(result['endpoints'][0]['tools_advertised'])
        self.assertTrue(result['catalog_only'])
        self.assertFalse(result['inference_verified'])
        unknown = self.check.model_summary({'data': {'endpoints': [{'provider_name': 'OpenAI'}]}})
        self.assertIsNone(unknown['endpoints'][0]['tools_advertised'])

    def test_tls_connects_to_validated_ip_and_keeps_original_hostname(self):
        from unittest.mock import Mock
        raw, tls, connection, context = Mock(), Mock(), Mock(), Mock()
        context.wrap_socket.return_value = tls
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = b'{"data":{"endpoints":[]}}'
        with patch.object(self.check.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]), \
             patch.object(self.check.socket, 'create_connection', return_value=raw) as connect, \
             patch.object(self.check.ssl, 'create_default_context', return_value=context), \
             patch.object(self.check.http.client, 'HTTPSConnection', return_value=connection):
            self.check.fetch('openrouter.ai', '/api/v1/models/' + self.check.MODEL + '/endpoints')
        connect.assert_called_once_with(('8.8.8.8', 443), timeout=20)
        context.wrap_socket.assert_called_once_with(raw, server_hostname='openrouter.ai')
        self.assertIs(connection.sock, tls)
        self.assertEqual(connection.request.call_args.args[0], 'GET')
        raw.close.assert_called_once()
