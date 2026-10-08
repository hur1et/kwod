[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]*$')][string]$SshTarget = 's340',
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^https://payments\.coinbase\.com/payment-sessions/paymentSession_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
    [string]$CheckoutUrl
)
$ErrorActionPreference = 'Stop'
$session = $CheckoutUrl.Split('/')[-1]
$source = Join-Path $PSScriptRoot 'check_checkout.py'
$digest = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$remote = ".kwod-incoming/checkout-$digest.py"
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
& ssh @options $SshTarget "python3 $remote $session"
if ($LASTEXITCODE -ne 0) { throw 'Checkout-Pruefung fehlgeschlagen; Abschlussausgabe pruefen.' }
Write-Host 'Zahlungsanforderung gelesen. Kein Schluessel gelesen, keine Freigabe und keine Zahlung.'
