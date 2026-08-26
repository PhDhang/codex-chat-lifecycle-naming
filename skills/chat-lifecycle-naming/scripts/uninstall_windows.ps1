[CmdletBinding()]
param(
    [string] $CodexHome,
    [string] $HomePath,
    [string] $SourceSkill,
    [switch] $PurgeConfig
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows_python.ps1")
$arguments = @()
if ($CodexHome) { $arguments += @("--codex-home", $CodexHome) }
if ($HomePath) { $arguments += @("--home", $HomePath) }
if ($SourceSkill) { $arguments += @("--source-skill", $SourceSkill) }
if ($PurgeConfig) { $arguments += "--purge-config" }
Invoke-LifecycleInstaller -Action "uninstall" -InstallerArguments $arguments
