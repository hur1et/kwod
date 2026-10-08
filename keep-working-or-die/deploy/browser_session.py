"""Runs INSIDE the isolated browser container; has no host credentials or tools."""
import json
from pathlib import Path
import re
import secrets
import socket
import socketserver
import sys
import time
from urllib.parse import urlsplit


def url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('public_http_url_required')
    return value


def secret_path(name):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',name): raise ValueError('invalid_secret_name')
    folder = Path('/home/agent/secrets')
    if folder.is_symlink(): raise ValueError('secret_directory_is_link')
    folder.mkdir(mode=0o700,exist_ok=True)
    path = folder/name
    if path.is_symlink(): raise ValueError('secret_is_link')
    return path


class Session:
    def __init__(self, context): self.context = context

    def handle(self, request):
        if set(request) != {'action','url','selector','text'} or not all(isinstance(x,str) for x in request.values()):
            raise ValueError('invalid_browser_request')
        action = request['action']
        if action == 'create_secret':
            path = secret_path(request['text'])
            if not path.exists():
                with path.open('x') as file: file.write(secrets.token_urlsafe(32))
                path.chmod(0o600)
            return {'ok':True,'secret_name':request['text'],'secret_returned':False}
        pages = [p for p in self.context.pages if not p.is_closed()]
        page = pages[-1] if pages else self.context.new_page()
        page.set_default_timeout(15000)
        if action == 'navigate': page.goto(url(request['url']),wait_until='domcontentloaded',timeout=30000)
        elif action == 'click': page.locator(request['selector']).click()
        elif action == 'fill': page.locator(request['selector']).fill(request['text'])
        elif action == 'fill_secret': page.locator(request['selector']).fill(secret_path(request['text']).read_text())
        elif action == 'press': page.locator(request['selector']).press(request['text'])
        elif action == 'select': page.locator(request['selector']).select_option(request['text'])
        elif action != 'snapshot': raise ValueError('invalid_browser_action')
        # Values, password fields and hidden inputs are deliberately not returned.
        forms = page.locator('input:not([type=hidden]),button,select,textarea,a[href]').evaluate_all('''els => els.slice(0,150).map(e => ({tag:e.tagName, id:e.id, name:e.name || '', type:e.type || '', text:(e.innerText || e.getAttribute('aria-label') || '').slice(0,160), href:e.tagName === 'A' ? e.href : null}))''')
        self.context.storage_state(path='/home/agent/browser/state.json')
        return {'ok':True,'url':page.url,'title':page.title(),
                'text':page.locator('body').inner_text(timeout=5000)[:24000],
                'elements':forms,'trust':'untrusted_external_content','side_effects_possible':action!='snapshot'}


def serve():
    from playwright.sync_api import sync_playwright
    folder = Path('/home/agent/browser'); folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(str(folder/'profile'),
            executable_path='/usr/bin/chromium',headless=True,accept_downloads=True,
            downloads_path=str(folder/'downloads'),args=['--no-sandbox','--disable-dev-shm-usage'])
        session = Session(context)
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.request.settimeout(55)
                raw = self.rfile.readline(262145)
                try:
                    if len(raw)>262144 or not raw.endswith(b'\n'): raise ValueError('invalid_frame')
                    result = session.handle(json.loads(raw))
                except Exception as exc:
                    # Browser exception strings can include filled credentials.
                    result = {'ok':False,'error':type(exc).__name__,'effect':'possibly_applied',
                              'next':'Inspect the page before repeating any submission.'}
                self.wfile.write(json.dumps(result).encode()+b'\n')
        with socketserver.TCPServer(('127.0.0.1',9229),Handler) as server: server.serve_forever()


def client():
    raw = sys.stdin.buffer.readline(262145)
    conn = None
    for _ in range(40):
        try: conn=socket.create_connection(('127.0.0.1',9229),timeout=1); break
        except OSError: time.sleep(0.25)
    if conn is None: raise ValueError('browser_not_ready')
    with conn:
        conn.settimeout(60); conn.sendall(raw)
        with conn.makefile('rb') as stream: result=stream.readline(262145)
    if not result.endswith(b'\n'): raise ValueError('browser_reply_incomplete')
    sys.stdout.buffer.write(result)


if __name__ == '__main__': {'serve':serve,'client':client}[sys.argv[1]]()
