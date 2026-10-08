"""Operator safety intervention. No changes to agent files, DB or balances."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

STOP=Path('/etc/kwod-safety/STOP')
UNITS=('kwod-operator.service','kwod-runtime.service','kwod-production.service','kwod-mail-safety.service','kwod-browser.service','kwod-watchdog.service','kwod-web.service','kwod-signer.service','kwod-assets.timer','kwod-assets.service','kwod-cost-observer.timer','kwod-cost-observer.service')

def stop():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    STOP.parent.mkdir(mode=0o755,exist_ok=True)
    if STOP.parent.is_symlink() or STOP.parent.stat().st_uid!=0: raise ValueError('unsafe_safety_directory')
    os.chmod(STOP.parent,0o755)
    temp=STOP.parent/('.stop-'+os.urandom(8).hex())
    with temp.open('x') as stream:
        stream.write(datetime.now(timezone.utc).isoformat()); stream.flush(); os.fsync(stream.fileno())
    temp.chmod(0o644); os.replace(temp,STOP)
    directory=os.open(STOP.parent,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    failures=[]
    for unit in ('kwod-s54-guard.service','kwod-s54-web.service', *UNITS):
        exists=subprocess.run(['systemctl','show',unit,'--property=LoadState','--value'],capture_output=True,text=True)
        if exists.stdout.strip()=='not-found': continue
        subprocess.run(['systemctl','kill','--signal=SIGKILL','--kill-who=all',unit],capture_output=True)
        if subprocess.run(['systemctl','stop',unit],capture_output=True).returncode: failures.append(unit)
    # Also cover manually started CLI/mail helpers, not only the service cgroup.
    subprocess.run(['pkill','-KILL','-u','kwod-runtime'],capture_output=True)
    subprocess.run(['pkill','-KILL','-u','kwod-safety'],capture_output=True)
    subprocess.run(['pkill','-KILL','-u','kwod-signer'],capture_output=True)
    subprocess.run(['pkill','-KILL','-u','kwod-browser'],capture_output=True)
    containers=subprocess.run(['docker','ps','-a','--format','{{.Names}}'],capture_output=True,text=True)
    if containers.returncode: failures.append('docker_inventory')
    else:
        for name in containers.stdout.splitlines():
            if re.fullmatch(r'kwod-(?:[a-f0-9]{32}|s54-(?:browser|app-[a-z][a-z0-9-]{0,31}))',name):
                if subprocess.run(['docker','rm','-f',name],capture_output=True).returncode: failures.append(name)
    if failures: raise RuntimeError('safety_stop_incomplete: '+','.join(failures))
    print(json.dumps({'safety_stop':True,'economic_event':False,'files_and_history_preserved':True,
                      'in_flight_effects_may_be_unknown':True,'automatic_resume':False}))

if __name__=='__main__': stop()
