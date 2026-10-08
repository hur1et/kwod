"""Host-owned network boundary and independent workload stop monitor."""
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.request

BRIDGE, NETWORK, SUBNET = 'kwod-world0', 'kwod-world', '172.30.254.0/24'
ROOT = Path('/etc/kwod-s54')
BLOCKED = ('0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8',
           '169.254.0.0/16','172.16.0.0/12','192.168.0.0/16','192.0.0.0/24',
           '192.0.2.0/24','192.88.99.0/24','198.18.0.0/15','198.51.100.0/24',
           '203.0.113.0/24','224.0.0.0/4','240.0.0.0/4')


def run(*args):
    return subprocess.run(list(args),check=True,capture_output=True,text=True,timeout=30).stdout


def stop_containers():
    names = run('docker','ps','-a','--filter','label=kwod.s54=1','--format','{{.Names}}').splitlines()
    for name in names:
        if not re.fullmatch(r'kwod-(?:[a-f0-9]{32}|s54-(?:browser|app-[a-z][a-z0-9-]{0,31}))',name):
            raise ValueError('unknown_labelled_workload')
        run('docker','rm','-f',name)


def own_egress():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('https://api.ipify.org?format=json',timeout=10) as response:
        value = str(ipaddress.IPv4Address(json.loads(response.read(1024))['ip']))
    if not ipaddress.ip_address(value).is_global: raise ValueError('egress_not_public')
    return value


def rules(public_ip):
    if not ipaddress.IPv4Address(public_ip).is_global: raise ValueError('invalid_public_egress')
    # Only replies to inbound connections may return to local clients.
    reply = ['-m','conntrack','--ctstate','ESTABLISHED','--ctdir','REPLY','-j','RETURN']
    return {'KWOD-S54-OUT':[reply] + [['-d',net,'-j','REJECT'] for net in (*BLOCKED,public_ip+'/32')]
                + [['-m','addrtype','--dst-type','LOCAL','-j','REJECT'],['-j','RETURN']],
            'KWOD-S54-HOST':[reply,['-j','REJECT']]}


def snapshot():
    return {chain:run('iptables','-w','-S',chain) for chain in ('KWOD-S54-OUT','KWOD-S54-HOST','DOCKER-USER','INPUT','FORWARD')}


def apply(public_ip):
    run('iptables','-w','-S','DOCKER-USER')
    first = next((line for line in run('iptables','-w','-S','FORWARD').splitlines() if line.startswith('-A ')), '')
    if first != '-A FORWARD -j DOCKER-USER': raise ValueError('docker_user_not_first_forward_hook')
    if subprocess.run(['docker','network','inspect',NETWORK],capture_output=True).returncode:
        run('docker','network','create','--driver','bridge','--subnet',SUBNET,
            '--opt','com.docker.network.bridge.name='+BRIDGE,
            '--opt','com.docker.network.bridge.enable_icc=false','--label','kwod.world=1',NETWORK)
    network = json.loads(run('docker','network','inspect',NETWORK))[0]
    if (network['Driver']!='bridge' or network.get('EnableIPv6') or
            network['Options'].get('com.docker.network.bridge.name')!=BRIDGE or
            network['Options'].get('com.docker.network.bridge.enable_icc')!='false' or
            [row['Subnet'] for row in network['IPAM']['Config']] != [SUBNET]):
        raise ValueError('network_configuration_conflict')
    if network.get('Containers'): raise ValueError('network_still_in_use')
    # Workloads are stopped first. Only dedicated chains change; SSH is untouched.
    for chain, entries in rules(public_ip).items():
        if subprocess.run(['iptables','-w','-S',chain],capture_output=True).returncode:
            run('iptables','-w','-N',chain)
        run('iptables','-w','-F',chain)
        for entry in entries: run('iptables','-w','-A',chain,*entry)
    for parent,child in [('DOCKER-USER','KWOD-S54-OUT'),('INPUT','KWOD-S54-HOST')]:
        old = ['-i',BRIDGE,'-j',child]
        while subprocess.run(['iptables','-w','-C',parent,*old],capture_output=True).returncode==0:
            run('iptables','-w','-D',parent,*old)
        run('iptables','-w','-I',parent,'1',*old)
    return snapshot()


def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    from kwod.safety import stopped
    stop_containers()
    if stopped(): raise ValueError('safety_stop_active')
    ip = own_egress()
    expected = apply(ip)
    (ROOT/'network-receipt.json').write_text(json.dumps({'public_egress':ip,'rules':expected}))
    run('systemd-notify','--ready')
    next_ip = time.monotonic()+60
    try:
        while not stopped():
            if snapshot()!=expected: raise ValueError('network_rules_changed')
            if time.monotonic()>=next_ip:
                if own_egress()!=ip: raise ValueError('public_egress_changed')
                next_ip=time.monotonic()+60
            time.sleep(2)
    except BaseException:
        Path('/etc/kwod-safety/WATCHDOG_PAUSE').touch(mode=0o644,exist_ok=True)
        raise
    finally: stop_containers()


if __name__=='__main__': main()
