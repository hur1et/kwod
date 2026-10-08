"""Explicit Ubuntu gate: public HTTPS, no LAN/host, browser and persistent home."""
import json
import sys
import uuid
from kwod.executor import DockerExecutor
from kwod.store import Store

script='''import pathlib, socket, urllib.request
with urllib.request.urlopen('https://example.com',timeout=20) as response:
    assert response.status==200
for host,port in [('192.168.0.118',22),('172.30.254.1',22),('169.254.169.254',80)]:
    try: socket.create_connection((host,port),timeout=2)
    except OSError: pass
    else: raise AssertionError('local_network_reachable')
assert not pathlib.Path('/var/run/docker.sock').exists()
assert not pathlib.Path('/etc/kwod-mail/credentials.json').exists()
assert not pathlib.Path('/etc/kwod-openrouter/api.key').exists()
assert not pathlib.Path('/var/lib/kwod/private/state.sqlite').exists()
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(); page.set_content('<title>KWOD browser check</title>')
    assert page.title()=='KWOD browser check'
    browser.close()
pathlib.Path('/home/agent/.world-probe').write_text('persistent')
print('public_https_ok lan_host_blocked browser_ok secrets_absent')
'''
def main():
    store=Store('/var/lib/kwod')
    try:
        executor=DockerExecutor(store.root/'workspace',store.archive,sys.argv[1],world_access=True)
        result=executor.execute(uuid.uuid4().hex,{'command':"python -c "+__import__('shlex').quote(script),'timeout_seconds':90})
        if not result['ok']: raise ValueError('world_probe_failed: '+result['stderr'])
        again=executor.execute(uuid.uuid4().hex,{'command':"python -c \"from pathlib import Path; p=Path('/home/agent/.world-probe'); assert p.read_text()=='persistent'; p.unlink()\"",'timeout_seconds':20})
        if not again['ok']: raise ValueError('home_persistence_failed')
        print(json.dumps({'public_https':True,'lan_host_blocked':True,'browser':True,
                          'persistent_home':True,'model_calls':0,'birth_triggered':False}))
    finally: store.close()

if __name__=='__main__': main()
