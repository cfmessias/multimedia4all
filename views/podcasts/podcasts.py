# views/podcasts/podcasts.py
from __future__ import annotations

import json
from typing import Dict, List, Optional

import requests
import streamlit as st
from streamlit import components

# LocalStorage (com fallback caso a lib não exista na cloud)
try:
    from streamlit_local_storage import LocalStorage  # type: ignore
except Exception:
    class LocalStorage:  # type: ignore
        def getItem(self, k: str):
            v = st.session_state.get(f"_ls:{k}")
            return v if isinstance(v, str) else None
        def setItem(self, k: str, v: str):
            st.session_state[f"_ls:{k}"] = v

# Spotify helpers
from services.music.spotify.lookup import get_spotify_token_cached, embed_spotify

# Normalização de país/market (import + fallback local)
try:
    from services.common.locale import norm_market  # type: ignore
except Exception:
    import re
    def norm_market(m: Optional[str], default: Optional[str] = "PT") -> Optional[str]:
        if not m:
            return default
        s = str(m).strip()
        s = re.split(r"[-_]", s, maxsplit=1)[0] if s else s
        s = s.upper()
        if s == "UK":
            s = "GB"
        return s if (len(s) == 2 and s.isalpha()) else default

# Serviço de episódios (usa o teu módulo)
from services.music.spotify.episodes import list_episodes

# ===================== Defaults & LocalStorage =====================

def _default_country() -> str:
    try:
        return (st.secrets.get("COUNTRY_CODE", "PT") or "PT").upper()
    except Exception:
        return "PT"

DEFAULTS: Dict[str, object] = {"term": "", "country": _default_country(), "limit": 30}
WKEY = {"term": "pod_term", "country": "pod_country", "limit": "pod_limit"}

TOGGLE_KEY = "podcasts_show_favs_v2"

_ls = LocalStorage()

def _ls_set(key: str, value: str) -> None:
    try:
        _ls.setItem(key, value)
    except Exception:
        st.session_state[key] = value

def _ls_get(key: str) -> Optional[str]:
    try:
        return _ls.getItem(key)
    except Exception:
        v = st.session_state.get(key)
        return v if isinstance(v, str) else None

def _merge_defaults(d: Dict | None) -> Dict:
    out = DEFAULTS.copy()
    if isinstance(d, dict):
        for k in out:
            v = d.get(k, None)
            if v not in (None, ""):
                out[k] = v
    return out

def load_device_defaults() -> Dict:
    raw = _ls_get("podcasts.defaults")
    try:
        return _merge_defaults(json.loads(raw) if raw else {})
    except Exception:
        return DEFAULTS.copy()

def save_device_defaults(prefs: Dict) -> None:
    _ls_set("podcasts.defaults", json.dumps(_merge_defaults(prefs), ensure_ascii=False))

def load_device_favorites() -> List[Dict]:
    raw = _ls_get("podcasts.favorites")
    try:
        rows = json.loads(raw) if raw else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []

def save_device_favorites(rows: List[Dict]) -> None:
    _ls_set("podcasts.favorites", json.dumps(rows, ensure_ascii=False))

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
    if k and not any(r.get("key") == k for r in favs):
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
    """
    Pesquisa robusta por shows:
      P1) frase exata em shows
      P2) todas as palavras em shows
      P3) frase exata em episodes (promove show pai)
      P4) fallback simples
    Filtra resultados para garantir que todas as palavras surgem em name|publisher (sem acentos).
    """
    import unicodedata, re

    def _norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s or "")
        s = "".join(c for c in s if not unicodedata.combining(c))
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s

    def _has_all_words(hay: str, words: list[str]) -> bool:
        h = _norm(hay)
        return all(w in h for w in words)

    q_raw = (term or "").strip()
    if not q_raw:
        return []

    mk  = norm_market(country, default="PT")
    lim = max(1, min(int(limit or 30), 50))
    words = [w for w in _norm(q_raw).split(" ") if w]

    def _fetch(q: str, type_: str):
        try:
            return _sp_get(
                "/search",
                {"q": q, "type": type_, "market": mk, "limit": lim},
            )
        except Exception:
            return {}

    results: List[Dict] = []

    # P1: frase exata em shows
    data = _fetch(f'"{q_raw}"', "show")
    items = ((data.get("shows") or {}).get("items")) or []
    results += [it for it in items
                if _has_all_words(f"{it.get('name','')} {it.get('publisher','')}", words)]

    # P2: todas as palavras em shows (broad)
    if len(results) < 5 and len(words) > 1:
        data = _fetch(" ".join(words), "show")
        items = ((data.get("shows") or {}).get("items")) or []
        results += [it for it in items
                    if _has_all_words(f"{it.get('name','')} {it.get('publisher','')}", words)]

    # P3: frase exata em episodes → sobe show pai
    if len(results) < 5:
        data = _fetch(f'"{q_raw}"', "episode")
        eps = ((data.get("episodes") or {}).get("items")) or []
        for ep in eps:
            sh = (ep.get("show") or {})
            if sh and _has_all_words(f"{sh.get('name','')} {sh.get('publisher','')}", words):
                results.append(sh)

    # P4: fallback simples
    if not results:
        data = _fetch(q_raw, "show")
        results += ((data.get("shows") or {}).get("items")) or []

    # dedupe preservando ordem
    seen: set[str] = set()
    out: List[Dict] = []
    for it in results:
        sid = it.get("id")
        if sid and sid not in seen:
            seen.add(sid)
            out.append(it)

    return out[:lim]

