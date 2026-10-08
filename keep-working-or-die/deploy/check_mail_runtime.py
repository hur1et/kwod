"""Read-only mailbox smoke test under the kwod-runtime identity."""
import json
import os
import sys


def main():
    if os.geteuid() == 0:
        raise ValueError('must_run_as_runtime_user')
    from kwod.mail_gateway import MailboxGateway
    messages = MailboxGateway().list_unread(limit=100)
    print(json.dumps({'mailbox_gateway': 'reachable', 'unread_count': len(messages),
                      'message_contents_read': False, 'message_sent': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('{"ok":false,"error":"mail_runtime_check_failed"}', file=sys.stderr)
        sys.exit(1)
