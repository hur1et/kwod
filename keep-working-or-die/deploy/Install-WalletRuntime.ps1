[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340'
)
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'install_wallet_runtime.py'
$digest = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$remote = '.kwod-incoming/wallet-runtime-' + $digest + '.py'
$sshOptions = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
    '-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @sshOptions $SshTarget 'mkdir -p .kwod-incoming'
if ($LASTEXITCODE -ne 0) { throw 'SSH-Zugang fehlgeschlagen.' }
& scp -o StrictHostKeyChecking=yes -o ForwardAgent=no $installer "${SshTarget}:$remote"
if ($LASTEXITCODE -ne 0) { throw 'Upload fehlgeschlagen.' }
$verifyCode = "import hashlib,pathlib; assert hashlib.sha256(pathlib.Path('$remote').read_bytes()).hexdigest()=='$digest'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verifyCode))
& ssh @sshOptions $SshTarget "printf %s $encoded | base64 -d | python3"
if ($LASTEXITCODE -ne 0) { throw 'Upload-Pruefsumme stimmt nicht.' }
& ssh @sshOptions -t $SshTarget "sudo python3 $remote"
if ($LASTEXITCODE -ne 0) { throw 'Wallet-Laufzeit konnte nicht eingerichtet werden. Ausgabe pruefen.' }
Write-Host 'Wallet-Laufzeit bereit. Keine Anmeldung, keine Einzahlung, kein Agentenstart.'
