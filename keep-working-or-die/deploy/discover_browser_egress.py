"""Discover the current public IPv4 address for NAT loopback exclusion."""
import ipaddress
import json
from kwod.browser_gateway import BrowserClient
from kwod.browser_policy import public_address

result=BrowserClient().open('https://api.ipify.org/?format=json')
if not result.get('ok') or result.get('http_status')!=200: raise SystemExit('public_egress_detection_failed')
try:
    address=str(ipaddress.ip_address(json.loads(result['text'])['ip']))
    if not public_address(address): raise ValueError('not_public')
except (ValueError,KeyError,TypeError): raise SystemExit('public_egress_detection_invalid')
print(json.dumps({'public_egress_address':address}))
