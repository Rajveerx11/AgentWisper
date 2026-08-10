[CmdletBinding()]
param(
    [switch]$Launch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$appName = 'AgentWisper'
$sourceDirectory = Join-Path $PSScriptRoot 'dist\AgentWisper'
$sourceExecutable = Join-Path $sourceDirectory 'AgentWisper.exe'
$programsRoot = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'Programs'))
$installDirectory = [System.IO.Path]::GetFullPath((Join-Path $programsRoot $appName))
$installedExecutable = Join-Path $installDirectory 'AgentWisper.exe'
$startMenuShortcut = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\AgentWisper.lnk'
$uninstallKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\AgentWisper'

$programsPrefix = $programsRoot.TrimEnd('\') + '\'
if (-not $installDirectory.StartsWith($programsPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Unsafe installation path: $installDirectory"
}
if ([System.IO.Path]::GetFileName($installDirectory) -ne $appName) {
    throw "Unexpected installation directory: $installDirectory"
}
if (-not (Test-Path -LiteralPath $sourceExecutable -PathType Leaf)) {
    throw 'Build missing. Run .\build.ps1 first.'
}

$runningProcesses = Get-CimInstance Win32_Process -Filter "Name = 'AgentWisper.exe'" -ErrorAction SilentlyContinue
$installedProcessIds = @()
foreach ($process in $runningProcesses) {
    if ($process.ExecutablePath -and $process.ExecutablePath.StartsWith($installDirectory, [System.StringComparison]::OrdinalIgnoreCase)) {
        $installedProcessIds += $process.ProcessId
    }
}
if ($installedProcessIds.Count -gt 0) {
    Stop-Process -Id $installedProcessIds -Force -ErrorAction SilentlyContinue
    Wait-Process -Id $installedProcessIds -Timeout 8 -ErrorAction SilentlyContinue
}

if (Test-Path -LiteralPath $installDirectory) {
    $removed = $false
    foreach ($attempt in 1..6) {
        try {
            Remove-Item -LiteralPath $installDirectory -Recurse -Force
            $removed = $true
            break
        }
        catch {
            if ($attempt -eq 6) {
                throw
            }
            Start-Sleep -Milliseconds 400
        }
    }
    if (-not $removed) {
        throw "Could not replace the existing AgentWisper installation."
    }
}
New-Item -ItemType Directory -Path $installDirectory -Force | Out-Null
Get-ChildItem -LiteralPath $sourceDirectory | Copy-Item -Destination $installDirectory -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'uninstall.ps1') -Destination $installDirectory -Force

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($startMenuShortcut)
$shortcut.TargetPath = $installedExecutable
$shortcut.WorkingDirectory = $installDirectory
$shortcut.IconLocation = "$installedExecutable,0"
$shortcut.Description = 'Private technical voice dictation'
$shortcut.Save()

New-Item -Path $uninstallKey -Force | Out-Null
$estimatedSize = [int]((Get-ChildItem -LiteralPath $installDirectory -Recurse -File | Measure-Object Length -Sum).Sum / 1KB)
$uninstallCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$installDirectory\uninstall.ps1`""
$registryValues = @{
    DisplayName = $appName
    DisplayVersion = '0.6.0'
    Publisher = 'Rajveer Vadnal'
    DisplayIcon = "$installedExecutable,0"
    InstallLocation = $installDirectory
    UninstallString = $uninstallCommand
    QuietUninstallString = $uninstallCommand
    URLInfoAbout = 'https://github.com/Rajveerx11/AgentWisper'
    NoModify = 1
    NoRepair = 1
    EstimatedSize = $estimatedSize
}
foreach ($entry in $registryValues.GetEnumerator()) {
    New-ItemProperty -Path $uninstallKey -Name $entry.Key -Value $entry.Value -Force | Out-Null
}

Write-Host "Installed $appName for the current Windows user."
Write-Host "Start Menu: $startMenuShortcut"
Write-Host "Location: $installDirectory"

if ($Launch) {
    Start-Process -FilePath $installedExecutable
}
