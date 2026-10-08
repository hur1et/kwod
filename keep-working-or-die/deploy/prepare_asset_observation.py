"""Prepare read-only observations. No birth, worker start, signing, mail or model."""
import os
from pathlib import Path
import shutil
import subprocess

if __name__=='__main__':
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve(): raise ValueError('installed_release_required')
    subprocess.run(['install','-d','-o','root','-g','root','-m','0755','/var/lib/kwod-assets'],check=True)
    for name in ('kwod-assets.service','kwod-assets.timer'):
        shutil.copyfile(source/name,Path('/etc/systemd/system')/name)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','kwod-assets.timer'],check=True)
    subprocess.run(['systemctl','start','kwod-assets.service'],check=True)
    print('Read-only resource observations prepared. No worker start, birth, mail or payment.')
