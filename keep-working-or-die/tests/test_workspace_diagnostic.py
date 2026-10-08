import importlib.util
import tempfile
import unittest
from pathlib import Path
from kwod.store import Store
from kwod.runtime import initialize
from kwod.config import Config


class WorkspaceDiagnosticTests(unittest.TestCase):
    def test_probe_reports_actual_access_without_returning_content_or_mutating_store(self):
        source=Path(__file__).parents[1]/'deploy/diagnose_workspace.py'
        spec=importlib.util.spec_from_file_location('workspace_diagnostic',source)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'prod'; store=Store(root,mode='prod'); initialize(store,'SECRET mission',Config(mode='prod'))
            rights=root/'workspace/RIGHTS_AND_LIMITS.md'; rights.write_text('SECRET rights')
            before=store.db.total_changes
            mode=(root/'workspace').stat().st_mode
            result=module.probe(root)
            self.assertTrue(result['files']['RIGHTS_AND_LIMITS.md']['readable'])
            self.assertEqual(result['files']['RIGHTS_AND_LIMITS.md']['installed_rule'],('ALLOW','none'))
            self.assertFalse(result['files']['MISSION.md']['readable'])
            self.assertNotIn('SECRET',str(result))
            self.assertEqual(mode,(root/'workspace').stat().st_mode)
            self.assertEqual(before,store.db.total_changes)
            store.close()
