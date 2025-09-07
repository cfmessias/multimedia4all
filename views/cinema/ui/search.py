# cinema/ui/search.py
from __future__ import annotations
import re
import pandas as pd
from cinema.filters import apply_filters
from cinema.providers.tmdb import tmdb_search_movies_advanced, tmdb_search_series_advanced
from cinema.providers.spotify import search_soundtrack_albums
from .helpers import title_match_score  # <- vamos usar o mesmo score da UI

def _norm(s: str) -> str:
    # normaliza: minúsculas, só letras/dígitos/espaços, trim e comprime espaços
    s = re.sub(r'[^a-z0-9]+', ' ', str(s or '').lower())
    return re.sub(r'\s+', ' ', s).strip()

def _filter_by_title_phrase_then_fuzzy(items: list[dict], query: str) -> list[dict]:
    q = _norm(query)
    if not q:
        return items

    # 1) filtro por FRASE (mais preciso): requer a sequência completa
    phrase = [it for it in items if q in _norm(it.get("title") or it.get("name") or "")]
    if phrase:
        return phrase

    # 2) fallback: fuzzy score (evita ficar sem resultados)
    thr = 0.62 if len(q.split()) >= 2 else 0.70
    fuzzy = []
    for it in items:
        t = it.get("title") or it.get("name") or ""
        sc = title_match_score(str(t), query)
        if sc >= thr:
            fuzzy.append(it)
    return fuzzy

def run_search(section: str, df_local: pd.DataFrame, *,
               title: str, genre: str, year_txt: str, min_rating: float,
               author_key: str, author_val: str, streaming_sel: str | None,
               online: bool) -> tuple[pd.DataFrame, list[dict]]:

    # --- local (CSV)
    filters = {
        "title": title,
        "genre": genre,
        "year": year_txt,
        "min_rating": min_rating,
        "streaming": streaming_sel,
        author_key: author_val,
    }
    local_out = apply_filters(section, df_local, filters)

    # --- remoto (TMDb / Spotify)
    remote: list[dict] = []
    if online:
        if section == "Movies":
            remote = tmdb_search_movies_advanced(
                title=title,
                genre_name=(genre if genre != "All" else ""),
                year_txt=year_txt,
                director_name=author_val,
            )
        elif section == "Series":
            remote = tmdb_search_series_advanced(
                title=title,
                genre_name=(genre if genre != "All" else ""),
                year_txt=year_txt,
                creator_name=author_val,
            )
        else:  # Soundtracks page
            remote = search_soundtrack_albums(
                title=(title or ""), year_txt=year_txt, artist=(author_val or ""), limit=25
            )

    # --- filtro de streaming (mantém o teu)
    try:
        if streaming_sel in ("Yes", "No") and isinstance(remote, list):
            want = (streaming_sel == "Yes")
            def _has_streaming(it):
                v = it.get("streaming")
                if v is None:
                    v = it.get("has_streaming")
                if v is None:
                    prov = it.get("watch_providers") or it.get("providers") or {}
                    v = bool(prov)
                return bool(v)
            remote = [r for r in remote if _has_streaming(r) == want]
    except Exception:
        pass

    # --- NOVO: filtrar por frase e, se preciso, fuzzy
    if section in ("Movies", "Series"):
        remote = _filter_by_title_phrase_then_fuzzy(remote, title)

    return local_out, remote
