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
function InjectImportIfMissing([string]$raw, [string]$importLine){
  $lines = $raw -split "`r?`n"
  # encontra fim do bloco de imports
  $idx = 0
  while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
  if($idx -gt 0){
    $head = $lines[0..($idx-1)]
    if(($head -join "`n") -notmatch [regex]::Escape($importLine)){
      $newLines = $head + @($importLine) + $lines[$idx..($lines.Length-1)]
      return ($newLines -join "`r`n")
    } else { return $raw }
  } else {
    if($raw -notmatch [regex]::Escape($importLine)){
      return ($importLine + "`r`n`r`n" + $raw)
    } else { return $raw }
  }
}

# 1) services/music/spotify/core.py
$core = Join-Path $Root "services\music\spotify\core.py"
if(Test-Path $core){
  $raw = TryRead $core
  if($raw){
    $orig = $raw
    $raw = InjectImportIfMissing $raw 'from services.common.paths import MUSIC_DATA'
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
    $raw = InjectImportIfMissing $raw 'from services.common.paths import MUSIC_DATA'
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
    $raw = InjectImportIfMissing $raw 'from services.common.paths import MUSIC_DATA'
    $lines = $raw -split "`r?`n"
    $match = $lines | Select-String -Pattern '["'']lista_artistas\.csv["'']' | Select-Object -First 1
    if($match){
      $idx = [int]$match.LineNumber - 1
      $indent = ""
      if($lines[$idx] -match '^(\s*)'){ $indent = $Matches[1] }
      # só insere se a linha anterior não for já o MUSIC_DATA
      $prevIsOurLine = $false
      if($idx -gt 0){
        if($lines[$idx-1] -match 'MUSIC_DATA\s*/\s*["'']lista_artistas\.csv["'']'){ $prevIsOurLine = $true }
      }
      if(-not $prevIsOurLine){
        $newLines = @()
        if($idx -gt 0){ $newLines += $lines[0..($idx-1)] }  # até antes da atual
        $newLines += ($indent + 'MUSIC_DATA / "lista_artistas.csv",')
        $newLines += $lines[$idx..($lines.Length-1)]
        $raw = ($newLines -join "`r`n")
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
    $raw = InjectImportIfMissing $raw 'from services.common.paths import MUSIC_DATA'
    $lines = $raw -split "`r?`n"
    $match = $lines | Select-String -Pattern '["'']hierarquia_generos\.csv["'']' | Select-Object -First 1
    if($match){
      $idx = [int]$match.LineNumber - 1
      $indent = ""
      if($lines[$idx] -match '^(\s*)'){ $indent = $Matches[1] }
      $prevIsOurLine = $false
      if($idx -gt 0){
        if($lines[$idx-1] -match 'MUSIC_DATA\s*/\s*["'']hierarquia_generos\.csv["'']'){ $prevIsOurLine = $true }
      }
      if(-not $prevIsOurLine){
        $newLines = @()
        if($idx -gt 0){ $newLines += $lines[0..($idx-1)] }
        $newLines += ($indent + 'MUSIC_DATA / "hierarquia_generos.csv",')
        $newLines += $lines[$idx..($lines.Length-1)]
        $raw = ($newLines -join "`r`n")
      }
    }
    if($raw -ne $orig){ SaveWithBackup $gcsv $raw; Write-Host " • Atualizado: .\services\genre_csv.py" -ForegroundColor DarkGreen }
  }
}

Write-Host ""
Write-Host "Patch concluído. Sugestão: correr novamente estes checks:" -ForegroundColor Cyan
Write-Host '  Get-ChildItem -Recurse -Include *.py -File ^| Select-String -Pattern ''pd\.read_csv\('' -AllMatches'
Write-Host '  Get-ChildItem -Recurse -Include *.py -File ^| Select-String -Pattern ''generos\.csv|hierarquia_generos\.csv|lista_artistas\.csv|dados[\\/](influences_edges|influences_origins)\.csv'''
