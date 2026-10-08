"""Check the actual launcher network property literals against CLI constraints."""
import ast
import ipaddress
from pathlib import Path
import unittest
import importlib.util
from unittest.mock import patch
from types import SimpleNamespace
import contextlib
import io
import json
import tempfile

from kwod.work_trial import run
from kwod.provider import FixtureProvider, ProviderError


class LauncherNetworkTests(unittest.TestCase):
    def test_pilot_stop_targets_only_pilot_directory_and_service(self):
        source = Path(__file__).parents[1] / 'deploy/run_work_trial.py'
        spec = importlib.util.spec_from_file_location('pilot_launcher', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.os, 'geteuid', return_value=0, create=True), \
             patch.object(module.sys, 'argv', ['launcher', 'unused', 'unused', '--stop-inspect', '--pilot']), \
             patch.object(module, 'stop_trial', return_value='stopped_or_not_running'), \
             patch.object(module, 'inspect_saved', return_value={}) as inspect, \
             contextlib.redirect_stdout(io.StringIO()):
            module.main()
        self.assertEqual(module.UNIT, 'kwod-work-pilot-02.service')
        inspect.assert_called_once_with('/var/lib/kwod-work-pilot-02', pilot=True)

    def test_stop_inspect_entrypoint_reads_actual_saved_database_without_start(self):
        source = Path(__file__).parents[1] / 'deploy/run_work_trial.py'
        spec = importlib.util.spec_from_file_location('trial_launcher_entry', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as root:
            run(root, FixtureProvider([ProviderError('openrouter_http_404')]))
            inspect = module.inspect_saved
            output = io.StringIO()
            with patch.object(module.os, 'geteuid', return_value=0, create=True), \
                 patch.object(module.sys, 'argv', ['launcher', 'unused', 'unused', '--stop-inspect']), \
                 patch.object(module, 'stop_trial', return_value='stopped_or_not_running') as stop, \
                 patch.object(module, 'inspect_saved', side_effect=lambda _: inspect(root)), \
                 patch.object(module.subprocess, 'run') as process, contextlib.redirect_stdout(output):
                module.main()
            stop.assert_called_once()
            process.assert_not_called()
            result = json.loads(output.getvalue())
            self.assertEqual(result['saved_attempts'][0]['error_code'], 'openrouter_http_404')
            self.assertEqual(result['service'], 'stopped_or_not_running')
            self.assertEqual(result['new_model_calls'], 0)

    def test_stop_checks_service_state_and_refuses_unconfirmed_stop(self):
        source = Path(__file__).parents[1] / 'deploy/run_work_trial.py'
        spec = importlib.util.spec_from_file_location('trial_launcher', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.subprocess, 'run', side_effect=[SimpleNamespace(returncode=0),
                SimpleNamespace(stdout='inactive\n')]) as call:
            self.assertEqual(module.stop_trial(), 'stopped_or_not_running')
            self.assertEqual(call.call_args_list[0].args[0], ['systemctl', 'stop', module.UNIT])
        with patch.object(module.subprocess, 'run', side_effect=[SimpleNamespace(returncode=1),
                SimpleNamespace(stdout='active\n'), SimpleNamespace(stdout='loaded\n')]):
            with self.assertRaises(RuntimeError):
                module.stop_trial()

    def test_numeric_lists_preserve_private_network_blocks_and_dns_exception(self):
        source = Path(__file__).parents[1] / 'deploy/run_work_trial.py'
        tree = ast.parse(source.read_text())
        properties = next([item.value for item in node.value.elts if isinstance(item, ast.Constant)] for node in ast.walk(tree)
                          if isinstance(node, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'properties' for t in node.targets))
        values = {}
        for kind in ('IPAddressAllow', 'IPAddressDeny'):
            entries = [p.split('=', 1)[1] for p in properties if p.startswith(kind + '=')]
            self.assertEqual(len(entries), 1)
            # Aliases mixed into this list reproduce the reported v255 failure.
            values[kind] = [ipaddress.ip_network(word) for word in entries[0].split()]
        self.assertEqual(values['IPAddressAllow'], [ipaddress.ip_network('127.0.0.53/32')])
        for raw in ('127.0.0.1', '::1', '169.254.1.1', 'fe80::1', 'febf::1',
                    '10.0.0.1', '172.16.0.1', '192.168.0.118', 'fd00::1'):
            address = ipaddress.ip_address(raw)
            with self.subTest(address=raw):
                self.assertTrue(any(address in net for net in values['IPAddressDeny']))
                self.assertFalse(any(address in net for net in values['IPAddressAllow']))


if __name__ == '__main__':
    unittest.main()
