$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment missing. Run the setup commands in README.md.'
}

& $python -m agent_whisper @args
