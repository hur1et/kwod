import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch
import contextlib
import io

from fastapi.testclient import TestClient

from kwod.api import create_app
from kwod.provider import FixtureProvider, ProviderError
from kwod.store import Store, atomic_write
from kwod.work_monitor import collect, observe, public_snapshot, service_state, RUNS
from kwod.work_trial import run
from test_runtime import response

ROOT = Path(__file__).parents[1]


def launcher():
    spec = importlib.util.spec_from_file_location('monitor_launcher', ROOT / 'deploy/run_work_trial.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def completed():
    return FixtureProvider([
        response(('write_file', {'path': 'works/entscheidung.md', 'content': 'SECRET buyer'}),
                 ('write_file', {'path': 'works/arbeitsprobe.md', 'content': 'SECRET draft'}),
                 ('write_file', {'path': 'works/angebot.md', 'content': 'SECRET offer'}),
                 ('checkpoint', {'memory': 'SECRET handoff'})),
        response(('write_file', {'path': 'works/pruefung.md', 'content': 'SECRET review'}), response_id='2'),
        response(response_id='3')])


class MonitorTests(unittest.TestCase):
    def test_completed_run_budget_files_and_private_independence(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / RUNS['pilot02'][0]
            provider = completed()
            run(root, provider, profile='earning')
            (root / 'report.json').write_text('SECRET malformed report; must not be read')
            snapshot = collect(base, lambda _: 'inactive')
            row = snapshot['runs'][1]
            self.assertEqual((row['phase'], row['attempts'], row['remaining'], row['handoffs']),
                             ('completed', 3, 3, 1))
            self.assertTrue(all(f['present'] for f in row['files']))
            self.assertNotIn('SECRET', json.dumps(snapshot))
            self.assertEqual(snapshot['runs'][0]['phase'], 'not_started')
            public = base / 'public'
            atomic_write(public / 'work-runs.json', json.dumps(snapshot).encode())
            # HTTP observer no longer has any accessible private source directory.
            (root / 'data').rename(root / 'hidden')
            with TestClient(create_app(public / 'missing-main.sqlite')) as client:
                result = client.get('/api/v1/work-runs')
                self.assertEqual(result.status_code, 200)
                self.assertEqual(result.json()['runs'][1]['phase'], 'completed')
                self.assertNotIn('SECRET', result.text)
                self.assertEqual(client.post('/api/v1/work-runs').status_code, 405)
                self.assertEqual(client.get('/api/v1/work-runs/pilot02/works/angebot.md').status_code, 404)
                page = client.get('/')
                self.assertIn('ARBEITSLÄUFE', page.text)

    def test_live_request_failed_attempt_and_read_only_collection(self):
        with tempfile.TemporaryDirectory() as temp:
            snapshots = []
            class Provider:
                def create(self, request):
                    snapshots.append(observe(temp, 'trial01', 'active'))
                    raise ProviderError('SECRET error')
            run(temp, Provider())
            self.assertEqual(snapshots[0]['phase'], 'model')
            self.assertEqual(snapshots[0]['remaining'], 5)
            database = Path(temp) / 'data/private/state.sqlite'
            before = database.read_bytes()
            stopped = observe(temp, 'trial01', 'inactive')
            self.assertEqual(stopped['phase'], 'incomplete')
            self.assertEqual(stopped['attempts'], 1)
            self.assertNotIn('SECRET', json.dumps(stopped))
            self.assertEqual(database.read_bytes(), before)
            never = FixtureProvider([])
            with self.assertRaises(FileExistsError):
                run(temp, never)
            self.assertEqual(never.requests, [])

    def test_exhausted_incomplete_and_uncertain_are_not_completed(self):
        for error, expected in [(ProviderError('timeout', unknown=True), 'needs_review'),
                                (None, 'budget_exhausted')]:
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp:
                provider = FixtureProvider([error] if error else [response(
                    ('write_file', {'path': 'n.txt', 'content': 'x'}), response_id=str(i)) for i in range(6)])
                run(temp, provider)
                row = observe(temp, 'trial01', 'inactive')
                self.assertEqual(row['phase'], expected)
                self.assertTrue(row['restart_blocked'])

    def test_missing_corrupt_stale_and_malicious_projection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'work-runs.json'
            self.assertFalse(public_snapshot(path)['available'])
            data = collect(Path(temp), lambda _: 'inactive')
            data['as_of'] = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
            for row in data['runs']:
                row.update(label='SECRET', phase='SECRET', service='SECRET', runtime_status='SECRET',
                           extra='SECRET', remaining='SECRET')
                row['files'].append({'name': 'SECRET', 'present': True})
            path.write_text(json.dumps(data))
            safe = public_snapshot(path)
            self.assertTrue(safe['stale'])
            self.assertEqual(len(safe['runs']), 3)
            self.assertNotIn('SECRET', json.dumps(safe))
            for contents in ('{', '[]', 'null', '{"as_of":"SECRET"}', 'x' * 32769):
                path.write_text(contents)
                self.assertFalse(public_snapshot(path)['available'])

    def test_state_change_during_collection_is_not_reported_as_live(self):
        with tempfile.TemporaryDirectory() as temp:
            run(Path(temp) / RUNS['trial01'][0], FixtureProvider([response()]))
            state = iter(['active', 'inactive', 'inactive', 'inactive', 'inactive', 'inactive'])
            snapshot = collect(Path(temp), lambda _: next(state))
            self.assertEqual(snapshot['runs'][0]['service'], 'unknown')
            self.assertEqual(snapshot['runs'][0]['phase'], 'unavailable')

    def test_corrupt_private_db_and_empty_marked_run_are_visible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'trial-started').touch()
            self.assertEqual(observe(root, 'trial01', 'inactive')['phase'], 'needs_review')
            database = root / 'data/private/state.sqlite'
            database.parent.mkdir(parents=True)
            database.write_text('SECRET not sqlite')
            self.assertEqual(observe(root, 'trial01', 'inactive')['phase'], 'unavailable')
            inspected = launcher().inspect_saved(root)
            self.assertFalse(inspected['saved_database_readable'])
            self.assertTrue(inspected['inspection_required'])
            self.assertNotIn('SECRET', json.dumps(inspected))

    def test_status_calls_only_systemctl_show_without_start_stop_or_key_access(self):
        module = launcher()
        with patch.object(module.os, 'geteuid', return_value=0, create=True), \
             patch.object(module.sys, 'argv', ['launcher', 'unused', 'unused', '--status', '--pilot']), \
             patch.object(module, 'inspect_saved', return_value={}) as inspect, \
             patch.object(module.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='inactive\n')) as process, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            module.main()
        process.assert_called_once()
        self.assertEqual(process.call_args.args[0], ['systemctl', 'show', 'kwod-work-pilot-02.service', '--property=ActiveState', '--value'])
        inspect.assert_called_once_with('/var/lib/kwod-work-pilot-02', pilot=True)
        self.assertEqual(json.loads(output.getvalue())['work_trial'], 'status_inspection')

    def test_offline_fixture_completes_without_real_provider_and_is_one_shot(self):
        from kwod.work_monitor_fixture import provider
        with tempfile.TemporaryDirectory() as temp, \
             patch('kwod.work_monitor_fixture.time.sleep'), \
             patch('kwod.work_trial.OpenRouterProvider') as live:
            fixture = provider()
            result = run(temp, fixture)
            self.assertEqual(result['work_trial'], 'completed')
            self.assertEqual(observe(temp, 'offlinecheck', 'inactive')['phase'], 'completed')
            with self.assertRaises(FileExistsError):
                run(temp, fixture)
            self.assertEqual(len(fixture.requests), 3)
            live.assert_not_called()

    def test_offline_launcher_has_no_credential_and_forces_network_isolation(self):
        module = launcher()
        spec = importlib.util.spec_from_file_location('monitor_bundle', ROOT / 'deploy/bundle.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        original_temporary = tempfile.TemporaryDirectory
        original_is_file = Path.is_file
        with original_temporary() as temp:
            bundle = builder.build(ROOT, Path(temp) / 'source.tar.gz')
            def is_file(path):
                if str(path).replace('\\', '/') == '/opt/kwod/current/.venv/bin/python':
                    return True
                return original_is_file(path)
            with patch.object(module.os, 'geteuid', return_value=0, create=True), \
                 patch.object(module.sys, 'argv', ['launcher', bundle['bundle'], bundle['sha256'], '--monitor-check']), \
                 patch.object(module.tempfile, 'TemporaryDirectory', side_effect=lambda **_: original_temporary(dir=temp)), \
                 patch.object(Path, 'is_file', is_file), \
                 patch.object(module.subprocess, 'run') as process, \
                 contextlib.redirect_stdout(io.StringIO()):
                module.main()
            args = process.call_args.args[0]
            self.assertIn('--unit=kwod-work-monitor-check', args)
            self.assertIn('PrivateNetwork=yes', args)
            self.assertIn('KillMode=control-group', args)
            self.assertFalse(any('LoadCredential=' in item for item in args))
            self.assertIn('kwod.work_monitor_fixture', args[-1])

    def test_pending_tool_after_stop_needs_review_and_file_links_are_not_read(self):
        with tempfile.TemporaryDirectory() as temp:
            run(temp, completed(), profile='earning')
            store = Store(Path(temp) / 'data')
            with store.transaction():
                store.db.execute("UPDATE runtime_state SET state='ready'")
                store.db.execute("UPDATE tool_call SET status='running' WHERE rowid=(SELECT max(rowid) FROM tool_call)")
            store.close()
            self.assertEqual(observe(temp, 'pilot02', 'active')['phase'], 'tools')
            self.assertEqual(observe(temp, 'pilot02', 'inactive')['phase'], 'needs_review')
            from kwod.work_monitor import regular_file
            with patch.object(Path, 'is_symlink', return_value=True), patch.object(Path, 'stat') as info:
                with self.assertRaises(ValueError):
                    regular_file(Path(temp), 'data/workspace/memory.md')
                info.assert_not_called()

    def test_systemctl_failure_is_unknown_and_stop_failure_is_not_success(self):
        with patch('kwod.work_monitor.subprocess.run', side_effect=subprocess.CalledProcessError(1, 'systemctl')):
            self.assertEqual(service_state('fixed.service'), 'unknown')
        module = launcher()
        with patch.object(module.subprocess, 'run', return_value=SimpleNamespace(returncode=1, stdout='not-found\n')):
            with self.assertRaises(RuntimeError):
                module.stop_trial()

    def test_stop_terminates_real_local_fixture_process_and_restart_spends_nothing(self):
        # systemd itself requires Ubuntu. Here its stop adapter controls a real
        # local child, interrupted after the runtime persisted a sent request.
        with tempfile.TemporaryDirectory() as temp:
            code = '''import sys,time
from kwod.work_trial import run
class Provider:
 def create(self, request):
  print('WAITING', flush=True)
  time.sleep(60)
run(sys.argv[1], Provider())
'''
            env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'))
            child = subprocess.Popen([sys.executable, '-u', '-c', code, temp],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            try:
                import threading
                ready = threading.Event()
                def read_ready():
                    for line in child.stdout:
                        if line.strip() == 'WAITING':
                            ready.set()
                            return
                thread = threading.Thread(target=read_ready, daemon=True)
                thread.start()
                self.assertTrue(ready.wait(10), 'fixture did not reach pending request')
                self.assertEqual(observe(temp, 'trial01', 'active')['phase'], 'model')
                module = launcher()
                def systemctl(args, **kwargs):
                    if args[1] == 'stop':
                        child.terminate()
                        child.wait(timeout=5)
                        return SimpleNamespace(returncode=0, stdout='')
                    return SimpleNamespace(returncode=0, stdout='inactive\n')
                with patch.object(module.subprocess, 'run', side_effect=systemctl):
                    self.assertEqual(module.stop_trial(), 'stopped_or_not_running')
                self.assertIsNotNone(child.poll())
                database = Path(temp) / 'data/private/state.sqlite'
                before = {p: p.read_bytes() for p in (database, Path(str(database) + '-wal')) if p.exists()}
                row = observe(temp, 'trial01', 'inactive')
                self.assertEqual((row['phase'], row['attempts']), ('needs_review', 1))
                self.assertEqual({p: p.read_bytes() for p in before}, before)
                provider = FixtureProvider([])
                with self.assertRaises(FileExistsError):
                    run(temp, provider)
                self.assertEqual(provider.requests, [])
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=5)
                child.stdout.close()
                child.stderr.close()
