$python = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Virtual environment missing. Run the setup commands in README.md.'
}

Start-Process -FilePath $python -ArgumentList '-m', 'agent_whisper.gui' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
