# views/radio/radio.py
# Internet Radio (Radio Browser) — per-device defaults & favorites via localStorage
# UI compacta (mobile), 🤔/🙂 favoritos, único player ativo, sem CSV.

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

import requests
import streamlit as st
from streamlit_local_storage import LocalStorage


# =========================
#   Config / Constantes
# =========================

RADIO_BROWSER_ENDPOINT = "https://de1.api.radio-browser.info/json/stations/search"
REQ_TIMEOUT = 12  # seg

DEFAULTS: Dict[str, object] = {
    "name": "",
    "country": "",
    "tag": "",
    "codec": "",
    "bitrate_min": 0,
    "limit": 20,
    "show_favs": True,
}

# instancia localStorage (browser) — segura para usar em callbacks
ls = LocalStorage()


# =========================
#   Helpers de LocalStorage
# =========================

def _ls_set(key: str, value: str) -> None:
    try:
        ls.setItem(key, value)
    except Exception:
        # ambiente sem localStorage (ex.: teste headless)
        st.session_state[key] = value

def _ls_get(key: str) -> Optional[str]:
    try:
        return ls.getItem(key)
    except Exception:
        return st.session_state.get(key)

def _ls_save_bool(key: str, val: bool) -> None:
    _ls_set(key, "true" if val else "false")

def _ls_load_bool(key: str, default: bool = False) -> bool:
    raw = _ls_get(key)
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in ("true", "1", "yes", "on"):  return True
        if s in ("false", "0", "no", "off"): return False
    return bool(default)


# =========================
#   Defaults por dispositivo
# =========================

def _merge_defaults(data: Dict | None) -> Dict:
    base = DEFAULTS.copy()
    if isinstance(data, dict):
        for k, v in data.items():
            if k in base:
                base[k] = v
    return base

def load_device_defaults() -> Dict:
    raw = _ls_get("radio.defaults")
    try:
        return _merge_defaults(json.loads(raw) if raw else {})
    except Exception:
        return DEFAULTS.copy()

def save_device_defaults(d: Dict) -> None:
    payload = {k: d.get(k, DEFAULTS[k]) for k in DEFAULTS}
    _ls_set("radio.defaults", json.dumps(payload, ensure_ascii=False))


# =========================
#   Favoritos (no device)
# =========================

def _fav_key(s: Dict) -> str:
    # chave estável por estação
    url = (s.get("url_resolved") or s.get("url") or "").strip().lower()
    uuid = (s.get("stationuuid") or "").strip().lower()
    name = (s.get("name") or "").strip().lower()
    home = (s.get("homepage") or "").strip().lower()
    return uuid or url or (name + "|" + home)

def load_device_favorites() -> List[Dict]:
    raw = _ls_get("radio.favorites")
    try:
        rows = json.loads(raw) if raw else []
        return rows if isinstance(rows, list) else []
    except Exception:
        return []

def save_device_favorites(rows: List[Dict]) -> None:
    _ls_set("radio.favorites", json.dumps(rows, ensure_ascii=False))

def add_favorite_local(station: Dict) -> None:
    favs = load_device_favorites()
    k = _fav_key(station)
    if not k:
        return
    if any(_fav_key(x) == k for x in favs):
        return
    favs.append({
        "key": _fav_key(station),
        "name": station.get("name") or "",
        "url": (station.get("url_resolved") or station.get("url") or ""),
        "homepage": (station.get("homepage") or ""),
        "countrycode": (station.get("countrycode") or station.get("country") or ""),
        "codec": (station.get("codec") or ""),
        "bitrate": int(station.get("bitrate") or 0),
        "tags": station.get("tags") or station.get("tag") or "",
        "favicon": (station.get("favicon") or ""),
        "stationuuid": (station.get("stationuuid") or ""),
    })
    save_device_favorites(favs)

def remove_favorite_local(key: str) -> None:
    favs = [x for x in load_device_favorites() if _fav_key(x) != key]
    save_device_favorites(favs)


# =========================
#   API Radio Browser
# =========================

def _clean_query_text(s: str) -> str:
    return (s or "").strip()

def _parse_tags(s: str) -> str:
    # normaliza tags "a, b; c d" -> "a,b,c,d"
    toks = [t for t in re.split(r"[;, ]+", (s or "").strip()) if t]
    return ",".join(sorted(set(toks)))

