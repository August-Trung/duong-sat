$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:PYTHONPATH = Join-Path $root 'src'
$activeDbFile = Join-Path $root 'data\active-db.txt'
$defaultDbPath = Join-Path $root 'data\railway.db'

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

python -m uvicorn railway_crawler.api:app --host 127.0.0.1 --port 8000
