"""Withhold generic network, preserve objective and durable work."""
from pathlib import Path
from kwod.config import Config, RIGHTS_AND_LIMITS
from kwod.store import Store, worker_lock, atomic_write

def configure(data_path='/var/lib/kwod'):
    store=Store(data_path)
    try:
        with worker_lock(store.root):
            cp=store.db.execute("SELECT * FROM checkpoint WHERE instance_id='dev'").fetchone()
            if cp is None: raise ValueError('initialize_first')
            home=store.root/'agent-home'
            changed=dict(store.archive.get(cp['config_ref']),world_access=False,
                         agent_home=home.is_dir() and not home.is_symlink(),watchdog_enabled=True)
            Config(**changed); ref=store.archive.put(changed)
            path=store.root/'workspace/RIGHTS_AND_LIMITS.md'
            if path.is_symlink(): raise ValueError('rights_document_is_link')
            atomic_write(path,RIGHTS_AND_LIMITS.encode(),mode=0o660)
            with store.transaction():
                store.db.execute("UPDATE checkpoint SET config_ref=? WHERE instance_id='dev'",(ref,))
                store.db.execute("UPDATE instance SET config_hash=? WHERE id='dev'",(ref,))
                store.event('safeguards_prepared',{'config_ref':ref,'terminal_network':'none',
                    'economic_event':False,'controlled_browser':'not_yet_available'})
    finally: store.close()

if __name__=='__main__': configure()
