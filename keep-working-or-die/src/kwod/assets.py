"""Read-only balance observations, separated from model and signing credentials."""
from datetime import datetime,timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import stat

import httpx
from .birth import credit_amount
from .payments import USDC
from .store import utcnow,encode,atomic_write
from .tools import parse_time

HOME=Path('/var/lib/kwod-assets')


def public_snapshot(path=HOME/'public.json'):
    try:
        value=json.loads(Path(path).read_text())
        for asset in value['assets']:
            asset['stale']=asset.get('observed_at') is None or (datetime.now(timezone.utc)-parse_time(asset['observed_at'])).total_seconds()>180 or bool(asset.get('error'))
        return value
    except (OSError,ValueError,KeyError,TypeError):
        return {'as_of':None,'assets':[],'quality':'unknown','net_worth_eur_micro':None}


def quantity(value):
    if not isinstance(value,str) or not re.fullmatch(r'0x[0-9a-fA-F]{1,64}',value): raise ValueError('invalid_rpc_quantity')
    return int(value,16)


def collect(previous=None):
    previous={asset['asset_id']:asset for asset in (previous or {}).get('assets',[])}
    assets=[]
    def failure(asset_id,currency,reason):
        value=dict(previous.get(asset_id,{'asset_id':asset_id,'currency':currency,'amount_micro':None,'amount_decimal':None,'observed_at':None,'quality':'unknown'}))
        value.update(error=reason,checked_at=utcnow()); assets.append(value)
    def success(asset_id,currency,units,decimals,source):
        scale=10**decimals
        amount_decimal=(str(units//scale)+'.'+str(units%scale).zfill(decimals)).rstrip('0').rstrip('.')
        assets.append({'asset_id':asset_id,'currency':currency,'amount_units':str(units),'decimals':decimals,
            'amount_micro':units*10**6//scale,'amount_decimal':amount_decimal,
            'observed_at':utcnow(),'quality':'confirmed','source':source,'error':None})
    with httpx.Client(trust_env=False,follow_redirects=False,timeout=15) as client:
        try:
            key=Path('/etc/kwod-openrouter/credits.key')
            if not key.exists(): key=Path('/etc/kwod-openrouter/api.key')
            info=key.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)!=0o600: raise ValueError('key_protection')
            response=client.get('https://openrouter.ai/api/v1/credits',headers={'Authorization':'Bearer '+key.read_text().strip()})
            if response.status_code!=200 or len(response.content)>65536: raise ValueError('credit_read_failed')
            data=response.json()['data']
            # A verified zero is a valid observation; birth itself requires positive credits.
            if data['total_credits']==data['total_usage'] and not isinstance(data['total_credits'],bool) and not isinstance(data['total_usage'],bool):
                total=Decimal(str(data['total_credits']))
                if not total.is_finite() or total<0: raise ValueError('invalid_credit_balance')
                amount=0
            else: amount=credit_amount(data)
            success('openrouter_credits','USD',amount,6,'openrouter_credits_api')
        except Exception: failure('openrouter_credits','USD','credit_read_failed')
        try:
            settings=Path('/etc/kwod-signer.json'); info=settings.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)&0o022: raise ValueError('wallet_config_protection')
            address=json.loads(settings.read_text())['address']
            if not isinstance(address,str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}',address) or int(address[2:],16)==0: raise ValueError('invalid_wallet_address')
            def rpc(method,params):
                response=client.post('https://mainnet.base.org',json={'jsonrpc':'2.0','id':1,'method':method,'params':params})
                if response.status_code!=200 or len(response.content)>65536: raise ValueError('rpc_failed')
                value=response.json()
                if value.get('id')!=1 or 'error' in value: raise ValueError('rpc_failed')
                return value['result']
            if quantity(rpc('eth_chainId',[]))!=8453: raise ValueError('wrong_chain')
            block=rpc('eth_blockNumber',[]); quantity(block)
            eth=quantity(rpc('eth_getBalance',[address,block]))
            usdc=quantity(rpc('eth_call',[{'to':USDC,'data':'0x70a08231'+address[2:].lower().zfill(64)},block]))
            success('wallet_base_eth','ETH',eth,18,'base_rpc_block_'+block)
            success('wallet_base_usdc','USDC',usdc,6,'base_rpc_block_'+block)
        except Exception:
            failure('wallet_base_eth','ETH','wallet_read_failed_or_not_configured')
            failure('wallet_base_usdc','USDC','wallet_read_failed_or_not_configured')
    return {'as_of':utcnow(),'assets':assets,'quality':'partial' if any(asset.get('error') for asset in assets) else 'confirmed','net_worth_eur_micro':None}


def absorb(store):
    """Agent runtime persists new trusted observations, without provider secrets."""
    snapshot=public_snapshot()
    from .accounting import import_observation
    for asset in snapshot['assets']:
        if asset.get('error') or asset.get('quality')!='confirmed' or asset.get('stale'): continue
        identity=asset['asset_id']+':'+asset['observed_at']
        existing=store.db.execute('SELECT 1 FROM evidence WHERE source=? AND external_id=?',('balance_observer',identity)).fetchone()
        if not existing:
            import_observation(store,{'source':'balance_observer','external_id':identity,'observed_at':asset['observed_at'],
                'asset_id':asset['asset_id'],'currency':asset['currency'],'amount_micro':asset['amount_micro'],'evidence':asset})
    return snapshot


def main():
    snapshot=collect(public_snapshot())
    atomic_write(HOME/'public.json',encode(snapshot),0o644)

if __name__=='__main__': main()
