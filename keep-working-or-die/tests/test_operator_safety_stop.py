import importlib.util
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

class OperatorSafetyStopTests(unittest.TestCase):
    def module(self):
        path=Path(__file__).resolve().parent.parent/'deploy/safety_control.py'
        spec=importlib.util.spec_from_file_location('safety_control_test',path)
        loaded=importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
        return loaded
    def exercise(self,fail=False):
        control=self.module()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); control.STOP=root/'safety/STOP'
            note=root/'memory.md'; note.write_text('Keep my memory')
            calls=[]
            name='kwod-'+'a'*32
            def command(args,**kwargs):
                calls.append(args)
                if args[:2]==['systemctl','show']: return SimpleNamespace(returncode=0,stdout='loaded\n')
                if args[:2]==['docker','ps']: return SimpleNamespace(returncode=0,stdout=name+'\nunrelated-container\nkwod-web\n')
                return SimpleNamespace(returncode=1 if fail and args[:2]==['systemctl','stop'] else 0,stdout='')
            with patch.object(control.os,'geteuid',return_value=0,create=True),patch.object(control.os,'O_DIRECTORY',0,create=True),patch.object(control.os,'open',return_value=123),patch.object(control.os,'close'),patch.object(control.os,'fsync'),patch.object(control.subprocess,'run',side_effect=command):
                if fail:
                    with self.assertRaisesRegex(RuntimeError,'incomplete'): control.stop()
                else: control.stop()
            self.assertTrue(control.STOP.exists())
            self.assertEqual(note.read_text(),'Keep my memory')
            self.assertEqual([c for c in calls if c[:2]==['docker','rm']],[['docker','rm','-f',name]])
            self.assertTrue(any(c[:2]==['systemctl','kill'] for c in calls))
    def test_stop_persists_marker_and_only_removes_agent_uuid_containers(self): self.exercise()
    def test_partial_failure_keeps_marker_and_does_not_report_success(self): self.exercise(fail=True)
