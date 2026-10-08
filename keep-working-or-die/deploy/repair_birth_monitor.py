"""Repair only operator readiness access; no agent start, birth, payment or model API."""
import json
import os
from pathlib import Path
import stat
import subprocess
from kwod.store import atomic_write


def main():
    if os.geteuid()!=0: raise ValueError('sudo_required')
    path=Path('/etc/systemd/system/kwod-operator.service')
    info=path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid!=0 or stat.S_IMODE(info.st_mode)&0o022:
        raise ValueError('unsafe_operator_unit')
    raw=path.read_bytes()
    old=b'RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6'
    new=old+b' AF_NETLINK'
    lines=raw.splitlines(keepends=True)
    found=False
    for index,line in enumerate(lines):
        ending=b'\r\n' if line.endswith(b'\r\n') else b'\n' if line.endswith(b'\n') else b''
        value=line.rstrip(b'\r\n')
        if value==old:
            if found: raise ValueError('duplicate_address_family_rule')
            lines[index]=new+ending; found=True
        elif value==new:
            if found: raise ValueError('duplicate_address_family_rule')
            found=True
        elif value.startswith(b'RestrictAddressFamilies='):
            raise ValueError('unexpected_address_family_rule')
    if not found: raise ValueError('operator_address_family_rule_missing')
    # runuser requires these already-authorized root identity capabilities across
    # child execs. Do not disable NoNewPrivileges or the remaining sandbox.
    ambient=b'AmbientCapabilities=CAP_SETUID CAP_SETGID'
    ambient_lines=[line.rstrip(b'\r\n') for line in lines if line.startswith(b'AmbientCapabilities=')]
    if ambient_lines and ambient_lines!=[ambient]: raise ValueError('unexpected_ambient_capabilities')
    if not ambient_lines:
        for index,line in enumerate(lines):
            if line.rstrip(b'\r\n')==b'NoNewPrivileges=true':
                ending=b'\r\n' if line.endswith(b'\r\n') else b'\n'
                lines.insert(index+1,ambient+ending)
                break
        else: raise ValueError('operator_no_new_privileges_rule_missing')
    repaired=b''.join(lines)
    if repaired!=raw:
        backup=path.with_name('kwod-operator.service.before-netlink-repair')
        if not backup.exists(): atomic_write(backup,raw,0o600)
        atomic_write(path,repaired,stat.S_IMODE(info.st_mode))
    subprocess.run(['systemd-analyze','verify',str(path)],check=True)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    subprocess.run(['systemctl','restart','kwod-operator.service'],check=True)
    subprocess.run(['systemctl','is-active','--quiet','kwod-operator.service'],check=True)
    capabilities=subprocess.check_output(['systemctl','show','kwod-operator.service','--property=AmbientCapabilities','--value'],text=True).strip()
    if not {'cap_setuid','cap_setgid'}<=set(capabilities.lower().split()):
        raise ValueError('operator_identity_capabilities_not_loaded')
    print(json.dumps({'operator_restarted':True,'operator_netlink_check_allowed':True,'operator_identity_switch_capabilities':capabilities,
        'agent_network_rules_changed':False,'birth_by_repair':False,'worker_start_by_repair':False,
        'next':'Reload the operator monitor. Fresh OpenRouter balance and explicit birth confirmation remain required.'}))

if __name__=='__main__': main()
