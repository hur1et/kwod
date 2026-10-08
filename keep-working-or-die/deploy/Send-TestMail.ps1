[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340')
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'send_mail_probe.py'
$digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$remote = ".kwod-incoming/mail-probe-$digest.py"
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
$temporary = "/tmp/kwod-mail-probe-$digest.py"
$command = "sudo install -o kwod-runtime -g kwod-workspace -m 0644 $remote $temporary && sudo -u kwod-runtime env PYTHONPATH=/opt/kwod/current/src /opt/kwod/current/.venv/bin/python $temporary && sudo rm -f $temporary"
Write-Host 'Einmalige Probemail an julius.weiske@gmx.de. Kein Birth oder Agentenworker. Die Versandpruefung kann einen kostenpflichtigen Modellaufruf verwenden.'
& ssh @options -t $SshTarget $command
if ($LASTEXITCODE -ne 0) { throw 'Probemail nicht eindeutig abgeschlossen. Posteingang pruefen; nicht blind wiederholen.' }
