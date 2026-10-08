import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from pathlib import Path
from kwod.store import Store
from kwod.runtime import initialize
from kwod.runtime import Runtime
from kwod.config import Config
from kwod.provider import FixtureProvider
from kwod.inbox_wake import record, notifications
from kwod.mail_gateway import operator_sender,MailboxGateway


class InboxWakeTests(unittest.TestCase):
    def test_gateway_finds_read_operator_mail_and_peeks_headers_only(self):
        imap=Mock(); imap.select.return_value=('OK',[])
        imap.response.return_value=('UIDVALIDITY',[b'123'])
        imap.uid.side_effect=[('OK',[b'42']),('OK',[(b'header',b'From: Julius <julius.weiske@gmx.de>\r\nSubject: test\r\n\r\n')])]
        with patch('kwod.mail_gateway.imaplib.IMAP4_SSL') as factory,patch.object(MailboxGateway,'_config',return_value={'imap_host':'imap.gmx.net','imap_port':993,'username':'fixture','password':'fixture'}):
            factory.return_value.__enter__.return_value=imap
            result=MailboxGateway().list_unread(100,operator_only=True)
        self.assertEqual(result[0]['uid'],'42')
        self.assertEqual(imap.uid.call_args_list[0].args,('search',None,'ALL','FROM','"julius.weiske@gmx.de"'))
        self.assertEqual(imap.uid.call_args_list[1].args,('fetch',b'42','(BODY.PEEK[HEADER])'))
        imap.select.assert_called_once_with('INBOX',readonly=True)

    def test_sleep_wakes_only_for_operator_and_not_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'data',mode='prod'); initialize(store,'test',Config(mode='prod'))
            current=datetime.now(timezone.utc)
            with store.transaction():
                store.db.execute("UPDATE instance SET born_at=?",(current.isoformat(),))
                store.db.execute("UPDATE runtime_state SET state='sleeping',wake_at=?",((current+timedelta(days=1)).isoformat(),))
            provider=FixtureProvider([{'id':'test-response','model':'gpt-6-astra','status':'completed','output':[], 'usage':None}])
            runtime=Runtime(store,provider,now=lambda:current)
            runtime.mail=Mock()
            runtime.mail.list_unread.return_value=[{'uid':'1','uidvalidity':'123','from':'other@gmx.de'}]
            with patch('kwod.assets.absorb',return_value={}):
                self.assertEqual(runtime.tick(),'sleeping')
                self.assertFalse(provider.requests)
                runtime.mail.list_unread.return_value=[{'uid':'2','uidvalidity':'123','from':'julius.weiske@gmx.de'}]
                current+=timedelta(seconds=61)
                runtime.tick()
                self.assertEqual(len(provider.requests),1)
                self.assertIn('New operator mail',str(provider.requests[0]))
                self.assertEqual(notifications(store),([],[]))
                runtime.process_tools(store.db.execute('SELECT * FROM model_attempt').fetchone())
                with store.transaction():
                    runtime.transition('sleeping','test',(current+timedelta(days=1)).isoformat())
                current+=timedelta(seconds=61)
                self.assertEqual(runtime.tick(),'sleeping')
                self.assertEqual(len(provider.requests),1)
            runtime.mail.list_unread.assert_called_with(100,operator_only=True)
            store.close()

    def test_sender_requires_one_exact_operator_address(self):
        self.assertTrue(operator_sender('Julius <julius.weiske@gmx.de>'))
        for value in ('other@gmx.de', 'julius.weiske@gmx.de.attacker.test',
                      '"julius.weiske@gmx.de" <other@gmx.de>',
                      'julius.weiske@gmx.de, other@gmx.de', None):
            self.assertFalse(operator_sender(value))

    def test_dedupe_survives_restart_and_uidvalidity_change(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'data'
            store=Store(root); initialize(store,'test')
            mail={'uid':'42','uidvalidity':'123','from':'julius.weiske@gmx.de'}
            self.assertEqual(record(store,[mail,{**mail,'uid':'43','from':'other@gmx.de'}]),['42'])
            self.assertEqual(len(notifications(store)[1]),1)
            store.close(); store=Store(root)
            self.assertEqual(record(store,[mail]),[])
            self.assertEqual(len(notifications(store)[1]),1)
            with store.transaction():
                store.db.execute('UPDATE inbox_wake SET delivered=1')
            self.assertEqual(notifications(store),([],[]))
            self.assertEqual(record(store,[{**mail,'uidvalidity':'124'}]),['42'])
            store.close()

    def test_missing_uidvalidity_cannot_trigger_wake(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'data'); initialize(store,'test')
            self.assertEqual(record(store,[{'uid':'42','from':'julius.weiske@gmx.de'}]),[])
            store.close()
