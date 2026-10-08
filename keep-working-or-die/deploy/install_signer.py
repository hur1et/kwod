"""Install the local signer in observation mode; never enable spending."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import grp
import stat
import subprocess
import time


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def protected(path, uid=0, directory=False):
    info = path.lstat()
    if (info.st_uid != uid or info.st_mode & 0o022
            or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise ValueError('Unexpected installation path')


def write_root(path, data):
    if path.exists() or path.is_symlink():
        protected(path)
        if path.read_bytes() == data:
            return
    temp = path.with_name(path.name + '.new-' + os.urandom(8).hex())
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise ValueError('sudo required')
    os.umask(0o022)
    source = args.source.read_bytes()
    if hashlib.sha256(source).hexdigest() != args.sha256:
        raise ValueError('Source checksum mismatch')
    root, home = Path('/opt/kwod-signer'), Path('/var/lib/kwod-signer')
    signer = pwd.getpwnam('kwod-signer')
    runtime = pwd.getpwnam('kwod-runtime')
    for parent in (Path('/opt'), Path('/var'), Path('/var/lib'), Path('/etc'),
                   Path('/etc/systemd'), Path('/etc/systemd/system'), root):
        protected(parent, directory=True)
    protected(home, signer.pw_uid, directory=True)
    if stat.S_IMODE(home.stat().st_mode) != 0o700 or signer.pw_uid in (0, runtime.pw_uid):
        raise ValueError('Signer identity is not isolated')
    identity_path = home / 'identity.json'
    protected(identity_path, signer.pw_uid)
    if stat.S_IMODE(identity_path.stat().st_mode) != 0o600 or identity_path.stat().st_nlink != 1:
        raise ValueError('Unsafe key permissions')
    identity = json.loads(identity_path.read_bytes())
    settings = {'address': identity['address'], 'runtime_uid': runtime.pw_uid, 'signing_enabled': False}
    config = Path('/etc/kwod-signer.json')
    if config.exists() or config.is_symlink():
        protected(config)
        if json.loads(config.read_bytes()) != settings:
            raise ValueError('Existing configuration differs; refusing automatic replacement')
    python = root / 'venv/bin/python'
    protected(root / 'venv', directory=True)
    for directory, dirs, files in os.walk(root / 'venv', followlinks=False):
        for name in dirs + files:
            info = (Path(directory) / name).lstat()
            if info.st_uid != 0 or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022):
                raise ValueError('Signer environment is not root controlled')
    program = root / ('payments-' + args.sha256 + '.py')
    write_root(program, source)
    # Real cryptography, fixed public test key, temporary journal and no network.
    run('systemd-run', '--quiet', '--wait', '--collect', '--pipe',
        '-p', 'User=kwod-signer', '-p', 'PrivateNetwork=yes', '-p', 'NoNewPrivileges=yes',
        '-p', 'ProtectSystem=strict', '-p', 'ProtectHome=yes', '-p', 'PrivateTmp=yes',
        '-p', 'LimitCORE=0', '-p', 'UMask=0077', python, '-I', program, 'selftest')
    try:
        group = grp.getgrnam('kwod-payments')
    except KeyError:
        run('groupadd', '--system', 'kwod-payments')
        group = grp.getgrnam('kwod-payments')
    if group.gr_gid == 0 or set(group.gr_mem) - {'kwod-runtime'}:
        raise ValueError('Unexpected payment group members')
    run('usermod', '-aG', 'kwod-payments', 'kwod-runtime')
    write_root(config, (json.dumps(settings, indent=2) + '\n').encode())
    unit = f'''[Unit]
Description=KEEP WORKING OR DIE isolated wallet signer
After=local-fs.target
ConditionPathExists=!/etc/kwod-safety/STOP
ConditionPathExists=!/etc/kwod-safety/WATCHDOG_PAUSE

[Service]
Type=simple
User=kwod-signer
Group=kwod-payments
ExecStart={python} -I {program} serve
UMask=0077
RuntimeDirectory=kwod-signer
RuntimeDirectoryMode=0750
PrivateNetwork=yes
RestrictAddressFamilies=AF_UNIX
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths={home}
ReadOnlyPaths={identity_path}
InaccessiblePaths={home}/backup.json
NoNewPrivileges=yes
CapabilityBoundingSet=
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictSUIDSGID=yes
RestrictNamespaces=yes
LockPersonality=yes
LimitCORE=0
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
'''
    unit_path = Path('/etc/systemd/system/kwod-signer.service')
    write_root(unit_path, unit.encode())
    run('systemd-analyze', 'verify', unit_path)
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', 'kwod-signer.service')
    run('systemctl', 'restart', 'kwod-signer.service')
    for attempt in range(15):
        check = subprocess.run(['runuser', '-u', 'kwod-runtime', '--', str(python), '-I', str(program), 'status'], capture_output=True, text=True)
        if check.returncode == 0:
            print(check.stdout.strip())
            break
        time.sleep(1)
    else:
        raise ValueError('Signer health check failed; inspect kwod-signer journal')
    for name in ('kwod-runtime', 'kwod-public', 'kwod-wallet'):
        try:
            pwd.getpwnam(name)
        except KeyError:
            continue
        if subprocess.run(['runuser', '-u', name, '--', 'test', '-r', str(identity_path)]).returncode != 1:
            raise ValueError('Key is readable outside signer')
        if name != 'kwod-runtime':
            check = subprocess.run(['runuser', '-u', name, '--', str(python), '-I', str(program), 'status'], capture_output=True)
            if check.returncode == 0:
                raise ValueError('Unexpected wallet API access')
    # Socket owner can reach the socket but is not an authorized API caller:
    # this exercises SO_PEERCRED separately from directory/group permissions.
    denied = subprocess.run(['runuser', '-u', 'kwod-signer', '--', str(python), '-I', str(program), 'status'], capture_output=True)
    if denied.returncode == 0:
        raise ValueError('Peer-credential boundary failed')
    print('{"signer_installed":true,"isolation_checks":"passed","signing_enabled":false,"worker_started":false}')


if __name__ == '__main__':
    main()
