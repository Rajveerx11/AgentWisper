$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment missing. Run the setup commands in README.md.'
}

& $python -m PyInstaller --noconfirm --clean (Join-Path $PSScriptRoot 'AgentWisper.spec')
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host "Built: $PSScriptRoot\dist\AgentWisper\AgentWisper.exe"
