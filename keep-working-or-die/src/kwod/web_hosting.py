"""Explicit static publication. No raw workspace mount on the public server."""
import argparse
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import shutil
import stat
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
from .store import atomic_write

MAX_FILES = 1000
MAX_BYTES = 100 * 1024 * 1024

def publish(files, root):
    source = files.path('site')
    if not source.is_dir():
        raise ValueError('create_site_directory_first')
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('hosting_not_installed')
    metadata = json.loads((root / 'address.json').read_text())
    if not isinstance(metadata.get('url'), str):
        raise ValueError('hosting_address_not_configured')
    staged = root / ('release-' + uuid.uuid4().hex)
    staged.mkdir(mode=0o2750)
    manifest, total = {}, 0
    try:
        for directory, dirs, names in os.walk(source, followlinks=False):
            for name in dirs:
                files.path((Path(directory) / name).relative_to(files.root).as_posix())
            for name in names:
                path = files.path((Path(directory) / name).relative_to(files.root).as_posix())
                if len(manifest) >= MAX_FILES:
                    raise ValueError('site_file_limit')
                relative = path.relative_to(source)
                target = staged / relative
                target.parent.mkdir(parents=True, exist_ok=True, mode=0o2750)
                # Reject links again at open. Runtime has the worker lock and no
                # executor may still run when publication starts.
                fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
                with os.fdopen(fd, 'rb') as inp, target.open('xb') as out:
                    info = os.fstat(inp.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                        raise ValueError('invalid_site_file')
                    digest = hashlib.sha256()
                    while chunk := inp.read(65536):
                        total += len(chunk)
                        if total > MAX_BYTES:
                            raise ValueError('site_size_limit')
                        out.write(chunk); digest.update(chunk)
                    out.flush(); os.fsync(out.fileno())
                target.chmod(0o640)
                manifest[relative.as_posix()] = digest.hexdigest()
        if 'index.html' not in manifest:
            raise ValueError('site_index_html_required')
        atomic_write(root / 'current.json', json.dumps({'release': staged.name,
                      'files': manifest}).encode(), mode=0o640)
    except BaseException:
        shutil.rmtree(staged)
        raise
    # Publications serialize under the runtime lock. Keep only the latest two.
    previous = sorted(root.glob('release-*'), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in previous[2:]:
        if old != staged and old.is_dir() and not old.is_symlink():
            shutil.rmtree(old)
    return {'ok': True, 'url': metadata['url'], 'release': staged.name,
            'file_count': len(manifest), 'bytes': total, 'public': True}

def handler(root):
    root = Path(root)
    class StaticHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                path = unquote(urlsplit(self.path).path)
                parts = Path(path.lstrip('/')).parts
                if any(p in ('.', '..') for p in parts) or '\\' in path:
                    raise ValueError('invalid_path')
                key = '/'.join(parts) or 'index.html'
                current = json.loads((root / 'current.json').read_text())
                if key not in current['files']:
                    self.send_error(404); return
                dest = root / current['release'] / key
                raw = dest.read_bytes()
                if hashlib.sha256(raw).hexdigest() != current['files'][key]:
                    raise ValueError('published_file_changed')
                self.send_response(200)
                self.send_header('Content-Type', mimetypes.guess_type(key)[0] or 'application/octet-stream')
                self.send_header('Content-Length', str(len(raw)))
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.end_headers(); self.wfile.write(raw)
            except (OSError, ValueError, KeyError):
                self.send_error(404)
        def do_HEAD(self):
            self.send_error(405)
        def log_message(self, *_):
            pass
    return StaticHandler

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--bind', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    ThreadingHTTPServer((args.bind, args.port), handler(args.root)).serve_forever()

if __name__ == '__main__':
    main()
