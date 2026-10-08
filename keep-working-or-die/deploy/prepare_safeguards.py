"""Install safeguards without inference, mail, payment or birth."""
import json
import os
from pathlib import Path
import pwd
import grp
import shutil
import subprocess

def run(*args): subprocess.run([str(x) for x in args],check=True)
def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve(): raise ValueError('installed_release_required')
    if subprocess.run(['systemctl','is-active','--quiet','kwod-runtime']).returncode==0:
        raise ValueError('stop_runtime_before_preparation')
    run('install','-d','-o','root','-g','root','-m','0755','/etc/kwod-safety')
    try: grp.getgrnam('kwod-payments')
    except KeyError: run('groupadd','--system','kwod-payments')
    run('usermod','-aG','kwod-payments','kwod-runtime')
    run('install','-d','-o','root','-g','root','-m','0700','/var/lib/kwod-safety')
    run('install','-d','-o','root','-g','kwod-public','-m','2750','/var/lib/kwod/public/safety')
    marker=Path('/etc/kwod-safety/WATCHDOG_REQUIRED')
    marker.write_text('Independent safety observer required.\n'); marker.chmod(0o644)
    try: pwd.getpwnam('kwod-safety')
    except KeyError: run('useradd','--system','--gid','kwod-workspace','--no-create-home','--shell','/usr/sbin/nologin','kwod-safety')
    shutil.copyfile(source/'kwod-mail-safety.service','/etc/systemd/system/kwod-mail-safety.service')
    shutil.copyfile(source/'kwod-watchdog.service','/etc/systemd/system/kwod-watchdog.service')
    if Path('/etc/systemd/system/kwod-web.service').exists():
        shutil.copyfile(source/'kwod-web.service','/etc/systemd/system/kwod-web.service')
    if Path('/etc/systemd/system/kwod-signer.service').exists():
        dropin=Path('/etc/systemd/system/kwod-signer.service.d'); dropin.mkdir(exist_ok=True)
        (dropin/'safety.conf').write_text('[Unit]\nConditionPathExists=!/etc/kwod-safety/STOP\nConditionPathExists=!/etc/kwod-safety/WATCHDOG_PAUSE\n')
    run('runuser','-u','kwod-runtime','--','env','PYTHONPATH=/opt/kwod/current/src',
        '/opt/kwod/current/.venv/bin/python',source/'configure_safety.py')
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','kwod-watchdog.service')
    # Starts only an idle reviewer service. Inference occurs only for future drafts.
    run('systemctl','enable','--now','kwod-mail-safety.service')
    active=subprocess.run(['systemctl','is-active','--quiet','kwod-mail-safety.service']).returncode==0
    watchdog_active=subprocess.run(['systemctl','is-active','--quiet','kwod-watchdog.service']).returncode==0
    paused=any(Path('/etc/kwod-safety',name).exists() for name in ('STOP','WATCHDOG_PAUSE'))
    if not paused and not (active and watchdog_active): raise ValueError('safety_service_not_running')
    print(json.dumps({'safeguards_prepared':True,'terminal_network':'none',
        'mail_gate':'independent_service','mail_gate_service_running':active,
        'watchdog_service_running':watchdog_active,'safety_paused':paused,
        'operator_stop_active':Path('/etc/kwod-safety/STOP').exists(),
        'model_calls_by_preparation':0,'mail_sent':False,
        'worker_started':False,'birth':False,'controlled_browser':'pending'}))

if __name__=='__main__': main()
