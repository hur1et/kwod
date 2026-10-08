"""Independent deterministic observer. No model, network, strategy or tools."""
from datetime import datetime, timezone
from email.utils import getaddresses
import hashlib
import ipaddress
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import socketserver
import sqlite3
import struct
import time
from urllib.parse import urlsplit
from .store import atomic_write
from .tools import validate
from .browser_policy import normalize_url,public_address,BrowserBlocked

def browser_enabled(): return Path('/etc/kwod-safety/BROWSER_ENABLED').exists()

REQUIRED=Path('/etc/kwod-safety/WATCHDOG_REQUIRED')
PAUSE=Path('/etc/kwod-safety/WATCHDOG_PAUSE')
CATEGORIES={'none','secret_access','unauthorized_access','private_network_access',
            'large_recipient_list','capability_withheld','invalid_arguments',
            'threat_or_coercion','fraud_or_impersonation','private_data_or_secrets',
            'unexpected_payment_destination','payment_capability_withheld',
            'repeated_guardrail_probing','review_required','uncertain','watchdog_unavailable','unsupported_content','response_limit'}
PROBES={'secret_access','unauthorized_access','private_network_access','large_recipient_list','capability_withheld'}

def required():
    try: REQUIRED.lstat(); return True
    except FileNotFoundError: return False
    except OSError: return True

def rule(event):
    kind=event.get('kind'); args=event.get('arguments',{})
    if kind=='payment_attempt':
        from .autonomy import enabled
        from .payments import transaction, PaymentError
        if enabled('payments'):
            try: transaction(args)
            except (PaymentError,TypeError): return 'BLOCK','invalid_arguments'
            return 'ALLOW','none'
        # No payment capability is enabled by preparation. Existing signer is
        # observation-only. Destination approval and fresh balance belong to
        # future payment gateway provisioning, never to model-supplied claims.
        return 'PAUSE_FOR_REVIEW','unexpected_payment_destination'
    if kind=='browser_navigation':
        try:
            policy_block=args.get('policy_block')
            if policy_block in ('invalid_arguments','capability_withheld','private_network_access','unsupported_content','response_limit'):
                return 'BLOCK',policy_block
            if policy_block=='review_required': return 'PAUSE_FOR_REVIEW','review_required'
            normalize_url(args.get('url',''))
            if not browser_enabled(): return 'BLOCK','capability_withheld'
            addresses=args.get('addresses',[])
            if args.get('destination_blocked') or any(not public_address(x) for x in addresses):
                return 'BLOCK','private_network_access'
            if not addresses: return 'BLOCK','invalid_arguments'
            return ('ALLOW','none') if browser_enabled() else ('BLOCK','capability_withheld')
        except BrowserBlocked as error: return 'BLOCK',error.category
        except (ValueError,TypeError): return 'BLOCK','invalid_arguments'
    if kind=='result':
        category=event.get('category','none')
        if category in ('threat_or_coercion','private_data_or_secrets'):
            return 'PAUSE_FOR_REVIEW',category
        if event.get('review_required'): return 'PAUSE_FOR_REVIEW','review_required'
        if event.get('blocked'): return 'BLOCK',category if category in CATEGORIES else 'uncertain'
        return 'ALLOW','none'
    if kind!='tool_attempt': return 'BLOCK','invalid_arguments'
    tool=event.get('tool')
    try: validate(tool,args)
    except (ValueError,TypeError): return 'BLOCK','invalid_arguments'
    if tool in ('read_file','write_file','list_files'):
        path=args['path']
        if tool=='list_files' and path=='': path='.'
        if path in ('/workspace','/workspace/'): path='.'
        elif path.startswith('/workspace/'): path=path[len('/workspace/'):]
        normalized=path.replace('\\','/')
        if any(p in normalized for p in ('/etc/kwod','/var/lib/kwod/private','/var/lib/kwod-signer','.ssh/','/etc/shadow')):
            return 'BLOCK','secret_access'
        if not path or PurePosixPath(path).is_absolute() or '..' in PurePosixPath(path).parts or '\\' in path or ':' in path:
            return 'BLOCK','unauthorized_access'
    if tool=='mail_send':
        if len(getaddresses([args['recipient']]))!=1:
            return 'BLOCK','large_recipient_list'
    from .autonomy import enabled
    features={'publish_website':'publication','browser_action':'browser_sessions',
              'service_start':'services','service_stop':'services','service_list':'services',
              'wallet_transfer':'payments','wallet_status':'payments'}
    if tool in features:
        return ('ALLOW','none') if enabled(features[tool]) else ('BLOCK','capability_withheld')
    if tool=='browser_open':
        try: normalize_url(args['url'])
        except BrowserBlocked as error: return 'BLOCK',error.category
        return ('ALLOW','none') if browser_enabled() else ('BLOCK','capability_withheld')
    # Arbitrary terminal programs remain confined by Docker network=none and
    # mounts. We do not pretend keyword matching understands arbitrary code.
    return 'ALLOW','none'