def search_stations(name: str = "", country: str = "", tag: str = "",
                    codec: str = "", bitrate_min: int = 0, limit: int = 20) -> List[Dict]:
    params = {
        "name": _clean_query_text(name),
        "countrycode": _clean_query_text(country),
        "tagList": _parse_tags(tag),
        "codec": _clean_query_text(codec).lower(),
        "bitrate_min": max(0, int(bitrate_min or 0)),
        "is_https": True,
        "order": "clickcount",   # popularidade
        "reverse": False,
        "hidebroken": True,
        "limit": max(1, min(int(limit or 20), 50)),
        "offset": 0,
    }
    # remove vazios
    params = {k: v for k, v in params.items() if v not in ("", None)}

    try:
        r = requests.get(RADIO_BROWSER_ENDPOINT, params=params, timeout=REQ_TIMEOUT)
        if r.status_code != 200:
            return []
        data = r.json() or []
        # protege contra itens None
        return [x for x in data if isinstance(x, dict)]
    except Exception:
        return []


# =========================
#   UI helpers
# =========================

def _ensure_ss_defaults() -> None:
    if "radio_defaults" not in st.session_state:
        st.session_state["radio_defaults"] = load_device_defaults()
    st.session_state.setdefault("radio_results", [])
    st.session_state.setdefault("radio_play_url", "")
    st.session_state.setdefault("radio_play_idx", None)
    st.session_state.setdefault("radio_play_source", None)
    st.session_state.setdefault("radio_audio_rev", 0)  # bump para forçar rerender

def _result_logo_url(s: Dict) -> Optional[str]:
    raw = (s.get("favicon") or "").strip()
    return raw or None

def _format_tags(s: str) -> str:
    if not s:
        return ""
    toks = [t for t in re.split(r"[;, ]+", s) if t]
    return ", ".join(sorted(set(toks)))


# =========================
#   Página principal
# =========================

