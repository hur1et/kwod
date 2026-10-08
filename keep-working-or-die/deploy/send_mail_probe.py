"""One explicitly authorized operator probe. No model call or production birth."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from kwod.mail_gateway import MailboxGateway
from kwod.mail_channel import build_outbound

marker = Path('/var/lib/kwod/private/operator-mail-probe-01.json')
recipient = 'julius.weiske@gmx.de'
def main():
    if os.geteuid() == 0:
        raise ValueError('must_run_as_runtime_user')
    gateway = MailboxGateway()
    raw = build_outbound(sender=gateway._config()['address'], recipient=recipient,
        subject='KWOD Probemail vor dem Start',
        text=('Hallo Julius,\n\n'
              'dies ist die von dir angeforderte technische Probemail des KWOD-Mailkanals. '
              'Sie wird ueber das auf Ubuntu hinterlegte Agentenpostfach versendet.\n\n'
              'Der Agent ist noch nicht geboren und der Modellworker wurde fuer diesen Test nicht gestartet. '
              'Diese Nachricht ist vorgegeben und wurde nicht vom Modell formuliert. '
              'Die erste selbst formulierte Orientierungsmail folgt erst nach deinem spaeteren Start.\n\n'
              'Viele Gruesse\nKWOD Mailkanal'),
        idempotency_key='operator-mail-probe-01')
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(json.dumps({'probe': 'already_attempted', 'new_message_sent': False,
                          'automatic_retry': False, 'marker': str(marker)}))
        return
    with os.fdopen(fd, 'w') as stream:
        json.dump({'status': 'started_outcome_may_be_unknown', 'recipient': recipient,
                   'started_at': datetime.now(timezone.utc).isoformat()}, stream)
        stream.flush(); os.fsync(stream.fileno())
    try:
        delivery = gateway.send(raw)
    except Exception:
        print(json.dumps({'probe': 'send_outcome_unknown', 'automatic_retry': False,
                          'check_recipient_inbox': True}))
        raise SystemExit(1)
    if not delivery.get('sent'):
        print(json.dumps({'probe':'not_sent','delivery':delivery,'automatic_retry':False}))
        raise SystemExit(1)
    with marker.open('w') as stream:
        json.dump({'status': 'smtp_accepted', 'recipient': recipient,
                   'delivery': delivery}, stream)
        stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({'probe': 'smtp_accepted', 'recipient': recipient,
                      'delivery_to_inbox_verified': False, 'agent_model_calls': 0,
                      'reviewer_model_call_may_have_occurred': True,
                      'birth_triggered_by_probe': False, 'automatic_retry': False}))

if __name__ == '__main__':
    main()
