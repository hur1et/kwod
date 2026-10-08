"""Provision only the controlled browser. No worker, birth or inference."""
import json
import os
from pathlib import Path
import pwd
import shutil
import subprocess
import time
import ipaddress

def run(*args): subprocess.run([str(arg) for arg in args],check=True)
def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve(): raise ValueError('installed_release_required')
    if subprocess.run(['systemctl','is-active','--quiet','kwod-runtime']).returncode==0: raise ValueError('stop_worker_first')
    if not Path('/etc/kwod-safety/WATCHDOG_REQUIRED').exists(): raise ValueError('prepare_safeguards_first')
    if any(Path('/etc/kwod-safety',name).exists() for name in ('STOP','WATCHDOG_PAUSE')): raise ValueError('operator_review_required')
    try: pwd.getpwnam('kwod-browser')
    except KeyError: run('useradd','--system','--gid','kwod-workspace','--groups','kwod-payments','--no-create-home','--shell','/usr/sbin/nologin','kwod-browser')
    run('usermod','-aG','kwod-payments','kwod-browser')
    run('install','-d','-o','root','-g','root','-m','0755','/etc/kwod-browser')
    run('systemctl','stop','kwod-browser.service') if Path('/etc/systemd/system/kwod-browser.service').exists() else None
    interfaces=json.loads(subprocess.check_output(['ip','-j','address','show'],text=True))
    addresses=sorted({item['local']+'/'+str(item['prefixlen']) for interface in interfaces for item in interface.get('addr_info',[])})
    path=Path('/etc/kwod-browser/blocked-addresses.json'); path.write_text(json.dumps(addresses)); path.chmod(0o644)
    dns=[]
    for line in Path('/etc/resolv.conf').read_text().splitlines():
        fields=line.split()
        if len(fields)>=2 and fields[0]=='nameserver': dns.append(str(ipaddress.ip_address(fields[1].split('%')[0])))
    if not dns: raise ValueError('configured_dns_resolver_required')
    dns_path=Path('/etc/kwod-browser/dns-resolvers.json'); dns_path.write_text(json.dumps(dns)); dns_path.chmod(0o644)
    shutil.copyfile(source/'kwod-browser.service','/etc/systemd/system/kwod-browser.service')
    shutil.copyfile(source/'kwod-browser-firewall.service','/etc/systemd/system/kwod-browser-firewall.service')
    shutil.copyfile(source/'kwod-watchdog.service','/etc/systemd/system/kwod-watchdog.service')
    marker=Path('/etc/kwod-safety/BROWSER_ENABLED'); marker.write_text('Public HTTPS read only.\n'); marker.chmod(0o644)
    run('systemd-analyze','verify','/etc/systemd/system/kwod-browser.service','/etc/systemd/system/kwod-watchdog.service','/etc/systemd/system/kwod-browser-firewall.service')
    run('systemctl','daemon-reload'); run('systemctl','restart','kwod-watchdog.service')
    run('systemctl','enable','kwod-browser-firewall.service'); run('systemctl','restart','kwod-browser-firewall.service')
    run('systemctl','enable','--now','kwod-browser.service')
    for attempt in range(50):
        if Path('/run/kwod-browser/browser.sock').exists() and Path('/run/kwod-watchdog/control.sock').exists(): break
        time.sleep(.1)
    else: raise ValueError('browser_socket_not_ready')
    discovery=subprocess.check_output(['runuser','-u','kwod-runtime','--','env','PYTHONPATH=/opt/kwod/current/src',
        '/opt/kwod/current/.venv/bin/python',str(source/'discover_browser_egress.py')],text=True)
    addresses.append(json.loads(discovery)['public_egress_address'])
    path.write_text(json.dumps(addresses)); path.chmod(0o644)
    run('systemctl','stop','kwod-browser.service')
    run('systemctl','restart','kwod-browser-firewall.service')
    run('systemctl','start','kwod-browser.service')
    for attempt in range(50):
        if Path('/run/kwod-browser/browser.sock').exists(): break
        time.sleep(.1)
    else: raise ValueError('browser_socket_not_ready')
    run('runuser','-u','kwod-runtime','--','env','PYTHONPATH=/opt/kwod/current/src',
        '/opt/kwod/current/.venv/bin/python',source/'check_browser_access.py')
    run('runuser','-u','kwod-runtime','--','env','PYTHONPATH=/opt/kwod/current/src',
        '/opt/kwod/current/.venv/bin/python',source/'configure_browser.py')
    if subprocess.run(['systemctl','is-active','--quiet','kwod-browser.service']).returncode!=0: raise ValueError('browser_service_not_running')
    print(json.dumps({'controlled_browser':'public_https_read_only','terminal_network':'none',
        'browser_service_running':True,'private_destinations':'blocked_before_connection',
        'own_public_egress_blocked':True,'javascript':False,'cookies':False,'forms':False,'model_calls':0,'mail_sent':False,
        'worker_started':False,'birth':False,'live_network_probe':'example.org_passed'}))

if __name__=='__main__': main()
