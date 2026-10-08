"""Read-only pre-birth checks; never reads wallet balances or performs payment."""
from __future__ import annotations

import json
from pathlib import Path
import os
import sqlite3
import stat
import urllib.request


def owned_mode(path, mode):
    info = path.stat()
    return info.st_uid == 0 and stat.S_IMODE(info.st_mode) == mode


def main():
    key = Path('/etc/kwod-openrouter/api.key')
    mail = Path('/etc/kwod-mail/credentials.json')
    db_path = Path('/var/lib/kwod/private/state.sqlite')
    result = {'model': 'gpt-6-astra', 'birth': False, 'worker_started': False,
              'mail_send': False, 'wallet_read': False, 'wallet_sign': False,
              'wallet_broadcast': False}
    result['openrouter_key_protected'] = key.is_file() and owned_mode(key, 0o600)
    result['mail_credentials_protected'] = mail.is_file() and owned_mode(mail, 0o640)
    result['database_present'] = db_path.is_file()
    if db_path.is_file():
        db = sqlite3.connect(db_path)
        try:
            row = db.execute("SELECT mode,born_at FROM instance WHERE id='dev'").fetchone()
            result['birth_absent'] = row is not None and row == ('dev', None) and db.execute("SELECT count(*) FROM trajectory_event WHERE kind='birth'").fetchone()[0] == 0
        finally:
            db.close()
    else:
        result['birth_absent'] = False
    if result['openrouter_key_protected']:
        token = key.read_text(encoding='utf-8').strip()
        req = urllib.request.Request('https://openrouter.ai/api/v1/key', headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.load(response)
            data = payload.get('data', {}) if isinstance(payload, dict) else {}
            result['openrouter_key_metadata'] = data.get('is_management_key') is False and data.get('is_provisioning_key', False) is False
        except Exception:
            result['openrouter_key_metadata'] = False
    else:
        result['openrouter_key_metadata'] = False
    result['all_nonfinancial_checks_pass'] = all(result[name] for name in (
        'openrouter_key_protected', 'mail_credentials_protected', 'database_present',
        'birth_absent', 'openrouter_key_metadata'))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
