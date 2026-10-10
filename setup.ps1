param([string]$Python = 'py', [switch]$SkipModels)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Program (exit $LASTEXITCODE)" }
}
if ($Python -eq 'py') { $taskPythonArgs = @('-3.12') } else { $taskPythonArgs = @() }
Invoke-Checked $Python ($taskPythonArgs + @('-c','import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 x64 required"; assert sys.maxsize > 2**32, "64-bit Python required"'))
Invoke-Checked 'node' @('-e','const [a,b]=process.versions.node.split(".").map(Number); if(!((a===22&&b>=12)||a>=24))throw Error("Node 22.12+ or 24+ required")')
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    Invoke-Checked $Python ($taskPythonArgs + @('-m','venv','.venv'))
}
$taskVenvPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
Invoke-Checked $taskVenvPython @('-m','pip','install','-r','backend/requirements-local.txt')
if (-not $SkipModels) {
    Invoke-Checked $taskVenvPython @('backend/scripts/install_replay_rtmw.py')
}
Push-Location -LiteralPath 'frontend'
try {
    $env:CLIMB_DESKTOP_BUILD = '1'
    Invoke-Checked 'npm.cmd' @('ci')
    Invoke-Checked 'npm.cmd' @('run','build','--','--mode','boulder-local')
} finally {
    Remove-Item Env:CLIMB_DESKTOP_BUILD -ErrorAction SilentlyContinue
    Pop-Location
}
Write-Host 'Setup completed. Run start.cmd. Photos need separately installed hold-model assets; see docs/MODELS.md.'
