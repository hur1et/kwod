"""Withdraw capabilities, preserve financial journals and existing birth/history."""
import json
import os
from pathlib import Path
import subprocess
from kwod.store import atomic_write


def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    subprocess.run(['systemctl','stop','kwod-production.service'],check=True)
    path=Path('/etc/kwod-s54/profile.json')
    value=json.loads(path.read_text())
    for key in ('internet','browser_sessions','services','publication','payments'): value[key]=False
    atomic_write(path,json.dumps(value).encode(),0o644)
    subprocess.run(['systemctl','stop','kwod-s54-guard.service','kwod-s54-web.service','kwod-signer.service'],check=True)
    settings=Path('/etc/kwod-signer.json'); value=json.loads(settings.read_text()); value['signing_enabled']=False
    atomic_write(settings,json.dumps(value).encode(),0o644)
    # Stop/revoke first even when an uncertain turn prevents configuration edits.
    subprocess.run(['runuser','-u','kwod-runtime','--','/opt/kwod/current/.venv/bin/python',
        '/opt/kwod/current/deploy/configure_s54.py','--disable'],check=True)
    drop=Path('/etc/systemd/system/kwod-production.service.d/s54.conf')
    if drop.is_file(): drop.unlink()
    subprocess.run(['systemctl','daemon-reload'],check=True)
    print(json.dumps({'s54_revoked':True,'worker_started':False,'history_and_payment_journals_preserved':True}))


if __name__=='__main__': main()
