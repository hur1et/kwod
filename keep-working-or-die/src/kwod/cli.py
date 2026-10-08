import argparse
import json
from pathlib import Path
import signal
import threading

from .accounting import import_financial_event, import_observation, register_tariff, reconcile_account
from .backup import backup, restore
from .config import Config
from .projection import project
from .provider import FixtureProvider, OpenAIProvider, OpenRouterProvider, ProviderError
from .runtime import initialize, Runtime
from .store import Store, worker_lock


def load_fixture(path, skip=0):
    rows = json.loads(Path(path).read_text(encoding='utf-8'))
    results = []
    for row in rows[skip:]:
        if 'fixture_error' in row:
            results.append(ProviderError(**row['fixture_error']))
        else:
            results.append(row)
    return FixtureProvider(results)


def main(argv=None):
    parser = argparse.ArgumentParser(description='KEEP WORKING OR DIE — isolated dev/prod instances')
    parser.add_argument('--mode',choices=('dev','prod'),default='dev')
    parser.add_argument('--data', type=Path, default=Path('../kwod-development-data'))
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init')
    init.add_argument('--objective', default='Organize your workspace and record a short development note.')
    init.add_argument('--executor-image', default=None)
    run = commands.add_parser('run')
    providers = run.add_mutually_exclusive_group(required=True)
    providers.add_argument('--fixture', type=Path)
    providers.add_argument('--openai-dev', action='store_true')
    providers.add_argument('--openrouter-dev', action='store_true')
    providers.add_argument('--openrouter-prod', action='store_true')
    run.add_argument('--steps', type=int, default=1)
    run.add_argument('--forever', action='store_true')
    run.add_argument('--poll-seconds', type=float, default=1)
    commands.add_parser('inspect')
    commands.add_parser('project')
    resolve = commands.add_parser('resolve')
    resolve.add_argument('--reason', required=True)
    imp = commands.add_parser('import-observation')
    imp.add_argument('file', type=Path)
    transaction = commands.add_parser('import-transaction')
    transaction.add_argument('file', type=Path)
    price = commands.add_parser('import-tariff')
    price.add_argument('file', type=Path)
    report = commands.add_parser('reconcile')
    report.add_argument('--asset-id', required=True)
    cost_report = commands.add_parser('cost-report')
    cost_report.add_argument('--trial-observation', type=Path, required=True)
    cost_report.add_argument('--pilot-observation', type=Path, required=True)
    b = commands.add_parser('backup')
    b.add_argument('destination', type=Path)
    r = commands.add_parser('restore')
    r.add_argument('source', type=Path)
    server = commands.add_parser('serve')
    server.add_argument('--public-db', required=True, type=Path)
    server.add_argument('--port', type=int, default=8000)
    server.add_argument('--safety-file',type=Path)
    args = parser.parse_args(argv)
    if args.command == 'serve':
        import uvicorn
        from .api import create_app
        uvicorn.run(create_app(args.public_db,safety_file=args.safety_file), host='127.0.0.1', port=args.port)
        return
    if args.command == 'cost-report':
        from .cost_report import summarize
        print(json.dumps(summarize(json.loads(args.trial_observation.read_text(encoding='utf-8')),
                                   json.loads(args.pilot_observation.read_text(encoding='utf-8'))), indent=2))
        return
    if args.mode=='prod' and args.data==Path('../kwod-development-data'): parser.error('production requires explicit separate --data')
    if args.command == 'restore':
        print(restore(args.source, args.data,mode=args.mode))
        return
    store = Store(args.data,mode=args.mode)
    try:
        if args.command == 'init':
            with worker_lock(store.root):
                if args.mode=='prod': parser.error('use Prepare-Production to persist the reviewed start context')
                created = initialize(store, args.objective, Config(executor_image=args.executor_image,mode=args.mode))
                project(store)
            print('Development initialized' if created else 'Already initialized; preserved existing state')
        elif args.command == 'inspect':
            print(json.dumps(dict(store.db.execute('SELECT * FROM runtime_state').fetchone()), indent=2))
            print('Private attempts:', store.db.execute('SELECT count(*) FROM model_attempt').fetchone()[0])
        elif args.command == 'backup':
            print(backup(store, args.destination))
        elif args.command == 'project':
            with worker_lock(store.root):
                project(store)
        elif args.command == 'import-observation':
            with worker_lock(store.root):
                print(import_observation(store, json.loads(args.file.read_text(encoding='utf-8'))))
        elif args.command == 'import-tariff':
            with worker_lock(store.root):
                register_tariff(store, json.loads(args.file.read_text(encoding='utf-8')))
        elif args.command == 'import-transaction':
            with worker_lock(store.root):
                print(import_financial_event(store, json.loads(args.file.read_text(encoding='utf-8'))))
        elif args.command == 'reconcile':
            print(json.dumps(reconcile_account(store, args.asset_id), indent=2))
        elif args.command == 'resolve':
            Runtime(store, FixtureProvider([])).resolve(args.reason)
            project(store)
        elif args.command == 'run':
            if bool(args.openrouter_prod)!=(args.mode=='prod'): parser.error('production runs require --mode prod --openrouter-prod; dev providers cannot run production')
            if args.mode=='prod':
                instance=store.db.execute('SELECT born_at FROM instance WHERE id=?',(store.instance_id,)).fetchone()
                if not instance or instance[0] is None: parser.error('production is not born; worker start withheld')
            if args.steps < 1 or not 0.05 <= args.poll_seconds <= 10:
                parser.error('steps must be positive and poll-seconds between 0.05 and 10')
            stop = threading.Event()
            for sig in (signal.SIGINT, signal.SIGTERM):
                signal.signal(sig, lambda *_: stop.set())
            with worker_lock(store.root):
                from .store import encode
                import hashlib
                binding = {'provider': 'openrouter-production' if args.openrouter_prod else ('fixture' if args.fixture else ('openrouter-development' if args.openrouter_dev else 'openai-development')),
                           'fixture_sha256': hashlib.sha256(args.fixture.read_bytes()).hexdigest() if args.fixture else None}
                previous = store.db.execute("SELECT payload_ref FROM trajectory_event WHERE kind='provider_bound' ORDER BY id LIMIT 1").fetchone()
                if previous and store.archive.get(previous['payload_ref']) != binding:
                    raise ValueError('provider or fixture changed; use a separate development data directory')
                if not previous:
                    with store.transaction():
                        store.event('provider_bound', binding)
                skipped = store.db.execute("SELECT count(*) FROM model_attempt WHERE status!='prepared'").fetchone()[0]
                from .provider import ProductionOpenRouterProvider
                provider = ProductionOpenRouterProvider() if args.openrouter_prod else (load_fixture(args.fixture, skipped) if args.fixture else (OpenRouterProvider() if args.openrouter_dev else OpenAIProvider()))
                runtime = Runtime(store, provider)
                index = 0
                while not stop.is_set() and (args.forever or index < args.steps):
                    state = runtime.safe_tick()
                    index += 1
                    if state in ('recovery_required', 'maintenance') or (state == 'provider_unavailable' and not runtime.state()['wake_at']):
                        print(state)
                        break
                    if args.forever or index < args.steps:
                        stop.wait(args.poll_seconds)
                print(json.dumps(runtime.state(), indent=2))
    finally:
        store.close()


if __name__ == '__main__':
    main()
