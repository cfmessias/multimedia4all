# Verificador de estrutura do projeto multimedia4all
$ErrorActionPreference = "Stop"
$Root = Resolve-Path -Path $PSScriptRoot
Write-Host "==> A verificar raiz: $Root" -ForegroundColor Cyan
function P($ok,$msg){ if($ok){Write-Host "  PASS " -ForegroundColor Green -NoNewline}else{Write-Host "  FAIL " -ForegroundColor Red -NoNewline}; Write-Host $msg }

# 1) Pastas de topo
$topDirs = "views","services","music","cinema","radio","podcasts"
foreach($d in $topDirs){ P (Test-Path (Join-Path $Root $d)) "Existe pasta '$d'?" }

# 2) Estrutura de views/music
$vm = "views\music\spotify","views\music\genres","views\music\wiki","views\music\influence_map","views\music\genealogy","views\music\playlists"
foreach($d in $vm){ P (Test-Path (Join-Path $Root $d)) "Existe '$d'?" }

# 3) views/cinema
P (Test-Path (Join-Path $Root "views\cinema\page.py")) "Existe 'views/cinema/page.py'?"
P (Test-Path (Join-Path $Root "views\cinema\ui")) "Existe 'views/cinema/ui/' (opcional)?"

# 4) services/common/paths.py
P (Test-Path (Join-Path $Root "services\common\paths.py")) "Existe 'services/common/paths.py'?"

# 5) CSVs: música
$musicData = Join-Path $Root "music\data"
$musCsv = "generos.csv","hierarquia_generos.csv","lista_artistas.csv","influences_edges.csv","influences_origins.csv"
foreach($f in $musCsv){ P (Test-Path (Join-Path $musicData $f)) "CSV música presente: $f?" }

# 6) CSVs: cinema
$cinData = Join-Path $Root "cinema\data"
$cinCsv = "movies.csv","series.csv","soundtracks.csv"
foreach($f in $cinCsv){ P (Test-Path (Join-Path $cinData $f)) "CSV cinema presente: $f?" }

# 7) Root “limpo” de CSVs que deviam ter sido movidos
$rootBad = @("generos.csv","hierarquia_generos.csv","lista_artistas.csv","movies.csv","series.csv","soundtracks.csv")
$badFound = @()
foreach($f in $rootBad){ if(Test-Path (Join-Path $Root $f)){ $badFound += $f } }
P ($badFound.Count -eq 0) "Sem CSVs indevidos na raiz? $(if($badFound){'Encontrados: '+($badFound -join ', ') } else {'—'})"

# 8) “Dados” antigos
P (-not (Test-Path (Join-Path $Root "dados\influences_edges.csv"))) "Sem 'dados/influences_edges.csv'?"
P (-not (Test-Path (Join-Path $Root "dados\influences_origins.csv"))) "Sem 'dados/influences_origins.csv'?"

# 9) Imports antigos no código (não deviam existir)
$codeDirs = @("views","services")
$oldImports = @(
  'from\s+views\.spotify\.',
  'from\s+views\.genres\.',
  'from\s+views\.wiki_page\s+import',
  'from\s+views\.playlists_page\s+import',
  'from\s+views\.influence_map(\w*)\s+import',
  'from\s+views\.genealogy(\w*)\s+import',
  'from\s+cinema\.page\s+import'
)
$oldHits = @()
foreach($dir in $codeDirs){
  if(Test-Path (Join-Path $Root $dir)){
    $hits = Select-String -Path (Join-Path $Root "$dir\**\*.py") -Pattern $oldImports -AllMatches -ErrorAction SilentlyContinue
    if($hits){ $oldHits += $hits }
  }
}
P ($oldHits.Count -eq 0) "Sem imports antigos? $(if($oldHits){'Restam '+$oldHits.Count} else {'—'})"
if($oldHits){ $oldHits | ForEach-Object { Write-Host "    > $($_.Path):$($_.LineNumber)  $($_.Line.Trim())" -ForegroundColor DarkYellow } }

# 10) Imports novos esperados no app.py
$app = Join-Path $Root "app.py"
if(Test-Path $app){
  $appText = Get-Content $app -Raw
  $must = @(
    'from\s+views\.music\.spotify\.',
    'from\s+views\.music\.genres\.',
    'from\s+views\.music\.playlists\.',
    'from\s+views\.music\.influence_map\.',
    'from\s+views\.music\.genealogy\.',
    'from\s+views\.cinema\.page\s+import'
  )
  $miss = @()
  foreach($m in $must){ if(-not ($appText -match $m)){ $miss += $m } }
  P ($miss.Count -eq 0) "app.py com imports novos?"
  if($miss){ $miss | ForEach-Object { Write-Host "    > Falta padrão: $_" -ForegroundColor DarkYellow } }
} else {
  P $false "Não encontrei app.py"
}

# 11) Leitura de CSVs: confirmar que usam MUSIC_DATA/CINEMA_DATA
$newPathHits = Select-String -Path (Join-Path $Root "views\**\*.py"), (Join-Path $Root "services\**\*.py") `
  -Pattern 'pd\.read_csv\(\s*(MUSIC_DATA|CINEMA_DATA)\s*/\s*["'']' -AllMatches -ErrorAction SilentlyContinue
P ($newPathHits.Count -ge 1) "Há leituras com MUSIC_DATA/CINEMA_DATA?"
# E procurar leituras “antigas” ainda por substituir
$oldReads = @(
  'pd\.read_csv\(\s*["'']generos\.csv["'']',
  'pd\.read_csv\(\s*["'']hierarquia_generos\.csv["'']',
  'pd\.read_csv\(\s*["'']lista_artistas\.csv["'']',
  'pd\.read_csv\(\s*["'']cinema[\\/]+movies\.csv["'']',
  'pd\.read_csv\(\s*["'']cinema[\\/]+series\.csv["'']',
  'pd\.read_csv\(\s*["'']cinema[\\/]+soundtracks\.csv["'']',
  'pd\.read_csv\(\s*["'']movies\.csv["'']',
  'pd\.read_csv\(\s*["'']series\.csv["'']',
  'pd\.read_csv\(\s*["'']soundtracks\.csv["'']',
  'pd\.read_csv\(\s*["''](?:dados[\\/]+)?influences_edges\.csv["'']',
  'pd\.read_csv\(\s*["''](?:dados[\\/]+)?influences_origins\.csv["'']'
)
$legacy = Select-String -Path (Join-Path $Root "views\**\*.py"), (Join-Path $Root "services\**\*.py") `
  -Pattern $oldReads -AllMatches -ErrorAction SilentlyContinue
P ($legacy.Count -eq 0) "Sem leituras antigas de CSV?"
if($legacy){ $legacy | ForEach-Object { Write-Host "    > $($_.Path):$($_.LineNumber)  $($_.Line.Trim())" -ForegroundColor DarkYellow } }

Write-Host ""
Write-Host "Sugestões rápidas:" -ForegroundColor Cyan
Write-Host " - Vê a árvore:  tree /F /A .\views\music" -ForegroundColor Gray
Write-Host " - Teste de runtime:  streamlit run app.py" -ForegroundColor Gray
