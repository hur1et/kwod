"""Capability migration, isolation contracts and payment recovery, all offline."""
import ast
import importlib.util
import ipaddress
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from kwod import autonomy
from kwod.config import Config, START_OBJECTIVE
from kwod.context import request
from kwod.runtime import initialize
from kwod.store import Store, Archive
from kwod.services import Services
from kwod.tools import definitions
from kwod.watchdog import rule
from kwod.payments import Journal, transaction, sign_function, PaymentError
from kwod.payment_relay import PaymentRelay, verify_signed
from kwod.wallet_gateway import BaseRPC, transfer_effect

REPO=Path(__file__).parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location(name,REPO/'deploy'/f'{name}.py')
    value=importlib.util.module_from_spec(spec); spec.loader.exec_module(value); return value


def receipt():
    return dict(level='S5.4',version=1,image='sha256:'+'a'*64,**{key:True for key in autonomy.CAPABILITIES})


class CapabilitiesTests(unittest.TestCase):
    def test_default_remains_offline_and_new_tools_require_cumulative_configuration(self):
        names={x['name'] for x in definitions()}
        self.assertNotIn('wallet_transfer',names); self.assertNotIn('browser_action',names)
        with self.assertRaises(ValueError): Config(world_access=True)
        with self.assertRaises(ValueError): Config(autonomy_level='S5.4')
        cfg=Config(mode='prod',autonomy_level='S5.4',world_access=True,agent_home=True,watchdog_enabled=True)
        payload=request(cfg,[])
        self.assertIn('service_start',{x['name'] for x in payload['tools']})
        self.assertIn('wallet_transfer',{x['name'] for x in payload['tools']})
        self.assertIn('S5.4 is cumulative',payload['instructions'])
        self.assertNotIn('terminal is offline',payload['instructions'])

    def test_receipt_missing_malformed_or_disabled_never_grants_a_capability(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'profile.json'
            with patch.object(autonomy,'PROFILE',path):
                self.assertFalse(autonomy.enabled('internet'))
                path.write_text('{'); self.assertFalse(autonomy.enabled('internet'))
                cfg=receipt(); cfg['payments']='yes'; path.write_text(json.dumps(cfg))
                self.assertFalse(autonomy.enabled('payments'))
                cfg=receipt(); cfg['payments']=False; path.write_text(json.dumps(cfg))
                # root ownership is tested by the Linux probe; local temp files may
                # belong to the unprivileged test user on Ubuntu installations.
                with patch('kwod.autonomy.profile',return_value=cfg):
                    self.assertFalse(autonomy.enabled('payments')); self.assertTrue(autonomy.enabled('internet'))

    def test_stop_dominates_valid_receipt(self):
        with patch('kwod.autonomy.profile',return_value=receipt()),patch('kwod.safety.stopped',return_value=True):
            with self.assertRaisesRegex(ValueError,'safety_stop'): autonomy.require('payments')

    def test_watchdog_opens_only_installed_features(self):
        args={'action':'snapshot','url':'','selector':'','text':''}
        with patch('kwod.autonomy.enabled',return_value=False):
            self.assertEqual(rule({'kind':'tool_attempt','tool':'browser_action','arguments':args})[0],'BLOCK')
        with patch('kwod.autonomy.enabled',return_value=True):
            self.assertEqual(rule({'kind':'tool_attempt','tool':'browser_action','arguments':args})[0],'ALLOW')
            self.assertEqual(rule({'kind':'payment_attempt','arguments':{'recipient':'anything'}})[0],'BLOCK')
            self.assertEqual(rule({'kind':'tool_attempt','tool':'read_file','arguments':{'path':'/etc/shadow','offset':0,'max_bytes':30}})[0],'BLOCK')


class MigrationTests(unittest.TestCase):
    def test_existing_life_work_and_objective_survive_enable_and_revoke(self):
        configure=module('configure_s54').configure
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); store=Store(root,mode='prod'); initialize(store,START_OBJECTIVE,Config(mode='prod'))
            store.db.execute("UPDATE instance SET born_at='2026-09-16T20:00:00Z'"); store.db.commit()
            for name in ('memory.md','strategy.md','order.txt'): (root/'workspace'/name).write_text('existing work '+name)
            store.close()
            configure(root,receipt=receipt())
            store=Store(root,mode='prod')
            cp=store.db.execute('SELECT * FROM checkpoint').fetchone()
            self.assertEqual(cp['objective'],START_OBJECTIVE)
            self.assertEqual(store.archive.get(cp['config_ref'])['autonomy_level'],'S5.4')
            self.assertEqual(store.db.execute('SELECT born_at FROM instance').fetchone()[0],'2026-09-16T20:00:00Z')
            self.assertEqual(store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0],0)
            store.close()
            configure(root,disable=True)
            for name in ('memory.md','strategy.md','order.txt'): self.assertEqual((root/'workspace'/name).read_text(),'existing work '+name)
            store=Store(root,mode='prod'); cp=store.db.execute('SELECT * FROM checkpoint').fetchone()
            self.assertFalse(store.archive.get(cp['config_ref'])['world_access']); store.close()

    def test_sent_pending_attempt_is_never_silently_reset(self):
        configure=module('configure_s54').configure
        with tempfile.TemporaryDirectory() as tmp:
            store=Store(tmp,mode='prod'); initialize(store,START_OBJECTIVE,Config(mode='prod'))
            with store.transaction():
                event=store.event('fixture',{})
                store.db.execute("INSERT INTO model_attempt(id,instance_id,event_id,started_at,status,model,request_ref) VALUES ('pending','prod',?,'2026-09-17','sent','gpt-6-astra',?)",(event,store.archive.put({})))
                store.db.execute("UPDATE checkpoint SET pending_attempt='pending'")
            store.close()
            with self.assertRaisesRegex(ValueError,'pending_work'): configure(tmp,receipt=receipt())
            store=Store(tmp,mode='prod'); self.assertEqual(store.db.execute('SELECT pending_attempt FROM checkpoint').fetchone()[0],'pending'); store.close()


