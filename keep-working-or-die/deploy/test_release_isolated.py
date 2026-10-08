"""Run release unit tests in private mount/network namespaces, never the host gate."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

MASKS=('/etc/kwod-safety','/etc/kwod-mail','/etc/kwod-openrouter','/etc/kwod',
       '/etc/kwod-signer.json','/run/kwod-watchdog','/run/kwod-mail-safety',
       '/run/kwod-browser','/run/kwod-signer','/run/docker.sock',
       '/etc/kwod-production','/var/lib/kwod','/var/lib/kwod-production','/var/lib/kwod-signer')

def namespaces():
    return tuple(os.readlink('/proc/self/ns/'+name) for name in ('mnt','net'))

def test_environment():
    env=dict(os.environ)
    for name in ('KWOD_DEV_OPENROUTER_API_KEY','KWOD_DEV_OPENAI_API_KEY',
                 'OPENAI_API_KEY','OPENROUTER_API_KEY','KWOD_RUN_LINUX_ISOLATION',
                 'KWOD_EXECUTOR_IMAGE'):
        env.pop(name,None)
    return env

def inside(parent):
    if len(parent)!=2 or not all(re.fullmatch(kind+r':\[\d+\]',value) for kind,value in zip(('mnt','net'),parent)):
        raise ValueError('invalid_parent_namespaces')
    current=namespaces()
    if any(a==b for a,b in zip(current,parent)): raise ValueError('private_test_namespaces_required')
    subprocess.run(['mount','--make-rprivate','/'],check=True)
    targets=[]
    with tempfile.TemporaryDirectory(prefix='kwod-release-tests-') as temp:
        empty=Path(temp)/'empty'; empty.mkdir(mode=0o755)
        file=Path(temp)/'empty-file'; file.write_text('{}')
        try:
            for raw in MASKS:
                target=Path(raw)
                if not target.exists(): continue
                source=empty if target.is_dir() else file
                subprocess.run(['mount','--bind',str(source),str(target)],check=True)
                targets.append(str(target))
                subprocess.run(['mount','-o','remount,bind,ro',str(target)],check=True)
            release=Path(__file__).resolve().parent.parent
            print('Release tests: isolated from host safety state, credentials and network.',flush=True)
            return subprocess.run([sys.executable,'-m','pytest','-q','-p','no:cacheprovider',str(release/'tests')],
                                  cwd=release,env=test_environment()).returncode
        finally:
            for target in reversed(targets): subprocess.run(['umount',target],check=True)

def main():
    if sys.platform!='linux' or os.geteuid()!=0: raise ValueError('ubuntu_root_required')
    if len(sys.argv)==1:
        parent=namespaces()
        return subprocess.run(['unshare','--mount','--net','--',sys.executable,
            str(Path(__file__).resolve()),'--inside',*parent],env=test_environment()).returncode
    if len(sys.argv)==4 and sys.argv[1]=='--inside': return inside(sys.argv[2:])
    raise ValueError('invalid_isolated_test_arguments')

if __name__=='__main__': raise SystemExit(main())
