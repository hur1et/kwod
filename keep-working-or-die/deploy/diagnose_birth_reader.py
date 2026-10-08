"""Operator-only read diagnosis in the live service mount namespace. No birth or API."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

PROBE='''import json
import subprocess
import threading
import kwod.operator as operator

original=subprocess.run
def traced(*args,**kwargs):
    kwargs['stdin']=subprocess.DEVNULL
    try:
        result=original(*args,**kwargs)
        if result.returncode:
            print(json.dumps({'reader_exit_code':result.returncode,'reader_error':(result.stderr or '')[-3000:]}),flush=True)
        return result
    except subprocess.CalledProcessError as exc:
        print(json.dumps({'reader_exception':type(exc).__name__,'reader_exit_code':exc.returncode,'reader_error':(exc.stderr or '')[-3000:]}),flush=True)
        raise
    except Exception as exc:
        print(json.dumps({'reader_exception':type(exc).__name__,'reader_errno':getattr(exc,'errno',None)}),flush=True)
        raise
operator.subprocess.run=traced
def test():
    print(json.dumps({'operator_module':operator.__file__,'operator_status':operator.Controller().status()}),flush=True)
thread=threading.Thread(target=test)
thread.start(); thread.join()
'''


def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    pid=subprocess.check_output(['systemctl','show','kwod-operator.service','--property=MainPID','--value'],text=True).strip()
    if not pid.isdigit() or int(pid)<=0: raise ValueError('operator_service_not_running')
    process=Path('/proc')/pid
    service_path=next((value[5:].decode() for value in (process/'environ').read_bytes().split(b'\0') if value.startswith(b'PATH=')),None)
    status=dict(line.split(':',1) for line in (process/'status').read_text().splitlines() if ':' in line)
    helper=['/usr/sbin/runuser','-u','kwod-runtime','--','/opt/kwod/current/.venv/bin/python',
            '/opt/kwod/current/deploy/read_production_state.py','--birth-only']
    env=dict(os.environ)
    if service_path is not None: env['PATH']=service_path
    command=['nsenter','--target',pid,'--mount','--wd=/','--']
    if status.get('NoNewPrivs','').strip()=='1': command+=['/usr/bin/setpriv','--no-new-privs','--']
    command+=helper
    result=subprocess.run(command,capture_output=True,text=True,timeout=20,env=env)
    try: observed=json.loads(result.stdout)
    except ValueError: observed=None
    print(json.dumps({'operator_pid':int(pid),'operator_path':service_path,
        'runuser_in_operator_path':shutil.which('runuser',path=service_path or ''),
        'operator_no_new_privileges':status.get('NoNewPrivs','').strip(),
        'reader_exit_code':result.returncode,'reader_result':observed,
        'reader_error':result.stderr[-3000:],
        'scope':'read-only birth-state diagnostic; no credentials read, no API, no birth, no worker start'},indent=2))
    # nsenter does not inherit seccomp or capability restrictions. Reproduce the
    # actual systemd properties in a temporary unit and trace only status reads.
    properties=('ProtectHome','ProtectSystem','ReadWritePaths','NoNewPrivileges',
        'ProtectKernelTunables','ProtectKernelModules','ProtectControlGroups',
        'PrivateDevices','RestrictAddressFamilies','PrivateTmp','UMask',
        'AmbientCapabilities','CapabilityBoundingSet','SecureBits')
    with tempfile.TemporaryDirectory(prefix='kwod-birth-reader-',dir='/run') as temporary:
        probe=Path(temporary)/'probe.py'; probe.write_text(PROBE); probe.chmod(0o600)
        command=['systemd-run','--wait','--pipe','--collect','--quiet','--property=WorkingDirectory=/']
        for name in properties:
            value=subprocess.check_output(['systemctl','show','kwod-operator.service','--property='+name,'--value'],text=True).strip()
            if value: command.append('--property='+name+'='+value)
        if service_path: command.append('--property=Environment=PATH='+service_path)
        command+=['/opt/kwod/current/.venv/bin/python',str(probe)]
        result=subprocess.run(command,capture_output=True,text=True,timeout=90)
        print(json.dumps({'sandbox_probe_exit_code':result.returncode,'sandbox_probe':result.stdout[-6000:],
            'sandbox_probe_error':result.stderr[-3000:]},indent=2))

if __name__=='__main__': main()
