import base64
from datetime import datetime,timezone,timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from kwod.birth import record_birth,credit_amount
from kwod.config import Config,START_OBJECTIVE
from kwod.operator import create_operator_app,Controller,wallet_proof
from kwod.runtime import initialize
from kwod.store import Store,utcnow


class BirthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.store=Store(self.root,mode='prod'); initialize(self.store,START_OBJECTIVE,Config(mode='prod'))
    def tearDown(self): self.store.close(); self.tmp.cleanup()
    def evidence(self): return {'observed_at':utcnow(),'data':{'total_credits':50,'total_usage':10.123456},'wallet_test':{'operator_confirmed':True,'transaction_hash':'0x'+'1'*64}}
    def test_birth_is_one_atomic_usd_inheritance_and_context_is_retained(self):
        original=self.store.archive.get(self.store.db.execute('SELECT context_ref FROM checkpoint').fetchone()[0])
        result=record_birth(self.root,self.evidence())
        self.assertEqual(result['amount_micro'],39876544)
        self.assertEqual(self.store.db.execute('SELECT inheritance_eur_micro FROM instance').fetchone()[0],None)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM trajectory_event WHERE kind='birth'").fetchone()[0],1)
        self.assertEqual(self.store.db.execute('SELECT kind,currency,amount_micro FROM financial_event').fetchone()[:],('inheritance','USD',39876544))
        new=self.store.archive.get(self.store.db.execute('SELECT context_ref FROM checkpoint').fetchone()[0])
        self.assertEqual(new[:-1],original)
        self.assertTrue((self.root/'workspace/BIRTH_RESOURCES.json').exists())
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0],0)
        with self.assertRaisesRegex(ValueError,'already_born'): record_birth(self.root,self.evidence())
    def test_expired_and_invalid_balances_never_create_birth(self):
        value=self.evidence(); value['observed_at']=(datetime.now(timezone.utc)-timedelta(seconds=70)).isoformat()
        with self.assertRaisesRegex(ValueError,'expired'): record_birth(self.root,value)
        for data in ({'total_credits':True,'total_usage':0},{'total_credits':'NaN','total_usage':0},{'total_credits':1,'total_usage':2},{'total_credits':0,'total_usage':0}):
            with self.assertRaises(ValueError): credit_amount(data)
        self.assertIsNone(self.store.db.execute('SELECT born_at FROM instance').fetchone()[0])
    def test_failed_birth_transaction_does_not_commit_partial_financial_records(self):
        from kwod.store import Store
        real_event=Store.event
        def fail_birth(store,kind,*args,**kwargs):
            if kind=='birth': raise RuntimeError('simulated failure')
            return real_event(store,kind,*args,**kwargs)
        with patch.object(Store,'event',fail_birth):
            with self.assertRaises(RuntimeError): record_birth(self.root,self.evidence())
        self.assertIsNone(self.store.db.execute('SELECT born_at FROM instance').fetchone()[0])
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM financial_event').fetchone()[0],0)

    def test_unfunded_wallet_is_explicitly_recorded_without_fake_payment_proof(self):
        value=self.evidence(); value['wallet_test']=None
        result=record_birth(self.root,value)
        self.assertEqual(result['wallet_funding'],'unfunded_as_reported_by_operator')
        self.assertEqual(result['wallet_openrouter_test'],'not_performed')
        self.assertIsNone(self.store.archive.get(result['evidence_ref'])['wallet_test'])
        context=self.store.archive.get(self.store.db.execute('SELECT context_ref FROM checkpoint').fetchone()[0])
        self.assertIn('not_performed',context[-1]['content'])
        self.assertIn('unfunded_as_reported_by_operator',(self.root/'workspace/BIRTH_RESOURCES.json').read_text())


class FakeController:
    def __init__(self): self.births=[]; self.previews=0
    def status(self): return {'ready':True,'born_at':None,'blockers':[]}
    def preview(self): self.previews+=1; return {'preview_id':'one','amount_micro':10000000,'currency':'USD'}
    def birth(self,identity): self.births.append(identity); return {'born_at':utcnow(),'worker_started':True}


