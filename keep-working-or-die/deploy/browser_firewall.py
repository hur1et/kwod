"""Persistent host-owned OUTPUT policy for the isolated browser service UID."""
import ipaddress
import json
import os
from pathlib import Path
import pwd
import subprocess

V4=('0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8','169.254.0.0/16',
    '172.16.0.0/12','192.168.0.0/16','192.0.0.0/24','192.0.2.0/24','198.18.0.0/15',
    '198.51.100.0/24','203.0.113.0/24','224.0.0.0/4','240.0.0.0/4')
V6=('::/96','::ffff:0:0/96','64:ff9b::/96','64:ff9b:1::/48','100::/64','2001::/32',
    '2001:db8::/32','2002::/16','fc00::/7','fe80::/10','ff00::/8')

def run(*args): return subprocess.run([str(x) for x in args],check=True,capture_output=True,text=True)
def apply():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    uid=pwd.getpwnam('kwod-browser').pw_uid
    networks=[ipaddress.ip_network(x,strict=False) for x in json.loads(Path('/etc/kwod-browser/blocked-addresses.json').read_text())]
    dns=[ipaddress.ip_address(x) for x in json.loads(Path('/etc/kwod-browser/dns-resolvers.json').read_text())]
    for binary,chain,version,blocked in (('iptables','KWOD-BROWSER4',4,V4),('ip6tables','KWOD-BROWSER6',6,V6)):
        run(binary,'-w','-S','OUTPUT')
        if subprocess.run([binary,'-w','-S',chain],capture_output=True).returncode: run(binary,'-w','-N',chain)
        run(binary,'-w','-F',chain)
        # Only configured DNS infrastructure may use port 53. No arbitrary UDP.
        for address in dns:
            if address.version!=version: continue
            for protocol in ('udp','tcp'): run(binary,'-w','-A',chain,'-d',address,'-p',protocol,'--dport','53','-j','ACCEPT')
        run(binary,'-w','-A',chain,'-m','addrtype','--dst-type','LOCAL','-j','REJECT')
        for network in list(blocked)+[str(n) for n in networks if n.version==version]:
            run(binary,'-w','-A',chain,'-d',network,'-j','REJECT')
        args=[binary,'-w','-A',chain,'-p','tcp','--dport','443']
        if version==6: args+=['-d','2000::/3']
        run(*args,'-j','ACCEPT')
        run(binary,'-w','-A',chain,'-j','REJECT')
        jump=[binary,'-w','-C','OUTPUT','-m','owner','--uid-owner',str(uid),'-j',chain]
        if subprocess.run(jump,capture_output=True).returncode:
            run(binary,'-w','-I','OUTPUT','1','-m','owner','--uid-owner',uid,'-j',chain)
    print(json.dumps({'browser_kernel_firewall':True,'web_transport':'tcp_443',
                      'dns':'configured_resolvers_only','arbitrary_udp':False}))

if __name__=='__main__': apply()
