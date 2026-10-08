import importlib.util
from pathlib import Path
import stat
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch


def repair_module():
    spec=importlib.util.spec_from_file_location('operator_repair',Path(__file__).parents[1]/'deploy/repair_birth_monitor.py')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


class OperatorRepairTests(unittest.TestCase):
    def invoke(self,raw):
        module=repair_module(); unit=Mock(); unit.read_bytes.return_value=raw
        unit.lstat.return_value=SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=0)
        unit.with_name.return_value.exists.return_value=False
        with patch.object(module.os,'geteuid',return_value=0,create=True),patch.object(module,'Path',return_value=unit),patch.object(module,'atomic_write') as write,patch.object(module.subprocess,'run') as run,patch.object(module.subprocess,'check_output',return_value='cap_setgid cap_setuid'),patch('builtins.print'):
            module.main()
            return write.call_args_list,run.call_args_list

    def test_repair_preserves_sandbox_and_restarts_only_operator(self):
        raw=b'[Service]\nNoNewPrivileges=true\nProtectSystem=strict\nRestrictAddressFamilies=AF_UNIX AF_INET AF_INET6\n'
        writes,runs=self.invoke(raw)
        repaired=writes[-1].args[1]
        self.assertIn(b'NoNewPrivileges=true\n',repaired)
        self.assertIn(b'ProtectSystem=strict\n',repaired)
        self.assertEqual(repaired.count(b'AmbientCapabilities=CAP_SETUID CAP_SETGID'),1)
        self.assertIn(b'AF_INET6 AF_NETLINK',repaired)
        actions=[call.args[0] for call in runs]
        self.assertEqual([action for action in actions if 'restart' in action],[['systemctl','restart','kwod-operator.service']])
        self.assertFalse(any('kwod-production.service' in action for action in actions))

    def test_repeated_repair_does_not_rewrite_unit_or_backup(self):
        raw=b'[Service]\nNoNewPrivileges=true\nAmbientCapabilities=CAP_SETUID CAP_SETGID\nRestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK\n'
        writes,_=self.invoke(raw)
        self.assertEqual(writes,[])

    def test_unknown_capability_configuration_is_rejected_before_writes(self):
        module=repair_module(); unit=Mock()
        unit.lstat.return_value=SimpleNamespace(st_mode=stat.S_IFREG|0o644,st_uid=0)
        unit.read_bytes.return_value=b'NoNewPrivileges=true\nAmbientCapabilities=CAP_SYS_ADMIN\nRestrictAddressFamilies=AF_UNIX AF_INET AF_INET6\n'
        with patch.object(module.os,'geteuid',return_value=0,create=True),patch.object(module,'Path',return_value=unit),patch.object(module,'atomic_write') as write,patch.object(module.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'unexpected_ambient'): module.main()
            write.assert_not_called(); run.assert_not_called()
