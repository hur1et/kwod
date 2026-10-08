"""Provision and verify one dedicated GMX mailbox without sending mail."""
from __future__ import annotations

import getpass
import grp
import imaplib
import json
import os
from pathlib import Path
import smtplib
import stat
import sys


MAIL_DIR = Path('/etc/kwod-mail')
MAIL_FILE = MAIL_DIR / 'credentials.json'
ADDRESS = 'agent.kwod@gmx.de'


def safe_dir():
    MAIL_DIR.parent.mkdir(mode=0o755, exist_ok=True)
    MAIL_DIR.mkdir(mode=0o750, exist_ok=True)
    runtime_group = grp.getgrnam('kwod-workspace').gr_gid
    os.chown(MAIL_DIR, 0, runtime_group)
    os.chmod(MAIL_DIR, 0o750)
    info = MAIL_DIR.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o750:
        raise ValueError('unsafe_mail_directory')


def main():
    if os.geteuid() != 0 or not sys.stdin.isatty():
        raise ValueError('sudo_and_interactive_terminal_required')
    safe_dir()
    password = getpass.getpass('GMX-Passwort oder App-Passwort (verdeckte Eingabe): ').strip()
    if not password:
        raise ValueError('empty_mail_password')
    runtime_group = grp.getgrnam('kwod-workspace').gr_gid
    with imaplib.IMAP4_SSL('imap.gmx.net', 993, timeout=30) as imap:
        imap.login(ADDRESS, password)
        imap.logout()
    with smtplib.SMTP_SSL('mail.gmx.net', 465, timeout=30) as smtp:
        smtp.login(ADDRESS, password)
    payload = {'address': ADDRESS, 'imap_host': 'imap.gmx.net', 'imap_port': 993,
               'smtp_host': 'mail.gmx.net', 'smtp_port': 465,
               'username': ADDRESS, 'password': password}
    temporary = MAIL_DIR / '.credentials.tmp'
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(payload, stream)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(temporary, 0o600)
    os.chown(temporary, 0, runtime_group)
    os.chmod(temporary, 0o640)
    os.replace(temporary, MAIL_FILE)
    os.chown(MAIL_FILE, 0, runtime_group)
    os.chmod(MAIL_FILE, 0o640)
    print(json.dumps({'mailbox': ADDRESS, 'imap': 'verified', 'smtp_auth': 'verified',
                      'message_sent': False, 'credentials_stored': True}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"ok":false,"error":"mailbox_check_failed"}', file=sys.stderr)
        sys.exit(1)
