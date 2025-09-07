# services/common/paths.py
from pathlib import Path

# Raiz do projeto (multimedia4all/)
ROOT = Path(__file__).resolve().parents[2]

# Pastas de dados por área
MUSIC_DIR   = ROOT / "music"
CINEMA_DIR  = ROOT / "cinema"
RADIO_DIR   = ROOT / "radio"
POD_DIR     = ROOT / "podcasts"

MUSIC_DATA  = MUSIC_DIR / "data"
CINEMA_DATA = CINEMA_DIR / "data"
RADIO_DATA  = RADIO_DIR / "data"
POD_DATA    = POD_DIR / "data"

# Conveniências
VIEWS_DIR    = ROOT / "views"
SERVICES_DIR = ROOT / "services"

# Garante existência das pastas de dados
for p in [MUSIC_DATA, CINEMA_DATA, RADIO_DATA, POD_DATA]:
    p.mkdir(parents=True, exist_ok=True)
