[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340')
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'check_nonfinancial_readiness.py'
$digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$remote = ".kwod-incoming/nonfinancial-readiness-$digest.py"
$temporary = "/tmp/kwod-nonfinancial-readiness-$digest.py"
$options = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @options $SshTarget 'mkdir -p .kwod-incoming'
if ($LASTEXITCODE -ne 0) { throw 'SSH-Zugang fehlgeschlagen.' }
& scp @options $source "${SshTarget}:$remote"
if ($LASTEXITCODE -ne 0) { throw 'Upload fehlgeschlagen.' }
$verify = "import hashlib,pathlib; assert hashlib.sha256(pathlib.Path('$remote').read_bytes()).hexdigest()=='$digest'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verify))
& ssh @options $SshTarget "printf %s $encoded | base64 -d | python3"
if ($LASTEXITCODE -ne 0) { throw 'Upload-Pruefsumme stimmt nicht.' }
$command = "sudo install -o root -g root -m 0644 $remote $temporary; sudo python3 $temporary && sudo rm -f $temporary"
& ssh @options -t $SshTarget $command
if ($LASTEXITCODE -ne 0) { throw 'Nichtfinanzielle Vorpruefung fehlgeschlagen.' }