class WatchdogState:
    def __init__(self,path,pause_file,public_file,*,clock=time.time,public_gid=None):
        self.path=Path(path); self.pause_file=Path(pause_file); self.public_file=Path(public_file)
        self.clock=clock; self.public_gid=public_gid
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS observation(id INTEGER PRIMARY KEY,at REAL NOT NULL,kind TEXT NOT NULL,tool TEXT NOT NULL,decision TEXT NOT NULL,category TEXT NOT NULL,request_hash TEXT NOT NULL,effect TEXT NOT NULL)')
        self.path.chmod(0o600)
        self.export()
    def close(self): self.db.close()
    def evaluate(self,event):
        if self.pause_file.exists():
            return {'decision':'PAUSE_FOR_REVIEW','category':'review_required'}
        decision,category=rule(event); now=self.clock()
        probes=self.db.execute("SELECT count(*) FROM observation WHERE at>? AND category IN ('secret_access','unauthorized_access','private_network_access','large_recipient_list','capability_withheld')",(now-3600,)).fetchone()[0]
        if decision=='BLOCK' and category in PROBES and probes>=2:
            decision='PAUSE_FOR_REVIEW'; category='repeated_guardrail_probing'
        effect=event.get('effect','not_started')
        if effect not in ('not_started','unknown','not_applicable'): effect='unknown'
        with self.db:
            cursor=self.db.execute('INSERT INTO observation(at,kind,tool,decision,category,request_hash,effect) VALUES (?,?,?,?,?,?,?)',
                (now,str(event.get('kind',''))[:40],str(event.get('tool',''))[:40],decision,category,
                 hashlib.sha256(json.dumps(event,sort_keys=True).encode()).hexdigest(),effect))
        if decision=='PAUSE_FOR_REVIEW':
            atomic_write(self.pause_file,json.dumps({'category':category,'observation_id':cursor.lastrowid,'economic_event':False}).encode(),mode=0o644)
        self.export()
        return {'decision':decision,'category':category,'observation_id':cursor.lastrowid}
    def export(self):
        count=self.db.execute("SELECT count(*) FROM observation WHERE decision!='ALLOW'").fetchone()[0]
        last=self.db.execute("SELECT id,at,decision,category,effect FROM observation WHERE decision!='ALLOW' ORDER BY id DESC LIMIT 1").fetchone()
        data={'available':True,'paused':self.pause_file.exists(),'interventions_count':count,
              'as_of':datetime.fromtimestamp(self.clock(),timezone.utc).isoformat(),
              'economic_event':False,'last_intervention':None}
        if last:
            data['last_intervention']={'id':last[0],'at':datetime.fromtimestamp(last[1],timezone.utc).isoformat(),
                'decision':last[2],'category':last[3],'effect':last[4]}
        atomic_write(self.public_file,json.dumps(data).encode(),mode=0o640)
        if self.public_gid is not None: os.chown(self.public_file,0,self.public_gid)

class SocketWatchdog:
    def __init__(self,path='/run/kwod-watchdog/control.sock'): self.path=path
    def evaluate(self,event):
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                conn.settimeout(10); conn.connect(self.path)
                conn.sendall(json.dumps(event).encode()+b'\n')
                with conn.makefile('rb') as stream: raw=stream.readline(4097)
            if len(raw)>4096: raise ValueError('oversized_watchdog_reply')
            verdict=json.loads(raw)
            if verdict.get('decision') not in ('ALLOW','BLOCK','PAUSE_FOR_REVIEW') or verdict.get('category') not in CATEGORIES:
                raise ValueError('invalid_watchdog_reply')
            return verdict
        except (OSError,ValueError,AttributeError):
            return {'decision':'PAUSE_FOR_REVIEW','category':'watchdog_unavailable'}

def main():
    import grp,pwd
    runtime=pwd.getpwnam('kwod-runtime').pw_uid
    authorized={runtime}
    browser_uid=None
    try:
        browser_uid=pwd.getpwnam('kwod-browser').pw_uid; authorized.add(browser_uid)
    except KeyError: pass
    try: authorized.add(pwd.getpwnam('kwod-signer').pw_uid)
    except KeyError: pass
    state=WatchdogState('/var/lib/kwod-safety/watchdog.sqlite',PAUSE,
                       '/var/lib/kwod/public/safety/status.json',public_gid=grp.getgrnam('kwod-public').gr_gid)
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(10)
            pid,uid,gid=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid not in authorized: return
            try:
                raw=self.rfile.readline(1_048_577)
                if len(raw)>1_048_576 or not raw.endswith(b'\n'): raise ValueError('oversized_observation')
                event=json.loads(raw)
                if not isinstance(event,dict): raise ValueError('invalid_observation')
                if uid==browser_uid:
                    if event.get('kind')!='browser_navigation': raise ValueError('caller_scope')
                elif uid==runtime:
                    if event.get('kind') not in ('tool_attempt','result'): raise ValueError('caller_scope')
                elif event.get('kind')!='payment_attempt': raise ValueError('caller_scope')
                verdict=state.evaluate(event)
            except (ValueError,TypeError,KeyError):
                verdict={'decision':'PAUSE_FOR_REVIEW','category':'uncertain'}
            self.wfile.write(json.dumps(verdict).encode()+b'\n')
    path=Path('/run/kwod-watchdog/control.sock')
    if path.exists(): path.unlink()
    try:
        with socketserver.UnixStreamServer(str(path),Handler) as server:
            path.chmod(0o660)
            server.timeout=5
            while True:
                server.handle_request()
                state.export()
    finally: state.close()

if __name__=='__main__': main()
