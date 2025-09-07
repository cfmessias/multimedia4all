$ErrorActionPreference = "Stop"
$Root = Resolve-Path -Path $PSScriptRoot
$app = Join-Path $Root "app.py"
if(-not (Test-Path $app)){ throw "Não encontrei app.py em $Root" }

# Linhas de import que queremos garantir (batem nos padrões do verificador)
$required = @(
  @{ pattern = 'from\s+views\.music\.genres\.';        line = 'from views.music.genres.page import render_genres_page' },
  @{ pattern = 'from\s+views\.music\.influence_map\.';  line = 'from views.music.influence_map.influence_map import render_influence_map_page' },
  @{ pattern = 'from\s+views\.music\.genealogy\.';      line = 'from views.music.genealogy.genealogy_page_up_down import render_genealogy_page' }
)

# Lê app.py e vê se falta algo
$content = Get-Content $app -Raw -Encoding UTF8
$missing = @()
foreach($r in $required){
  if(-not ($content -match $r.pattern)){ $missing += $r.line }
}

if($missing.Count -eq 0){
  Write-Host "Nada a fazer; imports já presentes." -ForegroundColor Green
  exit 0
}

# Inserir as linhas logo abaixo do bloco de imports existente
$lines = $content -split "`r?`n"
$idx = 0
while ($idx -lt $lines.Length -and ($lines[$idx] -match '^\s*(from\s+\S+\s+import|import\s+\S+)')) { $idx++ }

Copy-Item $app "$app.bak" -Force
$nl = [Environment]::NewLine
$newContent = ""
if($idx -gt 0){
  $head = $lines[0..($idx-1)]
  $tail = $lines[$idx..($lines.Length-1)]
  $newContent = ($head + $missing + @("") + $tail) -join $nl
}else{
  $newContent = ($missing + @("") + $lines) -join $nl
}

Set-Content -Path $app -Value $newContent -Encoding UTF8
Write-Host "app.py atualizado (backup em app.py.bak). Imports adicionados:" -ForegroundColor Green
$missing | ForEach-Object { Write-Host "  + $_" }
