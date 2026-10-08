"""Offline wallet initialization and encrypted export; no payment or agent service."""
import getpass
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

ROOT = Path('/opt/kwod-signer')
HOME = Path('/var/lib/kwod-signer')
PACKAGE = 'eth-account==0.14.0'


def secure_read(path, uid=None):
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    if path.is_symlink():
        raise ValueError('Linked file refused')
    fd = os.open(path, flags)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Regular file with one link required')
        if os.name == 'posix' and (info.st_uid != uid or stat.S_IMODE(info.st_mode) != 0o600):
            raise ValueError('Secret file ownership or permissions incorrect')
        data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError('Unexpected wallet file size')
        return data


def create_once(path, data):
    """Publish fully written data without replacing any existing identity."""
    fd, temp = tempfile.mkstemp(prefix='.wallet-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        os.unlink(temp)
    if os.name == 'posix':
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def check_directory(path, uid, mode):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or stat.S_IMODE(info.st_mode) != mode:
        raise ValueError('Unexpected directory ownership/permissions: ' + str(path))


def crypto_selftest():
    from eth_account import Account
    # Public test vector, never funded or saved as an operational wallet.
    key = bytes.fromhex('00' * 31 + '01')
    account = Account.from_key(key)
    assert account.address == '0x7E5F4552091A69125d5DfCb7b8C2659029395Bdf'
    encrypted = Account.encrypt(key, 'public-selftest-password', kdf='scrypt')
    assert bytes(Account.decrypt(encrypted, 'public-selftest-password')) == key
    try:
        Account.decrypt(encrypted, 'wrong-password')
    except ValueError:
        pass
    else:
        raise ValueError('Incorrect backup password was accepted')


def initialize(home=HOME):
    from eth_account import Account
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    check_directory(home, os.getuid(), 0o700)
    if not sys.stdin.isatty():
        raise ValueError('Interactive terminal required for backup password')
    crypto_selftest()
    identity = home / 'identity.json'
    backup = home / 'backup.json'
    if identity.exists() or identity.is_symlink():
        record = json.loads(secure_read(identity, os.getuid()))
        if set(record) != {'version', 'address', 'private_key'} or record['version'] != 1:
            raise ValueError('Invalid existing wallet; not replaced')
        account = Account.from_key(record['private_key'])
        if account.address != record['address']:
            raise ValueError('Wallet address does not match key')
    else:
        if backup.exists() or backup.is_symlink():
            raise ValueError('Backup exists without identity; recovery required')
        account = None
    existing_backup = backup.exists() or backup.is_symlink()
    password = getpass.getpass('Backup-Passwort (mindestens 16 Zeichen): ')
    if not existing_backup:
        if len(password) < 16 or password != getpass.getpass('Backup-Passwort wiederholen: '):
            raise ValueError('Passwords differ or password is too short; no new wallet created')
    if account is None:
        account = Account.create()
        record = {'version': 1, 'address': account.address, 'private_key': account.key.hex()}
        create_once(identity, json.dumps(record).encode())
    if existing_backup:
        encrypted = json.loads(secure_read(backup, os.getuid()))
    else:
        encrypted = Account.encrypt(account.key, password, kdf='scrypt')
        if bytes(Account.decrypt(encrypted, password)) != bytes(account.key):
            raise ValueError('Backup roundtrip failed')
        create_once(backup, json.dumps(encrypted, indent=2).encode())
    # Verify the bytes actually persisted, not only the in-memory result.
    saved = secure_read(backup, os.getuid())
    if bytes(Account.decrypt(json.loads(saved), password)) != bytes(account.key):
        raise ValueError('Backup belongs to a different wallet')
    print(json.dumps({'wallet': 'ready', 'address': account.address,
                      'backup_verified': True, 'backup_sha256': hashlib.sha256(saved).hexdigest(),
                      'payments_enabled': False, 'worker_started': False}), flush=True)


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def provision():
    import pwd
    import platform
    if os.geteuid() != 0 or os.environ.get('SUDO_UID', '0') == '0':
        raise ValueError('Start through sudo from the SSH administrator account')
    if not sys.stdin.isatty():
        raise ValueError('Use ssh -t for this installer')
    release = platform.freedesktop_os_release()
    if release.get('ID') != 'ubuntu' or release.get('VERSION_ID') != '24.04':
        raise ValueError('Ubuntu 24.04 required')
    admin = pwd.getpwuid(int(os.environ['SUDO_UID']))
    os.umask(0o022)
    for parent in (Path('/opt'), Path('/var'), Path('/var/lib')):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError('Unsafe parent directory')
    if not ROOT.exists():
        ROOT.mkdir(mode=0o755)
    check_directory(ROOT, 0, 0o755)
    try:
        account = pwd.getpwnam('kwod-signer')
    except KeyError:
        if HOME.exists() or HOME.is_symlink():
            raise ValueError('Existing signer data without account')
        run('useradd', '--system', '--user-group', '--create-home', '--home-dir', HOME,
            '--shell', '/usr/sbin/nologin', 'kwod-signer')
        account = pwd.getpwnam('kwod-signer')
        os.chmod(HOME, 0o700)
    if (account.pw_uid in (0, 65532, admin.pw_uid) or account.pw_dir != str(HOME)
            or account.pw_shell != '/usr/sbin/nologin'
            or set(os.getgrouplist('kwod-signer', account.pw_gid)) != {account.pw_gid}):
        raise ValueError('Conflicting signer account')
    check_directory(HOME, account.pw_uid, 0o700)
    # Content-addressed, root-owned code is not loaded from the SSH user's directory.
    source = Path(__file__).read_bytes()
    script = ROOT / ('setup-' + hashlib.sha256(source).hexdigest() + '.py')
    if not script.exists():
        create_once(script, source)
        os.chmod(script, 0o644)
    if script.is_symlink() or script.stat().st_uid != 0 or script.stat().st_mode & 0o022 or script.read_bytes() != source:
        raise ValueError('Unexpected installed helper')
    venv = ROOT / 'venv'
    if not venv.exists():
        run('/usr/bin/python3', '-m', 'venv', venv)
    check_directory(venv, 0, 0o755)
    # Refuse modified environments, including user-owned code files. Interpreter
    # symlinks made by venv are allowed; the enclosing directories are protected.
    for directory, dirs, files in os.walk(venv, followlinks=False):
        for name in dirs + files:
            info = (Path(directory) / name).lstat()
            if info.st_uid != 0 or (not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022):
                raise ValueError('Signer environment is not root controlled')
    python = venv / 'bin/python'
    run(python, '-I', '-m', 'pip', '--isolated', 'install', '--index-url', 'https://pypi.org/simple',
        '--only-binary=:all:', '--disable-pip-version-check', PACKAGE)
    run(python, '-I', '-m', 'pip', '--isolated', 'check')
    # Disable IP networking during generation and backup verification. A private
    # TTY keeps password entry out of shell history, argv and service logs.
    run('systemd-run', '--quiet', '--wait', '--collect', '--pty',
        '-p', 'User=kwod-signer', '-p', 'Group=' + str(account.pw_gid),
        '-p', 'PrivateNetwork=yes', '-p', 'NoNewPrivileges=yes',
        '-p', 'ProtectSystem=strict', '-p', 'ProtectHome=yes', '-p', 'PrivateTmp=yes',
        '-p', 'ReadWritePaths=' + str(HOME), '-p', 'LimitCORE=0', '-p', 'UMask=0077',
        python, '-I', script, '--initialize')
    for name in ('kwod-runtime', 'kwod-public', 'kwod-wallet'):
        try:
            pwd.getpwnam(name)
        except KeyError:
            continue
        result = subprocess.run(['runuser', '-u', name, '--', 'test', '-r', str(HOME / 'identity.json')])
        if result.returncode != 1:
            raise ValueError('Key isolation check failed: ' + name)
    export_root = Path('/var/lib/kwod-wallet-export')
    export_root.mkdir(mode=0o755, exist_ok=True)
    check_directory(export_root, 0, 0o755)
    export_dir = export_root / str(admin.pw_uid)
    export_dir.mkdir(mode=0o755, exist_ok=True)
    check_directory(export_dir, 0, 0o755)
    export = export_dir / 'backup.json'
    data = secure_read(HOME / 'backup.json', account.pw_uid)
    if export.exists() or export.is_symlink():
        if secure_read(export, admin.pw_uid) != data:
            raise ValueError('Existing export differs; not overwritten')
    else:
        create_once(export, data)
        os.chown(export, admin.pw_uid, admin.pw_gid)
    print('Verschluesselte Sicherung bereit:', export, flush=True)
    print('SHA256:', hashlib.sha256(data).hexdigest(), flush=True)


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['--initialize']:
            initialize()
        elif not sys.argv[1:]:
            provision()
        else:
            raise ValueError('Unknown arguments')
    except (Exception, KeyboardInterrupt) as error:
        # Third-party exceptions may contain input data; never print them.
        print('Wallet-Einrichtung abgebrochen (' + type(error).__name__ +
              '). Vorhandene Schluessel bleiben erhalten. Keine Zahlung gestartet.', file=sys.stderr)
        sys.exit(1)
