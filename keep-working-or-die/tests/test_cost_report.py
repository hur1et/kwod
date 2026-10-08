import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from kwod.cost_report import summarize

ROOT = Path(__file__).parents[1]


class CostReportTests(unittest.TestCase):
    def setUp(self):
        self.trial = json.loads((ROOT / 'docs/work-trial-cost-observation.json').read_text())
        self.pilot = json.loads((ROOT / 'docs/pilot-02-cost-observation.json').read_text())

    def test_report_keeps_sources_unknowns_and_no_debit(self):
        report = summarize(self.trial, self.pilot)
        self.assertEqual(report['combined_observed_cost'], '0.40')
        self.assertEqual(report['account_balance_after_pilot'], '39.60')
        self.assertIsNone(report['runs'][0]['per_attempt_cost'])
        self.assertEqual(report['provider_usage']['status'], 'unknown')
        self.assertFalse(report['ledger_debit_created'])
        self.assertIn('No other account consumption', report['runs'][1]['attribution_condition'])

    def test_provider_usage_is_additional_evidence_and_never_replaces_balance_observation(self):
        report = summarize(self.trial, self.pilot, provider_usage={'status': 'partial', 'attempts': 5})
        self.assertEqual(report['provider_usage']['attempts'], 5)
        self.assertEqual(report['combined_observed_cost'], '0.40')

    def test_invalid_or_increasing_balance_fails_closed(self):
        with self.assertRaises(ValueError):
            summarize({**self.trial, 'reported_total_decimal': '-0.01'}, self.pilot)
        with self.assertRaises(ValueError):
            summarize(self.trial, {**self.pilot, 'reported_balance_after': '40.01'})
        with self.assertRaises(ValueError):
            summarize({k: v for k, v in self.trial.items() if k != 'source'}, self.pilot)

    def test_cli_emits_report_without_creating_data(self):
        result = subprocess.run([sys.executable, '-m', 'kwod', '--data', str(ROOT / 'unused-ap2-data'),
                                 'cost-report', '--trial-observation', str(ROOT / 'docs/work-trial-cost-observation.json'),
                                 '--pilot-observation', str(ROOT / 'docs/pilot-02-cost-observation.json')],
                                cwd=ROOT, capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        self.assertEqual(output['combined_observed_cost'], '0.40')
        self.assertFalse((ROOT / 'unused-ap2-data').exists())
