param([ValidateSet('Register','Unregister','Install','Uninstall')][string]$Action = 'Register', [switch]$TrustLocalCertificate)
$ErrorActionPreference = 'Stop'
$installRoot = $PSScriptRoot
$marker = Join-Path $installRoot 'modern-menu.enabled'
$certificateMarker = Join-Path $installRoot 'certificate.imported'
function Update-Certificate([string]$operation) {
    $arguments = '-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + (Join-Path $installRoot 'trust.ps1') + '" -Action ' + $operation
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal $identity
    if ($principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WindowStyle Hidden -Wait -PassThru
    } else {
        $process = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -Verb RunAs -WindowStyle Hidden -Wait -PassThru
    }
    if ($process.ExitCode -ne 0) { throw 'Certificate trust update failed.' }
}
try {
    if ($Action -in 'Unregister','Uninstall') {
        Get-AppxPackage -Name 'MagicC.Desktop' | Remove-AppxPackage
        if (Test-Path -LiteralPath $marker) { Remove-Item -LiteralPath $marker }
        if ($Action -eq 'Uninstall' -and (Test-Path -LiteralPath $certificateMarker)) {
            $thumbprint = (Get-Content -LiteralPath $certificateMarker -Raw).Trim()
            if ($thumbprint -match '^[0-9A-F]{40}$') {
                Update-Certificate 'Remove'
            }
            Remove-Item -LiteralPath $certificateMarker
        }
    } else {
        if ($TrustLocalCertificate) {
            $certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (Join-Path $installRoot 'MagicC.cer')
            $certificatePath = "Cert:\LocalMachine\TrustedPeople\$($certificate.Thumbprint)"
            if (-not (Test-Path -LiteralPath $certificatePath)) {
                Update-Certificate 'Import'
                Set-Content -LiteralPath $certificateMarker -Value $certificate.Thumbprint -Encoding ASCII
            }
        }
        Add-AppxPackage -Path (Join-Path $installRoot 'MagicC.Menu.msix') -ExternalLocation $installRoot
        Set-Content -LiteralPath $marker -Value 'MagicC.Desktop' -Encoding ASCII
        # Remove the fallback entry to avoid duplicate commands in the classic menu.
        $legacy = 'Registry::HKEY_CURRENT_USER\Software\Classes\*\shell\MagicCShare'
        if (Test-Path -LiteralPath $legacy) { Remove-Item -LiteralPath $legacy -Recurse }
    }
    exit 0
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
