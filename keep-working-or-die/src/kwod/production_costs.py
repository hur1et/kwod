"""Produce a redacted, read-only production cost observation."""
from __future__ import annotations

from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .store import atomic_write, encode, utcnow

ARCHIVE_REF = re.compile(r'^[a-f0-9]{64}$')


def _micro_usd(value):
    if isinstance(value, bool):
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not decimal.is_finite() or decimal < 0:
        return None
    return int((decimal * 1_000_000).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def _archive_json(root: Path, ref: str | None):
    """Read a bounded structured result, never export its contents."""
    if not isinstance(ref, str) or not ARCHIVE_REF.fullmatch(ref):
        return None
    path = root / 'private' / 'archive' / ref
    try:
        info = path.lstat()
        if not path.is_file() or path.is_symlink() or info.st_size > 1_048_576:
            return None
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref:
            return None
        value = json.loads(raw)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, TypeError):
        return None


def _request_size(root: Path, ref: str | None):
    if not isinstance(ref, str) or not ARCHIVE_REF.fullmatch(ref):
        return None


def _review_usage():
    path=Path('/var/lib/kwod-safety/mail-review-usage.jsonl')
    rows=[]
    try:
        if path.stat().st_size>4_000_000: return rows
        for line in path.read_text(encoding='utf-8').splitlines()[-10000:]:
            value=json.loads(line)
            if isinstance(value,dict): rows.append(value)
    except (OSError,ValueError,TypeError):
        return []
    return rows
    path = root / 'private' / 'archive' / ref
    try:
        info = path.lstat()
        if not path.is_file() or path.is_symlink() or info.st_size > 1_048_576:
            return None
        return info.st_size
    except OSError:
        return None


