"""Loopback-only AP1 preview with temporary fixtures; zero provider/network calls."""
import argparse
import json
from pathlib import Path
import tempfile

import uvicorn
from fastapi.responses import HTMLResponse

from kwod.api import create_app
from kwod.projection import project
from kwod.provider import FixtureProvider
from kwod.runtime import initialize
from kwod.store import Store
from kwod.work_monitor import RUNS, collect
from kwod.work_trial import run


def response(number, *calls):
    return {'id': 'preview-' + str(number), 'status': 'completed', 'usage': None,
            'output': [{'type': 'function_call', 'call_id': 'call-' + str(i), 'name': name,
                        'arguments': json.dumps(args)} for i, (name, args) in enumerate(calls)]}


def preview(base):
    main = Store(base / 'main')
    initialize(main, 'Offline monitor preview')
    project(main)
    main.close()
    run(base / RUNS['trial01'][0], FixtureProvider([response(i, ('write_file',
        {'path': 'note.md', 'content': 'Fixture'})) for i in range(6)]))
    run(base / RUNS['pilot02'][0], FixtureProvider([
        response(0, ('write_file', {'path': 'works/entscheidung.md', 'content': 'Fixture'}),
                    ('write_file', {'path': 'works/arbeitsprobe.md', 'content': 'Fixture'}),
                    ('write_file', {'path': 'works/angebot.md', 'content': 'Fixture'}),
                    ('checkpoint', {'memory': 'Fixture handoff'})),
        response(1, ('write_file', {'path': 'works/pruefung.md', 'content': 'Fixture'})),
        response(2)]), profile='earning')
    app = create_app(base / 'main/public/public.sqlite')
    # Override only the preview's GET routes. Production uses the saved collector.
    app.router.routes = [r for r in app.router.routes if getattr(r, 'path', None) not in ('/', '/api/v1/work-runs')]

    @app.get('/', response_class=HTMLResponse)
    def page():
        html = (Path(__file__).parents[1] / 'src/kwod/static/index.html').read_text(encoding='utf-8')
        return html.replace('<body><main>', '<body><main><p style="border:2px solid;padding:12px">OFFLINE-PRÜFVORSCHAU · simulierte Läufe · keine echten Kontodaten</p>')

    @app.get('/api/v1/work-runs')
    def runs():
        return {**collect(base, lambda _: 'inactive'), 'stale': False}

    return app


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='kwod-ap1-preview-') as directory:
        uvicorn.run(preview(Path(directory)), host='127.0.0.1', port=args.port)
