"""Explicit integration gate; no Docker setup or image pull occurs during unit tests."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from kwod.executor import DockerExecutor
from kwod.store import Archive


@unittest.skipUnless(os.name == 'posix' and os.environ.get('KWOD_RUN_LINUX_ISOLATION') == '1'
                     and shutil.which('docker'), 'requires Linux, Docker and explicit isolation-test opt-in')
class LinuxExecutorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'workspace'
        self.workspace.mkdir(mode=0o770)
        self.workspace.chmod(0o770)
        self.archive = Archive(self.root / 'private/archive')
        self.executor = DockerExecutor(self.workspace, self.archive,
                                       os.environ.get('KWOD_EXECUTOR_IMAGE', 'kwod-executor:test'))

    def tearDown(self):
        self.temp.cleanup()

    def test_host_private_key_network_and_background_isolation(self):
        private_marker = self.root / 'private/key-canary'
        private_marker.write_text('HOST-SECRET')
        script = f'''python - <<'PY'
import os, pathlib, socket
assert os.getuid() == 65532
assert 'KWOD_DEV_OPENAI_API_KEY' not in os.environ
assert not pathlib.Path({str(private_marker)!r}).exists()
assert not pathlib.Path('/var/run/docker.sock').exists()
try:
    socket.create_connection(('1.1.1.1',443),timeout=1)
except OSError:
    pass
else:
    raise AssertionError('network escaped')
pathlib.Path('/workspace/persisted').write_text('works')
print('x' * 100000)
PY'''
        result = self.executor.execute('b' * 32, {'command': script, 'timeout_seconds': 15})
        self.assertTrue(result['ok'], result)
        self.assertTrue(result['stdout_truncated'])
        self.archive.verify(result['stdout_ref'])
        self.assertEqual((self.workspace / 'persisted').read_text(), 'works')
        self.assertEqual(private_marker.read_text(), 'HOST-SECRET')

    def test_timeout_removes_all_container_processes(self):
        result = self.executor.execute('c' * 32, {'command': 'sleep 30 & wait', 'timeout_seconds': 1})
        self.assertTrue(result['timed_out'])
        check = subprocess.run([self.executor.docker, 'ps', '-aq', '--filter', 'name=kwod-' + 'c' * 32],
                               capture_output=True, timeout=10, env=self.executor.environment())
        self.assertEqual(check.returncode, 0)
        self.assertEqual(check.stdout.strip(), b'')
