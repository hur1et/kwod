[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340',
    [ValidateSet('Check','Install')][string]$Action = 'Check',
    [string]$Python = (Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'),
    [switch]$InstallPrerequisites
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
foreach ($command in @('ssh','scp')) { $null = Get-Command $command -ErrorAction Stop }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Python nicht gefunden; -Python mit dem Pfad zu Python 3.12 angeben.' }
$release = 'dev-' + [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss') + '-' + ([guid]::NewGuid().ToString('N').Substring(0,8))
$bundle = Join-Path $source ('dist\' + $release + '.tar.gz')
$built = & $Python (Join-Path $PSScriptRoot 'bundle.py') --source $source --output $bundle
if ($LASTEXITCODE -ne 0) { throw 'Release-Paket konnte nicht gebaut werden.' }
$metadata = $built | ConvertFrom-Json
$digest = $metadata.sha256
if ($digest -notmatch '^[a-f0-9]{64}$') { throw 'Ungueltiger Paket-Hash.' }
# Honor the user's SSH alias, key agent, configured user and port. Never disable host-key checks.
$sshOptions = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @sshOptions $SshTarget 'mkdir -p .kwod-incoming'
if ($LASTEXITCODE -ne 0) { throw 'SSH-Zugang fehlgeschlagen. Alias und bekannten Host-Schluessel im eigenen Terminal pruefen.' }
& scp -o StrictHostKeyChecking=yes -o ForwardAgent=no $bundle "${SshTarget}:.kwod-incoming/$release.tar.gz"
if ($LASTEXITCODE -ne 0) { throw 'Upload fehlgeschlagen.' }
$remoteArchive = ".kwod-incoming/$release.tar.gz"
$remoteSource = ".kwod-incoming/$release"
# All interpolated remote values are generated locally from a fixed alphabet.
$verifyCode = "import hashlib,pathlib; p=pathlib.Path('$remoteArchive'); assert hashlib.sha256(p.read_bytes()).hexdigest()=='$digest'"
$verifyEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verifyCode))
$verify = "printf %s $verifyEncoded | base64 -d | python3"
& ssh @sshOptions $SshTarget $verify
if ($LASTEXITCODE -ne 0) { throw 'Upload-Hash stimmt nicht ueberein.' }
$extractCode = "import pathlib,tarfile; p=pathlib.Path('$remoteSource'); p.mkdir(); tarfile.open('$remoteArchive').extractall(p,filter='data')"
$extractEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($extractCode))
$extract = "printf %s $extractEncoded | base64 -d | python3"
& ssh @sshOptions $SshTarget $extract
if ($LASTEXITCODE -ne 0) { throw 'Sicheres Entpacken fehlgeschlagen; Python 3.12 erforderlich.' }
$remoteCommand = "python3 $remoteSource/deploy/install_ubuntu.py --source $remoteSource --release $release --action $($Action.ToLower())"
if ($Action -eq 'Install') {
    $remoteCommand = 'sudo ' + $remoteCommand
    if ($InstallPrerequisites) { $remoteCommand += ' --install-prerequisites' }
    & ssh @sshOptions -t $SshTarget $remoteCommand
} else {
    & ssh @sshOptions $SshTarget $remoteCommand
}
if ($LASTEXITCODE -ne 0) { throw 'Ubuntu-Pruefung/Installation nicht erfolgreich. Remote-Ausgabe beachten.' }
Write-Host "Fertig: $Action / $release / SHA256 $digest"
Write-Host 'Kein API-Key wurde uebertragen, kein Modell-Worker gestartet und kein Birth-Event erzeugt.'
