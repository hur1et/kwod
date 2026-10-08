"""Consistent SQLite snapshot + hashed immutable archive + stopped workspace."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3

from .store import atomic_write, encode, Store, sync_dir, utcnow, worker_lock
from .tools import FileTools


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def durable_copy(source, target):
    with Path(source).open('rb') as src, Path(target).open('wb') as dest:
        shutil.copyfileobj(src, dest, 1024 * 1024)
        dest.flush()
        os.fsync(dest.fileno())
    sync_dir(Path(target).parent)


def backup(store, destination):
    dest = Path(destination).resolve()
    if dest.exists() or dest.is_relative_to(store.root) or store.root.is_relative_to(dest):
        raise ValueError('backup must be a new directory outside runtime data')
    with worker_lock(store.root):
        if store.db.execute("SELECT 1 FROM tool_call WHERE status IN ('running','outcome_unknown')").fetchone():
            raise ValueError('resolve uncertain tools before backup')
        files = FileTools(store.root / 'workspace', store.archive)
        snapshot = files.snapshot()
        dest.mkdir(parents=True, mode=0o700)
        private = dest / 'private'
        private.mkdir(mode=0o700)
        archive = private / 'archive'
        archive.mkdir(mode=0o700)
        target = sqlite3.connect(private / 'state.sqlite')
        try:
            store.db.backup(target)
        finally:
            target.close()
        outbound=store.private/'mail-outbound.sqlite'
        if outbound.exists():
            if outbound.is_symlink(): raise ValueError('outbound ledger is a link')
            mail_source=sqlite3.connect(outbound.as_uri()+'?mode=ro',uri=True)
            mail_target=sqlite3.connect(private/'mail-outbound.sqlite')
            try:
                mail_source.backup(mail_target)
            finally:
                mail_source.close(); mail_target.close()
            (private/'mail-outbound.sqlite').chmod(0o600)
        for path in store.archive.path.iterdir():
            if re.fullmatch('[a-f0-9]{64}', path.name):
                store.archive.verify(path.name)
                durable_copy(path, archive / path.name)
        spool = store.private / 'spool'
        if spool.exists():
            for path in spool.rglob('*'):
                if path.is_symlink():
                    raise ValueError('unexpected link in private spool')
                if path.is_file():
                    target_path = private / 'spool' / path.relative_to(spool)
                    target_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                    durable_copy(path, target_path)
        workspace = dest / 'workspace'
        workspace.mkdir()
        for name, item in snapshot.items():
            path = workspace / name
            if item['type'] == 'directory':
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                durable_copy(archive / item['ref'], path)
            if os.name == 'posix':
                os.chmod(path, item['mode'] & 0o777)  # Do not restore setuid/setgid executables.
        manifest = {p.relative_to(dest).as_posix(): digest(p) for p in dest.rglob('*') if p.is_file()}
        modes = {p.relative_to(dest).as_posix(): p.stat().st_mode & 0o777 for p in workspace.rglob('*')}
        atomic_write(dest / 'manifest.json', encode({'created_at': utcnow(), 'files': manifest, 'modes': modes}))
        with store.transaction():
            store.event('backup_created', {'manifest_sha256': digest(dest / 'manifest.json')})
    return dest


def restore(source, destination, *, mode='dev'):
    source, dest = Path(source).resolve(), Path(destination).resolve()
    if dest.exists():
        raise ValueError('restore target must not exist')
    metadata = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
    manifest = metadata['files']
    if 'private/state.sqlite' not in manifest:
        raise ValueError('missing database')
    for name, expected in manifest.items():
        rel = Path(name)
        path = source / rel
        if rel.is_absolute() or '..' in rel.parts or ':' in name or '\\' in name or not path.resolve().is_relative_to(source):
            raise ValueError('invalid manifest path')
        if path.is_symlink() or digest(path) != expected:
            raise ValueError('backup hash mismatch')
    dest.mkdir(parents=True, mode=0o700)
    for name in manifest:
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        durable_copy(source / name, target)
    for name, file_mode in metadata.get('modes', {}).items():
        target = dest / name
        if not name.startswith('workspace/') or not target.resolve().is_relative_to(dest / 'workspace'):
            raise ValueError('invalid mode path')
        if not target.exists():
            target.mkdir(parents=True, mode=0o770)
        if os.name == 'posix':
            os.chmod(target, file_mode & 0o777)
    store = Store(dest, mode=mode)
    try:
        if (store.private/'mail-outbound.sqlite').exists():
            ledger=sqlite3.connect((store.private/'mail-outbound.sqlite').as_uri()+'?mode=ro',uri=True)
            try:
                if ledger.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('mail ledger integrity failure')
            finally: ledger.close()
            # Effects since the backup may be missing. Never treat a historical
            # ledger as proof that an external action did not happen.
            atomic_write(store.private/'mail-restore-review-required',
                         b'Operator reconciliation required before outbound mail.',mode=0o600)
        if store.db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('database integrity failure')
        if store.db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('database foreign key failure')
        with store.transaction():
            store.event('restored', {'manifest_sha256': digest(source / 'manifest.json')})
        from .projection import project
        project(store)
    finally:
        store.close()
    return dest
