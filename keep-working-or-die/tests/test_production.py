import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from kwod.cli import main
from kwod.config import Config,START_OBJECTIVE,constitution
from kwod.provider import FixtureProvider,ProductionOpenRouterProvider
from kwod.runtime import initialize,Runtime
from kwod.store import Store
from kwod.projection import project
from kwod.backup import backup,restore

def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).parents[1]/'deploy'/f'{name}.py')
    loaded=importlib.util.module_from_spec(spec); spec.loader.exec_module(loaded); return loaded

class ProductionTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def prepare(self):
        module('configure_production').configure(self.root/'prod','sha256:'+'1'*64)
        return Store(self.root/'prod',mode='prod')
    def test_prod_is_separate_persists_context_and_never_births_or_calls(self):
        dev=Store(self.root/'dev'); initialize(dev,'Development only'); dev.close()
        prod=self.prepare()
        try:
            cp=prod.db.execute('SELECT * FROM checkpoint').fetchone()
            self.assertEqual(cp['objective'],START_OBJECTIVE)
            self.assertEqual(prod.archive.get(cp['context_ref'])[0]['content'],START_OBJECTIVE)
            self.assertEqual(prod.archive.get(prod.db.execute('SELECT prompt_hash FROM instance').fetchone()[0]),constitution('prod'))
            provider=FixtureProvider([]); runtime=Runtime(prod,provider)
            self.assertEqual(runtime.tick(),'not_born'); self.assertFalse(provider.requests)
            self.assertEqual(prod.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0],0)
            public=sqlite3.connect(prod.root/'public/public.sqlite')
            try: snapshot=json.loads(public.execute('SELECT payload FROM snapshot').fetchone()[0])
            finally: public.close()
            self.assertEqual((snapshot['mode'],snapshot['status']),('prod','not_born'))
        finally: prod.close()
    def test_store_rejects_cross_mode_before_runtime_access(self):
        prod=self.prepare(); prod.close()
        with self.assertRaisesRegex(ValueError,'store_mode_mismatch'): Store(self.root/'prod')
        dev=Store(self.root/'dev'); initialize(dev,'Dev'); dev.close()
        with self.assertRaisesRegex(ValueError,'store_mode_mismatch'): Store(self.root/'dev',mode='prod')
    def test_cli_wrong_providers_and_unborn_guard_do_not_construct_live_client(self):
        prod=self.prepare(); prod.close()
        with patch('kwod.provider.ProductionOpenRouterProvider') as provider:
            for provider_flag in ('--openrouter-dev','--openai-dev','--openrouter-prod'):
                with self.assertRaises(SystemExit): main(['--mode','prod','--data',str(self.root/'prod'),'run',provider_flag])
            provider.assert_not_called()
    def test_prod_event_and_accounting_ids_are_prod_and_backup_restores_mode(self):
        prod=self.prepare()
        try:
            self.assertEqual({row[0] for row in prod.db.execute('SELECT instance_id FROM trajectory_event')},{'prod'})
            backup(prod,self.root/'backup')
        finally: prod.close()
        restore(self.root/'backup',self.root/'restored',mode='prod')
        restored=Store(self.root/'restored',mode='prod'); restored.close()
    def test_repreparation_is_idempotent_and_refuses_changed_start_objective(self):
        prod=self.prepare()
        prod.db.execute("UPDATE checkpoint SET objective='Changed'"); prod.db.commit(); prod.close()
        with self.assertRaisesRegex(ValueError,'production_context_changed'): self.prepare()
    def test_readiness_observes_unborn_database_and_detects_missing_archive(self):
        prod=self.prepare(); prod.close(); check=module('check_production_readiness')
        result=check.state(self.root/'prod')
        self.assertEqual((result['instance']['mode'],result['attempts'],result['births']),('prod',0,0))
        self.assertEqual(result['context'][0]['content'],START_OBJECTIVE)
        (self.root/'prod/private/archive'/result['checkpoint']['context_ref']).write_text('changed')
        with self.assertRaises(ValueError): check.state(self.root/'prod')
    def test_production_provider_ignores_dev_key_and_requires_service_credential(self):
        with patch.dict('os.environ',{'KWOD_DEV_OPENROUTER_API_KEY':'development-key'},clear=True):
            with self.assertRaisesRegex(ValueError,'production_service_credential_required'): ProductionOpenRouterProvider()
