"""Separate loopback operator surface. Never embedded in the public observer."""
import base64
from datetime import datetime,timezone
import hashlib
import hmac
import json
import logging
from pathlib import Path
import secrets
import stat
import subprocess
import threading
import time

import httpx
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import HTMLResponse,Response

from .birth import credit_amount
from .store import atomic_write,encode,utcnow
from .tools import parse_time

CONTROL=Path('/etc/kwod-production')
ROOT=Path('/var/lib/kwod-production')
RELEASE=Path('/opt/kwod/current')


def wallet_proof(control=CONTROL):
    """Operator-reviewed external evidence, not an automatically verified payment."""
    path=control/'wallet-openrouter-verified.json'
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600 or info.st_size>16384:
        raise ValueError('wallet_test_evidence_unprotected')
    value=json.loads(path.read_text())
    import re
    if value.get('operator_confirmed') is not True or not re.fullmatch('0x[a-fA-F0-9]{64}',value.get('transaction_hash','')) or not isinstance(value.get('openrouter_payment_id'),str) or not 1<=len(value['openrouter_payment_id'])<=200:
        raise ValueError('wallet_test_evidence_invalid')
    if parse_time(value['reviewed_at'])>datetime.now(timezone.utc): raise ValueError('wallet_test_evidence_invalid')
    return value


class Controller:
    def __init__(self): self.lock=threading.Lock(); self.previews={}

    def status(self):
        try:
            result=subprocess.run(['runuser','-u','kwod-runtime','--',str(RELEASE/'.venv/bin/python'),str(RELEASE/'deploy/read_production_state.py'),'--birth-only'],capture_output=True,text=True,timeout=10,check=True)
            born_at=json.loads(result.stdout)['born_at']
        except Exception as exc:
            # This helper reads only born_at, never credentials or mail content.
            logging.getLogger(__name__).error('Birth state reader failed: type=%s errno=%s exit=%s stderr=%s',
                type(exc).__name__,getattr(exc,'errno',None),getattr(exc,'returncode',None),(getattr(exc,'stderr','') or '')[-3000:])
            return {'ready':False,'born_at':None,'blockers':['Produktionszustand konnte im Operatordienst nicht gelesen werden.']}
        if born_at:
            result=subprocess.run(['systemctl','show','kwod-production.service','--property=ActiveState','--value'],capture_output=True,text=True,timeout=10)
            return {'ready':False,'born_at':born_at,'worker_state':result.stdout.strip() if result.returncode==0 else 'unknown','blockers':[]}
        result=subprocess.run([str(RELEASE/'.venv/bin/python'),str(RELEASE/'deploy/check_production_readiness.py')],capture_output=True,text=True,timeout=30)
        try: readiness=json.loads(result.stdout); blockers=readiness['blockers']
        except (ValueError,KeyError,TypeError): blockers=['Installierte Readiness konnte nicht geprüft werden.']
        if result.returncode and not blockers: blockers=['Installierte Readiness fehlgeschlagen.']
        return {'ready':not blockers,'born_at':None,'blockers':blockers,
            'warnings':['Start ohne finanziertes Wallet. Wallet–OpenRouter-Verbindung ungeprüft; Erbe besteht aus den vorhandenen OpenRouter-Credits.']}

    def balance(self):
        # Read account balance with an independently protected management credential.
        path=Path('/etc/kwod-openrouter/credits.key')
        if not path.exists(): path=Path('/etc/kwod-openrouter/api.key')
        info=path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600:
            raise ValueError('OpenRouter-Zugang ist nicht geschützt.')
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=20) as client:
            response=client.get('https://openrouter.ai/api/v1/credits',headers={'Authorization':'Bearer '+path.read_text().strip()})
            if response.status_code in (401,403): raise ValueError('Für den Kontostand fehlt ein gültiger OpenRouter-Management-Key.')
            if response.status_code!=200 or len(response.content)>65536: raise ValueError('OpenRouter-Kontostand konnte nicht gelesen werden.')
            data=response.json()['data']; credit_amount(data)
            return {'observed_at':utcnow(),'data':{key:data[key] for key in ('total_credits','total_usage')},'wallet_test':None}

    def preview(self):
        with self.lock:
            state=self.status()
            if not state['ready']: raise ValueError('; '.join(state['blockers']) or 'Birth bereits erfolgt.')
            evidence=self.balance(); identity=secrets.token_urlsafe(32)
            self.previews={identity:(time.monotonic(),evidence)}
            return {'preview_id':identity,'amount_micro':credit_amount(evidence['data']),'currency':'USD','expires_in':60}

    def birth(self,preview_id):
        with self.lock:
            preview=self.previews.pop(preview_id,None)
            if preview is None or time.monotonic()-preview[0]>60: raise ValueError('Vorschau abgelaufen. Bitte erneut prüfen.')
            state=self.status()
            if not state['ready']: raise ValueError('; '.join(state['blockers']) or 'Birth bereits erfolgt.')
            evidence=self.balance()
            if credit_amount(evidence['data'])!=credit_amount(preview[1]['data']) or evidence['wallet_test']!=preview[1]['wallet_test']:
                raise ValueError('Erbe oder Startbedingungen geändert. Bitte erneut prüfen.')
            if any(Path('/etc/kwod-safety',name).exists() for name in ('STOP','WATCHDOG_PAUSE')):
                raise ValueError('Sicherheitsstopp aktiv.')
            result=subprocess.run(['runuser','-u','kwod-runtime','--',str(RELEASE/'.venv/bin/python'),str(RELEASE/'deploy/record_birth.py')],
                input=encode(evidence).decode(),capture_output=True,text=True,timeout=30)
            if result.returncode: raise ValueError('Birth konnte nicht vollständig bestätigt werden. Status prüfen; kein automatischer Wiederholungsversuch.')
            resources=json.loads(result.stdout)
            atomic_write(CONTROL/'BORN',encode(resources),0o600)
            # No retry after any outcome. Recorded birth remains single, even if start fails.
            try:
                started=subprocess.run(['systemctl','enable','--now','kwod-production.service'],capture_output=True,text=True,timeout=30)
                active=subprocess.run(['systemctl','is-active','--quiet','kwod-production.service'],timeout=10).returncode==0
            except subprocess.TimeoutExpired: active=False; started=None
            return {'born_at':resources['born_at'],'worker_started':active and started is not None and started.returncode==0,
                'message':'Birth gespeichert. Bei fehlendem Workerstart den gespeicherten Stand prüfen; Birth wird nicht wiederholt.'}


