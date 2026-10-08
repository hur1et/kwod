from pathlib import Path
import unittest


class CostObserverServiceTests(unittest.TestCase):
    def test_wal_companions_are_available_and_safety_pause_stops_observer(self):
        service=(Path(__file__).parents[1]/'deploy/kwod-cost-observer.service').read_text()
        self.assertIn('ReadWritePaths=/var/lib/kwod-production/private /var/lib/kwod-production/public',service)
        self.assertIn('ConditionPathExists=!/etc/kwod-safety/WATCHDOG_PAUSE',service)
        self.assertIn('User=kwod-runtime',service)
