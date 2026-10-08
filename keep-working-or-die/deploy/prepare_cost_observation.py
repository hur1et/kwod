"""Install a read-only cost observer without starting the production worker."""
import os
from pathlib import Path
import shutil
import subprocess

def run(*args): subprocess.run([str(x) for x in args],check=True)

if __name__=='__main__':
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve(): raise ValueError('installed_release_required')
    if not Path('/var/lib/kwod-production/private/state.sqlite').exists(): raise ValueError('production_store_required')
    run('install','-d','-o','kwod-safety','-g','kwod-workspace','-m','0750','/var/lib/kwod-safety')
    usage=Path('/var/lib/kwod-safety/mail-review-usage.jsonl')
    if not usage.exists(): run('install','-o','kwod-safety','-g','kwod-workspace','-m','0660','/dev/null',usage)
    for name in ('kwod-cost-observer.service','kwod-cost-observer.timer'):
        shutil.copyfile(source/name,Path('/etc/systemd/system')/name)
    run('systemctl','daemon-reload')
    run('systemctl','enable','--now','kwod-cost-observer.timer')
    run('systemctl','start','kwod-cost-observer.service')
    print('{"cost_observation":"prepared","model_calls":0,"mail_sent":false,"worker_started":false,"birth":false}')
