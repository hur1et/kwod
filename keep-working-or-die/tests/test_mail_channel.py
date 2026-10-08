import unittest

from kwod.mail_channel import build_outbound, parse_inbound


class MailChannelTests(unittest.TestCase):
    def test_external_identity_is_kwod_in_subject_body_and_signature(self):
        raw=build_outbound(sender='agent.kwod@gmx.de',recipient='julius.weiske@gmx.de',
            subject='KEEP WORKING OR DIE',text='I am Keep Working Or Die. KWOD.',idempotency_key='identity-test')
        message=parse_inbound(raw)
        self.assertEqual(message.subject,'kwod')
        self.assertNotIn('working',message.text.casefold())
        self.assertIn('I am kwod. kwod.',message.text)
        self.assertIn('Sent autonomously by the AI agent kwod.',message.text)
    def test_parse_plain_message_and_fingerprint(self):
        raw = (b'Message-ID: <one@example.test>\r\nFrom: customer@example.test\r\n'
               b'To: agent@kwod.tld\r\nSubject: Briefing\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nHallo')
        message = parse_inbound(raw)
        self.assertEqual(message.message_id, '<one@example.test>')
        self.assertEqual(message.text, 'Hallo')
        self.assertEqual(len(message.fingerprint), 64)

    def test_missing_identity_or_oversized_message_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_inbound(b'From: x\r\nTo: y\r\n\r\nbody')
        with self.assertRaises(ValueError):
            parse_inbound(b'x', max_bytes=0)

    def test_outbound_contains_idempotency_marker(self):
        raw = build_outbound(sender='agent@kwod.tld', recipient='x@example.test',
                             subject='Angebot', text='Hallo', idempotency_key='abc123')
        self.assertIn(b'X-KWOD-Idempotency-Key: abc123', raw)
        self.assertEqual(parse_inbound(raw).message_id, '<kwod-abc123@local>')
