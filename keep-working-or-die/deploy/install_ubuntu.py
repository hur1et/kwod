"""Ubuntu development deployment. Installs public observer; never starts inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile


def run(*args, capture=False, **kwargs):
    result = subprocess.run([str(x) for x in args], check=True, text=True,
                            stdout=subprocess.PIPE if capture else None, **kwargs)
    return result.stdout.strip() if capture else None


def verify_source(source):
    manifest = json.loads((source / 'bundle-manifest.json').read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError('missing source manifest')
    for name, expected in manifest.items():
        path = source / name
        if Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name or ':' in name:
            raise ValueError('unsafe manifest path')
        if not path.resolve().is_relative_to(source) or path.is_symlink() or not path.is_file():
            raise ValueError('invalid source file')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('source hash mismatch: ' + name)
    return manifest


def preflight():
    release = platform.freedesktop_os_release() if sys.platform == 'linux' else {}
    result = {'os': release.get('ID'), 'version': release.get('VERSION_ID'),
              'architecture': platform.machine(), 'python': platform.python_version(),
              'systemd': Path('/run/systemd/system').exists(), 'docker': bool(shutil.which('docker')),
              'python_venv': Path('/usr/share/python3-wheels').exists()}
    result['supported'] = result['os'] == 'ubuntu' and sys.version_info >= (3, 12) and result['systemd']
    return result


def install(source, release, prerequisites):
    if not re.fullmatch(r'dev-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}', release):
        raise ValueError('invalid release ID')
    if os.geteuid() != 0:
        raise ValueError('installation requires sudo')
    check = preflight()
    if not check['supported']:
        raise ValueError('Ubuntu with systemd and Python >=3.12 required')
    for worker in ('kwod-runtime', 'kwod-production'):
        if subprocess.run(['systemctl', 'is-active', '--quiet', worker]).returncode == 0:
            raise ValueError('stop ' + worker + ' before installing; no automatic interruption or restart')
    manifest = verify_source(source)
    # A previously loaded root operator must not use old code after the release switch.
    subprocess.run(['systemctl', 'stop', 'kwod-operator.service'],capture_output=True)
    if prerequisites:
        run('apt-get', 'update')
        run('apt-get', 'install', '-y', 'python3-venv', 'docker.io')
    if not shutil.which('docker'):
        raise ValueError('Docker missing; rerun with --install-prerequisites')
    run('systemctl', 'start', 'docker')
    if run('docker', 'info', '--format', '{{.OSType}}', capture=True) != 'linux':
        raise ValueError('Linux Docker daemon required')
    import grp
    import pwd
    try:
        group = grp.getgrnam('kwod-workspace')
        if group.gr_gid != 65532:
            raise ValueError('kwod-workspace must have GID 65532')
    except KeyError:
        try:
            grp.getgrgid(65532)
        except KeyError:
            run('groupadd', '--gid', '65532', 'kwod-workspace')
        else:
            raise ValueError('GID 65532 already belongs to another group')
    for user, group in [('kwod-runtime', 'kwod-workspace'), ('kwod-public', 'kwod-public')]:
        try:
            account = pwd.getpwnam(user)
            if account.pw_gid != grp.getgrnam(group).gr_gid or account.pw_uid in (0, 65532):
                raise ValueError('existing account conflicts with isolated identities: ' + user)
        except KeyError:
            if user == 'kwod-public':
                run('useradd', '--system', '--user-group', '--no-create-home', '--shell', '/usr/sbin/nologin', user)
            else:
                run('useradd', '--system', '--gid', group, '--no-create-home', '--shell', '/usr/sbin/nologin', user)
    run('usermod', '-aG', 'docker,kwod-public', 'kwod-runtime')
    for path, group, mode in [('/var/lib/kwod', 'kwod-public', '0750'),
                               ('/var/lib/kwod/private', 'kwod-workspace', '0700'),
                               ('/var/lib/kwod/workspace', 'kwod-workspace', '2770'),
                               ('/var/lib/kwod/public', 'kwod-public', '2750')]:
        run('install', '-d', '-o', 'kwod-runtime', '-g', group, '-m', mode, path)
    run('install', '-d', '-o', 'root', '-g', 'root', '-m', '0700', '/etc/kwod')
    releases = Path('/opt/kwod/releases')
    releases.mkdir(parents=True, exist_ok=True)
    dest = releases / release
    dest.mkdir(mode=0o755)  # Existing releases are never overwritten.
    for name in manifest:
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
        target.chmod(0o644)
    shutil.copyfile(source / 'bundle-manifest.json', dest / 'bundle-manifest.json')
    verify_source(dest)
    run(sys.executable, '-m', 'venv', dest / '.venv')
    python = dest / '.venv/bin/python'
    kwod = dest / '.venv/bin/kwod'
    run(python, '-m', 'pip', 'install', '--no-cache-dir', '-r', dest / 'requirements-tested.txt')
    run(python, '-m', 'pip', 'install', '--no-cache-dir', '--no-build-isolation', '--no-deps', dest)
    run(python, '-m', 'pip', 'check')
    # The installed host watchdog must not govern temporary fixture runtimes.
    # Namespace isolation also covers CLI subprocesses, without a production bypass.
    run(python, dest / 'deploy/test_release_isolated.py', cwd=dest)
    image_tag = 'kwod-executor:' + release
    run('docker', 'build', '-f', dest / 'deploy/Executor.Dockerfile', '-t', image_tag, dest / 'deploy')
    image_id = run('docker', 'image', 'inspect', '--format', '{{.Id}}', image_tag, capture=True)
    if not re.fullmatch('sha256:[a-f0-9]{64}', image_id):
        raise ValueError('invalid executor image ID')
    # Run boundary tests under the actual runtime identity and shared workspace GID.
    run('runuser', '-u', 'kwod-runtime', '--', 'env', 'PYTHONDONTWRITEBYTECODE=1',
        'KWOD_RUN_LINUX_ISOLATION=1', 'KWOD_EXECUTOR_IMAGE=' + image_id,
        python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', dest / 'tests/test_linux_executor.py', cwd=dest)
    # Existing data needs a consistent backup before migration; a new instance needs no key.
    if Path('/var/lib/kwod/private/state.sqlite').exists():
        backup_path = '/var/lib/kwod-backups/' + release
        run('install', '-d', '-o', 'kwod-runtime', '-g', 'kwod-workspace', '-m', '0700', '/var/lib/kwod-backups')
        current_kwod = Path('/opt/kwod/current/.venv/bin/kwod')
        if not current_kwod.exists():
            raise ValueError('existing data without prior release; manual backup required')
        run('runuser', '-u', 'kwod-runtime', '--', current_kwod, '--data', '/var/lib/kwod', 'backup', backup_path)
    if Path('/var/lib/kwod-production/private/state.sqlite').exists():
        run('install', '-d', '-o', 'kwod-runtime', '-g', 'kwod-workspace', '-m', '0700', '/var/lib/kwod-production-backups')
        current_kwod = Path('/opt/kwod/current/.venv/bin/kwod')
        if not current_kwod.exists(): raise ValueError('production_data_without_prior_release')
        run('runuser', '-u', 'kwod-runtime', '--', current_kwod, '--mode', 'prod', '--data', '/var/lib/kwod-production', 'backup', '/var/lib/kwod-production-backups/' + release)
    run('runuser', '-u', 'kwod-runtime', '--', kwod, '--data', '/var/lib/kwod', 'init', '--executor-image', image_id)
    # Journal the deployed source without creating a model attempt.
    run('runuser', '-u', 'kwod-runtime', '--', python, dest / 'deploy/record_deployment.py', release, image_id)
    # Repair files created by earlier releases and verify access as the reader,
    # rather than letting root's successful reads hide permission errors.
    public_db = Path('/var/lib/kwod/public/public.sqlite')
    if public_db.is_symlink() or not public_db.is_file():
        raise ValueError('public database must be a regular file')
    run('chown', 'kwod-runtime:kwod-public', public_db)
    run('chmod', '0640', public_db)
    run('runuser', '-u', 'kwod-public', '--', python, '-c',
        'from kwod.projection import connect_readonly; '
        'db = connect_readonly("/var/lib/kwod/public/public.sqlite"); '
        'assert db.execute("SELECT payload FROM snapshot WHERE id=1").fetchone(); db.close()')
    current = Path('/opt/kwod/current')
    if current.exists() and not current.is_symlink():
        raise ValueError('current path must be a release symlink')
    pending = Path('/opt/kwod/current-' + release)
    pending.symlink_to(dest, target_is_directory=True)
    os.replace(pending, current)
    for unit in ('kwod-runtime.service', 'kwod-public.service', 'kwod-work-monitor.service', 'kwod-work-monitor.timer'):
        if unit == 'kwod-public.service' and Path('/var/lib/kwod-production/private/state.sqlite').exists():
            # Keep the installed production observer and its isolated projection.
            if not Path('/etc/systemd/system/kwod-public.service').exists():
                raise ValueError('production_observer_unit_missing')
            continue
        shutil.copyfile(dest / 'deploy' / unit, Path('/etc/systemd/system') / unit)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'start', 'kwod-work-monitor.service')
    run('runuser', '-u', 'kwod-public', '--', python, '-c',
        'from kwod.work_monitor import public_snapshot; '
        'assert len(public_snapshot("/var/lib/kwod/public/work-runs.json")["runs"]) == 3')
    run('systemctl', 'enable', '--now', 'kwod-work-monitor.timer')
    run('systemctl', 'enable', '--now', 'kwod-public')
    run('systemctl', 'restart', 'kwod-public')
    import urllib.request
    import time
    for attempt in range(20):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2) as response:
                if json.load(response)['ok']:
                    break
        except OSError:
            time.sleep(0.5)
    else:
        raise RuntimeError('public observer health check failed')
    print(json.dumps({'release': release, 'executor_image': image_id, 'public_observer': 'running',
                      'model_worker_started': False, 'production_birth': False}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--action', choices=('check', 'install'), default='check')
    parser.add_argument('--install-prerequisites', action='store_true')
    args = parser.parse_args()
    source = args.source.resolve()
    verify_source(source)
    if args.action == 'check':
        result = preflight()
        print(json.dumps(result, indent=2))
        sys.exit(0 if result['supported'] else 1)
    install(source, args.release, args.install_prerequisites)
