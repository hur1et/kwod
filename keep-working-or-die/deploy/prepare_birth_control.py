"""Install operator UI only. Does not enable birth or query financial providers."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
from kwod.store import atomic_write,encode

def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    source=Path(__file__).resolve().parent
    if source!=Path('/opt/kwod/current/deploy').resolve(): raise ValueError('installed_release_required')
    control=Path('/etc/kwod-production')
    if not (control/'preparation.json').exists(): raise ValueError('production_preparation_required')
    subprocess.run(['/opt/kwod/current/.venv/bin/python',str(source/'check_production_readiness.py')],check=True)
    password_file=control/'operator-password.json'
    if not password_file.exists():
        password=getpass.getpass('Neues Passwort für Birth-Steuerung (mindestens 12 Zeichen): ')
        if len(password)<12 or password!=getpass.getpass('Passwort wiederholen: '): raise ValueError('password_invalid_or_mismatch')
        salt=secrets.token_bytes(32); iterations=600000
        atomic_write(password_file,encode({'salt':salt.hex(),'iterations':iterations,
            'digest':hashlib.pbkdf2_hmac('sha256',password.encode(),salt,iterations).hex()}),0o600)
    if password_file.is_symlink(): raise ValueError('unsafe_password_file')
    password_file.chmod(0o600); os.chown(password_file,0,0)
    shutil.copyfile(source/'kwod-operator.service','/etc/systemd/system/kwod-operator.service')
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','enable','--now','kwod-operator.service'],check=True)
    subprocess.run(['systemctl','restart','kwod-operator.service'],check=True)
    subprocess.run(['systemctl','is-active','--quiet','kwod-operator.service'],check=True)
    print(json.dumps({'operator_ui_prepared':True,'user':'operator','local_url':'http://127.0.0.1:8766',
        'model_calls_by_preparation':0,'wallet_transactions_by_preparation':0,'birth_by_preparation':False,'worker_start_by_preparation':False}))

if __name__=='__main__': main()
