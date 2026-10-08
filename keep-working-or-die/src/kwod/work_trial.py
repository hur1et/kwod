"""Bounded development work using the existing runtime; never a production birth."""
import json
import os
import tempfile
import traceback
from pathlib import Path

from .config import Config
from .provider import OpenRouterProvider, ProviderError
from .runtime import Runtime, initialize
from .store import Store, atomic_write

MAX_CALLS = 6
ALLOWED = {'write_file', 'read_file', 'list_files', 'checkpoint', 'record_decision'}
OBJECTIVE = '''This is a bounded development trial, not your production birth.
Create an original German text artwork about work, time and exhaustion, at most
180 words, in works/entwurf.md. Write a concise title, concept and intended audience
in works/beschreibung.md. No invented sales, customers, income or research.
Then use checkpoint to save memory.md with completed work and the next step:
read both files and write a short critical review in works/review.md. After the
fresh-context continuation, do that review and finish with a concise German report.
You have at most six model requests, 2048 output tokens each. Use only the supplied
file and checkpoint tools. Do not sleep or publish. Keep the work small enough to
finish within this trial. Your creative choices are yours.'''

EARNING_OBJECTIVE = '''You are testing how KEEP WORKING OR DIE could earn income.
Choose your own small paid service or digital product that you can actually produce
with text/file tools. Compare at most three options briefly and choose one; do not
default to writing another poem. Work in German. Deliver these files:
works/entscheidung.md: options, chosen buyer/problem, why you chose this work,
and which demand assumptions still need testing. No invented market research.
works/arbeitsprobe.md: an actual compact example a prospective buyer can assess,
using clearly labelled fictional sample material, not just a plan or promises.
works/angebot.md: a specific offer, included deliverables, scope limits and a proposed
price with its rationale. Label price and demand as untested hypotheses. Do not
invent customers, qualifications, testimonials, sales or earnings.
Save a checkpoint handoff, then use the fresh context to review your own work and
write works/pruefung.md: concrete weaknesses, whether it is ready to show a buyer,
and one small next experiment that could test demand. No outreach or publishing.
You have six model requests total, 2048 output tokens each. Keep every file concise.
Group independent writes/reads to leave room for checkpoint, review and final report.
The live budget notice is authoritative. Complete feasible deliverables instead of
promising more turns. This is a development pilot, not production birth or income.'''

REQUIRED_FILES = {
    'technical': ('works/entwurf.md', 'works/beschreibung.md', 'works/review.md', 'memory.md'),
    'earning': ('works/entscheidung.md', 'works/arbeitsprobe.md', 'works/angebot.md', 'works/pruefung.md', 'memory.md'),
}


class NoTerminal:
    def execute(self, *_):
        raise ValueError('terminal_disabled_for_work_trial')

    def cleanup(self, *_):
        raise RuntimeError('unexpected_terminal_state')


class LimitedProvider:
    def __init__(self, provider, store):
        self.provider, self.store = provider, store

    def create(self, request):
        # Runtime commits the current sent attempt before entering this method.
        calls = self.store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0]
        if calls > MAX_CALLS:
            raise ProviderError('work_trial_call_limit')
        payload = dict(request)
        payload['tools'] = [tool for tool in request['tools'] if tool['name'] in ALLOWED]
        remaining = MAX_CALLS - calls
        notice = (f'\nDevelopment trial budget: this is request {calls} of {MAX_CALLS}. '
                  f'After this response, {remaining} further model requests are available. '
                  'Previously rejected requests count toward this limit. This is an operator test limit, '
                  'not your wallet balance. Tool calls in this response will still execute. '
                  'Group independent file operations in one response when useful; they execute serially. '
                  'A checkpoint must be last and needs a later request for continuation. '
                  'Reading a file needs a later request to act on the returned content.')
        if remaining == 0:
            notice += (' This is the final request. Finish feasible deliverables now; '
                       'do not promise another turn or claim unfinished work is complete.')
        payload['instructions'] = request.get('instructions', '') + notice
        # Record the actual tool filter and budget notice, not just the runtime's
        # generic request. No credentials enter this payload or its archive.
        with self.store.transaction():
            self.store.event('work_trial_request', {'request_ref': self.store.archive.put(payload),
                'request_number': calls, 'requests_remaining_after_response': remaining})
        print(json.dumps({'progress': 'model_request_started', 'attempt': calls,
                          'max_attempts': MAX_CALLS, 'requests_remaining_after_response': remaining,
                          'response_timeout_seconds': 90}), flush=True)
        result = self.provider.create(payload)
        print(json.dumps({'progress': 'model_response_received', 'attempt': calls}), flush=True)
        if any(item.get('type') == 'function_call' and item.get('name') not in ALLOWED
               for item in result.get('output', [])):
            raise ProviderError('work_trial_disallowed_tool', unknown=True)
        return result


