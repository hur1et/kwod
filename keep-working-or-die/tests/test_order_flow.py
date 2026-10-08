import json
from pathlib import Path
import tempfile
import unittest

from kwod.order_flow import OrderFlow


class OrderFlowTests(unittest.TestCase):
    briefing = {'buyer': 'Fahrradwerkstatt Nord', 'deliverable': 'Abhol-FAQ',
                'audience': 'Kundschaft mit Reparaturauftrag', 'tone': 'klar und freundlich'}

    def test_missing_fact_question_draft_review_revision_delivery(self):
        with tempfile.TemporaryDirectory() as temp:
            flow = OrderFlow(temp)
            self.assertEqual(flow.receive_briefing(self.briefing)['stage'], 'clarification_needed')
            self.assertEqual(flow.state['question'], 'Welche Frist soll auf dem Entwurf stehen?')
            self.assertEqual(flow.answer_clarification('deadline', 'innerhalb von 2 Werktagen')['stage'], 'clarification_received')
            self.assertEqual(flow.create_draft()['stage'], 'draft_ready')
            self.assertEqual(flow.review(accepted=False, change='Beispielkontakt als Platzhalter markieren')['stage'], 'revision_needed')
            self.assertEqual(flow.revise()['stage'], 'review_ready')
            self.assertEqual(flow.deliver()['stage'], 'delivered')
            self.assertTrue((Path(temp) / 'delivery.md').is_file())
            events = [e['kind'] for e in flow.state['events']]
            self.assertEqual(events.count('clarification_requested'), 1)
            self.assertEqual(events.count('draft_created'), 1)
            self.assertEqual(events.count('draft_revised'), 1)
            self.assertEqual(events.count('delivery_created'), 1)

    def test_restart_at_each_stage_does_not_duplicate_artifacts_or_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            flow = OrderFlow(temp)
            flow.receive_briefing(self.briefing)
            flow = OrderFlow(temp); flow.answer_clarification('deadline', 'Freitag')
            flow = OrderFlow(temp); flow.create_draft()
            flow = OrderFlow(temp); flow.review(accepted=False, change='Platzhalter prüfen')
            flow = OrderFlow(temp); flow.revise()
            flow = OrderFlow(temp); flow.review(accepted=True)
            flow = OrderFlow(temp); flow.deliver()
            flow = OrderFlow(temp)
            self.assertEqual(flow.state['stage'], 'delivered')
            self.assertEqual([e['kind'] for e in flow.state['events']].count('delivery_created'), 1)
            self.assertGreaterEqual(len(flow.state['events']), 9)
            self.assertEqual(len(flow.state['events']), len(OrderFlow(temp).state['events']))
            before = (Path(temp) / 'delivery.md').read_bytes()
            self.assertEqual(flow.state['stage'], 'delivered')
            self.assertEqual((Path(temp) / 'delivery.md').read_bytes(), before)

    def test_invalid_order_cannot_skip_question_or_review(self):
        with tempfile.TemporaryDirectory() as temp:
            flow = OrderFlow(temp)
            with self.assertRaises(ValueError):
                flow.receive_briefing({'buyer': 'x'})
            with self.assertRaises(ValueError):
                flow.answer_clarification('deadline', 'x')
            flow.receive_briefing(self.briefing)
            with self.assertRaises(ValueError):
                flow.create_draft()
            with self.assertRaises(ValueError):
                flow.review(accepted=True)
            with self.assertRaises(ValueError):
                flow.deliver()
