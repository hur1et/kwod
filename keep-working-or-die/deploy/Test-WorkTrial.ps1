[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340', [switch]$Diagnose, [switch]$ResumeUnstarted, [switch]$CheckProvider, [switch]$ResumeRejected, [switch]$StopAndInspect, [switch]$Pilot, [switch]$Status, [switch]$MonitorCheck)
$ErrorActionPreference = 'Stop'
if ($MonitorCheck -and ($Pilot -or $Diagnose -or $ResumeUnstarted -or $ResumeRejected -or $CheckProvider)) { throw 'Offline-Prueflauf nicht mit Pilot-/Provider-/Resume-Modi kombinieren.' }
if ($Pilot -and ($ResumeUnstarted -or $ResumeRejected)) { throw 'Pilot nicht mit alten Resume-Modi kombinieren.' }
if (([int]$Diagnose.IsPresent + [int]$ResumeUnstarted.IsPresent + [int]$CheckProvider.IsPresent + [int]$ResumeRejected.IsPresent + [int]$StopAndInspect.IsPresent + [int]$Status.IsPresent) -gt 1) { throw 'Nur einen Modus waehlen.' }
$source = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $PSScriptRoot '..\..\.venv\Scripts\python.exe'
$bundle = Join-Path $source 'dist\kwod-work-trial.tar.gz'
$digest = 'unused'
if (-not ($Status -or $StopAndInspect)) {
    $built = & $python (Join-Path $PSScriptRoot 'bundle.py') --source $source --output $bundle
    if ($LASTEXITCODE -ne 0) { throw 'Paketbau fehlgeschlagen.' }
    $digest = ($built | ConvertFrom-Json).sha256
    if ($digest -notmatch '^[a-f0-9]{64}$') { throw 'Ungueltiger Paket-Hash.' }
}
$launcher = Join-Path $PSScriptRoot 'run_work_trial.py'
$launcherHash = (Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant()
$remoteBundle = ".kwod-incoming/work-trial-$digest.tar.gz"
$remoteLauncher = ".kwod-incoming/work-trial-$launcherHash.py"
$options = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
    '-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
& ssh @options $SshTarget 'mkdir -p .kwod-incoming'
if ($LASTEXITCODE -ne 0) { throw 'SSH-Zugang fehlgeschlagen.' }
if (-not ($Status -or $StopAndInspect)) {
    & scp @options $bundle "${SshTarget}:$remoteBundle"
    if ($LASTEXITCODE -ne 0) { throw 'Paket-Upload fehlgeschlagen.' }
}
& scp @options $launcher "${SshTarget}:$remoteLauncher"
if ($LASTEXITCODE -ne 0) { throw 'Launcher-Upload fehlgeschlagen.' }
$verify = "import hashlib,pathlib; assert hashlib.sha256(pathlib.Path('$remoteLauncher').read_bytes()).hexdigest()=='$launcherHash'"
if (-not ($Status -or $StopAndInspect)) { $verify += "; assert hashlib.sha256(pathlib.Path('$remoteBundle').read_bytes()).hexdigest()=='$digest'" }
$encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verify))
& ssh @options $SshTarget "printf %s $encoded | base64 -d | python3"
if ($LASTEXITCODE -ne 0) { throw 'Upload-Pruefsumme stimmt nicht.' }
$diagnoseArg = ''
if ($Status) {
    $diagnoseArg = ' --status'
    Write-Host 'Gespeicherten Status lesen. Kein Stop, Start oder Modellaufruf.'
} elseif ($StopAndInspect) {
    $diagnoseArg = ' --stop-inspect'
    Write-Host 'Trial beenden und gespeicherten Status lesen. Kein neuer Modellaufruf.'
} elseif ($Diagnose) {
    $diagnoseArg = ' --diagnose'
    Write-Host 'Nur Zugriffsdiagnose und gespeicherter Laufstatus. Kein Modellaufruf, kein Schluesselinhalt.'
} elseif ($CheckProvider) {
    $diagnoseArg = ' --check-provider'
    Write-Host 'Nur Modell-/Routenmetadaten von OpenRouter lesen. Kein Modellaufruf oder Trial-Neustart.'
} elseif ($MonitorCheck) {
    Write-Host 'Offline-Prueflauf: nur feste Testantworten, kein Schluessel und kein Netzwerk; rund 45 Sekunden.'
} else {
    if ($ResumeUnstarted) { $diagnoseArg = ' --resume-unstarted' }
    if ($ResumeRejected) { $diagnoseArg = ' --resume-rejected' }
    Write-Host 'Echter OpenRouter-Probelauf: hoechstens 6 Modellaufrufe, je 2048 Output-Tokens.'
    Write-Host 'Nutzt das vorhandene Guthaben. Kein Nachkauf, keine Veroeffentlichung, kein Produktionsstart.'
}
if ($Pilot) { $diagnoseArg += ' --pilot'; Write-Host 'Ausgewaehlter Lauf: Pilot02.' }
if ($MonitorCheck) { $diagnoseArg += ' --monitor-check'; Write-Host 'Ausgewaehlter Lauf: Offline-Prueflauf.' }
& ssh @options -t $SshTarget "sudo python3 $remoteLauncher $remoteBundle $digest$diagnoseArg"
if ($LASTEXITCODE -ne 0) { throw 'Probelauf gestoppt. Ausgabe pruefen; nicht erneut starten, um weitere Aufrufe zu erzwingen.' }
Write-Host 'Aktion beendet. Die JSON-Zusammenfassung zeigt den beobachteten Stand.'
if ($MonitorCheck) { Write-Host 'Testdateien: /var/lib/kwod-work-monitor-check/.' }
elseif ($Pilot) { Write-Host 'Dateien und Verbrauchsangaben: /var/lib/kwod-work-pilot-02/.' }
else { Write-Host 'Dateien und Verbrauchsangaben: /var/lib/kwod-work-trial-01/.' }
