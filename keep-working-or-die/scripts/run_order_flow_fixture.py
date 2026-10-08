"""Run the AP3 sample order entirely offline in a temporary directory."""
import json
from pathlib import Path
import tempfile

from kwod.order_flow import OrderFlow


def run():
    briefing = {'buyer': 'Fahrradwerkstatt Nord', 'deliverable': 'Abhol-FAQ',
                'audience': 'Kundschaft mit Reparaturauftrag', 'tone': 'klar und freundlich'}
    with tempfile.TemporaryDirectory(prefix='kwod-ap3-') as root:
        flow = OrderFlow(root)
        flow.receive_briefing(briefing)
        flow = OrderFlow(root)
        question = flow.state['question']
        flow.answer_clarification('deadline', 'innerhalb von 2 Werktagen')
        flow = OrderFlow(root); flow.create_draft()
        flow = OrderFlow(root); flow.review(accepted=False, change='Beispielkontakt als Platzhalter markieren')
        flow = OrderFlow(root); flow.revise()
        flow = OrderFlow(root); flow.review(accepted=True)
        flow = OrderFlow(root); flow.deliver()
        return {'offline_fixture': True, 'external_messages': 0, 'payments': 0,
                'question': question, 'stage': flow.state['stage'],
                'events': len(flow.state['events']),
                'artifacts': sorted(flow.state['artifacts'])}


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False))
