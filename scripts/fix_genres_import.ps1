$ErrorActionPreference = "Stop"
$Root = Resolve-Path -Path $PSScriptRoot
Write-Host "==> Raiz: $Root" -ForegroundColor Cyan

function TryRead([string]$p){
  try { Get-Content -Path $p -Raw -Encoding UTF8 -ErrorAction Stop } catch {
    try { Get-Content -Path $p -Raw -Encoding Default -ErrorAction Stop } catch { $null }
  }
}
function SaveWithBackup([string]$p,[string]$txt){
  if(Test-Path $p){ Copy-Item $p "$p.bak" -Force }
  Set-Content -Path $p -Value $txt -Encoding UTF8
}

# 1) Garantir alias em views/music/genres/page.py
$genresPage = Join-Path $Root "views\music\genres\page.py"
if(-not (Test-Path $genresPage)){ throw "Não encontrei $genresPage" }
$txt = TryRead $genresPage
if($null -eq $txt){ throw "Não consegui ler $genresPage" }

$needsAlias = $false
if($txt -notmatch '^\s*def\s+render_genres_page\s*\(' -and $txt -match '^\s*def\s+render_genres_page_roots\s*\('){
  # Só cria alias se não existir ainda
  if($txt -notmatch '(?m)^\s*render_genres_page\s*=\s*render_genres_page_roots\s*$'){
    $needsAlias = $true
  }
}
if($needsAlias){
  $newTxt = $txt.TrimEnd() + "`r`n`r`n" + "# alias para compatibilidade com app.py" + "`r`n" + "render_genres_page = render_genres_page_roots" + "`r`n"
  SaveWithBackup $genresPage $newTxt
  Write-Host "• page.py: adicionado alias 'render_genres_page = render_genres_page_roots'" -ForegroundColor DarkGreen
} else {
  Write-Host "• page.py: já expõe 'render_genres_page' (direta ou via alias)" -ForegroundColor Green
}

# 2) Garantir export no __init__.py do package views/music/genres
$pkgInit = Join-Path $Root "views\music\genres\__init__.py"
if(-not (Test-Path $pkgInit)){ New-Item -ItemType File -Force -Path $pkgInit | Out-Null }

$initTxt = TryRead $pkgInit; if($null -eq $initTxt){ $initTxt = "" }

# Se existir uma linha 'from .page import ...', assegura que inclui 'render_genres_page'
if($initTxt -match '(?m)^\s*from\s+\.page\s+import\s+([^\r\n]+)'){
  $line     = $Matches[0]
  $symbols  = $Matches[1]
  if($symbols -notmatch '(^|,\s*)render_genres_page(,|\s*$)'){
    $newLine = $line.TrimEnd() -replace '\s+$',''
    if($symbols.Trim().Length -gt 0){ $newLine = $newLine -replace [regex]::Escape($symbols), ($symbols.Trim() + ', render_genres_page') }
    else { $newLine = 'from .page import render_genres_page' }
    $initTxt = $initTxt -replace [regex]::Escape($line), $newLine
    SaveWithBackup $pkgInit $initTxt
    Write-Host "• __init__.py: adicionado 'render_genres_page' à exportação de .page" -ForegroundColor DarkGreen
  } else {
    Write-Host "• __init__.py: já exporta 'render_genres_page'" -ForegroundColor Green
  }
} else {
  # Não havia linha: cria uma
  $newInit = ($initTxt.TrimEnd() + "`r`nfrom .page import render_genres_page`r`n")
  SaveWithBackup $pkgInit $newInit
  Write-Host "• __init__.py: criada exportação 'from .page import render_genres_page'" -ForegroundColor DarkGreen
}

Write-Host ""
Write-Host "Feito. Experimenta arrancar a app. Se surgir outro import em falta, manda o traceback." -ForegroundColor Cyan
