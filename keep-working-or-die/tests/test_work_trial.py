import tempfile
from pathlib import Path
import unittest
import contextlib
import io
import json
import os
from unittest.mock import patch

from kwod.provider import FixtureProvider, ProviderError
from kwod.work_trial import run, MAX_CALLS, ALLOWED
from kwod.work_trial import main, error_details, check_provider
from test_runtime import response


class WorkTrialTests(unittest.TestCase):
    def test_earning_pilot_uses_own_objective_and_required_deliverables(self):
        from kwod.work_trial import EARNING_OBJECTIVE
        provider = FixtureProvider([
            response(('write_file', {'path': 'works/entscheidung.md', 'content': 'Choose a service'}),
                ('write_file', {'path': 'works/arbeitsprobe.md', 'content': 'Fictional sample'}),
                ('write_file', {'path': 'works/angebot.md', 'content': 'Untested offer'}),
                ('checkpoint', {'memory': 'Review offer and sample next.'})),
            response(('write_file', {'path': 'works/pruefung.md', 'content': 'Needs a buyer test'}), response_id='2'),
            response(response_id='3')])
        with tempfile.TemporaryDirectory() as root:
            result = run(root, provider, profile='earning')
            self.assertEqual(result['work_trial'], 'completed')
            self.assertEqual(result['profile'], 'earning')
            self.assertEqual(result['missing_files'], [])
            self.assertEqual(provider.requests[0]['input'][0]['content'], EARNING_OBJECTIVE)
            with self.assertRaises(FileExistsError):
                run(root, provider, profile='earning')
            with self.assertRaises(ValueError):
                run(root, provider, profile='earning', resume_rejected=True)

    def test_rejected_resume_preserves_original_attempt_and_total_limit(self):
        with tempfile.TemporaryDirectory() as root:
            run(root, FixtureProvider([ProviderError('openrouter_http_404')]))
            provider = FixtureProvider([response(('write_file', {'path': f'f{i}', 'content': 'x'}),
                response_id=str(i)) for i in range(6)])
            result = run(root, provider, resume_rejected=True)
            self.assertEqual(result['model_attempts'], 6)
            self.assertEqual(len(provider.requests), 5)
            self.assertIn('this is request 2 of 6', provider.requests[0]['instructions'])
            self.assertIn('4 further model requests', provider.requests[0]['instructions'])
            self.assertIn('This is the final request.', provider.requests[-1]['instructions'])
            self.assertEqual(result['requests_remaining'], 0)
            self.assertEqual(result['stop_reason'], 'trial_call_limit')
            self.assertEqual(result['attempts'][0]['error_code'], 'openrouter_http_404')
            with self.assertRaises(ValueError):
                run(root, provider, resume_rejected=True)

    def test_rejected_resume_refuses_uncertain_or_other_failures(self):
        for error in (ProviderError('timeout', unknown=True), ProviderError('openrouter_http_401')):
            with tempfile.TemporaryDirectory() as root:
                run(root, FixtureProvider([error]))
                provider = FixtureProvider([])
                with self.assertRaises(ValueError):
                    run(root, provider, resume_rejected=True)
                self.assertEqual(provider.requests, [])
    def test_provider_check_uses_only_fixed_gets_and_filters_account_data(self):
        import httpx
        calls = []
        def handler(request):
            calls.append((request.method, request.url.path))
            if request.url.path.endswith('/endpoints'):
                return httpx.Response(200, json={'data': {'endpoints': [{
                    'provider_name': 'OpenAI', 'tag': 'openai', 'supported_parameters': ['tools'],
                    'user_id': 'SECRET', 'message': 'SECRET'}]}})
            return httpx.Response(200, json={'data': [{'id': 'openai/gpt-6-astra'}]})
        with httpx.Client(base_url='https://openrouter.ai/api/v1/', transport=httpx.MockTransport(handler)) as client:
            result = check_provider(client)
        self.assertEqual(calls, [('GET', '/api/v1/models'), ('GET', '/api/v1/models/openai/gpt-6-astra/endpoints')])
        self.assertEqual(result['model_calls'], 0)
        self.assertTrue(result['checks'][0]['model_listed'])
        self.assertNotIn('SECRET', json.dumps(result))

    def test_resume_only_before_initialization_and_never_twice(self):
        with tempfile.TemporaryDirectory() as root:
            provider = FixtureProvider([response()])
            with patch('kwod.runtime.FileTools', side_effect=PermissionError(1, 'setgid denied')):
                with self.assertRaises(PermissionError):
                    run(root, provider)
            self.assertEqual(provider.requests, [])
            result = run(root, provider, resume_unstarted=True)
            self.assertEqual(result['model_attempts'], 1)
            self.assertTrue((Path(root) / 'trial-started').is_file())
            with self.assertRaises(ValueError):
                run(root, provider, resume_unstarted=True)
            self.assertEqual(len(provider.requests), 1)

    def test_resume_refuses_existing_provider_attempt(self):
        with tempfile.TemporaryDirectory() as root:
            provider = FixtureProvider([ProviderError('timeout', unknown=True)])
            run(root, provider)
            with self.assertRaises(ValueError):
                run(root, provider, resume_unstarted=True)
            self.assertFalse((Path(root) / 'resume-unstarted-used').exists())
            self.assertEqual(len(provider.requests), 1)

    def test_trial_uses_private_workspace_permissions(self):
        from kwod.tools import FileTools
        modes = []
        class CheckedFiles(FileTools):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                modes.append((self.directory_mode, self.file_mode))
        with tempfile.TemporaryDirectory() as root, patch('kwod.runtime.FileTools', CheckedFiles):
            run(root, FixtureProvider([response()]))
        self.assertEqual(modes, [(0o700, 0o600), (0o700, 0o600)])

    def test_diagnosis_never_calls_provider_or_reads_credential_contents(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'openrouter').write_text('SECRET-test-key')
            output = io.StringIO()
            with patch.dict(os.environ, {'KWOD_TRIAL_DIAGNOSE': '1',
                    'STATE_DIRECTORY': root, 'CREDENTIALS_DIRECTORY': root}), \
                 patch('kwod.work_trial.OpenRouterProvider') as provider, \
                 contextlib.redirect_stdout(output):
                main()
            provider.assert_not_called()
            report = json.loads(output.getvalue())
            self.assertTrue(all(row['ok'] for row in report['checks']))
            self.assertNotIn('SECRET-test-key', output.getvalue())
            self.assertFalse((Path(root) / 'trial-started').exists())
            self.assertFalse((Path(root) / 'data').exists())

    def test_error_details_exclude_exception_messages_and_paths(self):
        try:
            raise PermissionError(13, 'SECRET-message', '/private/SECRET-file')
        except PermissionError as exc:
            report = error_details(exc)
        self.assertEqual(report['errno'], 13)
        self.assertNotIn('SECRET', json.dumps(report))
        self.assertTrue(report['frames'])

    def test_work_handoff_review_and_no_second_paid_run(self):
        provider = FixtureProvider([
            response(('write_file', {'path': 'works/entwurf.md', 'content': 'Fixture artwork'}),
                     ('write_file', {'path': 'works/beschreibung.md', 'content': 'Fixture concept'}),
                     ('checkpoint', {'memory': 'Review the two files next.'})),
            response(('read_file', {'path': 'works/entwurf.md', 'offset': 0, 'max_bytes': 2000}), response_id='2'),
            response(('write_file', {'path': 'works/review.md', 'content': 'Fixture review'}), response_id='3'),
            response(response_id='4')])
        with tempfile.TemporaryDirectory() as root:
            result = run(root, provider)
            self.assertEqual(result['work_trial'], 'completed')
            self.assertEqual(result['model_attempts'], 4)
            self.assertEqual(result['handoffs'], 1)
            self.assertIn('this is request 2 of 6', provider.requests[1]['instructions'])
            self.assertIn('Review the two files next.', provider.requests[1]['input'][1]['content'])
            for sent in provider.requests:
                self.assertEqual({tool['name'] for tool in sent['tools']}, ALLOWED)
                self.assertEqual(sent['max_output_tokens'], 2048)
            self.assertTrue((Path(root) / 'report.json').exists())
            from kwod.store import Store
            store = Store(Path(root) / 'data')
            try:
                events = store.db.execute("SELECT payload_ref FROM trajectory_event WHERE kind='work_trial_request' ORDER BY id").fetchall()
                self.assertEqual(len(events), 4)
                for event, actual in zip(events, provider.requests):
                    record = store.archive.get(event[0])
                    self.assertEqual(store.archive.get(record['request_ref']), actual)
            finally:
                store.close()
            with self.assertRaises(FileExistsError):
                run(root, provider)
            self.assertEqual(len(provider.requests), 4)

    def test_request_limit_still_commits_last_tool_result(self):
        provider = FixtureProvider([response(('write_file', {'path': f'note{i}.md', 'content': 'done'}),
                                            response_id=str(i)) for i in range(MAX_CALLS + 1)])
        with tempfile.TemporaryDirectory() as root:
            result = run(root, provider)
            self.assertEqual(len(provider.requests), MAX_CALLS)
            self.assertEqual(result['work_trial'], 'incomplete')
            self.assertEqual(len(result['artifacts']), MAX_CALLS)

    def test_no_retry_on_provider_failure_or_timeout(self):
        for error in (ProviderError('rate_limit', retryable=True), ProviderError('timeout', unknown=True)):
            with self.subTest(error=str(error)), tempfile.TemporaryDirectory() as root:
                provider = FixtureProvider([error, response()])
                result = run(root, provider)
                self.assertEqual(len(provider.requests), 1)
                self.assertEqual(result['work_trial'], 'incomplete')

    def test_invented_terminal_call_is_never_executed(self):
        with tempfile.TemporaryDirectory() as root:
            provider = FixtureProvider([response(('terminal', {'command': 'anything', 'timeout_seconds': 1}))])
            result = run(root, provider)
            self.assertEqual(result['runtime_status'], 'recovery_required')
            self.assertEqual(result['artifacts'], {})


if __name__ == '__main__':
    unittest.main()
