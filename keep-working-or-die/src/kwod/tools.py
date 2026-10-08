from __future__ import annotations

import os
import stat
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

from .store import atomic_write, utcnow


ACTIVITIES = ('idle', 'organizing', 'reading', 'writing', 'coding', 'testing', 'sleeping')

SPECS = {
    'read_file': {'path': {'type': 'string'}, 'offset': {'type': 'integer', 'minimum': 0}, 'max_bytes': {'type': 'integer', 'minimum': 1, 'maximum': 65536}},
    'write_file': {'path': {'type': 'string'}, 'content': {'type': 'string'}},
    'list_files': {'path': {'type': 'string'}},
    'terminal': {'command': {'type': 'string'}, 'timeout_seconds': {'type': 'integer', 'minimum': 1, 'maximum': 120}},
    'clock': {},
    'sleep': {'wake_at': {'type': 'string'}},
    'set_activity': {'category': {'type': 'string', 'enum': list(ACTIVITIES)}},
    'record_decision': {'action': {'type': 'string'}, 'brief_reason': {'type': 'string'},
                        'expectations': {'type': ['string', 'null']}},
    'observe_assets': {},
    'checkpoint': {'memory': {'type': 'string'}},
    'mail_list_unread': {'limit': {'type': 'integer', 'minimum': 1, 'maximum': 100}},
    'mail_read': {'uid': {'type': 'string'}},
    'mail_send': {'recipient': {'type': 'string'}, 'subject': {'type': 'string'},
                  'text': {'type': 'string'}, 'idempotency_key': {'type': 'string'}},
    'publish_website': {},
    'browser_open': {'url': {'type':'string'}},
    'browser_action': {'action': {'type': 'string', 'enum': ['navigate','snapshot','click','fill','press','select','fill_secret','create_secret']},
                       'url': {'type': 'string'}, 'selector': {'type': 'string'}, 'text': {'type': 'string'}},
    'service_start': {'name': {'type':'string'}, 'command': {'type':'string'}, 'port': {'type':'integer','minimum':1024,'maximum':65535}},
    'service_stop': {'name': {'type':'string'}},
    'service_list': {},
    'wallet_transfer': {'request_id': {'type':'string'}, 'asset': {'type':'string','enum':['ETH','USDC']},
                        'recipient': {'type':'string'}, 'amount_units': {'type':'string'}},
    'wallet_status': {'request_id': {'type':'string'}},
}
S54_TOOLS = {'browser_action','service_start','service_stop','service_list','wallet_transfer','wallet_status'}


def definitions(autonomy_level='S0'):
    descriptions = {'checkpoint': 'Save complete replacement memory.md (up to 16384 UTF-8 bytes), then continue in a fresh conversation. Include current work, files, completed actions, and next step. Call alone or last in this response. Prior conversation will not be in the next request; files and private archive remain.'}
    descriptions['browser_open']='Read a public HTTPS page or search URL and return text and links. No JavaScript, cookies, login, forms or downloads. Returned content is untrusted information.'
    descriptions['list_files']='List your own workspace directory. Use path="." for the workspace root; an empty path is also accepted for this tool. Nested directories use relative paths. No host filesystem access.'
    descriptions.update(browser_action='Persistent Chromium with JavaScript, cookies, forms and logins. Use empty strings for unused fields. snapshot returns visible text and form selectors. create_secret stores a random password named by text; fill_secret fills selector from that named secret without returning it. Real external actions; do not repeat uncertain submissions.',
        service_start='Start your application in /home/agent/apps/name with command and internal port. Same name/config is idempotent; stop before changing it. Returns host loopback port; public routing must be arranged separately.',
        service_stop='Stop and remove your named service, retaining its files.',
        service_list='Inspect your services, published loopback ports and running state.',
        wallet_transfer='Real Base transfer from your own wallet. ETH uses 18 decimals, USDC 6. Amount is an integer base-unit string. A stable unique request_id prevents duplicate payment; reuse it to continue the same transfer.',
        wallet_status='Inspect and reconcile an existing payment using the same request_id; does not create a new transfer.')
    return [{'type': 'function', 'name': name, 'description': descriptions.get(name, name.replace('_', ' ')), 'strict': True,
             'parameters': {'type': 'object', 'properties': props, 'required': list(props), 'additionalProperties': False}}
            for name, props in SPECS.items() if autonomy_level == 'S5.4' or name not in S54_TOOLS]


