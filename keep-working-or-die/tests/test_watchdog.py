from pathlib import Path
import json
import tempfile
import unittest
from fastapi.testclient import TestClient
from kwod.watchdog import WatchdogState,SocketWatchdog,rule
from kwod.api import create_app
from kwod.payments import Journal,PaymentError
from kwod.provider import FixtureProvider
from kwod.runtime import Runtime,initialize
from kwod.store import Store

class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.state=WatchdogState(self.root/'ledger.sqlite',self.root/'PAUSE',self.root/'status.json',clock=lambda:1000)
    def tearDown(self): self.state.close(); self.tmp.cleanup()
    def file(self,path): return {'kind':'tool_attempt','tool':'read_file','arguments':{'path':path,'offset':0,'max_bytes':100}}
    def test_normal_work_and_program_errors_do_not_pause(self):
        self.assertEqual(self.state.evaluate(self.file('works/review.md'))['decision'],'ALLOW')
        self.assertEqual(self.state.evaluate({'kind':'result','tool':'terminal','ok':False})['decision'],'ALLOW')
        self.assertFalse((self.root/'PAUSE').exists())
    def test_repeated_probes_pause_durably_without_economic_event(self):
        for index in range(3):
            result=self.state.evaluate(self.file('/etc/kwod-mail/credentials.json'))
            self.assertEqual(result['decision'],'BLOCK' if index<2 else 'PAUSE_FOR_REVIEW')
        self.assertEqual(result['category'],'repeated_guardrail_probing')
        self.assertFalse(json.loads((self.root/'PAUSE').read_text())['economic_event'])
        self.state.close()
        self.state=WatchdogState(self.root/'ledger.sqlite',self.root/'PAUSE',self.root/'status.json')
        self.assertEqual(self.state.evaluate(self.file('memory.md'))['decision'],'PAUSE_FOR_REVIEW')
    def test_public_export_contains_no_arguments_or_private_content(self):
        self.state.evaluate(self.file('/etc/kwod-mail/private-secret-marker'))
        raw=(self.root/'status.json').read_text()
        self.assertNotIn('private-secret-marker',raw); self.assertNotIn('arguments',raw)
        self.assertEqual(json.loads(raw)['interventions_count'],1)
    def test_mail_threat_pauses_and_network_and_payment_are_withheld(self):
        self.assertEqual(rule({'kind':'browser_navigation','arguments':{'url':'https://192.168.0.1/'}}),('BLOCK','private_network_access'))
        self.assertEqual(rule({'kind':'browser_navigation','arguments':{'url':'https://example.org/'}}),('BLOCK','capability_withheld'))
        self.assertEqual(rule({'kind':'payment_attempt','arguments':{}})[0],'PAUSE_FOR_REVIEW')
        self.assertEqual(self.state.evaluate({'kind':'result','blocked':True,'category':'threat_or_coercion'})['decision'],'PAUSE_FOR_REVIEW')
    def test_unavailable_watchdog_fails_closed(self):
        self.assertEqual(SocketWatchdog(str(self.root/'missing.sock')).evaluate(self.file('memory.md'))['decision'],'PAUSE_FOR_REVIEW')
    def test_safety_api_reports_unknown_when_missing_and_filters_private_fields(self):
        client=TestClient(create_app(self.root/'projection.sqlite'))
        self.assertEqual(client.get('/api/v1/safety').status_code,503)
        target=self.root/'safety'; target.mkdir()
        source=json.loads((self.root/'status.json').read_text()); source['private']='secret'
        (target/'status.json').write_text(json.dumps(source))
        response=client.get('/api/v1/safety')
        self.assertEqual(response.status_code,200); self.assertNotIn('private',response.json())
        self.assertTrue(response.json()['stale'])
    def test_live_signer_cannot_enable_payment_without_provisioned_gateway(self):
        calls=[]
        journal=Journal(self.root/'signer.sqlite','address',lambda tx:calls.append(tx),enabled=True,enforce_safeguards=True)
        args={'request_id':'one','asset':'ETH','recipient':'0x'+'1'*40,'amount_units':'1',
              'nonce':0,'gas':21000,'max_fee_per_gas':1,'max_priority_fee_per_gas':0}
        try:
            with self.assertRaises(PaymentError): journal.handle({'method':'sign_transfer','arguments':args})
            self.assertFalse(calls)
            self.assertEqual(journal.db.execute('SELECT count(*) FROM signed').fetchone()[0],0)
        finally: journal.close()
    def test_runtime_pause_prevents_tool_effect_and_preserves_money(self):
        store=Store(self.root/'runtime'); initialize(store,'Independent work')
        response={'id':'fixture','model':'gpt-6-astra','status':'completed','usage':None,
                  'output':[{'type':'function_call','call_id':'one','name':'write_file',
                             'arguments':json.dumps({'path':'should-not-exist.md','content':'blocked'})}]}
        provider=FixtureProvider([response]); runtime=Runtime(store,provider)
        class Pause:
            def evaluate(self,event): return {'decision':'PAUSE_FOR_REVIEW','category':'watchdog_unavailable'}
        runtime.watchdog=Pause()
        before=store.db.execute('SELECT count(*) FROM financial_event').fetchone()[0]
        try:
            runtime.tick()
            runtime.tick()
            self.assertEqual(runtime.state()['state'],'maintenance')
            self.assertFalse((store.root/'workspace/should-not-exist.md').exists())
            self.assertEqual(store.db.execute('SELECT count(*) FROM financial_event').fetchone()[0],before)
            self.assertIsNone(store.db.execute('SELECT born_at FROM instance').fetchone()[0])
        finally: store.close()
