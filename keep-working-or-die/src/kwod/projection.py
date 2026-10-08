"""A separate database, populated only from fixed templates and typed fields."""
import json
import os
from pathlib import Path
import sqlite3

from .store import utcnow
from .tools import ACTIVITIES

STATES = {'not_born', 'ready', 'working', 'sleeping', 'idle', 'provider_unavailable',
          'recovery_required', 'maintenance'}
EVENTS = {'birth': 'Production birth recorded', 'initialized': 'Instance prepared', 'request_prepared': 'Model request prepared',
          'response_observed': 'Model response observed', 'tool_intent': 'Tool started',
          'tool_result': 'Tool finished', 'provider_error': 'Provider unavailable',
          'request_outcome_unknown': 'Request outcome unknown',
          'operator_intervention': 'Operator intervention',
          'state_changed': 'State changed', 'activity_changed': 'Activity changed',
          'autonomy_changed':'Autonomy configuration changed'}


def project(store):
    target = store.root / 'public'
    # Preserve the deployment's group inheritance; an unprivileged chmod can
    # silently clear setgid when the directory belongs to another group.
    target.mkdir(mode=0o750, exist_ok=True)
    db = sqlite3.connect(target / 'public.sqlite', timeout=10)
    try:
        db.executescript('''CREATE TABLE IF NOT EXISTS snapshot (id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS public_event (id INTEGER PRIMARY KEY AUTOINCREMENT,
                private_event_id INTEGER NOT NULL UNIQUE, occurred_at TEXT NOT NULL,
                published_at TEXT NOT NULL, schema_version INTEGER NOT NULL, kind TEXT NOT NULL, label TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS cursor (id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL);''')
        db.execute('CREATE TABLE IF NOT EXISTS asset_history (observation_id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, observed_at TEXT NOT NULL, currency TEXT NOT NULL, amount_micro INTEGER NOT NULL)')
        db.execute('CREATE INDEX IF NOT EXISTS asset_history_time ON asset_history(asset_id,observed_at)')
        db.execute('CREATE TABLE IF NOT EXISTS asset_cursor (id INTEGER PRIMARY KEY, row_id INTEGER NOT NULL)')
        with db:
            asset_cursor=db.execute('SELECT row_id FROM asset_cursor WHERE id=1').fetchone()
            last_asset=asset_cursor[0] if asset_cursor else 0
            for asset in store.db.execute('SELECT rowid,id,asset_id,observed_at,currency,amount_micro,quality FROM asset_observation WHERE rowid>? ORDER BY rowid',(last_asset,)):
                last_asset=asset['rowid']
                if asset['quality']=='confirmed' and asset['asset_id'] in ('openrouter_credits','wallet_base_eth','wallet_base_usdc'):
                    db.execute('INSERT OR IGNORE INTO asset_history VALUES (?,?,?,?,?)',tuple(asset)[1:6])
            db.execute('INSERT OR REPLACE INTO asset_cursor VALUES (1,?)',(last_asset,))
            row = db.execute('SELECT event_id FROM cursor WHERE id=1').fetchone()
            cursor = row[0] if row else 0
            last = cursor
            for event in store.db.execute('SELECT id,kind,occurred_at FROM trajectory_event WHERE id>? ORDER BY id', (cursor,)):
                last = event['id']
                if event['kind'] in EVENTS:
                    db.execute('INSERT OR IGNORE INTO public_event(private_event_id,occurred_at,published_at,schema_version,kind,label) VALUES (?,?,?,?,?,?)',
                               (event['id'], event['occurred_at'], utcnow(), 1, event['kind'], EVENTS[event['kind']]))
            state = store.db.execute("SELECT * FROM runtime_state WHERE instance_id=?",(store.instance_id,)).fetchone()
            cp = store.db.execute("SELECT activity,config_ref FROM checkpoint WHERE instance_id=?",(store.instance_id,)).fetchone()
            instance=store.db.execute('SELECT * FROM instance WHERE id=?',(store.instance_id,)).fetchone()
            snapshot = {'schema_version': 1, 'mode': store.mode, 'born_at': instance['born_at'],
                        'status': 'not_born' if instance['born_at'] is None else state['state'], 'runtime_status': state['state'] if state['state'] in STATES else 'unknown',
                        'activity': cp['activity'] if cp['activity'] in ACTIVITIES else 'idle',
                        'since': state['since'], 'wake_at': state['wake_at'],
                        'last_success_at': state['last_success_at'], 'as_of': utcnow(),
                        'net_worth_eur_micro': None, 'quality': 'unknown', 'unreconciled': True,
                        'last_call_cost': None}
            level=store.archive.get(cp['config_ref']).get('autonomy_level','S0')
            snapshot['autonomy_level']=level if level in ('S0','S5.4') else 'unknown'
            poll=store.db.execute("SELECT occurred_at,payload_ref FROM trajectory_event WHERE kind='inbox_poll' ORDER BY id DESC LIMIT 1").fetchone()
            snapshot['mail_wake_poll']={'checked_at':poll['occurred_at'],'ok':bool(store.archive.get(poll['payload_ref']).get('ok'))} if poll else None
            db.execute('INSERT OR REPLACE INTO snapshot VALUES (1,?)', (json.dumps(snapshot),))
            db.execute('INSERT OR REPLACE INTO cursor VALUES (1,?)', (last,))
    finally:
        db.close()
    if os.name == 'posix':
        os.chmod(target / 'public.sqlite', 0o640)


def connect_readonly(path):
    uri = Path(path).resolve().as_uri() + '?mode=ro'
    db = sqlite3.connect(uri, uri=True, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')
    return db
