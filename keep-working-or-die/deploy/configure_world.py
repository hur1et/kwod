"""Set prepared capability configuration under runtime lock, no model or birth."""
import json
import sys
from pathlib import Path
from kwod.config import Config
from kwod.store import Store, worker_lock, atomic_write

def configure(image, url, *, data_path='/var/lib/kwod',
              capabilities_path=Path('/opt/kwod/current/deploy/WORLD_ACCESS.md')):
    store=Store(data_path)
    try:
        with worker_lock(store.root):
            if store.db.execute("SELECT count(*) FROM tool_call WHERE status IN ('planned','running','outcome_unknown')").fetchone()[0]:
                raise ValueError('resolve_pending_tools_before_configuration')
            if store.db.execute("SELECT count(*) FROM model_attempt WHERE status='sent'").fetchone()[0]:
                raise ValueError('resolve_sent_request_before_configuration')
            row=store.db.execute("SELECT * FROM checkpoint WHERE instance_id='dev'").fetchone()
            if row is None: raise ValueError('initialize_first')
            previous=store.archive.get(row['config_ref'])
            changed=dict(previous,world_access=True,executor_image=image)
            Config(**changed)
            ref=store.archive.put(changed)
            content=Path(capabilities_path).read_bytes()
            workspace=store.root/'workspace'
            for name,raw in [('WORLD_ACCESS.md',content),('WORLD_ADDRESS.json',json.dumps({
                'url':url,'public_https':False,'worldwide_reachability_verified':False}).encode())]:
                dest=workspace/name
                if dest.is_symlink(): raise ValueError('workspace_document_is_link')
                atomic_write(dest,raw,mode=0o660)
            with store.transaction():
                store.db.execute("UPDATE checkpoint SET config_ref=? WHERE instance_id='dev'",(ref,))
                store.db.execute("UPDATE instance SET config_hash=? WHERE id='dev'",(ref,))
                store.event('world_access_prepared',{'previous_config_ref':row['config_ref'],
                    'config_ref':ref,'url':url,'worker_started_by_action':False,
                    'birth_triggered_by_action':False,'wallet_signing_enabled':False})
        print(json.dumps({'world_access_prepared':True,'url':url,
                          'worker_started_by_action':False,'birth_triggered_by_action':False}))
    finally: store.close()

if __name__=='__main__': configure(sys.argv[1],sys.argv[2])
