# Reorganiza projeto: move views para a hierarquia nova, cria pastas por área,
# move CSVs, cria services/common/paths.py, atualiza imports e read_csv(...)
# Seguro para duplo-clique (usa a pasta do próprio script como raiz).

param([string]$ProjectRoot = $null)
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = $PSScriptRoot }
$Root = Resolve-Path -Path $ProjectRoot
if (-not (Test-Path (Join-Path $Root "app.py"))) {
  throw "A raiz '$Root' não contém app.py. Coloca este script na raiz do projeto ou passa -ProjectRoot."
}
Write-Host "==> Raiz do projeto: $Root" -ForegroundColor Cyan

function Ensure-Dir($p){ if(-not (Test-Path $p)){ New-Item -ItemType Directory -Force -Path $p | Out-Null } }
function Move-Dir-Into($src,$dst){
  if(-not (Test-Path $src)){ return }
  Ensure-Dir $dst
  if(-not (Test-Path $dst)){ New-Item -ItemType Directory -Force -Path $dst | Out-Null }
  # se destino vazio, tenta mover diretamente
  try { Move-Item $src $dst -Force -ErrorAction Stop; return } catch {}
  # caso já exista, move conteúdos e remove origem
  Get-ChildItem $src -Force | ForEach-Object { Move-Item $_.FullName (Join-Path $dst $_.Name) -Force }
  try { Remove-Item $src -Force -Recurse } catch {}
}

# 1) Pastas alvo
$dirs = @(
  "views\music\spotify","views\music\genres","views\music\wiki",
  "views\music\influence_map","views\music\genealogy","views\music\playlists",
  "views\cinema\ui",
  "services\common",
  "music\data","music\assets","music\config",
  "cinema\data","cinema\assets","cinema\config",
  "radio\data","radio\assets","radio\config",
  "podcasts\data","podcasts\assets","podcasts\config"
)
$dirs | ForEach-Object { Ensure-Dir (Join-Path $Root $_) }

# 2) __init__.py para pacotes Python
$pkgs = @(
  "views","views\music","views\cinema",
  "views\music\spotify","views\music\genres","views\music\wiki",
  "views\music\influence_map","views\music\genealogy","views\music\playlists",
  "services","services\common"
)
$pkgs | ForEach-Object {
  $initPath = Join-Path $Root ($_ + "\__init__.py")
  if(-not (Test-Path $initPath)){ New-Item -ItemType File -Force -Path $initPath | Out-Null }
}

# 3) Movimentos de UI (Fase 1)
Move-Dir-Into (Join-Path $Root "views\spotify")        (Join-Path $Root "views\music\spotify")
Move-Dir-Into (Join-Path $Root "views\genres")         (Join-Path $Root "views\music\genres")

if(Test-Path (Join-Path $Root "views\wiki_page.py")){
  Move-Item (Join-Path $Root "views\wiki_page.py") (Join-Path $Root "views\music\wiki\wiki_page.py") -Force
}

Get-ChildItem (Join-Path $Root "views") -Filter "influence_map*.py" -File -ErrorAction SilentlyContinue | ForEach-Object {
  Move-Item $_.FullName (Join-Path $Root "views\music\influence_map\$($_.Name)") -Force
}
Get-ChildItem (Join-Path $Root "views") -Filter "genealogy*.py" -File -ErrorAction SilentlyContinue | ForEach-Object {
  Move-Item $_.FullName (Join-Path $Root "views\music\genealogy\$($_.Name)") -Force
}
if(Test-Path (Join-Path $Root "views\playlists_page.py")){
  Move-Item (Join-Path $Root "views\playlists_page.py") (Join-Path $Root "views\music\playlists\playlists_page.py") -Force
}

# Cinema UI para views/cinema
if(Test-Path (Join-Path $Root "cinema\page.py")){
  Ensure-Dir (Join-Path $Root "views\cinema")
  Move-Item (Join-Path $Root "cinema\page.py") (Join-Path $Root "views\cinema\page.py") -Force
}
if(Test-Path (Join-Path $Root "cinema\ui")){
  Move-Dir-Into (Join-Path $Root "cinema\ui") (Join-Path $Root "views\cinema\ui")
}

# 4) Criar/atualizar services/common/paths.py
$pathsPy = Join-Path $Root "services\common\paths.py"
$pathsContent = @'
# services/common/paths.py
from pathlib import Path

# Raiz do projeto (multimedia4all/)
ROOT = Path(__file__).resolve().parents[2]

