"""Host-side GMX mailbox gateway.

The runtime may use this boundary once a supervised host service is enabled.
Credentials are read locally and are never returned to the agent.
"""
from __future__ import annotations

import email
from email import policy
from email.parser import BytesParser
import imaplib
import json
from pathlib import Path
import smtplib
import os
import stat
from .mail_delivery import MailDelivery
from .safety import stopped
from email.utils import getaddresses

OPERATOR_ADDRESS = 'julius.weiske@gmx.de'


def operator_sender(value):
    addresses = getaddresses([value or ''])
    return len(addresses) == 1 and addresses[0][1].casefold() == OPERATOR_ADDRESS


class MailboxGateway:
    def __init__(self, credentials=Path('/etc/kwod-mail/credentials.json'), *, delivery=None):
        self.credentials = Path(credentials)
        self.delivery = delivery or MailDelivery()

    def _config(self):
        if stopped(): raise ValueError('operator_safety_stop')
        if os.name=='posix':
            info=self.credentials.lstat()
            parent=self.credentials.parent.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or info.st_gid!=65532
                or stat.S_IMODE(info.st_mode)!=0o640 or not stat.S_ISDIR(parent.st_mode)
                or parent.st_uid!=0 or parent.st_mode & 0o022):
                raise ValueError('unsafe_mail_credentials')
        data = json.loads(self.credentials.read_text(encoding='utf-8'))
        required = {'address', 'username', 'password', 'imap_host', 'imap_port', 'smtp_host', 'smtp_port'}
        if set(data) != required:
            raise ValueError('invalid_mailbox_configuration')
        if data['imap_host']!='imap.gmx.net' or data['smtp_host']!='mail.gmx.net' or data['imap_port']!=993 or data['smtp_port']!=465:
            raise ValueError('mail_provider_not_allowed')
        return data

    def list_unread(self, limit=20, *, operator_only=False):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid_mail_limit')
        c = self._config()
        with imaplib.IMAP4_SSL(c['imap_host'], c['imap_port'], timeout=30) as imap:
            imap.login(c['username'], c['password'])
            status, data = imap.select('INBOX', readonly=True)
            if status != 'OK':
                raise RuntimeError('mailbox_select_failed')
            validity = imap.response('UIDVALIDITY')[1]
            validity = validity[0].decode() if validity and validity[0] else None
            if operator_only and (not validity or not validity.isdigit()):
                raise RuntimeError('mailbox_uidvalidity_missing')
            # A webmail client may already have marked an operator message read.
            # Durable UID deduplication, not the mutable Seen flag, decides wakeups.
            criteria = ('ALL', 'FROM', '"'+OPERATOR_ADDRESS+'"') if operator_only else ('UNSEEN',)
            status, rows = imap.uid('search', None, *criteria)
            if status != 'OK':
                raise RuntimeError('mailbox_search_failed')
            uids = rows[0].split()[-limit:]
            result = []
            for uid in uids:
                status, fetched = imap.uid('fetch', uid, '(BODY.PEEK[HEADER])')
                if status != 'OK':
                    continue
                raw = next((part[1] for part in fetched if isinstance(part, tuple)), b'')
                msg = BytesParser(policy=policy.default).parsebytes(raw)
                if operator_only and not operator_sender(msg.get('From')):
                    continue
                result.append({'uid': uid.decode(), 'message_id': msg.get('Message-ID'),
                               'from': msg.get('From'), 'subject': msg.get('Subject'), 'date': msg.get('Date'),
                               'uidvalidity': validity})
            return result

    def read(self, uid: str):
        if not isinstance(uid, str) or not uid.isdigit():
            raise ValueError('invalid_mail_uid')
        c = self._config()
        with imaplib.IMAP4_SSL(c['imap_host'], c['imap_port'], timeout=30) as imap:
            imap.login(c['username'], c['password'])
            if imap.select('INBOX', readonly=True)[0] != 'OK':
                raise RuntimeError('mailbox_select_failed')
            status, size_rows = imap.uid('fetch', uid, '(RFC822.SIZE)')
            import re
            sizes = re.findall(rb'RFC822.SIZE\s+(\d+)', b' '.join(p for p in size_rows if isinstance(p,bytes)))
            if status!='OK' or len(sizes)!=1 or int(sizes[0])>1_048_576:
                raise ValueError('mail_read_size_boundary')
            status, fetched = imap.uid('fetch', uid, '(BODY.PEEK[])')
            if status != 'OK':
                raise RuntimeError('mail_read_failed')
            raw = next((part[1] for part in fetched if isinstance(part, tuple)), b'')
            if len(raw)>1_048_576: raise ValueError('mail_read_size_boundary')
            msg = BytesParser(policy=policy.default).parsebytes(raw)
            return {'uid': uid, 'message_id': msg.get('Message-ID'), 'from': msg.get('From'),
                    'to': msg.get('To'), 'subject': msg.get('Subject'),
                    'text': msg.get_body(preferencelist=('plain',)).get_content() if msg.get_body(preferencelist=('plain',)) else ''}

    def send(self, raw: bytes):
        c = self._config()
        def transport(sender,recipient,outgoing):
            if stopped(): raise ValueError('operator_safety_stop')
            with smtplib.SMTP_SSL(c['smtp_host'],c['smtp_port'],timeout=30) as smtp:
                smtp.login(c['username'],c['password'])
                refused=smtp.sendmail(sender,[recipient],outgoing)
                if refused: raise RuntimeError('smtp_recipient_refused')
            msg=email.message_from_bytes(outgoing,policy=policy.default)
            return {'message_id':str(msg['Message-ID']),'recipients':[recipient]}
        return self.delivery.deliver(raw,c['address'],transport)
