"""Durable one-recipient mail boundary. No blind SMTP or gate retry."""
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
from .mail_channel import AI_SIGNATURE, build_outbound, MAX_MESSAGE_BYTES, external_name
from .safety import SocketReviewer, stopped

class MailDelivery:
    def __init__(self,path=None,*,reviewer=None,clock=None):
        if path is None:
            pointer=Path('/etc/kwod-production/mail-ledger.path')
            if pointer.exists():
                path=pointer.read_text().strip()
                if path!='/var/lib/kwod-production/private/mail-outbound.sqlite': raise ValueError('invalid_production_mail_ledger')
            else: path='/var/lib/kwod/private/mail-outbound.sqlite'
        self.path=Path(path)
        self.reviewer=reviewer or SocketReviewer()
        self.clock=clock or (lambda:datetime.now(timezone.utc).timestamp())

    def initialize_ledger(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink(): raise ValueError('mail_ledger_is_link')
        db=sqlite3.connect(self.path,timeout=30)
        self.path.chmod(0o600)
        db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL')
        db.execute('''CREATE TABLE IF NOT EXISTS outbound (
            key TEXT PRIMARY KEY, digest TEXT NOT NULL, recipient TEXT NOT NULL,
            created REAL NOT NULL, send_started REAL, status TEXT NOT NULL,
            raw BLOB NOT NULL, verdict TEXT, result TEXT)''')
        return db

    def deliver(self,raw,sender,transport):
        if stopped(): return {'sent':False,'status':'safety_paused'}
        if not isinstance(raw,bytes) or len(raw)>MAX_MESSAGE_BYTES:
            raise ValueError('invalid_outbound_message')
        msg=BytesParser(policy=policy.default).parsebytes(raw)
        if msg.defects or msg.is_multipart() or msg.get_content_type()!='text/plain':
            raise ValueError('plain_mail_only_no_attachments')
        if msg.get_all('Cc') or msg.get_all('Bcc') or msg.get_all('Resent-To') or msg.get_all('Resent-Bcc'):
            raise ValueError('single_recipient_only_no_cc_bcc')
        if len(msg.get_all('From',[]))!=1 or str(msg['From'])!=sender or len(msg.get_all('To',[]))!=1:
            raise ValueError('invalid_mail_identity')
        if msg.get_all('Sender') or msg.get_all('Reply-To'):
            raise ValueError('alternate_identity_not_allowed')
        addresses=getaddresses([str(msg['To'])])
        if len(addresses)!=1: raise ValueError('exactly_one_recipient_required')
        recipient=addresses[0][1]
        key=str(msg.get('X-KWOD-Idempotency-Key',''))
        if len(msg.get_all('X-KWOD-Idempotency-Key',[]))!=1 or len(msg.get_all('Subject',[]))!=1:
            raise ValueError('duplicate_mail_headers')
        if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}',key): raise ValueError('invalid_mail_idempotency_key')
        text=msg.get_content().rstrip()
        if text.endswith(AI_SIGNATURE): text=text[:-len(AI_SIGNATURE)].rstrip()
        text=external_name(text)
        subject=external_name(str(msg.get('Subject','')))
        canonical={'sender':sender,'recipient':recipient,'subject':subject,'text':text}
        digest=hashlib.sha256(json.dumps(canonical,sort_keys=True).encode()).hexdigest()
        outgoing=build_outbound(**canonical,idempotency_key=key)
        db=self.initialize_ledger()
        now=self.clock()
        try:
            db.execute('BEGIN IMMEDIATE')
            existing=db.execute('SELECT digest,status,result FROM outbound WHERE key=?',(key,)).fetchone()
            if existing:
                db.rollback()
                if existing[0]!=digest: raise ValueError('idempotency_key_payload_conflict')
                return {'sent':False,'status':'duplicate_not_replayed','previous_status':existing[1],
                        'previous_result':json.loads(existing[2]) if existing[2] else None}
            db.execute('INSERT INTO outbound(key,digest,recipient,created,status,raw) VALUES (?,?,?,?,?,?)',
                       (key,digest,recipient,now,'reviewing',outgoing)); db.commit()
            if (self.path.parent/'mail-restore-review-required').exists():
                verdict={'decision':'PAUSE_FOR_REVIEW','category':'restored_ledger_requires_reconciliation'}
                db.execute("UPDATE outbound SET status='review_required',verdict=? WHERE key=?",(json.dumps(verdict),key)); db.commit()
                return {'sent':False,'status':'review_required','safety':verdict}
            # Bound reviewer costs too. Ten reserved candidates per rolling day,
            # not just ten successful deliveries. Unknown SMTP effects count.
            reserved=db.execute("SELECT count(*) FROM outbound WHERE created>? AND status!='rate_limited'",(now-86400,)).fetchone()[0]
            if reserved>10:
                db.execute("UPDATE outbound SET status='rate_limited' WHERE key=?",(key,)); db.commit()
                return {'sent':False,'status':'rate_limited'}
            # This reviewer has no agent context or tools. Failure never enables SMTP.
            verdict=self.reviewer(dict(canonical,untrusted_external_content=True))
            decision=verdict.get('decision')
            if decision not in ('ALLOW','BLOCK','PAUSE_FOR_REVIEW'):
                decision='PAUSE_FOR_REVIEW'; verdict={'decision':decision,'category':'invalid_gate_reply'}
            if decision!='ALLOW':
                status='blocked' if decision=='BLOCK' else 'review_required'
                db.execute('UPDATE outbound SET status=?,verdict=? WHERE key=?',(status,json.dumps(verdict),key)); db.commit()
                return {'sent':False,'status':status,'safety':verdict}
            db.execute('BEGIN IMMEDIATE')
            count=db.execute('SELECT count(*) FROM outbound WHERE send_started>?',(now-86400,)).fetchone()[0]
            status='rate_limited' if count>=10 else ('safety_paused' if stopped() else 'sending_outcome_unknown')
            db.execute('UPDATE outbound SET status=?,verdict=?,send_started=? WHERE key=?',
                       (status,json.dumps(verdict),now if status=='sending_outcome_unknown' else None,key)); db.commit()
            if status!='sending_outcome_unknown': return {'sent':False,'status':status}
            try:
                result=transport(sender,recipient,outgoing)
            except Exception:
                return {'sent':False,'status':'outcome_unknown','automatic_retry':False}
            db.execute('UPDATE outbound SET status=?,result=? WHERE key=?',
                       ('smtp_accepted',json.dumps(result),key)); db.commit()
            return {'sent':True,'status':'smtp_accepted','delivery_to_inbox_verified':False,**result}
        finally: db.close()
