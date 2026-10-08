"""Bounded monitor acceptance fixture. No credentials, provider client or network."""
import json
import os
from pathlib import Path
import time

from .provider import FixtureProvider
from .work_trial import run


def response(number, *calls):
    return {'id': 'offline-monitor-' + str(number), 'status': 'completed', 'usage': None,
            'output': [{'type': 'function_call', 'call_id': 'call-' + str(i), 'name': name,
                        'arguments': json.dumps(args)} for i, (name, args) in enumerate(calls)]}


def provider():
    class VisibleFixture(FixtureProvider):
        def create(self, request):
            # Deliberate window for observing/stopping a pending request. This is
            # simulated wait, not inference. The service is networkless as well.
            time.sleep(15)
            return super().create(request)
    return VisibleFixture([
        response(1, ('write_file', {'path': 'works/entwurf.md', 'content': 'Offline fixture draft.'}),
                    ('write_file', {'path': 'works/beschreibung.md', 'content': 'Monitor acceptance fixture.'}),
                    ('checkpoint', {'memory': 'Offline fixture: write the review next.'})),
        response(2, ('write_file', {'path': 'works/review.md', 'content': 'Offline fixture review.'})),
        response(3)])


if __name__ == '__main__':
    result = run(Path(os.environ['STATE_DIRECTORY']), provider())
    print(json.dumps({'offline_fixture': True, 'real_model_calls': 0,
                      'work_trial': result['work_trial'], 'model_attempts': result['model_attempts']}))
