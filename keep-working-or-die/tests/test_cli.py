import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class CLITests(unittest.TestCase):
    def test_separate_processes_resume_and_backup_restore(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = root / 'data'
            def run(*args, target=data):
                result = subprocess.run([sys.executable, '-m', 'kwod', '--data', str(target), *args],
                                        capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result.stdout
            run('init')
            fixture = str(Path(__file__).resolve().parent.parent / 'fixtures/development.json')
            run('run', '--fixture', fixture)
            run('run', '--fixture', fixture)
            run('run', '--fixture', fixture)
            self.assertIn('idle', run('inspect'))
            self.assertIn('Offline development', (data / 'workspace/memory.md').read_text())
            run('backup', str(root / 'backup'))
            run('restore', str(root / 'backup'), target=root / 'restored')
            self.assertIn('idle', run('inspect', target=root / 'restored'))