def observe(root='/var/lib/kwod-production', *, ledger_path=None):
    root = Path(root)
    database = root / 'private' / 'state.sqlite'
    status_counts = Counter()
    completed = provider_cost_rows = missing_provider_cost = failed_before_response = 0
    provider_cost_micro = 0
    input_tokens = output_tokens = 0
    token_usage_rows = 0
    request_sizes = []
    tool_blocks = Counter()
    tool_block_categories = Counter()
    phase = {name:{'attempts':0,'cost_usd_micro':0,'responses_with_cost':0,'responses_without_cost':0,'input_tokens':0,'output_tokens':0}
             for name in ('planning','orientation_research','execution','communication','finance')}
    with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        for row in db.execute('SELECT id,status,usage_json,request_ref,response_ref FROM model_attempt'):
            status_counts[row['status']] += 1
            size = _request_size(root, row['request_ref'])
            if size is not None:
                request_sizes.append(size)
            usage = None
            try:
                usage = json.loads(row['usage_json']) if row['usage_json'] else None
            except (ValueError, TypeError):
                pass
            if row['status'] == 'completed':
                completed += 1
                cost = _micro_usd(usage.get('cost')) if isinstance(usage, dict) else None
                if cost is None:
                    missing_provider_cost += 1
                else:
                    provider_cost_rows += 1
                    provider_cost_micro += cost
            elif row['status'] in ('failed', 'refused', 'outcome_unknown'):
                failed_before_response += 1
            if isinstance(usage, dict):
                incoming, outgoing = usage.get('input_tokens'), usage.get('output_tokens')
                if type(incoming) is int and incoming >= 0 and type(outgoing) is int and outgoing >= 0:
                    token_usage_rows += 1
                    input_tokens += incoming
                    output_tokens += outgoing
            tools=[r[0] for r in db.execute('SELECT tool FROM tool_call WHERE attempt_id=?',(row['id'],))]
            if 'mail_send' in tools: phase_name='communication'
            elif 'browser_open' in tools: phase_name='orientation_research'
            elif any(t in tools for t in ('write_file','terminal','checkpoint')): phase_name='execution'
            elif 'observe_assets' in tools: phase_name='finance'
            elif any(t in tools for t in ('read_file','list_files','mail_list_unread','mail_read')): phase_name='orientation_research'
            else: phase_name='planning'
            bucket=phase[phase_name]; bucket['attempts']+=1
            if isinstance(usage,dict) and type(usage.get('input_tokens')) is int: bucket['input_tokens']+=usage['input_tokens']
            if isinstance(usage,dict) and type(usage.get('output_tokens')) is int: bucket['output_tokens']+=usage['output_tokens']
            cost=_micro_usd(usage.get('cost')) if isinstance(usage,dict) else None
            if cost is None: bucket['responses_without_cost']+=1
            else: bucket['responses_with_cost']+=1; bucket['cost_usd_micro']+=cost
        for row in db.execute("SELECT tool,result_ref FROM tool_call WHERE status IN ('completed','failed')"):
            result = _archive_json(root, row['result_ref'])
            if not result or result.get('error') != 'safety_guard':
                continue
            tool_blocks[row['tool']] += 1
            safety = result.get('safety')
            if isinstance(safety, dict) and isinstance(safety.get('category'), str):
                tool_block_categories[safety['category']] += 1
    ledger = Path(ledger_path) if ledger_path else root / 'private' / 'mail-outbound.sqlite'
    mail_statuses = Counter()
    try:
        with closing(sqlite3.connect(ledger.as_uri() + '?mode=ro', uri=True)) as db:
            for row in db.execute('SELECT status FROM outbound'):
                mail_statuses[row[0]] += 1
    except (OSError, sqlite3.Error):
        pass
    reviewer=_review_usage()
    reviewer_cost=sum(x['cost_usd_micro'] for x in reviewer if type(x.get('cost_usd_micro')) is int)
    reviewer_cost_rows=sum(type(x.get('cost_usd_micro')) is int for x in reviewer)
    reviewer_inputs=sum(x['input_tokens'] for x in reviewer if type(x.get('input_tokens')) is int)
    reviewer_outputs=sum(x['output_tokens'] for x in reviewer if type(x.get('output_tokens')) is int)
    return {
        'as_of': utcnow(),
        'currency': 'USD',
        'model_attempts': dict(sorted(status_counts.items())),
        'completed_responses': completed,
        'openrouter_cost_usd_micro': provider_cost_micro if provider_cost_rows else None,
        'responses_with_openrouter_cost': provider_cost_rows,
        'responses_without_openrouter_cost': missing_provider_cost,
        'attempts_without_confirmed_response_cost': failed_before_response,
        'token_usage': {'responses': token_usage_rows, 'input_tokens': input_tokens, 'output_tokens': output_tokens},
        'cost_by_phase': phase,
        'request_payload_bytes': {'count': len(request_sizes), 'total': sum(request_sizes),
                                  'average': sum(request_sizes) // len(request_sizes) if request_sizes else None,
                                  'maximum': max(request_sizes) if request_sizes else None},
        'safety_guard_blocks': {'by_tool': dict(sorted(tool_blocks.items())),
                                'by_category': dict(sorted(tool_block_categories.items()))},
        'mail': {'outbound_by_status': dict(sorted(mail_statuses.items())),
                 'review_candidates': sum(count for status, count in mail_statuses.items() if status != 'rate_limited'),
                 'review_usage_records':len(reviewer),'review_responses_with_cost':reviewer_cost_rows,
                 'review_cost_usd_micro':reviewer_cost if reviewer_cost_rows else None,
                 'review_responses_without_cost':len(reviewer)-reviewer_cost_rows,
                 'review_input_tokens':reviewer_inputs,'review_output_tokens':reviewer_outputs},
        'notes': ['OpenRouter response costs are reported only when returned with a completed response.',
                  'Unknown or interrupted attempts are not treated as free.',
                  'Request payload bytes are a size indicator, not a token count or a cost estimate.',
                  'Mail review usage is recorded as billing metadata without message text; historical records before this observer remain unknown.'],
    }


def write_public(root='/var/lib/kwod-production', output=None):
    root = Path(root)
    output = Path(output) if output else root / 'public' / 'costs.json'
    value = observe(root)
    atomic_write(output, encode(value), 0o644)
    return value
