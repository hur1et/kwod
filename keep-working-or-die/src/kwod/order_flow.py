"""Durable, local AP3 sample-order workflow.

The fixture models the control flow around a delivery. It does not call a model,
send a message, or imply that the generated sample is customer work.
"""
from datetime import datetime, timezone
import json
from pathlib import Path

from .store import atomic_write

STAGES = ('briefing_received', 'clarification_needed', 'clarification_received',
          'draft_ready', 'review_ready', 'revision_needed', 'delivered')
REQUIRED_BRIEFING = ('buyer', 'deliverable', 'audience', 'tone')


def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


class OrderFlow:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / 'order-flow.json'
        if self.state_path.exists():
            self.state = json.loads(self.state_path.read_text(encoding='utf-8'))
        else:
            self.state = {'version': 1, 'stage': 'new', 'briefing': {}, 'answers': {},
                          'revision': None, 'events': [], 'artifacts': {}}

    def save(self):
        atomic_write(self.state_path, json.dumps(self.state, ensure_ascii=False, indent=2).encode('utf-8'))

    def event(self, kind, detail=None):
        self.state['events'].append({'at': now(), 'kind': kind, 'detail': detail or {}})

    def _advance(self, stage):
        if self.state['stage'] == stage:
            return False
        self.state['stage'] = stage
        self.event('stage_changed', {'stage': stage})
        return True

    def receive_briefing(self, briefing):
        if self.state['stage'] not in ('new', 'briefing_received', 'clarification_needed'):
            return self.state
        if not isinstance(briefing, dict) or any(not isinstance(briefing.get(k), str) or not briefing[k].strip()
                                                 for k in REQUIRED_BRIEFING):
            raise ValueError('briefing_requires_buyer_deliverable_audience_tone')
        self.state['briefing'] = {k: briefing[k].strip() for k in REQUIRED_BRIEFING}
        self._advance('briefing_received')
        if 'deadline' not in briefing or not str(briefing.get('deadline', '')).strip():
            self.state['question'] = 'Welche Frist soll auf dem Entwurf stehen?'
            self.event('clarification_requested', {'field': 'deadline'})
            self._advance('clarification_needed')
        self.save()
        return self.state

    def answer_clarification(self, field, value):
        if self.state['stage'] != 'clarification_needed' or field != 'deadline' or not isinstance(value, str) or not value.strip():
            raise ValueError('unexpected_clarification')
        self.state['answers'][field] = value.strip()
        self.state.pop('question', None)
        self.event('clarification_received', {'field': field})
        self._advance('clarification_received')
        self.save()
        return self.state

    def create_draft(self):
        if self.state['stage'] not in ('clarification_received', 'draft_ready'):
            raise ValueError('draft_requires_clarification')
        content = (f"# {self.state['briefing']['deliverable']}\n\n"
                   f"Zielgruppe: {self.state['briefing']['audience']}\n"
                   f"Ton: {self.state['briefing']['tone']}\n"
                   f"Frist: {self.state['answers']['deadline']}\n\n"
                   "## Musterlieferung\n\nDies ist ein lokaler AP3-Fixture-Entwurf.\n")
        path = self.root / 'draft.md'
        if not path.exists():
            atomic_write(path, content.encode('utf-8'))
            self.state['artifacts']['draft'] = 'draft.md'
            self.event('draft_created', {'artifact': 'draft.md'})
        self._advance('draft_ready')
        self.save()
        return self.state

    def review(self, *, accepted=False, change=None):
        if self.state['stage'] not in ('draft_ready', 'review_ready', 'revision_needed'):
            raise ValueError('review_requires_draft')
        if accepted:
            self.event('review_accepted', {'criteria': ['audience', 'tone', 'deadline']})
            self._advance('review_ready')
        else:
            if not isinstance(change, str) or not change.strip():
                raise ValueError('revision_request_required')
            self.state['revision'] = change.strip()
            self.event('revision_requested', {'change': self.state['revision']})
            self._advance('revision_needed')
        self.save()
        return self.state

    def revise(self):
        if self.state['stage'] != 'revision_needed':
            raise ValueError('revision_requires_review_request')
        text = self.root / 'draft.md'
        existing = text.read_text(encoding='utf-8')
        marker = f"\n\nÄnderung umgesetzt: {self.state['revision']}\n"
        if marker not in existing:
            atomic_write(text, (existing.rstrip() + marker).encode('utf-8'))
            self.event('draft_revised', {'artifact': 'draft.md'})
        self.state['revision'] = None
        self._advance('review_ready')
        self.save()
        return self.state

    def deliver(self):
        if self.state['stage'] != 'review_ready':
            raise ValueError('delivery_requires_accepted_review')
        delivery = self.root / 'delivery.md'
        if not delivery.exists():
            atomic_write(delivery, self.root.joinpath('draft.md').read_bytes())
            self.state['artifacts']['delivery'] = 'delivery.md'
            self.event('delivery_created', {'artifact': 'delivery.md'})
        self._advance('delivered')
        self.save()
        return self.state
