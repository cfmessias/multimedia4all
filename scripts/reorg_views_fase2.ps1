$script2 = @'
param([string]$ProjectRoot = $null)
$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = $PSScriptRoot }
$Root = Resolve-Path -Path $ProjectRoot
if (-not (Test-Path (Join-Path $Root "app.py"))) { throw "A raiz '$Root' não contém app.py." }
Write-Host "==> Raiz do projeto: $Root" -ForegroundColor Cyan
function Ensure-Dir($p){ if(-not (Test-Path $p)){ New-Item -ItemType Directory -Force -Path $p | Out-Null } }
$dirs = @("services\common","music\data","music\assets","music\config","cinema\data","cinema\assets","cinema\config","radio\data","radio\assets","radio\config","podcasts\data","podcasts\assets","podcasts\config")
$dirs | % { Ensure-Dir (Join-Path $Root $_) }
$pathsPy = Join-Path $Root "services\common\paths.py"
$pathsContent = @"
# services/common/paths.py
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
MUSIC_DIR   = ROOT / "music"
CINEMA_DIR  = ROOT / "cinema"
RADIO_DIR   = ROOT / "radio"
POD_DIR     = ROOT / "podcasts"
MUSIC_DATA  = MUSIC_DIR / "data"
CINEMA_DATA = CINEMA_DIR / "data"
RADIO_DATA  = RADIO_DIR / "data"
POD_DATA    = POD_DIR / "data"
VIEWS_DIR    = ROOT / "views"
SERVICES_DIR = ROOT / "services"
for p in [MUSIC_DATA, CINEMA_DATA, RADIO_DATA, POD_DATA]:
    p.mkdir(parents=True, exist_ok=True)
"@
if(Test-Path $pathsPy){ Copy-Item $pathsPy "$pathsPy.bak" -Force }
Set-Content -Path $pathsPy -Value $pathsContent -Encoding UTF8
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
if($moves.Count -gt 0){ Write-Host "✔ CSVs movidos:" -ForegroundColor Green; $moves | % { Write-Host "   - $_" } } else { Write-Host "ℹ Nenhum CSV para mover." -ForegroundColor Yellow }
function Update-PyFile {
  param([string]$FilePath)
  try { $raw = Get-Content -Path $FilePath -Raw -Encoding UTF8 -ErrorAction Stop } catch { return $false }
  if ([string]::IsNullOrEmpty($raw)) { return $false }
  $orig = $raw
  $repl = @(
    @{ o = 'pd\.read_csv\(\s*["'']generos\.csv["'']';               n = 'pd.read_csv(MUSIC_DATA / "generos.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']hierarquia_generos\.csv["'']';     n = 'pd.read_csv(MUSIC_DATA / "hierarquia_generos.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']lista_artistas\.csv["'']';         n = 'pd.read_csv(MUSIC_DATA / "lista_artistas.csv"' },
    @{ o = 'pd\.read_csv\(\s*["''](?:dados[\\/]+)?influences_edges\.csv["'']';   n = 'pd.read_csv(MUSIC_DATA / "influences_edges.csv"' },
    @{ o = 'pd\.read_csv\(\s*["''](?:dados[\\/]+)?influences_origins\.csv["'']'; n = 'pd.read_csv(MUSIC_DATA / "influences_origins.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']cinema[\\/]+movies\.csv["'']';      n = 'pd.read_csv(CINEMA_DATA / "movies.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']cinema[\\/]+series\.csv["'']';      n = 'pd.read_csv(CINEMA_DATA / "series.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']cinema[\\/]+soundtracks\.csv["'']'; n = 'pd.read_csv(CINEMA_DATA / "soundtracks.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']movies\.csv["'']';                  n = 'pd.read_csv(CINEMA_DATA / "movies.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']series\.csv["'']';                  n = 'pd.read_csv(CINEMA_DATA / "series.csv"' },
    @{ o = 'pd\.read_csv\(\s*["'']soundtracks\.csv["'']';             n = 'pd.read_csv(CINEMA_DATA / "soundtracks.csv"' }
  )
  foreach($r in $repl){ $raw = $raw -replace $r.o, $r.n }
  $changed = ($raw -ne $orig)
  if($raw -match 'pd\.read_csv\(\s*(MUSIC_DATA|CINEMA_DATA)\s*/\s*["'']'){
    if($raw -notmatch 'from\s+services\.common\.paths\s+import\s+MUSIC_DATA(?:\s*,\s*CINEMA_DATA)?|from\s+services\.common\.paths\s+import\s+CINEMA_DATA'){
      $lines = $raw -split "`r?`n"
      $insert = 'from services.common.paths import MUSIC_DATA, CINEMA_DATA'
      $idx = 0; while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
      if($idx -gt 0){ $lines = $lines[0..($idx-1)] + @($insert) + $lines[$idx..($lines.Length-1)] } else { $lines = @($insert, '') + $lines }
      $raw = ($lines -join "`r`n"); $changed = $true
    }
  }
  if($changed){ Copy-Item $FilePath "$FilePath.bak" -Force; Set-Content -Path $FilePath -Value $raw -Encoding UTF8; return $true }
  return $false
}
$scanDirs = @("views","services") | % { Join-Path $Root $_ } | ? { Test-Path $_ }
$targets = @()
foreach($d in $scanDirs){
  $targets += Get-ChildItem -Path $d -Include *.py -Recurse -File | Where-Object { $_.FullName -notmatch '(\\\.venv\\|__pycache__|\.pytest_cache|\.mypy_cache)' }
}
$appPy = Join-Path $Root "app.py"; if(Test-Path $appPy){ $targets += Get-Item $appPy }
$modified = 0
foreach($f in $targets){ if (Update-PyFile -FilePath $f.FullName){ $modified++; Write-Host (" • Atualizado: " + ($f.FullName.Replace($Root, '.'))) -ForegroundColor DarkGreen } }
Write-Host ""; Write-Host (" - Ficheiros Python alterados: {0}" -f $modified) -ForegroundColor Cyan
Write-Host " - paths.py criado/atualizado em services/common/paths.py"
if($moves.Count -gt 0){ Write-Host (" - CSVs movidos: {0}" -f $moves.Count) } else { Write-Host " - Sem CSVs movidos" }
Write-Host ""; Write-Host "Teste: streamlit run app.py" -ForegroundColor Cyan
'@
Set-Content -Path .\migraFase2_safe.ps1 -Value $script2 -Encoding UTF8
