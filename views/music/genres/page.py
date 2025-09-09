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
from html import escape
# (opcional) integração Spotify nos resultados de pesquisa por path
from services.music.spotify.lookup import (
    get_spotify_token_cached, spotify_genre_top_artists, spotify_genre_playlists
)
from .spotify_widgets import render_artist_list, render_playlist_list

def _orient_edges_lr(edges, level):
    """Garante que toda aresta tem level[source] <= level[target]."""
    out = []
    for a, b in edges:
        la = level.get(a, 0)
        lb = level.get(b, 0)
        # se veio invertida, troca
        if la > lb:
            a, b = b, a
        out.append((a, b))
    return out

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
    # Caminho atual
        if path:
            st.caption("Path:")
            st.write(" / ".join(path))

            # 1) Botão Back (sobe um nível)
            if st.button("⬅ Back one level", key=_key("back_btn", path)):
                st.session_state["genres_path"] = path[:-1]
                st.rerun()

        # 2) Picker de subgéneros (selectbox com scroll quando longo; radio quando curto)
        next_children = sorted(children_idx.get(tuple(path), []), key=str.lower)

        if next_children:
            st.caption("Subgenres")

            radio_key  = _key("branch_radio", path)
            select_key = _key("branch_select", path)

            if len(next_children) > 10:
                # Dropdown com scroll nativo
                sel = st.selectbox(
                    "Subgenres",
                    options=next_children,
                    index=None,                 # nada selecionado por omissão
                    key=select_key,
                    label_visibility="collapsed",
                    placeholder="Choose a subgenre…",
                )
            else:
                # Lista curta: radio
                sel = st.radio(
                    "Subgenres",
                    next_children,
                    index=None,                 # nada selecionado por omissão
                    key=radio_key,
                    label_visibility="collapsed",
                )

            # Avança quando o utilizador escolhe um subgénero
            if sel:
                child_path = path + [sel]
                child_url = leaf_url.get(tuple(child_path))
                if child_url:
                    st.caption(f"[Wikipedia]({child_url})")
                st.session_state["genres_path"] = child_path
                st.rerun()

        else:
            # Último nível: mostra leaves (se existirem)
            rows = (leaves_idx.get(tuple(path), []) or [])
            if rows:
                st.write("Leaves in this branch:")
                for txt, url, p in rows[:1000]:
                    if url:
                        st.markdown(f"[🔗]({url})  **{txt}**  \n`{' / '.join(p)}`")
                    else:
                        st.markdown(f"**{txt}**  \n`{' / '.join(p)}`")
            else:
                st.info("No leaves under this path.")
        # ---------------------- FIM ESQUERDA ----------------------
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
            #st.markdown(" • ".join(downstream) if downstream else "—")
            

            # 👉 CSS para scroll vertical (máx. 5 linhas) e fonte mais pequena
            st.markdown("""
            <style>
            .chips-scroll{
            max-height: calc(5 * 1.25em);   /* ~5 linhas com line-height 1.25 */
            overflow-y: auto;
            padding-right: .5rem;
            margin-top: .25rem;
            }
            .chips-scroll::-webkit-scrollbar{width:8px;height:8px}
            .chips-scroll::-webkit-scrollbar-thumb{background:rgba(255,255,255,.2);border-radius:6px}
            .chips-scroll span{
            font-size: 0.92rem;             /* ~-8% */
            line-height: 1.25;
            }
            </style>
            """, unsafe_allow_html=True)

            # 👉 prepara o texto (mantendo o “•”)
            deriv_labels = [lbl for lbl in sorted(downstream, key=str.lower) if lbl != root_genre]
            deriv_html = " • ".join(escape(x) for x in deriv_labels)

            # 👉 contêiner com scroll
            st.markdown(f'<div class="chips-scroll"><span>{deriv_html}</span></div>', unsafe_allow_html=True)

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
        # === Dados do gráfico (branch-only só quando excede o MAX) ===
        # === Dados do gráfico (branch-only só quando excede o MAX) ===
        #adj = build_label_adjacency(children_idx)

        MAX_FIRST_LEVEL = 20  # ajusta aqui (20 ou 30, etc.)
        root_first_children = sorted(children_idx.get((root_genre,), []), key=str.lower)
        direct_count = len(root_first_children)
        too_many = direct_count > MAX_FIRST_LEVEL

        # (debug opcional — remove depois)
        st.caption(f"mode: "
                f"{'await-branch' if (too_many and len(path)<=1) else ('branch-only' if (too_many and len(path)>1) else 'full')}"
                f" | direct={direct_count}/{MAX_FIRST_LEVEL} | path_len={len(path)}")

        # 2) Construção do grafo conforme a regra
        adj = build_label_adjacency(children_idx)

        if too_many and len(path) <= 1:
            # Excede o MAX mas ainda só tens o root → NÃO desenhar nada (espera seleção)
            st.info(f'“{root_genre}” has {direct_count} direct subgenres. '
                    'Pick a subgenre on the left to display just that branch.')
            st.stop()  # impede qualquer plot mais abaixo

        if too_many and len(path) > 1:
            # 🚦 EXCEDE o MAX e já há seleção → mostrar APENAS o ramo root → path[1] → …
            selected_first = path[1]
            depth_right = max(0, depth - 1)

            # Direita: ramo a partir do 1.º subgénero escolhido
            right_nodes, right_edges, right_level = bfs_down_labels(adj, selected_first, depth_right)

            # Esquerda: upstream do root (contexto)
            adj_up = build_reverse_adjacency(adj)
            nodes_up, edges_up, level_up = bfs_up_labels(adj_up, root_genre, depth)

            # Compõe grafo só com o ramo selecionado
            edges = edges_up + [(root_genre, selected_first)] + right_edges
            level = {
                **level_up,
                root_genre: 0,
                selected_first: 1,
                **{n: l + 1 for n, l in right_level.items()}  # desloca níveis do ramo para a direita
            }
            nodes = sorted(set([*nodes_up, root_genre, selected_first, *right_nodes]), key=str.lower)

            fig = branch_sankey(
                nodes, edges, level,
                root=root_genre, focus=path[-1],
                branch_only=True, is_mobile=False,
                height_override=gh, font_size_override=fs
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("Blue = highlighted path from root to the selected branch.")
        else:
            # ✅ Não excede o MAX → grafo completo
            nodes_ds, edges_ds, level_ds = bfs_down_labels(adj, root_genre, depth)
            adj_up = build_reverse_adjacency(adj)
            nodes_up, edges_up, level_up = bfs_up_labels(adj_up, root_genre, depth)

            nodes = sorted(set([*nodes_up, *nodes_ds]), key=str.lower)
            edges = edges_up + edges_ds
            level = {root_genre: 0, **level_up, **level_ds}

            fig = branch_sankey(
                nodes, edges, level,
                root=root_genre, focus=path[-1] if path else root_genre,
                branch_only=False, is_mobile=False,
                height_override=gh, font_size_override=fs
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            st.caption("Blue = highlighted path from root to the selected branch.")

        # alias de compatibilidade
        render_genres_page = render_genres_page_roots

