# views/podcasts/podcasts.py
from __future__ import annotations

import json
from typing import Dict, List, Optional

import requests
import streamlit as st
from streamlit_local_storage import LocalStorage
from services.music.spotify.lookup import get_spotify_token_cached, embed_spotify
from services.music.spotify.episodes import list_episodes  # <- novo serviço

# ===================== Defaults & helpers =====================

def _default_country() -> str:
    try:
        return (st.secrets.get("COUNTRY_CODE", "PT") or "PT").upper()
    except Exception:
        return "PT"

DEFAULTS = {"term": "", "country": _default_country(), "limit": 30}
WIDGET_KEYS = {"term": "pod_term", "country": "pod_country", "limit": "pod_limit"}

ls = LocalStorage()

def _merge_defaults(d: Dict | None) -> Dict:
    out = DEFAULTS.copy()
    if isinstance(d, dict):
        for k in out:
            v = d.get(k, None)
            if v not in (None, ""):
                out[k] = v
    return out

def load_device_defaults() -> Dict:
    raw = ls.getItem("podcasts.defaults")
    try:
        return _merge_defaults(json.loads(raw) if raw else {})
    except Exception:
        return DEFAULTS.copy()

def save_device_defaults(prefs: Dict) -> None:
    ls.setItem("podcasts.defaults", json.dumps(_merge_defaults(prefs), ensure_ascii=False))

def load_device_favorites() -> List[Dict]:
    raw = ls.getItem("podcasts.favorites")
    try:
        rows = json.loads(raw) if raw else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []

def save_device_favorites(rows: List[Dict]) -> None:
    ls.setItem("podcasts.favorites", json.dumps(rows, ensure_ascii=False))

def _fav_key(show: Dict) -> str:
    return str(show.get("id") or "").strip()

def _show_minimal(show: Dict) -> Dict:
    images = show.get("images") or []
    img = images[0]["url"] if images else ""
    return {
        "key": _fav_key(show),
        "id": show.get("id"),
        "name": show.get("name") or "",
        "publisher": show.get("publisher") or "",
        "languages": show.get("languages") or [],
        "image": img,
        "url": (show.get("external_urls") or {}).get("spotify", ""),
    }

def add_favorite_local(show: Dict) -> None:
    favs = load_device_favorites()
    k = _fav_key(show)
    if k and not any(f.get("key") == k for k in [k] for f in favs):
        favs.append(_show_minimal(show))
        save_device_favorites(favs)

def remove_favorite_local(key: str) -> None:
    favs = [r for r in load_device_favorites() if r.get("key") != key]
    save_device_favorites(favs)

# ===================== Spotify API helpers =====================

def _sp_headers() -> Dict:
    tok = get_spotify_token_cached()
    return {"Authorization": f"Bearer {tok}"} if tok else {}

def _sp_get(path: str, params: Dict | None = None) -> Dict:
    r = requests.get(
        f"https://api.spotify.com/v1{path}",
        headers=_sp_headers(),
        params=params or {},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=900, show_spinner=True)
def search_shows(term: str, country: str, limit: int) -> List[Dict]:
    term = (term or "").strip()
    if not term:
        return []
    try:
        data = _sp_get(
            "/search",
            {"q": term, "type": "show", "market": (country or "PT").upper(),
             "limit": max(1, min(int(limit or 30), 50))},
        )
        items = ((data.get("shows") or {}).get("items") or [])
        seen, out = set(), []
        for it in items:
            sid = it.get("id")
            if sid in seen:
                continue
            seen.add(sid)
            out.append(it)
        return out
    except Exception:
        return []

@st.cache_data(ttl=900, show_spinner=False)
def latest_episode_id(show_id: str, country: str) -> Optional[str]:
    if not show_id:
        return None
    try:
        data = _sp_get(f"/shows/{show_id}/episodes",
                       {"market": (country or "PT").upper(), "limit": 1})
        items = data.get("items") or []
        return items[0]["id"] if items else None
    except Exception:
        return None

# ===================== Embed + toggle helpers =====================

def _embed(kind: str, sid: str, *, compact: bool = True):
    if not sid:
        st.info("Nothing to play.")
        return
    height = 152 if (compact and kind == "episode") else (232 if compact else 352)
    try:
        return embed_spotify(kind, sid, height=height)
    except TypeError:
        return embed_spotify(kind, sid)

def _set_embed(kind: str | None, sid: str | None, idx, src: str | None):
    st.session_state["pod_embed"] = None if not kind else (kind, sid, idx, src)

def _toggle_embed(kind: str, sid: str, idx, src: str):
    cur = st.session_state.get("pod_embed")
    if cur and (cur[0], cur[1], cur[2], cur[3]) == (kind, sid, idx, src):
        _set_embed(None, None, None, None)   # fechar se clicar de novo
    else:
        _set_embed(kind, sid, idx, src)

