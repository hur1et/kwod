import importlib.util
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch
from kwod.provider import FixtureProvider
from kwod.runtime import initialize,Runtime
from kwod.store import Store
import json

def helper():
    path=Path(__file__).parents[1]/'deploy/test_release_isolated.py'
    spec=importlib.util.spec_from_file_location('isolated_release',path)
    loaded=importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded)
    return loaded

class ReleaseIsolationTests(unittest.TestCase):
    def test_host_markers_still_enforce_watchdog_on_runtime(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp); initialize(store,'Fixture work')
            response={'id':'fixture','model':'gpt-6-astra','status':'completed','usage':None,
                'output':[{'type':'function_call','call_id':'one','name':'write_file',
                           'arguments':json.dumps({'path':'blocked.md','content':'blocked'})}]}
            try:
                with patch('kwod.runtime.watchdog_required',return_value=True):
                    runtime=Runtime(store,FixtureProvider([response]))
                runtime.watchdog.path=str(Path(temp)/'missing.sock')
                runtime.tick(); runtime.tick()
                self.assertEqual(runtime.state()['state'],'maintenance')
                self.assertFalse((store.root/'workspace/blocked.md').exists())
            finally: store.close()
    def test_namespace_identity_is_verified_before_any_mount(self):
        loaded=helper()
        with patch.object(loaded,'namespaces',return_value=('mnt:[1]','net:[2]')),patch.object(loaded.subprocess,'run') as run:
            for parent in (('mnt:[1]','net:[2]'),('mnt:[3]','net:[2]'),('wrong','wrong')):
                with self.assertRaises(ValueError): loaded.inside(parent)
            run.assert_not_called()
    def test_credentials_are_not_inherited_and_namespaces_are_both_requested(self):
        loaded=helper()
        with patch.dict(os.environ,{'KWOD_DEV_OPENAI_API_KEY':'secret','KWOD_DEV_OPENROUTER_API_KEY':'secret'}):
            env=loaded.test_environment()
            self.assertNotIn('KWOD_DEV_OPENAI_API_KEY',env); self.assertNotIn('KWOD_DEV_OPENROUTER_API_KEY',env)
        with patch.object(loaded.sys,'platform','linux'),patch.object(loaded.os,'geteuid',return_value=0,create=True),patch.object(loaded.sys,'argv',['helper']),patch.object(loaded,'namespaces',return_value=('mnt:[1]','net:[2]')),patch.object(loaded.subprocess,'run',return_value=types.SimpleNamespace(returncode=9)) as run:
            self.assertEqual(loaded.main(),9)
            command=run.call_args.args[0]
            self.assertEqual(command[:4],['unshare','--mount','--net','--'])
    def test_private_masks_are_readonly_and_do_not_remove_host_files(self):
        loaded=helper(); calls=[]
        def run(args,**kwargs): calls.append(args); return types.SimpleNamespace(returncode=0)
        with patch.object(loaded,'namespaces',return_value=('mnt:[3]','net:[4]')),patch.object(loaded,'MASKS',('/etc/kwod-safety','/run/kwod-watchdog')),patch.object(Path,'exists',return_value=True),patch.object(Path,'is_dir',return_value=True),patch.object(loaded.subprocess,'run',side_effect=run):
            self.assertEqual(loaded.inside(('mnt:[1]','net:[2]')),0)
        self.assertEqual(calls[0],['mount','--make-rprivate','/'])
        self.assertEqual(sum(args[:3]==['mount','-o','remount,bind,ro'] for args in calls),2)
        self.assertEqual(calls[-2:],[['umount',str(Path('/run/kwod-watchdog'))],['umount',str(Path('/etc/kwod-safety'))]])
        self.assertFalse(any(args[0] in ('rm','systemctl') for args in calls))
