"""One disposable Linux container per command, offline unless world mode is enabled.

No host-shell fallback. Container control belongs to the trusted runtime only.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess


class DockerExecutor:
    def __init__(self, workspace, archive, image, *, world_access=False, persistent_home=False):
        self.workspace = Path(workspace).resolve()
        self.archive = archive
        self.image = image
        self.docker = shutil.which('docker')
        self.world_access = world_access
        self.persistent_home = persistent_home

    def world_ready(self):
        # Firewall is a host-owned service. Never silently fall back to an
        # unrestricted default bridge or to the host network.
        from .autonomy import require
        try: require('internet')
        except (OSError,ValueError) as exc:
            raise ValueError('world_firewall_not_prepared') from exc
        result = subprocess.run(['systemctl', 'is-active', '--quiet', 'kwod-s54-guard.service'],
                                env=self.environment(), timeout=10)
        if result.returncode:
            raise ValueError('world_firewall_unavailable')

    def name(self, call_id):
        if not re.fullmatch('[a-f0-9]{32}', call_id):
            raise ValueError('invalid internal call id')
        return 'kwod-' + call_id

    def command(self, call_id):
        if not self.docker or not self.image:
            raise ValueError('isolated_executor_unavailable')
        if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_./:@-]*', self.image):
            raise ValueError('invalid executor image')
        if ',' in str(self.workspace):
            raise ValueError('unsupported workspace path')
        if self.world_access:
            self.world_ready()
        command = [self.docker, 'run', '--name', self.name(call_id), '--pull=never',
                '--network=none', '--read-only', '--cap-drop=ALL',
                '--security-opt=no-new-privileges:true', '--pids-limit=64',
                '--memory=256m', '--memory-swap=256m', '--cpus=1',
                '--user=65532:65532', '--init', '--log-driver=none',
                '--mount', f'type=bind,source={self.workspace},target=/workspace',
                '--tmpfs', '/tmp:rw,noexec,nosuid,nodev,size=16m',
                '--workdir=/workspace', '--env=HOME=/tmp',
                '--entrypoint=/bin/sh', '-i', self.image, '-s']
        if self.world_access or self.persistent_home:
            home = self.workspace.parent / 'agent-home'
            if home.is_symlink() or not home.is_dir() or ',' in str(home):
                raise ValueError('invalid_agent_home')
            if self.world_access:
                command[command.index('--network=none')] = '--network=kwod-world'
                command[command.index('--read-only'):command.index('--read-only')] = ['--dns=1.1.1.1','--dns=9.9.9.9','--label=kwod.s54=1']
            for old, new in [('--memory=256m','--memory=1g'),('--memory-swap=256m','--memory-swap=1g'),
                             ('--cpus=1','--cpus=2'),('--pids-limit=64','--pids-limit=256')]:
                command[command.index(old)] = new
            command[command.index('/tmp:rw,noexec,nosuid,nodev,size=16m')] = '/tmp:rw,nosuid,nodev,size=256m'
            command[command.index('--env=HOME=/tmp')] = '--env=HOME=/home/agent'
            command[command.index('--entrypoint=/bin/sh'):command.index('--entrypoint=/bin/sh')] = [
                '--mount', f'type=bind,source={home},target=/home/agent',
                '--env=PYTHONUSERBASE=/home/agent/.local',
                '--env=NPM_CONFIG_PREFIX=/home/agent/.local',
                '--env=PATH=/home/agent/.local/bin:/usr/local/bin:/usr/bin:/bin',
                '--sysctl=net.ipv6.conf.all.disable_ipv6=1']
        return command

    def environment(self):
        # Never forward runtime credentials, proxy variables or alternate Docker hosts.
        return {k: os.environ[k] for k in ('PATH', 'SystemRoot', 'WINDIR', 'TEMP', 'TMP')
                if k in os.environ}

    def cleanup(self, call_id):
        if not self.docker:
            raise RuntimeError('cannot verify executor cleanup')
        proc = subprocess.run([self.docker, 'rm', '-f', self.name(call_id)],
                              capture_output=True, env=self.environment(), timeout=20)
        if proc.returncode and b'No such container' not in proc.stderr:
            raise RuntimeError('executor cleanup failed; recovery required')

    def execute(self, call_id, args):
        command = self.command(call_id)
        # Persistent spool survives process death, cleanup failure and archive failure.
        # Never automatically delete uncommitted observed output.
        spool = self.archive.path.parent / 'spool' / call_id
        spool.mkdir(parents=True, exist_ok=False, mode=0o700)
        stdout, stderr = spool / 'stdout', spool / 'stderr'
        timed_out = False
        with stdout.open('wb') as out, stderr.open('wb') as err:
            proc = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=out, stderr=err,
                                    env=self.environment())
            try:
                proc.communicate(args['command'].encode('utf-8'), timeout=args['timeout_seconds'])
            except subprocess.TimeoutExpired:
                timed_out = True
                self.cleanup(call_id)  # Kill all container processes, including background jobs.
                proc.kill()
                proc.wait(timeout=10)
            finally:
                try:
                    self.cleanup(call_id)
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=10)
                    out.flush()
                    err.flush()
                    os.fsync(out.fileno())
                    os.fsync(err.fileno())
        result = {'ok': proc.returncode == 0 and not timed_out,
                  'exit_code': proc.returncode, 'timed_out': timed_out}
        for key, path in [('stdout', stdout), ('stderr', stderr)]:
            result[key + '_ref'] = self.archive.put_file(path)
            with path.open('rb') as file:
                result[key] = file.read(24000).decode('utf-8', errors='replace')
            result[key + '_bytes'] = path.stat().st_size
            result[key + '_truncated'] = path.stat().st_size > 24000
        return result
