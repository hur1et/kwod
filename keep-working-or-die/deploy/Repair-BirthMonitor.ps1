[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget='s340')
$ErrorActionPreference='Stop'
$options=@('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& scp (Join-Path $PSScriptRoot 'repair_birth_monitor.py') "${SshTarget}:kwod-repair-birth-monitor.py"
if ($LASTEXITCODE -ne 0) { throw 'Reparaturskript konnte nicht uebertragen werden.' }
& ssh @options -t $SshTarget 'sudo /opt/kwod/current/.venv/bin/python ./kwod-repair-birth-monitor.py'
if ($LASTEXITCODE -ne 0) { throw 'Operator-Reparatur nicht abgeschlossen. Serverausgabe beachten.' }
