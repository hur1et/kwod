"""Host-owned egress boundary for one dedicated Docker bridge (iptables only)."""
import json
import os
import subprocess

NETWORK='kwod-world'
BRIDGE='kwod-world0'
SUBNET='172.30.254.0/24'
BLOCKED=('0.0.0.0/8','10.0.0.0/8','100.64.0.0/10','127.0.0.0/8',
         '169.254.0.0/16','172.16.0.0/12','192.168.0.0/16',
         '192.0.0.0/24','198.18.0.0/15','224.0.0.0/4','240.0.0.0/4')

def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True).stdout

def apply():
    if os.geteuid()!=0:
        raise ValueError('root_required')
    # nftables backend has no DOCKER-USER chain. Refuse rather than claim
    # isolation with rules Docker never traverses.
    run('iptables','-w','-S','DOCKER-USER')
    result=subprocess.run(['docker','network','inspect',NETWORK],capture_output=True,text=True)
    if result.returncode:
        run('docker','network','create','--driver','bridge','--subnet',SUBNET,
            '--opt','com.docker.network.bridge.name='+BRIDGE,
            '--opt','com.docker.network.bridge.enable_icc=false',
            '--label','kwod.world=1',NETWORK)
    data=json.loads(run('docker','network','inspect',NETWORK))[0]
    if (data['Driver']!='bridge' or data.get('EnableIPv6') or
        data.get('Labels',{}).get('kwod.world')!='1' or
        data['Options'].get('com.docker.network.bridge.name')!=BRIDGE or
        data['Options'].get('com.docker.network.bridge.enable_icc')!='false' or
        [c['Subnet'] for c in data['IPAM']['Config']]!=[SUBNET]):
        raise ValueError('network_configuration_conflict')
    if data.get('Containers'):
        raise ValueError('stop_agent_containers_before_firewall_changes')
    for chain in ('KWOD-WORLD','KWOD-WORLD-HOST'):
        check=subprocess.run(['iptables','-w','-S',chain],capture_output=True)
        if check.returncode: run('iptables','-w','-N',chain)
        run('iptables','-w','-F',chain)
    for cidr in BLOCKED:
        run('iptables','-w','-A','KWOD-WORLD','-d',cidr,'-j','REJECT')
    run('iptables','-w','-A','KWOD-WORLD','-j','RETURN')
    # INPUT handles connections to any host address, including a public IP.
    run('iptables','-w','-A','KWOD-WORLD-HOST','-j','REJECT')
    for parent,child in [('DOCKER-USER','KWOD-WORLD'),('INPUT','KWOD-WORLD-HOST')]:
        check=subprocess.run(['iptables','-w','-C',parent,'-i',BRIDGE,'-j',child],capture_output=True)
        if check.returncode: run('iptables','-w','-I',parent,'1','-i',BRIDGE,'-j',child)
    print(json.dumps({'internet_egress':'enabled','lan_access':'blocked',
                      'host_services':'blocked','ipv6':'disabled','bridge':BRIDGE}))

if __name__=='__main__': apply()
