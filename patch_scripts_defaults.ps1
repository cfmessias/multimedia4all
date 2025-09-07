# Ajusta defaults de saída e mensagens nos scripts para music/data
$ErrorActionPreference = "Stop"
$Root = Resolve-Path -Path $PSScriptRoot

$repls = @(
  # build_influences_csv.py
  @{file="scripts\build_influences_csv.py"; o='default="dados/influences_origins\.csv"'; n='default="music/data/influences_origins.csv"'},
  @{file="scripts\build_influences_csv.py"; o='--out dados/influences_origins\.csv';     n='--out music/data/influences_origins.csv'},
  @{file="scripts\build_influences_csv.py"; o='--wikipedia-csv dados/graficos_generos\.csv'; n='--wikipedia-csv music/data/graficos_generos.csv'},
  @{file="scripts\build_influences_csv.py"; o='Saída \(por omissão\): dados/influences_origins\.csv'; n='Saída (por omissão): music/data/influences_origins.csv'},

  # build_influence_paths.py (prompts)
  @{file="scripts\build_influence_paths.py"; o='ENTER= dados/influences_origins\.csv'; n='ENTER= music/data/influences_origins.csv'},
  @{file="scripts\build_influence_paths.py"; o='ENTER= dados/influences_edges\.csv';   n='ENTER= music/data/influences_edges.csv'},

  # Mensagens/erros em services/genre_csv.py
  @{file="services\genre_csv.py"; o='Não encontrei ''hierarquia_generos\.csv'' \(nem em dados/ ou data/\)\.'; n='Não encontrei ''hierarquia_generos.csv'' (nem em music/data/).'}
)

foreach($r in $repls){
  $p = Join-Path $Root $r.file
  if(Test-Path $p){
    $raw = Get-Content $p -Raw -Encoding UTF8
    $new = [regex]::Replace($raw, $r.o, $r.n)
    if($new -ne $raw){
      Copy-Item $p "$p.bak" -Force
      Set-Content $p $new -Encoding UTF8
      Write-Host "Atualizado: .\$($r.file)"
    }
  }
}

Write-Host "Patch aplicado. Se quiseres, corre os scripts para confirmar os novos defaults."
