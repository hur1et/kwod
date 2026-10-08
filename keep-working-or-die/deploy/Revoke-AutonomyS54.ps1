[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget='s340')
$ErrorActionPreference='Stop'
& ssh -o StrictHostKeyChecking=yes -o ForwardAgent=no -o ClearAllForwardings=yes -t $SshTarget 'sudo /opt/kwod/current/.venv/bin/python /opt/kwod/current/deploy/revoke_s54.py'
if ($LASTEXITCODE -ne 0) { throw 'Ruecknahme nicht vollstaendig. Worker gestoppt lassen und Serverausgabe beachten.' }
