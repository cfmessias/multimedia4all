# views/music/genre.py  (ajusta o path conforme o teu projeto)
# Página de géneros: UI em EN, comentários em PT.

from __future__ import annotations

import streamlit as st

# helpers do teu projeto (ajusta caminhos se necessário)
from services.page_help import show_page_help
from services.genre_csv import load_hierarchy_csv, make_key as _key

from .css import STYLE
from .state import PLACEHOLDER, CLEAR_FLAG, on_root_change
from .search import build_indices_cached, search_paths
from .graph import (
    build_label_adjacency, build_reverse_adjacency,
    bfs_down_labels, bfs_up_labels, branch_sankey
)
from . import wiki as WIKI

# (opcional) Spotify – é seguro falhar
try:
    from services.music.spotify.lookup import (
        get_spotify_token_cached, spotify_genre_top_artists, spotify_genre_playlists
    )
    from .spotify_widgets import render_artist_list, render_playlist_list
except Exception:  # pragma: no cover
    get_spotify_token_cached = None
    spotify_genre_top_artists = spotify_genre_playlists = None
    render_artist_list = render_playlist_list = None


# ---------- Helpers locais ----------

def _genre_blurb_and_source(name: str):
    """Prefere resumo da Wikipedia; senão cai para summaries/BLURBS se existir."""
    wiki_txt, wiki_url = WIKI.wiki_summary_any(name)
    if wiki_txt:
        lines = [ln.strip() for ln in wiki_txt.splitlines() if ln.strip()]
        return "\n\n".join(lines[:4]), wiki_url

    # fallback leve (não falha se o módulo não existir)
    try:
        from .summaries import genre_summary, BLURBS  # type: ignore
    except Exception:
        genre_summary = None
        BLURBS = {}

    txt = ""
    if callable(genre_summary):
        try:
            txt = (genre_summary(name) or "").strip()
        except Exception:
            txt = ""
    if not txt and isinstance(BLURBS, dict):
        b = BLURBS.get(name, {})
        if b:
            period  = b.get("period") or "—"
            regions = ", ".join(b.get("regions", []) or []) or "—"
            chars   = ", ".join(b.get("characteristics", []) or []) or "—"
            txt = f"**Period:** {period}\n\n**Key areas:** {regions}\n\n**Typical traits:** {chars}"
    if not txt:
        txt = "**Period:** —\n\n**Key areas:** —\n\n**Typical traits:** —"
    lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
    return "\n\n".join(lines[:4]), ""


def _fill_levels(nodes, edges, level):
    """
    Propaga níveis em falta: se (u→v) e lvl(u) existe, lvl(v)=lvl(u)+1; e vice-versa.
    Repete até estabilizar; preenche faltantes com 0 no fim (defensivo).
    """
    lev = dict(level)
    for _ in range(len(nodes) + 2):
        changed = False
        for a, b in edges:
            la = lev.get(a)
            lb = lev.get(b)
            if la is not None and lb is None:
                lev[b] = la + 1; changed = True
            elif lb is not None and la is None:
                lev[a] = lb - 1; changed = True
        if not changed:
            break
    for n in nodes:
        if n not in lev:
            lev[n] = 0
    return lev


def _orient_lr(edges, level):
    """Garante que toda aresta aponta do nível menor para o maior (esquerda→direita)."""
    out = []
    for a, b in edges:
        la = level.get(a, 0)
        lb = level.get(b, 0)
        out.append((a, b) if la <= lb else (b, a))
    return out


# ---------- Página ----------

