# fix_genres_page_alias.ps1
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

# 1) Alias dentro de views/music/genres/page.py
$genresPage = Join-Path $Root "views\music\genres\page.py"
if(-not (Test-Path $genresPage)){ throw "Não encontrei $genresPage" }
$pg = TryRead $genresPage; if($null -eq $pg){ throw "Não consegui ler $genresPage" }

$needsAliasInPage = $false
if($pg -notmatch '(?m)^\s*def\s+render_genres_page\s*\('){
  if($pg -match '(?m)^\s*def\s+render_genres_page_roots\s*\('){
    if($pg -notmatch '(?m)^\s*render_genres_page\s*=\s*render_genres_page_roots\s*$'){
      $needsAliasInPage = $true
    }
  } else {
    Write-Host "⚠ Em page.py não encontrei render_genres_page_roots(). Confirma o nome da função." -ForegroundColor Yellow
  }
}
if($needsAliasInPage){
  $pg_new = $pg.TrimEnd() + "`r`n`r`n# alias de compatibilidade`r`nrender_genres_page = render_genres_page_roots`r`n"
  SaveWithBackup $genresPage $pg_new
  Write-Host "• page.py: adicionado alias 'render_genres_page = render_genres_page_roots'" -ForegroundColor DarkGreen
} else {
  Write-Host "• page.py: já expõe 'render_genres_page' (direta ou via alias)" -ForegroundColor Green
}

# 2) Corrigir views/music/genres/__init__.py
$initPath = Join-Path $Root "views\music\genres\__init__.py"
if(-not (Test-Path $initPath)){ New-Item -ItemType File -Force -Path $initPath | Out-Null }
$it = TryRead $initPath; if($null -eq $it){ $it = "" }

# a) Ajustar linha 'from .page import ...' removendo render_genres_page se não existir em page.py
$it_new = $it
$hadFromPage = $false
$matches = Select-String -InputObject $it -Pattern '^(?m)\s*from\s+\.page\s+import\s+([^\r\n#]+)'
if($matches){
  $hadFromPage = $true
  $line = $matches.Matches[0].Value
  $symbols = $matches.Matches[0].Groups[1].Value
  # normalizar: tirar espaços extra
  $symList = ($symbols -split '\s*,\s*') | Where-Object { $_ -ne "" }
  # garantir que inclui render_genres_page_roots
  if(-not ($symList -contains 'render_genres_page_roots')){ $symList += 'render_genres_page_roots' }
  # remover render_genres_page (vai ficar via alias)
  $symList = $symList | Where-Object { $_ -ne 'render_genres_page' }
  $newLine = 'from .page import ' + ($symList -join ', ')
  if($newLine -ne $line){ $it_new = $it_new -replace [regex]::Escape($line), [System.Text.RegularExpressions.Regex]::Escape($newLine).Replace('\','\\') ; $it_new = $it_new -replace [regex]::Escape($line), $newLine }
} else {
  # não existia — cria
  $prefix = $it_new.TrimEnd()
  if($prefix.Length -gt 0){ $prefix += "`r`n" }
  $it_new = $prefix + "from .page import render_genres_page_roots`r`n"
  $hadFromPage = $true
}

# b) Criar alias também no __init__ (opcional, não atrapalha)
if($it_new -notmatch '(?m)^\s*render_genres_page\s*=\s*render_genres_page_roots\s*$'){
  $it_new = $it_new.TrimEnd() + "`r`n" + "render_genres_page = render_genres_page_roots" + "`r`n"
}

if($it_new -ne $it){
  SaveWithBackup $initPath $it_new
  Write-Host "• __init__.py: import de .page ajustado e alias criado" -ForegroundColor DarkGreen
} else {
  Write-Host "• __init__.py: já está compatível" -ForegroundColor Green
}

Write-Host ""
Write-Host "Feito. Tenta arrancar a app agora:  streamlit run app.py  (ou python app.py)" -ForegroundColor Cyan