# ===================== Page =====================

def render_podcasts_page():
    # Estilo: usa ciano da tab como cor primária para slider/badges/botões
    st.markdown("""
    <style>
    :root {
      --pod-accent: #22d3ee; /* cyan */
      --pod-bg-2: #2b2f36;
      --pod-bg-3: #3b4048;
      --pod-fg:   #e5e7eb;
    }
    /* botões neutros em dark */
    .stButton > button, .stLinkButton > a {
      background: var(--pod-bg-2) !important;
      color: var(--pod-fg) !important;
      border: 1px solid var(--pod-bg-3) !important;
      box-shadow: none !important;
    }
    .stButton > button:hover, .stLinkButton > a:hover {
      background: var(--pod-bg-3) !important;
      border-color: #4b5563 !important;
      color: #ffffff !important;
    }
    /* badge 'Playing' */
    .pod-badge {
      background: var(--pod-accent);
      color: #05151b;
      padding: 2px 8px;
      border-radius: 999px;
      font-weight: 700;
      font-size: 0.82rem;
      display: inline-block;
      margin-top: 6px;
    }
    /* slider com a mesma cor da tab */
    [data-testid="stSlider"] div[role="slider"] {
      background-color: var(--pod-accent) !important;
      border-color: var(--pod-accent) !important;
    }
    [data-testid="stSlider"] .css-1dp5vir,    /* label numérica (fallback) */
    [data-testid="stSlider"] .stSliderValue { /* quando existir */
      color: var(--pod-accent) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.subheader("Podcasts")
    st.caption("Source: Spotify")

    if not get_spotify_token_cached():
        st.warning("Spotify credentials missing (SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET). "
                   "Search may fail until configured.")

    # ---- Favorites (device) ----
    favs = load_device_favorites()
    st.markdown("#### ⭐ My favorites (on this device)")
    if not favs:
        st.info("No favorites yet.")
    else:
        st.caption(f"{len(favs)} favorite(s)")
        for j, row in enumerate(favs, start=1):
            with st.container(border=True):
                c1, c2, c3 = st.columns([0.14, 0.56, 0.30])

                with c1:
                    if row.get("image"):
                        st.image(row["image"], width=56)
                    else:
                        st.write("—")

                with c2:
                    name = row.get("name") or "—"
                    pub = row.get("publisher") or "—"
                    langs = ", ".join(row.get("languages") or [])
                    meta = pub + (f" • {langs}" if langs else "")
                    st.markdown(f"**{name}**  \n{meta}")

                with c3:
                    a1, a2, a3 = st.columns([0.28, 0.44, 0.28])
                    with a1:
                        st.button("🙂", key=f"fav_ok_{j}", help="In favorites",
                                  use_container_width=True, disabled=True)
                    with a2:
                        if st.button("Play latest", key=f"fav_play_{j}", use_container_width=True):
                            ep = latest_episode_id(row.get("id") or "",
                                                   st.session_state.get(WIDGET_KEYS["country"], DEFAULTS["country"]))
                            if ep:
                                _toggle_embed("episode", ep, f"fav_{j}", "fav")
                            else:
                                _toggle_embed("show", row.get("id") or "", f"fav_{j}", "fav")
                        # badge “Playing”
                        emb = st.session_state.get("pod_embed")
                        if emb and emb[2] == f"fav_{j}" and emb[3] == "fav":
                            st.markdown('<span class="pod-badge">Playing</span>', unsafe_allow_html=True)
                    with a3:
                        if row.get("url"):
                            st.link_button("Open", row["url"], use_container_width=True)

            emb = st.session_state.get("pod_embed")
            if emb and emb[2] == f"fav_{j}" and emb[3] == "fav":
                kind, sid, *_ = emb
                _embed(kind, sid)
                if st.button("✖ Close player", key=f"close_fav_{j}", help="Hide player"):
                    _set_embed(None, None, None, None)
                    st.rerun()

    st.markdown("---")

    # ---- Search form ----
    cA, cB = st.columns([3, 2])
    with cA:
        term = st.text_input("Search", key=WIDGET_KEYS["term"],
                             placeholder="e.g., science, cinema, news",
                             label_visibility="collapsed")
        country = st.text_input("Country", key=WIDGET_KEYS["country"],
                                placeholder="PT, US, ES…",
                                label_visibility="collapsed")
    with cB:
        limit = st.slider("Results limit", 10, 50, value=DEFAULTS["limit"],
                          key=WIDGET_KEYS["limit"], step=10, label_visibility="collapsed")
        cols = st.columns(2)
        with cols[0]:
            if st.button("Save defaults", use_container_width=True):
                save_device_defaults({k: st.session_state.get(WIDGET_KEYS[k], DEFAULTS[k]) for k in DEFAULTS})
        with cols[1]:
            if st.button("Load defaults", use_container_width=True):
                prefs = load_device_defaults()
                for k in DEFAULTS:
                    st.session_state[WIDGET_KEYS[k]] = prefs[k]
                st.rerun()

    c1, c2 = st.columns(2)
    with c1:
        do_search = st.button("🔎 Search", use_container_width=True)
    with c2:
        if st.button("⟳ Reset", use_container_width=True):
            for k, v in DEFAULTS.items():
                st.session_state[WIDGET_KEYS[k]] = v
            st.rerun()

    st.markdown("---")

    if do_search:
        results = search_shows(term, country or DEFAULTS["country"], limit)
        st.session_state["pod_results"] = results
        _set_embed(None, None, None, None)

    results = st.session_state.get("pod_results", [])
    if not results:
        st.info("Enter a search term and press **Search**.")
        return

    st.write(f"Found **{len(results)}** podcast(s).")
    fav_ids = {f.get("id") for f in load_device_favorites()}

    # ---- Results list ----
    for i, show in enumerate(results, start=1):
        with st.container(border=True):
            c1, c2, c3 = st.columns([0.14, 0.56, 0.30])

            with c1:
                imgs = (show.get("images") or [])
                url = imgs[0]["url"] if imgs else ""
                st.image(url, width=56) if url else st.write("—")

            with c2:
                name = show.get("name") or "—"
                pub  = show.get("publisher") or "—"
                langs = ", ".join(show.get("languages") or [])
                st.markdown(f"**{name}**  \n{pub}" + (f" • {langs}" if langs else ""))

            with c3:
                sid = show.get("id") or ""
                is_fav = sid in fav_ids
                a1, a2, a3 = st.columns([0.28, 0.44, 0.28])

                with a1:
                    face = "🙂" if is_fav else "🤔"
                    tip  = "Remove from favorites" if is_fav else "Add to favorites"
                    if st.button(face, key=f"pod_face_{i}", help=tip, use_container_width=True):
                        if is_fav:
                            remove_favorite_local(sid)
                        else:
                            add_favorite_local(show)
                        st.rerun()

                with a2:
                    if st.button("Play latest", key=f"pod_play_{i}", use_container_width=True):
                        ep = latest_episode_id(sid, country or DEFAULTS["country"])
                        if ep:
                            _toggle_embed("episode", ep, f"res_{i}", "res")
                        else:
                            _toggle_embed("show", sid, f"res_{i}", "res")
                    emb = st.session_state.get("pod_embed")
                    if emb and emb[2] == f"res_{i}" and emb[3] == "res":
                        st.markdown('<span class="pod-badge">Playing</span>', unsafe_allow_html=True)

                with a3:
                    sp = (show.get("external_urls") or {}).get("spotify", "")
                    if sp:
                        st.link_button("Open", sp, use_container_width=True)

        # Player (result card)
        emb = st.session_state.get("pod_embed")
        if emb and emb[2] == f"res_{i}" and emb[3] == "res":
            kind, sid, *_ = emb
            _embed(kind, sid)
            if st.button("✖ Close player", key=f"close_res_{i}", help="Hide player"):
                _set_embed(None, None, None, None)
                st.rerun()

        # Episodes list (expandable)
        with st.expander("Episodes", expanded=False):
            sid = show.get("id") or ""
            eps_pack = list_episodes(sid, country or DEFAULTS["country"], limit=10, offset=0)
            eps = eps_pack["items"]
            if not eps:
                st.caption("No episodes found.")
            else:
                for k, ep in enumerate(eps, start=1):
                    ec1, ec2, ec3 = st.columns([0.68, 0.18, 0.14])
                    with ec1:
                        line = f"**{ep['name']}**  \n{ep['release_date']} • {ep['duration']}"
                        if ep.get("explicit"):
                            line += " • 🔞 explicit"
                        st.markdown(line)
                    with ec2:
                        if st.button("▶ Play", key=f"ep_play_{i}_{k}", use_container_width=True):
                            _toggle_embed("episode", ep["id"], f"ep_{i}_{k}", "res_ep")
                        # badge
                        emb = st.session_state.get("pod_embed")
                        if emb and emb[2] == f"ep_{i}_{k}" and emb[3] == "res_ep":
                            st.markdown('<span class="pod-badge">Playing</span>', unsafe_allow_html=True)
                    with ec3:
                        if ep.get("url"):
                            st.link_button("Open", ep["url"], use_container_width=True)

                    # inline episode player
                    emb = st.session_state.get("pod_embed")
                    if emb and emb[2] == f"ep_{i}_{k}" and emb[3] == "res_ep":
                        _embed("episode", ep["id"])
                        if st.button("✖ Close player", key=f"close_ep_{i}_{k}", use_container_width=True):
                            _set_embed(None, None, None, None)
                            st.rerun()

