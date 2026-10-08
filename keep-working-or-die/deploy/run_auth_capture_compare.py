"""Install isolated test dependencies without scripts; compare without network."""
import hashlib
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import tempfile
import zipfile


def main():
    if os.geteuid() != 0:
        raise RuntimeError('sudo required for systemd sandbox')
    source, digest = sys.argv[1:]
    data = Path(source).read_bytes()
    if not re.fullmatch('[0-9a-f]{64}', digest) or len(data) > 200000 or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Test bundle checksum mismatch')
    for path in ['/opt', '/opt/kwod-signer', '/opt/kwod-signer/venv', '/opt/kwod-wallet', '/opt/kwod-wallet/node']:
        info = Path(path).lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Untrusted dependency runtime')
    user = pwd.getpwnam('nobody')
    if user.pw_uid == 0:
        raise ValueError('Unsafe test user')
    with tempfile.TemporaryDirectory(prefix='kwod-client-test-', dir='/run') as directory:
        root = Path(directory)
        root.chmod(0o755)
        user_config = root / 'npm-user.conf'
        global_config = root / 'npm-global.conf'
        for config in (user_config, global_config):
            config.write_text('', encoding='utf-8')
            config.chmod(0o644)
        work = root / 'dependencies'
        work.mkdir(mode=0o700)
        os.chown(work, user.pw_uid, user.pw_gid)
        bundle = root / 'test.pyz'
        bundle.write_bytes(data)
        bundle.chmod(0o644)
        with zipfile.ZipFile(bundle) as archive:
            code = archive.read('compare.mjs')
        common = ['systemd-run', '--quiet', '--wait', '--collect', '--pipe',
                  '-p', 'User=' + str(user.pw_uid), '-p', 'Group=' + str(user.pw_gid),
                  '-p', 'NoNewPrivileges=yes', '-p', 'ProtectSystem=strict',
                  '-p', 'ProtectHome=yes', '-p', 'PrivateTmp=yes', '-p', 'UMask=0077',
                  '-p', 'CapabilityBoundingSet=', '-p', 'LimitCORE=0', '-p', 'RuntimeMaxSec=240',
                  '-p', 'InaccessiblePaths=-/var/lib/kwod-signer -/run/kwod-signer -/etc/kwod-openrouter -/var/lib/kwod-wallet -/var/lib/kwod/private',
                  '--setenv=HOME=' + str(work),
                  '--setenv=PATH=/opt/kwod-wallet/node/bin:/usr/bin:/bin']
        subprocess.run(common + ['-p', 'ReadWritePaths=' + str(work),
            '/opt/kwod-wallet/node/bin/npm', '--prefix', str(work), 'install',
            '--ignore-scripts', '--no-audit', '--no-fund', '--save-exact',
            '--userconfig=' + str(user_config), '--globalconfig=' + str(global_config),
            '--registry=https://registry.npmjs.org',
            'x402legacy@npm:@x402/evm@2.17.0', 'x402current@npm:@x402/evm@2.25.0',
            'viem@2.48.11'], check=True, timeout=300)
        (work / 'compare.mjs').write_bytes(code)
        (work / 'compare.mjs').chmod(0o644)
        subprocess.run(common + ['-p', 'PrivateNetwork=yes', '-p', 'RestrictAddressFamilies=AF_UNIX',
            '/opt/kwod-signer/venv/bin/python', '-I', str(bundle), str(work)], check=True, timeout=300)


if __name__ == '__main__':
    main()
