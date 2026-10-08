[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget='s340')
$ErrorActionPreference='Stop'
$options=@('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no',
    '-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @options -t $SshTarget 'sudo python3 /opt/kwod/current/deploy/prepare_world.py'
if ($LASTEXITCODE -ne 0) { throw 'Vorbereitung nicht abgeschlossen. Serverausgabe beachten. Kein automatischer Workerstart.' }
