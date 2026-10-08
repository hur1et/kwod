import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from kwod.provider import OpenRouterProvider, ProviderError, FixtureProvider
from kwod.runtime import initialize, Runtime
from kwod.store import Store
from kwod.accounting import register_tariff
from test_accounting import TARIFF, USAGE
from test_deployment import module


class OpenRouterTests(unittest.TestCase):
    def provider(self, handler):
        provider = OpenRouterProvider.__new__(OpenRouterProvider)
        provider.client = httpx.Client(base_url='https://openrouter.ai/api/v1/',
            headers={'Authorization': 'Bearer fixture-secret'}, follow_redirects=False,
            transport=httpx.MockTransport(handler))
        self.addCleanup(provider.client.close)
        return provider

    def test_preserves_tools_reasoning_usage_and_pins_routing(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json={'model': 'openai/gpt-6-astra', 'status': 'completed',
                'output': [{'type': 'reasoning', 'encrypted_content': 'fixture-encrypted'}],
                'usage': {'cost': 0.0123, 'input_tokens': 10, 'novel_field': 4}})
        payload = {'model': 'gpt-6-astra', 'store': False, 'parallel_tool_calls': False, 'service_tier': 'default',
                   'input': [{'type': 'function_call_output', 'call_id': 'a', 'output': '{}'}],
                   'include': ['reasoning.encrypted_content'], 'tools': [{'type': 'function', 'name': 'clock'}]}
        result = self.provider(handler).create(payload)
        sent = json.loads(calls[0].content)
        self.assertEqual(str(calls[0].url), 'https://openrouter.ai/api/v1/responses')
        self.assertEqual(sent['model'], 'openai/gpt-6-astra')
        self.assertEqual(payload['model'], 'gpt-6-astra')
        self.assertEqual(sent['input'], payload['input'])
        self.assertEqual(sent['tools'], payload['tools'])
        self.assertFalse(sent['provider']['allow_fallbacks'])
        self.assertNotIn('parallel_tool_calls', sent)
        self.assertNotIn('service_tier', sent)
        self.assertEqual(payload['service_tier'], 'default')
        self.assertEqual(sent['provider']['only'], ['openai'])
        self.assertEqual(result['usage']['novel_field'], 4)
        self.assertEqual(result['output'][0]['encrypted_content'], 'fixture-encrypted')
        self.assertEqual(result['_billing_provider'], 'openrouter')

    def test_errors_never_echo_secret_or_retry_inside_adapter(self):
        for status in (302, 401, 402, 408, 429, 500):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, headers={'location': 'https://other.invalid/'},
                                      json={'error': {'message': 'fixture-secret'}})
            with self.subTest(status=status), self.assertRaises(ProviderError) as caught:
                self.provider(handler).create({'model': 'gpt-6-astra', 'store': False})
            self.assertEqual(len(calls), 1)
            self.assertEqual(caught.exception.unknown, status in (408, 500))
            self.assertEqual(caught.exception.retryable, status == 429)
            self.assertNotIn('fixture-secret', str(caught.exception))
            self.assertIsNone(caught.exception.details)

    def test_timeout_and_wrong_model_are_uncertain(self):
        def timeout(request):
            raise httpx.ReadTimeout('fixture', request=request)
        for handler in (timeout, lambda req: httpx.Response(200, json={'model': 'another-model'}),
                        lambda req: httpx.Response(200, text='not-json')):
            with self.assertRaises(ProviderError) as caught:
                self.provider(handler).create({'model': 'gpt-6-astra', 'store': False})
            self.assertTrue(caught.exception.unknown)

    def test_error_category_retained_without_raw_message(self):
        provider = self.provider(lambda request: httpx.Response(404, json={
            'error': {'message': 'No endpoints matching data policy; fixture-secret'}}))
        with self.assertRaises(ProviderError) as caught:
            provider.create({'model': 'gpt-6-astra', 'store': False})
        self.assertEqual(caught.exception.details, {'category': 'data_policy'})
        self.assertNotIn('fixture-secret', str(caught.exception.details))

    def test_production_and_generic_keys_are_not_used_for_development(self):
        with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'fixture', 'OPENAI_API_KEY': 'fixture'}, clear=True):
            with self.assertRaises(ValueError):
                OpenRouterProvider()

    def test_router_usage_is_not_priced_with_direct_openai_tariff(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            try:
                initialize(store, 'fixture')
                register_tariff(store, {'id': 'fixture', 'valid_from': '2026-01-01T00:00:00Z',
                    'currency': 'USD', 'source_url': 'https://example.invalid/fixture',
                    'tariff': {**TARIFF, 'mapping_evidence': 'fixture'}})
                result = {'model': 'gpt-6-astra', 'status': 'completed', 'service_tier': 'default',
                          'output': [], 'usage': USAGE, '_billing_provider': 'openrouter'}
                Runtime(store, FixtureProvider([result])).tick()
                row = store.db.execute('SELECT * FROM model_attempt').fetchone()
                self.assertIsNone(row['estimated_cost_micro'])
                self.assertIsNone(row['price_version_id'])
                self.assertIsNone(row['cost_currency'])
            finally:
                store.close()


class KeyCheckTests(unittest.TestCase):
    def setUp(self):
        self.check = module('check_openrouter')

    def test_metadata_hides_identity_and_does_not_invent_account_balance(self):
        result = self.check.summarize({'data': {'is_management_key': False,
            'label': 'fixture-secret', 'creator_user_id': 'private-user', 'limit': 40,
            'limit_remaining': 39, 'usage': 1}})
        self.assertIsNone(result['account_credit_balance_usd'])
        self.assertEqual(result['key_limit_remaining_usd'], '39')
        self.assertNotIn('fixture-secret', json.dumps(result))
        self.assertNotIn('private-user', json.dumps(result))
        self.assertFalse(result['inference_tested'])

    def test_rejects_management_keys_unknown_privileges_and_nonfinite_metadata(self):
        for data in ({}, {'is_management_key': True}, {'is_management_key': False, 'is_provisioning_key': True},
                     {'is_management_key': False, 'usage': 'NaN'}, {'is_management_key': False, 'limit': True}):
            with self.subTest(data=data), self.assertRaises(self.check.CheckError):
                self.check.summarize({'data': data})

    def test_redirect_is_refused(self):
        with self.assertRaises(self.check.CheckError):
            self.check.NoRedirect().redirect_request(None, None, 302, '', {}, 'http://192.168.0.1')

    def test_only_get_key_is_requested(self):
        import io
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(b'{"data":{"is_management_key":false}}')
        with patch.object(self.check.urllib.request, 'build_opener', return_value=opener):
            self.check.query('fixture-secret')
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), 'GET')
        self.assertEqual(req.full_url, 'https://openrouter.ai/api/v1/key')