def render_radio_page() -> None:
    _ensure_ss_defaults()
    d = st.session_state["radio_defaults"]

    st.title("📻 Rádio (Radio Browser)")

    with st.container(border=True):
        st.markdown("#### 🔎 Pesquisa")
        c1, c2, c3, c4, c5 = st.columns([0.32, 0.18, 0.20, 0.15, 0.15])

        with c1:
            d["name"] = st.text_input("Nome contém", value=str(d.get("name", "")), key="radio_name")
        with c2:
            d["country"] = st.text_input("País (código ISO2)", value=str(d.get("country", "")), max_chars=2, key="radio_country")
        with c3:
            d["tag"] = st.text_input("Tags (a,b,c)", value=str(d.get("tag", "")), key="radio_tag")
        with c4:
            codec_opts = ["", "mp3", "aac", "ogg", "opus"]
            cur_codec = str(d.get("codec", "") or "").strip().lower()
            if cur_codec not in codec_opts:  # trata "(any)" e afins
                cur_codec = ""
            d["codec"] = st.selectbox("Codec", codec_opts, index=codec_opts.index(cur_codec), key="radio_codec")
        with c5:
            d["bitrate_min"] = st.number_input("Bitrate ≥", min_value=0, max_value=320, step=16, value=int(d.get("bitrate_min", 0)), key="radio_bitrate_min")

        c6, c7, _ = st.columns([0.22, 0.20, 0.58])
        with c6:
            d["limit"] = st.slider("Limite", min_value=5, max_value=50, step=5, value=int(d.get("limit", 20)), key="radio_limit")
        with c7:
            if st.button("Pesquisar", type="primary", use_container_width=True):
                results = search_stations(
                    name=d.get("name",""),
                    country=d.get("country",""),
                    tag=d.get("tag",""),
                    codec=d.get("codec",""),
                    bitrate_min=int(d.get("bitrate_min", 0)),
                    limit=int(d.get("limit", 20)),
                )
                st.session_state["radio_results"] = results
                save_device_defaults(d)

    st.markdown("---")

    # =========================
    #   Resultados (primeiro)
    # =========================
    results = st.session_state.get("radio_results", [])
    st.markdown("### Resultados")

    if not results:
        st.info("Use os filtros acima e carregue em **Pesquisar** para encontrar estações.")
    else:
        # favoritos atuais (para pintar 🤔/🙂 nos resultados)
        fav_keys = {_fav_key(r) for r in load_device_favorites()}
        st.caption(f"{len(results)} estação(ões) encontradas.")

        for i, s in enumerate(results, start=1):
            with st.container(border=True):
                cols = st.columns([0.12, 0.63, 0.25])

                # Logo — 40px
                with cols[0]:
                    logo = _result_logo_url(s)
                    if logo:
                        st.image(logo, width=40)
                    else:
                        st.write("—")

                # Info
                with cols[1]:
                    name = s.get("name") or "—"
                    country = s.get("countrycode") or s.get("country") or "—"
                    codec = (s.get("codec") or "—").upper()
                    br = int(s.get("bitrate") or 0)
                    tags = s.get("tags") or s.get("tag") or ""
                    st.markdown(f"**{name}**  \n{country} • {codec} • {br} kbps")
                    if tags:
                        st.caption(_format_tags(tags))

                # Actions
                with cols[2]:
                    url = s.get("url_resolved") or s.get("url") or ""
                    key = _fav_key(s)
                    is_fav = key in fav_keys

                    a1, a2, a3 = st.columns([0.25, 0.4, 0.35])

                    with a1:
                        face = "🙂" if is_fav else "🤔"
                        tip  = "Remover dos favoritos" if is_fav else "Adicionar aos favoritos"
                        if st.button(face, key=f"radio_res_face_{i}", help=tip, use_container_width=True):
                            if is_fav:
                                remove_favorite_local(key)
                            else:
                                add_favorite_local(s)
                            st.rerun()

                    with a2:
                        if st.button("Play", key=f"radio_res_play_{i}", use_container_width=True):
                            st.session_state["radio_play_url"] = url
                            st.session_state["radio_play_idx"] = i
                            st.session_state["radio_play_source"] = "results"
                            st.session_state["radio_audio_rev"] += 1

                    with a3:
                        home = (s.get("homepage") or "").strip()
                        if home:
                            st.link_button("Homepage", home, use_container_width=True)

                # Inline player (apenas um ativo)
                if (
                    st.session_state.get("radio_play_source") == "results" and
                    st.session_state.get("radio_play_idx") == i and
                    st.session_state.get("radio_play_url")
                ):
                    st.audio(st.session_state["radio_play_url"])
                    st.caption(st.session_state["radio_play_url"])

    st.markdown("---")

    # =========================
    #   Favoritos (DEPOIS)
    # =========================
    st.markdown("### ⭐ Favoritos (neste dispositivo)")

    show_favs = st.toggle(
        "Mostrar lista de favoritos",
        value=_ls_load_bool("radio.showFavs", bool(DEFAULTS["show_favs"])),
        key="radio_show_favs",
    )
    # persistência da preferência (e rerender suave)
    if show_favs != _ls_load_bool("radio.showFavs", bool(DEFAULTS["show_favs"])):
        _ls_save_bool("radio.showFavs", bool(show_favs))
        st.rerun()

    if show_favs:
        favs = load_device_favorites()
        if not favs:
            st.info("Ainda não tem favoritos. Use **🤔** para adicionar a partir dos resultados.")
        else:
            st.caption(f"{len(favs)} favorito(s). Toque em **Play** para ouvir.")
            for j, row in enumerate(favs, start=1):
                with st.container(border=True):
                    cols = st.columns([0.12, 0.63, 0.25])

                    # logo
                    with cols[0]:
                        favico = (row.get("favicon") or "").strip()
                        if favico:
                            st.image(favico, width=40)
                        else:
                            st.write("—")

                    # info
                    with cols[1]:
                        name = row.get("name") or "—"
                        country = row.get("countrycode") or "—"
                        codec = (row.get("codec") or "—").upper()
                        br = int(row.get("bitrate") or 0)
                        tags = row.get("tags") or ""
                        st.markdown(f"**{name}**  \n{country} • {codec} • {br} kbps")
                        if tags:
                            st.caption(_format_tags(tags))

                    # actions
                    with cols[2]:
                        a1, a2, a3 = st.columns([0.25, 0.4, 0.35])

                        with a1:
                            # sempre “🙂” porque já é favorito; botão para remover
                            if st.button("🙂", key=f"radio_fav_icon_{j}", help="Remover dos favoritos", use_container_width=True):
                                remove_favorite_local(_fav_key(row))
                                st.rerun()

                        with a2:
                            if st.button("Play", key=f"radio_fav_play_{j}", use_container_width=True):
                                st.session_state["radio_play_url"] = row.get("url","")
                                st.session_state["radio_play_idx"] = f"fav_{j}"
                                st.session_state["radio_play_source"] = "favorites"
                                st.session_state["radio_audio_rev"] += 1

                        with a3:
                            home = (row.get("homepage") or "").strip()
                            if home:
                                st.link_button("Homepage", home, use_container_width=True)

                    # inline player
                    if (
                        st.session_state.get("radio_play_source") == "favorites" and
                        st.session_state.get("radio_play_idx") == f"fav_{j}" and
                        st.session_state.get("radio_play_url")
                    ):
                        st.audio(st.session_state["radio_play_url"])
                        st.caption(st.session_state["radio_play_url"])


# Permite correr isolado para teste rápido
if __name__ == "__main__":
    st.set_page_config(page_title="Rádio", page_icon="📻", layout="centered")
    render_radio_page()
