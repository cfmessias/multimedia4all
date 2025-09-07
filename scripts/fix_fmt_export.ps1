param(
  [string]$ProjectRoot = $null,
  [switch]$AlsoFixLookupImport # se quiseres que o lookup.py passe a importar diretamente do módulo
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) { $ProjectRoot = $PSScriptRoot }
$Root = Resolve-Path -Path $ProjectRoot
if (-not (Test-Path (Join-Path $Root "app.py"))) { throw "A raiz '$Root' não contém app.py." }
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

$pkgDir = Join-Path $Root "services\music\spotify"
if(-not (Test-Path $pkgDir)){ throw "Não encontrei $pkgDir" }
$initPy = Join-Path $pkgDir "__init__.py"
if(-not (Test-Path $initPy)){ New-Item -ItemType File -Force -Path $initPy | Out-Null }

# 1) Descobrir o módulo que define 'fmt' (função ou variável)
$def = Get-ChildItem -Path $pkgDir -Recurse -Include *.py -File |
  Where-Object { $_.FullName -ne $initPy } |
  Select-String -Pattern '^\s*def\s+fmt\s*\(|^\s*fmt\s*=' -AllMatches -ErrorAction SilentlyContinue |
  Select-Object -First 1

if(-not $def){
  Write-Host "⚠ Não encontrei definição de 'fmt' em services/music/spotify/*.py" -ForegroundColor Yellow
  Write-Host "   Se souberes o módulo, diz-me já (ex.: search_service.py) e ajusto." -ForegroundColor Yellow
  exit 0
}

$moduleFile = Split-Path -Leaf $def.Path
$moduleName = [System.IO.Path]::GetFileNameWithoutExtension($moduleFile)
Write-Host ("• 'fmt' encontrado em: {0}" -f $moduleFile) -ForegroundColor Green

# 2) Re-exportar no __init__.py
$initTxt = TryRead $initPy; if($null -eq $initTxt){ $initTxt = "" }
$exportLine = "from .${moduleName} import fmt"
if($initTxt -notmatch [regex]::Escape($exportLine)){
  if([string]::IsNullOrWhiteSpace($initTxt)){
    SaveWithBackup $initPy ($exportLine + "`r`n")
  } else {
    SaveWithBackup $initPy ($initTxt.TrimEnd() + "`r`n" + $exportLine + "`r`n")
  }
  Write-Host "• __init__.py: adicionado export 'fmt' de .$moduleName" -ForegroundColor DarkGreen
} else {
  Write-Host "• __init__.py já exporta 'fmt' de .$moduleName" -ForegroundColor Green
}

# 3) (Opcional) Em vez de depender do export do pacote, corrigir lookup.py para importar direto do módulo
$lookup = Join-Path $pkgDir "lookup.py"
if($AlsoFixLookupImport -and (Test-Path $lookup)){
  $txt = TryRead $lookup
  if($txt){
    $orig = $txt
    # Remove 'fmt' do import do pacote, caso exista
    $txt = [regex]::Replace($txt, '(?m)^(\s*from\s+services\.music\.spotify\s+import\s+)(.*?\b)fmt\s*,?\s*(.*)$', {
      param($m)
      $pre = $m.Groups[1].Value
      $left = $m.Groups[2].Value
      $right = $m.Groups[3].Value
      $list = ($left + $right).Trim()
      if($list -match '^[,\s]+$' -or [string]::IsNullOrWhiteSpace($list)){ return "# " + $m.Value } # comenta se ficar vazio
      # arruma vírgulas duplicadas
      $list = $list -replace '^\s*,\s*','' -replace '\s*,\s*,', ', '
      return $pre + $list
    })
    # Adiciona import direto do módulo
    if($txt -notmatch [regex]::Escape("from services.music.spotify.${moduleName} import fmt")){
      $lines = $txt -split "`r?`n"
      # inserir após o bloco de imports
      $idx = 0
      while($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')){ $idx++ }
      $ins = "from services.music.spotify.${moduleName} import fmt"
      if($idx -gt 0){
        $newLines = $lines[0..($idx-1)] + @($ins) + $lines[$idx..($lines.Length-1)]
      } else {
        $newLines = @($ins,"") + $lines
      }
      $txt = ($newLines -join "`r`n")
    }
    if($txt -ne $orig){
      SaveWithBackup $lookup $txt
      Write-Host "• lookup.py: ajustado import de 'fmt' para vir de .$moduleName" -ForegroundColor DarkGreen
    }
  }
}

# 4) Verificação rápida: tenta encontrar quaisquer imports com 'X import Y' sem 'from'
$bad = Get-ChildItem -Path $pkgDir -Recurse -Include *.py -File |
  ForEach-Object {
    $t = TryRead $_.FullName
    if($null -eq $t){ return $null }
    $m = Select-String -InputObject $t -Pattern '^(?!\s*(from|import)\b)\s*[A-Za-z_][\w\.]*\s+import\s+' -AllMatches
    if($m){ ,@($_.FullName, ($m | % LineNumber), ($m | % Line)) }
  } | Where-Object { $_ -ne $null }

if($bad){
  Write-Host "ATENÇÃO: Restam imports duvidosos em services/music/spotify:" -ForegroundColor Yellow
  $bad | ForEach-Object { Write-Host ("  > {0}" -f $_[0]) }
} else {
  Write-Host "✓ Sem imports duvidosos em services/music/spotify." -ForegroundColor Green
}
