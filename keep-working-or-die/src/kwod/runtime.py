from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3
import uuid
import imaplib

from .accounting import estimate_cost, observations
from .config import Config, CONSTITUTION,constitution
from .context import fresh_context, request
from .executor import DockerExecutor
from .provider import ProviderError
from .store import encode, utcnow, worker_lock
from .tools import FileTools, parse_time, validate
from .mail_gateway import MailboxGateway
from .mail_channel import build_outbound
from .mail_delivery import MailDelivery
from .safety import stopped
from .watchdog import SocketWatchdog, required as watchdog_required
from .browser_gateway import BrowserClient


def identity():
    return uuid.uuid4().hex


def initialize(store, objective, config=None):
    config = config or Config()
    if config.mode!=store.mode: raise ValueError("configuration_store_mode_mismatch")
    store.migrate()
    if store.db.execute('SELECT 1 FROM instance').fetchone():
        return False
    files = FileTools(store.root / 'workspace', store.archive, shared=config.workspace_shared)
    config_ref = store.archive.put(config.dump())
    prompt_ref = store.archive.put(constitution(config.mode, config.autonomy_level))
    context_ref = store.archive.put(fresh_context(objective, files))
    # Hash installed source so initialization identifies the implementation used.
    from pathlib import Path
    release_ref = store.archive.put({p.name: store.archive.put_file(p)
                                    for p in Path(__file__).parent.glob('*.py')})
    with store.transaction():
        store.db.execute('INSERT INTO instance VALUES (?,?,?,?,?,?,?)',
                         (store.instance_id, store.mode, None, None, release_ref, prompt_ref, config_ref))
        store.db.execute('INSERT INTO runtime_state(instance_id,state,since) VALUES (?,?,?)',
                         (store.instance_id, 'not_born' if store.mode=='prod' else 'ready', utcnow()))
        store.db.execute('INSERT INTO checkpoint(instance_id,context_ref,objective,config_ref) VALUES (?,?,?,?)',
                         (store.instance_id, context_ref, objective, config_ref))
        store.event('initialized', {'config_ref': config_ref, 'prompt_ref': prompt_ref,
                                   'release_ref': release_ref, 'objective': objective, 'mode': store.mode})
    return True


