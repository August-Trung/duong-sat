$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$localEnvFile = Join-Path $root '.env.local'
$env:PYTHONPATH = Join-Path $root 'src'
$activeDbFile = Join-Path $root 'data\active-db.txt'
$defaultDbPath = Join-Path $root 'data\railway.db'
$venvPython = Join-Path $root '.venv\Scripts\python.exe'

if (Test-Path $localEnvFile) {
  Get-Content $localEnvFile | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith('#')) { return }
    $parts = $line.Split('=', 2)
    if ($parts.Count -eq 2) {
      [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim())
    }
  }
}

if (Test-Path $activeDbFile) {
  $activeDbPath = (Get-Content $activeDbFile -Raw).Trim()
  if ($activeDbPath -and (Test-Path $activeDbPath)) {
    $env:RAILWAY_DB_PATH = $activeDbPath
  } else {
    $env:RAILWAY_DB_PATH = $defaultDbPath
  }
} else {
  $env:RAILWAY_DB_PATH = $defaultDbPath
}

$apiHost = if ($env:RAILWAY_API_HOST) { $env:RAILWAY_API_HOST } else { '127.0.0.1' }
$apiPort = if ($env:RAILWAY_API_PORT) { $env:RAILWAY_API_PORT } else { '8000' }

if (Test-Path $venvPython) {
  & $venvPython -m uvicorn railway_crawler.api:app --host $apiHost --port $apiPort
} else {
  python -m uvicorn railway_crawler.api:app --host $apiHost --port $apiPort
}
