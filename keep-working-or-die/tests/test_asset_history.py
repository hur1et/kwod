import tempfile
import unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from kwod.store import Store
from kwod.runtime import initialize
from kwod.accounting import import_observation
from kwod.projection import project
from kwod.api import create_app


class AssetHistoryTests(unittest.TestCase):
    def test_history_survives_projection_without_private_access_and_has_no_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp); initialize(store,'SECRET objective')
            for i,balance in enumerate((40000000,38205797)):
                import_observation(store,{'source':'fixture','external_id':str(i),'observed_at':(datetime.now(timezone.utc)-timedelta(minutes=3-i)).isoformat(),
                    'asset_id':'openrouter_credits','currency':'USD','amount_micro':balance,'evidence':{'secret':'SECRET wallet'}})
            project(store); project(store)
            store.close(); (Path(temp)/'private/state.sqlite').rename(Path(temp)/'private/hidden.sqlite')
            with TestClient(create_app(Path(temp)/'public/public.sqlite')) as client:
                response=client.get('/api/v1/asset-history')
                self.assertEqual(response.status_code,200)
                self.assertEqual([row['amount_micro'] for row in response.json()['points']],[40000000,38205797])
                self.assertNotIn('SECRET',response.text)
                self.assertEqual(client.get('/api/v1/asset-history?asset_id=private').status_code,422)
