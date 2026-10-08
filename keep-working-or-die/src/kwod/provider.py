from __future__ import annotations

import copy
import os


class ProviderError(Exception):
    def __init__(self, code, *, unknown=False, retryable=False, details=None):
        super().__init__(code)
        self.code = code
        self.unknown = unknown
        self.retryable = retryable
        self.details = details


class OpenAIProvider:
    def __init__(self):
        from openai import OpenAI
        import httpx
        key = os.environ.get('KWOD_DEV_OPENAI_API_KEY')
        if not key:
            raise ValueError('KWOD_DEV_OPENAI_API_KEY is required; use separate development billing')
        # Explicit URL prevents inherited proxy/base-url settings changing the provider.
        self.client = OpenAI(api_key=key, base_url='https://api.openai.com/v1', max_retries=0,
                             timeout=90, http_client=httpx.Client(trust_env=False, timeout=90))

    def create(self, request):
        from openai import APIConnectionError, APIStatusError
        try:
            response = self.client.responses.create(**request)
            result = response.model_dump(mode='json')
            result['_request_id'] = response._request_id
            return result
        except APIConnectionError as exc:
            raise ProviderError('transport_unknown', unknown=True) from exc
        except APIStatusError as exc:
            body = exc.body if isinstance(exc.body, dict) else {}
            error = body.get('error', body)
            code = error.get('code') or str(exc.status_code)
            # A 429 is not evidence that the account has no money.
            retryable = exc.status_code == 429 and code not in ('insufficient_quota', 'credit_balance_exhausted')
            raise ProviderError(str(code), unknown=exc.status_code >= 500,
                                retryable=retryable, details=body) from exc


class OpenRouterProvider:
    """Development adapter; never reads the production credential file."""
    def __init__(self):
        import httpx
        key = os.environ.get('KWOD_DEV_OPENROUTER_API_KEY')
        if not key:
            raise ValueError('KWOD_DEV_OPENROUTER_API_KEY required; development billing must be separate')
        self.client = httpx.Client(base_url='https://openrouter.ai/api/v1/',
                                   headers={'Authorization': 'Bearer ' + key},
                                   trust_env=False, follow_redirects=False, timeout=90)

    def create(self, request):
        import httpx
        if request.get('model') != 'gpt-6-astra' or request.get('store') is not False:
            raise ProviderError('unsupported_request')
        if request.get('previous_response_id') is not None or any(k in request for k in ('models', 'route', 'provider', 'plugins')):
            raise ProviderError('unsupported_routing_or_state')
        payload = copy.deepcopy(request)
        payload['model'] = 'openai/gpt-6-astra'
        # Router metadata does not advertise these direct-API parameters.
        # Runtime still executes every tool serially; it accepts multiple calls.
        payload.pop('parallel_tool_calls', None)
        payload.pop('service_tier', None)
        payload['provider'] = {'only': ['openai'], 'allow_fallbacks': False, 'require_parameters': True}
        try:
            response = self.client.post('responses', json=payload)
        except httpx.TransportError as exc:
            raise ProviderError('transport_unknown', unknown=True) from exc
        if not 200 <= response.status_code < 300:
            # Do not archive untrusted error bodies; they may echo credentials.
            status = response.status_code
            diagnostic = 'unclassified'
            try:
                message = response.json().get('error', {}).get('message', '')
                if isinstance(message, str):
                    lowered = message.lower()
                    for needle, label in (('data policy', 'data_policy'), ('data region', 'data_region'),
                            ('support tool', 'tool_support'), ('parameter', 'parameter_support'),
                            ('no endpoints', 'no_matching_endpoints'), ('no allowed providers', 'no_allowed_providers')):
                        if needle in lowered:
                            diagnostic = label
                            break
            except (ValueError, AttributeError, TypeError):
                pass
            raise ProviderError('openrouter_http_' + str(status),
                                retryable=status == 429, unknown=status >= 500 or status == 408,
                                details={'category': diagnostic} if diagnostic != 'unclassified' else None)
        try:
            result = response.json()
        except ValueError as exc:
            raise ProviderError('invalid_response', unknown=True) from exc
        if not isinstance(result, dict) or result.get('model') not in ('openai/gpt-6-astra', 'gpt-6-astra'):
            raise ProviderError('unexpected_response_model', unknown=True)
        result['_request_id'] = response.headers.get('x-request-id')
        result['_billing_provider'] = 'openrouter'
        return result


class ProductionOpenRouterProvider(OpenRouterProvider):
    """Production key comes exclusively from the service credential, never dev env."""
    def __init__(self):
        from pathlib import Path
        import httpx
        from .safety import stopped
        if stopped(): raise ValueError('safety_paused')
        directory=os.environ.get('CREDENTIALS_DIRECTORY')
        if not directory: raise ValueError('production_service_credential_required')
        key=(Path(directory)/'openrouter.key').read_text().strip()
        if not key: raise ValueError('empty_production_credential')
        self.client=httpx.Client(base_url='https://openrouter.ai/api/v1/',
            headers={'Authorization':'Bearer '+key},trust_env=False,follow_redirects=False,timeout=90)

class FixtureProvider:
    """Offline test input only; never models a funded production life."""
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def create(self, request):
        self.requests.append(copy.deepcopy(request))
        try:
            response = next(self.responses)
        except StopIteration as exc:
            raise ProviderError('fixture_exhausted') from exc
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)
