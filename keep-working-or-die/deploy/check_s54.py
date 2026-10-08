"""Actual installed capabilities and bounded Linux probes; no economic actions."""
import argparse
import json
from pathlib import Path
import shlex
import socket
import subprocess
import tempfile
import uuid
from kwod.autonomy import profile
from kwod.executor import DockerExecutor
from kwod.services import Services
from kwod.store import Archive, Store


def active(name):
    return subprocess.run(['systemctl','is-active','--quiet',name],capture_output=True).returncode==0


def check(probe=False):
    cfg=profile()
    checks={'network_guard_running':active('kwod-s54-guard.service'),
            'watchdog_running':active('kwod-watchdog.service'),
            'static_host_running':active('kwod-s54-web.service')}
    if probe:
        # Temporary own files only; never reset the agent's work or browser data.
        with tempfile.TemporaryDirectory(prefix='s54-probe-',dir='/var/lib/kwod-production') as temp:
            root=Path(temp); root.chmod(0o750)
            (root/'workspace').mkdir(mode=0o2770); (root/'agent-home').mkdir(mode=0o2770)
            for part in ('workspace','agent-home'): (root/part).chmod(0o2770)
            archive=Archive(root/'private/archive')
            executor=DockerExecutor(root/'workspace',archive,cfg['image'],world_access=True,persistent_home=True)
            public_ip=json.loads(Path('/etc/kwod-s54/network-receipt.json').read_text())['public_egress']
            script=r'''import json, pathlib, socket, urllib.request
with urllib.request.urlopen('https://example.org',timeout=20) as r: assert r.status==200
for host,port in [('192.168.0.118',22),('172.30.254.1',22),('169.254.169.254',80),(PUBLIC_IP,22)]:
    try: c=socket.create_connection((host,port),timeout=2)
    except OSError: pass
    else: c.close(); raise AssertionError('private_or_host_reachable')
for path in ('/var/run/docker.sock','/etc/kwod-mail/credentials.json','/etc/kwod-openrouter/api.key','/var/lib/kwod-signer/identity.json'):
    assert not pathlib.Path(path).exists()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    c=p.chromium.launch_persistent_context('/home/agent/probe-browser',executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=c.new_page(); page.set_content('<input id="name"><button onclick="document.title=document.querySelector(\'#name\').value">Set</button>')
    page.locator('#name').fill('forms-ok'); page.locator('button').click(); assert page.title()=='forms-ok'
    c.add_cookies([{'name':'probe','value':'persisted','domain':'example.org','path':'/'}]); c.close()
pathlib.Path('/home/agent/persisted').write_text('yes')
print('public_https private_blocked no_host_secrets javascript_forms_ok')
'''.replace('PUBLIC_IP',repr(public_ip))
            result=executor.execute(uuid.uuid4().hex,{'command':'python -c '+shlex.quote(script),'timeout_seconds':90})
            checks['network_and_browser_probe']=result['ok']
            if not result['ok']: raise ValueError('s54_linux_probe_failed: '+result['stderr'][-2000:])
            again='''from pathlib import Path
assert Path('/home/agent/persisted').read_text()=='yes'
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    c=p.chromium.launch_persistent_context('/home/agent/probe-browser',executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
    assert any(x['name']=='probe' and x['value']=='persisted' for x in c.cookies()); c.close()
'''
            result=executor.execute(uuid.uuid4().hex,{'command':'python -c '+shlex.quote(again),'timeout_seconds':30})
            checks['home_and_cookie_persistence']=result['ok']
            # Exercise durable service start/idempotence/stop with an empty server.
            manager=Services(root,archive)
            try:
                created=manager.start('probe','python -m http.server 8081 --bind 0.0.0.0',8081)
                duplicate=manager.start('probe','python -m http.server 8081 --bind 0.0.0.0',8081)
                checks['service_start_and_dedupe']=created['running'] and duplicate.get('existing') is True
            finally: manager.stop('probe')
            checks['service_stopped']=not any(x['name']=='kwod-s54-app-probe' for x in manager.list()['services'])
    else:
        with_store=Store('/var/lib/kwod-production',mode='prod')
        try:
            cp=with_store.db.execute("SELECT config_ref FROM checkpoint WHERE instance_id='prod'").fetchone()
            actual=with_store.archive.get(cp[0])
            checks['runtime_configuration']=actual['autonomy_level']=='S5.4' and actual['executor_image']==cfg['image']
        finally: with_store.close()
        from kwod.wallet_gateway import signer
        status=signer({'method':'status','arguments':{}})
        checks['signer_enabled']=status.get('signing_enabled') is True and status.get('chain_id')==8453
        checks['all_capabilities_prepared']=all(cfg.get(key) is True for key in ('internet','browser_sessions','services','publication','payments'))
    result={'checks':checks,'all_checks_pass':all(checks.values()),'model_calls':0,'mail_sent':False,
            'payment_sent':False,'birth_changed':False,'worker_started':False,
            'public_endpoint_verified':False,'real_payment_receipt_verified':False}
    print(json.dumps(result,indent=2))
    if not result['all_checks_pass']: raise ValueError('s54_installation_not_ready')


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--probe',action='store_true')
    check(parser.parse_args().probe)
