"""Exercise generated firewall policy against representative outbound packets."""
import importlib.util
import ipaddress
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

class BrowserFirewallTests(unittest.TestCase):
    def test_policy_rejects_lan_metadata_ssh_and_udp_but_allows_https_and_dns(self):
        source=Path(__file__).parents[1]/'deploy/browser_firewall.py'
        fake_pwd=types.SimpleNamespace(getpwnam=lambda name:types.SimpleNamespace(pw_uid=991))
        with patch.dict(sys.modules,{'pwd':fake_pwd}):
            spec=importlib.util.spec_from_file_location('browser_firewall',source)
            module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        calls=[]
        def run(*args): calls.append([str(x) for x in args])
        def config(path,*args,**kwargs):
            return json.dumps(['93.184.216.34/32','2001:4860:abcd::/64']) if path.name=='blocked-addresses.json' else json.dumps(['127.0.0.53'])
        with patch.object(module.os,'geteuid',return_value=0,create=True),patch.object(module,'run',side_effect=run),patch.object(module.subprocess,'run',return_value=types.SimpleNamespace(returncode=1)),patch.object(Path,'read_text',config):
            module.apply()
        def verdict(destination,protocol,port,local=False):
            address=ipaddress.ip_address(destination); binary='iptables' if address.version==4 else 'ip6tables'
            for args in calls:
                if args[0]!=binary or '-A' not in args: continue
                if '-d' in args and address not in ipaddress.ip_network(args[args.index('-d')+1],strict=False): continue
                if '-p' in args and args[args.index('-p')+1]!=protocol: continue
                if '--dport' in args and int(args[args.index('--dport')+1])!=port: continue
                if '--dst-type' in args and not local: continue
                return args[args.index('-j')+1]
            return None
        for destination,protocol,port,expected in (
            ('8.8.8.8','tcp',443,'ACCEPT'),('8.8.8.8','tcp',22,'REJECT'),
            ('8.8.8.8','udp',443,'REJECT'),('8.8.8.8','udp',53,'REJECT'),
            ('127.0.0.53','udp',53,'ACCEPT'),('127.0.0.53','tcp',443,'REJECT'),
            ('192.168.0.118','tcp',443,'REJECT'),('169.254.169.254','tcp',443,'REJECT'),
            ('93.184.216.34','tcp',443,'REJECT'),('2001:4860:4860::8888','tcp',443,'ACCEPT'),
            ('2001:4860:abcd::2','tcp',443,'REJECT'),('fc00::1','tcp',443,'REJECT'),
            ('2002:c0a8:101::1','tcp',443,'REJECT')):
            with self.subTest(destination=destination,protocol=protocol,port=port):
                self.assertEqual(verdict(destination,protocol,port),expected)
        self.assertEqual(verdict('8.8.8.8','tcp',443,local=True),'REJECT')
        jumps=[args for args in calls if '-I' in args]
        self.assertEqual(len(jumps),2)
        self.assertTrue(all('--uid-owner' in args and '991' in args for args in jumps))
