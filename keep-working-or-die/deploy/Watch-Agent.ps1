[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340',
    [ValidateRange(1024,65535)][int]$LocalPort = 8765
)
$ErrorActionPreference = 'Stop'
if ($LocalPort -eq 8766) { throw 'Port 8766 ist fuer die geschuetzte Birth-Steuerung reserviert.' }
$sshExe = (Get-Command ssh.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
# Do not inherit backgrounding or a multiplexed connection from the SSH alias.
# Otherwise ssh can return successfully while this terminal owns no tunnel.
$options = @('-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no','-o','ForwardX11=no',
    '-o','ForkAfterAuthentication=no','-o','ControlMaster=no','-o','ControlPath=none',
    '-o','ControlPersist=no','-o','ExitOnForwardFailure=yes','-o','ConnectTimeout=15',
    '-o','ServerAliveInterval=30','-o','ServerAliveCountMax=3')
$effective = & $sshExe -G @options $SshTarget
if ($LASTEXITCODE -ne 0) { throw 'SSH-Konfiguration konnte nicht gelesen werden.' }
if ($effective | Where-Object { $_ -match '^(remote|local|dynamic)forward\s' }) {
    throw 'Bitte einen SSH-Alias ohne vorkonfigurierte Portweiterleitungen verwenden.'
}
Write-Host "Statusansicht: http://127.0.0.1:$LocalPort"
Write-Host 'Birth-Steuerung: http://127.0.0.1:8766 (Benutzer operator, eigenes Passwort)'
Write-Host 'Dieses Terminal offen lassen. Strg+C beendet den Beobachtungstunnel.'
# Local forwarding only. No agent forwarding, reverse tunnel, X11 or remote shell.
& $sshExe -N -T @options -L "127.0.0.1:${LocalPort}:127.0.0.1:8000" -L '127.0.0.1:8766:127.0.0.1:8001' $SshTarget
if ($LASTEXITCODE -ne 0) { throw 'SSH-Tunnel beendet; SSH-Zugang und lokalen Port pruefen.' }
Write-Warning 'SSH ist beendet. Dieses Terminal haelt keinen Beobachtungstunnel mehr offen.'
