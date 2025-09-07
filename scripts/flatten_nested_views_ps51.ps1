param([string]$ProjectRoot = $null)
$ErrorActionPreference = "Stop"

# Raiz segura
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = $PSScriptRoot }
$Root = Resolve-Path -Path $ProjectRoot
if (-not (Test-Path (Join-Path $Root "app.py"))) { throw "A raiz '$Root' não contém app.py." }
Write-Host "==> Raiz: $Root" -ForegroundColor Cyan

function Ensure-Dir($p){ if(-not (Test-Path $p)){ New-Item -ItemType Directory -Force -Path $p | Out-Null } }
function TryRead([string]$p){
  try { Get-Content -Path $p -Raw -Encoding UTF8 -ErrorAction Stop } catch {
    try { Get-Content -Path $p -Raw -Encoding Default -ErrorAction Stop } catch { $null }
  }
}
function SaveWithBackup([string]$p,[string]$txt){
  Copy-Item $p "$p.bak" -Force
  Set-Content -Path $p -Value $txt -Encoding UTF8
}
function MergeMove([string]$src,[string]$dst){
  if(-not (Test-Path $src)){ return $false }
  Ensure-Dir $dst
  $changed = $false
  Get-ChildItem -LiteralPath $src -Force | ForEach-Object {
    $destPath = Join-Path $dst $_.Name
    if(Test-Path $destPath){
      # backup do destino antes de sobrescrever
      Copy-Item -Recurse -Force $destPath "$destPath.bak"
    }
    Move-Item -Force -Path $_.FullName -Destination $destPath
    $changed = $true
  }
  try { Remove-Item -Recurse -Force $src } catch {}
  return $changed
}

# 1) Achatar pastas duplicadas
$didMove = $false
$op1 = @{ src = Join-Path $Root "views\music\genres\genres";   dst = Join-Path $Root "views\music\genres" }
$op2 = @{ src = Join-Path $Root "views\music\spotify\spotify"; dst = Join-Path $Root "views\music\spotify" }

if(Test-Path $op1.src){
  if(MergeMove $op1.src $op1.dst){
    Write-Host "• Movido: $($op1.src)  →  $($op1.dst)" -ForegroundColor DarkGreen
    $didMove = $true
  }
}
if(Test-Path $op2.src){
  if(MergeMove $op2.src $op2.dst){
    Write-Host "• Movido: $($op2.src)  →  $($op2.dst)" -ForegroundColor DarkGreen
    $didMove = $true
  }
}

# remover parent vazio (caso raro)
$parents = @((Split-Path -Parent $op1.src),(Split-Path -Parent $op2.src))
foreach($parent in $parents){
  if(([string]::IsNullOrEmpty($parent)) -or (-not (Test-Path $parent))){ continue }
  if((Get-ChildItem $parent -Force | Measure-Object).Count -eq 0){
    try { Remove-Item $parent -Recurse -Force } catch {}
  }
}

# garantir __init__.py nos destinos
$inits = @(
  (Join-Path $Root "views\music\genres\__init__.py"),
  (Join-Path $Root "views\music\spotify\__init__.py")
)
foreach($i in $inits){ if(-not (Test-Path $i)){ New-Item -ItemType File -Force -Path $i | Out-Null } }

# 2) Corrigir imports no código
$patterns = @(
  @{ o='views\.music\.genres\.genres';   n='views.music.genres' },
  @{ o='views\.music\.spotify\.spotify'; n='views.music.spotify' }
)

$targets = Get-ChildItem -Path $Root -Recurse -Include *.py -File |
  Where-Object { $_.FullName -notmatch '(\\\.venv\\|__pycache__|\.pytest_cache|\.mypy_cache)' }

$modCount = 0
foreach($f in $targets){
  $raw = TryRead $f.FullName
  if($null -eq $raw){ continue }
  $orig = $raw
  foreach($p in $patterns){
    $raw = [regex]::Replace($raw, $p.o, $p.n)
  }
  if($raw -ne $orig){
    SaveWithBackup $f.FullName $raw
    $modCount++
    Write-Host ("• Atualizado: " + ($f.FullName.Replace($Root, '.'))) -ForegroundColor DarkGreen
  }
}

Write-Host ""
Write-Host "Resumo:" -ForegroundColor Cyan
$pastasAchatadas = 0
if($didMove){ $pastasAchatadas = 1 }
Write-Host (" - Pastas achatadas: {0}" -f $pastasAchatadas)
Write-Host (" - Ficheiros Python alterados: {0}" -f $modCount)

# 3) Verificação rápida
$left = Get-ChildItem -Path $Root -Recurse -Include *.py -File |
  Select-String -Pattern 'views\.music\.(genres\.genres|spotify\.spotify)' -AllMatches -ErrorAction SilentlyContinue
if($left){
  Write-Host "ATENÇÃO: Restam referências a '.genres.genres' ou '.spotify.spotify':" -ForegroundColor Yellow
  $left | ForEach-Object { Write-Host ("  > {0}:{1}  {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()) }
} else {
  Write-Host "✓ Sem referências a '.genres.genres' / '.spotify.spotify'." -ForegroundColor Green
}
