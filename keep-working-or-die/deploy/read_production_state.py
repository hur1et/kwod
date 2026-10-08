"""Read under database owner's identity so SQLite WAL sidecars never become root-owned."""
import json
from pathlib import Path
import sqlite3
import sys
from check_production_readiness import state

root=Path('/var/lib/kwod-production')
if __name__=='__main__':
    if sys.argv[1:]==['--birth-only']:
        db=sqlite3.connect((root/'private/state.sqlite').as_uri()+'?mode=ro',uri=True)
        try:
            row=db.execute("SELECT mode,born_at FROM instance WHERE id='prod'").fetchone()
            if row is None or row[0]!='prod': raise ValueError('wrong_store')
            print(json.dumps({'born_at':row[1]}))
        finally: db.close()
    elif not sys.argv[1:]:
        result={'state':state(root),'mail_ledger_valid':False,'mail_ledger_rows':None}
        try:
            db=sqlite3.connect((root/'private/mail-outbound.sqlite').as_uri()+'?mode=ro',uri=True)
            try:
                columns={row[1] for row in db.execute('PRAGMA table_info(outbound)')}
                result['mail_ledger_valid']=db.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and {'key','digest','raw','status','send_started','verdict','result'}<=columns
                result['mail_ledger_rows']=db.execute('SELECT count(*) FROM outbound').fetchone()[0]
            finally: db.close()
        except sqlite3.Error: pass
        print(json.dumps(result))
    else: raise ValueError('invalid_state_request')
