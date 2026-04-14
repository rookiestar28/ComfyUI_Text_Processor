param(
    [string]$Python = "",
    [switch]$SkipPreCommit
)

$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

if ($Python) {
    $PythonExe = $Python
    $PythonPrefixArgs = @()
} else {
    $UserCondaComfyPython = Join-Path $env:USERPROFILE ".conda\envs\comfyui\python.exe"
    $ProgramDataCondaComfyPython = "C:\ProgramData\anaconda3\envs\comfyui\python.exe"

    if ($env:PYTHON) {
        $PythonExe = $env:PYTHON
        $PythonPrefixArgs = @()
    } elseif (Test-Path ".venv\Scripts\python.exe") {
        $PythonExe = ".venv\Scripts\python.exe"
        $PythonPrefixArgs = @()
    } elseif (Test-Path $UserCondaComfyPython) {
        $PythonExe = $UserCondaComfyPython
        $PythonPrefixArgs = @()
    } elseif (Test-Path $ProgramDataCondaComfyPython) {
        $PythonExe = $ProgramDataCondaComfyPython
        $PythonPrefixArgs = @()
    } else {
        $PythonExe = "python"
        $PythonPrefixArgs = @()
    }
}

function Invoke-Step {
    param(
        [string]$Name,
        [string[]]$Command
    )

    Write-Host ""
    Write-Host "==> $Name"
    if ($Command.Length -gt 1) {
        & $Command[0] @($Command[1..($Command.Length - 1)])
    } else {
        & $Command[0]
    }
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-PythonStep {
    param(
        [string]$Name,
        [string[]]$PythonArgs
    )

    Invoke-Step -Name $Name -Command (@($PythonExe) + $PythonPrefixArgs + $PythonArgs)
}

Invoke-PythonStep -Name "Python version" -PythonArgs @("--version")

if (-not $SkipPreCommit) {
    Invoke-PythonStep -Name "detect-secrets" -PythonArgs @("-m", "pre_commit", "run", "detect-secrets", "--all-files")
    Invoke-PythonStep -Name "pre-commit" -PythonArgs @("-m", "pre_commit", "run", "--all-files", "--show-diff-on-failure")
}

Invoke-PythonStep -Name "unit tests" -PythonArgs @("-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")
