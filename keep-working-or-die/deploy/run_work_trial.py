"""Stage verified source and run one credential-isolated development trial."""
import hashlib
import io
import os
from pathlib import Path
import re
import stat
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import json

UNIT = 'kwod-work-trial-01.service'


def stop_trial():
    subprocess.run(['systemctl', 'stop', UNIT], capture_output=True, text=True, timeout=45)
    status = subprocess.run(['systemctl', 'show', UNIT, '--property=ActiveState', '--value'],
                            capture_output=True, text=True, timeout=15)
    state = status.stdout.strip() if getattr(status, 'returncode', 0) == 0 else 'unknown'
    if state not in ('inactive', 'failed'):
        load = subprocess.run(['systemctl', 'show', UNIT, '--property=LoadState', '--value'],
                              capture_output=True, text=True, timeout=15)
        if getattr(load, 'returncode', 0) != 0 or load.stdout.strip() != 'not-found':
            raise RuntimeError('trial_stop_not_confirmed')
    return 'stopped_or_not_running'


def status_trial():
    status = subprocess.run(['systemctl', 'show', UNIT, '--property=ActiveState', '--value'],
                            capture_output=True, text=True, timeout=15)
    value = status.stdout.strip()
    return value if status.returncode == 0 and value in (
        'active', 'inactive', 'failed', 'activating', 'deactivating') else 'unknown'


def inspect_saved(root, *, pilot=False):
    root = Path(root)
    result = {'work_trial': 'stopped_inspection', 'automatic_retry': False,
              'new_model_calls': 0, 'saved_attempts': None}
    database = root / 'data/private/state.sqlite'
    if database.exists():
        connection = None
        try:
            connection = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
            connection.row_factory = sqlite3.Row
            result['saved_attempts'] = [dict(row) for row in connection.execute(
                'SELECT status,error_code,started_at,ended_at FROM model_attempt ORDER BY rowid')]
            state = connection.execute('SELECT state,reason FROM runtime_state').fetchone()
            result['saved_runtime_state'] = dict(state) if state else None
            result['saved_tool_states'] = dict(connection.execute('SELECT status,count(*) FROM tool_call GROUP BY status'))
            result['saved_database_readable'] = True
        except sqlite3.Error:
            # A confirmed stop stays confirmed even when crash recovery is
            # needed to read the DB. The monitor handles that in a private copy.
            result['saved_database_readable'] = False
            result['inspection_required'] = True
        finally:
            if connection is not None:
                connection.close()
    names = (('works/entscheidung.md', 'works/arbeitsprobe.md', 'works/angebot.md', 'works/pruefung.md', 'memory.md')
             if pilot else ('works/entwurf.md', 'works/beschreibung.md', 'works/review.md', 'memory.md'))
    result['files_present'] = {name: (root / 'data/workspace' / name).is_file() for name in names}
    return result


