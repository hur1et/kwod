"""Run a hash-verified test zip in a transient networkless service; no installation."""
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


def main():
    if os.geteuid() != 0:
        raise RuntimeError('sudo required for systemd sandbox')
    source, digest = sys.argv[1:]
    if not re.fullmatch('[0-9a-f]{64}', digest):
        raise ValueError('Invalid checksum')
    data = Path(source).read_bytes()
    if len(data) > 200000 or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Test bundle checksum mismatch')
    for path in (Path('/opt'), Path('/opt/kwod-signer'), Path('/opt/kwod-signer/venv')):
        info = path.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Untrusted Python installation')
    with tempfile.TemporaryDirectory(prefix='kwod-crypto-test-', dir='/run') as directory:
        root = Path(directory)
        root.chmod(0o755)
        bundle = root / 'selftest.pyz'
        bundle.write_bytes(data)
        bundle.chmod(0o644)
        subprocess.run(['systemd-run', '--quiet', '--wait', '--collect', '--pipe',
            '-p', 'DynamicUser=yes', '-p', 'PrivateNetwork=yes',
            '-p', 'RestrictAddressFamilies=AF_UNIX', '-p', 'NoNewPrivileges=yes',
            '-p', 'ProtectSystem=strict', '-p', 'ProtectHome=yes', '-p', 'PrivateTmp=yes',
            '-p', 'InaccessiblePaths=-/var/lib/kwod-signer -/run/kwod-signer -/etc/kwod-openrouter',
            '-p', 'CapabilityBoundingSet=', '-p', 'LimitCORE=0', '-p', 'UMask=0077',
            '/opt/kwod-signer/venv/bin/python', '-I', str(bundle)], check=True)


if __name__ == '__main__':
    main()
