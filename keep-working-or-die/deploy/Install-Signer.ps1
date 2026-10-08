[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340')
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'install_signer.py'
$program = Join-Path $PSScriptRoot '..\src\kwod\payments.py'
$installerHash = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$programHash = (Get-FileHash -LiteralPath $program -Algorithm SHA256).Hash.ToLowerInvariant()
$remoteInstaller = ".kwod-incoming/install-signer-$installerHash.py"
$remoteProgram = ".kwod-incoming/payments-$programHash.py"
$options = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
    '-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @options $SshTarget 'mkdir -p .kwod-incoming'
if ($LASTEXITCODE -ne 0) { throw 'SSH-Zugang fehlgeschlagen.' }
& scp @options $installer "${SshTarget}:$remoteInstaller"
if ($LASTEXITCODE -ne 0) { throw 'Installer-Upload fehlgeschlagen.' }
& scp @options $program "${SshTarget}:$remoteProgram"
if ($LASTEXITCODE -ne 0) { throw 'Programm-Upload fehlgeschlagen.' }
$verify = "import hashlib,pathlib; assert hashlib.sha256(pathlib.Path('$remoteInstaller').read_bytes()).hexdigest()=='$installerHash'; assert hashlib.sha256(pathlib.Path('$remoteProgram').read_bytes()).hexdigest()=='$programHash'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verify))
& ssh @options $SshTarget "printf %s $encoded | base64 -d | python3"
if ($LASTEXITCODE -ne 0) { throw 'Upload-Pruefsumme stimmt nicht.' }
& ssh @options -t $SshTarget "sudo python3 $remoteInstaller --source $remoteProgram --sha256 $programHash"
if ($LASTEXITCODE -ne 0) { throw 'Signer-Einrichtung nicht abgeschlossen; Ausgabe pruefen.' }
Write-Host 'Signierdienst im Pruefmodus installiert. Keine Zahlung freigeschaltet und kein Agent gestartet.'
