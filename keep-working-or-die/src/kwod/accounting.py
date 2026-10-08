"""Observation only. Never authorizes or blocks inference."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def estimate_cost(usage, tariff):
    """Return currency micro-units. Requires explicit, verified category semantics.

    tariff rates: micro-units per token (same numeric value as currency/M tokens).
    cache_writes_in_input must be verified for the selected API/tariff.
    """
    if usage is None or not tariff or tariff.get('verified') is not True:
        return None
    try:
        total, output = usage['input_tokens'], usage['output_tokens']
        details = usage.get('input_tokens_details') or {}
        cached = details['cached_tokens']
        field = tariff['cache_write_field']
        writes = details.get(field, 0 if tariff.get('missing_writes_means_zero') is True else None)
        if any(type(x) is not int or x < 0 for x in (total, output, cached, writes)):
            return None
        if tariff.get('cache_writes_in_input') is not True:
            return None
        uncached = total - cached - writes
        if uncached < 0 or total > tariff['max_input_tokens']:
            return None
        rates = [Decimal(str(tariff[k])) for k in ('input', 'cached', 'cache_write', 'output')]
        if any(not r.is_finite() or r < 0 for r in rates):
            return None
        cost = sum(r * n for r, n in zip(rates, (uncached, cached, writes, output)))
        # Reasoning is already included in output_tokens.
        return int(cost.quantize(Decimal(1), rounding=ROUND_HALF_UP))
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return None


def import_observation(store, value):
    """Import operator-supplied evidence. Corrections require a new external ID."""
    import uuid
    from .store import utcnow
    from .tools import parse_time
    required = {'source', 'external_id', 'observed_at', 'asset_id', 'currency', 'amount_micro', 'evidence'}
    if set(value) != required or type(value['amount_micro']) is not int:
        raise ValueError('invalid observation')
    for key in ('source', 'external_id', 'asset_id'):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 200:
            raise ValueError(key)
    if value['currency'] not in ('EUR', 'USD', 'ETH', 'USDC'):
        raise ValueError('unsupported currency; explicit valuation required')
    when = parse_time(value['observed_at']).isoformat().replace('+00:00', 'Z')
    if when > utcnow() or not value['evidence']:
        raise ValueError('past timestamp and evidence required')
    ref = store.archive.put(value)
    with store.transaction():
        existing = store.db.execute('SELECT * FROM evidence WHERE source=? AND external_id=?',
                                    (value['source'], value['external_id'])).fetchone()
        if existing:
            if existing['sha256'] != ref:
                raise ValueError('external ID reused with different content')
            return existing['id']
        identity = uuid.uuid4().hex
        store.db.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?)',
                         (identity, value['source'], when, ref, ref, value['external_id']))
        store.db.execute('INSERT INTO asset_observation VALUES (?,?,?,?,?,?,?,?)',
                         (identity, store.instance_id, value['asset_id'], when, value['currency'],
                          value['amount_micro'], identity, 'confirmed'))
        store.event('observation_imported', {'evidence_id': identity, 'source_ref': ref})
    return identity


def observations(store):
    return [dict(row) for row in store.db.execute('''SELECT asset_id,observed_at,currency,
        amount_micro,quality FROM asset_observation a WHERE rowid=(SELECT rowid
        FROM asset_observation b WHERE b.asset_id=a.asset_id
        ORDER BY observed_at DESC,rowid DESC LIMIT 1) ORDER BY asset_id''')]


def reconcile_snapshot(amount_micro, as_of, currency, consumption):
    """Only usage after the balance cutoff is subtracted; purchases are not usage.

    Currency conversion and overlapping/unknown consumption remain unknown.
    Account aggregate costs must never be passed alongside the same per-call costs.
    """
    from .tools import parse_time
    total, cutoff, changed = amount_micro, parse_time(as_of), False
    for item in consumption:
        start, end = parse_time(item['started_at']), parse_time(item['ended_at'])
        if end <= cutoff:
            continue
        if start < cutoff or item['amount_micro'] is None or item['currency'] != currency:
            return {'amount_micro': None, 'quality': 'unknown', 'unreconciled': True}
        total -= item['amount_micro']
        changed = True
    return {'amount_micro': total, 'quality': 'estimated' if changed else 'confirmed',
            'unreconciled': False}


def register_tariff(store, value):
    """Operator attests provider category mapping; no tariff is activated by default."""
    import json
    from .tools import parse_time
    required = {'id', 'valid_from', 'currency', 'source_url', 'tariff'}
    if set(value) != required or value['currency'] not in ('EUR', 'USD'):
        raise ValueError('invalid tariff record')
    tariff = value['tariff']
    for key in ('verified', 'input', 'cached', 'cache_write', 'output', 'cache_write_field',
                'cache_writes_in_input', 'max_input_tokens', 'mapping_evidence'):
        if key not in tariff:
            raise ValueError('missing tariff field: ' + key)
    if not tariff['mapping_evidence'] or not value['source_url'].startswith('https://'):
        raise ValueError('source and mapping evidence required')
    sample = {'input_tokens': 0, 'output_tokens': 0,
              'input_tokens_details': {'cached_tokens': 0, tariff['cache_write_field']: 0}}
    if estimate_cost(sample, tariff) != 0:
        raise ValueError('unsupported tariff category semantics')
    when = parse_time(value['valid_from']).isoformat().replace('+00:00', 'Z')
    with store.transaction():
        store.db.execute('INSERT INTO price_version VALUES (?,?,?,?,?)',
                         (value['id'], when, value['currency'], value['source_url'], json.dumps(tariff)))
        store.event('tariff_registered', value)


def reconcile_account(store, asset_id):
    """Private development report in the asset's original currency; never a gate."""
    found = [x for x in observations(store) if x['asset_id'] == asset_id]
    if not found:
        return {'amount_micro': None, 'quality': 'unknown', 'unreconciled': True}
    asset = found[0]
    attempts = store.db.execute('SELECT * FROM model_attempt WHERE status!=?', ('prepared',)).fetchall()
    consumption = []
    from .store import utcnow
    for item in attempts:
        consumption.append({'started_at': item['started_at'], 'ended_at': item['ended_at'] or utcnow(),
                            'amount_micro': item['estimated_cost_micro'], 'currency': item['cost_currency']})
    return {**reconcile_snapshot(asset['amount_micro'], asset['observed_at'], asset['currency'], consumption),
            'asset_id': asset_id, 'currency': asset['currency'], 'balance_as_of': asset['observed_at']}


