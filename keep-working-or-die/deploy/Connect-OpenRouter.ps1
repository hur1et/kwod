[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340')
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'check_openrouter.py'
$digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$remote = ".kwod-incoming/openrouter-check-$digest.py"
$options = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
    '-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @options $SshTarget 'mkdir -p .kwod-incoming'
if ($LASTEXITCODE -ne 0) { throw 'SSH-Zugang fehlgeschlagen.' }
& scp @options $source "${SshTarget}:$remote"
if ($LASTEXITCODE -ne 0) { throw 'Upload fehlgeschlagen.' }
$verify = "import hashlib,pathlib; assert hashlib.sha256(pathlib.Path('$remote').read_bytes()).hexdigest()=='$digest'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verify))
& ssh @options $SshTarget "printf %s $encoded | base64 -d | python3"
if ($LASTEXITCODE -ne 0) { throw 'Upload-Pruefsumme stimmt nicht.' }
Write-Host 'Nur Key-Pruefung. Kein Modellaufruf, kein Guthabenkauf und kein Agentenstart.'
Write-Host 'Ubuntu fragt nach sudo und beim ersten Aufruf verdeckt nach dem normalen OpenRouter-Key.'
& ssh @options -t $SshTarget "sudo python3 $remote"
if ($LASTEXITCODE -ne 0) { throw 'OpenRouter-Key-Pruefung fehlgeschlagen; Fehlercode beachten.' }
Write-Host 'Key auf Ubuntu geschuetzt hinterlegt. Modellzugang und Kontoguthaben sind dadurch noch nicht bestaetigt.'
