"""Create a source-only release; never copy runtime data or local credentials."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT_FILES = ('pyproject.toml', 'requirements-tested.txt', 'README.md', '04_ENTWICKLUNGSKERN.md', '05_DEPLOYMENT_UND_ZUGRIFF.md')
PATTERNS = ('src/kwod/*.py', 'src/kwod/migrations/*.sql', 'src/kwod/static/*.html', 'tests/test_*.py',
            'fixtures/development.json', 'config/astra-standard-*.json',
            'docs/*.json', 'docs/production-preparation.md', 'docs/birth-control.md', 'docs/agent-live-update.md', 'docs/autonomy-s54.md',
            'deploy/*.py', 'deploy/*.ps1', 'deploy/*.service', 'deploy/*.timer', 'deploy/Executor.Dockerfile',
            'deploy/WorldExecutor.Dockerfile', 'deploy/S54.Dockerfile', 'deploy/WORLD_ACCESS.md',
            'scripts/offline_soak.py', 'scripts/preview_work_monitor.py', 'scripts/run_order_flow_fixture.py')


def build(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    paths = {source / name for name in ROOT_FILES}
    for pattern in PATTERNS:
        paths.update(source.glob(pattern))
    contents = {}
    for path in sorted(paths):
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(source):
            raise ValueError('source contains missing file or link: ' + str(path))
        for parent in path.parents:
            if parent == source:
                break
            if parent.is_symlink():
                raise ValueError('linked source directory')
        name = path.relative_to(source).as_posix()
        contents[name] = path.read_bytes()
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()}
    contents['bundle-manifest.json'] = json.dumps(manifest, sort_keys=True, indent=2).encode()
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, 'w:gz') as archive:
        for name, data in sorted(contents.items()):
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            archive.addfile(info, io.BytesIO(data))
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return {'bundle': str(target), 'sha256': digest, 'files': len(contents)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.output)))
