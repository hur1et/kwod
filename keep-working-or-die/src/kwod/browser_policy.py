"""URL and destination policy shared by gateway and independent observer."""
import ipaddress
import re
from urllib.parse import urlsplit,urlunsplit,quote

class BrowserBlocked(ValueError):
    def __init__(self,category): super().__init__(category); self.category=category

TRANSITION=tuple(ipaddress.ip_network(x) for x in ('64:ff9b::/96','64:ff9b:1::/48','2002::/16','2001::/32'))

def public_address(raw):
    address=ipaddress.ip_address(raw)
    return address.is_global and not address.is_multicast and not (
        address.version==6 and (address.ipv4_mapped or any(address in net for net in TRANSITION)))

def normalize_url(raw):
    if not isinstance(raw,str) or len(raw)>4096 or any(ord(c)<33 or ord(c)==127 for c in raw) or '\\' in raw:
        raise BrowserBlocked('invalid_arguments')
    try:
        parts=urlsplit(raw)
        if parts.scheme!='https' or parts.username is not None or parts.password is not None or parts.port not in (None,443):
            raise BrowserBlocked('capability_withheld')
        host=(parts.hostname or '').rstrip('.').encode('idna').decode('ascii').lower()
        if not host or '%' in host: raise BrowserBlocked('invalid_arguments')
        try:
            if not public_address(host): raise BrowserBlocked('private_network_access')
        except ValueError as error:
            if isinstance(error,BrowserBlocked): raise
            if not re.fullmatch(r'[a-z0-9.-]+',host) or '..' in host: raise BrowserBlocked('invalid_arguments')
            if '.' not in host or host.endswith(('.local','.localhost','.internal','.lan','.home','.onion')):
                raise BrowserBlocked('private_network_access')
        authority='['+host+']' if ':' in host else host
        return urlunsplit(('https',authority,quote(parts.path or '/',safe='/%:@!$&\'()*+,;=-._~'),quote(parts.query,safe='%=&/:?@!$\'()*+,;~-._'),'')),host
    except (ValueError,UnicodeError) as error:
        if isinstance(error,BrowserBlocked): raise
        raise BrowserBlocked('invalid_arguments') from None