def main():
    global UNIT
    if os.geteuid() != 0:
        raise ValueError('sudo_required')
    tail = sys.argv[3:]
    offline = '--monitor-check' in tail
    if offline:
        tail = tail.copy()
        tail.remove('--monitor-check')
    pilot = '--pilot' in tail
    if offline and pilot:
        raise ValueError('conflicting_profiles')
    if pilot:
        tail = tail.copy()
        tail.remove('--pilot')
    state_name = 'kwod-work-monitor-check' if offline else 'kwod-work-pilot-02' if pilot else 'kwod-work-trial-01'
    UNIT = state_name + '.service'
    if tail in (['--stop-inspect'], ['--status']):
        stopped = stop_trial() if tail == ['--stop-inspect'] else status_trial()
        saved = inspect_saved('/var/lib/' + state_name, pilot=True) if pilot else inspect_saved('/var/lib/' + state_name)
        if tail == ['--status']:
            saved['work_trial'] = 'status_inspection'
        print(json.dumps({**saved, 'service': stopped}))
        return
    source, digest = sys.argv[1:3]
    diagnosis = tail == ['--diagnose']
    resume_unstarted = tail == ['--resume-unstarted']
    check_provider = tail == ['--check-provider']
    resume_rejected = tail == ['--resume-rejected']
    if offline and tail:
        raise ValueError('offline_check_has_no_resume_or_provider_modes')
    if (tail and not (diagnosis or resume_unstarted or check_provider or resume_rejected)) or (pilot and (resume_unstarted or resume_rejected)):
        raise ValueError('invalid_arguments')
    if diagnosis:
        state = Path('/var/lib') / state_name
        db_path = state / 'data/private/state.sqlite'
        audit = {'saved_trial_marker': (state / 'trial-started').exists(),
                 'saved_database': db_path.exists(), 'attempt_status_counts': None}
        if db_path.exists():
            try:
                connection = sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True)
                try:
                    audit['attempt_status_counts'] = dict(connection.execute('SELECT status,count(*) FROM model_attempt GROUP BY status'))
                finally:
                    connection.close()
            except sqlite3.Error:
                audit['database_audit'] = 'unavailable'
        print(json.dumps(audit), flush=True)
    data = Path(source).read_bytes()
    if not re.fullmatch('[a-f0-9]{64}', digest) or len(data) > 5000000 or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('invalid_bundle')
    python = Path('/opt/kwod/current/.venv/bin/python')
    if not python.is_file():
        raise ValueError('installed_runtime_python_missing')
    key = Path('/etc/kwod-openrouter/api.key')
    for path in (() if offline else (key.parent, key)):
        info = path.lstat()
        expected = 0o700 if path == key.parent else 0o600
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != expected or path.is_symlink():
            raise ValueError('unsafe_credential_permissions')
    if not offline and (not stat.S_ISREG(key.stat().st_mode) or key.stat().st_nlink != 1):
        raise ValueError('unsafe_credential_file')
    with tempfile.TemporaryDirectory(prefix='kwod-work-trial-', dir='/run') as directory:
        root = Path(directory)
        root.chmod(0o755)
        with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
            total = 0
            for member in archive.getmembers():
                if not re.fullmatch(r'src/kwod/(?:[a-z_]+\.py|migrations/[0-9]+\.sql)', member.name):
                    continue
                total += member.size
                if not member.isfile() or total > 2000000:
                    raise ValueError('invalid_source_member')
                target = root / member.name
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
                target.write_bytes(archive.extractfile(member).read())
                target.chmod(0o644)
        entrypoint = 'kwod.work_monitor_fixture' if offline else 'kwod.work_trial'
        code = "import sys,runpy; sys.path.insert(0, " + repr(str(root / 'src')) + "); runpy.run_module(" + repr(entrypoint) + ",run_name='__main__')"
        args = ['systemd-run', '--unit=' + state_name, '--quiet', '--wait', '--collect', '--pipe']
        properties = ['DynamicUser=yes', 'StateDirectory=' + state_name, 'StateDirectoryMode=0700',
            'RuntimeMaxSec=900',
            'ProtectSystem=strict', 'ProtectHome=yes', 'PrivateTmp=yes', 'PrivateDevices=yes',
            'NoNewPrivileges=yes', 'CapabilityBoundingSet=', 'RestrictSUIDSGID=yes',
            'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6', 'LimitCORE=0', 'UMask=0077',
            'MemoryMax=512M', 'TasksMax=32', 'KillMode=control-group', 'TimeoutStopSec=15',
            'InaccessiblePaths=-/var/lib/kwod -/var/lib/kwod-signer -/run/kwod-signer -/run/docker.sock -/etc/kwod-openrouter',
            # systemd-run v255 recognizes aliases only as the entire value.
            # In a list every entry must be a numeric IP prefix.
            'IPAddressDeny=127.0.0.0/8 ::1/128 169.254.0.0/16 fe80::/10 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 fc00::/7',
            'IPAddressAllow=127.0.0.53/32']
        if offline:
            properties.append('PrivateNetwork=yes')
        else:
            properties.append('LoadCredential=openrouter:/etc/kwod-openrouter/api.key')
        for prop in properties:
            args.extend(['-p', prop])
        if diagnosis:
            args.extend(['-p', 'PrivateNetwork=yes', '--setenv=KWOD_TRIAL_DIAGNOSE=1'])
        if resume_unstarted:
            args.append('--setenv=KWOD_TRIAL_RESUME_UNSTARTED=1')
        if check_provider:
            args.append('--setenv=KWOD_TRIAL_CHECK_PROVIDER=1')
        if resume_rejected:
            args.append('--setenv=KWOD_TRIAL_RESUME_REJECTED=1')
        if pilot:
            args.append('--setenv=KWOD_TRIAL_PROFILE=earning')
        try:
            subprocess.run(args + [str(python), '-I', '-B', '-c', code], check=True)
        except KeyboardInterrupt:
            # Stop the actual service before temporary source files disappear.
            stop_trial()
            print(json.dumps({'work_trial': 'interrupted', 'service': 'stopped_or_not_running',
                              'automatic_retry': False, 'inspect_required': True}), flush=True)
            raise SystemExit(130) from None
    print('Private result: /var/lib/' + state_name + '/report.json')
    print('Work files: /var/lib/' + state_name + '/data/workspace/works/')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Trial stopped: ' + type(exc).__name__ + '. No automatic retry.', file=sys.stderr)
        sys.exit(1)