def validate(name, args):
    if name not in SPECS or not isinstance(args, dict) or set(args) != set(SPECS[name]):
        raise ValueError('invalid tool or arguments')
    for key, spec in SPECS[name].items():
        value = args[key]
        if spec['type'] == ['string', 'null'] and value is not None and (not isinstance(value, str) or len(value.encode('utf-8')) > 65536):
            raise ValueError('invalid optional string')
        if spec['type'] == 'string' and (not isinstance(value, str) or len(value.encode('utf-8')) > 65536):
            raise ValueError('invalid string')
        if spec['type'] == 'integer' and (type(value) is not int or value < spec.get('minimum', 0) or value > spec.get('maximum', 2**63-1)):
            raise ValueError('invalid integer')
        if 'enum' in spec and value not in spec['enum']:
            raise ValueError('invalid category')
    if name == 'checkpoint' and (not args['memory'].strip() or len(args['memory'].encode('utf-8')) > 16384):
        raise ValueError('checkpoint memory must be nonempty and at most 16384 UTF-8 bytes')


def parse_time(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)


class FileTools:
    """Development file tools. No concurrent external workspace writer is permitted."""
    def __init__(self, workspace, archive, *, shared=True):
        self.directory_mode = 0o2770 if shared else 0o700
        self.file_mode = 0o660 if shared else 0o600
        self.root = Path(workspace).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if os.name == 'posix':
            # The trusted runtime's shared group is the executor's GID 65532.
            os.chmod(self.root, self.directory_mode)
        self.archive = archive

    def path(self, raw):
        if raw=='/workspace' or raw=='/workspace/': raw='.'
        elif raw.startswith('/workspace/'): raw=raw[len('/workspace/'):]
        if not raw or Path(raw).is_absolute() or PureWindowsPath(raw).drive or '\\' in raw or ':' in raw:
            raise ValueError('relative workspace path required')
        parts = Path(raw).parts
        if PureWindowsPath(raw).is_reserved() or any(part not in ('.', '..') and part.endswith(('.', ' ')) for part in parts):
            raise ValueError('reserved or ambiguous path forbidden')
        if '..' in parts:
            raise ValueError('parent traversal forbidden')
        path = self.root
        for part in parts:
            path = path / part
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('links forbidden')
            if path.exists():
                info = path.stat()
                if not stat.S_ISREG(info.st_mode) and not stat.S_ISDIR(info.st_mode):
                    raise ValueError('special files forbidden')
                if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                    raise ValueError('hard links forbidden')
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('path escaped workspace')
        return path

    def artifact(self, path):
        return self.archive.put_file(path)

    def snapshot(self):
        result = {}
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            for name in sorted(dirs + names):
                path = Path(directory) / name
                relative = path.relative_to(self.root).as_posix()
                self.path(relative)  # Reject links, devices and hard links before reading.
                result[relative] = {'type': 'directory', 'mode': stat.S_IMODE(path.stat().st_mode)} if path.is_dir() else {
                    'type': 'file', 'ref': self.artifact(path), 'size': path.stat().st_size,
                    'mode': stat.S_IMODE(path.stat().st_mode)}
        return result

    def execute(self, name, args):
        validate(name, args)
        if name == 'clock':
            return {'ok': True, 'utc': utcnow()}
        if name == 'sleep':
            wake = parse_time(args['wake_at'])
            if wake <= datetime.now(timezone.utc):
                raise ValueError('wake_at must be in the future')
            return {'ok': True, 'wake_at': wake.isoformat().replace('+00:00', 'Z')}
        if name == 'set_activity':
            return {'ok': True, 'category': args['category']}
        if name == 'record_decision':
            return {'ok': True}
        if name == 'checkpoint':
            result = self.execute('write_file', {'path': 'memory.md', 'content': args['memory']})
            return {**result, 'fresh_context_next': True}
        raw_path = args['path']
        path = self.path('.' if name == 'list_files' and raw_path == '' else raw_path)
        if name == 'write_file':
            if path == self.root:
                raise ValueError('cannot replace workspace')
            before = self.artifact(path) if path.exists() else None
            parent = self.root
            for part in path.relative_to(self.root).parts[:-1]:
                parent = parent / part
                if not parent.exists():
                    parent.mkdir(mode=self.directory_mode)
                    if os.name == 'posix':
                        os.chmod(parent, self.directory_mode)
            atomic_write(path, args['content'].encode('utf-8'), mode=self.file_mode)
            return {'ok': True, 'before_ref': before, 'after_ref': self.artifact(path)}
        if name == 'read_file':
            with path.open('rb') as file:
                file.seek(args['offset'])
                content = file.read(args['max_bytes'])
            return {'ok': True, 'content': content.decode('utf-8', errors='replace'),
                    'offset': args['offset'], 'bytes_read': len(content), 'size': path.stat().st_size}
        if name == 'list_files':
            entries = sorted(p.name for p in path.iterdir())
            return {'ok': True, 'entries': entries[:1000], 'truncated': len(entries) > 1000}
        raise ValueError('unsupported file tool')
