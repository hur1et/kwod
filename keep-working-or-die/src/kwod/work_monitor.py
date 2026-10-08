"""Allowlisted work-run metadata. Never opens model output, credentials or reports."""
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import tempfile
from datetime import datetime, timezone

from .store import atomic_write, utcnow

# Operator-defined registrations, never supplied by model text or HTTP requests.
RUNS = {
    'trial01': ('kwod-work-trial-01', 'Trial01 · Text und Review',
                ('works/entwurf.md', 'works/beschreibung.md', 'works/review.md', 'memory.md')),
    'pilot02': ('kwod-work-pilot-02', 'Pilot02 · Angebot und Arbeitsprobe',
                ('works/entscheidung.md', 'works/arbeitsprobe.md', 'works/angebot.md', 'works/pruefung.md', 'memory.md')),
    'offlinecheck': ('kwod-work-monitor-check', 'Offline-Prüflauf · keine Modellkosten',
                     ('works/entwurf.md', 'works/beschreibung.md', 'works/review.md', 'memory.md')),
}
LIMIT = 6
SERVICES = {'active', 'activating', 'deactivating', 'inactive', 'failed', 'not-found', 'unknown'}
PHASES = {'not_started', 'starting', 'model', 'tools', 'running', 'completed',
          'incomplete', 'budget_exhausted', 'stopped', 'needs_review', 'unavailable'}
STATES = {'not_born', 'ready', 'working', 'sleeping', 'idle', 'provider_unavailable',
          'recovery_required', 'maintenance', 'unknown'}


def regular_file(root, name):
    """Permit systemd's root StateDirectory alias, never links within the run."""
    path = root
    for part in Path(name).parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('linked_run_metadata')
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('invalid_run_metadata')
    return path, info


def read_counts(database):
    db = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=1)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        state = db.execute("SELECT state FROM runtime_state WHERE instance_id='dev'").fetchone()
        attempts = dict(db.execute('SELECT status,count(*) FROM model_attempt GROUP BY status'))
        tools = dict(db.execute('SELECT status,count(*) FROM tool_call GROUP BY status'))
        handoffs = db.execute("SELECT count(*) FROM trajectory_event WHERE kind='context_checkpoint'").fetchone()[0]
        return state, attempts, tools, handoffs
    finally:
        db.close()


def stopped_counts(root):
    # Abrupt termination can require WAL-index recovery or truncation that a
    # read-only original must not perform. Copy only the stopped DB and WAL;
    # rebuild transient SQLite bookkeeping privately, never in the run itself.
    with tempfile.TemporaryDirectory(prefix='kwod-monitor-read-') as temp:
        copied = Path(temp) / 'state.sqlite'
        for suffix in ('', '-wal'):
            try:
                source, info = regular_file(root, 'data/private/state.sqlite' + suffix)
            except FileNotFoundError:
                if suffix:
                    continue
                raise
            if info.st_size > 64 * 1024 * 1024:
                raise ValueError('metadata_size_limit')
            with source.open('rb') as stream:
                content = stream.read(64 * 1024 * 1024 + 1)
            if len(content) > 64 * 1024 * 1024:
                raise ValueError('metadata_size_limit')
            Path(str(copied) + suffix).write_bytes(content)
        # Rebuild SHM/checkpoint only in the temporary copy, before readonly use.
        db = sqlite3.connect(copied)
        try:
            db.execute('SELECT count(*) FROM sqlite_master').fetchone()
        finally:
            db.close()
        return read_counts(copied)


