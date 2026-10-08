"""Combine observed run costs without creating accounting debits."""
from decimal import Decimal, InvalidOperation


def _usd(value):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError('invalid USD amount') from None
    if not amount.is_finite() or amount < 0:
        raise ValueError('invalid USD amount')
    return amount.quantize(Decimal('0.01'))


def summarize(trial, pilot, *, provider_usage=None):
    """Return an auditable report from supplied observations.

    ``provider_usage`` is deliberately optional: absent or non-per-attempt usage
    remains unknown. This function never writes a Store, ledger, or balance.
    """
    required_trial = {'trial', 'reported_total_decimal', 'successful_model_attempts',
                      'rejected_model_attempts', 'source', 'verification'}
    required_pilot = {'reported_balance_before', 'reported_balance_after',
                      'successful_model_attempts', 'source', 'verification',
                      'attribution_condition'}
    if not required_trial <= set(trial) or not required_pilot <= set(pilot):
        raise ValueError('incomplete cost observation')
    trial_cost = _usd(trial['reported_total_decimal'])
    before, after = _usd(pilot['reported_balance_before']), _usd(pilot['reported_balance_after'])
    derived = (before - after).quantize(Decimal('0.01'))
    if derived < 0:
        raise ValueError('balance increased; cannot derive consumption')
    report = {
        'currency': 'USD',
        'runs': [
            {'id': trial['trial'], 'cost': f'{trial_cost:.2f}',
             'successful_attempts': trial['successful_model_attempts'],
             'rejected_attempts': trial['rejected_model_attempts'],
             'cost_source': trial['source'], 'verification': trial['verification'],
             'per_attempt_cost': None},
            {'id': 'pilot02', 'cost': f'{derived:.2f}',
             'successful_attempts': pilot['successful_model_attempts'],
             'rejected_attempts': None, 'cost_source': pilot['source'],
             'verification': pilot['verification'],
             'attribution_condition': pilot['attribution_condition'],
             'per_attempt_cost': None},
        ],
        'combined_observed_cost': f'{(trial_cost + derived):.2f}',
        'account_balance_after_pilot': f'{after:.2f}',
        'provider_usage': provider_usage if provider_usage is not None else {
            'status': 'unknown', 'reason': 'no independently retrieved per-attempt usage'
        },
        'eur_conversion': None,
        'ledger_debit_created': False,
        'double_debit_protection': 'balance delta is an observation; no ledger debit is created',
    }
    return report
