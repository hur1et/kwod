from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from kwod.config import Config
from kwod.provider import FixtureProvider, ProviderError
from kwod.runtime import initialize, Runtime
from kwod.store import Store, worker_lock


def response(*calls, status='completed', response_id='fixture-1', **extra):
    return dict(id=response_id, model='gpt-6-astra', status=status, usage=None,
                output=[{'type': 'function_call', 'call_id': f'call-{i}', 'name': name,
                         'arguments': json.dumps(args)} for i, (name, args) in enumerate(calls)], **extra)


class Crash(BaseException):
    pass


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / 'data'
        self.store = Store(self.root)
        initialize(self.store, 'SECRET objective for development')

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def runtime(self, *responses, **kwargs):
        self.provider = FixtureProvider(responses)
        return Runtime(self.store, self.provider, **kwargs)

    def reopen(self):
        self.store.close()
        self.store = Store(self.root)
        self.store.migrate()

    def crash_at(self, phase):
        def crash(actual):
            if phase == actual:
                raise Crash()
        return crash

    def test_migrations_are_repeatable_without_birth(self):
        self.store.migrate()
        self.assertFalse(initialize(self.store, 'replacement'))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM schema_version').fetchone()[0], 3)
        row = self.store.db.execute('SELECT * FROM instance').fetchone()
        self.assertIsNone(row['born_at'])
        self.assertIsNone(row['inheritance_eur_micro'])
        self.assertEqual(self.store.db.execute('SELECT objective FROM checkpoint').fetchone()[0], 'SECRET objective for development')

    def test_write_sleep_reopen_wake_no_duplicate(self):
        wake = datetime.now(timezone.utc) + timedelta(hours=1)
        calls = response(('write_file', {'path': 'memory.md', 'content': 'remember'}),
                         ('sleep', {'wake_at': wake.isoformat()}))
        runtime = self.runtime(calls)
        runtime.tick()
        self.assertEqual(runtime.tick(), 'sleeping')
        self.reopen()
        runtime = self.runtime(response(response_id='fixture-2'), now=lambda: wake - timedelta(seconds=1))
        self.assertEqual(runtime.tick(), 'sleeping')
        self.assertEqual(len(self.provider.requests), 0)
        runtime.now = lambda: wake + timedelta(seconds=1)
        self.assertEqual(runtime.tick(), 'ready')
        self.assertEqual(runtime.tick(), 'idle')
        inputs = self.provider.requests[0]['input']
        self.assertEqual(len([x for x in inputs if x.get('type') == 'function_call_output']), 2)
        self.assertEqual((self.root / 'workspace/memory.md').read_text(), 'remember')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM tool_call').fetchone()[0], 2)

    def test_prepared_request_is_safe_to_send_after_restart(self):
        runtime = self.runtime(response(), hook=self.crash_at('prepared'))
        with self.assertRaises(Crash):
            runtime.tick()
        self.assertEqual(len(self.provider.requests), 0)
        self.reopen()
        runtime = self.runtime(response())
        self.assertEqual(runtime.tick(), 'idle')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0], 1)

    def test_sent_and_unpersisted_response_become_unknown(self):
        for phase in ('sent', 'response_received'):
            with self.subTest(phase=phase), tempfile.TemporaryDirectory() as temp:
                store = Store(temp)
                initialize(store, 'test')
                provider = FixtureProvider([response()])
                runtime = Runtime(store, provider, hook=self.crash_at(phase))
                with self.assertRaises(Crash):
                    runtime.tick()
                runtime.hook = lambda _: None
                self.assertEqual(runtime.tick(), 'recovery_required')
                attempt = store.db.execute('SELECT * FROM model_attempt').fetchone()
                self.assertEqual(attempt['status'], 'outcome_unknown')
                self.assertIsNone(attempt['estimated_cost_micro'])
                self.assertIsNone(attempt['usage_json'])
                store.close()

    def test_persisted_response_resumes_planned_tool(self):
        runtime = self.runtime(response(('write_file', {'path': 'x', 'content': 'once'})),
                               hook=self.crash_at('response_persisted'))
        with self.assertRaises(Crash):
            runtime.tick()
        self.reopen()
        runtime = self.runtime()
        self.assertEqual(runtime.tick(), 'ready')
        self.assertEqual((self.root / 'workspace/x').read_text(), 'once')
        self.assertEqual(len(self.provider.requests), 0)

    def test_crash_after_effect_never_repeats_tool(self):
        runtime = self.runtime(response(('write_file', {'path': 'x', 'content': 'once'})))
        runtime.tick()
        runtime.hook = self.crash_at('tool_executed')
        with self.assertRaises(Crash):
            runtime.tick()
        (self.root / 'workspace/x').write_text('operator-marker')
        self.reopen()
        runtime = self.runtime()
        self.assertEqual(runtime.tick(), 'recovery_required')
        self.assertEqual((self.root / 'workspace/x').read_text(), 'operator-marker')
        runtime.resolve('Reviewed file effect; continue in a new turn')
        self.assertEqual(runtime.state()['state'], 'ready')
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM trajectory_event WHERE kind='operator_intervention'").fetchone()[0], 1)

    def test_committed_result_not_executed_twice(self):
        runtime = self.runtime(response(('write_file', {'path': 'x', 'content': 'once'})))
        runtime.tick()
        runtime.hook = self.crash_at('tool_result_persisted')
        with self.assertRaises(Crash):
            runtime.tick()
        (self.root / 'workspace/x').write_text('later')
        self.reopen()
        runtime = self.runtime()
        self.assertEqual(runtime.tick(), 'ready')
        self.assertEqual((self.root / 'workspace/x').read_text(), 'later')

    def test_full_disk_before_request_prevents_send(self):
        runtime = self.runtime(response())
        with patch.object(self.store.archive, 'put', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                runtime.tick()
        self.assertEqual(len(self.provider.requests), 0)
        self.assertEqual(runtime.state()['state'], 'recovery_required')

    def test_full_disk_after_response_preserves_sent_marker(self):
        runtime = self.runtime(response())
        original = self.store.archive.put
        def put(value):
            if isinstance(value, dict) and value.get('id') == 'fixture-1':
                raise OSError('disk full')
            return original(value)
        with patch.object(self.store.archive, 'put', side_effect=put):
            with self.assertRaises(OSError):
                runtime.tick()
        self.assertEqual(runtime.tick(), 'recovery_required')
        self.assertEqual(self.store.db.execute('SELECT status FROM model_attempt').fetchone()[0], 'outcome_unknown')

    def test_incomplete_and_refusal_do_not_execute_calls(self):
        runtime = self.runtime(response(('write_file', {'path': 'x', 'content': 'no'}), status='incomplete'))
        self.assertEqual(runtime.tick(), 'recovery_required')
        self.assertFalse((self.root / 'workspace/x').exists())
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM tool_call').fetchone()[0], 0)

    def test_refusal_is_explicit(self):
        value = response()
        value['output'] = [{'type': 'message', 'content': [{'type': 'refusal', 'refusal': 'no'}]}]
        runtime = self.runtime(value)
        self.assertEqual(runtime.tick(), 'recovery_required')
        self.assertEqual(self.store.db.execute('SELECT status FROM model_attempt').fetchone()[0], 'refused')

    def test_invalid_arguments_return_error_without_effect(self):
        runtime = self.runtime(response(('write_file', {'path': 'x', 'content': 'no', 'unknown': True})))
        runtime.tick()
        runtime.tick()
        row = self.store.db.execute('SELECT * FROM tool_call').fetchone()
        self.assertEqual(row['status'], 'failed')
        self.assertFalse((self.root / 'workspace/x').exists())

    def test_unknown_timeout_not_retried(self):
        runtime = self.runtime(ProviderError('timeout', unknown=True))
        self.assertEqual(runtime.tick(), 'recovery_required')
        runtime.tick()
        self.assertEqual(len(self.provider.requests), 1)

    def test_429_backoff_and_retry_is_separate_attempt(self):
        current = datetime.now(timezone.utc)
        runtime = self.runtime(ProviderError('rate_limit_exceeded', retryable=True), response(), now=lambda: current)
        self.assertEqual(runtime.tick(), 'provider_unavailable')
        runtime.tick()
        self.assertEqual(len(self.provider.requests), 1)
        runtime.now = lambda: current + timedelta(minutes=1)
        self.assertEqual(runtime.tick(), 'idle')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0], 2)

    def test_quota_does_not_mean_death_or_automatic_retry(self):
        runtime = self.runtime(ProviderError('insufficient_quota'))
        self.assertEqual(runtime.tick(), 'provider_unavailable')
        self.assertIsNone(runtime.state()['wake_at'])
        self.assertEqual(runtime.tick(), 'provider_unavailable')

    def test_no_local_balance_required(self):
        runtime = self.runtime(response())
        self.assertEqual(runtime.tick(), 'idle')
        self.assertEqual(len(self.provider.requests), 1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM asset_observation').fetchone()[0], 0)

    def test_worker_lock_excludes_second_worker(self):
        with worker_lock(self.root):
            with self.assertRaises(RuntimeError):
                self.runtime().tick()

    def test_archive_integrity_and_append_only(self):
        ref = self.store.archive.put({'test': 'payload'})
        (self.store.archive.path / ref).write_bytes(b'corrupt')
        with self.assertRaises(OSError):
            self.store.archive.get(ref)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.db.execute("DELETE FROM trajectory_event")
        self.store.db.rollback()

    def test_context_limit_stops_before_request(self):
        runtime = self.runtime(response())
        runtime.config = Config(context_bytes=1)
        self.assertEqual(runtime.tick(), 'recovery_required')
        self.assertEqual(len(self.provider.requests), 0)

    def test_decision_and_activity_are_private_and_typed(self):
        runtime = self.runtime(response(('record_decision', {'action': 'SECRET-action',
            'brief_reason': 'SECRET-reason', 'expectations': None}), ('set_activity', {'category': 'coding'})))
        runtime.tick()
        runtime.tick()
        row = self.store.db.execute('SELECT * FROM decision_record').fetchone()
        self.assertEqual(row['action'], 'SECRET-action')
        self.assertIsNone(row['expectations_json'])
        self.assertEqual(runtime.checkpoint()['activity'], 'coding')


    def test_encrypted_reasoning_and_call_id_preserved(self):
        value = response(('clock', {}))
        value['output'].insert(0, {'type': 'reasoning', 'id': 'rs_1', 'summary': [], 'encrypted_content': 'opaque'})
        runtime = self.runtime(value, response(response_id='fixture-2'))
        runtime.tick()
        runtime.tick()
        runtime.tick()
        sent = self.provider.requests[-1]
        self.assertEqual(sent['include'], ['reasoning.encrypted_content'])
        self.assertFalse(sent['store'])
        self.assertIn(value['output'][0], sent['input'])
        self.assertEqual([x['call_id'] for x in sent['input'] if x.get('type') == 'function_call_output'], ['call-0'])


if __name__ == '__main__':
    unittest.main()
