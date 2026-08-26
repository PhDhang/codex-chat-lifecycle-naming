[CmdletBinding()]
param(
    [string] $CodexHome,
    [string] $HomePath,
    [string] $SourceSkill
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows_python.ps1")
$arguments = @()
if ($CodexHome) { $arguments += @("--codex-home", $CodexHome) }
if ($HomePath) { $arguments += @("--home", $HomePath) }
if ($SourceSkill) { $arguments += @("--source-skill", $SourceSkill) }
Invoke-LifecycleInstaller -Action "verify" -InstallerArguments $arguments
