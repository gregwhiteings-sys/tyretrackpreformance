param([ValidateSet('Install','Remove')][string]$Action = 'Install')
$ErrorActionPreference = 'Stop'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'TyreTrack Production.lnk'
if ($Action -eq 'Remove') {
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
    Write-Host 'TyreTrack sign-in startup shortcut removed. Other scheduled tasks were not changed.'
    exit 0
}
$exePath = Join-Path $PSScriptRoot 'TyreTrack.exe'
if (!(Test-Path -LiteralPath $exePath)) { throw 'Run this installer from the built TyreTrack portable folder beside TyreTrack.exe.' }
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $exePath
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Description = 'TyreTrack production monitoring - automatic OAK connection'
$shortcut.Save()
if (!(Test-Path -LiteralPath $shortcutPath)) { throw 'Startup shortcut was not created.' }
Write-Host 'Installed for the current Windows user. TyreTrack will launch at sign-in.'
Write-Host 'Keep this portable folder at its current location. Counting follows Brisbane production hours.'
Write-Host 'This does not enable automatic Windows sign-in or start before a user signs in.'
