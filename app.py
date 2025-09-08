from __future__ import annotations
from services.music.spotify.core import get_spotify_token
import importlib
import os
import streamlit as st
from views.music.genres.page import render_genres_page_roots as render_genres_page

from views.music.influence_map.influence_map import render_influence_map_page
from views.music.genealogy.genealogy_page_up_down import render_genealogy_page

# app.py — Music & Cinema with Tabs + Typography normalization


# ------------------------------------------------------------
# Page config (tem de ser o primeiro comando Streamlit)
# ------------------------------------------------------------
st.set_page_config(
    page_title="Multimedia4all",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ------------------------------------------------------------
# CSS — tipografia consistente e estilo das tabs (dark mode)
# ------------------------------------------------------------
ACCENT = "#22d3ee"   # cor da tab ativa
TEXT   = "#cbd5e1"   # texto normal
ACTIVE_BG = "rgba(34, 211, 238, 0.10)"  # fundo suave para a aba ativa

st.markdown(f"""
<style>
:root {{
  --brand: 28px;   /* Branding do topo */
  --h1: 24px;      /* Títulos de página (st.title) */
  --h2: 20px;      /* Subtítulos (st.header/subheader) */
  --h3: 16px;      /* Headings menores */
  --text: {TEXT};
}}

html, body, [data-testid="block-container"] {{
  color: var(--text);
}}

/* Branding de topo */
.app-brand {{
  font-size: var(--brand);
  font-weight: 700;
  line-height: 1.2;
  margin: 0 0 .5rem 0;
}}

/* Normaliza headings do Streamlit */
h1 {{ font-size: var(--h1) !important; line-height: 1.25; }}
h2 {{ font-size: var(--h2) !important; line-height: 1.3;  }}
h3 {{ font-size: var(--h3) !important; line-height: 1.3;  }}

/* Tabs */
.stTabs [role="tablist"] {{
  border-bottom: 1px solid rgba(255,255,255,.08);
  gap: .25rem;
}}
.stTabs [role="tab"] {{
  font-size: 1.05rem;                /* ↑ aumenta letra das labels */
  color: {TEXT};                     /* cor inativas */
  padding: 0.5rem 0.75rem;
  background: transparent;
  border: 1px solid rgba(148,163,184,.25);
  border-bottom: none;
  border-top-left-radius: .75rem;
  border-top-right-radius: .75rem;
}}
.stTabs [role="tab"][aria-selected="true"] {{
  color: {ACCENT};                   /* cor da label ativa */
  background: {ACTIVE_BG};           /* realce opcional */
  border-color: {ACCENT};
  font-weight: 600;
}}
.stTabs [role="tab"]:focus {{
  outline: none;
  box-shadow: 0 0 0 2px rgba(34,211,238,.35) inset;
}}

@media (max-width: 640px) {{
  .stTabs [role="tab"] {{
    font-size: 1rem;
    padding: 0.4rem 0.6rem;
  }}
}}
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------
# Branding
# ------------------------------------------------------------
MUSIC_ICON = "🎵\ufe0e"   # VS-15 → força estilo de texto (monocromático)
CINEMA_ICON = "🎬\ufe0e"
RADIO_ICON = "📻\ufe0e"  # text style (mono) como fizeste nos outros
PODCASTS_ICON  = "🎙\ufe0e"
st.markdown(f"<div class='app-brand'>{MUSIC_ICON} {CINEMA_ICON} Multimedia4all</div>",
            unsafe_allow_html=True)

# ------------------------------------------------------------
# Toggles globais
# ------------------------------------------------------------
c1, c2 = st.columns([1, 1])
with c1:
    st.toggle("📱 Mobile layout", key="ui_mobile")
with c2:
    st.toggle("🔊 Audio previews", key="ui_audio_preview")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# Spotify token (usado nas páginas de música)
# ------------------------------------------------------------
#
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
TOKEN = get_spotify_token(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)

# ------------------------------------------------------------
# Imports das páginas
# ------------------------------------------------------------
# Music
from views.music.spotify.page import render_spotify_page
from views.music.playlists.playlists_page import render_playlists_page
from views.radio.radio import render_radio_page

from views.music.wiki.wiki_page import render_wikipedia_page
from views.podcasts.podcasts import render_podcasts_page

# Cinema — resolve diferença de nomes/assinaturas
def _resolve_cinema_runner():
    try:
        # módulo certo da UI
        mod = importlib.import_module("views.cinema.page")

        # tenta primeiro o nome novo; senão, o legacy
        _cin = getattr(mod, "render_cinema_page", None) or getattr(mod, "render_page", None)
        if _cin is None:
            raise AttributeError("Nem 'render_cinema_page' nem 'render_page' existem em views.cinema.page")

        def run(section: str = "Movies"):
            try:
                # preferimos com argumento nomeado
                return _cin(section=section)
            except TypeError:
                # se a assinatura não aceitar 'section', chama sem args
                return _cin()

        return run

    except Exception as e:
        # MOSTRA o erro real — muito mais útil para debugging
        def run(section: str = "Movies", _e=e):
            st.error(f"Cinema page not available: {_e.__class__.__name__}: {_e}")
            # se quiseres o traceback completo:
            # st.exception(_e)
        return run

render_cinema = _resolve_cinema_runner()

# ------------------------------------------------------------
# Abas principais (substitui o 1º radio)
# ------------------------------------------------------------
#tab_music, tab_cinema = st.tabs([f"{MUSIC_ICON} Music", f"{CINEMA_ICON} Cinema"])
tab_music, tab_cinema, tab_radio, tab_podcasts = st.tabs([
    f"{MUSIC_ICON} Music",
    f"{CINEMA_ICON} Cinema",
    f"{RADIO_ICON} Radio",
    f"{PODCASTS_ICON} Podcasts",
])

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# =========================
# Aba: Music
# =========================
with tab_music:
    music_labels = [
        "🎧 Spotify",
        "🎼 Playlists",
        #"📻 Radio",
        "🧭 Genres",
        "📚 Wikipedia",
        # "🧬 Genealogy",
        # "🗺️ Influence map",
    ]
    music_choice = st.radio(
        label="music_submenu",
        options=music_labels,
        horizontal=True,
        key="ui_music_submenu",
        label_visibility="collapsed",
    )
    selected = music_choice.split(" ", 1)[1] if " " in music_choice else music_choice

    st.markdown("---")
    if selected == "Spotify":
        render_spotify_page(TOKEN, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
    elif selected == "Playlists":
        render_playlists_page()    
    elif selected == "Genres":
        render_genres_page()
    elif selected == "Wikipedia":
        render_wikipedia_page(TOKEN)
# =========================
# Aba: Radio
# =========================

with tab_radio:
    render_radio_page()

# =========================
# Aba: Podcasts
# =========================
with tab_podcasts:
    if render_podcasts_page:
        render_podcasts_page()
    else:
        st.subheader("Podcasts")
        st.info("Página de Podcasts ainda não criada (views/podcasts/podcasts.py).")
# =========================
# Aba: Cinema
# =========================
with tab_cinema:
    #cinema_labels = ["🍿 Movies", "📺 Series", "🎼 Soundtracks", "👤 Artists"]
    cinema_labels = ["🍿 Movies", "📺 Series", "👤 Artists"]
    cinema_choice = st.radio(
        label="cinema_submenu",
        options=cinema_labels,
        horizontal=True,
        key="ui_cinema_submenu",
        label_visibility="collapsed",
    )
    section = cinema_choice.split(" ", 1)[1] if " " in cinema_choice else cinema_choice

    st.markdown("---")
    if section == "Artists":
        # Importa só quando necessário
        from cinema.artists.page import render_artists_page
        render_artists_page()
    else:
        render_cinema(section=section)






