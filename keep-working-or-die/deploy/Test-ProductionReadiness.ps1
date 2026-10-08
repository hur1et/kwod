[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget='s340')
$ErrorActionPreference='Stop'
$options=@('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @options -t $SshTarget 'sudo /opt/kwod/current/.venv/bin/python /opt/kwod/current/deploy/check_production_readiness.py'
if ($LASTEXITCODE -ne 0) { throw 'Installierter Produktionszustand noch nicht bereit. Blocker in JSON beachten.' }
