"""Prepare cumulative autonomy on the dedicated Ubuntu host; never starts inference."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from datetime import datetime, timezone

SOURCE=Path(__file__).resolve().parent
ROOT=Path('/var/lib/kwod-production')
CONTROL=Path('/etc/kwod-s54')
PYTHON='/opt/kwod/current/.venv/bin/python'


def run(*args, capture=False):
    return subprocess.run([str(a) for a in args],check=True,text=True,
        stdout=subprocess.PIPE if capture else None).stdout


def as_runtime(script,*args):
    return run('runuser','-u','kwod-runtime','--',PYTHON,SOURCE/script,*args)


def write(path, text, mode=0o644):
    from kwod.store import atomic_write
    if path.is_symlink(): raise ValueError('linked_control_file')
    atomic_write(path,text.encode(),mode)


def main():
    from kwod.safety import stopped
    if os.geteuid()!=0 or SOURCE!=Path('/opt/kwod/current/deploy').resolve():
        raise ValueError('run_installed_release_with_sudo')
    if stopped(): raise ValueError('existing_safety_stop_requires_operator_resolution')
    for unit in ('kwod-production.service','kwod-runtime.service'):
        if subprocess.run(['systemctl','is-active','--quiet',unit]).returncode==0:
            raise ValueError('stop_worker_before_preparation')
    as_runtime('configure_s54.py','--check')
    if CONTROL.is_symlink(): raise ValueError('linked_control_directory')
    CONTROL.mkdir(mode=0o755,exist_ok=True)
    if CONTROL.stat().st_uid!=0 or CONTROL.stat().st_mode & 0o022: raise ValueError('unsafe_control_directory')
    # Remove previous workloads before snapshotting session/application files.
    subprocess.run(['systemctl','stop','kwod-s54-guard.service'],capture_output=True)
    from s54_firewall import stop_containers
    stop_containers()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=Path('/var/lib/kwod-s54-backups')/stamp
    backup.mkdir(parents=True,mode=0o700)
    backup.parent.chmod(0o700)
    # Root-owned archive is not downloadable by the agent. Preserve symlinks in
    # package/browser data without following them into other host paths.
    with tarfile.open(backup/'before.tar.gz','w:gz',dereference=False) as archive:
        for item in (ROOT,CONTROL,Path('/etc/kwod-signer.json'),Path('/etc/systemd/system/kwod-production.service')):
            if item.exists(): archive.add(item,arcname=str(item).lstrip('/'))
    write(backup/'source-release.txt',str(SOURCE.parent)+'\n',0o600)
    # A failed preparation must not leave signing enabled from an earlier run.
    signer_settings=Path('/etc/kwod-signer.json')
    settings=json.loads(signer_settings.read_text())
    settings['signing_enabled']=False; write(signer_settings,json.dumps(settings))
    if (CONTROL/'profile.json').exists():
        old=json.loads((CONTROL/'profile.json').read_text())
        for key in ('internet','browser_sessions','services','publication','payments'): old[key]=False
        write(CONTROL/'profile.json',json.dumps(old))
    run('docker','build','-f',SOURCE/'S54.Dockerfile','-t','kwod-s54:prepared',SOURCE)
    image=run('docker','image','inspect','--format','{{.Id}}','kwod-s54:prepared',capture=True).strip()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}',image): raise ValueError('invalid_image')
    # Separate signing runtime already contains this dependency; the relay also
    # independently decodes and verifies the signed bytes before broadcasting.
    run(PYTHON,'-m','pip','install','--no-cache-dir','eth-account==0.14.0')
    run(PYTHON,'-m','pip','check')
    home=ROOT/'agent-home'
    if home.is_symlink(): raise ValueError('linked_agent_home')
    run('install','-d','-o','65532','-g','kwod-workspace','-m','2770',home)
    run('install','-d','-o','65532','-g','kwod-workspace','-m','2770',home/'apps')
    website=ROOT/'public/website'
    run('install','-d','-o','kwod-runtime','-g','kwod-public','-m','2750',website)
    if not (website/'address.json').exists():
        write(website/'address.json',json.dumps({'url':'http://192.168.0.118:8080/','worldwide_reachability_verified':False}),0o640)
        run('chown','kwod-runtime:kwod-public',website/'address.json')
    receipt={'level':'S5.4','version':1,'image':image,'internet':True,'browser_sessions':True,
             'services':True,'publication':True,'payments':False,'prepared_at':stamp,
             'public_endpoint_verified':False}
    write(CONTROL/'profile.json',json.dumps(receipt,indent=2))
    shutil.copyfile(SOURCE/'kwod-s54-guard.service','/etc/systemd/system/kwod-s54-guard.service')
    web=(SOURCE/'kwod-web.service').read_text().replace('/var/lib/kwod/public/website',str(website))
    write(Path('/etc/systemd/system/kwod-s54-web.service'),web)
    # Operator-owned guards must load the new tool definitions and capability rules.
    run('systemctl','restart','kwod-watchdog.service')
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','kwod-s54-guard.service')
    run('systemctl','stop','kwod-web.service')
    run('systemctl','enable','--now','kwod-s54-web.service')
    as_runtime('check_s54.py','--probe')
    # Signer is standalone, root-owned and still has no IP networking.
    signer_source=SOURCE.parent/'src/kwod/payments.py'
    digest=hashlib.sha256(signer_source.read_bytes()).hexdigest()
    run(PYTHON,SOURCE/'install_signer.py','--source',signer_source,'--sha256',digest)
    # All infrastructure probes succeeded. Enable own-funds spending as requested;
    # preparation itself performs no signing, transfer, mail or model call.
    receipt['payments']=True
    write(CONTROL/'profile.json',json.dumps(receipt,indent=2))
    settings['signing_enabled']=True; write(signer_settings,json.dumps(settings))
    run('systemctl','restart','kwod-signer.service')
    as_runtime('configure_s54.py')
    drop=Path('/etc/systemd/system/kwod-production.service.d'); drop.mkdir(exist_ok=True)
    write(drop/'s54.conf','[Unit]\nRequires=kwod-s54-guard.service\nAfter=kwod-s54-guard.service\n')
    run('systemctl','daemon-reload')
    as_runtime('check_s54.py')
    print(json.dumps({'s54_prepared':True,'backup':str(backup),'worker_started':False,
                      'birth_changed':False,'model_calls':0,'mail_sent':False,'payment_sent':False,
                      'public_endpoint_verified':False,'next':'Start the existing production worker when ready.'}))


if __name__=='__main__':
    try: main()
    except BaseException:
        # Fail closed even if a late step failed after enabling the signer.
        if CONTROL.is_dir() and (CONTROL/'profile.json').is_file():
            value=json.loads((CONTROL/'profile.json').read_text())
            for key in ('internet','browser_sessions','services','publication','payments'): value[key]=False
            write(CONTROL/'profile.json',json.dumps(value))
        subprocess.run(['systemctl','stop','kwod-s54-guard.service','kwod-s54-web.service','kwod-signer.service'],capture_output=True)
        raise
