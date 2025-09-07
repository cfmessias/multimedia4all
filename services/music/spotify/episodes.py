# services/spotify/episodes.py
from __future__ import annotations
import requests
import streamlit as st
from services.music.spotify.lookup import get_spotify_token_cached

def _sp_headers() -> dict:
    tok = get_spotify_token_cached()
    return {"Authorization": f"Bearer {tok}"} if tok else {}

def _sp_get(path: str, params: dict | None = None) -> dict:
    r = requests.get(
        f"https://api.spotify.com/v1{path}",
        headers=_sp_headers(),
        params=params or {},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def _fmt_dur(ms) -> str:
    try:
        ms = int(ms)
        m, s = divmod(ms // 1000, 60)
        h, m = divmod(m, 60)
        return f"{h:d}:{m:02d}:{s:02d}" if h else f"{m:d}:{s:02d}"
    except Exception:
        return ""

@st.cache_data(ttl=900, show_spinner=False)
def list_episodes(show_id: str, market: str, limit: int = 20, offset: int = 0) -> dict:
    """
    Devolve {"items":[{id,name,release_date,duration,url,explicit,description}], "has_more":bool, "next_offset":int|None}
    """
    if not (show_id or "").strip():
        return {"items": [], "has_more": False, "next_offset": None}

    data = _sp_get(
        f"/shows/{show_id}/episodes",
        {"market": (market or "PT").upper(), "limit": max(1, min(limit, 50)), "offset": max(0, offset)},
    )
    items = data.get("items") or []
    out = []
    for it in items:
        out.append({
            "id": it.get("id"),
            "name": it.get("name") or "",
            "release_date": it.get("release_date") or "",
            "duration": _fmt_dur(it.get("duration_ms")),
            "url": (it.get("external_urls") or {}).get("spotify", ""),
            "explicit": bool(it.get("explicit")),
            "description": it.get("description") or "",
        })
    has_more = bool(data.get("next"))
    next_offset = (offset + len(items)) if has_more else None
    return {"items": out, "has_more": has_more, "next_offset": next_offset}

