import re
import sys
from kwod.store import Store, worker_lock

if len(sys.argv) != 3 or not re.fullmatch(r'dev-[0-9]{8}-[0-9]{6}-[a-f0-9]{8}', sys.argv[1]):
    raise ValueError('invalid deployment identity')
if not re.fullmatch('sha256:[a-f0-9]{64}', sys.argv[2]):
    raise ValueError('invalid executor image')
store = Store('/var/lib/kwod')
try:
    with worker_lock(store.root), store.transaction():
        store.event('deployment_observed', {'release': sys.argv[1], 'built_executor_image': sys.argv[2],
                    'note': 'Existing instance configuration and image selection remain unchanged.'})
finally:
    store.close()
