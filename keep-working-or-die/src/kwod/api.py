"""Read-only public observer. It has no Store, provider or worker instance."""
from datetime import datetime, timezone
import json
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse

from .projection import connect_readonly
from .tools import parse_time
from .work_monitor import public_snapshot


def create_app(public_db,*,safety_file=None):
    app = FastAPI(title='kwod — public observer')

    @app.get('/', response_class=HTMLResponse, include_in_schema=False)
    def dashboard():
        return HTMLResponse((Path(__file__).parent / 'static/index.html').read_text(encoding='utf-8'),
            headers={'Content-Security-Policy': "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
                     'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer'})

    def read(sql, params=()):
        try:
            db = connect_readonly(public_db)
            try:
                return [dict(r) for r in db.execute(sql, params)]
            finally:
                db.close()
        except sqlite3.Error:
            raise HTTPException(503, 'Public projection unavailable') from None

    @app.get('/healthz')
    def health():
        read('SELECT id FROM snapshot LIMIT 1')
        return {'ok': True, 'component': 'public_observer'}

    @app.get('/api/v1/status')
    def status():
        rows = read('SELECT payload FROM snapshot WHERE id=1')
        if not rows:
            raise HTTPException(503, 'Public projection unavailable')
        result = json.loads(rows[0]['payload'])
        age = (datetime.now(timezone.utc) - parse_time(result['as_of'])).total_seconds()
        result['stale'] = age > 30
        result['worker_observation'] = 'unknown' if result['stale'] else 'recent'
        return result

    @app.get('/api/v1/events')
    def events(after_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)):
        rows = read('SELECT id,occurred_at,published_at,schema_version,kind,label FROM public_event WHERE id>? ORDER BY id LIMIT ?', (after_id, limit))
        return {'events': rows, 'next_cursor': rows[-1]['id'] if rows else after_id}

    @app.get('/api/v1/assets')
    def assets():
        from .assets import public_snapshot
        return {**public_snapshot(),'born_at':status()['born_at']}

    @app.get('/api/v1/costs')
    def costs():
        try:
            value=json.loads((Path(public_db).parent/'costs.json').read_text(encoding='utf-8'))
            required={'as_of','currency','model_attempts','completed_responses','openrouter_cost_usd_micro',
                      'responses_with_openrouter_cost','responses_without_openrouter_cost',
                      'attempts_without_confirmed_response_cost','token_usage','request_payload_bytes',
                      'safety_guard_blocks','mail','notes'}
            if set(value) != required:
                raise ValueError('invalid_cost_observation')
            return value
        except (OSError,ValueError,TypeError,json.JSONDecodeError):
            raise HTTPException(503,'Cost observation unavailable') from None

    @app.get('/api/v1/work-runs')
    def work_runs():
        return public_snapshot(Path(public_db).parent / 'work-runs.json')

    @app.get('/api/v1/safety')
    def safety():
        try:
            source=json.loads(Path(safety_file or Path(public_db).parent/'safety/status.json').read_text())
            result={key:source[key] for key in ('available','paused','interventions_count','as_of','economic_event')}
            last=source.get('last_intervention')
            result['last_intervention']={key:last[key] for key in ('id','at','decision','category','effect')} if last else None
            result['stale']=(datetime.now(timezone.utc)-parse_time(result['as_of'])).total_seconds()>30
            result['operator_stopped']=Path('/etc/kwod-safety/STOP').exists()
            result['paused']=result['paused'] or result['operator_stopped']
            return result
        except (OSError,ValueError,KeyError,TypeError):
            raise HTTPException(503,'Safety observation unavailable') from None

    @app.get('/api/v1/net-worth')
    def net_worth(after: str | None = None):
        if after is not None:
            try:
                parse_time(after)
            except ValueError:
                raise HTTPException(422, 'Timezone-aware timestamp required') from None
        return {'points': [], 'quality': 'unknown', 'born_at': status()['born_at']}

    @app.get('/api/v1/asset-history')
    def asset_history(asset_id: str = 'openrouter_credits'):
        if asset_id not in ('openrouter_credits','wallet_base_eth','wallet_base_usdc'):
            raise HTTPException(422,'Unsupported asset')
        try:
            rows=read('SELECT observed_at,currency,amount_micro FROM (SELECT observed_at,currency,amount_micro FROM asset_history WHERE asset_id=? ORDER BY observed_at DESC LIMIT 1440) ORDER BY observed_at',(asset_id,))
        except HTTPException:
            # An older projection is awaiting its first tick after installation.
            rows=[]
        return {'asset_id':asset_id,'points':rows,'quality':'confirmed' if rows else 'unknown'}

    return app
