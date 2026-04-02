$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$env:PYTHONPATH = Join-Path $root 'src'

python -m uvicorn railway_crawler.api:app --host 127.0.0.1 --port 8000
