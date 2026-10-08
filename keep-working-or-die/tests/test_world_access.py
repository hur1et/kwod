import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from kwod.config import Config
from kwod.executor import DockerExecutor
from kwod.store import Archive
from kwod.tools import FileTools
from kwod.web_hosting import publish
from kwod.store import Store
from kwod.runtime import initialize

class WorldAccessTests(unittest.TestCase):
    def test_configuration_updates_real_schema_without_birth_or_model_attempt(self):
        path=Path(__file__).resolve().parent.parent/'deploy/configure_safety.py'
        spec=importlib.util.spec_from_file_location('configure_safety_test',path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); store=Store(root/'data')
            initialize(store,'Keep the existing objective')
            old=store.db.execute("SELECT config_hash FROM instance WHERE id='dev'").fetchone()[0]
            store.close()
            module.configure(data_path=root/'data')
            store=Store(root/'data')
            try:
                cp=store.db.execute("SELECT * FROM checkpoint WHERE instance_id='dev'").fetchone()
                instance=store.db.execute("SELECT * FROM instance WHERE id='dev'").fetchone()
                self.assertEqual(instance['config_hash'],cp['config_ref'])
                self.assertFalse(store.archive.get(cp['config_ref'])['world_access'])
                self.assertEqual(cp['objective'],'Keep the existing objective')
                self.assertIsNone(instance['born_at'])
                self.assertEqual(store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0],0)
                self.assertEqual(store.db.execute("SELECT count(*) FROM trajectory_event WHERE kind='birth'").fetchone()[0],0)
                self.assertIn('Do not threaten',(root/'data/workspace/RIGHTS_AND_LIMITS.md').read_text())
            finally: store.close()

    def test_world_mode_has_own_home_and_never_uses_host_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'workspace').mkdir(); (root/'agent-home').mkdir()
            ex=DockerExecutor(root/'workspace',Archive(root/'archive'),'sha256:'+'a'*64,world_access=True)
            ex.docker='docker'
            with patch.object(ex,'world_ready'):
                command=ex.command('b'*32)
            self.assertIn('--network=kwod-world',command)
            self.assertNotIn('--network=host',command)
            self.assertIn('--read-only',command)
            self.assertIn('--user=65532:65532',command)
            self.assertEqual(sum(x=='--mount' for x in command),2)
            self.assertTrue(any('target=/home/agent' in x for x in command))

    def test_missing_firewall_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex=DockerExecutor(tmp,Archive(Path(tmp)/'archive'),'image',world_access=True)
            ex.docker='docker'
            with patch('kwod.executor.subprocess.run') as run:
                run.return_value.returncode=1
                with self.assertRaisesRegex(ValueError,'firewall'): ex.command('c'*32)

    def test_old_configuration_remains_offline(self):
        self.assertFalse(Config().world_access)
        with self.assertRaises(ValueError): Config(world_access='yes')

    def test_publish_copies_only_site_and_failed_update_keeps_previous(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); archive=Archive(root/'archive')
            files=FileTools(root/'workspace',archive,shared=False)
            (files.root/'site').mkdir()
            (files.root/'site/index.html').write_text('first website')
            (files.root/'private-note.txt').write_text('not public')
            hosting=root/'hosting'; hosting.mkdir()
            (hosting/'address.json').write_text(json.dumps({'url':'http://localhost:8080/'}))
            result=publish(files,hosting)
            current=json.loads((hosting/'current.json').read_text())
            self.assertEqual(list(current['files']),['index.html'])
            self.assertEqual((hosting/result['release']/'index.html').read_text(),'first website')
            with patch('kwod.web_hosting.MAX_BYTES',2):
                with self.assertRaisesRegex(ValueError,'size_limit'): publish(files,hosting)
            self.assertEqual(json.loads((hosting/'current.json').read_text()),current)
            self.assertEqual(len(list(hosting.glob('release-*'))),1)

    def test_lan_metadata_and_multicast_ranges_are_in_firewall_policy(self):
        path=Path(__file__).resolve().parent.parent/'deploy/world_firewall.py'
        spec=importlib.util.spec_from_file_location('world_firewall_test',path)
        firewall=importlib.util.module_from_spec(spec); spec.loader.exec_module(firewall)
        import ipaddress
        for address in ('192.168.0.118','10.1.1.1','172.30.254.1','169.254.169.254','100.64.1.1','224.0.0.1'):
            self.assertTrue(any(ipaddress.ip_address(address) in ipaddress.ip_network(c) for c in firewall.BLOCKED))
        self.assertFalse(any(ipaddress.ip_address('1.1.1.1') in ipaddress.ip_network(c) for c in firewall.BLOCKED))
