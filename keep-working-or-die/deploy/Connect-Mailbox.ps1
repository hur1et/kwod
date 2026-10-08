[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340')
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'check_mailbox.py'
$digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$remote = ".kwod-incoming/mailbox-check-$digest.py"
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
Write-Host 'GMX-Zugang wird verdeckt auf Ubuntu abgefragt. Es wird keine Nachricht versendet.'
& ssh @options -t $SshTarget "sudo python3 $remote"
if ($LASTEXITCODE -ne 0) { throw 'GMX-Zugang konnte nicht verifiziert werden.' }
Write-Host 'GMX-Zugang auf Ubuntu geschuetzt hinterlegt.'
