param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Set-Location (Split-Path -Parent $PSScriptRoot)

# Use the system Python explicitly to avoid PATH conflicts
& C:\Python\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