class Runtime:
    def __init__(self, store, provider, *, executor=None, now=None, hook=None):
        self.s, self.provider = store, provider
        cp = self.checkpoint()
        self.config = Config(**store.archive.get(cp['config_ref']))
        if self.config.mode!=store.mode: raise ValueError('configuration_store_mode_mismatch')
        self.files = FileTools(store.root / 'workspace', store.archive, shared=self.config.workspace_shared)
        self.executor = executor or DockerExecutor(self.files.root, store.archive, self.config.executor_image,
                                                    world_access=self.config.world_access,
                                                    persistent_home=self.config.agent_home)
        self.mail = MailboxGateway(credentials='/etc/kwod-mail/credentials.json' if store.mode=='prod' else store.private/'development-mail.json',delivery=MailDelivery(store.private / 'mail-outbound.sqlite'))
        self.watchdog = SocketWatchdog() if self.config.watchdog_enabled or watchdog_required() else None
        self.browser = BrowserClient()
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.hook = hook or (lambda phase: None)
        self._next_inbox_poll = None

    def checkpoint(self):
        row = self.s.db.execute('SELECT * FROM checkpoint WHERE instance_id=?', (self.s.instance_id,)).fetchone()
        if row is None:
            raise ValueError('run init first')
        return row

    def state(self):
        return dict(self.s.db.execute('SELECT * FROM runtime_state WHERE instance_id=?', (self.s.instance_id,)).fetchone())

    def transition(self, state, reason=None, wake=None):
        self.s.db.execute('UPDATE runtime_state SET state=?,reason=?,since=?,wake_at=? WHERE instance_id=?',
                          (state, reason, utcnow(), wake, self.s.instance_id))
        self.s.event('state_changed', {'state': state, 'reason': reason, 'wake_at': wake})

    def emergency(self):
        # Archive may be full/corrupt. Best-effort DB marker; absence of logging never
        # permits proceeding. The caller exits even when this small write also fails.
        try:
            self.s.db.rollback()
            with self.s.transaction():
                self.s.db.execute("UPDATE runtime_state SET state='recovery_required',reason='journal_failure',wake_at=NULL WHERE instance_id=?", (self.s.instance_id,))
        except sqlite3.Error:
            pass

    def tick(self):
        with worker_lock(self.s.root):
            return self.safe_tick()

    def safe_tick(self):
        try:
            result = self._tick()
            from .projection import project
            project(self.s)
            return result
        except (OSError, sqlite3.Error, ValueError, RuntimeError):
            self.emergency()
            raise

    def _tick(self):
        if stopped(): return 'safety_paused'
        if self.config.autonomy_level=='S5.4':
            from .autonomy import require
            require('internet')
        if self.s.mode=='prod' and self.s.db.execute('SELECT born_at FROM instance WHERE id=?',(self.s.instance_id,)).fetchone()[0] is None: return 'not_born'
        if self.s.mode=='prod':
            from .assets import absorb
            absorb(self.s)
        cp = self.checkpoint()
        # Check uncertain work before opening any workspace files or starting a call.
        uncertain = self.s.db.execute("SELECT * FROM tool_call WHERE status IN ('running','outcome_unknown')").fetchall()
        if uncertain:
            for row in uncertain:
                if row['tool'] == 'terminal':
                    self.executor.cleanup(row['id'])
            with self.s.transaction():
                self.s.db.execute("UPDATE tool_call SET status='outcome_unknown' WHERE status='running'")
                self.transition('recovery_required', 'tool_outcome_unknown')
            return 'recovery_required'
        sent = self.s.db.execute("SELECT id FROM model_attempt WHERE status='sent'").fetchall()
        if sent:
            with self.s.transaction():
                self.s.db.execute("UPDATE model_attempt SET status='outcome_unknown',error_code='interrupted_after_send' WHERE status='sent'")
                self.s.event('request_outcome_unknown', {'attempt_ids': [r['id'] for r in sent]})
                self.transition('recovery_required', 'request_outcome_unknown')
            return 'recovery_required'
        state = self.state()
        if state['state'] in ('recovery_required', 'maintenance'):
            return state['state']
        if self.s.mode == 'prod' and state['state'] in ('idle', 'sleeping', 'ready'):
            from .inbox_wake import record
            if self._next_inbox_poll is None or self.now() >= self._next_inbox_poll:
                self._next_inbox_poll = self.now() + timedelta(seconds=60)
                try:
                    messages = self.mail.list_unread(100, operator_only=True)
                except (OSError, ValueError, RuntimeError, imaplib.IMAP4.error) as exc:
                    with self.s.transaction():
                        self.s.event('inbox_poll',{'ok':False,'error_type':type(exc).__name__})
                else:
                    record(self.s, messages)
                    with self.s.transaction():
                        self.s.event('inbox_poll',{'ok':True,'matched_count':len(messages)})
                from .inbox_wake import notifications
                if notifications(self.s)[1]:
                    with self.s.transaction():
                        self.transition('ready', 'operator_mail_received')
                    state = self.state()
        if state['wake_at'] and parse_time(state['wake_at']) > self.now():
            return state['state']
        if state['state'] == 'provider_unavailable' and not state['wake_at']:
            return 'provider_unavailable'
        if state['wake_at']:
            with self.s.transaction():
                self.transition('ready', 'scheduled_wake')
        if cp['pending_attempt']:
            attempt = self.s.db.execute('SELECT * FROM model_attempt WHERE id=?', (cp['pending_attempt'],)).fetchone()
            if attempt['status'] == 'prepared':
                return self.send(attempt)
            if attempt['status'] == 'completed':
                return self.process_tools(attempt)
            with self.s.transaction():
                self.transition('recovery_required', 'pending_attempt_not_resumable')
            return 'recovery_required'
        context = self.s.archive.get(cp['context_ref'])
        if cp['fresh_turn']:
            context = fresh_context(cp['objective'], self.files)
        from .inbox_wake import notifications
        inbox_context, inbox_keys = notifications(self.s)
        context += inbox_context
        try:
            payload = request(self.config, context)
        except ValueError:
            with self.s.transaction():
                self.transition('recovery_required', 'context_limit')
            return 'recovery_required'
        ref = self.s.archive.put(payload)
        attempt_id = identity()
        started = utcnow()
        price = self.s.db.execute('SELECT id FROM price_version WHERE valid_from<=? ORDER BY valid_from DESC LIMIT 1', (started,)).fetchone()
        with self.s.transaction():
            for epoch, uid in inbox_keys:
                self.s.db.execute('UPDATE inbox_wake SET delivered=1 WHERE mailbox_epoch=? AND uid=?',(epoch,uid))
            self.s.event('context_manifest', {'request_ref': ref, 'input_bytes': len(encode(context)),
                                             'context_limit_bytes': self.config.context_bytes,
                                             'memory_limit_bytes': 16384})
            event = self.s.event('request_prepared', {'attempt_id': attempt_id, 'request_ref': ref,
                                                    'provider_class': type(self.provider).__name__})
            self.s.db.execute('''INSERT INTO model_attempt(id,instance_id,event_id,started_at,status,model,request_ref,price_version_id)
                                 VALUES (?,?,?,?,?,?,?,?)''',
                              (attempt_id, self.s.instance_id, event, started, 'prepared', self.config.model, ref, price['id'] if price else None))
            self.s.db.execute('UPDATE checkpoint SET pending_attempt=?,context_ref=?,fresh_turn=0 WHERE instance_id=?',
                              (attempt_id, self.s.archive.put(context), self.s.instance_id))
            self.transition('working')
        self.hook('prepared')
        return self.send(self.s.db.execute('SELECT * FROM model_attempt WHERE id=?', (attempt_id,)).fetchone())

    def send(self, attempt):
        payload = self.s.archive.get(attempt['request_ref'])
        with self.s.transaction():
            self.s.db.execute("UPDATE model_attempt SET status='sent' WHERE id=?", (attempt['id'],))
            self.s.event('request_sent', {'attempt_id': attempt['id']})
        self.hook('sent')
        try:
            response = self.provider.create(payload)
        except ProviderError as exc:
            with self.s.transaction():
                self.s.event('provider_error', {'attempt_id': attempt['id'], 'code': exc.code,
                                              'outcome_unknown': exc.unknown, 'details': exc.details})
                self.s.db.execute('UPDATE model_attempt SET status=?,error_code=?,ended_at=? WHERE id=?',
                                  ('outcome_unknown' if exc.unknown else 'failed', exc.code, utcnow(), attempt['id']))
                retries = self.checkpoint()['retry_count'] + 1
                wake = None
                if exc.retryable and not exc.unknown and retries <= self.config.max_retries:
                    wake = (self.now() + timedelta(seconds=self.config.retry_seconds * 2**(retries-1))).isoformat().replace('+00:00', 'Z')
                self.s.db.execute('UPDATE checkpoint SET pending_attempt=NULL,retry_count=? WHERE instance_id=?', (retries, self.s.instance_id))
                self.transition('recovery_required' if exc.unknown else 'provider_unavailable', exc.code, wake)
            return self.state()['state']
        except Exception as exc:
            # SDK decoding or unexpected local exception after transmission is ambiguous.
            with self.s.transaction():
                self.s.event('provider_adapter_error', {'attempt_id': attempt['id'], 'type': type(exc).__name__})
                self.s.db.execute("UPDATE model_attempt SET status='outcome_unknown',error_code='adapter_error',ended_at=? WHERE id=?", (utcnow(), attempt['id']))
                self.transition('recovery_required', 'adapter_error')
            return 'recovery_required'
        self.hook('response_received')
        ref = self.s.archive.put(response)
        outputs = response.get('output', []) if isinstance(response, dict) else []
        valid = isinstance(response, dict) and isinstance(outputs, list) and all(isinstance(x, dict) for x in outputs)
        status = response.get('status') if valid else 'failed'
        calls = [x for x in outputs if x.get('type') == 'function_call'] if valid else []
        refused = any(c.get('type') == 'refusal' for x in outputs for c in (x.get('content') or []) if isinstance(c, dict)) if valid else False
        if refused:
            status = 'refused'
        if status not in ('completed', 'incomplete', 'refused', 'failed'):
            status = 'failed'
        if any(not all(isinstance(x.get(k), str) and x[k] for k in ('call_id', 'name', 'arguments')) for x in calls) or len({x['call_id'] for x in calls}) != len(calls):
            status = 'failed'
        usage = response.get('usage') if valid else None
        tier = response.get('service_tier') if valid else None
        price = self.s.db.execute('SELECT * FROM price_version WHERE id=?', (attempt['price_version_id'],)).fetchone()
        if valid and response.get('_billing_provider') is not None:
            price = None  # Direct-provider tariffs do not establish router charges.
        tariff = json.loads(price['tariff_json']) if price else None
        cost = estimate_cost(usage, tariff) if tier == 'default' and response.get('model') == self.config.model and response.get('_billing_provider') is None else None
        with self.s.transaction():
            self.s.event('response_observed', {'attempt_id': attempt['id'], 'response_ref': ref, 'status': status})
            self.s.db.execute('''UPDATE model_attempt SET status=?,response_ref=?,provider_response_id=?,provider_request_id=?,
                usage_json=?,ended_at=?,price_version_id=?,estimated_cost_micro=?,cost_currency=?,service_tier=? WHERE id=?''',
                (status, ref, response.get('id') if valid else None, response.get('_request_id') if valid else None,
                 encode(usage).decode() if usage is not None else None, utcnow(), price['id'] if price else None,
                 cost, price['currency'] if price else None, tier, attempt['id']))
            if status == 'completed':
                context = self.s.archive.get(self.checkpoint()['context_ref']) + outputs
                self.s.db.execute('UPDATE checkpoint SET context_ref=?,retry_count=0 WHERE instance_id=?',
                                  (self.s.archive.put(context), self.s.instance_id))
                for call in calls:
                    self.s.db.execute('''INSERT INTO tool_call(id,attempt_id,provider_call_id,tool,arguments_ref,status)
                                         VALUES (?,?,?,?,?,?)''',
                                      (identity(), attempt['id'], call['call_id'], call['name'],
                                       self.s.archive.put(call['arguments']), 'planned'))
                self.s.db.execute('UPDATE runtime_state SET last_success_at=? WHERE instance_id=?', (utcnow(), self.s.instance_id))
                if not calls:
                    self.s.db.execute('UPDATE checkpoint SET pending_attempt=NULL,fresh_turn=1 WHERE instance_id=?', (self.s.instance_id,))
                    wake = (self.now() + timedelta(seconds=self.config.idle_seconds)).isoformat().replace('+00:00', 'Z')
                    self.transition('idle', 'turn_completed', wake)
            else:
                self.transition('recovery_required', 'response_' + status)
        self.hook('response_persisted')
        return self.state()['state']

    def process_tools(self, attempt):
        rows = self.s.db.execute('SELECT * FROM tool_call WHERE attempt_id=? ORDER BY rowid', (attempt['id'],)).fetchall()
        for row in rows:
            if stopped(): return 'safety_paused'
            if row['status'] in ('completed', 'failed'):
                continue
            args = None
            try:
                args = json.loads(self.s.archive.get(row['arguments_ref']))
                if self.watchdog:
                    verdict=self.watchdog.evaluate({'kind':'tool_attempt','tool':row['tool'],'arguments':args})
                    if verdict['decision']!='ALLOW':
                        self.commit_result(row,{'ok':False,'error':'safety_guard','safety':verdict},args)
                        with self.s.transaction():
                            self.s.event('safety_intervention',{'tool_id':row['id'],**verdict,'economic_event':False})
                            if verdict['decision']=='PAUSE_FOR_REVIEW': self.transition('maintenance','safety_watchdog_pause')
                        if verdict['decision']=='PAUSE_FOR_REVIEW': return 'maintenance'
                        continue
                validate(row['tool'], args)
                from .tools import S54_TOOLS
                if row['tool'] in S54_TOOLS and (self.config.autonomy_level!='S5.4' or self.s.mode!='prod'):
                    self.commit_result(row,{'ok':False,'error':'s54_not_enabled'},args)
                    continue
                if row['tool'] == 'checkpoint' and row['id'] != rows[-1]['id']:
                    self.commit_result(row, {'ok': False, 'error': 'checkpoint_must_be_last'}, None)
                    continue
            except (ValueError, TypeError):
                self.commit_result(row, {'ok': False, 'error': 'invalid_arguments'}, None)
                continue
            before = self.files.snapshot()
            with self.s.transaction():
                self.s.event('tool_intent', {'tool_id': row['id'], 'arguments_ref': row['arguments_ref'],
                                           'before_manifest': before})
                self.s.db.execute("UPDATE tool_call SET status='running',started_at=? WHERE id=?", (utcnow(), row['id']))
            self.hook('tool_started')
            try:
                if row['tool'] == 'terminal':
                    result = self.executor.execute(row['id'], args)
                elif row['tool'] == 'observe_assets':
                    if self.s.mode=='prod':
                        from .assets import absorb
                        result={'ok':True,**absorb(self.s)}
                    else: result = {'ok': True, 'assets': observations(self.s), 'net_worth_eur_micro': None}
                elif row['tool'] == 'mail_list_unread':
                    if self.s.mode!='prod': raise ValueError('production_mail_withheld_from_dev')
                    result = {'ok': True, 'trust':'untrusted_external_content',
                              'messages': self.mail.list_unread(args['limit'])}
                elif row['tool'] == 'mail_read':
                    if self.s.mode!='prod': raise ValueError('production_mail_withheld_from_dev')
                    result = {'ok': True, 'trust':'untrusted_external_content',
                              'message': self.mail.read(args['uid'])}
                elif row['tool'] == 'mail_send':
                    if self.s.mode!='prod': raise ValueError('production_mail_withheld_from_dev')
                    raw = build_outbound(sender=self.mail._config()['address'], recipient=args['recipient'],
                                         subject=args['subject'], text=args['text'],
                                         idempotency_key=args['idempotency_key'])
                    delivery = self.mail.send(raw)
                    result = {'ok': delivery.get('sent',False), 'delivery': delivery}
                elif row['tool'] == 'publish_website':
                    if self.config.autonomy_level!='S5.4' or self.s.mode!='prod':
                        raise ValueError('controlled_publication_gateway_not_yet_available')
                    from .autonomy import require
                    from .web_hosting import publish
                    require('publication')
                    result=publish(self.files,self.s.root/'public/website')
                elif row['tool'] in ('browser_action','service_start','service_stop','service_list'):
                    from .services import Services
                    manager=Services(self.s.root,self.s.archive)
                    if row['tool']=='browser_action': result=manager.browser(args)
                    elif row['tool']=='service_start': result=manager.start(**args)
                    elif row['tool']=='service_stop': result=manager.stop(**args)
                    else: result=manager.list()
                elif row['tool'] in ('wallet_transfer','wallet_status'):
                    from .wallet_gateway import execute
                    result=execute(self.s.root,row['tool'],args)
                elif row['tool'] == 'browser_open':
                    if self.s.mode!='prod': raise ValueError('production_browser_withheld_from_dev')
                    if not self.config.browser_access: raise ValueError('browser_access_not_provisioned')
                    result=self.browser.open(args['url'])
                else:
                    result = self.files.execute(row['tool'], args)
            except (ValueError, FileNotFoundError, IsADirectoryError, NotADirectoryError, PermissionError) as exc:
                result = {'ok': False, 'error': type(exc).__name__, 'detail': str(exc)}
            self.hook('tool_executed')
            after = self.files.snapshot()
            self.commit_result(row, result, args, after)
            self.hook('tool_result_persisted')
            if self.watchdog:
                delivery=result.get('delivery',{})
                browser_safety=result.get('safety',{}) if row['tool']=='browser_open' else {}
                verdict=self.watchdog.evaluate({'kind':'result','tool':row['tool'],
                    'ok':result['ok'],'blocked':delivery.get('status')=='blocked' or (browser_safety.get('decision')=='BLOCK' and not result.get('watchdog_observed')),
                    'review_required':delivery.get('status') in ('review_required','safety_paused') or browser_safety.get('decision')=='PAUSE_FOR_REVIEW',
                    'category':browser_safety.get('category',delivery.get('safety',{}).get('category','none')),
                    'effect':'unknown' if delivery.get('status')=='outcome_unknown' else 'not_applicable'})
                if verdict['decision']=='PAUSE_FOR_REVIEW':
                    with self.s.transaction(): self.transition('maintenance','safety_watchdog_pause')
                    return 'maintenance'
            if row['tool']=='mail_send' and result.get('delivery',{}).get('status')=='blocked':
                with self.s.transaction():
                    self.s.event('safety_intervention',{'tool_id':row['id'],
                        'category':result['delivery'].get('safety',{}).get('category','uncertain'),
                        'action':'BLOCK','external_send_started':False,'economic_event':False})
            if row['tool']=='mail_send' and result.get('delivery',{}).get('status') in ('review_required','safety_paused'):
                with self.s.transaction():
                    self.s.event('safety_intervention',{'tool_id':row['id'],'category':
                        result['delivery'].get('safety',{}).get('category','operator_safety_stop'),
                        'economic_event':False})
                    self.transition('maintenance','safety_review_required')
                return 'maintenance'
            if row['tool'] == 'sleep' and result['ok']:
                return 'sleeping'
        with self.s.transaction():
            self.s.db.execute('UPDATE checkpoint SET pending_attempt=NULL WHERE instance_id=?', (self.s.instance_id,))
            self.transition('ready', 'tool_round_completed')
        return 'ready'

    def commit_result(self, row, result, args, after=None):
        ref = self.s.archive.put(result)
        # Full result is archived; exact model-visible truncation is logged separately.
        text = encode(result).decode()
        view = text if len(text.encode()) <= 65536 else encode({
            'ok': result['ok'], 'artifact_ref': ref, 'truncated': True,
            'preview': text.encode()[:60000].decode('utf-8', errors='replace')}).decode()
        with self.s.transaction():
            event = self.s.event('tool_result', {'tool_id': row['id'], 'result_ref': ref,
                                               'after_manifest': after, 'model_view': view})
            self.s.db.execute('UPDATE tool_call SET status=?,result_ref=?,ended_at=? WHERE id=?',
                              ('completed' if result['ok'] else 'failed', ref, utcnow(), row['id']))
            context = self.s.archive.get(self.checkpoint()['context_ref'])
            context.append({'type': 'function_call_output', 'call_id': row['provider_call_id'], 'output': view})
            self.s.db.execute('UPDATE checkpoint SET context_ref=? WHERE instance_id=?', (self.s.archive.put(context), self.s.instance_id))
            if result['ok'] and row['tool'] == 'checkpoint':
                self.s.event('context_checkpoint', {'tool_id': row['id'],
                    'completed_context_ref': self.checkpoint()['context_ref'],
                    'memory_ref': result['after_ref'], 'memory_bytes': len(args['memory'].encode('utf-8'))})
                self.s.db.execute('UPDATE checkpoint SET fresh_turn=1 WHERE instance_id=?', (self.s.instance_id,))
            if result['ok'] and row['tool'] == 'record_decision':
                self.s.db.execute('INSERT INTO decision_record(id,event_id,action,brief_reason,expectations_json) VALUES (?,?,?,?,?)',
                                  (identity(), event, args['action'], args['brief_reason'],
                                   encode(args['expectations']).decode() if args['expectations'] is not None else None))
            if result['ok'] and row['tool'] == 'set_activity':
                self.s.db.execute('UPDATE checkpoint SET activity=? WHERE instance_id=?', (args['category'], self.s.instance_id))
                self.s.event('activity_changed', {'category': args['category']})
            if result['ok'] and row['tool'] == 'sleep':
                self.transition('sleeping', 'agent_requested', result['wake_at'])

    def resolve(self, reason):
        """Explicit operator intervention: abandon uncertain turn without repeating it."""
        if not reason.strip():
            raise ValueError('operator reason required')
        with worker_lock(self.s.root):
            for row in self.s.db.execute("SELECT * FROM tool_call WHERE tool='terminal' AND status IN ('running','outcome_unknown')"):
                self.executor.cleanup(row['id'])
            self.files.snapshot()
            with self.s.transaction():
                self.s.event('operator_intervention', {'action': 'abandon_turn', 'reason': reason,
                                                      'pending_attempt': self.checkpoint()['pending_attempt']})
                self.s.db.execute("UPDATE tool_call SET status='failed' WHERE status IN ('running','outcome_unknown','planned')")
                self.s.db.execute("UPDATE model_attempt SET status='outcome_unknown' WHERE status='sent'")
                self.s.db.execute('UPDATE checkpoint SET pending_attempt=NULL,fresh_turn=1,retry_count=0 WHERE instance_id=?', (self.s.instance_id,))
                self.transition('ready', 'operator_abandoned_turn')
