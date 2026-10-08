"""Provision a production key with a read-only GET /key; no inference endpoint."""
from decimal import Decimal, InvalidOperation
import getpass
import json
import os
from pathlib import Path
import re
import stat
import sys
import urllib.request
import urllib.error

KEY_DIR = Path('/etc/kwod-openrouter')


class CheckError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CheckError('redirect_refused')


def number(value):
    if value is None:
        return None
    if type(value) not in (str, int, float, Decimal):
        raise CheckError('invalid_numeric_metadata')
    try:
        result = Decimal(str(value))
    except InvalidOperation:
        raise CheckError('invalid_numeric_metadata') from None
    if not result.is_finite():
        raise CheckError('invalid_numeric_metadata')
    return str(result)


def summarize(response):
    data = response.get('data') if isinstance(response, dict) else None
    if not isinstance(data, dict):
        raise CheckError('invalid_metadata')
    if data.get('is_management_key') is not False or data.get('is_provisioning_key', False) is not False:
        raise CheckError('normal_inference_key_required')
    return {'openrouter_key': 'verified', 'management_key': False,
            'key_usage_usd': number(data.get('usage')),
            'key_limit_usd': number(data.get('limit')),
            'key_limit_remaining_usd': number(data.get('limit_remaining')),
            'account_credit_balance_usd': None,
            'account_credit_balance_status': 'not_available_with_normal_key',
            'inference_tested': False, 'worker_started': False}


def query(key):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request('https://openrouter.ai/api/v1/key',
                                     headers={'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}, method='GET')
    with opener.open(request, timeout=30) as response:
        body = response.read(65537)
        if len(body) > 65536:
            raise CheckError('response_too_large')
        return summarize(json.loads(body, parse_float=Decimal))


def check_key(key):
    if not isinstance(key, str) or not re.fullmatch(r'sk-or-v1-[A-Za-z0-9_-]{20,512}', key):
        raise CheckError('invalid_key_format')
    return key


def main():
    import resource
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    os.umask(0o077)
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise CheckError('sudo_and_interactive_terminal_required')
    parent = KEY_DIR.parent.lstat()
    if not stat.S_ISDIR(parent.st_mode) or parent.st_uid != 0 or parent.st_mode & 0o022:
        raise CheckError('unsafe_parent')
    KEY_DIR.mkdir(mode=0o700, exist_ok=True)
    info = KEY_DIR.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o700:
        raise CheckError('unsafe_key_directory')
    path = KEY_DIR / 'api.key'
    exists = path.exists() or path.is_symlink()
    if exists:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'r') as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600:
                raise CheckError('unsafe_key_file')
            key = check_key(stream.read(1024))
    else:
        key = check_key(getpass.getpass('OpenRouter API-Key (verdeckte Eingabe): ').strip())
    result = query(key)
    if not exists:
        # Never replace an existing key, even if another invocation raced us.
        import tempfile
        fd, temporary = tempfile.mkstemp(prefix='.key-', dir=KEY_DIR)
        try:
            with os.fdopen(fd, 'w') as stream:
                stream.write(key)
                stream.flush()
                os.fsync(stream.fileno())
            os.link(temporary, path)
        finally:
            os.unlink(temporary)
        fd = os.open(KEY_DIR, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    print(json.dumps(dict(result, key_stored=True), indent=2))


if __name__ == '__main__':
    try:
        main()
    except CheckError as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as error:
        print(json.dumps({'ok': False, 'http_status': error.code}), file=sys.stderr)
        sys.exit(1)
    except (Exception, KeyboardInterrupt):
        print('{"ok":false,"error":"key_check_failed"}', file=sys.stderr)
        sys.exit(1)
