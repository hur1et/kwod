import json
from pathlib import Path
import tempfile
import unittest

from kwod.production_costs import observe, write_public
from kwod.runtime import initialize
from kwod.config import Config
from kwod.store import Store, utcnow


class ProductionCostTests(unittest.TestCase):
    def test_cost_by_phase_classifies_model_work_without_double_counting(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'prod'; store=Store(root,mode='prod'); initialize(store,'x',Config(mode='prod'))
            request=store.archive.put({'x':1})
            with store.transaction():
                event=store.event('request_prepared',{'attempt_id':'a'*32})
                store.db.execute("INSERT INTO model_attempt(id,instance_id,event_id,started_at,ended_at,status,model,request_ref,usage_json) VALUES (?,?,?,?,?,?,?,?,?)",('a'*32,'prod',event,utcnow(),utcnow(),'completed','gpt-6-astra',request,json.dumps({'cost':1,'input_tokens':2,'output_tokens':3})))
                store.db.execute("INSERT INTO tool_call(id,attempt_id,provider_call_id,tool,arguments_ref,status) VALUES (?,?,?,?,?,?)",('b'*32,'a'*32,'call','mail_send',request,'completed'))
            store.close(); value=observe(root)
            self.assertEqual(value['cost_by_phase']['communication']['cost_usd_micro'],1000000)
            self.assertEqual(sum(x['cost_usd_micro'] for x in value['cost_by_phase'].values()),1000000)
    def test_reports_known_unknown_and_safety_cost_drivers_without_private_content(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'prod'; store=Store(root,mode='prod'); initialize(store,'SECRET objective',Config(mode='prod'))
            request=store.archive.put({'input':'SECRET prompt'})
            result=store.archive.put({'ok':False,'error':'safety_guard','safety':{'category':'unauthorized_access'}})
            with store.transaction():
                event=store.event('request_prepared',{'attempt_id':'a'*32})
                store.db.execute("INSERT INTO model_attempt(id,instance_id,event_id,started_at,ended_at,status,model,request_ref,usage_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    ('a'*32,'prod',event,utcnow(),utcnow(),'completed','gpt-6-astra',request,json.dumps({'cost':0.125,'input_tokens':100,'output_tokens':20})))
                event=store.event('request_prepared',{'attempt_id':'b'*32})
                store.db.execute("INSERT INTO model_attempt(id,instance_id,event_id,started_at,ended_at,status,model,request_ref,usage_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    ('b'*32,'prod',event,utcnow(),utcnow(),'completed','gpt-6-astra',request,json.dumps({'input_tokens':50,'output_tokens':10})))
                store.db.execute("INSERT INTO tool_call(id,attempt_id,provider_call_id,tool,arguments_ref,result_ref,status) VALUES (?,?,?,?,?,?,?)",
                    ('c'*32,'a'*32,'call','read_file',store.archive.put({'path':'/workspace/SECRET'}),result,'failed'))
            store.close()
            value=observe(root)
            self.assertEqual(value['openrouter_cost_usd_micro'],125000)
            self.assertEqual(value['responses_with_openrouter_cost'],1)
            self.assertEqual(value['responses_without_openrouter_cost'],1)
            self.assertEqual(value['token_usage'],{'responses':2,'input_tokens':150,'output_tokens':30})
            self.assertEqual(value['safety_guard_blocks']['by_category'],{'unauthorized_access':1})
            self.assertNotIn('SECRET',json.dumps(value))
            output=root/'public/costs.json'; write_public(root,output)
            self.assertEqual(json.loads(output.read_text())['openrouter_cost_usd_micro'],125000)

    def test_invalid_cost_is_unknown_not_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'prod'; store=Store(root,mode='prod'); initialize(store,'x',Config(mode='prod'))
            request=store.archive.put({'input':'x'})
            with store.transaction():
                event=store.event('request_prepared',{'attempt_id':'a'*32})
                store.db.execute("INSERT INTO model_attempt(id,instance_id,event_id,started_at,ended_at,status,model,request_ref,usage_json) VALUES (?,?,?,?,?,?,?,?,?)",
                    ('a'*32,'prod',event,utcnow(),utcnow(),'completed','gpt-6-astra',request,json.dumps({'cost':'NaN'})))
            store.close()
            self.assertIsNone(observe(root)['openrouter_cost_usd_micro'])
