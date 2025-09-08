# views/genres/page.py
# UI em inglês; comentários em PT.

from __future__ import annotations

import streamlit as st

from services.page_help import show_page_help
from services.genre_csv import load_hierarchy_csv, make_key as _key

# módulos auxiliares da própria pasta
from .css import STYLE
from .state import PLACEHOLDER, CLEAR_FLAG, on_root_change
from .search import build_indices_cached, flatten_all_paths, search_paths
from .graph import (
    build_label_adjacency, build_reverse_adjacency,
    bfs_down_labels, bfs_up_labels, branch_sankey
)
from . import wiki as WIKI

# (opcional) integração Spotify nos resultados de pesquisa por path
from services.music.spotify.lookup import (
    get_spotify_token_cached, spotify_genre_top_artists, spotify_genre_playlists
)
from .spotify_widgets import render_artist_list, render_playlist_list



def _genre_blurb_and_source(name: str):
    """
    Mostra SEMPRE o resumo da Wikipédia (EN→PT) quando existir.
    Se não houver, cai para genre_summary/BLURBS. Devolve (markdown, fonte_url).
    """
    # 1) Wikipedia summary primeiro
    wiki_txt, wiki_url = WIKI.wiki_summary_any(name)
    if wiki_txt:
        lines = [ln.strip() for ln in wiki_txt.splitlines() if ln.strip()]
        return "\n\n".join(lines[:4]), wiki_url

    # 2) KB interna (opcional) e BLURBS
    txt = ""
    try:
        from services.genres_kb import genre_summary, BLURBS
    except Exception:
        genre_summary = None
        BLURBS = {}

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