class ServiceTests(unittest.TestCase):
    def test_names_cannot_select_host_services_or_inject_docker_options(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'agent-home').mkdir(); manager=Services(root,Archive(root/'archive'))
            with patch.object(manager,'ready',return_value=receipt()),patch.object(manager,'run') as run:
                for name in ('../host','--privileged','browser/x','x;sudo',''):
                    with self.subTest(name=name),self.assertRaises(ValueError): manager.start(name,'true',8080)
                run.assert_not_called()

    def test_container_has_no_host_secrets_socket_or_host_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'agent-home').mkdir(); manager=Services(root,Archive(root/'archive'))
            args=manager.base('kwod-s54-app-test',receipt())
            self.assertIn('--network=kwod-world',args); self.assertIn('--cap-drop=ALL',args)
            self.assertIn('--restart=no',args); self.assertIn('--user=65532:65532',args)
            mounts=[args[i+1] for i,x in enumerate(args) if x=='--mount']
            self.assertEqual(len(mounts),1); self.assertTrue(mounts[0].endswith('target=/home/agent'))
            self.assertNotIn('--privileged',args); self.assertNotIn('--network=host',args)

    def test_same_service_configuration_does_not_start_a_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'agent-home').mkdir(); manager=Services(root,Archive(root/'archive'))
            created=[]
            def run(*args,**kwargs): created.append(args); return 'container-id'
            def inspect(name):
                import hashlib
                return {'Name':'/'+name,'State':{'Running':True},'Config':{'Labels':{'kwod.spec':hashlib.sha256(json.dumps(['sleep 20',8080,receipt()['image']]).encode()).hexdigest()}},'NetworkSettings':{'Ports':{'8080/tcp':[{'HostPort':'18080'}]}}}
            with patch.object(manager,'ready',return_value=receipt()),patch.object(manager,'run',side_effect=run),patch.object(manager,'inspect',side_effect=inspect),patch.object(manager,'inventory',side_effect=[[],[inspect('kwod-s54-app-demo')]]):
                self.assertTrue(manager.start('demo','sleep 20',8080)['running'])
                self.assertTrue(manager.start('demo','sleep 20',8080)['existing'])
            self.assertEqual(len(created),1)
            self.assertIn('127.0.0.1:18080:8080',created[0])

    def test_firewall_blocks_private_destinations_before_allowing_egress(self):
        firewall=module('s54_firewall'); rules=firewall.rules('8.8.8.8')
        entries=rules['KWOD-S54-OUT']
        self.assertIn('--ctdir',entries[0]); self.assertIn('REPLY',entries[0])
        nets=[ipaddress.ip_network(x[1]) for x in entries if x[0]=='-d']
        for address in ('192.168.0.118','172.30.254.1','169.254.169.254','100.64.1.1','127.0.0.1','8.8.8.8'):
            self.assertTrue(any(ipaddress.ip_address(address) in net for net in nets))
        self.assertEqual(rules['KWOD-S54-HOST'][-1],['-j','REJECT'])

    def test_embedded_linux_probes_are_valid_python(self):
        tree=ast.parse((REPO/'deploy/check_s54.py').read_text())
        snippets=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value.startswith(('import json, pathlib','from pathlib import Path\nassert'))]
        self.assertEqual(len(snippets),2)
        for snippet in snippets: compile(snippet,'linux-probe','exec')


