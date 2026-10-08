"""Deterministic mail boundary for the agent's future SMTP/IMAP adapter.

This module parses and builds messages only. Network access and delivery remain
outside the runtime until the operator provisions the real domain and secrets.
"""
from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import formatdate
import hashlib
import re
from email.utils import getaddresses


MAX_MESSAGE_BYTES = 1_048_576
AI_SIGNATURE = 'Sent autonomously by the AI agent kwod.'


def external_name(text):
    """Deterministic outgoing identity rule, including model-generated body text."""
    text=re.sub(r'(?i)\bkeep[\s_\-\u2010-\u2015]*working[\s_\-\u2010-\u2015]*or[\s_\-\u2010-\u2015]*die\b','kwod',text)
    return re.sub(r'(?i)\bkwod\b','kwod',text)


@dataclass(frozen=True)
class InboundMessage:
    message_id: str
    sender: str
    recipient: str
    subject: str
    text: str
    fingerprint: str


def parse_inbound(raw: bytes, *, max_bytes: int = MAX_MESSAGE_BYTES) -> InboundMessage:
    """Parse one bounded RFC822 message without following links or attachments."""
    if not isinstance(raw, bytes) or not raw or len(raw) > max_bytes:
        raise ValueError('mail message exceeds configured boundary')
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    message_id = (msg.get('Message-ID') or '').strip()
    sender = (msg.get('From') or '').strip()
    recipient = (msg.get('To') or '').strip()
    if not message_id or not sender or not recipient:
        raise ValueError('mail requires Message-ID, From and To')
    if msg.is_multipart():
        parts = [p for p in msg.walk() if p.get_content_type() == 'text/plain' and not p.is_attachment()]
        text = '\n'.join(p.get_content() for p in parts)
    elif msg.get_content_type() == 'text/plain':
        text = msg.get_content()
    else:
        text = ''
    return InboundMessage(message_id, sender, recipient, (msg.get('Subject') or '').strip(), text,
                          hashlib.sha256(raw).hexdigest())


def build_outbound(*, sender: str, recipient: str, subject: str, text: str, idempotency_key: str) -> bytes:
    """Build a stable outbound message; the caller owns delivery and retry policy."""
    values = (sender, recipient, subject, text, idempotency_key)
    if not all(isinstance(v, str) and v.strip() for v in values):
        raise ValueError('outbound mail fields must be non-empty strings')
    if not re.fullmatch(r'[A-Za-z0-9._-]{1,128}', idempotency_key):
        raise ValueError('invalid_mail_idempotency_key')
    if any(c in sender + recipient + subject for c in '\r\n'):
        raise ValueError('invalid_mail_header')
    addresses=getaddresses([recipient])
    if len(addresses)!=1 or not re.fullmatch(r'[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+',addresses[0][1]):
        raise ValueError('exactly_one_recipient_required')
    msg = EmailMessage(policy=policy.SMTP)
    msg['From'] = sender
    msg['To'] = recipient
    msg['Subject'] = external_name(subject)
    msg['Date'] = formatdate(usegmt=True)
    msg['Message-ID'] = f'<kwod-{idempotency_key}@local>'
    msg['X-KWOD-Idempotency-Key'] = idempotency_key
    msg.set_content(external_name(text).rstrip() + '\n\n' + AI_SIGNATURE + '\n')
    return msg.as_bytes()
