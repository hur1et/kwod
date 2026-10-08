"""Agent applications in fixed mounts/network; never expose Docker arguments."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

from .autonomy import require
from .executor import DockerExecutor

LABEL = 'kwod.s54=1'


class Services:
    def __init__(self, root, archive):
        self.root, self.archive = Path(root), archive

    def run(self, *args, input=None, timeout=30):
        result = subprocess.run(['docker', *args], input=input, capture_output=True,
                                text=True, timeout=timeout, env=DockerExecutor.environment(self))
        if result.returncode:
            raise ValueError('application_container_operation_failed')
        return result.stdout

    def inventory(self):
        names = self.run('ps','-a','--filter','label='+LABEL,'--format','{{.Names}}').splitlines()
        return [self.inspect(name) for name in names]

    def inspect(self, name):
        if not re.fullmatch(r'kwod-s54-(?:browser|app-[a-z][a-z0-9-]{0,31})', name):
            raise ValueError('invalid_managed_container')
        value = json.loads(self.run('inspect',name))[0]
        if value['Config'].get('Labels',{}).get('kwod.s54') != '1':
            raise ValueError('container_not_owned')
        return value

    def base(self, name, cfg):
        home = self.root/'agent-home'
        if home.is_symlink() or not home.is_dir() or ',' in str(home):
            raise ValueError('invalid_agent_home')
        return ['run','-d','--name',name,'--label',LABEL,'--pull=never',
                '--network=kwod-world','--dns=1.1.1.1','--dns=9.9.9.9',
                '--read-only','--cap-drop=ALL','--security-opt=no-new-privileges:true',
                '--pids-limit=256','--memory=1g','--memory-swap=1g','--cpus=2',
                '--user=65532:65532','--init','--restart=no','--log-driver=local',
                '--log-opt=max-size=10m','--log-opt=max-file=2',
                '--sysctl=net.ipv6.conf.all.disable_ipv6=1',
                '--tmpfs','/tmp:rw,nosuid,nodev,size=256m',
                '--mount',f'type=bind,source={home},target=/home/agent',
                '--env=HOME=/home/agent','--env=PYTHONUSERBASE=/home/agent/.local',
                '--env=NPM_CONFIG_PREFIX=/home/agent/.local',
                '--env=PATH=/home/agent/.local/bin:/usr/local/bin:/usr/bin:/bin']

    def ready(self, capability):
        cfg = require(capability)
        check = subprocess.run(['systemctl','is-active','--quiet','kwod-s54-guard.service'],
                               capture_output=True, timeout=10)
        if check.returncode: raise ValueError('s54_guard_unavailable')
        return cfg

    def list(self):
        self.ready('services')
        return {'ok':True,'services':[{'name':x['Name'].lstrip('/'),
                 'running':x['State']['Running'],'ports':x['NetworkSettings']['Ports']}
                 for x in self.inventory()]}

    def start(self, name, command, port):
        cfg = self.ready('services')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}', name) or not command.strip():
            raise ValueError('invalid_service_name_or_command')
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('invalid_service_port')
        directory = self.root/'agent-home'/'apps'/name
        for p in (directory.parent, directory):
            if p.is_symlink(): raise ValueError('linked_application_directory')
            p.mkdir(exist_ok=True, mode=0o2770)
        full = 'kwod-s54-app-'+name
        fingerprint = hashlib.sha256(json.dumps([command,port,cfg['image']]).encode()).hexdigest()
        rows = self.inventory()
        for row in rows:
            if row['Name'].lstrip('/') == full:
                if row['Config']['Labels'].get('kwod.spec') != fingerprint:
                    raise ValueError('stop_service_before_changing_configuration')
                return {'ok':True,'name':name,'running':row['State']['Running'],
                        'ports':row['NetworkSettings']['Ports'],'existing':True}
        if len(rows) >= 8: raise ValueError('server_service_capacity_reached')
        used = {int(p['HostPort']) for row in rows for ports in row['NetworkSettings']['Ports'].values()
                for p in (ports or [])}
        host_port = next(p for p in range(18080,18180) if p not in used)
        args = self.base(full,cfg) + ['--label','kwod.spec='+fingerprint,
            '--publish',f'127.0.0.1:{host_port}:{port}',
            '--workdir','/home/agent/apps/'+name,'--entrypoint=/bin/sh',cfg['image'],'-c',command]
        self.run(*args)
        row = self.inspect(full)
        return {'ok':True,'name':name,'running':row['State']['Running'],
                'host_loopback_url':f'http://127.0.0.1:{host_port}/',
                'worldwide_reachability_verified':False,
                'next':'Use your hosting provider, domain or a public tunnel running alongside this application.'}

    def stop(self, name):
        self.ready('services')
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,31}',name): raise ValueError('invalid_service_name')
        full = 'kwod-s54-app-'+name
        if any(x['Name'].lstrip('/') == full for x in self.inventory()):
            self.run('rm','-f',full)
        return {'ok':True,'stopped':name,'files_preserved':True}

    def browser(self, args):
        cfg = self.ready('browser_sessions')
        full = 'kwod-s54-browser'
        rows = self.inventory()
        row = next((x for x in rows if x['Name'].lstrip('/') == full),None)
        if row is not None and not row['State']['Running']:
            self.run('rm','-f',full); row = None
        if row is None:
            self.run(*(self.base(full,cfg)+['--entrypoint=python',cfg['image'],
                                          '/opt/kwod/browser_session.py','serve']))
        # Arguments travel over stdin, never Docker environment/command strings.
        output = self.run('exec','-i',full,'python','/opt/kwod/browser_session.py','client',
                          input=json.dumps(args)+'\n',timeout=70)
        return json.loads(output)
