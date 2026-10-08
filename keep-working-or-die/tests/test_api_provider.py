from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from openai import OpenAI

from kwod.api import create_app
from kwod.projection import project
from kwod.provider import OpenAIProvider, ProviderError
from kwod.runtime import initialize
from kwod.store import Store


class APITests(unittest.TestCase):
    def test_public_api_leakage_pagination_staleness_and_worker_independence(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            initialize(store, 'SECRET raw prompt')
            with store.transaction():
                store.event('tool_result', {'stdout': 'SECRET output', 'path': 'SECRET/private.sqlite',
                                            'decision': '<script>SECRET</script>'})
            project(store)
            public_path = Path(temp) / 'public/public.sqlite'
            store.close()
            # Remove private DB access entirely; the observer still answers.
            (Path(temp) / 'private/state.sqlite').rename(Path(temp) / 'private/hidden.sqlite')
            with TestClient(create_app(public_path)) as client:
                page = client.get('/')
                self.assertEqual(page.status_code, 200)
                self.assertIn('<h1>kwod</h1>', page.text)
                self.assertIn("frame-ancestors 'none'", page.headers['content-security-policy'])
                self.assertNotIn('SECRET', page.text)
                for path in ('/healthz', '/api/v1/status', '/api/v1/events', '/api/v1/assets', '/api/v1/net-worth'):
                    r = client.get(path)
                    self.assertEqual(r.status_code, 200)
                    self.assertNotIn('SECRET', r.text)
                    self.assertNotIn('<script>', r.text)
                self.assertIsNone(client.get('/api/v1/status').json()['net_worth_eur_micro'])
                first = client.get('/api/v1/events?limit=1').json()
                second = client.get('/api/v1/events', params={'after_id': first['next_cursor']}).json()
                self.assertGreater(second['events'][0]['id'], first['next_cursor'])
                self.assertEqual(client.get('/api/v1/events?limit=501').status_code, 422)
                self.assertEqual(client.get('/api/v1/events?after_id=-1').status_code, 422)
                self.assertEqual(client.get('/api/v1/net-worth?after=bad').status_code, 422)
                self.assertEqual(client.post('/api/v1/status', json={}).status_code, 405)
                self.assertEqual(client.get('/private/state.sqlite').status_code, 404)
            import sqlite3
            db = sqlite3.connect(public_path)
            payload = json.loads(db.execute('SELECT payload FROM snapshot').fetchone()[0])
            payload['as_of'] = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
            db.execute('UPDATE snapshot SET payload=?', (json.dumps(payload),))
            db.commit()
            db.close()
            with TestClient(create_app(public_path)) as client:
                self.assertTrue(client.get('/api/v1/status').json()['stale'])
                self.assertEqual(client.get('/api/v1/status').json()['worker_observation'], 'unknown')

    def test_missing_projection_returns_generic_503(self):
        with tempfile.TemporaryDirectory() as temp, TestClient(create_app(Path(temp) / 'SECRET.sqlite')) as client:
            r = client.get('/healthz')
            self.assertEqual(r.status_code, 503)
            self.assertNotIn('SECRET', r.text)


class ProviderTests(unittest.TestCase):
    def provider(self, handler):
        p = OpenAIProvider.__new__(OpenAIProvider)
        p.client = OpenAI(api_key='offline-secret', base_url='https://api.openai.com/v1', max_retries=0,
                          http_client=httpx.Client(transport=httpx.MockTransport(handler)))
        self.addCleanup(p.client.close)
        return p

    def test_actual_sdk_serialization_and_raw_usage_without_network(self):
        captured = []
        def handler(request):
            captured.append(json.loads(request.content))
            return httpx.Response(200, headers={'x-request-id': 'request-fixture'}, json={
                'id': 'resp_fixture', 'object': 'response', 'created_at': 1,
                'status': 'completed', 'model': 'gpt-6-astra', 'output': [],
                'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120,
                          'input_tokens_details': {'cached_tokens': 10, 'novel_cache_field': 4},
                          'output_tokens_details': {'reasoning_tokens': 15}}})
        provider = self.provider(handler)
        result = provider.create({'model': 'gpt-6-astra', 'input': [{'role': 'user', 'content': 'fixture'}],
                                  'include': ['reasoning.encrypted_content'], 'store': False,
                                  'reasoning': {'effort': 'low'}, 'max_output_tokens': 4096})
        self.assertEqual(result['_request_id'], 'request-fixture')
        self.assertEqual(result['usage']['input_tokens_details']['novel_cache_field'], 4)
        self.assertEqual(captured[0]['model'], 'gpt-6-astra')
        self.assertFalse(captured[0]['store'])

    def test_status_classification_without_sdk_retries(self):
        for status, code, retryable, unknown in ((401, 'invalid_api_key', False, False),
                                                (429, 'insufficient_quota', False, False),
                                                (429, 'rate_limit_exceeded', True, False),
                                                (500, 'server_error', False, True)):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status, json={'error': {'code': code, 'message': 'fixture'}})
            provider = self.provider(handler)
            with self.subTest(code=code), self.assertRaises(ProviderError) as error:
                provider.create({'model': 'gpt-6-astra', 'input': 'fixture'})
            self.assertEqual(error.exception.code, code)
            self.assertEqual(error.exception.retryable, retryable)
            self.assertEqual(error.exception.unknown, unknown)
            self.assertEqual(len(calls), 1)

    def test_timeout_is_unknown(self):
        def handler(request):
            raise httpx.ReadTimeout('fixture', request=request)
        provider = self.provider(handler)
        with self.assertRaises(ProviderError) as error:
            provider.create({'model': 'gpt-6-astra', 'input': 'fixture'})
        self.assertTrue(error.exception.unknown)

    def test_development_key_required_not_inherited_from_generic_key(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'not-a-development-key'}, clear=True):
            with self.assertRaises(ValueError):
                OpenAIProvider()
