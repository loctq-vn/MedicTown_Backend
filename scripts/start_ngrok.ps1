param(
    [int]$Port = 8200,
    [string]$Domain = $env:NGROK_DOMAIN
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$localNgrok = Join-Path $repoRoot "tools\ngrok.exe"

if (Test-Path $localNgrok) {
    $ngrok = $localNgrok
} else {
    $ngrokCommand = Get-Command ngrok -ErrorAction SilentlyContinue
    if (-not $ngrokCommand) {
        throw "ngrok is not installed. Install ngrok, then run: ngrok config add-authtoken <your-token>"
    }
    $ngrok = $ngrokCommand.Source
}

if ($Domain) {
    & $ngrok http --domain=$Domain "http://127.0.0.1:$Port"
} else {
    & $ngrok http "http://127.0.0.1:$Port"
}