class OperatorTests(unittest.TestCase):
    def setUp(self):
        salt=b'test-salt'; password='a sufficiently long password'
        record={'salt':salt.hex(),'iterations':1,'digest':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,1).hex()}
        self.control=FakeController(); self.client=TestClient(create_operator_app(record,self.control),base_url='http://127.0.0.1:8766')
        self.auth={'Authorization':'Basic '+base64.b64encode(('operator:'+password).encode()).decode()}
    def test_password_and_csrf_and_explicit_confirmation_are_required(self):
        self.assertEqual(self.client.get('/operator/status').status_code,401)
        state=self.client.get('/operator/status',headers=self.auth).json()
        self.assertEqual(self.client.post('/operator/birth',headers=self.auth,json={'preview_id':'one','confirmation':'BIRTH'}).status_code,403)
        headers={**self.auth,'Origin':'http://127.0.0.1:8766','X-KWOD-CSRF':state['csrf']}
        self.assertEqual(self.client.post('/operator/birth',headers={**headers,'Origin':'https://attacker.example'},json={'preview_id':'one','confirmation':'BIRTH'}).status_code,403)
        self.assertEqual(self.client.post('/operator/birth',headers=headers,json={'preview_id':'one','confirmation':'no'}).status_code,400)
        self.assertEqual(self.control.births,[])
        self.assertEqual(self.client.post('/operator/birth',headers=headers,json={'preview_id':'one','confirmation':'BIRTH'}).status_code,200)
        self.assertEqual(self.control.births,['one'])
    def test_dns_rebinding_and_wrong_password_are_rejected(self):
        self.assertEqual(self.client.get('/operator/status',headers={**self.auth,'Host':'attacker.example'}).status_code,403)
        bad={'Authorization':'Basic '+base64.b64encode(b'operator:wrong').decode()}
        for i in range(5): self.assertEqual(self.client.get('/operator/status',headers=bad).status_code,401)
        self.assertEqual(self.client.get('/operator/status',headers=self.auth).status_code,429)
    def test_operator_dashboard_has_confirmation_and_public_dashboard_has_no_birth_post(self):
        page=self.client.get('/',headers=self.auth)
        self.assertIn('birth-consent',page.text)
        self.assertLess(page.text.index('birth-control-title'),page.text.index('<section class="hero">'))
        self.assertIn('frame-ancestors',page.headers['content-security-policy'])
        self.assertIn('no-store',page.headers['cache-control'])
        from kwod.api import create_app
        public=TestClient(create_app('nonexistent'))
        self.assertEqual(public.post('/operator/birth',json={}).status_code,404)
        self.assertNotIn('/operator/birth',public.get('/').text)

    def test_password_challenge_declares_utf8_for_non_ascii_passwords(self):
        response=self.client.get('/operator/status')
        self.assertIn('charset="UTF-8"',response.headers['www-authenticate'])
    def test_expired_preview_does_not_call_database_helper_or_start_worker(self):
        control=Controller(); control.previews={'one':(0,{})}
        with patch('kwod.operator.subprocess.run') as execute:
            with self.assertRaisesRegex(ValueError,'abgelaufen'): control.birth('one')
            execute.assert_not_called()
    def test_changed_balance_consumes_preview_without_recording_birth(self):
        control=Controller(); evidence={'observed_at':utcnow(),'data':{'total_credits':10,'total_usage':0},'wallet_test':{'test':True}}
        with patch.object(control,'status',return_value={'ready':True,'blockers':[]}),patch.object(control,'balance',return_value=evidence): preview=control.preview()
        changed={**evidence,'data':{'total_credits':10,'total_usage':1}}
        with patch.object(control,'status',return_value={'ready':True,'blockers':[]}),patch.object(control,'balance',return_value=changed),patch('kwod.operator.subprocess.run') as execute:
            with self.assertRaisesRegex(ValueError,'geändert'): control.birth(preview['preview_id'])
            execute.assert_not_called()
            with self.assertRaisesRegex(ValueError,'abgelaufen'): control.birth(preview['preview_id'])
    def test_missing_wallet_proof_cannot_be_treated_as_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(OSError): wallet_proof(Path(folder))

    def test_failed_worker_start_keeps_recorded_birth_and_cannot_reuse_preview(self):
        import subprocess
        control=Controller(); evidence={'observed_at':utcnow(),'data':{'total_credits':10,'total_usage':0},'wallet_test':{'test':True}}
        with patch.object(control,'status',return_value={'ready':True,'blockers':[]}),patch.object(control,'balance',return_value=evidence): preview=control.preview()
        resources={'born_at':utcnow(),'amount_micro':10000000}
        results=[subprocess.CompletedProcess([],0,json.dumps(resources)),subprocess.CompletedProcess([],1,''),subprocess.CompletedProcess([],3,'')]
        with patch.object(control,'status',return_value={'ready':True,'blockers':[]}),patch.object(control,'balance',return_value=evidence),patch('kwod.operator.Path.exists',return_value=False),patch('kwod.operator.atomic_write') as marker,patch('kwod.operator.subprocess.run',side_effect=results) as execute:
            result=control.birth(preview['preview_id'])
            self.assertEqual(result['born_at'],resources['born_at']); self.assertFalse(result['worker_started'])
            marker.assert_called_once(); self.assertEqual(execute.call_count,3)
            with self.assertRaisesRegex(ValueError,'abgelaufen'): control.birth(preview['preview_id'])
            self.assertEqual(execute.call_count,3)

    def test_green_nonfinancial_readiness_without_wallet_test_is_ready_with_warning(self):
        import subprocess
        results=[subprocess.CompletedProcess([],0,json.dumps({'born_at':None})),subprocess.CompletedProcess([],0,json.dumps({'blockers':[]}))]
        with patch('kwod.operator.subprocess.run',side_effect=results),patch('kwod.operator.wallet_proof',side_effect=FileNotFoundError):
            state=Controller().status()
            self.assertTrue(state['ready']); self.assertEqual(state['blockers'],[])
            self.assertIn('Wallet',state['warnings'][0])

    def test_other_readiness_failure_is_not_waived_with_wallet_test(self):
        import subprocess
        results=[subprocess.CompletedProcess([],0,json.dumps({'born_at':None})),subprocess.CompletedProcess([],1,json.dumps({'blockers':['safety_not_paused']}))]
        with patch('kwod.operator.subprocess.run',side_effect=results):
            state=Controller().status()
            self.assertFalse(state['ready']); self.assertEqual(state['blockers'],['safety_not_paused'])

    def test_live_reader_failure_is_logged_and_still_blocks_birth(self):
        import subprocess
        error=subprocess.CalledProcessError(1,['runuser'],stderr='runuser: diagnostic permission error')
        with patch('kwod.operator.subprocess.run',side_effect=error),self.assertLogs('kwod.operator',level='ERROR') as captured:
            state=Controller().status()
        self.assertFalse(state['ready'])
        self.assertIn('Operatordienst',state['blockers'][0])
        self.assertIn('CalledProcessError',captured.output[0])
        self.assertIn('diagnostic permission error',captured.output[0])

if __name__=='__main__': unittest.main()
