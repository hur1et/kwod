from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from kwod.accounting import estimate_cost, import_financial_event, import_observation, observations, reconcile_snapshot, register_tariff
from kwod.runtime import initialize
from kwod.store import Store
from kwod.provider import FixtureProvider
from kwod.runtime import Runtime

TARIFF = {'verified': True, 'input': '10', 'cached': '1', 'cache_write': '12.5', 'output': '50',
          'cache_write_field': 'fixture_cache_writes', 'cache_writes_in_input': True,
          'max_input_tokens': 272000, 'missing_writes_means_zero': False}
USAGE = {'input_tokens': 1000, 'output_tokens': 100,
         'input_tokens_details': {'cached_tokens': 200, 'fixture_cache_writes': 100},
         'output_tokens_details': {'reasoning_tokens': 80}}


class AccountingTests(unittest.TestCase):
    def test_end_to_end_usage_uses_persisted_price_version(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            try:
                initialize(store, 'offline tariff test')
                register_tariff(store, {'id': 'fixture-price', 'valid_from': '2026-01-01T00:00:00Z',
                    'currency': 'USD', 'source_url': 'https://developers.openai.com/api/docs/models/gpt-6-astra',
                    'tariff': {**TARIFF, 'mapping_evidence': 'Offline fixture category definition'}})
                runtime = Runtime(store, FixtureProvider([{'id': 'fixture-price-response', 'status': 'completed',
                    'model': 'gpt-6-astra', 'service_tier': 'default', 'usage': USAGE, 'output': []}]))
                self.assertEqual(runtime.tick(), 'idle')
                attempt = store.db.execute('SELECT * FROM model_attempt').fetchone()
                self.assertEqual(attempt['estimated_cost_micro'], 13450)
                self.assertEqual(attempt['price_version_id'], 'fixture-price')
                self.assertEqual(attempt['cost_currency'], 'USD')
            finally:
                store.close()

    def test_credit_purchase_is_not_a_second_balance_debit(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            try:
                initialize(store, 'offline transaction test')
                transfer = {'source': 'fixture', 'external_id': 'purchase', 'occurred_at': '2026-01-01T10:00:00Z',
                            'kind': 'transfer', 'source_asset': 'cash', 'target_asset': 'credits',
                            'amount_micro': 10000000, 'currency': 'EUR', 'eur_value_micro': 10000000,
                            'fx_decimal': None, 'corrects_id': None, 'evidence': {'fixture': True}}
                first = import_financial_event(store, transfer)
                self.assertEqual(import_financial_event(store, transfer), first)
                for asset, amount in [('cash', 40000000), ('credits', 10000000)]:
                    import_observation(store, {'source': 'fixture', 'external_id': asset,
                        'observed_at': '2026-01-01T11:00:00Z', 'asset_id': asset, 'currency': 'EUR',
                        'amount_micro': amount, 'evidence': {'fixture': True}})
                self.assertEqual(sum(x['amount_micro'] for x in observations(store)), 50000000)
                corrected = import_financial_event(store, {**transfer, 'external_id': 'correction',
                    'kind': 'correction', 'corrects_id': first, 'amount_micro': 9000000})
                self.assertNotEqual(first, corrected)
                self.assertEqual(store.db.execute('SELECT count(*) FROM financial_event').fetchone()[0], 2)
                self.assertEqual(sum(x['amount_micro'] for x in observations(store)), 50000000)
            finally:
                store.close()

    def test_cache_categories_and_reasoning_not_double_counted(self):
        self.assertEqual(estimate_cost(USAGE, TARIFF), 13450)
        other = deepcopy(USAGE)
        other['output_tokens_details']['reasoning_tokens'] = 0
        self.assertEqual(estimate_cost(other, TARIFF), 13450)

    def test_unknowns_invalid_counts_and_unverified_categories(self):
        for usage, tariff in [(None, TARIFF), (USAGE, {}), (USAGE, {**TARIFF, 'verified': False}),
                             (USAGE, {**TARIFF, 'cache_writes_in_input': False}),
                             (USAGE, {**TARIFF, 'input': 'NaN'}),
                             ({**USAGE, 'input_tokens': -1}, TARIFF),
                             ({**USAGE, 'output_tokens': True}, TARIFF),
                             ({**USAGE, 'input_tokens': 272001}, TARIFF),
                             ({**USAGE, 'input_tokens_details': {'cached_tokens': 200}}, TARIFF)]:
            with self.subTest(usage=usage, tariff=tariff):
                self.assertIsNone(estimate_cost(usage, tariff))

    def test_snapshot_cutoff_avoids_double_consumption(self):
        usage = [{'started_at': '2026-09-01T10:00:00Z', 'ended_at': '2026-09-01T10:01:00Z',
                  'amount_micro': 1000000, 'currency': 'EUR'},
                 {'started_at': '2026-09-01T12:00:00Z', 'ended_at': '2026-09-01T12:01:00Z',
                  'amount_micro': 500000, 'currency': 'EUR'}]
        # Purchased credits are already part of the confirmed balance, not a second cost.
        value = reconcile_snapshot(9000000, '2026-09-01T11:00:00Z', 'EUR', usage)
        self.assertEqual(value['amount_micro'], 8500000)
        newer = reconcile_snapshot(8500000, '2026-09-01T13:00:00Z', 'EUR', usage)
        self.assertEqual(newer['amount_micro'], 8500000)
        self.assertEqual(newer['quality'], 'confirmed')

    def test_unknown_currency_overlap_and_negative_balance(self):
        usage = [{'started_at': '2026-09-01T12:00:00Z', 'ended_at': '2026-09-01T12:01:00Z',
                  'amount_micro': 500000, 'currency': 'USD'}]
        self.assertIsNone(reconcile_snapshot(1, '2026-09-01T11:00:00Z', 'EUR', usage)['amount_micro'])
        self.assertIsNone(reconcile_snapshot(1, '2026-09-01T12:00:30Z', 'USD', usage)['amount_micro'])
        self.assertEqual(reconcile_snapshot(1, '2026-09-01T11:00:00Z', 'USD', usage)['amount_micro'], -499999)

    def test_evidence_deduplication_and_conflicting_external_id(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(temp)
            try:
                initialize(store, 'test')
                value = {'source': 'offline-test-evidence', 'external_id': 'receipt-1',
                         'observed_at': '2026-01-01T12:00:00Z', 'asset_id': 'cash', 'currency': 'EUR',
                         'amount_micro': -1000000, 'evidence': {'fixture': True}}
                first = import_observation(store, value)
                self.assertEqual(import_observation(store, value), first)
                with self.assertRaises(ValueError):
                    import_observation(store, {**value, 'amount_micro': 10})
                self.assertEqual(observations(store)[0]['amount_micro'], -1000000)
                self.assertEqual(store.db.execute('SELECT count(*) FROM evidence').fetchone()[0], 1)
            finally:
                store.close()
