"""Prepare actual agent environment and hosting, never start inference."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

def run(*args,capture=False):
    return subprocess.run([str(x) for x in args],check=True,text=True,
        stdout=subprocess.PIPE if capture else None).stdout

def main():
    raise ValueError('world_mode_withheld: use Prepare-Safeguards.ps1; controlled browser access is pending')
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve():
        raise ValueError('run_verified_installed_release_only')
    if subprocess.run(['systemctl','is-active','--quiet','kwod-runtime']).returncode==0:
        raise ValueError('stop_runtime_before_preparing')
    run('iptables','-w','-S','DOCKER-USER')
    run('docker','build','-f',source/'WorldExecutor.Dockerfile','-t','kwod-world:prepared',source)
    image=run('docker','image','inspect','--format','{{.Id}}','kwod-world:prepared',capture=True).strip()
    if not re.fullmatch('sha256:[a-f0-9]{64}',image): raise ValueError('invalid_image')
    run('install','-d','-o','65532','-g','kwod-workspace','-m','0700','/var/lib/kwod/agent-home')
    website=Path('/var/lib/kwod/public/website')
    if website.is_symlink(): raise ValueError('hosting_path_is_link')
    run('install','-d','-o','kwod-runtime','-g','kwod-public','-m','2750',website)
    address=website/'address.json'
    if address.is_symlink(): raise ValueError('address_is_link')
    # Existing private LAN address from deployment. Operator can later supply
    # a real public HTTPS endpoint; this does not invent worldwide reachability.
    url='http://192.168.0.118:8080/'
    address.write_text(json.dumps({'url':url})); run('chown','kwod-runtime:kwod-public',address); address.chmod(0o640)
    for name in ('kwod-world-firewall.service','kwod-web.service'):
        shutil.copyfile(source/name,Path('/etc/systemd/system')/name)
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','kwod-world-firewall.service')
    # Integration gate uses the real egress boundary and browser. No mailbox,
    # wallet or OpenRouter calls and no modelworker are involved.
    run('runuser','-u','kwod-runtime','--','env','PYTHONPATH=/opt/kwod/current/src',
        '/opt/kwod/current/.venv/bin/python',source/'check_world_access.py',image)
    run('runuser','-u','kwod-runtime','--','env','PYTHONPATH=/opt/kwod/current/src',
        '/opt/kwod/current/.venv/bin/python',source/'configure_world.py',image,url)
    run('systemctl','enable','--now','kwod-web.service')
    print(json.dumps({'hosting_url':url,'public_https':False,
        'worldwide_reachability_verified':False,'worker_started_by_action':False,
        'birth_triggered_by_action':False,'wallet_signing_enabled':False}))

if __name__=='__main__': main()
