# services/music/spotify/episodes.py
from __future__ import annotations

import requests
import streamlit as st
from services.music.spotify.search_service import get_auth_header
from services.music.spotify.lookup import get_spotify_token_cached
# Normalização de market (import + fallback)
try:
    from services.common.locale import norm_market  # type: ignore
except Exception:
    import re

def norm_market(m: str | None, default: str | None = "PT") -> str | None:
        if not m:
            return default
        s = str(m).strip()
        s = re.split(r"[-_]", s, maxsplit=1)[0] if s else s
        s = s.upper()
        if s == "UK":
            s = "GB"
        return s if (len(s) == 2 and s.isalpha()) else default
    
def _episode_date_key(ep: dict) -> str:
    """
    Cria uma chave YYYYMMDD mesmo quando release_date vem como 'YYYY' ou 'YYYY-MM'.
    Episódios sem data vão para o fim.
    """
    s = (ep.get("release_date") or "").strip()
    if not s:
        return "00000000"
    parts = s.split("-")  # "YYYY" | "YYYY-MM" | "YYYY-MM-DD"
    y = parts[0] if len(parts) > 0 else "0000"
    m = parts[1] if len(parts) > 1 else "00"
    d = parts[2] if len(parts) > 2 else "00"
    return f"{y}{m}{d}"

@st.cache_data(ttl=900, show_spinner=False)
def list_episodes(show_id: str, market: str, *, limit: int = 10, offset: int = 0):
    """
    Lista episódios de um podcast do Spotify.
    Retorna sempre {"items": [ {...}, ... ]} e filtra itens None.
    """
    if not show_id:
        return {"items": []}

    tok = get_spotify_token_cached()
    if not tok:
        return {"items": []}
    headers = {"Authorization": f"Bearer {tok}"}

    params = {
        "limit": max(1, min(int(limit or 10), 50)),
        "offset": max(0, int(offset or 0)),
    }
    mk = norm_market(market, default=None)
    if mk:
        params["market"] = mk

    try:
        r = requests.get(
            f"https://api.spotify.com/v1/shows/{show_id}/episodes",
            headers=headers, params=params, timeout=15,
        )
    except Exception:
        return {"items": []}

    if r.status_code != 200:
        return {"items": []}

    data = r.json() or {}
    raw_items = data.get("items") or []
    items = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        dur_ms = int(it.get("duration_ms") or 0)
        mm = dur_ms // 60000
        ss = (dur_ms // 1000) % 60
        items.append({
            "id": it.get("id") or "",
            "name": it.get("name") or "",
            "release_date": it.get("release_date") or "",
            "duration": f"{mm:d}:{ss:02d}",
            "explicit": bool(it.get("explicit")),
            "url": (it.get("external_urls") or {}).get("spotify") or "",
        })
    items_sorted = sorted(items, key=_episode_date_key, reverse=True)
    return {"items": items_sorted}
