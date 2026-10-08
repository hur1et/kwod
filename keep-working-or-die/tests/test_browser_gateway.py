import json
from pathlib import Path
import ssl
import tempfile
import unittest
from unittest.mock import patch,MagicMock
from kwod.browser_policy import normalize_url,BrowserBlocked,public_address
from kwod.browser_gateway import BrowserGateway,PinnedHTTPS,BrowserClient,fetch
from kwod.watchdog import rule
from kwod.store import Store
from kwod.runtime import initialize

class Observer:
    def __init__(self): self.events=[]
    def evaluate(self,event): self.events.append(event); return {'decision':'ALLOW','category':'none'}

class BrowserTests(unittest.TestCase):
    def browser(self,resolver=lambda host:['93.184.216.34'],fetcher=None,blocked=()):
        self.observer=Observer(); self.calls=[]
        def default(url,host,address):
            self.calls.append((url,host,address))
            return 200,{'mime':'text/html'},b'<title>Research</title><script>secret JS</script><p>Hello</p><a href="/next">Next</a>'
        return BrowserGateway(resolver=resolver,fetcher=fetcher or default,watchdog=self.observer,blocked_addresses=blocked,enabled=lambda:True)
    def test_reads_text_links_and_marks_external_content_untrusted(self):
        result=self.browser().open('https://example.org/#fragment')
        self.assertTrue(result['ok']); self.assertEqual(result['trust'],'untrusted_external_content')
        self.assertNotIn('secret JS',result['text']); self.assertEqual(result['links'][0]['url'],'https://example.org/next')
        self.assertEqual(self.calls[0][2],'93.184.216.34'); self.assertNotIn('#',result['url'])
        self.assertFalse(result['capabilities']['forms'])
    def test_dns_private_mixed_and_transition_addresses_are_blocked_before_fetch(self):
        for address in ('127.0.0.1','192.168.0.118','10.0.0.1','169.254.169.254','100.64.0.1','::1','fe80::1','fc00::1','::ffff:127.0.0.1','64:ff9b::c0a8:1','2002:c0a8:101::1'):
            with self.subTest(address=address):
                result=self.browser(resolver=lambda host:['93.184.216.34',address]).open('https://example.org/')
                self.assertFalse(result['ok']); self.assertFalse(self.calls)
    def test_redirect_to_private_host_is_blocked_without_second_connection(self):
        calls=[]
        def fetch(url,host,address): calls.append(url); return 302,{'location':'https://192.168.0.118/'},b''
        result=self.browser(fetcher=fetch).open('https://example.org/')
        self.assertFalse(result['ok']); self.assertEqual(len(calls),1)
        self.assertEqual(result['safety']['category'],'private_network_access')
    def test_redirect_dns_rebinding_is_checked_again(self):
        dns=[]; calls=[]
        def resolve(host): dns.append(host); return ['93.184.216.34'] if len(dns)==1 else ['127.0.0.1']
        def fetch(url,host,address): calls.append(url); return 302,{'location':'/next'},b''
        result=self.browser(resolver=resolve,fetcher=fetch).open('https://example.org/')
        self.assertFalse(result['ok']); self.assertEqual(len(calls),1); self.assertEqual(len(dns),2)
    def test_local_public_interfaces_and_neighbor_prefixes_are_blocked(self):
        result=self.browser(blocked=['93.184.216.0/24']).open('https://example.org/')
        self.assertFalse(result['ok']); self.assertFalse(self.calls)
    def test_credentials_protocols_ports_and_local_names_are_rejected(self):
        for url in ('file:///etc/shadow','http://example.org/','https://user:password@example.org/',
                    'https://example.org:8443/','https://localhost/','https://router.local/',
                    'https://[::1]/','https://example.org/\nHeader: bad','https://example.org\\@127.0.0.1/'):
            with self.subTest(url=url):
                with self.assertRaises(BrowserBlocked): normalize_url(url)
    def test_tls_connect_uses_numeric_address_with_original_host_for_sni(self):
        raw=MagicMock(); context=MagicMock()
        with patch('kwod.browser_gateway.ssl.create_default_context',return_value=context),patch('kwod.browser_gateway.socket.socket',return_value=raw):
            conn=PinnedHTTPS('example.org','93.184.216.34'); conn.connect()
            raw.connect.assert_called_once_with(('93.184.216.34',443))
            context.wrap_socket.assert_called_once_with(raw,server_hostname='example.org')
    def test_watchdog_and_operator_stop_prevent_connections(self):
        browser=self.browser()
        browser.watchdog.evaluate=lambda event:{'decision':'PAUSE_FOR_REVIEW','category':'watchdog_unavailable'}
        self.assertFalse(browser.open('https://example.org/')['ok']); self.assertFalse(self.calls)
        browser=self.browser()
        with patch('kwod.browser_gateway.stopped',return_value=True):
            self.assertEqual(browser.open('https://example.org/')['safety']['decision'],'PAUSE_FOR_REVIEW')
            self.assertFalse(self.calls)
    def test_observer_allows_provisioned_navigation_and_rejects_private_dns(self):
        with patch('kwod.watchdog.browser_enabled',return_value=True):
            self.assertEqual(rule({'kind':'browser_navigation','arguments':{'url':'https://example.org/','addresses':['93.184.216.34']}}),('ALLOW','none'))
            self.assertEqual(rule({'kind':'browser_navigation','arguments':{'url':'https://example.org/','addresses':['127.0.0.1']}}),('BLOCK','private_network_access'))
    def test_missing_service_returns_clear_failure(self):
        self.assertFalse(BrowserClient('missing-browser-socket').open('https://example.org/')['ok'])
    def test_unsupported_and_oversized_content_are_rejected_before_body_read(self):
        for mime,length,category in (('application/octet-stream','10','unsupported_content'),('text/html','1048577','response_limit')):
            conn=MagicMock(); response=conn.getresponse.return_value; response.status=200
            response.getheader.side_effect=lambda key,default=None:{'Content-Type':mime,'Content-Length':length}.get(key,default)
            with patch('kwod.browser_gateway.PinnedHTTPS',return_value=conn):
                with self.assertRaises(BrowserBlocked) as caught: fetch('https://example.org/','example.org','93.184.216.34')
                self.assertEqual(caught.exception.category,category); response.read1.assert_not_called()
                self.assertEqual(conn.request.call_args.args[0],'GET')
                self.assertNotIn('Cookie',conn.request.call_args.kwargs['headers'])
                self.assertNotIn('Authorization',conn.request.call_args.kwargs['headers'])
    def test_unsupported_pages_do_not_become_repeated_guardrail_probes(self):
        from kwod.watchdog import WatchdogState
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); state=WatchdogState(root/'ledger',root/'PAUSE',root/'status')
            try:
                for attempt in range(4):
                    result=state.evaluate({'kind':'browser_navigation','arguments':{'url':'https://example.org/file.pdf','policy_block':'unsupported_content'}})
                    self.assertEqual(result['decision'],'BLOCK')
                self.assertFalse((root/'PAUSE').exists())
            finally: state.close()
    def test_configuration_preserves_objective_and_financial_state(self):
        import importlib.util
        path=Path(__file__).parents[1]/'deploy/configure_browser.py'
        spec=importlib.util.spec_from_file_location('configure_browser',path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp); initialize(store,'Find your own work')
            before=store.db.execute('SELECT count(*) FROM financial_event').fetchone()[0]; store.close()
            module.configure(temp)
            store=Store(temp)
            try:
                cp=store.db.execute('SELECT * FROM checkpoint').fetchone()
                self.assertEqual(cp['objective'],'Find your own work')
                self.assertTrue(store.archive.get(cp['config_ref'])['browser_access'])
                self.assertEqual(store.db.execute('SELECT count(*) FROM financial_event').fetchone()[0],before)
                self.assertIsNone(store.db.execute('SELECT born_at FROM instance').fetchone()[0])
            finally: store.close()