def observe(root, run_id, service='unknown'):
    """Read a consistent DB snapshot; no Store construction, retries or migrations."""
    _, label, names = RUNS[run_id]
    root = Path(root).resolve()
    service = service if service in SERVICES else 'unknown'
    result = {'id': run_id, 'label': label, 'phase': 'unavailable', 'service': service,
              'runtime_status': 'unknown', 'attempts': None, 'remaining': None,
              'max_calls': LIMIT, 'handoffs': None, 'restart_blocked': None,
              'files': [{'name': name, 'present': None} for name in names]}
    try:
        result['restart_blocked'] = (root / 'trial-started').exists()
        database = root / 'data/private/state.sqlite'
        if not database.exists():
            result['phase'] = ('starting' if service in {'active', 'activating'} else
                               'needs_review' if result['restart_blocked'] else
                               'not_started' if service in {'inactive', 'failed', 'not-found'} else 'unavailable')
            return result
        database, _ = regular_file(root, 'data/private/state.sqlite')
        try:
            state, attempts, tools, handoffs = read_counts(database)
        except sqlite3.Error:
            if service not in {'inactive', 'failed', 'not-found'}:
                raise
            state, attempts, tools, handoffs = stopped_counts(root)
        if state is None:
            result['phase'] = 'starting' if service in {'active', 'activating'} else 'needs_review'
            return result
        result.update(runtime_status=state[0] if state[0] in STATES else 'unknown',
                      attempts=sum(attempts.values()), handoffs=handoffs)
        result['remaining'] = max(0, LIMIT - result['attempts'])
        for item in result['files']:
            try:
                _, info = regular_file(root, 'data/workspace/' + item['name'])
                item['present'] = info.st_size > 0
            except FileNotFoundError:
                item['present'] = False
        active = service in {'active', 'activating', 'deactivating'}
        uncertain = (attempts.get('outcome_unknown', 0) or tools.get('outcome_unknown', 0)
                     or state[0] == 'recovery_required'
                     or (not active and (attempts.get('sent', 0) or tools.get('running', 0))))
        if uncertain:
            phase = 'needs_review'
        elif state[0] == 'idle' and handoffs and all(f['present'] for f in result['files']):
            phase = 'completed'
        elif service == 'unknown':
            phase = 'unavailable'
        elif state[0] in {'provider_unavailable', 'maintenance', 'idle'}:
            phase = 'incomplete'
        elif active:
            phase = ('model' if attempts.get('sent', 0) else 'tools' if
                     tools.get('planned', 0) or tools.get('running', 0) else 'running')
        elif result['remaining'] == 0:
            phase = 'budget_exhausted'
        else:
            phase = 'stopped'
        result['phase'] = phase
    except (OSError, sqlite3.Error, ValueError):
        result['phase'] = 'unavailable'
    return result


def service_state(unit):
    try:
        result = subprocess.run(['systemctl', 'show', unit, '--property=LoadState,ActiveState'],
                                capture_output=True, text=True, timeout=3, check=True)
        fields = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        if fields.get('LoadState') == 'not-found':
            return 'not-found'
        value = fields.get('ActiveState')
        return value if value in SERVICES else 'unknown'
    except (OSError, subprocess.SubprocessError):
        return 'unknown'


def collect(base=Path('/var/lib'), get_service=service_state):
    runs = []
    for run_id, (directory, _, _) in RUNS.items():
        unit = directory + '.service'
        before = get_service(unit)
        row = observe(Path(base) / directory, run_id, before)
        if get_service(unit) != before:
            row = observe(Path(base) / directory, run_id, 'unknown')
        runs.append(row)
    return {'schema_version': 1, 'as_of': utcnow(), 'runs': runs}


def public_snapshot(path):
    """Rebuild the API payload from typed fields, even if projection is tampered with."""
    try:
        with Path(path).open('rb') as stream:
            raw = stream.read(32769)
        if len(raw) > 32768:
            raise ValueError('oversize')
        data = json.loads(raw)
        stamp = datetime.fromisoformat(data['as_of'].replace('Z', '+00:00'))
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        result = {'schema_version': 1, 'as_of': stamp.isoformat(), 'stale': age > 30 or age < -5, 'runs': []}
        if data['schema_version'] != 1 or len(data['runs']) != len(RUNS):
            raise ValueError('schema')
        rows = {row['id']: row for row in data['runs']}
        for run_id, (_, label, names) in RUNS.items():
            row = rows[run_id]
            def count(key):
                value = row[key]
                if value is not None and (type(value) is not int or not 0 <= value <= 1000000):
                    raise ValueError('count')
                return value
            attempts = count('attempts')
            files = {f['name']: f['present'] for f in row['files']}
            if any(files[name] is not None and type(files[name]) is not bool for name in names):
                raise ValueError('files')
            result['runs'].append({'id': run_id, 'label': label,
                'phase': row['phase'] if row['phase'] in PHASES else 'unavailable',
                'service': row['service'] if row['service'] in SERVICES else 'unknown',
                'runtime_status': row['runtime_status'] if row['runtime_status'] in STATES else 'unknown',
                'attempts': attempts, 'max_calls': LIMIT,
                'remaining': max(0, LIMIT - attempts) if attempts is not None else None,
                'handoffs': count('handoffs'),
                'restart_blocked': row['restart_blocked'] if type(row['restart_blocked']) is bool else None,
                'files': [{'name': name, 'present': files[name]} for name in names]})
        return result
    except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
        return {'schema_version': 1, 'as_of': None, 'stale': True, 'runs': [], 'available': False}


def main():
    # Installed as a networkless collector. Its group is kwod-public; replacing
    # this one file never grants the HTTP service access to private run directories.
    if os.geteuid() != 0:
        raise ValueError('collector_requires_root')
    atomic_write(Path('/var/lib/kwod/public/work-runs.json'),
                 json.dumps(collect(), ensure_ascii=False).encode(), mode=0o640)


if __name__ == '__main__':
    main()
