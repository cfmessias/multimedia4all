param([string]$ProjectRoot = $null)
$ErrorActionPreference = "Stop"

# Raiz segura
if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = $PSScriptRoot }
$Root = Resolve-Path -Path $ProjectRoot
if (-not (Test-Path (Join-Path $Root "app.py"))) { throw "A raiz '$Root' não contém app.py." }
Write-Host "==> Raiz do projeto: $Root" -ForegroundColor Cyan

function TryRead([string]$p){
  try { return Get-Content -Path $p -Raw -Encoding UTF8 -ErrorAction Stop } catch {
    try { return Get-Content -Path $p -Raw -Encoding Default -ErrorAction Stop } catch { return $null }
  }
}
function SaveWithBackup([string]$p, [string]$txt){
  Copy-Item $p "$p.bak" -Force
  Set-Content -Path $p -Value $txt -Encoding UTF8
}

# 1) services/music/spotify/core.py
$core = Join-Path $Root "services\music\spotify\core.py"
if(Test-Path $core){
  $raw = TryRead $core
  if($raw){
    $orig = $raw
    # garantir import MUSIC_DATA
    if($raw -notmatch 'from\s+services\.common\.paths\s+import\s+MUSIC_DATA'){
      $lines = $raw -split "`r?`n"
      $idx = 0; while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
      $lines = ($idx -gt 0) ? ($lines[0..($idx-1)] + @('from services.common.paths import MUSIC_DATA') + $lines[$idx..($lines.Length-1)]) : (@('from services.common.paths import MUSIC_DATA','') + $lines)
      $raw = ($lines -join "`r`n")
    }
    # "spotify_genres.csv" -> MUSIC_DATA / "spotify_genres.csv"
    $raw = $raw -replace 'pd\.read_csv\(\s*["'']spotify_genres\.csv["'']', 'pd.read_csv(MUSIC_DATA / "spotify_genres.csv"'
    # exists("generos.csv") -> exists(MUSIC_DATA / "generos.csv")
    $raw = $raw -replace 'os\.path\.exists\(\s*["'']generos\.csv["'']\s*\)', 'os.path.exists(MUSIC_DATA / "generos.csv")'

    if($raw -ne $orig){ SaveWithBackup $core $raw; Write-Host " • Atualizado: .\services\music\spotify\core.py" -ForegroundColor DarkGreen }
  }
}

# 2) views/music/genealogy/genealogy_page_up_down.py
$gen = Join-Path $Root "views\music\genealogy\genealogy_page_up_down.py"
if(Test-Path $gen){
  $raw = TryRead $gen
  if($raw){
    $orig = $raw
    # garantir import MUSIC_DATA
    if($raw -notmatch 'from\s+services\.common\.paths\s+import\s+MUSIC_DATA'){
      $lines = $raw -split "`r?`n"
      $idx = 0; while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
      $lines = ($idx -gt 0) ? ($lines[0..($idx-1)] + @('from services.common.paths import MUSIC_DATA') + $lines[$idx..($lines.Length-1)]) : (@('from services.common.paths import MUSIC_DATA','') + $lines)
      $raw = ($lines -join "`r`n")
    }
    # default "dados/influences_origins.csv" -> MUSIC_DATA / "influences_origins.csv"
    $raw = $raw -replace '["'']dados/influences_origins\.csv["'']', 'MUSIC_DATA / "influences_origins.csv"'
    if($raw -ne $orig){ SaveWithBackup $gen $raw; Write-Host " • Atualizado: .\views\music\genealogy\genealogy_page_up_down.py" -ForegroundColor DarkGreen }
  }
}

# 3) views/music/wiki/wiki_page.py  (inserir MUSIC_DATA / "lista_artistas.csv" na lista de candidatos)
$wiki = Join-Path $Root "views\music\wiki\wiki_page.py"
if(Test-Path $wiki){
  $raw = TryRead $wiki
  if($raw){
    $orig = $raw
    # garantir import
    if($raw -notmatch 'from\s+services\.common\.paths\s+import\s+MUSIC_DATA'){
      $lines = $raw -split "`r?`n"
      $idx = 0; while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
      $lines = ($idx -gt 0) ? ($lines[0..($idx-1)] + @('from services.common.paths import MUSIC_DATA') + $lines[$idx..($lines.Length-1)]) : (@('from services.common.paths import MUSIC_DATA','') + $lines)
      $raw = ($lines -join "`r`n")
    }
    # inserir linha MUSIC_DATA / "lista_artistas.csv", imediatamente antes da primeira ocorrência de "lista_artistas.csv"
    $lines = $raw -split "`r?`n"
    $i = ($lines | Select-String -Pattern '["'']lista_artistas\.csv["'']' | Select-Object -First 1).LineNumber
    if($i){
      $idx = [int]$i - 1
      $indent = ($lines[$idx] -match '^(\s*)')[1]
      if(-not ($lines[$idx-1] -match 'MUSIC_DATA\s*/\s*["'']lista_artistas\.csv["'']')){
        $lines = $lines[0..($idx-1)] + @("$indent" + 'MUSIC_DATA / "lista_artistas.csv",') + $lines[$idx..($lines.Length-1)]
        $raw = ($lines -join "`r`n")
      }
    }
    if($raw -ne $orig){ SaveWithBackup $wiki $raw; Write-Host " • Atualizado: .\views\music\wiki\wiki_page.py" -ForegroundColor DarkGreen }
  }
}

# 4) services/genre_csv.py  (inserir MUSIC_DATA / "hierarquia_generos.csv" nos candidatos)
$gcsv = Join-Path $Root "services\genre_csv.py"
if(Test-Path $gcsv){
  $raw = TryRead $gcsv
  if($raw){
    $orig = $raw
    # garantir import
    if($raw -notmatch 'from\s+services\.common\.paths\s+import\s+MUSIC_DATA'){
      $lines = $raw -split "`r?`n"
      $idx = 0; while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
      $lines = ($idx -gt 0) ? ($lines[0..($idx-1)] + @('from services.common.paths import MUSIC_DATA') + $lines[$idx..($lines.Length-1)]) : (@('from services.common.paths import MUSIC_DATA','') + $lines)
      $raw = ($lines -join "`r`n")
    }
    # inserir MUSIC_DATA / "hierarquia_generos.csv" antes da primeira ocorrência do literal
    $lines = $raw -split "`r?`n"
    $i = ($lines | Select-String -Pattern '["'']hierarquia_generos\.csv["'']' | Select-Object -First 1).LineNumber
    if($i){
      $idx = [int]$i - 1
      $indent = ($lines[$idx] -match '^(\s*)')[1]
      if(-not ($lines[$idx-1] -match 'MUSIC_DATA\s*/\s*["'']hierarquia_generos\.csv["'']')){
        $lines = $lines[0..($idx-1)] + @("$indent" + 'MUSIC_DATA / "hierarquia_generos.csv",') + $lines[$idx..($lines.Length-1)]
        $raw = ($lines -join "`r`n")
      }
    }
    if($raw -ne $orig){ SaveWithBackup $gcsv $raw; Write-Host " • Atualizado: .\services\genre_csv.py" -ForegroundColor DarkGreen }
  }
}

Write-Host ""
Write-Host "Patch concluído. Se quiseres, corre novamente:" -ForegroundColor Cyan
Write-Host "  .\verifica_estrutura.ps1"