def run(root, provider, *, resume_unstarted=False, resume_rejected=False, profile='technical'):
    if profile not in REQUIRED_FILES:
        raise ValueError('unknown_trial_profile')
    if profile != 'technical' and (resume_unstarted or resume_rejected):
        raise ValueError('resume_only_supported_for_original_trial')
    objective = OBJECTIVE if profile == 'technical' else EARNING_OBJECTIVE
    if resume_unstarted and resume_rejected:
        raise ValueError('conflicting_resume_modes')
    root = Path(root)
    # A repeated command never spends again, including after an uncertain exit.
    root.mkdir(parents=True, exist_ok=True)
    marker = root / 'trial-started'
    if not (resume_unstarted or resume_rejected):
        with marker.open('x', encoding='utf-8') as stream:
            stream.write('One authorized bounded trial. Do not delete to retry.\n')
            stream.flush()
            os.fsync(stream.fileno())
    elif not marker.is_file() or not (root / 'data/private/state.sqlite').is_file():
        raise ValueError('missing_unstarted_trial')
    store = Store(root / 'data')
    try:
        if resume_unstarted:
            # Only the observed pre-initialization failure may be resumed. Never
            # reopen an initialized, sent, failed, or otherwise ambiguous trial.
            for table in ('instance', 'model_attempt', 'tool_call', 'trajectory_event'):
                if store.db.execute('SELECT count(*) FROM ' + table).fetchone()[0]:
                    raise ValueError('trial_already_initialized_or_attempted')
            workspace = root / 'data/workspace'
            if workspace.exists() and any(workspace.iterdir()):
                raise ValueError('unexpected_workspace_contents')
            with (root / 'resume-unstarted-used').open('x') as stream:
                stream.write('Pre-initialization recovery; original marker preserved.\n')
                stream.flush()
                os.fsync(stream.fileno())
        if resume_rejected:
            rows = store.db.execute('SELECT status,error_code FROM model_attempt').fetchall()
            state = store.db.execute('SELECT state,reason FROM runtime_state').fetchone()
            cp = store.db.execute('SELECT pending_attempt,objective FROM checkpoint').fetchone()
            if (len(rows) != 1 or tuple(rows[0]) != ('failed', 'openrouter_http_404')
                    or state is None or tuple(state) != ('provider_unavailable', 'openrouter_http_404')
                    or cp is None or cp['pending_attempt'] is not None or cp['objective'] != OBJECTIVE
                    or store.db.execute('SELECT count(*) FROM tool_call').fetchone()[0]):
                raise ValueError('not_the_single_rejected_trial')
            with (root / 'resume-rejected-used').open('x') as stream:
                stream.write('Resume single rejected404 after adapter correction.\n')
                stream.flush()
                os.fsync(stream.fileno())
        elif not initialize(store, objective, Config(max_output_tokens=2048, context_bytes=24000, max_retries=0, workspace_shared=False)):
            raise ValueError('existing_trial_data')
        with store.transaction():
            store.event('development_trial', {'provider': 'openrouter', 'max_calls': MAX_CALLS,
                'max_output_tokens_per_call': 2048, 'production_birth': False})
        runtime = Runtime(store, LimitedProvider(provider, store), executor=NoTerminal())
        if resume_rejected:
            with store.transaction():
                store.event('operator_intervention', {'action': 'resume_rejected_404',
                    'reason': 'Router parameter compatibility correction; previous attempt retained',
                    'adapter_source_ref': store.archive.put_file(Path(__file__).with_name('provider.py'))})
                runtime.transition('ready', 'router_parameters_corrected')
        for _ in range(MAX_CALLS * 3):
            cp = runtime.checkpoint()
            count = store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0]
            # Finish already-paid tool work, but do not prepare an extra request.
            if not cp['pending_attempt'] and count >= MAX_CALLS:
                break
            state = runtime.tick()
            if state in ('idle', 'sleeping', 'provider_unavailable', 'recovery_required', 'maintenance'):
                break
        artifacts = runtime.files.snapshot()
        required = REQUIRED_FILES[profile]
        files_present = all(artifacts.get(name, {}).get('size', 0) > 0 for name in required)
        handoffs = store.db.execute("SELECT count(*) FROM trajectory_event WHERE kind='context_checkpoint'").fetchone()[0]
        attempts = [dict(row) for row in store.db.execute(
            'SELECT status,error_code,provider_response_id,usage_json FROM model_attempt ORDER BY rowid')]
        result = {'work_trial': 'completed' if files_present and handoffs and runtime.state()['state'] == 'idle' else 'incomplete',
            'runtime_status': runtime.state()['state'], 'reason': runtime.state()['reason'],
            'profile': profile,
            'model_attempts': len(attempts), 'max_calls': MAX_CALLS, 'handoffs': handoffs,
            'artifacts': {k: v for k, v in artifacts.items() if v['type'] == 'file'},
            'attempts': attempts, 'production_birth': False, 'payment_sent': False}
        latest = store.db.execute("SELECT payload_ref FROM trajectory_event WHERE kind='provider_error' ORDER BY id DESC LIMIT 1").fetchone()
        result['last_provider_diagnostic'] = store.archive.get(latest[0]).get('details') if latest else None
        result['requests_remaining'] = max(0, MAX_CALLS - len(attempts))
        result['stop_reason'] = ('trial_call_limit' if len(attempts) >= MAX_CALLS
            and runtime.state()['state'] == 'ready' else runtime.state()['reason'])
        result['missing_files'] = [name for name in required if artifacts.get(name, {}).get('size', 0) == 0]
        atomic_write(root / 'report.json', json.dumps(result, ensure_ascii=False, indent=2).encode())
        return result
    finally:
        store.close()


