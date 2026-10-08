"""Read actual installed production state without creating a Store or calling models."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
from kwod.config import START_OBJECTIVE,constitution
from kwod.store import encode

SERVICES=('kwod-watchdog.service','kwod-mail-safety.service','kwod-browser.service')

def property(unit,name):
    result=subprocess.run(['systemctl','show',unit,'--property='+name,'--value'],capture_output=True,text=True)
    return result.stdout.strip() if result.returncode==0 else None

def protected(path,mode,gid=None):
    try:
        info=path.lstat()
        return stat.S_ISREG(info.st_mode) and info.st_size>0 and info.st_uid==0 and stat.S_IMODE(info.st_mode)==mode and (gid is None or info.st_gid==gid)
    except OSError: return False

def archived(root,ref):
    raw=(root/'private/archive'/ref).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ref: raise ValueError('archive_hash_mismatch')
    return json.loads(raw)

def state(root):
    database=root/'private/state.sqlite'
    if not database.is_file(): return None
    db=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True); db.row_factory=sqlite3.Row
    try:
        instance=db.execute('SELECT * FROM instance').fetchone()
        cp=db.execute('SELECT * FROM checkpoint').fetchone()
        if not instance or not cp: return None
        return {'instance':dict(instance),'checkpoint':dict(cp),'config':archived(root,cp['config_ref']),
            'prompt':archived(root,instance['prompt_hash']),
            'context':archived(root,cp['context_ref']),
            'attempts':db.execute('SELECT count(*) FROM model_attempt').fetchone()[0],
            'births':db.execute("SELECT count(*) FROM trajectory_event WHERE kind='birth'").fetchone()[0]}
    finally: db.close()

def main():
    import pwd
    root=Path('/var/lib/kwod-production'); release=Path('/opt/kwod/current').resolve()
    control=Path('/etc/kwod-production'); checks={}; observations={}
    readback={}
    try:
        result=subprocess.run(['runuser','-u','kwod-runtime','--',str(release/'.venv/bin/python'),str(release/'deploy/read_production_state.py')],capture_output=True,text=True,timeout=20,check=True)
        readback=json.loads(result.stdout); saved=readback['state']
    except (OSError,ValueError,sqlite3.Error,KeyError,subprocess.SubprocessError): saved=None
    checks['production_store_separate']=saved is not None and saved['instance']['id']=='prod' and saved['instance']['mode']=='prod' and root.resolve()!=Path('/var/lib/kwod').resolve()
    checks['start_context_persisted']=saved is not None and saved['checkpoint']['objective']==START_OBJECTIVE and bool(saved['context']) and saved['context'][0]=={'role':'user','content':START_OBJECTIVE}
    checks['constitution_current']=saved is not None and saved['prompt']==constitution('prod')
    checks['config_current']=saved is not None and all(saved['config'].get(key)==value for key,value in {'mode':'prod','model':'gpt-6-astra','world_access':False,'watchdog_enabled':True,'browser_access':True}.items())
    checks['birth_absent']=saved is not None and saved['instance']['born_at'] is None and saved['births']==0 and not (control/'BORN').exists()
    checks['no_production_model_attempts']=saved is not None and saved['attempts']==0
    observations['model_attempts']=saved['attempts'] if saved else None
    observations['born_at']=saved['instance']['born_at'] if saved else None
    checks['openrouter_key_protected']=protected(Path('/etc/kwod-openrouter/api.key'),0o600)
    checks['mail_credentials_protected']=protected(Path('/etc/kwod-mail/credentials.json'),0o640,65532)
    checks['safety_not_paused']=not any(Path('/etc/kwod-safety',name).exists() for name in ('STOP','WATCHDOG_PAUSE'))
    checks['watchdog_required']=Path('/etc/kwod-safety/WATCHDOG_REQUIRED').is_file()
    checks['persistent_mail_ledger']=readback.get('mail_ledger_valid') is True
    observations['mail_ledger_rows']=readback.get('mail_ledger_rows')
    try:
        receipt=json.loads((control/'preparation.json').read_text())
        expected={str(p.relative_to(release)) for p in (release/'src/kwod').glob('*.py')}
        checks['deployed_source_current']=receipt['release']==release.name and set(receipt['source_hashes'])==expected and all(hashlib.sha256((release/name).read_bytes()).hexdigest()==digest for name,digest in receipt['source_hashes'].items())
        checks['mail_code_manifest_current']=all(name in receipt['source_hashes'] for name in ('src/kwod/mail_delivery.py','src/kwod/mail_gateway.py','src/kwod/mail_channel.py','src/kwod/mail_safety_service.py'))
        checks['gate_processes_current']=all(property(unit,'InvocationID')==receipt['service_invocations'][unit] for unit in SERVICES)
        checks['mail_ledger_pointer_current']=(control/'mail-ledger.path').read_text().strip()==str(root/'private/mail-outbound.sqlite')==receipt['mail_ledger']
    except (OSError,ValueError,KeyError):
        for key in ('deployed_source_current','mail_code_manifest_current','gate_processes_current','mail_ledger_pointer_current'): checks[key]=False
    for unit in SERVICES:
        checks[unit+'_active']=property(unit,'ActiveState')=='active'
    for folder,file in (('kwod-watchdog','control.sock'),('kwod-mail-safety','gate.sock'),('kwod-browser','browser.sock')):
        path=Path('/run',folder,file)
        try: checks[folder+'_socket']=stat.S_ISSOCK(path.lstat().st_mode)
        except OSError: checks[folder+'_socket']=False
    for unit in ('kwod-runtime.service','kwod-production.service'):
        observed=property(unit,'ActiveState'); observations[unit+'_state']=observed
        checks[unit+'_stopped']=observed=='inactive'
        checks[unit+'_disabled']=property(unit,'UnitFileState')=='disabled'
    try:
        uid=pwd.getpwnam('kwod-runtime').pw_uid; running=[]
        for process in Path('/proc').iterdir():
            if not process.name.isdigit(): continue
            try:
                if process.stat().st_uid!=uid: continue
                args=(process/'cmdline').read_bytes().decode(errors='replace').split(chr(0))
                if 'run' in args and any(Path(arg).name=='kwod' for arg in args): running.append(int(process.name))
            except (OSError,ValueError): continue
        observations['manual_worker_pids']=running; checks['no_manual_cli_worker']=not running
    except (OSError,KeyError): observations['manual_worker_pids']=None; checks['no_manual_cli_worker']=False
    try:
        unit=Path('/etc/systemd/system/kwod-production.service').read_text()
        checks['production_service_current']=unit==(release/'deploy/kwod-production.service').read_text()
        checks['astra_openrouter_wiring']='--mode prod --data /var/lib/kwod-production run --openrouter-prod' in (property('kwod-production.service','ExecStart') or '') and 'LoadCredential=openrouter.key:/etc/kwod-openrouter/api.key' in unit
        checks['worker_birth_condition']='ConditionPathExists=/etc/kwod-production/BORN' in unit
    except OSError: checks['production_service_current']=checks['astra_openrouter_wiring']=checks['worker_birth_condition']=False
    image=saved['config'].get('executor_image') if saved else None
    checks['executor_image_present']=bool(image) and subprocess.run(['docker','image','inspect',image],capture_output=True).returncode==0
    checks['browser_firewall_active']=property('kwod-browser-firewall.service','ActiveState')=='active'
    try:
        uid=pwd.getpwnam('kwod-browser').pw_uid
        checks['browser_firewall_hooks']=all(subprocess.run([binary,'-w','-C','OUTPUT','-m','owner','--uid-owner',str(uid),'-j',chain],capture_output=True).returncode==0 for binary,chain in (('iptables','KWOD-BROWSER4'),('ip6tables','KWOD-BROWSER6')))
    except (OSError,KeyError): checks['browser_firewall_hooks']=False
    try:
        public=sqlite3.connect((root/'public/public.sqlite').as_uri()+'?mode=ro',uri=True)
        try: snapshot=json.loads(public.execute('SELECT payload FROM snapshot WHERE id=1').fetchone()[0])
        finally: public.close()
        checks['production_projection']=snapshot['mode']=='prod' and snapshot['status']=='not_born'
    except (OSError,ValueError,sqlite3.Error,TypeError,KeyError): checks['production_projection']=False
    ok=all(checks.values())
    print(json.dumps({'checks':checks,'observations':observations,'all_five_preparation_checks_pass':ok,
        'blockers':[name for name,value in checks.items() if not value],
        'birth_authorization_marker_present':(control/'BORN').exists(),
        'scope':'nonfinancial production preparation; explicit birth and fresh credit observation remain separate; wallet payment test is optional'},indent=2))
    if not ok: raise SystemExit(1)

if __name__=='__main__': main()
