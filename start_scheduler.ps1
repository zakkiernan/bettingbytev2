$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = "D:\tools\python\python.exe"
$runnerPath = Join-Path $repoRoot "run_scheduler.py"
$logDir = Join-Path $repoRoot "logs"
$pidPath = Join-Path $logDir "scheduler_runner.pid"

if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$existingPid = $null
if (Test-Path $pidPath) {
    $rawPid = (Get-Content $pidPath -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if ($rawPid -match '^\d+$') {
        $existingPid = [int]$rawPid
    }
}

if ($existingPid) {
    $runningProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
    if ($runningProcess) {
        exit 0
    }

    Remove-Item $pidPath -ErrorAction SilentlyContinue
}

$env:PYTHONPATH = "$repoRoot;$repoRoot\.venv\Lib\site-packages"

Start-Process -FilePath $pythonPath -ArgumentList $runnerPath -WorkingDirectory $repoRoot -WindowStyle Hidden
