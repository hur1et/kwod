"""Provision a separate Node 24 runtime; no wallet login, keys or payments."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tarfile
import tempfile
import urllib.request


def select_release(rows):
    candidates = [r['version'] for r in rows
                  if re.fullmatch(r'v24\.\d+\.\d+', r.get('version', '')) and r.get('lts')]
    if not candidates:
        raise ValueError('No Node 24 LTS release found')
    return max(candidates, key=lambda v: tuple(map(int, v[1:].split('.'))))


def expected_hash(manifest, filename):
    matches = [parts[0] for line in manifest.splitlines()
               if len(parts := line.split()) == 2 and parts[1] == filename]
    if len(matches) != 1 or not re.fullmatch(r'[a-f0-9]{64}', matches[0]):
        raise ValueError('Missing or ambiguous official checksum')
    return matches[0]


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def main():
    import grp
    import pwd
    if os.geteuid() != 0:
        raise ValueError('Run this installer using sudo')
    if platform.freedesktop_os_release().get('ID') != 'ubuntu' or platform.machine() != 'x86_64':
        raise ValueError('This installer targets Ubuntu x86_64 only')
    os.umask(0o022)
    root = Path('/opt/kwod-wallet')
    home = Path('/var/lib/kwod-wallet')
    node_dir = root / 'node'
    for path in (root, home, node_dir):
        if path.is_symlink():
            raise ValueError('Refusing linked installation path: ' + str(path))
    if root.exists() and (root.stat().st_uid != 0 or root.stat().st_mode & 0o022):
        raise ValueError('Wallet installation directory must be root-owned and not group/world writable')
    root.mkdir(mode=0o755, exist_ok=True)
    if not node_dir.exists():
        version = select_release(json.loads(fetch('https://nodejs.org/dist/index.json')))
        filename = f'node-{version}-linux-x64.tar.xz'
        base_url = f'https://nodejs.org/dist/{version}/'
        digest = expected_hash(fetch(base_url + 'SHASUMS256.txt').decode(), filename)
        print('Downloading official Node release:', version, flush=True)
        with tempfile.TemporaryDirectory(prefix='node-install-', dir=root) as temp:
            temp = Path(temp)
            archive = temp / filename
            archive.write_bytes(fetch(base_url + filename))
            if hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
                raise ValueError('Node archive checksum mismatch')
            with tarfile.open(archive) as bundle:
                for member in bundle.getmembers():
                    if member.name.split('/')[0] != f'node-{version}-linux-x64':
                        raise ValueError('Unexpected Node archive layout')
                bundle.extractall(temp, filter='data')
            (temp / f'node-{version}-linux-x64').rename(node_dir)
        (root / 'node-install.json').write_text(json.dumps(
            {'version': version, 'url': base_url + filename, 'sha256': digest}, indent=2))
    version = subprocess.check_output([str(node_dir / 'bin/node'), '--version'], text=True).strip()
    if not re.fullmatch(r'v24\.\d+\.\d+', version):
        raise ValueError('Existing wallet Node is not version 24; no automatic replacement')
    try:
        account = pwd.getpwnam('kwod-wallet')
    except KeyError:
        if home.exists():
            raise ValueError('Existing wallet home without account; manual inspection required')
        run('useradd', '--system', '--user-group', '--create-home', '--home-dir', home,
            '--shell', '/usr/sbin/nologin', 'kwod-wallet')
        account = pwd.getpwnam('kwod-wallet')
    group = grp.getgrnam('kwod-wallet')
    if (account.pw_uid in (0, 65532) or account.pw_gid != group.gr_gid
            or account.pw_dir != str(home)
            or account.pw_shell != '/usr/sbin/nologin'
            or set(os.getgrouplist('kwod-wallet', account.pw_gid)) != {group.gr_gid}):
        raise ValueError('Existing wallet account conflicts with isolated setup')
    run('install', '-d', '-o', 'kwod-wallet', '-g', 'kwod-wallet', '-m', '0700', home)
    run('runuser', '-u', 'kwod-wallet', '--', node_dir / 'bin/node', '--version')
    run('runuser', '-u', 'kwod-wallet', '--', node_dir / 'bin/node',
        node_dir / 'lib/node_modules/npm/bin/npm-cli.js', '--version')
    print(json.dumps({'wallet_runtime': 'ready', 'node': version, 'home_mode': '0700',
                      'wallet_created': False, 'payments_sent': False, 'worker_started': False}))


if __name__ == '__main__':
    main()