# Pastas de dados por área
MUSIC_DIR   = ROOT / "music"
CINEMA_DIR  = ROOT / "cinema"
RADIO_DIR   = ROOT / "radio"
POD_DIR     = ROOT / "podcasts"

MUSIC_DATA  = MUSIC_DIR / "data"
CINEMA_DATA = CINEMA_DIR / "data"
RADIO_DATA  = RADIO_DIR / "data"
POD_DATA    = POD_DIR / "data"

# Conveniências
VIEWS_DIR    = ROOT / "views"
SERVICES_DIR = ROOT / "services"

# Garante existência das pastas de dados
for p in [MUSIC_DATA, CINEMA_DATA, RADIO_DATA, POD_DATA]:
    p.mkdir(parents=True, exist_ok=True)
'@
if(Test-Path $pathsPy){ Copy-Item $pathsPy "$pathsPy.bak" -Force }
Set-Content -Path $pathsPy -Value $pathsContent -Encoding UTF8

# 5) Mover CSVs (Fase 2)
$moves = @()
foreach($f in @("generos.csv","hierarquia_generos.csv","lista_artistas.csv")){
  $src = Join-Path $Root $f; $dst = Join-Path $Root ("music\data\" + $f)
  if(Test-Path $src){ Move-Item $src $dst -Force; $moves += "Move: $f -> music/data/$f" }
}
foreach($f in @("influences_edges.csv","influences_origins.csv")){
  $srcA = Join-Path $Root ("dados\" + $f); $dstA = Join-Path $Root ("music\data\" + $f)
  if(Test-Path $srcA){ Move-Item $srcA $dstA -Force; $moves += "Move: dados/$f -> music/data/$f" }
}
foreach($f in @("movies.csv","series.csv","soundtracks.csv")){
  $src = Join-Path $Root ("cinema\" + $f); $dst = Join-Path $Root ("cinema\data\" + $f)
  if(Test-Path $src){ Move-Item $src $dst -Force; $moves += "Move: cinema/$f -> cinema/data/$f" }
}
if($moves.Count -gt 0){
  Write-Host "✔ CSVs movidos:" -ForegroundColor Green
  $moves | ForEach-Object { Write-Host "   - $_" }
} else {
  Write-Host "ℹ Nenhum CSV para mover (já estavam no sítio certo)." -ForegroundColor Yellow
}

# 6) Atualizar imports no código (inclui app.py e quaisquer módulos)
function Update-File-Imports {
  param([string]$FilePath)
  try { $raw = Get-Content $FilePath -Raw -Encoding UTF8 } catch { return $false }
  if ([string]::IsNullOrEmpty($raw)) { return $false }
  $orig = $raw

  # Regras de re-map
  $rules = @(
    @{ o='from\s+views\.spotify\.';                           n='from views.music.spotify.' },
    @{ o='from\s+views\.genres\.';                            n='from views.music.genres.' },
    @{ o='from\s+views\.wiki_page\s+import';                  n='from views.music.wiki.wiki_page import' },
    @{ o='from\s+views\.playlists_page\s+import';             n='from views.music.playlists.playlists_page import' },
    @{ o='from\s+views\.influence_map([_\w]*)\s+import';      n='from views.music.influence_map.influence_map$1 import' },
    @{ o='from\s+views\.genealogy([_\w]*)\s+import';          n='from views.music.genealogy.genealogy$1 import' },
    @{ o='from\s+cinema\.page\s+import';                      n='from views.cinema.page import' }
  )
  foreach($r in $rules){ $raw = [Regex]::Replace($raw, $r.o, $r.n) }

  # Caso específico apontado pelo verificador
  $raw = $raw -replace 'from\s+views\.spotify\.results\s+import', 'from views.music.spotify.results import'

  if ($raw -ne $orig){
    Copy-Item $FilePath "$FilePath.bak" -Force
    Set-Content -Path $FilePath -Value $raw -Encoding UTF8
    return $true
  }
  return $false
}

# 7) Atualizar pd.read_csv(...) -> MUSIC_DATA/CINEMA_DATA e injetar import
function Update-File-ReadCsv {
  param([string]$FilePath)
  try { $raw = Get-Content $FilePath -Raw -Encoding UTF8 } catch { return $false }
  if ([string]::IsNullOrEmpty($raw)) { return $false }
  $orig = $raw

  $repl = @(
    # Música
    @{ o='pd\.read_csv\(\s*["'']generos\.csv["'']';               n='pd.read_csv(MUSIC_DATA / "generos.csv"' },
    @{ o='pd\.read_csv\(\s*["'']hierarquia_generos\.csv["'']';     n='pd.read_csv(MUSIC_DATA / "hierarquia_generos.csv"' },
    @{ o='pd\.read_csv\(\s*["'']lista_artistas\.csv["'']';         n='pd.read_csv(MUSIC_DATA / "lista_artistas.csv"' },
    @{ o='pd\.read_csv\(\s*["''](?:dados[\\/]+)?influences_edges\.csv["'']';   n='pd.read_csv(MUSIC_DATA / "influences_edges.csv"' },
    @{ o='pd\.read_csv\(\s*["''](?:dados[\\/]+)?influences_origins\.csv["'']'; n='pd.read_csv(MUSIC_DATA / "influences_origins.csv"' },
    # Cinema
    @{ o='pd\.read_csv\(\s*["'']cinema[\\/]+movies\.csv["'']';      n='pd.read_csv(CINEMA_DATA / "movies.csv"' },
    @{ o='pd\.read_csv\(\s*["'']cinema[\\/]+series\.csv["'']';      n='pd.read_csv(CINEMA_DATA / "series.csv"' },
    @{ o='pd\.read_csv\(\s*["'']cinema[\\/]+soundtracks\.csv["'']'; n='pd.read_csv(CINEMA_DATA / "soundtracks.csv"' },
    @{ o='pd\.read_csv\(\s*["'']movies\.csv["'']';                  n='pd.read_csv(CINEMA_DATA / "movies.csv"' },
    @{ o='pd\.read_csv\(\s*["'']series\.csv["'']';                  n='pd.read_csv(CINEMA_DATA / "series.csv"' },
    @{ o='pd\.read_csv\(\s*["'']soundtracks\.csv["'']';             n='pd.read_csv(CINEMA_DATA / "soundtracks.csv"' }
  )
  foreach($r in $repl){ $raw = $raw -replace $r.o, $r.n }

  $changed = ($raw -ne $orig)

  # Injetar import se necessário
  if($changed -and ($raw -match 'pd\.read_csv\(\s*(MUSIC_DATA|CINEMA_DATA)\s*/\s*["'']')){
    if($raw -notmatch 'from\s+services\.common\.paths\s+import\s+MUSIC_DATA(?:\s*,\s*CINEMA_DATA)?|from\s+services\.common\.paths\s+import\s+CINEMA_DATA'){
      $lines = $raw -split "`r?`n"
      $insert = 'from services.common.paths import MUSIC_DATA, CINEMA_DATA'
      $idx = 0
      while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
      if($idx -gt 0){ $lines = $lines[0..($idx-1)] + @($insert) + $lines[$idx..($lines.Length-1)] }
      else { $lines = @($insert, '') + $lines }
      $raw = ($lines -join "`r`n")
    }
  }

  if ($raw -ne $orig){
    Copy-Item $FilePath "$FilePath.bak" -Force
    Set-Content -Path $FilePath -Value $raw -Encoding UTF8
    return $true
  }
  return $false
}

# 8) Aplicar às árvores views/ e services/ e ao app.py
$scanDirs = @("views","services") | ForEach-Object { Join-Path $Root $_ } | Where-Object { Test-Path $_ }
$targets = @()
foreach($d in $scanDirs){
  $targets += Get-ChildItem -Path $d -Include *.py -Recurse -File |
    Where-Object { $_.FullName -notmatch '(\\\.venv\\|__pycache__|\.pytest_cache|\.mypy_cache)' }
}
$appPy = Join-Path $Root "app.py"; if(Test-Path $appPy){ $targets += Get-Item $appPy }

$mods = 0
foreach($f in $targets){
  $a = Update-File-Imports -FilePath $f.FullName
  $b = Update-File-ReadCsv -FilePath $f.FullName
  if($a -or $b){
    $mods++
    Write-Host (" • Atualizado: " + ($f.FullName.Replace($Root, '.'))) -ForegroundColor DarkGreen
  }
}

Write-Host ""
Write-Host "Resumo:" -ForegroundColor Cyan
Write-Host (" - Ficheiros Python alterados: {0}" -f $mods)
Write-Host " - paths.py criado/atualizado em services/common/paths.py"
if($moves.Count -gt 0){ Write-Host (" - CSVs movidos: {0}" -f $moves.Count) } else { Write-Host " - Sem CSVs movidos" }
Write-Host ""
Write-Host "Sugestão: execute agora o verificador -> .\verifica_estrutura.ps1" -ForegroundColor Cyan