@st.cache_data(ttl=900, show_spinner=False)
def latest_episode_id(show_id: str, country: str) -> Optional[str]:
    if not show_id:
        return None
    try:
        data = _sp_get(f"/shows/{show_id}/episodes",
                       {"market": norm_market(country, default="PT"), "limit": 1})
        items = data.get("items") or []
        return items[0]["id"] if items else None
    except Exception:
        return None

# ===================== Embed helpers =====================

def _embed(kind: str, sid: str, *, compact: bool = True):
    if not sid:
        st.info("Nothing to play.")
        return
    try:
        # versão unificada (preferida)
        embed_spotify(kind, sid, size="compact" if compact else "medium")
    except TypeError:
        # retro-compat: algumas versões aceitam height/width
        h = 152 if kind == "episode" else 232
        embed_spotify(kind, sid, height=h, width=380)
    except Exception:
        # fallback bruto
        h = 152 if kind == "episode" else 232
        components.v1.iframe(f"https://open.spotify.com/embed/{kind}/{sid}", height=h, width=380)

def _set_embed(kind: str | None, sid: str | None, idx, src: str | None):
    st.session_state["pod_embed"] = None if not kind else (kind, sid, idx, src)

def _toggle_embed(kind: str, sid: str, idx, src: str):
    cur = st.session_state.get("pod_embed")
    if cur and (cur[0], cur[1], cur[2], cur[3]) == (kind, sid, idx, src):
        _set_embed(None, None, None, None)   # fechar se clicar de novo
    else:
        _set_embed(kind, sid, idx, src)

# ===================== Página =====================

