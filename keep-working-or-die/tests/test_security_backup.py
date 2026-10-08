from pathlib import Path
import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from kwod.backup import backup, restore
from kwod.executor import DockerExecutor
from kwod.projection import project, connect_readonly
from kwod.provider import FixtureProvider
from kwod.runtime import initialize, Runtime
from kwod.store import Store
from kwod.tools import FileTools, validate


class SecurityBackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / 'data')
        initialize(self.store, 'SECRET-objective')
        self.files = FileTools(self.store.root / 'workspace', self.store.archive)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_traversal_windows_drives_and_device_paths(self):
        for path in ('../private/state.sqlite', '/etc/passwd', 'C:/Users/key', 'a/../../b',
                     'a\\b', '//server/share', 'x:stream', '', 'NUL', 'CON.txt', 'name.', 'name '):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.files.path(path)

    def test_symlink_rejected(self):
        secret = self.root / 'secret'
        secret.write_text('SECRET')
        link = self.files.root / 'link'
        try:
            link.symlink_to(secret)
        except OSError:
            self.skipTest('Windows symlink privilege unavailable; Linux integration still required')
        with self.assertRaises(ValueError):
            self.files.execute('read_file', {'path': 'link', 'offset': 0, 'max_bytes': 10})

    def test_hardlink_rejected(self):
        secret = self.root / 'secret'
        secret.write_text('SECRET')
        os.link(secret, self.files.root / 'link')
        with self.assertRaises(ValueError):
            self.files.snapshot()

    def test_container_boundary_contract_and_no_secret_environment(self):
        executor = DockerExecutor(self.files.root, self.store.archive, 'kwod-executor:test')
        executor.docker = '/usr/bin/docker'
        with patch.dict(os.environ, {'KWOD_DEV_OPENAI_API_KEY': 'SECRET', 'DOCKER_HOST': 'attacker'}):
            command = executor.command('a' * 32)
            self.assertNotIn('KWOD_DEV_OPENAI_API_KEY', executor.environment())
            self.assertNotIn('DOCKER_HOST', executor.environment())
        for flag in ('--network=none', '--read-only', '--cap-drop=ALL', '--user=65532:65532',
                     '--pids-limit=64', '--memory=256m', '--pull=never'):
            self.assertIn(flag, command)
        mounts = [x for x in command if x.startswith('type=bind')]
        self.assertEqual(len(mounts), 1)
        self.assertIn(str(self.files.root), mounts[0])
        self.assertNotIn(str(self.store.private), ' '.join(command))
        self.assertNotIn('--privileged', command)

    def test_no_unisolated_terminal_fallback(self):
        executor = DockerExecutor(self.files.root, self.store.archive, None)
        with self.assertRaises(ValueError):
            executor.execute('a' * 32, {'command': 'echo unsafe', 'timeout_seconds': 1})

    def test_projection_preserves_provisioned_directory_permissions(self):
        target = self.store.root / 'public'
        target.mkdir(exist_ok=True)
        calls = []
        with patch('kwod.projection.os', SimpleNamespace(
                name='posix', chmod=lambda path, mode: calls.append((path, mode)))):
            project(self.store)
            project(self.store)
        self.assertEqual(calls, [(target / 'public.sqlite', 0o640)] * 2)
        db = connect_readonly(target / 'public.sqlite')
        try:
            self.assertIsNotNone(db.execute('SELECT payload FROM snapshot WHERE id=1').fetchone())
        finally:
            db.close()

    def test_public_projection_excludes_private_data_and_deduplicates(self):
        with self.store.transaction():
            self.store.event('tool_result', {'command': 'SECRET-command', 'result': 'SECRET-key',
                                           'public_title': 'SECRET-injection'})
            self.store.event('private_unknown_kind_SECRET', {'text': 'SECRET'})
        project(self.store)
        project(self.store)
        path = self.store.root / 'public/public.sqlite'
        db = connect_readonly(path)
        try:
            self.assertNotIn('SECRET', '\n'.join(db.iterdump()))
            self.assertEqual(db.execute('SELECT count(*) FROM public_event').fetchone()[0], 2)
            with self.assertRaises(sqlite3.OperationalError):
                db.execute('DELETE FROM public_event')
        finally:
            db.close()

    def test_backup_restore_and_tamper_detection(self):
        self.files.execute('write_file', {'path': 'memory.md', 'content': 'persistent memory'})
        spool = self.store.private / 'spool' / ('a' * 32)
        spool.mkdir(parents=True)
        (spool / 'stdout').write_bytes(b'recovered output')
        destination = backup(self.store, self.root / 'backup')
        restored = restore(destination, self.root / 'restored')
        self.assertEqual((restored / 'workspace/memory.md').read_text(), 'persistent memory')
        self.assertEqual((restored / 'private/spool' / ('a' * 32) / 'stdout').read_bytes(), b'recovered output')
        other = Store(restored)
        try:
            other.migrate()
            self.assertEqual(Runtime(other, FixtureProvider([])).state()['state'], 'ready')
            for row in other.db.execute('SELECT payload_ref FROM trajectory_event'):
                other.archive.get(row['payload_ref'])
        finally:
            other.close()
        (destination / 'workspace/memory.md').write_text('tampered')
        with self.assertRaises(ValueError):
            restore(destination, self.root / 'rejected')
        self.assertFalse((self.root / 'rejected').exists())

    def test_backup_must_not_include_itself(self):
        with self.assertRaises(ValueError):
            backup(self.store, self.store.root / 'backup')

    def test_restore_manifest_traversal_rejected(self):
        source = self.root / 'bad-backup'
        source.mkdir()
        (source / 'manifest.json').write_text(json.dumps({'files': {'private/state.sqlite': 'bad', '../secret': 'bad'}}))
        with self.assertRaises((ValueError, FileNotFoundError)):
            restore(source, self.root / 'target')
