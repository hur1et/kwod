[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget='s340')
$ErrorActionPreference='Stop'
$options=@('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
# Only this fixed diagnostic is uploaded. No release installation or runtime change.
& scp (Join-Path $PSScriptRoot 'diagnose_birth_reader.py') "${SshTarget}:kwod-birth-reader-diagnostic.py"
if ($LASTEXITCODE -ne 0) { throw 'Diagnose konnte nicht uebertragen werden.' }
& ssh @options -t $SshTarget 'sudo python3 ./kwod-birth-reader-diagnostic.py'
if ($LASTEXITCODE -ne 0) { throw 'Diagnose nicht abgeschlossen. Serverausgabe beachten.' }