def render_podcasts_page():
    # === CSS compacto ===
    st.markdown("""
    <style>
    .stTextInput input, .stNumberInput input, .stButton > button, .stLinkButton > a {
      padding: .40rem .55rem; font-size: .92rem;
    }
    .pod-badge {
      background: #22d3ee; color: #05151b; padding: 2px 8px; border-radius: 999px;
      font-weight: 700; font-size: 0.82rem; display: inline-block; margin-top: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

    # === aplicar pedidos PENDENTES de valores (antes de criar widgets) ===
    pending_vals = st.session_state.pop("_pod_next_values", None)
    if isinstance(pending_vals, dict):
        for k in DEFAULTS:
            st.session_state[WKEY[k]] = pending_vals.get(k, DEFAULTS[k])

    # controla quais favoritos estão com a lista de episódios aberta
    if "pod_fav_eps_open" not in st.session_state:
        st.session_state["pod_fav_eps_open"] = {}  # dict[str,bool]

    # === aplicar AÇÕES agendadas (search) ANTES dos widgets ===
    pending_act = st.session_state.pop("_pod_action", None)
    if isinstance(pending_act, dict) and pending_act.get("name") == "search":
        p = pending_act.get("params") or {}
        term    = p.get("term", "")
        country = p.get("country", str(DEFAULTS["country"]))
        limit   = p.get("limit", DEFAULTS["limit"])
        results = search_shows(term, norm_market(country, default="PT") or "PT", limit)
        st.session_state["pod_results"] = results
        _set_embed(None, None, None, None)

    # === cabeçalho ===
    st.subheader("Podcasts")
    st.caption("Source: Spotify")

    if not get_spotify_token_cached():
        st.warning("Spotify credentials missing (SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET). "
                   "Search and episodes may be empty until configured.")

    # === SEARCH form (duas linhas) ===
    with st.container(border=True):
        st.markdown("#### 🔎 Search")

        # Linha 1: campos
        r1c1, r1c2, r1c3 = st.columns([0.56, 0.18, 0.26])
        with r1c1:
            st.text_input("Search", key=WKEY["term"], placeholder="e.g., science, cinema, news")
        with r1c2:
            st.text_input("Country", key=WKEY["country"], placeholder="PT", max_chars=5)
        with r1c3:
            st.slider("Results limit", 10, 50, value=int(DEFAULTS["limit"]),
                      key=WKEY["limit"], step=10)

        # Linha 2: botões
        r2c1, r2c2, r2c3, r2c4 = st.columns([0.24, 0.24, 0.24, 0.28])
        with r2c1:
            if st.button("Save defaults", use_container_width=True):
                save_device_defaults({k: st.session_state.get(WKEY[k], DEFAULTS[k]) for k in DEFAULTS})
        with r2c2:
            if st.button("Load defaults", use_container_width=True):
                prefs = load_device_defaults()
                st.session_state["_pod_next_values"] = {k: prefs[k] for k in DEFAULTS}
                st.rerun()
        with r2c3:
            if st.button("🔎 Search", type="primary", use_container_width=True):
                st.session_state["_pod_action"] = {
                    "name": "search",
                    "params": {
                        "term":    st.session_state.get(WKEY["term"], ""),
                        "country": st.session_state.get(WKEY["country"], str(DEFAULTS["country"])),
                        "limit":   st.session_state.get(WKEY["limit"], DEFAULTS["limit"]),
                    },
                }
                st.rerun()
        with r2c4:
            # Reset filters: limpa filtros, resultados e player, limpa cache e refresca
            if st.button("⟳ Reset filters", use_container_width=True):
                st.session_state["_pod_next_values"] = {k: DEFAULTS[k] for k in DEFAULTS}
                st.session_state.pop("pod_results", None)
                _set_embed(None, None, None, None)
                st.cache_data.clear()
                st.rerun()

    st.markdown("---")

    # === resultados ===
    results = st.session_state.get("pod_results", [])
    st.markdown("### Results")
    if not results:
        st.info("Enter a search term and press **Search**.")
        

    st.write(f"Found **{len(results)}** podcast(s).")
    fav_ids = {r.get("id") for r in load_device_favorites()}

    for i, show in enumerate(results, start=1):
        with st.container(border=True):
            c1, c2, c3 = st.columns([0.14, 0.56, 0.30])

            with c1:
                imgs = (show.get("images") or [])
                url = imgs[0]["url"] if imgs else ""
                st.image(url, width=56) if url else st.write("—")

            with c2:
                name  = show.get("name") or "—"
                pub   = show.get("publisher") or "—"
                langs = ", ".join(show.get("languages") or [])
                st.markdown(f"**{name}**  \n{pub}" + (f" • {langs}" if langs else ""))

            with c3:
                sid = show.get("id") or ""
                is_fav = sid in fav_ids
                a1, a2, a3 = st.columns([0.28, 0.44, 0.28])

                with a1:
                    face = "🙂" if is_fav else "🤔"
                    tip  = "Remove from favorites" if is_fav else "Add to favorites"
                    # usa o id como parte da key para evitar colisões entre runs/cartas
                    if st.button(face, key=f"pod_face_{sid}", help=tip, use_container_width=True):
                        if is_fav:
                            remove_favorite_local(sid)
                        else:
                            add_favorite_local(show)
                        st.rerun()
                with a2:
                    if st.button("Play latest", key=f"pod_play_{i}", use_container_width=True):
                        ep = latest_episode_id(sid, st.session_state.get(WKEY["country"], DEFAULTS["country"]))
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

        # Episodes (expandable, com Refresh sem cache)
        pass

    st.markdown("---")

    # === Favoritos (toggle e lista) ===
    st.markdown("### ⭐ My favorites (on this device)")

    _raw = (_ls_get("podcasts.showFavs") or "true").strip().lower()
    _show_default = _raw in ("true", "1", "yes", "on")
    show_favs = st.toggle("Show favorites", value=_show_default, key=TOGGLE_KEY)
    if show_favs != _show_default:
        _ls_set("podcasts.showFavs", "true" if show_favs else "false")

    if show_favs:
        favs = load_device_favorites()
        if not favs:
            st.info("No favorites yet.")
        else:
            st.caption(f"{len(favs)} favorite(s)")
            for j, row in enumerate(favs, start=1):
                row_key = (row.get("key") or row.get("id") or str(j)).replace(" ", "_")
                with st.container(border=True):
                    c1, c2, c3 = st.columns([0.14, 0.56, 0.30])

                    with c1:
                        if row.get("image"):
                            st.image(row["image"], width=56)
                        else:
                            st.write("—")

                    with c2:
                        name = row.get("name") or "—"
                        pub  = row.get("publisher") or "—"
                        langs = ", ".join(row.get("languages") or [])
                        meta = pub + (f" • {langs}" if langs else "")
                        st.markdown(f"**{name}**  \n{meta}")

                    with c3:
                        a1, a2, a3 = st.columns([0.28, 0.44, 0.28])

                        # 🗑 remover dos favoritos
                        with a1:
                            if st.button("🗑 Remove", key=f"fav_del_{row_key}",
                                         help="Remove from favorites", use_container_width=True):
                                remove_favorite_local(row_key)
                                # fecha lista de episódios se estiver aberta
                                st.session_state["pod_fav_eps_open"].pop(row_key, None)
                                st.rerun()

                        # 📻 abrir/fechar lista de episódios deste favorito
                        with a2:
                            opened = bool(st.session_state["pod_fav_eps_open"].get(row_key))
                            label  = "📻 Episodes (hide)" if opened else "📻 Episodes"
                            if st.button(label, key=f"fav_eps_btn_{row_key}", use_container_width=True):
                                st.session_state["pod_fav_eps_open"][row_key] = not opened
                                st.rerun()

                        with a3:
                            if row.get("url"):
                                st.link_button("Open", row["url"], use_container_width=True)

                # === lista de episódios do favorito (se aberta) ===
                if st.session_state["pod_fav_eps_open"].get(row_key):
                    with st.container(border=True):
                        sid = row.get("id") or ""
                        mk  = norm_market(st.session_state.get(WKEY["country"], str(DEFAULTS["country"])), default="PT") or "PT"

                        b1, b2 = st.columns([0.22, 0.78])
                        with b1:
                            refresh = st.button("⟳ Refresh", key=f"fav_eps_refresh_{row_key}", use_container_width=True)
                        with b2:
                            if not get_spotify_token_cached():
                                st.warning("Spotify token missing — episodes may be empty.")

                        eps_pack = (list_episodes.__wrapped__(sid, mk, limit=50, offset=0) if refresh
                                    else list_episodes(sid, mk, limit=50, offset=0))
                        eps = (eps_pack or {}).get("items") or []

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
                                    if st.button("▶ Play", key=f"fav_ep_play_{row_key}_{k}", use_container_width=True):
                                        _toggle_embed("episode", ep["id"], f"fav_ep_{row_key}_{k}", "fav_eps")
                                    emb = st.session_state.get("pod_embed")
                                    if emb and emb[2] == f"fav_ep_{row_key}_{k}" and emb[3] == "fav_eps":
                                        st.markdown('<span class="pod-badge">Playing</span>', unsafe_allow_html=True)
                                with ec3:
                                    if ep.get("url"):
                                        st.link_button("Open", ep["url"], use_container_width=True)

                                # player inline por episódio (favoritos)
                                emb = st.session_state.get("pod_embed")
                                if emb and emb[2] == f"fav_ep_{row_key}_{k}" and emb[3] == "fav_eps":
                                    _embed("episode", ep["id"])
                                    if st.button("✖ Close player", key=f"close_fav_ep_{row_key}_{k}", help="Hide player"):
                                        _set_embed(None, None, None, None)
                                        st.rerun()


    st.markdown("---")

  

if __name__ == "__main__":
    st.set_page_config(page_title="Podcasts", page_icon="🎙️", layout="centered")
    render_podcasts_page()
