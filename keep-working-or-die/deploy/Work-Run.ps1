[CmdletBinding()]
param(
    [ValidateSet('Trial01','Pilot02','OfflineCheck')][string]$Run = 'Pilot02',
    [ValidateSet('Status','Stop','Start')][string]$Action = 'Status',
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340'
)
$ErrorActionPreference = 'Stop'
$arguments = @{ SshTarget = $SshTarget; Pilot = ($Run -eq 'Pilot02'); MonitorCheck = ($Run -eq 'OfflineCheck') }
if ($Action -eq 'Status') { $arguments.Status = $true }
elseif ($Action -eq 'Stop') { $arguments.StopAndInspect = $true }
else { Write-Host 'Start verwendet den einmaligen Laufmarker. Vorhandene Laeufe werden nicht wiederholt.' }
& (Join-Path $PSScriptRoot 'Test-WorkTrial.ps1') @arguments
