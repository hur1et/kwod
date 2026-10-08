"""Migrate a stopped existing agent's capabilities without rewriting its life."""
import argparse
import json
from pathlib import Path
from kwod.autonomy import S54_RIGHTS, profile
from kwod.config import Config, constitution
from kwod.store import Store, worker_lock, atomic_write
from kwod.tools import FileTools


def configure(root='/var/lib/kwod-production', *, receipt=None, check=False, disable=False):
    store=Store(root,mode='prod')
    try:
        with worker_lock(store.root):
            cp=store.db.execute("SELECT * FROM checkpoint WHERE instance_id='prod'").fetchone()
            if cp is None: raise ValueError('existing_production_required')
            if store.db.execute("SELECT 1 FROM tool_call WHERE status IN ('running','outcome_unknown')").fetchone():
                raise ValueError('pending_work_requires_completion_or_review')
            if cp['pending_attempt']:
                pending=store.db.execute('SELECT status FROM model_attempt WHERE id=?',(cp['pending_attempt'],)).fetchone()
                if pending is None or pending['status'] not in ('prepared','completed'):
                    raise ValueError('pending_work_requires_completion_or_review')
            if store.db.execute("SELECT 1 FROM model_attempt WHERE status IN ('sent','outcome_unknown')").fetchone():
                state=store.db.execute("SELECT state FROM runtime_state WHERE instance_id='prod'").fetchone()[0]
                if state=='recovery_required': raise ValueError('resolve_uncertain_turn_before_migration')
            if check: return {'migration_ready':True}
            before=store.archive.get(cp['config_ref'])
            changed=dict(before,autonomy_level='S0' if disable else 'S5.4',world_access=not disable,
                         agent_home=True,watchdog_enabled=True)
            if not disable: changed['executor_image']=(receipt or profile())['image']
            config=Config(**changed)
            config_ref=store.archive.put(config.dump())
            prompt=constitution('prod',config.autonomy_level)
            files=FileTools(store.root/'workspace',store.archive)
            if disable:
                from kwod.config import RIGHTS_AND_LIMITS
                rights=RIGHTS_AND_LIMITS
            else: rights=S54_RIGHTS
            contents={'RIGHTS_AND_LIMITS.md':rights,'AUTONOMY.md':rights,
                'BROWSER_ACCESS.md':('Use browser_action for JavaScript, persistent sessions and forms. '
                    'Use browser_open for inexpensive text-only research. /home/agent holds your own sessions and software.'
                    if not disable else 'Only browser_open is enabled. Terminal is offline.'),
                'WORLD_ACCESS.md':rights}
            previous={name:files.artifact(files.path(name)) if files.path(name).exists() else None for name in contents}
            for name,text in contents.items(): files.execute('write_file',{'path':name,'content':text})
            # Keep objective, memory, strategy, birth, balances and interrupted-work
            # evidence. Add a notice to the current context, not a forced restart.
            context=store.archive.get(cp['context_ref'])
            notice={'role':'user','content':f'Operator capability update: {config.autonomy_level}. '
                    'Read AUTONOMY.md. Your existing work, obligations and economic history continue; do not repeat orientation mail or completed actions.'}
            if not cp['pending_attempt'] and (not context or context[-1]!=notice): context.append(notice)
            with store.transaction():
                store.db.execute("UPDATE checkpoint SET config_ref=?,context_ref=? WHERE instance_id='prod'",(config_ref,store.archive.put(context)))
                store.db.execute("UPDATE instance SET config_hash=?,prompt_hash=? WHERE id='prod'",(config_ref,store.archive.put(prompt)))
                store.event('autonomy_changed',{'level':config.autonomy_level,'previous_config_ref':cp['config_ref'],
                    'previous_documents':previous,'birth_changed':False,'model_calls':0},actor='operator')
            from kwod.projection import project
            project(store)
            return {'configured':config.autonomy_level,'existing_life_preserved':True,'worker_started':False}
    finally: store.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--check',action='store_true'); parser.add_argument('--disable',action='store_true')
    args=parser.parse_args(); print(json.dumps(configure(check=args.check,disable=args.disable)))
