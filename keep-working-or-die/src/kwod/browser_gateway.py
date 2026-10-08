"""Read-only HTTPS browser via authenticated local IPC and pinned DNS."""
import hashlib
from html.parser import HTMLParser
import http.client
import ipaddress
import json
import os
from pathlib import Path
import socket
import socketserver
import ssl
import struct
import time
from urllib.parse import urljoin,urlsplit
from .browser_policy import BrowserBlocked,normalize_url,public_address
from .safety import stopped
from .watchdog import SocketWatchdog

MAX_BODY=1_048_576
MAX_TEXT=24000

class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.parts=[]; self.links=[]; self.hidden=0; self.anchor=None; self.title=False; self.titles=[]
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag in ('script','style','template','noscript'): self.hidden+=1
        if tag=='title': self.title=True
        if tag=='a' and not self.hidden: self.anchor=[values.get('href',''),[]]
        if tag in ('p','div','br','h1','h2','h3','li','tr'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style','template','noscript'): self.hidden=max(0,self.hidden-1)
        if tag=='title': self.title=False
        if tag=='a' and self.anchor:
            self.links.append({'url':self.anchor[0],'text':' '.join(self.anchor[1])[:200]}); self.anchor=None
    def handle_data(self,data):
        if self.hidden: return
        self.parts.append(data+' ')
        if self.anchor: self.anchor[1].append(data)
        if self.title: self.titles.append(data)

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,host,address):
        super().__init__(host,443,timeout=10,context=ssl.create_default_context()); self.address=address
    def connect(self):
        # Connect to a vetted numeric address without a second DNS lookup.
        family=socket.AF_INET6 if ':' in self.address else socket.AF_INET
        raw=socket.socket(family,socket.SOCK_STREAM); raw.settimeout(self.timeout)
        try:
            raw.connect((self.address,443))
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except BaseException: raw.close(); raise

def fetch(url,host,address):
    parts=urlsplit(url); conn=PinnedHTTPS(host,address)
    try:
        conn.request('GET',parts.path+('?' + parts.query if parts.query else ''),headers={
            'User-Agent':'KWOD-AI-Agent/1.0 (read-only research)',
            'Accept':'text/html,text/plain,application/json','Accept-Encoding':'identity','Connection':'close'})
        response=conn.getresponse()
        if response.status in (301,302,303,307,308):
            return response.status,{'location':response.getheader('Location','')},b''
        mime=response.getheader('Content-Type','').split(';')[0].lower().strip()
        if mime not in ('text/html','text/plain','application/json'): raise BrowserBlocked('unsupported_content')
        if response.getheader('Content-Encoding','identity').lower() not in ('','identity'):
            raise BrowserBlocked('unsupported_content')
        length=response.getheader('Content-Length')
        if length and (not length.isdigit() or int(length)>MAX_BODY): raise BrowserBlocked('response_limit')
        chunks=[]; size=0; deadline=time.monotonic()+20
        while size<=MAX_BODY:
            if time.monotonic()>deadline or stopped(): raise TimeoutError()
            chunk=response.read1(min(65536,MAX_BODY+1-size))
            if not chunk: break
            chunks.append(chunk); size+=len(chunk)
        body=b''.join(chunks)
        if len(body)>MAX_BODY: raise BrowserBlocked('response_limit')
        return response.status,{'mime':mime,'charset':response.headers.get_content_charset() or 'utf-8'},body
    finally: conn.close()

def resolve(host):
    return list(dict.fromkeys(item[4][0] for item in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))

