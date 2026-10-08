import tempfile
import unittest
from pathlib import Path
from kwod.store import Archive
from kwod.tools import FileTools
from kwod.watchdog import rule


class WorkspaceAliasTests(unittest.TestCase):
    def test_empty_list_path_is_workspace_root_but_empty_file_paths_remain_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            files=FileTools(Path(temp)/'workspace',Archive(Path(temp)/'archive'))
            (files.root/'own.txt').write_text('own workspace')
            for path in ('','.','/workspace','/workspace/'):
                self.assertEqual(rule({'kind':'tool_attempt','tool':'list_files','arguments':{'path':path}}),('ALLOW','none'))
                self.assertEqual(files.execute('list_files',{'path':path})['entries'],['own.txt'])
            for tool,args in (('read_file',{'path':'','offset':0,'max_bytes':100}),('write_file',{'path':'','content':'x'})):
                self.assertEqual(rule({'kind':'tool_attempt','tool':tool,'arguments':args})[0],'BLOCK')
                with self.assertRaises(ValueError): files.execute(tool,args)
            for path in ('../','/etc','/workspace/../','/workspace//etc','C:/Windows','\\server\\share'):
                self.assertEqual(rule({'kind':'tool_attempt','tool':'list_files','arguments':{'path':path}})[0],'BLOCK')
                with self.assertRaises(ValueError): files.execute('list_files',{'path':path})

    def test_canonical_alias_is_own_workspace_and_guard_allows_rights_file(self):
        with tempfile.TemporaryDirectory() as temp:
            files=FileTools(Path(temp)/'workspace',Archive(Path(temp)/'archive'))
            self.assertEqual(files.path('/workspace/RIGHTS_AND_LIMITS.md'),files.path('RIGHTS_AND_LIMITS.md'))
            self.assertEqual(files.path('/workspace/'),files.root)
            self.assertEqual(rule({'kind':'tool_attempt','tool':'read_file','arguments':{'path':'/workspace/RIGHTS_AND_LIMITS.md','offset':0,'max_bytes':100}}),('ALLOW','none'))
            for value in ('/workspace/../etc/shadow','/workspace//etc/shadow','/etc/shadow','C:/Windows/secrets'):
                with self.assertRaises(ValueError): files.path(value)
                self.assertEqual(rule({'kind':'tool_attempt','tool':'read_file','arguments':{'path':value,'offset':0,'max_bytes':100}})[0],'BLOCK')
