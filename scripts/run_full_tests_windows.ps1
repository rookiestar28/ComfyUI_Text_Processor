param(
    [string]$Python = "",
    [switch]$SkipPreCommit
)

$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

$RepoRoot = (Get-Location).Path

if (-not $env:PRE_COMMIT_HOME) {
    $env:PRE_COMMIT_HOME = Join-Path (Get-Location) ".tmp\pre-commit-cache"
}
New-Item -ItemType Directory -Force -Path $env:PRE_COMMIT_HOME | Out-Null

$env:npm_config_cache = Join-Path $RepoRoot ".tmp\npm-cache"
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $RepoRoot ".tmp\playwright-browsers"
$env:TMP = Join-Path $RepoRoot ".tmp\playwright-temp"
$env:TEMP = $env:TMP
foreach ($Path in @(
    $env:npm_config_cache,
    $env:PLAYWRIGHT_BROWSERS_PATH,
    $env:TMP
)) {
    New-Item -ItemType Directory -Force -Path $Path | Out-Null
}

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

$NodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $NodeCommand) {
    throw "Node.js is required for frontend E2E. Install Node.js 18+."
}
$NodeVersion = (& $NodeCommand.Source --version).Trim()
$NodeMajor = [int]($NodeVersion.TrimStart("v").Split(".")[0])
if ($NodeMajor -lt 18) {
    throw "Node.js 18+ is required; active version is $NodeVersion."
}
Write-Host ""
Write-Host "==> Node.js version"
Write-Host $NodeVersion

if (-not $SkipPreCommit) {
    Invoke-PythonStep -Name "detect-secrets" -PythonArgs @("-m", "pre_commit", "run", "detect-secrets", "--all-files")
    Invoke-PythonStep -Name "pre-commit" -PythonArgs @("-m", "pre_commit", "run", "--all-files", "--show-diff-on-failure")
}

Invoke-PythonStep -Name "unit tests" -PythonArgs @("-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py")

Invoke-Step -Name "npm clean install" -Command @("npm", "ci", "--ignore-scripts")
Invoke-Step -Name "Playwright Chromium" -Command @("npx", "playwright", "install", "chromium")
Invoke-Step -Name "npm audit" -Command @("npm", "audit", "--audit-level=high")
Invoke-Step -Name "frontend E2E" -Command @("npm", "test")
