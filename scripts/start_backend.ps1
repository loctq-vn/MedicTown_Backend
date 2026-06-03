param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

python -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
