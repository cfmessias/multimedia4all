$ErrorActionPreference = "Stop"
$Root = Resolve-Path -Path $PSScriptRoot
Write-Host "==> Raiz: $Root" -ForegroundColor Cyan

function ReadText($p){
  try { Get-Content $p -Raw -Encoding UTF8 -ErrorAction Stop } catch {
    try { Get-Content $p -Raw -Encoding Default -ErrorAction Stop } catch { $null }
  }
}
function SaveWithBackup($p,$txt){
  Copy-Item $p "$p.bak" -Force
  Set-Content -Path $p -Value $txt -Encoding UTF8
}

# 1) Corrigir linhas sem "from" no app.py (ex.: 'services.music.spotify import ...')
$app = Join-Path $Root "app.py"
if(-not (Test-Path $app)){ throw "Não encontrei app.py" }
$raw = ReadText $app
$orig = $raw
# início de linha, espaços, services.music.spotify import  → prefixa "from "
$raw = [regex]::Replace($raw, '(?m)^\s*services\.music\.spotify\s+import\s+', 'from services.music.spotify import ')
if($raw -ne $orig){
  SaveWithBackup $app $raw
  Write-Host "• app.py: corrigido import sem 'from' (backup em app.py.bak)" -ForegroundColor DarkGreen
} else {
  Write-Host "• app.py: sem linhas de import quebradas" -ForegroundColor Green
}

# 2) Garantir que get_spotify_token é re-exportado por services/music/spotify/__init__.py
$pkgInit = Join-Path $Root "services\music\spotify\__init__.py"
if(-not (Test-Path $pkgInit)){
  New-Item -ItemType File -Force -Path $pkgInit | Out-Null
}

# Descobrir onde está definido get_spotify_token
$def = Get-ChildItem -Path (Join-Path $Root "services\music\spotify") -Recurse -Include *.py -File |
  Select-String -Pattern '^\s*def\s+get_spotify_token\s*\(' -AllMatches -ErrorAction SilentlyContinue |
  Select-Object -First 1

if($def){
  $moduleFile = Split-Path -Leaf $def.Path
  $moduleName = [System.IO.Path]::GetFileNameWithoutExtension($moduleFile)
  $initText = ReadText $pkgInit
  if($initText -notmatch "from\s+\.\s*$([regex]::Escape($moduleName))\s+import\s+get_spotify_token"){
    $append = "from .${moduleName} import get_spotify_token"
    if([string]::IsNullOrEmpty($initText)){ $newInit = $append + "`r`n" }
    else { $newInit = $initText.TrimEnd() + "`r`n" + $append + "`r`n" }
    SaveWithBackup $pkgInit $newInit
    Write-Host "• __init__.py: adicionado re-export 'from .$moduleName import get_spotify_token'" -ForegroundColor DarkGreen
  } else {
    Write-Host "• __init__.py: já exporta get_spotify_token" -ForegroundColor Green
  }
} else {
  Write-Host "• Aviso: não encontrei definição de get_spotify_token em services/music/spotify/*.py" -ForegroundColor Yellow
  Write-Host "         Se a função existir noutro sítio, ajusta o import no app.py para apontar ao módulo correto." -ForegroundColor Yellow
}

# 3) Verificação rápida de que não sobraram linhas 'xxx import yyy' sem 'from'
$bad = Select-String -Path $app -Pattern '^(?!\s*(from|import)\b)\s*[A-Za-z_][\w\.]*\s+import\s+' -AllMatches -ErrorAction SilentlyContinue
if($bad){
  Write-Host "• Restam linhas de import potencialmente inválidas em app.py:" -ForegroundColor Yellow
  $bad | ForEach-Object { Write-Host ("  > linha {0}: {1}" -f $_.LineNumber, $_.Line.Trim()) }
} else {
  Write-Host "• app.py: sem mais imports suspeitos" -ForegroundColor Green
}
