$ErrorActionPreference = "Stop"
$Root = Resolve-Path -Path $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "app.py"))) { throw "A raiz '$Root' não contém app.py." }
Write-Host "==> Raiz do projeto: $Root" -ForegroundColor Cyan
function Ensure-Dir($p){ if(-not (Test-Path $p)){ New-Item -ItemType Directory -Force -Path $p | Out-Null } }
$targets = @("views\music\spotify","views\music\genres","views\music\wiki","views\music\influence_map","views\music\genealogy","views\music\playlists","views\cinema\ui")
$targets | % { Ensure-Dir (Join-Path $Root $_) }
$pkgs = @("views","views\music","views\cinema","views\music\spotify","views\music\genres","views\music\wiki","views\music\influence_map","views\music\genealogy","views\music\playlists")
$pkgs | % { $p = Join-Path $Root ($_ + "\__init__.py"); if(-not (Test-Path $p)){ New-Item -ItemType File -Force -Path $p | Out-Null } }
if(Test-Path "$Root\views\spotify"){ Move-Item "$Root\views\spotify" "$Root\views\music\spotify" -Force }
if(Test-Path "$Root\views\genres"){  Move-Item "$Root\views\genres"  "$Root\views\music\genres"  -Force }
if(Test-Path "$Root\views\wiki_page.py"){ Move-Item "$Root\views\wiki_page.py" "$Root\views\music\wiki\wiki_page.py" -Force }
Get-ChildItem "$Root\views" -Filter "influence_map*.py" -File -ErrorAction SilentlyContinue | % { Move-Item $_.FullName (Join-Path "$Root\views\music\influence_map" $_.Name) -Force }
Get-ChildItem "$Root\views" -Filter "genealogy*.py" -File -ErrorAction SilentlyContinue | % { Move-Item $_.FullName (Join-Path "$Root\views\music\genealogy" $_.Name) -Force }
if(Test-Path "$Root\views\playlists_page.py"){ Move-Item "$Root\views\playlists_page.py" "$Root\views\music\playlists\playlists_page.py" -Force }
if(Test-Path "$Root\cinema\page.py"){ Ensure-Dir "$Root\views\cinema"; Move-Item "$Root\cinema\page.py" "$Root\views\cinema\page.py" -Force }
if(Test-Path "$Root\cinema\ui"){ Ensure-Dir "$Root\views\cinema\ui"; Move-Item "$Root\cinema\ui\*" "$Root\views\cinema\ui" -Force; Remove-Item "$Root\cinema\ui" -Force -Recurse }
$app = Join-Path $Root "app.py"; if(-not (Test-Path $app)){ throw "Não encontrei app.py" }
Copy-Item $app "$app.bak" -Force
$content = Get-Content $app -Raw -Encoding UTF8
$rules = @(
  @{ pattern = 'from\s+views\.spotify\.';                           replace = 'from views.music.spotify.' },
  @{ pattern = 'from\s+views\.genres\.';                             replace = 'from views.music.genres.' },
  @{ pattern = 'from\s+views\.wiki_page\s+import';                   replace = 'from views.music.wiki.wiki_page import' },
  @{ pattern = 'from\s+views\.playlists_page\s+import';              replace = 'from views.music.playlists.playlists_page import' },
  @{ pattern = 'from\s+views\.influence_map([_\w]*)\s+import';       replace = 'from views.music.influence_map.influence_map$1 import' },
  @{ pattern = 'from\s+views\.genealogy([_\w]*)\s+import';           replace = 'from views.music.genealogy.genealogy$1 import' },
  @{ pattern = 'from\s+cinema\.page\s+import';                       replace = 'from views.cinema.page import' }
)
foreach($r in $rules){ $content = [Regex]::Replace($content, $r.pattern, $r.replace) }
Set-Content -Path $app -Value $content -Encoding UTF8
Write-Host "✔ Fase 1 concluída (views movidas + imports; backup em app.py.bak)." -ForegroundColor Green
Write-Host "Teste: streamlit run app.py" -ForegroundColor Cyan
