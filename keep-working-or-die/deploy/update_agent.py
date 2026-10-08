"""Refresh services for an existing born agent, without birth or worker start."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess

def run(*args): subprocess.run([str(arg) for arg in args],check=True)

def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve(): raise ValueError('installed_release_required')
    if subprocess.run(['systemctl','is-active','--quiet','kwod-production.service']).returncode==0:
        raise ValueError('stop_production_worker_before_update')
    database=Path('/var/lib/kwod-production/private/state.sqlite')
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute("SELECT born_at FROM instance WHERE id='prod' AND mode='prod'").fetchone()
    if not row or not row[0] or not Path('/etc/kwod-production/BORN').is_file():
        raise ValueError('existing_born_production_required')
    for name in ('kwod-watchdog.service','kwod-mail-safety.service','kwod-production.service'):
        text=(source/name).read_text()
        if name != 'kwod-production.service':
            text=text.replace('InaccessiblePaths=', 'InaccessiblePaths=/var/lib/kwod-production/private /var/lib/kwod-production/workspace /var/lib/kwod-production/agent-home ')
        (Path('/etc/systemd/system')/name).write_text(text)
    run('systemctl','daemon-reload')
    run('systemctl','restart','kwod-watchdog.service','kwod-mail-safety.service')
    run('/opt/kwod/current/.venv/bin/python',source/'prepare_asset_observation.py')
    run('/opt/kwod/current/.venv/bin/python',source/'prepare_cost_observation.py')
    run('systemctl','restart','kwod-public.service')
    if Path('/etc/systemd/system/kwod-operator.service').exists():
        run('systemctl','restart','kwod-operator.service')
    print(json.dumps({'existing_birth_preserved':True,'birth':False,'worker_started':False,
                     'mail_sent':False,'wallet_signed':False,
                     'safety_markers_preserved':True,'operator_only_mail_wake':True,
                     'cost_observation_prepared':True}))

if __name__=='__main__': main()
