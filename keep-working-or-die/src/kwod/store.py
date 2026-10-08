from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode('utf-8')


def sync_dir(path):
    if os.name == 'posix':
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def atomic_write(path: Path, data: bytes, mode=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.kwod-')
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        if mode is not None and os.name == 'posix':
            os.chmod(tmp, mode)
        os.replace(tmp, path)
        sync_dir(path.parent)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True, mode=0o700)

    def put(self, value):
        data = encode(value)
        digest = hashlib.sha256(data).hexdigest()
        dest = self.path / digest
        if not dest.exists():
            atomic_write(dest, data)
        elif dest.read_bytes() != data:
            raise IOError('archive integrity failure')
        return digest

    def get(self, ref):
        if not re.fullmatch('[a-f0-9]{64}', ref):
            raise ValueError('invalid archive reference')
        data = (self.path / ref).read_bytes()
        if hashlib.sha256(data).hexdigest() != ref:
            raise IOError('archive integrity failure')
        return json.loads(data)

    def put_file(self, path):
        """Stream arbitrary file contents without loading large terminal output into RAM."""
        fd, tmp = tempfile.mkstemp(dir=self.path, prefix='.blob-')
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, 'wb') as out, Path(path).open('rb') as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b''):
                    digest.update(chunk)
                    out.write(chunk)
                out.flush()
                os.fsync(out.fileno())
            ref = digest.hexdigest()
            dest = self.path / ref
            if dest.exists():
                self.verify(ref)
            else:
                os.replace(tmp, dest)
                sync_dir(self.path)
            return ref
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def verify(self, ref):
        if not re.fullmatch('[a-f0-9]{64}', ref):
            raise ValueError('invalid archive reference')
        digest = hashlib.sha256()
        with (self.path / ref).open('rb') as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b''):
                digest.update(chunk)
        if digest.hexdigest() != ref:
            raise IOError('archive integrity failure')


class Store:
    def __init__(self, root, *, mode='dev'):
        if mode not in ('dev','prod'): raise ValueError('invalid_store_mode')
        self.mode=mode; self.instance_id=mode
        self.root = Path(root).resolve()
        database=self.root/'private/state.sqlite'
        if database.exists():
            check=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
            try:
                if check.execute("SELECT 1 FROM sqlite_master WHERE name='instance'").fetchone():
                    rows=check.execute('SELECT id,mode FROM instance').fetchall()
                    if rows and rows!=[(mode,mode)]: raise ValueError('store_mode_mismatch')
            finally: check.close()
        self.private = self.root / 'private'
        self.private.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.archive = Archive(self.private / 'archive')
        self.db = sqlite3.connect(self.private / 'state.sqlite', timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        if os.name == 'posix':
            os.chmod(self.private, 0o700)

    def migrate(self):
        exists = self.db.execute("SELECT 1 FROM sqlite_master WHERE name='schema_version'").fetchone()
        version = self.db.execute('SELECT max(version) FROM schema_version').fetchone()[0] if exists else 0
        for path in sorted((Path(__file__).parent / 'migrations').glob('*.sql')):
            if int(path.stem) > version:
                sql = path.read_text(encoding='utf-8')
                if path.stem == '001':
                    # journal mode is configured outside the migration transaction.
                    sql = sql.replace('PRAGMA journal_mode = WAL;', '')
                    sql = 'BEGIN IMMEDIATE;\n' + sql + '\nCOMMIT;'
                self.db.executescript(sql)

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def event(self, kind, value, actor='runtime'):
        ref = self.archive.put(value)
        cur = self.db.execute(
            'INSERT INTO trajectory_event(instance_id,occurred_at,kind,actor,payload_ref,payload_sha256) VALUES (?,?,?,?,?,?)',
            (self.instance_id, utcnow(), kind, actor, ref, ref))
        return cur.lastrowid

    def close(self):
        self.db.close()


@contextmanager
def worker_lock(root):
    path = Path(root) / 'private' / 'worker.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    file = path.open('a+b')
    try:
        if os.name == 'nt':
            import msvcrt
            file.seek(0, 2)
            if file.tell() == 0:
                file.write(b'0')
                file.flush()
            file.seek(0)
            msvcrt.locking(file.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        file.close()
        raise RuntimeError('another worker or maintenance operation holds the lock') from exc
    try:
        yield
    finally:
        file.close()