def import_financial_event(store, value):
    """Append a documented transaction. Authoritative asset snapshots set balances.

    This journal never independently debits balances, so an already reflected
    purchase, invoice or fee cannot be deducted twice. No birth/inheritance here.
    """
    import uuid
    from .tools import parse_time
    from .store import utcnow
    required = {'source', 'external_id', 'occurred_at', 'kind', 'source_asset', 'target_asset',
                'amount_micro', 'currency', 'eur_value_micro', 'fx_decimal', 'corrects_id', 'evidence'}
    if set(value) != required or value['kind'] not in ('transfer', 'expense', 'income', 'fee', 'correction'):
        raise ValueError('invalid transaction; birth is unavailable')
    if type(value['amount_micro']) is not int or value['amount_micro'] < 0:
        raise ValueError('nonnegative integer micro-units required')
    if value['currency'] not in ('EUR', 'USD') or not value['evidence']:
        raise ValueError('currency and evidence required')
    for key in ('source', 'external_id'):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 200:
            raise ValueError(key)
    for key in ('source_asset', 'target_asset', 'corrects_id'):
        if value[key] is not None and (not isinstance(value[key], str) or not value[key]):
            raise ValueError(key)
    if value['kind'] == 'transfer' and (not value['source_asset'] or not value['target_asset'] or value['source_asset'] == value['target_asset']):
        raise ValueError('transfer requires two distinct assets')
    if (value['kind'] == 'correction') != bool(value['corrects_id']):
        raise ValueError('correction must reference its original transaction')
    if value['eur_value_micro'] is not None and (type(value['eur_value_micro']) is not int or value['eur_value_micro'] < 0):
        raise ValueError('invalid EUR valuation')
    if value['fx_decimal'] is not None:
        if not isinstance(value['fx_decimal'], str):
            raise ValueError('FX must be decimal text')
        rate = Decimal(value['fx_decimal'])
        if not rate.is_finite() or rate <= 0:
            raise ValueError('invalid FX')
    when = parse_time(value['occurred_at']).isoformat().replace('+00:00', 'Z')
    if when > utcnow():
        raise ValueError('future transaction')
    ref = store.archive.put(value)
    with store.transaction():
        existing = store.db.execute('SELECT f.id,e.sha256 FROM financial_event f JOIN evidence e ON e.id=f.evidence_id WHERE f.source=? AND f.external_id=?',
                                    (value['source'], value['external_id'])).fetchone()
        if existing:
            if existing['sha256'] != ref:
                raise ValueError('external ID conflict; append a correction')
            return existing['id']
        identity = uuid.uuid4().hex
        store.db.execute('INSERT INTO evidence VALUES (?,?,?,?,?,?)',
                         (identity, value['source'], when, ref, ref, 'transaction:' + value['external_id']))
        store.db.execute('INSERT INTO financial_event VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                         (identity, store.instance_id, when, value['kind'], value['source_asset'], value['target_asset'],
                          value['amount_micro'], value['currency'], value['eur_value_micro'], value['fx_decimal'],
                          identity, value['source'], value['external_id'], value['corrects_id']))
        store.event('financial_event_imported', {'financial_event_id': identity, 'evidence_ref': ref})
    return identity
