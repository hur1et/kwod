[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget='s340')
$ErrorActionPreference='Stop'
$options=@('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @options -t $SshTarget 'sudo /opt/kwod/current/.venv/bin/python /opt/kwod/current/deploy/prepare_s54.py'
if ($LASTEXITCODE -ne 0) { throw 'S5.4 nicht vollstaendig vorbereitet. Worker bleibt gestoppt; Serverausgabe beachten.' }