def render_genres_page_roots():
    show_page_help("genres_roots", lang="EN")
    st.subheader("🧭 Genres")
    st.markdown(f"<style>{STYLE}</style>", unsafe_allow_html=True)

    # ---------- Dados ----------
    try:
        df, _ = load_hierarchy_csv()
    except Exception as e:
        st.error(str(e)); return
    children_idx, leaves_idx, roots, leaf_url = build_indices_cached(df)

    # ---------- Primeira linha: botões ----------
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("🔎 Search", key="genres_top_search"):
            q = (st.session_state.get("genres_search_q") or "").strip()
            if not q:
                st.warning("Type something to search.")
            else:
                all_paths, _ = flatten_all_paths(df)
                hits = search_paths(all_paths, q, max_results=300)
                st.session_state["genres_search_results"] = {"query": q, "hits": hits}
                st.session_state["genres_search_page"] = 1
    with b2:
        if st.button("🧹 Reset filters", key="genres_top_reset"):
            st.session_state.pop("genres_search_q", None)
            st.session_state.pop("genres_search_results", None)
            st.session_state.pop("genres_search_page", None)
            st.session_state["genres_path"] = []
            # limpa restos spotify
            for k in list(st.session_state.keys()):
                if k.endswith(("_artists", "_playlists")) or k.startswith(("sr_spotify", "list_spotify")):
                    st.session_state.pop(k, None)

    # ---------- Segunda linha: select root + search ----------
    root_list = sorted([r for r in (roots or set()) if r], key=str.lower)
    if "genres_path" not in st.session_state:
        st.session_state["genres_path"] = []
    path = st.session_state["genres_path"]
    current_root = (path[0] if path else None)

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

    # ---------- Estado ----------
    path = st.session_state["genres_path"]
    prefix = tuple(path)

    # ---------- Fluxo: resultados de pesquisa ----------
    found = st.session_state.get("genres_search_results")
    if found:
        q = found["query"]; hits = found["hits"]
        st.markdown(f"**Results for**: `{q}`  \nTotal: **{len(hits)}**")
        page_size = 15
        page = int(st.session_state.get("genres_search_page", 1))
        total_pages = max((len(hits)+page_size-1)//page_size, 1)

        with st.container(border=True):
            top, _p, _n = st.columns([6,2,2])
            with _p:
                if st.button("◀ Prev", key="genres_search_prev") and page > 1:
                    st.session_state["genres_search_page"] = page - 1
            with _n:
                if st.button("Next ▶", key="genres_search_next") and page < total_pages:
                    st.session_state["genres_search_page"] = page + 1
            st.caption(f"Page {page}/{total_pages}")

            start = (page-1)*page_size
            chunk = hits[start:start+page_size]

            for idx, p in enumerate(chunk):
                row = st.columns([1, 6, 1])  # wiki | path | Go
                with row[0]:
                    url = leaf_url.get(tuple(p))
                    if url: st.markdown(f"[🔗]({url})", help="Wikipedia")
                    else:   st.write("")
                with row[1]:
                    st.markdown(f"`{' / '.join(p)}`")
                with row[2]:
                    go_key = _key("sr_spotify_go", p, idx=idx)
                    if st.button("Go", key=go_key, help="Search in Spotify"):
                        token = get_spotify_token_cached()
                        try:
                            leaf = p[-1] if p else ""
                            from services.genre_csv import build_context_keywords
                            ctx = build_context_keywords(list(p), leaf)
                            artists = spotify_genre_top_artists(token, ctx[0], ctx, limit=10)
                            playlists = spotify_genre_playlists(token, ctx[0], ctx, limit=10) if not artists else []
                            base = _key("sr_spotify", p, idx=idx)
                            st.session_state[f"{base}_artists"] = artists
                            st.session_state[f"{base}_playlists"] = playlists
                        except Exception:
                            base = _key("sr_spotify", p, idx=idx)
                            st.session_state[f"{base}_artists"] = []
                            st.session_state[f"{base}_playlists"] = []
                base = _key("sr_spotify", p, idx=idx)
                artists   = st.session_state.get(f"{base}_artists")
                playlists = st.session_state.get(f"{base}_playlists")
                if artists is not None or playlists is not None:
                    if artists:
                        st.markdown("**Artists**"); render_artist_list(artists, play_prefix=f"{base}_art")
                    elif playlists:
                        st.markdown("**Playlists**"); render_playlist_list(playlists, play_prefix=f"{base}_pl")
                    else:
                        st.caption("no data")
        st.divider(); return

    # ---------- Navegação normal ----------
    st.markdown("### Current branch")
    st.write("Select a branch to drill down:")

    st.markdown('<div class="breadcrumbs">', unsafe_allow_html=True)
    bc_cols = st.columns(max(len(path), 1) + 1)
    with bc_cols[0]:
        if st.button("🏠 Home", key=_key("home", []), use_container_width=True):
            st.session_state["genres_path"] = []
    for i, label in enumerate(path, start=1):
        with bc_cols[i]:
            is_last = (i == len(path))
            if is_last:
                st.button(label, key=_key("bc_active", path[:i]), disabled=True, use_container_width=True)
            else:
                if st.button(f"{label} ⤴", key=_key("bc", path[:i]), use_container_width=True):
                    st.session_state["genres_path"] = path[:i]
    st.markdown('</div>', unsafe_allow_html=True)

    if len(path) == 0:
        st.info("Choose a root genre above to see its subgenres and the graph.")
        return

    # ---------- Duas colunas ----------
    colL, colR = st.columns([5, 7])

    # ---------------------- ESQUERDA: subgéneros / folhas ----------------------
    with colL:
        # filhos diretos deste nó
        next_children = sorted(x for x in children_idx.get(prefix, set()) if x)

        st.markdown('<div class="branches">', unsafe_allow_html=True)

        if next_children:
            # ✅ apenas quando há filhos mostramos o link do nó atual
            cur_url = leaf_url.get(prefix)
            if cur_url:
                st.markdown(f"**This node has a Wikipedia page:** [🔗]({cur_url})")

            # --- ALTERNATIVA RADIO: super compacto ---
            radio_key = _key("branch_radio", path)
            sel = st.radio(
                "Subgenres",
                next_children,
                index=None,  # nada selecionado por omissão
                key=radio_key,
                label_visibility="collapsed",
            )

            # mostra dinamicamente link para o subgénero selecionado
            if sel:
                child_path = path + [sel]
                child_url = leaf_url.get(tuple(child_path))
                if child_url:
                    st.caption(f"[Wikipedia]({child_url})")

                # navega imediatamente
                st.session_state["genres_path"] = child_path
                st.rerun()

        else:
            # ✅ último nível: só mostra leaves (sem duplicar links)
            rows = (leaves_idx.get(prefix, []) or [])
            if rows:
                st.write("Leaves in this branch:")
                for idx, (txt, url, p) in enumerate(rows[:1000]):
                    if url:
                        st.markdown(f"[🔗]({url})  **{txt}**  \n`{' / '.join(p)}`")
                    else:
                        st.markdown(f"**{txt}**  \n`{' / '.join(p)}`")
            else:
                st.info("No leaves under this node.")

        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------------- DIREITA: resumo + relations + gráfico ----------------------
    with colR:
        root_genre = path[0]     # selecionado na selectbox
        focus      = path[-1]    # último nó clicado

        st.markdown(f"### {root_genre}")

        # Refresh dos caches (summary/infobox)
        rc1, rc2 = st.columns([1, 1])
        with rc1:
            if st.button("↻ Refresh summary", key="refresh_wiki_summary"):
                try:
                    WIKI.wiki_fetch_summary.clear()
                except Exception:
                    pass
        with rc2:
            if st.button("↻ Refresh facts", key="refresh_wiki_facts"):
                try:
                    WIKI.wiki_infobox_any.clear()
                except Exception:
                    pass

        # Resumo + fonte
        blurb_md, blurb_src = _genre_blurb_and_source(root_genre)
        st.markdown(blurb_md)
        if blurb_src:
            st.caption(f"Source: [Wikipedia]({blurb_src})")

        # Infobox facts (se existirem)
        facts, facts_url = WIKI.wiki_infobox_any(root_genre)
        if facts:
            st.markdown("#### Key facts")
            for k in ("Stylistic origins", "Cultural origins", "Typical instruments"):
                if k in facts:
                    st.markdown(f"**{k}:** {facts[k]}")
            if facts_url:
                st.caption(f"Source: [Wikipedia infobox]({facts_url})")

        # Relations para o género selecionado (focus)
        st.markdown(f"#### Relations for **{focus}**")

        # Influences = tudo o que vem antes no path
        upstream = path[:-1]
        colInf, colDer = st.columns([1, 1])

        with colInf:
            st.markdown(f"**Influences ({len(upstream)} upstream)**")
            st.markdown(" • ".join(upstream) if upstream else "—")

        # Derivatives = descendentes do focus
        adj_for_rel = build_label_adjacency(children_idx)
        nodes_f, edges_f, level_f = bfs_down_labels(adj_for_rel, focus, depth=6)
        downstream = sorted({n for n in nodes_f if level_f.get(n, 0) > 0}, key=str.lower)

        with colDer:
            st.markdown(f"**Derivatives ({len(downstream)} downstream)**")
            st.markdown(" • ".join(downstream) if downstream else "—")

        # Controlo: profundidade e opções do gráfico lado a lado
        ctrlL, ctrlR = st.columns([3, 2])
        with ctrlL:
            depth = st.slider("Map depth (levels down)", 1, 4, 2, key="gen_depth")

        with ctrlR:
            preset = st.selectbox(
                "Chart options",
                ["Default", "Compact", "Large labels", "Tall chart", "Custom"],
                index=0,
                key="chart_opts",
            )
            gh, fs = 680, 15
            if preset == "Compact":
                gh, fs = 420, 13
            elif preset == "Large labels":
                gh, fs = 560, 18
            elif preset == "Tall chart":
                gh, fs = 760, 15
            elif preset == "Custom":
                gh = st.slider("Height (px)", 300, 900, 520, 20, key="g_height")
                fs = st.slider("Label size", 10, 22, 15, 1, key="g_font")

        min_depth = max(1, len(path) - 1)
        depth = max(depth, min_depth)
        # Dados do gráfico
        adj = build_label_adjacency(children_idx)

        # --- helpers para normalizar rótulos e obter filhos diretos de forma robusta ---
        def _norm_label(s: str) -> str:
            if s is None:
                return ""
            return (str(s)
                    .replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
                    .replace("–", "-").replace("—", "-").replace("\xa0", " ")
                    .strip().casefold())

        def get_direct_children_adj(adj_map: dict, label: str):
            # tenta chave exata
            kids = adj_map.get(label, set())
            if not kids:
                # fallback: procura chave equivalente (case/hífen/nbsp)
                norm = _norm_label(label)
                for k in adj_map.keys():
                    if _norm_label(k) == norm:
                        kids = adj_map.get(k, set())
                        break
            # garante lista e dedup por normalização
            kids_list = sorted(list(kids), key=str.lower)
            uniq_norm = { _norm_label(k) for k in kids_list }
            return kids_list, len(uniq_norm)

        MAX_FIRST_LEVEL = 20
        direct_children, direct_count = get_direct_children_adj(adj, root_genre)
        too_many = direct_count > MAX_FIRST_LEVEL

        if too_many and len(path) <= 1:
            st.info(
                f"“{root_genre}” has {direct_count} direct subgenres. "
                "Pick a subgenre on the left to display just that branch."
            )
        else:
            # --- exatamente como já tinhas ---
            nodes_ds, edges_ds, level_ds = bfs_down_labels(adj, root_genre, depth)
            adj_up = build_reverse_adjacency(adj)
            nodes_up, edges_up, level_up = bfs_up_labels(adj_up, root_genre, depth)

            nodes = sorted(set([*nodes_up, *nodes_ds]), key=str.lower)
            edges = edges_up + edges_ds
            level = {root_genre: 0, **level_up, **level_ds}

            # quando há muitos ramos diretos, renderiza só o ramo escolhido
            branch_only = (too_many and len(path) > 1)
            if branch_only and len(path) > 1:
                selected_first = path[1]
                right_nodes, right_edges, right_level = bfs_down_labels(adj, selected_first, max(0, depth - 1))
                edges = edges_up + [(root_genre, selected_first)] + right_edges
                level = {
                    **level_up,
                    root_genre: 0,
                    selected_first: 1,
                    **{n: l + 1 for n, l in right_level.items()}
                }
                nodes = sorted(set([*nodes_up, root_genre, selected_first, *right_nodes]), key=str.lower)

            if not nodes or not edges:
                st.info("No links for this depth.")
            else:
                fig = branch_sankey(
                    nodes, edges, level,
                    root=root_genre, focus=focus,
                    branch_only=branch_only, is_mobile=False,
                    height_override=gh, font_size_override=fs
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
                st.caption("Blue = highlighted path from root to the selected branch.")


# alias de compatibilidade
render_genres_page = render_genres_page_roots

