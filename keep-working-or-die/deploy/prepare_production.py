"""Prepare five production prerequisites. No birth or inference or worker start."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import time

ROOT=Path('/var/lib/kwod-production')
def run(*args): subprocess.run([str(x) for x in args],check=True)
def value(unit,property):
    return subprocess.check_output(['systemctl','show',unit,'--property='+property,'--value'],text=True).strip()
def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve(): raise ValueError('installed_release_required')
    for unit in ('kwod-runtime.service','kwod-production.service'):
        if value(unit,'ActiveState') in ('active','activating','deactivating'): raise ValueError('worker_must_be_stopped')
    for name in ('STOP','WATCHDOG_PAUSE'):
        if Path('/etc/kwod-safety',name).exists(): raise ValueError('safety_review_required')
    if Path('/etc/kwod-production/BORN').exists(): raise ValueError('birth_already_authorized')
    if not Path('/etc/kwod-safety/BROWSER_ENABLED').exists(): raise ValueError('browser_preparation_required')
    run('systemctl','disable','kwod-runtime.service')
    for path,owner,group,mode in ((ROOT,'kwod-runtime','kwod-public','0750'),(ROOT/'private','kwod-runtime','kwod-workspace','0700'),
        (ROOT/'workspace','kwod-runtime','kwod-workspace','2770'),(ROOT/'public','kwod-runtime','kwod-public','2750'),
        (ROOT/'agent-home','65532','65532','2770'),(Path('/etc/kwod-production'),'root','root','0755')):
        run('install','-d','-o',owner,'-g',group,'-m',mode,path)
    old=Path('/var/lib/kwod/private/state.sqlite')
    db=sqlite3.connect(old.as_uri()+'?mode=ro',uri=True); db.row_factory=sqlite3.Row
    try:
        event=db.execute("SELECT payload_ref FROM trajectory_event WHERE kind='deployment_observed' ORDER BY id DESC LIMIT 1").fetchone()
        payload=json.loads((old.parent/'archive'/event['payload_ref']).read_text())
        image=payload['built_executor_image']
    finally: db.close()
    if (ROOT/'private/state.sqlite').exists():
        db=sqlite3.connect((ROOT/'private/state.sqlite').as_uri()+'?mode=ro',uri=True)
        try:
            ref=db.execute("SELECT config_ref FROM checkpoint WHERE instance_id='prod'").fetchone()[0]
            image=json.loads((ROOT/'private/archive'/ref).read_text())['executor_image']
        finally: db.close()
    run('docker','image','inspect',image)
    # Preserve account-wide dedupe/history. Never overwrite an existing prod ledger.
    legacy=Path('/var/lib/kwod/private/mail-outbound.sqlite'); ledger=ROOT/'private/mail-outbound.sqlite'
    if legacy.exists() and not ledger.exists():
        old_mail=sqlite3.connect(legacy.as_uri()+'?mode=ro',uri=True); new_mail=sqlite3.connect(ledger)
        try: old_mail.backup(new_mail)
        finally: old_mail.close(); new_mail.close()
        run('chown','kwod-runtime:kwod-workspace',ledger); ledger.chmod(0o600)
    fence=legacy.parent/'mail-restore-review-required'
    if fence.exists():
        target=ledger.parent/fence.name; shutil.copyfile(fence,target)
        run('chown','kwod-runtime:kwod-workspace',target); target.chmod(0o600)
    run('runuser','-u','kwod-runtime','--','env','PYTHONPATH=/opt/kwod/current/src',
        '/opt/kwod/current/.venv/bin/python',source/'configure_production.py',image)
    pointer=Path('/etc/kwod-production/mail-ledger.path'); pointer.write_text(str(ledger)+'\n'); pointer.chmod(0o644)
    shutil.copyfile(source/'kwod-production.service','/etc/systemd/system/kwod-production.service')
    # Observer is independent: switching projection does not start a worker.
    public=(source/'kwod-public.service').read_text().replace('/var/lib/kwod/public/public.sqlite',str(ROOT/'public/public.sqlite'))
    public=public.replace('ExecStart=/opt/kwod/current/.venv/bin/kwod serve',
        'ExecStart=/opt/kwod/current/.venv/bin/kwod serve --safety-file /var/lib/kwod/public/safety/status.json')
    public=public.replace('InaccessiblePaths=', 'InaccessiblePaths=/var/lib/kwod-production/private /var/lib/kwod-production/workspace /var/lib/kwod-production/agent-home ')
    Path('/etc/systemd/system/kwod-public.service').write_text(public)
    for name in ('kwod-watchdog.service','kwod-mail-safety.service','kwod-browser.service'):
        text=(source/name).read_text().replace('InaccessiblePaths=', 'InaccessiblePaths=/var/lib/kwod-production/private /var/lib/kwod-production/workspace /var/lib/kwod-production/agent-home ')
        Path('/etc/systemd/system',name).write_text(text)
    run('systemctl','daemon-reload'); run('systemd-analyze','verify','/etc/systemd/system/kwod-production.service')
    run('systemctl','disable','kwod-production.service')
    for unit in ('kwod-watchdog.service','kwod-mail-safety.service','kwod-browser.service','kwod-public.service'): run('systemctl','restart',unit)
    # Wait for actual processes/socket startup rather than hardcode service health.
    for attempt in range(50):
        if all(Path('/run',folder,file).exists() for folder,file in (('kwod-watchdog','control.sock'),('kwod-mail-safety','gate.sock'),('kwod-browser','browser.sock'))): break
        time.sleep(.1)
    else: raise ValueError('gateway_socket_not_ready')
    receipt={'release':source.parent.name,'image':image,'mail_ledger':str(ledger),
        'source_hashes':{str(p.relative_to(source.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (source.parent/'src/kwod').glob('*.py')},
        'service_invocations':{unit:value(unit,'InvocationID') for unit in ('kwod-watchdog.service','kwod-mail-safety.service','kwod-browser.service')}}
    receipt_path=Path('/etc/kwod-production/preparation.json'); receipt_path.write_text(json.dumps(receipt)); receipt_path.chmod(0o644)
    run('/opt/kwod/current/.venv/bin/python',source/'check_production_readiness.py')

if __name__=='__main__': main()
