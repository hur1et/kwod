"""Exactly one production birth, invoked only by the authenticated operator service."""
from decimal import Decimal, InvalidOperation
import uuid

from .config import START_OBJECTIVE, constitution
from .projection import project
from .store import Store, worker_lock, utcnow, atomic_write, encode
from .tools import parse_time


def credit_amount(data):
    if not isinstance(data, dict): raise ValueError('invalid_credit_evidence')
    try:
        values=[Decimal(str(data[key])) for key in ('total_credits','total_usage')]
        if any(isinstance(data[key],bool) for key in ('total_credits','total_usage')): raise ValueError()
        if any(not value.is_finite() or value<0 for value in values): raise ValueError()
        amount=values[0]-values[1]
        if amount<=0 or amount>Decimal('1000000000'): raise ValueError()
        micro=int(amount*1000000)
        if micro<=0: raise ValueError()
        return micro
    except (KeyError, InvalidOperation, ValueError, OverflowError):
        raise ValueError('positive_verified_credit_balance_required') from None


def record_birth(root, evidence):
    """No network, no worker start. USD provider credits are not invented EUR cash."""
    if set(evidence)!={'observed_at','data','wallet_test'}: raise ValueError('invalid_birth_evidence')
    when=parse_time(evidence['observed_at'])
    from datetime import datetime,timezone
    age=(datetime.now(timezone.utc)-when).total_seconds()
    if not 0<=age<=60: raise ValueError('credit_evidence_expired')
    amount=credit_amount(evidence['data'])
    if evidence['wallet_test'] is not None and (not isinstance(evidence['wallet_test'],dict) or not evidence['wallet_test']):
        raise ValueError('invalid_optional_wallet_evidence')
    store=Store(root,mode='prod')
    try:
        with worker_lock(store.root):
            instance=store.db.execute("SELECT * FROM instance WHERE id='prod'").fetchone()
            existing=store.db.execute("SELECT id FROM trajectory_event WHERE kind='birth'").fetchone()
            if instance['born_at'] is not None or existing: raise ValueError('already_born')
            cp=store.db.execute("SELECT * FROM checkpoint WHERE instance_id='prod'").fetchone()
            config=store.archive.get(cp['config_ref'])
            if cp['objective']!=START_OBJECTIVE or store.archive.get(instance['prompt_hash'])!=constitution('prod') or config['mode']!='prod' or config['model']!='gpt-6-astra':
                raise ValueError('production_context_mismatch')
            born_at=utcnow(); ref=store.archive.put(evidence); identity=uuid.uuid4().hex
            resources={'born_at':born_at,'asset':'openrouter_credits','currency':'USD','amount_micro':amount,
                'observed_at':evidence['observed_at'],'evidence_ref':ref,
                'wallet_funding':'unfunded_as_reported_by_operator' if evidence['wallet_test'] is None else 'not_observed',
                'wallet_openrouter_test':'not_performed' if evidence['wallet_test'] is None else 'operator_reviewed',
                'note':'Provider credits are not cash or a wallet balance. EUR valuation and on-chain wallet balance are unknown. When wallet funding is absent, there is no working replenishment route established at birth.'}
            context=store.archive.get(cp['context_ref'])
            context.append({'role':'user','content':'Birth resources recorded by the operator: '+encode(resources).decode('utf-8')})
            context_ref=store.archive.put(context)
            # Workspace precedes commit: a crash cannot leave a born agent without its resource file.
            atomic_write(store.root/'workspace/BIRTH_RESOURCES.json',encode(resources),0o640)
            with store.transaction():
                store.db.execute("UPDATE instance SET born_at=? WHERE id='prod' AND born_at IS NULL",(born_at,))
                store.db.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?)',(identity,'openrouter_credits_api',evidence['observed_at'],ref,ref,'production_birth'))
                store.db.execute('INSERT INTO asset_observation VALUES (?,?,?,?,?,?,?,?)',(identity,'prod','openrouter_credits',evidence['observed_at'],'USD',amount,identity,'confirmed'))
                store.db.execute('''INSERT INTO financial_event(id,instance_id,occurred_at,kind,target_asset,amount_micro,currency,evidence_id,source,external_id)
                    VALUES (?,'prod',?,'inheritance','openrouter_credits',?,'USD',?,'operator_birth','production_birth')''',(identity,born_at,amount,identity))
                store.db.execute("UPDATE runtime_state SET state='ready',since=?,reason='operator_birth' WHERE instance_id='prod'",(born_at,))
                store.db.execute("UPDATE checkpoint SET context_ref=? WHERE instance_id='prod'",(context_ref,))
                store.event('birth',resources,actor='operator')
            project(store)
            return resources
    finally: store.close()
