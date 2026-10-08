[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340', [switch]$OfficialClient)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression
$stream = New-Object System.IO.MemoryStream
$archive = [System.IO.Compression.ZipArchive]::new($stream, [System.IO.Compression.ZipArchiveMode]::Create, $true)
$files = @{
    '__main__.py' = (Join-Path $PSScriptRoot 'auth_capture_selftest.py')
    'kwod/payments.py' = (Join-Path $PSScriptRoot '..\src\kwod\payments.py')
    'kwod/auth_capture.py' = (Join-Path $PSScriptRoot '..\src\kwod\auth_capture.py')
    'kwod/auth_capture_signing.py' = (Join-Path $PSScriptRoot '..\src\kwod\auth_capture_signing.py')
}
if ($OfficialClient) {
    $files['__main__.py'] = Join-Path $PSScriptRoot 'auth_capture_compare.py'
    $files['compare.mjs'] = Join-Path $PSScriptRoot 'auth_capture_official.mjs'
}
try {
    $archive.CreateEntry('kwod/__init__.py') | Out-Null
    foreach ($name in $files.Keys) {
        $entry = $archive.CreateEntry($name)
        $entryStream = $entry.Open()
        try {
            $bytes = [IO.File]::ReadAllBytes($files[$name])
            $entryStream.Write($bytes, 0, $bytes.Length)
        } finally { $entryStream.Dispose() }
    }
} finally { $archive.Dispose() }
$bundle = Join-Path ([IO.Path]::GetTempPath()) ('kwod-crypto-test-' + [guid]::NewGuid().ToString('N') + '.pyz')
try {
    [IO.File]::WriteAllBytes($bundle, $stream.ToArray())
    $launcher = Join-Path $PSScriptRoot 'run_auth_capture_selftest.py'
    if ($OfficialClient) { $launcher = Join-Path $PSScriptRoot 'run_auth_capture_compare.py' }
    $bundleHash = (Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant()
    $launcherHash = (Get-FileHash -LiteralPath $launcher -Algorithm SHA256).Hash.ToLowerInvariant()
    $remoteBundle = ".kwod-incoming/crypto-test-$bundleHash.pyz"
    $remoteLauncher = ".kwod-incoming/crypto-test-$launcherHash.py"
    $options = @('-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15',
        '-o','ForwardAgent=no','-o','ForwardX11=no','-o','ClearAllForwardings=yes')
    & ssh @options $SshTarget 'mkdir -p .kwod-incoming'
    if ($LASTEXITCODE -ne 0) { throw 'SSH-Zugang fehlgeschlagen.' }
    & scp @options $bundle "${SshTarget}:$remoteBundle"
    if ($LASTEXITCODE -ne 0) { throw 'Test-Upload fehlgeschlagen.' }
    & scp @options $launcher "${SshTarget}:$remoteLauncher"
    if ($LASTEXITCODE -ne 0) { throw 'Launcher-Upload fehlgeschlagen.' }
    $verify = "import hashlib,pathlib; assert hashlib.sha256(pathlib.Path('$remoteLauncher').read_bytes()).hexdigest()=='$launcherHash'; assert hashlib.sha256(pathlib.Path('$remoteBundle').read_bytes()).hexdigest()=='$bundleHash'"
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($verify))
    & ssh @options $SshTarget "printf %s $encoded | base64 -d | python3"
    if ($LASTEXITCODE -ne 0) { throw 'Upload-Pruefsumme stimmt nicht.' }
    & ssh @options -t $SshTarget "sudo python3 $remoteLauncher $remoteBundle $bundleHash"
    if ($LASTEXITCODE -ne 0) { throw 'Kryptografietest fehlgeschlagen; Ausgabe pruefen.' }
    Write-Host 'Test abgeschlossen. Keine Dienstinstallation und keine echte Zahlung.'
} finally {
    $stream.Dispose()
    if (Test-Path -LiteralPath $bundle) { Remove-Item -LiteralPath $bundle }
}