def create_operator_app(password_record,controller=None):
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    control=controller or Controller(); csrf=secrets.token_urlsafe(32)
    allowed_hosts={'127.0.0.1:8766','127.0.0.1:8001','localhost:8766'}
    attempts={}; auth_lock=threading.Lock()

    @app.middleware('http')
    async def authenticate(request,call_next):
        if request.headers.get('host') not in allowed_hosts:
            return Response('Ungültiger Operator-Host.',status_code=403)
        address=request.client.host if request.client else 'unknown'
        now=time.monotonic()
        with auth_lock:
            failed=[at for at in attempts.get(address,[]) if now-at<60]
            attempts[address]=failed
            if len(failed)>=5: return Response('Bitte eine Minute warten.',status_code=429)
        valid=False
        try:
            scheme,raw=request.headers.get('authorization','').split(' ',1)
            if scheme.lower()=='basic' and len(raw)<1024:
                user,password=base64.b64decode(raw,validate=True).decode().split(':',1)
                digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(password_record['salt']),password_record['iterations']).hex()
                valid=user=='operator' and hmac.compare_digest(digest,password_record['digest'])
        except (ValueError,UnicodeError): pass
        if not valid:
            if request.headers.get('authorization'):
                with auth_lock: attempts[address].append(now)
            return Response('Operator-Anmeldung erforderlich.',status_code=401,headers={'WWW-Authenticate':'Basic realm="KWOD Operator", charset="UTF-8"'})
        if request.method!='GET':
            origin=request.headers.get('origin')
            if origin!='http://'+request.headers['host'] or not hmac.compare_digest(request.headers.get('x-kwod-csrf',''),csrf):
                return Response('Ungültige Startfreigabe.',status_code=403)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        return response

    @app.get('/',response_class=HTMLResponse)
    def dashboard():
        page=(Path(__file__).parent/'static/index.html').read_text(encoding='utf-8')
        panel=(Path(__file__).parent/'static/birth-panel.html').read_text(encoding='utf-8')
        return HTMLResponse(page.replace('<section class="hero">',panel+'<section class="hero">',1),headers={'Content-Security-Policy':"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"})

    @app.get('/operator/status')
    def status(): return {**control.status(),'csrf':csrf}

    def failure(exc):
        if isinstance(exc,ValueError): return HTTPException(409,str(exc))
        return HTTPException(503,'Operatoraktion nicht bestätigt. Gespeicherten Status prüfen.')

    @app.post('/operator/preview')
    def preview():
        try: return control.preview()
        except Exception as exc: raise failure(exc) from None

    @app.post('/operator/birth')
    async def birth(request:Request):
        length=request.headers.get('content-length','')
        if not length.isdigit() or int(length)>512: raise HTTPException(413,'Ungültige Startanfrage.')
        try:
            value=json.loads(await request.body())
            if set(value)!={'preview_id','confirmation'} or value['confirmation']!='BIRTH' or not isinstance(value['preview_id'],str):
                raise HTTPException(400,'Ausdrückliche Bestätigung fehlt.')
        except (ValueError,TypeError): raise HTTPException(400,'Ungültige Startanfrage.') from None
        from starlette.concurrency import run_in_threadpool
        try: return await run_in_threadpool(control.birth,value['preview_id'])
        except Exception as exc: raise failure(exc) from None

    @app.get('/api/v1/{name}')
    def public_data(name:str,request:Request):
        if name not in {'status','events','assets','work-runs','safety','net-worth','costs'}: raise HTTPException(404)
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=10) as client:
            response=client.get('http://127.0.0.1:8000/api/v1/'+name,params=request.query_params)
        return Response(response.content,status_code=response.status_code,media_type='application/json')

    return app


def main():
    import uvicorn
    uvicorn.run(create_operator_app(json.loads((CONTROL/'operator-password.json').read_text())),host='127.0.0.1',port=8001,access_log=False)

if __name__=='__main__': main()
