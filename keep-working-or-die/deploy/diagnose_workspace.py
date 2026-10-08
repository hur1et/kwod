"""Read-only diagnosis of the installed workspace boundary; never invoke watchdog."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing

ROOT=Path('/var/lib/kwod-production')

def probe(root=ROOT):
    from kwod.store import Archive
    from kwod.tools import FileTools
    from kwod.watchdog import rule
    # Avoid constructors which create directories or chmod the workspace.
    archive=object.__new__(Archive); archive.path=root/'private/archive'
    files=object.__new__(FileTools); files.root=root/'workspace'; files.archive=archive
    result={'runtime_uid':os.geteuid() if hasattr(os,'geteuid') else None,'runtime_groups':os.getgroups() if hasattr(os,'getgroups') else [],
            'workspace_exists':files.root.is_dir(),
            'workspace_writable_by_permission':os.access(files.root,os.W_OK),
            'files':{},'recent_file_calls':[]}
    for name in ('RIGHTS_AND_LIMITS.md','MISSION.md','memory.md'):
        args={'path':'/workspace/'+name,'offset':0,'max_bytes':1}
        item={'installed_rule':rule({'kind':'tool_attempt','tool':'read_file','arguments':args})}
        try:
            path=files.path(args['path'])
            info=path.stat()
            item.update(owner_uid=info.st_uid,group_gid=info.st_gid,mode=oct(info.st_mode & 0o7777))
            with path.open('rb') as stream: stream.read(1)
            item['readable']=True
        except (OSError,ValueError) as exc:
            item.update(readable=False,error=type(exc).__name__)
        result['files'][name]=item
    with closing(sqlite3.connect((root/'private/state.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        result['runtime_state']=dict(db.execute("SELECT state,reason,wake_at FROM runtime_state WHERE instance_id='prod'").fetchone())
        for row in db.execute("SELECT tool,status,arguments_ref,result_ref,ended_at FROM tool_call WHERE tool IN ('read_file','write_file','list_files') ORDER BY rowid DESC LIMIT 5"):
            call={'tool':row['tool'],'status':row['status'],'ended_at':row['ended_at']}
            try:
                args=json.loads(archive.get(row['arguments_ref']))
                call['path']=str(args.get('path',''))[:256]
                if row['result_ref']:
                    saved=archive.get(row['result_ref'])
                    call['ok']=saved.get('ok'); call['error']=saved.get('error')
                    safety=saved.get('safety') or {}
                    call['safety']={key:safety[key] for key in ('decision','category','observation_id') if key in safety}
            except (OSError,ValueError,TypeError,AttributeError) as exc:
                call['diagnostic_error']=type(exc).__name__
            result['recent_file_calls'].append(call)
    return result

def main():
    if '--runtime-probe' in sys.argv:
        if os.geteuid()==0: raise ValueError('runtime_identity_required')
        print(json.dumps(probe(),ensure_ascii=True)); return
    if os.geteuid()!=0: raise ValueError('sudo_required')
    result={'scope':'read-only diagnosis; no model, credentials, mail, birth, worker start, permission repair or safety reset',
            'installed_release':str(Path('/opt/kwod/current').resolve()),
            'stop_active':Path('/etc/kwod-safety/STOP').exists(),
            'safety_pause_active':Path('/etc/kwod-safety/WATCHDOG_PAUSE').exists()}
    for unit in ('kwod-production.service','kwod-watchdog.service'):
        response=subprocess.run(['systemctl','show',unit,'--property=ActiveState,MainPID,ExecMainStartTimestamp'],capture_output=True,text=True,timeout=10)
        result[unit]=dict(line.split('=',1) for line in response.stdout.splitlines() if '=' in line)
    with tempfile.TemporaryDirectory(prefix='kwod-workspace-diagnostic-') as temp:
        directory=Path(temp); directory.chmod(0o755)
        script=directory/'probe.py'; shutil.copyfile(Path(__file__).resolve(),script); script.chmod(0o644)
        response=subprocess.run(['/usr/sbin/runuser','-u','kwod-runtime','--','/opt/kwod/current/.venv/bin/python',str(script),'--runtime-probe'],capture_output=True,text=True,timeout=30)
        result['probe_exit_code']=response.returncode
        if response.returncode==0: result['probe']=json.loads(response.stdout)
        else:
            # Tracebacks may contain private context; do not print them.
            result['probe_error']='runtime_probe_failed'
    print(json.dumps(result,ensure_ascii=True,indent=2))

if __name__=='__main__': main()
