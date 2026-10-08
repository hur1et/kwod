"""Real elapsed-time offline soak with repeated Store reopen and final restore.

Use a fresh, private data directory. This is not simulated production economics.
"""
import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

from kwod.backup import backup, restore
from kwod.config import Config
from kwod.provider import FixtureProvider
from kwod.runtime import initialize, Runtime
from kwod.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=60)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.data.exists() or args.seconds <= 0:
        parser.error('positive duration and new data directory required')
    store = Store(args.data)
    initialize(store, 'OFFLINE SOAK FIXTURE. Save a marker and sleep.', Config(idle_seconds=1))
    store.close()
    started = time.monotonic()
    ticks = 0
    while time.monotonic() - started < args.seconds:
        store = Store(args.data)
        try:
            count = store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0]
            calls = []
            if count % 2 == 0:
                for i, (name, params) in enumerate([
                    ('write_file', {'path': 'memory.md', 'content': f'OFFLINE fixture attempt {count}'}),
                    ('sleep', {'wake_at': (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat()})]):
                    calls.append({'type': 'function_call', 'call_id': f'fixture-{count}-{i}',
                                  'name': name, 'arguments': json.dumps(params)})
            value = {'id': f'soak-{count}', 'model': 'gpt-6-astra', 'status': 'completed', 'output': calls, 'usage': None}
            state = Runtime(store, FixtureProvider([value])).tick()
            if state not in ('ready', 'working', 'sleeping', 'idle'):
                raise RuntimeError(f'unexpected soak state: {state}')
            ticks += 1
        finally:
            store.close()
        time.sleep(0.1)
    store = Store(args.data)
    try:
        root = args.data.resolve()
        target = backup(store, root.with_name(root.name + '-backup'))
        restored = restore(target, root.with_name(root.name + '-restored'))
        count = store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0]
        events = store.db.execute('SELECT count(*) FROM trajectory_event').fetchone()[0]
        assert store.db.execute('SELECT born_at FROM instance').fetchone()[0] is None
    finally:
        store.close()
    check = Store(restored)
    try:
        assert check.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0] == count
        for path in check.archive.path.iterdir():
            if len(path.name) == 64:
                check.archive.verify(path.name)
    finally:
        check.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {'mode': 'offline_fixture', 'elapsed_seconds': round(time.monotonic() - started, 2),
              'requested_seconds': args.seconds, 'ticks_with_store_reopen': ticks,
              'model_fixture_attempts': count, 'private_events': events,
              'backup_restore_verified': True, 'production_birth': False, 'real_api_calls': 0}
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
