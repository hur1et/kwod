"""Root-owned operator stop and a separate, tool-free reviewer connection."""
import json
from pathlib import Path
import socket

STOP_FILE=Path('/etc/kwod-safety/STOP')
WATCHDOG_PAUSE=Path('/etc/kwod-safety/WATCHDOG_PAUSE')
def stopped():
    for path in (STOP_FILE,WATCHDOG_PAUSE):
        try: path.lstat(); return True
        except FileNotFoundError: pass
        except OSError: return True
    return False

class SocketReviewer:
    def __init__(self,path='/run/kwod-mail-safety/gate.sock'):
        self.path=path
    def __call__(self, message):
        if stopped(): return {'decision':'PAUSE_FOR_REVIEW','category':'operator_safety_stop'}
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as conn:
                conn.settimeout(45); conn.connect(self.path)
                conn.sendall(json.dumps(message).encode()+b'\n')
                with conn.makefile('rb') as stream:
                    raw=stream.readline(4097)
                if len(raw)>4096: raise ValueError('oversized_gate_reply')
                result=json.loads(raw)
            if result['decision'] not in ('ALLOW','BLOCK','PAUSE_FOR_REVIEW'):
                raise ValueError('invalid_gate_decision')
            if result.get('category') not in ('none','threat_or_coercion','fraud_or_impersonation',
                    'private_data_or_secrets','unauthorized_access','uncertain'):
                raise ValueError('invalid_gate_category')
            return result
        except (OSError,ValueError,KeyError,AttributeError):
            return {'decision':'PAUSE_FOR_REVIEW','category':'safety_gate_unavailable'}