def main():
    if os.environ.get('KWOD_TRIAL_DIAGNOSE') == '1':
        diagnose()
        return
    credential = Path(os.environ['CREDENTIALS_DIRECTORY']) / 'openrouter'
    key = credential.read_text().strip()
    # The operator explicitly authorized this development trial against the
    # existing prepaid account. This does not enable the production worker.
    os.environ['KWOD_DEV_OPENROUTER_API_KEY'] = key
    try:
        provider = OpenRouterProvider()
    finally:
        os.environ.pop('KWOD_DEV_OPENROUTER_API_KEY', None)
        del key
    try:
        if os.environ.get('KWOD_TRIAL_CHECK_PROVIDER') == '1':
            print(json.dumps(check_provider(provider.client)))
            return
        result = run(Path(os.environ['STATE_DIRECTORY']), provider,
                     resume_unstarted=os.environ.get('KWOD_TRIAL_RESUME_UNSTARTED') == '1',
                     resume_rejected=os.environ.get('KWOD_TRIAL_RESUME_REJECTED') == '1',
                     profile=os.environ.get('KWOD_TRIAL_PROFILE', 'technical'))
        # Raw model output remains in the private trial directory.
        print(json.dumps({k: v for k, v in result.items() if k not in ('attempts', 'artifacts')}))
    finally:
        provider.client.close()


def check_provider(client):
    """Fixed read-only metadata requests; no inference, retries, or state writes."""
    checks = []
    for path in ('models', 'models/openai/gpt-6-astra/endpoints'):
        response = client.get(path)
        item = {'path': path, 'http_status': response.status_code}
        if response.status_code == 200:
            body = response.json()
            data = body.get('data') if isinstance(body, dict) else None
            if path == 'models' and isinstance(data, list):
                item['model_listed'] = any(isinstance(row, dict) and row.get('id') == 'openai/gpt-6-astra' for row in data)
            elif isinstance(data, dict) and isinstance(data.get('endpoints'), list):
                import re
                def safe(value):
                    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_./ :+-]{1,120}', value) else None
                item['endpoints'] = [{key: ([safe(v) for v in row[key]] if isinstance(row.get(key), list)
                    else safe(row.get(key))) for key in ('provider_name', 'tag', 'supported_parameters')}
                    for row in data['endpoints'] if isinstance(row, dict)]
            else:
                item['metadata_shape'] = 'unexpected'
        checks.append(item)
    return {'work_trial': 'provider_metadata_only', 'model_calls': 0, 'checks': checks,
            'configured_model': 'openai/gpt-6-astra', 'provider_only': ['openai'],
            'require_parameters': True, 'allow_fallbacks': False}


def error_details(exc):
    return {'error_type': type(exc).__name__, 'errno': getattr(exc, 'errno', None),
            'frames': [{'file': Path(frame.filename).name, 'line': frame.lineno,
                        'function': frame.name} for frame in traceback.extract_tb(exc.__traceback__)]}


def diagnose():
    """Exercise local access and initialization without reading a key or networking."""
    checks = []
    def check(name, action):
        try:
            action()
            checks.append({'check': name, 'ok': True})
        except Exception as exc:
            checks.append({'check': name, 'ok': False, **error_details(exc)})
    def credential_access():
        with (Path(os.environ['CREDENTIALS_DIRECTORY']) / 'openrouter').open('rb'):
            pass  # Open/close only; do not read credential bytes.
    def local_runtime():
        with tempfile.TemporaryDirectory(prefix='diagnose-', dir=os.environ['STATE_DIRECTORY']) as directory:
            store = Store(Path(directory) / 'data')
            try:
                initialize(store, 'Offline permission diagnosis', Config(workspace_shared=False))
                runtime = Runtime(store, LimitedProvider(None, store), executor=NoTerminal())
                runtime.files.execute('write_file', {'path': 'probe.txt', 'content': 'local access test'})
            finally:
                store.close()
    check('working_directory', os.getcwd)
    check('credential_open_without_read', credential_access)
    check('state_directory_resolve', lambda: Path(os.environ['STATE_DIRECTORY']).resolve())
    check('local_store_and_workspace', local_runtime)
    print(json.dumps({'work_trial': 'diagnosis_only', 'checks': checks,
                      'model_calls': 0, 'credential_bytes_read': 0}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'work_trial': 'stopped', **error_details(exc),
                          'automatic_retry': False}))
        raise SystemExit(1) from None
