[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget='s340')
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'diagnose_workspace.py'
$digest=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$remote="kwod-workspace-diagnostic-$digest.py"
$options=@('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& scp @options $source "${SshTarget}:$remote"
if ($LASTEXITCODE -ne 0) { throw 'Workspace-Diagnose konnte nicht uebertragen werden.' }
& ssh @options -t $SshTarget "sudo python3 ./$remote"
if ($LASTEXITCODE -ne 0) { throw 'Workspace-Diagnose nicht abgeschlossen.' }
