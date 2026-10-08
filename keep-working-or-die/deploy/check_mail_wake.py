"""Read-only mailbox and worker diagnosis. No model, mail send or state writes."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
from kwod.mail_gateway import MailboxGateway

def main():
    if os.geteuid()==0: raise ValueError('runtime_identity_required')
    result={'model_calls':0,'mail_sent':False,'message_contents_read':False,'state_modified':False}
    process=subprocess.run(['systemctl','is-active','kwod-production.service'],capture_output=True,text=True)
    result['production_service']=process.stdout.strip()
    with sqlite3.connect(Path('/var/lib/kwod-production/private/state.sqlite').as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        result['runtime']=dict(db.execute("SELECT state,reason,wake_at FROM runtime_state WHERE instance_id='prod'").fetchone())
        result['pending_requests']=db.execute("SELECT count(*) FROM model_attempt WHERE status IN ('sent','outcome_unknown')").fetchone()[0]
        result['stop_active']=Path('/etc/kwod-safety/STOP').exists()
        result['safety_pause_active']=Path('/etc/kwod-safety/WATCHDOG_PAUSE').exists()
        try:
            messages=MailboxGateway().list_unread(100,operator_only=True)
            result['mail_poll']='ok'; result['operator_messages_found']=len(messages)
            if db.execute("SELECT 1 FROM sqlite_master WHERE name='inbox_wake'").fetchone():
                result['unnotified_operator_messages']=sum(not db.execute('SELECT 1 FROM inbox_wake WHERE mailbox_epoch=? AND uid=?',(m['uidvalidity'],m['uid'])).fetchone() for m in messages)
        except Exception as exc:
            result['mail_poll']='failed'; result['error_type']=type(exc).__name__
            known={'unsafe_mail_credentials','invalid_mailbox_configuration','mail_provider_not_allowed','mailbox_uidvalidity_missing','operator_safety_stop','mailbox_select_failed','mailbox_search_failed'}
            if str(exc) in known: result['error_code']=str(exc)
    print(json.dumps(result,ensure_ascii=True))

if __name__=='__main__': main()
