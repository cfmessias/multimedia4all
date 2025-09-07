param(
  [string]$ProjectRoot = $null,
  [switch]$NoShim # usar se não quiser criar o shim em services/spotify/__init__.py
)

$ErrorActionPreference = "Stop"

# 0) Raiz segura
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = $PSScriptRoot }
$Root = Resolve-Path -Path $ProjectRoot
if (-not (Test-Path (Join-Path $Root "app.py"))) {
  throw "A raiz '$Root' não contém app.py. Coloca o script na raiz do projeto ou passa -ProjectRoot."
}
Write-Host "==> Raiz do projeto: $Root" -ForegroundColor Cyan

function Ensure-Dir($p){ if(-not (Test-Path $p)){ New-Item -ItemType Directory -Force -Path $p | Out-Null } }

# 1) Pastas destino
$old = Join-Path $Root "services\spotify"
$new = Join-Path $Root "services\music\spotify"
Ensure-Dir (Join-Path $Root "services\music")
Ensure-Dir $new

# 2) Mover conteúdos de services/spotify para services/music/spotify (se existirem)
if (Test-Path $old) {
  $items = Get-ChildItem $old -Force -ErrorAction SilentlyContinue
  foreach($it in $items){
    Move-Item $it.FullName (Join-Path $new $it.Name) -Force
  }
  # (re)criar pasta services/spotify para servir de shim se necessário
  if (-not $NoShim) { Ensure-Dir $old }
}

# 3) Criar __init__.py nos novos pacotes
$initPaths = @(
  (Join-Path $Root "services\music\__init__.py"),
  (Join-Path $Root "services\music\spotify\__init__.py")
)
foreach($p in $initPaths){ if(-not (Test-Path $p)){ New-Item -ItemType File -Force -Path $p | Out-Null } }

# 4) Criar shim de compatibilidade (opcional)
if (-not $NoShim) {
  $shim = @'
# Temporary compatibility shim — prefer: from services.music.spotify import ...
import sys
from services.music import spotify as _mod
sys.modules[__name__] = _mod
from services.music.spotify import *  # re-export
'@
  Set-Content -Path (Join-Path $old "__init__.py") -Value $shim -Encoding UTF8
}

# 5) Atualizar imports em todo o projeto (robusto a ficheiros não-texto)
function Try-ReadFile([string]$Path){
  try { return Get-Content -Path $Path -Raw -Encoding UTF8 -ErrorAction Stop } catch {
    try { return Get-Content -Path $Path -Raw -Encoding Default -ErrorAction Stop } catch { return $null }
  }
}

$patterns = @(
  # Casos explícitos
  @{o='(?m)^\s*from\s+services\.spotify\.';               n='from services.music.spotify.'},
  @{o='(?m)^\s*from\s+services\s+import\s+spotify\b';     n='from services.music import spotify'},
  @{o='(?m)^\s*import\s+services\.spotify\s+as\s+([A-Za-z_][A-Za-z0-9_]*)'; n='from services.music import spotify as $1'},
  @{o='(?m)^\s*import\s+services\.spotify\b';             n='from services.music import spotify as spotify'},
  # fallback seguro (evitar alterar o próprio shim)
  @{o='(?!^#).*?\bservices\.spotify\b';                   n='services.music.spotify'}
)

# alvo: .py do projeto (exclui .venv, caches e o shim)
$targets = Get-ChildItem -Path $Root -Recurse -Include *.py -File | Where-Object {
  $_.FullName -notmatch '(\\\.venv\\|__pycache__|\.pytest_cache|\.mypy_cache)' -and
  $_.FullName -ne (Join-Path $old "__init__.py")
}

$modified = 0
foreach($f in $targets){
  $raw = Try-ReadFile $f.FullName
  if ($null -eq $raw) { continue }           # evita erro "Value cannot be null"
  $orig = $raw
  foreach($p in $patterns){
    $raw = [regex]::Replace($raw, $p.o, $p.n)
  }
  if ($raw -ne $orig){
    Copy-Item $f.FullName "$($f.FullName).bak" -Force
    Set-Content -Path $f.FullName -Value $raw -Encoding UTF8
    Write-Host ("Atualizado: " + ($f.FullName.Replace($Root, '.'))) -ForegroundColor DarkGreen
    $modified++
  }
}

# 6) Relatório + verificação de restos
Write-Host ""
Write-Host "Resumo:" -ForegroundColor Cyan
Write-Host (" - Ficheiros Python alterados: {0}" -f $modified)
Write-Host (" - Pasta nova: services\music\spotify (com __init__.py)") 
if (-not $NoShim) { Write-Host " - Shim criado em services\spotify\__init__.py (temporário)" }

$left = Select-String -Path (Join-Path $Root "**\*.py") -Pattern '\bservices\.spotify\b' -AllMatches -Recurse -ErrorAction SilentlyContinue
if($left){
  Write-Host ""
  Write-Host "ATENÇÃO: Restam referências a 'services.spotify' (reveja manualmente):" -ForegroundColor Yellow
  $left | ForEach-Object { Write-Host ("  > {0}:{1}  {2}" -f $_.Path, $_.LineNumber, $_.Line.Trim()) }
} else {
  Write-Host ""
  Write-Host "✓ Não restam referências a 'services.spotify'." -ForegroundColor Green
}
