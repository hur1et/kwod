from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from kwod.executor import DockerExecutor
from kwod.store import Archive


class ExecutorLifecycleTests(unittest.TestCase):
    def test_archive_failure_retains_observed_output_in_private_spool(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Archive(Path(temp) / 'archive')
            executor = DockerExecutor(temp, archive, 'kwod-executor:test')
            executor.docker = 'docker'
            class Process:
                returncode = 0
                def communicate(self, data, timeout):
                    pass
                def poll(self):
                    return 0
            def launch(*_, **kwargs):
                kwargs['stdout'].write(b'observed before disk failure')
                return Process()
            with patch('kwod.executor.subprocess.Popen', side_effect=launch), patch.object(executor, 'cleanup'), patch.object(archive, 'put_file', side_effect=OSError('full archive')):
                with self.assertRaises(OSError):
                    executor.execute('f' * 32, {'command': 'fixture', 'timeout_seconds': 1})
            self.assertEqual((Path(temp) / 'spool' / ('f' * 32) / 'stdout').read_bytes(), b'observed before disk failure')

    def test_timeout_kills_container_and_archives_full_streams(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Archive(Path(temp) / 'archive')
            executor = DockerExecutor(temp, archive, 'kwod-executor:test')
            executor.docker = 'docker'
            class Process:
                returncode = None
                def communicate(self, data, timeout):
                    raise subprocess.TimeoutExpired('docker', timeout)
                def kill(self):
                    self.returncode = -9
                def wait(self, timeout):
                    return self.returncode
                def poll(self):
                    return self.returncode
            def launch(*_, **kwargs):
                kwargs['stdout'].write(b'x' * 100000)
                kwargs['stderr'].write(b'full stderr')
                return Process()
            with patch('kwod.executor.subprocess.Popen', side_effect=launch), patch.object(executor, 'cleanup') as cleanup:
                result = executor.execute('d' * 32, {'command': 'fixture', 'timeout_seconds': 1})
            self.assertTrue(result['timed_out'])
            self.assertEqual(cleanup.call_count, 2)
            self.assertEqual(result['stdout_bytes'], 100000)
            self.assertTrue(result['stdout_truncated'])
            self.assertEqual((archive.path / result['stdout_ref']).read_bytes(), b'x' * 100000)

    def test_cleanup_failure_is_not_reported_as_success(self):
        with tempfile.TemporaryDirectory() as temp:
            executor = DockerExecutor(temp, Archive(Path(temp) / 'archive'), 'kwod-executor:test')
            executor.docker = 'docker'
            with patch('kwod.executor.subprocess.run', return_value=subprocess.CompletedProcess([], 1, b'', b'daemon unreachable')):
                with self.assertRaises(RuntimeError):
                    executor.cleanup('e' * 32)