class BrowserGateway:
    def __init__(self,*,resolver=resolve,fetcher=fetch,watchdog=None,blocked_addresses=(),enabled=lambda:Path('/etc/kwod-safety/BROWSER_ENABLED').exists()):
        self.resolver=resolver; self.fetcher=fetcher; self.watchdog=watchdog or SocketWatchdog()
        self.blocked_networks=[ipaddress.ip_network(x,strict=False) for x in blocked_addresses]; self.enabled=enabled
    def open(self,raw):
        trail=[]; deadline=time.monotonic()+45; failure_verdict=None
        try:
            if not self.enabled(): raise BrowserBlocked('capability_withheld')
            for hop in range(6):
                if stopped(): raise BrowserBlocked('review_required')
                if time.monotonic()>deadline: raise TimeoutError()
                url,host=normalize_url(raw); addresses=self.resolver(host)
                if not addresses or any(not public_address(x) or any(ipaddress.ip_address(x) in net for net in self.blocked_networks) for x in addresses):
                    # Observer records DNS-based LAN attempts before any connection.
                    failure_verdict=self.watchdog.evaluate({'kind':'browser_navigation','arguments':{'url':url,'addresses':addresses,'destination_blocked':True}})
                    raise BrowserBlocked('private_network_access')
                verdict=self.watchdog.evaluate({'kind':'browser_navigation','arguments':{'url':url,'addresses':addresses}})
                if verdict['decision']!='ALLOW': return {'ok':False,'safety':verdict,'watchdog_observed':True,'error':'safety_guard','external_effect':'not_started'}
                if stopped(): raise BrowserBlocked('review_required')
                status,headers,body=self.fetcher(url,host,addresses[0]); trail.append(url)
                if status in (301,302,303,307,308):
                    if not headers.get('location'): raise BrowserBlocked('invalid_arguments')
                    raw=urljoin(url,headers['location']); continue
                text=body.decode(headers.get('charset','utf-8'),errors='replace')
                links=[]; title=''
                if headers['mime']=='text/html':
                    page=PageText(); page.feed(text); text='\n'.join(line.strip() for line in ''.join(page.parts).splitlines() if line.strip())
                    title=' '.join(page.titles)[:300]
                    link_bytes=0
                    for link in page.links:
                        try: target,_=normalize_url(urljoin(url,link['url']))
                        except BrowserBlocked: continue
                        candidate={'url':target,'text':link['text']}
                        link_bytes+=len(json.dumps(candidate).encode())
                        if link_bytes>20000: break
                        links.append(candidate)
                        if len(links)>=80: break
                truncated=len(text)>MAX_TEXT
                while len(json.dumps(text[:MAX_TEXT]).encode())>60000:
                    text=text[:len(text)//2]; truncated=True
                return {'ok':True,'trust':'untrusted_external_content','url':url,'http_status':status,
                        'title':title,'text':text[:MAX_TEXT],'truncated':truncated,
                        'links':links,'redirects':trail[:-1],'content_sha256':hashlib.sha256(body).hexdigest(),
                        'capabilities':{'javascript':False,'forms':False,'cookies':False,'downloads':False}}
            raise BrowserBlocked('response_limit')
        except BrowserBlocked as error:
            if failure_verdict is None:
                failure_verdict=self.watchdog.evaluate({'kind':'browser_navigation','arguments':{'url':raw,'policy_block':error.category}})
            safety=failure_verdict if failure_verdict['decision']=='PAUSE_FOR_REVIEW' else {'decision':'PAUSE_FOR_REVIEW' if error.category=='review_required' else 'BLOCK','category':error.category}
            return {'ok':False,'error':'browser_blocked','watchdog_observed':True,'safety':safety}
        except (OSError,ValueError,http.client.HTTPException,LookupError):
            return {'ok':False,'error':'browser_fetch_failed'}

class BrowserClient:
    def __init__(self,path='/run/kwod-browser/browser.sock'): self.path=path
    def open(self,url):
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                conn.settimeout(70); conn.connect(self.path); conn.sendall(json.dumps({'url':url}).encode()+b'\n')
                with conn.makefile('rb') as stream: raw=stream.readline(131073)
            if len(raw)>131072: raise ValueError('oversized_browser_reply')
            result=json.loads(raw)
            if not isinstance(result,dict) or type(result.get('ok')) is not bool: raise ValueError('invalid_browser_reply')
            return result
        except (OSError,ValueError,AttributeError): return {'ok':False,'error':'browser_gateway_unavailable'}

def main():
    import pwd
    runtime=pwd.getpwnam('kwod-runtime').pw_uid
    blocked=json.loads(Path('/etc/kwod-browser/blocked-addresses.json').read_text())
    browser=BrowserGateway(blocked_addresses=blocked)
    class Handler(socketserver.StreamRequestHandler):
        def handle(self):
            self.request.settimeout(70)
            _,uid,_=struct.unpack('3i',self.request.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            if uid!=runtime: return
            try:
                raw=self.rfile.readline(8193)
                if len(raw)>8192 or not raw.endswith(b'\n'): raise ValueError('invalid_request')
                request=json.loads(raw)
                if not isinstance(request,dict) or set(request)!={'url'}: raise ValueError('invalid_request')
                result=browser.open(request['url'])
            except (ValueError,TypeError): result={'ok':False,'error':'invalid_browser_request'}
            self.wfile.write(json.dumps(result,ensure_ascii=False).encode()+b'\n')
    path=Path('/run/kwod-browser/browser.sock')
    if path.exists(): path.unlink()
    with socketserver.UnixStreamServer(str(path),Handler) as server:
        path.chmod(0o660); server.serve_forever()

if __name__=='__main__': main()
