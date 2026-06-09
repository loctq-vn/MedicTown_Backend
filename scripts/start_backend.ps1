param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

$PythonCandidates = @(
    ".\.venv\Scripts\python.exe",
    ".\venv\Scripts\python.exe",
    "python",
    "py"
)

$PythonCommand = $null
foreach ($Candidate in $PythonCandidates) {
    $Command = Get-Command $Candidate -ErrorAction SilentlyContinue
    if ($Command) {
        $PythonCommand = $Command.Source
        break
    }
}

if (-not $PythonCommand) {
    throw "Python was not found. Please install Python or create a virtual environment in MedicTown_Backend."
}

& $PythonCommand -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
