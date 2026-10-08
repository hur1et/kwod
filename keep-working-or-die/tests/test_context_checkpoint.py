"""Durable agent handoffs: preserve files and never repeat completed actions."""
from pathlib import Path
import tempfile
import unittest

from kwod.config import Config
from kwod.provider import FixtureProvider
from kwod.runtime import Runtime, initialize
from kwod.store import Store
from test_runtime import Crash, response


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        initialize(self.store, 'Develop a series of digital artworks.')

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def reopen(self):
        self.store.close()
        self.store = Store(self.root)
        self.store.migrate()

    def test_artwork_survives_handoff_and_restart_without_old_tool_items(self):
        memory = 'Draft saved at works/study.svg. Next: review its composition. Do not recreate it.'
        first = response(('write_file', {'path': 'works/study.svg', 'content': '<svg>draft</svg>'}),
                         ('checkpoint', {'memory': memory}))
        first['output'].insert(0, {'type': 'reasoning', 'encrypted_content': 'old-opaque'})
        runtime = Runtime(self.store, FixtureProvider([first]))
        runtime.tick()
        self.assertEqual(runtime.tick(), 'ready')
        original_context = runtime.checkpoint()['context_ref']
        self.reopen()
        provider = FixtureProvider([response(response_id='second')])
        runtime = Runtime(self.store, provider)
        self.assertEqual(runtime.tick(), 'idle')
        sent = provider.requests[0]['input']
        self.assertIn('of 96000 bytes', provider.requests[0]['instructions'])
        self.assertEqual(sent[0]['content'], 'Develop a series of digital artworks.')
        self.assertIn(memory, sent[1]['content'])
        self.assertFalse(any('type' in item for item in sent))
        self.assertEqual((self.root / 'workspace/works/study.svg').read_text(), '<svg>draft</svg>')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM tool_call').fetchone()[0], 2)
        saved = self.store.archive.get(original_context)
        self.assertTrue(any(item.get('encrypted_content') == 'old-opaque' for item in saved))
        event = self.store.db.execute("SELECT payload_ref FROM trajectory_event WHERE kind='context_checkpoint'").fetchone()
        self.assertEqual(self.store.archive.get(event[0])['completed_context_ref'], original_context)

    def test_committed_handoff_resumes_after_crash_before_round_completion(self):
        def crash(phase):
            if phase == 'tool_result_persisted':
                raise Crash()
        runtime = Runtime(self.store, FixtureProvider([response(('checkpoint', {'memory': 'Continue reviewing draft.'}))]), hook=crash)
        runtime.tick()
        with self.assertRaises(Crash):
            runtime.tick()
        self.reopen()
        provider = FixtureProvider([response(response_id='second')])
        runtime = Runtime(self.store, provider)
        self.assertEqual(runtime.tick(), 'ready')
        self.assertEqual(provider.requests, [])
        self.assertEqual(runtime.tick(), 'idle')
        self.assertIn('Continue reviewing draft.', provider.requests[0]['input'][1]['content'])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM trajectory_event WHERE kind='context_checkpoint'").fetchone()[0], 1)

    def test_uncertain_memory_write_still_requires_recovery(self):
        def crash(phase):
            if phase == 'tool_executed':
                raise Crash()
        runtime = Runtime(self.store, FixtureProvider([response(('checkpoint', {'memory': 'Draft complete.'}))]), hook=crash)
        runtime.tick()
        with self.assertRaises(Crash):
            runtime.tick()
        self.reopen()
        provider = FixtureProvider([])
        self.assertEqual(Runtime(self.store, provider).tick(), 'recovery_required')
        self.assertEqual(provider.requests, [])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM trajectory_event WHERE kind='context_checkpoint'").fetchone()[0], 0)

    def test_handoff_before_another_call_is_rejected_without_losing_result(self):
        provider = FixtureProvider([response(('checkpoint', {'memory': 'Premature.'}),
                                            ('write_file', {'path': 'draft.txt', 'content': 'keep'})), response(response_id='second')])
        runtime = Runtime(self.store, provider)
        runtime.tick()
        runtime.tick()
        self.assertFalse((self.root / 'workspace/memory.md').exists())
        runtime.tick()
        outputs = [x for x in provider.requests[-1]['input'] if x.get('type') == 'function_call_output']
        self.assertEqual(len(outputs), 2)
        self.assertIn('checkpoint_must_be_last', outputs[0]['output'])
        self.assertEqual((self.root / 'workspace/draft.txt').read_text(), 'keep')

    def test_invalid_handoff_does_not_replace_memory(self):
        for memory in (' ', 'ä' * 8193):
            with self.subTest(memory_size=len(memory)):
                runtime = Runtime(self.store, FixtureProvider([response(('checkpoint', {'memory': memory}), response_id='invalid-' + str(len(memory)))]))
                runtime.tick()
                runtime.tick()
                self.assertFalse((self.root / 'workspace/memory.md').exists())
                self.assertEqual(runtime.checkpoint()['fresh_turn'], 0)

    def test_handoff_avoids_limit_from_completed_long_tool_round(self):
        runtime = Runtime(self.store, FixtureProvider([
            response(('write_file', {'path': 'draft.txt', 'content': 'x' * 3000}),
                     ('checkpoint', {'memory': 'Draft saved. Review draft.txt next.'})), response(response_id='second')]))
        runtime.config = Config(context_bytes=1000)
        runtime.tick()
        runtime.tick()
        self.assertEqual(runtime.tick(), 'idle')

    def test_full_archive_prevents_handoff_and_continuation(self):
        from unittest.mock import patch
        runtime = Runtime(self.store, FixtureProvider([response(('checkpoint', {'memory': 'Draft.'}))]))
        runtime.tick()
        with patch.object(self.store.archive, 'put', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                runtime.tick()
        self.assertEqual(runtime.state()['state'], 'recovery_required')
        self.assertFalse((self.root / 'workspace/memory.md').exists())


if __name__ == '__main__':
    unittest.main()