def render_genres_page_roots():
    show_page_help("genres_roots", lang="EN")
    st.subheader("🧭 Genres")
    st.markdown(f"<style>{STYLE}</style>", unsafe_allow_html=True)

    # CSS local (seguro)
    st.markdown("""
    <style>
    [data-baseweb="select"] div, [role="radiogroup"] label { font-size: 0.95rem; line-height: 1.25; }
    .chips-scroll{ max-height: calc(5 * 1.25em); overflow-y:auto; padding-right:.5rem; margin-top:.25rem; }
    .chips-scroll::-webkit-scrollbar{width:8px;height:8px}
    .chips-scroll::-webkit-scrollbar-thumb{background:rgba(255,255,255,.2);border-radius:6px}
    .chips-scroll span{ font-size:.92rem; line-height:1.25; }
    </style>
    """, unsafe_allow_html=True)

    # ---------- Dados ----------
    try:
        df, _ = load_hierarchy_csv()
    except Exception as e:
        st.error(str(e)); return
    children_idx, leaves_idx, roots, leaf_url = build_indices_cached(df)

    # ---------- Top bar ----------
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("🔎 Search", key="genres_top_search"):
            q = (st.session_state.get("genres_search_q") or "").strip()
            if q:
                hits = search_paths(df, q)
                st.session_state["genres_search_results"] = {"query": q, "hits": hits}
                st.session_state["genres_search_page"] = 1
            else:
                st.warning("Type something to search paths (e.g., Rock / Art Rock / Math Rock).")
    with b2:
        if st.button("🧹 Reset filters", key="genres_top_reset"):
            for k in ("genres_search_q","genres_search_results","genres_search_page"):
                st.session_state.pop(k, None)
            st.session_state["genres_path"] = []
            for k in list(st.session_state.keys()):
                if k.endswith(("_artists","_playlists")) or k.startswith(("sr_spotify","list_spotify")):
                    st.session_state.pop(k, None)

    # ---------- Root + Search ----------
    root_list = sorted([r for r in (roots or set()) if r], key=str.lower)
    if "genres_path" not in st.session_state:
        st.session_state["genres_path"] = []
    path = st.session_state["genres_path"]
    current_root = path[0] if path else None

    options = [PLACEHOLDER] + root_list
    default_index = options.index(current_root) if current_root in options else 0

    c_root, c_search = st.columns([4, 8])
    with c_root:
        st.selectbox("Root genre", options=options, index=default_index, key="root_select",
                     label_visibility="collapsed", placeholder=PLACEHOLDER, on_change=on_root_change)
    if st.session_state.pop(CLEAR_FLAG, False):
        st.session_state["genres_search_q"] = ""
    with c_search:
        st.text_input("Search", key="genres_search_q", label_visibility="collapsed",
                      placeholder="Search genre/path (e.g., Art Rock or Rock / Progressive)")

    st.divider()

    # ---------- Fluxo: resultados de pesquisa ----------
    found = st.session_state.get("genres_search_results")
    if found:
        q = found["query"]; hits = found["hits"]
        st.markdown(f"**Results for**: `{q}`  \nTotal: **{len(hits)}**")

        page_size = 15
        page = int(st.session_state.get("genres_search_page", 1))
        total_pages = max((len(hits)+page_size-1)//page_size, 1)

        pgL, pgR = st.columns([1, 1])
        with pgL:
            if st.button("← Prev", disabled=(page <= 1)):
                st.session_state["genres_search_page"] = max(1, page-1); st.rerun()
        with pgR:
            if st.button("Next →", disabled=(page >= total_pages)):
                st.session_state["genres_search_page"] = min(total_pages, page+1); st.rerun()

        start = (page-1)*page_size
        for row in hits[start:start+page_size]:
            p = row["path"]; name = p[-1]
            blurb, src = _genre_blurb_and_source(name)
            st.markdown(f"### {' / '.join(p)}")
            st.markdown(blurb)
            if src: st.caption(f"[Wikipedia]({src})")
        st.caption(f"Page **{page} / {total_pages}**")
        return

    # ---------- Fluxo: árvore ----------
    path = st.session_state["genres_path"]
    if not path:
        st.info("Pick a **root genre** in the select box above, or use **Search**.")
        return

    root_genre = path[0]
    blurb, src = _genre_blurb_and_source(root_genre)
    st.markdown(f"### {root_genre}")
    st.markdown(blurb)
    if src: st.caption(f"Source: [Wikipedia]({src})")

    colL, colRight = st.columns([3, 7])

    # ------ Navegação (esquerda) ------
    with colL:
        st.caption("Path:")
        st.write(" / ".join(path))

        if len(path) > 0 and st.button("⬅ Back one level", key=_key("back_btn", path)):
            st.session_state["genres_path"] = path[:-1]
            st.rerun()

        next_children = sorted(children_idx.get(tuple(path), []), key=str.lower)
        if next_children:
            st.caption("Subgenres")
            radio_key  = _key("branch_radio", path)
            select_key = _key("branch_select", path)
            if len(next_children) > 10:
                sel = st.selectbox("Subgenres", next_children, index=None, key=select_key,
                                   label_visibility="collapsed", placeholder="Choose a subgenre…")
            else:
                sel = st.radio("Subgenres", next_children, index=None, key=radio_key,
                               label_visibility="collapsed")
            if sel:
                child_path = path + [sel]
                if (u := leaf_url.get(tuple(child_path))): st.caption(f"[Wikipedia]({u})")
                st.session_state["genres_path"] = child_path
                st.rerun()
        else:
            rows = (leaves_idx.get(tuple(path), []) or [])
            if rows:
                st.write("Leaves in this branch:")
                for txt, url, p in rows[:1000]:
                    st.markdown(f"[🔗]({url})  **{txt}**  \n`{' / '.join(p)}`" if url
                                else f"**{txt}**  \n`{' / '.join(p)}`")
            else:
                st.info("No leaves under this path.")

    # ------ Info + gráfico (direita) ------
    with colRight:
        focus = path[-1] if path else root_genre

        facts = st.columns([1, 1])
        with facts[0]:
            adj_rel = build_label_adjacency(children_idx)
            nodes_u, edges_u, level_u = bfs_up_labels(build_reverse_adjacency(adj_rel), focus, depth=6)
            upstream = sorted({n for n in nodes_u if level_u.get(n, 0) < 0}, key=str.lower)
            st.markdown(f"**Influences ({len(upstream)} upstream)**")
            st.markdown(" • ".join(upstream) if upstream else "—")
        with facts[1]:
            adj_rel = build_label_adjacency(children_idx)
            nodes_d, edges_d, level_d = bfs_down_labels(adj_rel, focus, depth=6)
            downstream = sorted({n for n in nodes_d if level_d.get(n, 0) > 0}, key=str.lower)
            from html import escape
            st.markdown(f"**Derivatives ({len(downstream)} downstream)**")
            st.markdown(
                f'<div class="chips-scroll"><span>{" • ".join(escape(x) for x in downstream)}</span></div>',
                unsafe_allow_html=True
            ) if downstream else st.markdown("—")

        # Controlo
        ctrlL, ctrlR = st.columns([3, 2])
        with ctrlL:
            depth = st.slider("Map depth (levels down)", 1, 4, 2, key="gen_depth")
        with ctrlR:
            preset = st.selectbox("Chart options",
                                  ["Default","Compact","Large labels","Tall chart","Custom"],
                                  index=0, key="chart_opts")
            gh, fs = 680, 15
            if preset == "Compact": gh, fs = 420, 13
            elif preset == "Large labels": gh, fs = 560, 18
            elif preset == "Tall chart": gh, fs = 760, 15
            elif preset == "Custom":
                gh = st.slider("Height (px)", 300, 900, 520, 20, key="g_height")
                fs = st.slider("Label size", 10, 22, 15, 1, key="g_font")

        depth = max(depth, max(1, len(path) - 1))  # respeita o caminho já escolhido

        # === Dados do gráfico ===
        adj = build_label_adjacency(children_idx)
        MAX_FIRST_LEVEL = 30  # ajusta aqui

        # filhos diretos do root (mesma fonte do picker)
        root_first_children = children_idx.get((root_genre,), [])
        direct_count = len(root_first_children)
        too_many = direct_count > MAX_FIRST_LEVEL

        # normalizador e mapeamento nó real ←→ rótulo
        def _norm(s: str) -> str:
            return (str(s).replace("\u2011","-").replace("\u2013","-").replace("\u2014","-")
                    .replace("–","-").replace("—","-").replace("\xa0"," ").strip().casefold())

        if too_many and len(path) <= 1:
            st.info(f"“{root_genre}” has {direct_count} direct subgenres. "
                    "Pick a subgenre on the left to display just that branch.")
            st.stop()

        # função para aplicar níveis do breadcrumb nos nós reais (robusto a variações)
        def _force_path_levels(nodes, level, path):
            by_norm = {}
            for n in nodes:
                nn = _norm(n)
                # mantém a primeira ocorrência (estável)
                if nn not in by_norm:
                    by_norm[nn] = n
            for i, lbl in enumerate(path):
                m = by_norm.get(_norm(lbl))
                if m:
                    level[m] = i
            return level

        if too_many and len(path) > 1:
            # --- BRANCH-ONLY ---
            selected_first = path[1]
            depth_right = max(0, depth - 1)

            right_nodes, right_edges, right_level = bfs_down_labels(adj, selected_first, depth_right)
            adj_up = build_reverse_adjacency(adj)
            nodes_up, edges_up, level_up = bfs_up_labels(adj_up, root_genre, depth)

            nodes = sorted(set([*nodes_up, root_genre, selected_first, *right_nodes]), key=str.lower)
            edges = edges_up + [(root_genre, selected_first)] + right_edges
            level = {**level_up, root_genre: 0, selected_first: 1,
                     **{n: l + 1 for n, l in right_level.items()}}

            # 🔑 força níveis do breadcrumb em nós REAIS + completa + orienta
            level = _force_path_levels(nodes, level, path)
            level = _fill_levels(nodes, edges, level)
            edges = _orient_lr(edges, level)
            st.write({n: level.get(n) for n in path})  # deve dar {root:0, filho:1, focus:2}
            fig = branch_sankey(
                nodes, edges, level,
                root=root_genre, focus=path[-1],
                branch_only=True, is_mobile=False,
                height_override=gh, font_size_override=fs,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("Blue = highlighted path from root to the selected branch.")
        else:
            # --- FULL ---
            nodes_ds, edges_ds, level_ds = bfs_down_labels(adj, root_genre, depth)
            adj_up = build_reverse_adjacency(adj)
            nodes_up, edges_up, level_up = bfs_up_labels(adj_up, root_genre, depth)

            nodes = sorted(set([*nodes_up, *nodes_ds]), key=str.lower)
            edges = edges_up + edges_ds
            level = {root_genre: 0, **level_up, **level_ds}

            # 🔑 força níveis do breadcrumb em nós REAIS + completa + orienta
            level = _force_path_levels(nodes, level, path)
            level = _fill_levels(nodes, edges, level)
            edges = _orient_lr(edges, level)

            st.write({n: level.get(n) for n in path})  # deve dar {root:0, filho:1, focus:2}
            fig = branch_sankey(
                nodes, edges, level,
                root=root_genre, focus=path[-1] if path else root_genre,
                branch_only=False, is_mobile=False,
                height_override=gh, font_size_override=fs,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("Blue = highlighted path from root to the selected branch.")
