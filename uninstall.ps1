[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$appName = 'AgentWisper'
$programsRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs'))
$installDirectory = [System.IO.Path]::GetFullPath((Join-Path $programsRoot $appName))
$startMenuShortcut = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AgentWisper.lnk'
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentWisper'
$startupKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'

$programsPrefix = $programsRoot.TrimEnd('\') + '\'
if (-not $installDirectory.StartsWith($programsPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe uninstall path: $installDirectory"
}
if ([System.IO.Path]::GetFileName($installDirectory) -ne $appName) {
    throw "Unexpected uninstall directory: $installDirectory"
}

$runningProcesses = Get-CimInstance Win32_Process -Filter "Name = 'AgentWisper.exe'" -ErrorAction SilentlyContinue
foreach ($process in $runningProcesses) {
    if ($process.ExecutablePath -and $process.ExecutablePath.StartsWith($installDirectory, [System.StringComparison]::OrdinalIgnoreCase)) {
        Stop-Process -Id $process.ProcessId -Force
    }
}

Remove-Item -LiteralPath $startMenuShortcut -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $uninstallKey -Recurse -Force -ErrorAction SilentlyContinue
Remove-ItemProperty -LiteralPath $startupKey -Name $appName -Force -ErrorAction SilentlyContinue

$escapedInstallDirectory = $installDirectory.Replace("'", "''")
$cleanupCommand = "Start-Sleep -Milliseconds 500; Remove-Item -LiteralPath '$escapedInstallDirectory' -Recurse -Force"
Start-Process -FilePath 'powershell.exe' -ArgumentList @(
    '-NoProfile',
    '-WindowStyle', 'Hidden',
    '-Command', $cleanupCommand
) -WindowStyle Hidden

Write-Host "$appName was uninstalled. Transcript history and settings were kept."
