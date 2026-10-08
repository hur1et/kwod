import json
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from kwod.assets import collect, public_snapshot, absorb
from kwod.store import Store, utcnow
from kwod.runtime import initialize


class AssetsTests(unittest.TestCase):
    def test_failure_keeps_last_known_balance_and_marks_stale(self):
        previous={'assets':[{'asset_id':'openrouter_credits','amount_decimal':'40','amount_micro':40000000,
                            'currency':'USD','observed_at':utcnow(),'quality':'confirmed'}]}
        with patch('kwod.assets.httpx.Client') as client, patch('kwod.assets.Path.lstat',side_effect=OSError):
            result=collect(previous)
            client.return_value.__enter__.return_value.get.assert_not_called()
        self.assertEqual(result['assets'][0]['amount_decimal'],'40')
        self.assertEqual(result['quality'],'partial')
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'public.json'; file.write_text(json.dumps(result))
            self.assertTrue(public_snapshot(file)['assets'][0]['stale'])
        self.assertIsNone(result['assets'][1]['amount_micro'])

    def test_verified_zero_is_distinct_from_unknown_and_uses_only_credits_endpoint(self):
        client=MagicMock(); response=client.get.return_value
        response.status_code=200; response.content=b'{}'; response.json.return_value={'data':{'total_credits':12,'total_usage':12}}
        with patch('kwod.assets.httpx.Client') as factory, patch('kwod.assets.Path.lstat',return_value=SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_uid=0)), patch('kwod.assets.Path.read_text',return_value='fixture-key'), patch('kwod.assets.Path.exists',return_value=True):
            factory.return_value.__enter__.return_value=client
            result=collect()
        self.assertEqual(result['assets'][0]['amount_micro'],0)
        self.assertEqual(result['assets'][0]['quality'],'confirmed')
        self.assertEqual(client.get.call_args.args[0],'https://openrouter.ai/api/v1/credits')
        client.post.assert_not_called()

    def test_absorb_is_durable_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'data'); initialize(store,'test')
            snapshot={'assets':[{'asset_id':'wallet_base_eth','currency':'ETH','amount_micro':1,
                'amount_units':'1000000000001','decimals':18,'observed_at':utcnow(),'quality':'confirmed','stale':False}]}
            with patch('kwod.assets.public_snapshot',return_value=snapshot):
                absorb(store); absorb(store)
            self.assertEqual(store.db.execute('SELECT COUNT(*) FROM asset_observation').fetchone()[0],1)
            store.close()
