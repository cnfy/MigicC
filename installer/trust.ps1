param([ValidateSet('Import','Remove')][string]$Action = 'Import')
$ErrorActionPreference = 'Stop'
try {
    $certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (Join-Path $PSScriptRoot 'MagicC.cer')
    if ($certificate.Subject -ne 'CN=MagicC Local Build') { throw 'Unexpected certificate publisher.' }
    $path = "Cert:\LocalMachine\TrustedPeople\$($certificate.Thumbprint)"
    if ($Action -eq 'Import') {
        if (-not (Test-Path -LiteralPath $path)) {
            Import-Certificate -FilePath (Join-Path $PSScriptRoot 'MagicC.cer') -CertStoreLocation 'Cert:\LocalMachine\TrustedPeople' | Out-Null
        }
    } elseif (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path
    }
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
