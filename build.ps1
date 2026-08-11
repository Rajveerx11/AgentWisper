$ErrorActionPreference = 'Stop'

$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment missing. Run the setup commands in README.md.'
}

& $python -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot 'AgentWisper.spec')
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

$packageDirectory = Join-Path $PSScriptRoot 'dist\AgentWisper'
foreach ($document in @('LICENSE', 'NOTICE.md', 'THIRD_PARTY_NOTICES.md')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $document) -Destination $packageDirectory -Force
}

$internalLicenses = Join-Path $packageDirectory '_internal\licenses'
$packageLicenses = Join-Path $packageDirectory 'licenses'
if (-not (Test-Path -LiteralPath $internalLicenses -PathType Container)) {
    throw 'Collected runtime dependency licenses are missing from the package.'
}
New-Item -ItemType Directory -Path $packageLicenses -Force | Out-Null
Get-ChildItem -LiteralPath $internalLicenses | Copy-Item -Destination $packageLicenses -Recurse -Force

Write-Host "Built: $PSScriptRoot\dist\AgentWisper\AgentWisper.exe"
