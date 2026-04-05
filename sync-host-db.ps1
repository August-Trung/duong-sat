$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$activeDbFile = Join-Path $root 'data\active-db.txt'
$hostDbPath = Join-Path $root 'data\railway.db'

if (Test-Path $activeDbFile) {
  $sourceDbPath = (Get-Content $activeDbFile -Raw).Trim()
} else {
  $sourceDbPath = $hostDbPath
}

if (-not $sourceDbPath) {
  throw 'Khong xac dinh duoc DB local de dong bo.'
}

if (-not (Test-Path $sourceDbPath)) {
  throw "DB local khong ton tai: $sourceDbPath"
}

$resolvedSource = (Resolve-Path $sourceDbPath).Path
$resolvedHost = (Resolve-Path $hostDbPath).Path

if ($resolvedSource -ne $resolvedHost) {
  Copy-Item -LiteralPath $resolvedSource -Destination $resolvedHost -Force
  Write-Output "Da dong bo DB local -> host snapshot: $resolvedSource -> $resolvedHost"
} else {
  Write-Output "DB local hien da la DB host snapshot: $resolvedHost"
}

Write-Output 'Buoc tiep theo: git add data/railway.db, git commit, git push de host nhan cung du lieu.'
