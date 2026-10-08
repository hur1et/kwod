"""Runtime identity helper. No credentials or network; caller supplies evidence on stdin."""
import json
import sys
from kwod.birth import record_birth

if __name__=='__main__':
    raw=sys.stdin.buffer.read(65537)
    if len(raw)>65536: raise ValueError('evidence_too_large')
    print(json.dumps(record_birth('/var/lib/kwod-production',json.loads(raw))))
