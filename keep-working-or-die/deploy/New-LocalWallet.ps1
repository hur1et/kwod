[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340',
    [string]$BackupDirectory = (Join-Path $env:USERPROFILE 'KWOD-Wallet-Backup')
)
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot 'setup_local_wallet.py'
$digest = (Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant()
$remote = '.kwod-incoming/local-wallet-' + $digest + '.py'
$sshOptions = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
    '-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
$scpOptions = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
    '-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
$remoteUid = (& ssh @sshOptions $SshTarget 'id -u' | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $remoteUid -notmatch '^[1-9][0-9]*$') {
    throw 'SSH-Benutzer konnte nicht eindeutig ermittelt werden.'
}
if (-not (Test-Path -LiteralPath $BackupDirectory)) {
    New-Item -ItemType Directory -Path $BackupDirectory | Out-Null
}
$backupRoot = (Get-Item -LiteralPath $BackupDirectory).FullName
if (-not (Get-Item -LiteralPath $backupRoot).PSIsContainer) { throw 'Backup-Ziel ist kein Verzeichnis.' }
$localBackup = Join-Path $backupRoot ('wallet-' + [Guid]::NewGuid().ToString('N') + '.json')
& ssh @sshOptions $SshTarget 'mkdir -p .kwod-incoming'
if ($LASTEXITCODE -ne 0) { throw 'Upload-Verzeichnis konnte nicht vorbereitet werden.' }
& scp @scpOptions $installer "${SshTarget}:$remote"
if ($LASTEXITCODE -ne 0) { throw 'Upload fehlgeschlagen.' }
$verifyCode = "import hashlib,pathlib; assert hashlib.sha256(pathlib.Path('$remote').read_bytes()).hexdigest()=='$digest'"
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verifyCode))
& ssh @sshOptions $SshTarget "printf %s $encoded | base64 -d | python3"
if ($LASTEXITCODE -ne 0) { throw 'Upload-Pruefsumme stimmt nicht.' }
Write-Host 'Ubuntu fragt zuerst nach sudo, danach nach einem neuen Backup-Passwort.'
Write-Host 'Backup-Passwort sicher und getrennt von der Sicherungsdatei aufbewahren.'
& ssh @sshOptions -t $SshTarget "sudo python3 $remote"
if ($LASTEXITCODE -ne 0) { throw 'Einrichtung nicht abgeschlossen. Ein erneuter Aufruf ersetzt kein bestehendes Wallet.' }
$export = "/var/lib/kwod-wallet-export/$remoteUid/backup.json"
$hashLine = (& ssh @sshOptions $SshTarget "sha256sum $export" | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $hashLine -notmatch '^([a-f0-9]{64})\s+') { throw 'Backup-Pruefsumme fehlt.' }
$expectedHash = $Matches[1]
& scp @scpOptions "${SshTarget}:$export" $localBackup
if ($LASTEXITCODE -ne 0) { throw 'Backup-Download fehlgeschlagen; die Serverkopie bleibt erhalten.' }
if ((Get-FileHash -LiteralPath $localBackup -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
    throw 'Backup-Pruefsumme stimmt nicht. Diese lokale Kopie nicht verwenden.'
}
$backup = Get-Content -LiteralPath $localBackup -Raw | ConvertFrom-Json
if ($backup.version -ne 3 -or -not $backup.crypto -or $backup.address -notmatch '^[a-fA-F0-9]{40}$') {
    throw 'Unerwartetes Backup-Format.'
}
Write-Host "Verschluesselte Sicherung heruntergeladen und SHA256 geprueft: $localBackup"
Write-Host "Empfangsadresse: 0x$($backup.address)"
Write-Host 'Diese Datei auf den anderen Laptop kopieren. Passwort getrennt aufbewahren.'
Write-Host 'Noch keine Einzahlung: Zahlungsdienst und Compute-Nachkauf sind noch nicht angebunden.'