class WalletTests(unittest.TestCase):
    def test_real_signature_replay_and_wire_verification_with_public_test_key(self):
        from eth_account import Account
        account=Account.from_key('0x'+'00'*31+'01')
        args=dict(request_id='one',asset='USDC',recipient='0x'+'11'*20,amount_units='1000000',nonce=0,gas=100000,max_fee_per_gas=10,max_priority_fee_per_gas=1)
        with tempfile.TemporaryDirectory() as tmp:
            journal=Journal(Path(tmp)/'signer.sqlite',account.address,sign_function(account),enabled=True)
            signed=journal.handle({'method':'sign_transfer','arguments':args}); journal.close()
            verify_signed(args,signed,account.address)
            journal=Journal(Path(tmp)/'signer.sqlite',account.address,lambda tx:self.fail('duplicate signing'),enabled=True)
            try: self.assertEqual(signed,journal.handle({'method':'sign_transfer','arguments':args}))
            finally: journal.close()
            with self.assertRaises(PaymentError): verify_signed(dict(args,amount_units='2000000'),signed,account.address)

    def test_quote_includes_all_fees_and_rejects_pending_outside_spend(self):
        from eth_utils import keccak
        rpc=BaseRPC('0x'+'22'*20,None)
        calls=[]
        def call(method,params):
            calls.append((method,params))
            if method=='eth_chainId': return hex(8453)
            if method=='eth_blockNumber': return '0x10'
            if method=='eth_getTransactionCount': return '0x0'
            if method=='eth_maxPriorityFeePerGas': return '0x1'
            if method=='eth_gasPrice': return '0x2'
            if method=='eth_estimateGas': return hex(30000)
            if method=='eth_getBalance': return hex(10**18)
            if method=='eth_call': return hex(100)
            raise AssertionError(method)
        intent=dict(request_id='one',asset='ETH',recipient='0x'+'11'*20,amount_units='1')
        with patch.object(rpc,'rpc',side_effect=call):
            quote=rpc.quote(intent)
        self.assertEqual(quote['l1_fee_reserve_wei'],200)
        self.assertEqual(quote['operator_fee_reserve_wei'],200)
        self.assertGreater(quote['arguments']['gas'],30000)
        original=call
        def pending(method,params):
            if method=='eth_getTransactionCount': return '0x1' if params[-1]=='pending' else '0x0'
            return original(method,params)
        with patch.object(rpc,'rpc',side_effect=pending),self.assertRaisesRegex(PaymentError,'pending_transaction'):
            rpc.quote(intent)

    def test_receipt_status_alone_does_not_prove_expected_transfer(self):
        from eth_utils import keccak
        address='0x'+'22'*20; recipient='0x'+'11'*20
        intent=dict(request_id='one',asset='ETH',recipient=recipient,amount_units='42')
        tx={'from':address,'to':recipient,'value':'0x2a','input':'0x','hash':'0x'+'a'*64,'blockHash':'0x'+'b'*64}
        receipt={'transactionHash':tx['hash'],'blockHash':tx['blockHash'],'status':'0x1','logs':[]}
        self.assertTrue(transfer_effect(tx,receipt,intent,address))
        self.assertFalse(transfer_effect(dict(tx,to=address),receipt,intent,address))
        self.assertFalse(transfer_effect(dict(tx,value='0x1'),receipt,intent,address))
