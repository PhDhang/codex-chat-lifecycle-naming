Set-StrictMode -Version 2.0

function Get-LifecyclePython {
    $isWindowsHost = $env:OS -eq "Windows_NT"
    if ($isWindowsHost) {
        $candidates = @(
            [pscustomobject]@{ Name = "py"; PrefixArgs = @("-3") },
            [pscustomobject]@{ Name = "python"; PrefixArgs = @() }
        )
    }
    else {
        $candidates = @(
            [pscustomobject]@{ Name = "python3"; PrefixArgs = @() },
            [pscustomobject]@{ Name = "python"; PrefixArgs = @() }
        )
    }

    foreach ($candidate in $candidates) {
        $command = Get-Command -Name $candidate.Name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -ne $command) {
            $probeArguments = @($candidate.PrefixArgs) + @(
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info.major == 3 else 1)"
            )
            & $command.Source @probeArguments 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return [pscustomobject]@{
                    Path = $command.Source
                    PrefixArgs = $candidate.PrefixArgs
                }
            }
        }
    }
    throw "Python 3 was not found. On Windows install the py launcher or provide python on PATH."
}

function Invoke-LifecycleInstaller {
    param(
        [Parameter(Mandatory = $true)] [string] $Action,
        [string[]] $InstallerArguments = @()
    )
    $python = Get-LifecyclePython
    $installer = Join-Path $PSScriptRoot "installer.py"
    $commandArguments = @($python.PrefixArgs) + @($installer, $Action) + @($InstallerArguments)
    & $python.Path @commandArguments
    if ($LASTEXITCODE -ne 0) {
        throw "chat-lifecycle-naming $Action failed with exit code $LASTEXITCODE"
    }
}
