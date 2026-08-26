[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $BackupPath,
    [string] $CodexHome,
    [string] $HomePath,
    [string] $SourceSkill
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "windows_python.ps1")
$arguments = @("--backup", $BackupPath)
if ($CodexHome) { $arguments += @("--codex-home", $CodexHome) }
if ($HomePath) { $arguments += @("--home", $HomePath) }
if ($SourceSkill) { $arguments += @("--source-skill", $SourceSkill) }
Invoke-LifecycleInstaller -Action "rollback" -InstallerArguments $arguments
