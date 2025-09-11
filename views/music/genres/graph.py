# views/genres/graph.py
# BFS + Sankey
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict, deque
import numpy as np
from typing import List, Tuple, Dict, Set
import numpy as np  
from collections import defaultdict as _dd, deque as _deq

Edge = Tuple[str, str]

def _norm(s: str) -> str:
    if s is None:
        return ""
    # normaliza hífens/dashes e NBSP para garantir matching de labels
    return (str(s)
            .replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
            .replace("–", "-").replace("—", "-")
            .replace("\xa0", " ")
            .strip()
            .casefold())

def _path_root_to_focus(root: str, focus: str, edges: List[Edge], level: Dict[str, int]) -> List[Edge]:
    """
    Reconstrói um caminho root→focus respeitando os níveis visíveis em 'level'.
    Faz matching por labels normalizados, mas devolve as arestas ORIGINAIS.
    """
    if not root or not focus:
        return []

    # mapa normalizado -> original
    nodes_orig = {n for e in edges for n in e} | set(level.keys())
    canon_by_norm: Dict[str, str] = {}
    for n in nodes_orig:
        canon_by_norm.setdefault(_norm(n), n)

    root_c = canon_by_norm.get(_norm(root))
    focus_c = canon_by_norm.get(_norm(focus))
    if root_c is None or focus_c is None:
        return []

    # pais por filho apenas entre níveis contíguos (o que está desenhado)
    parents_by_child: Dict[str, list] = {}
    edge_norm_to_orig: Dict[Tuple[str, str], Edge] = {}

    lvl = {_norm(k): v for k, v in level.items()}
    for u, v in edges:
        nu, nv = _norm(u), _norm(v)
        if nu in lvl and nv in lvl and lvl.get(nu) + 1 == lvl.get(nv):
            parents_by_child.setdefault(nv, []).append(nu)
            edge_norm_to_orig[(nu, nv)] = (u, v)

    # sobe do focus até ao root
    path_rev: list[Tuple[str, str]] = []
    cur = _norm(focus_c)
    target_root = _norm(root_c)
    seen: Set[str] = set()
    while cur != target_root and cur not in seen:
        seen.add(cur)
        parents = sorted(parents_by_child.get(cur, []), key=str.lower)
        if not parents:
            break
        p = parents[0]            # determinístico
        path_rev.append((p, cur))
        cur = p

    if cur != target_root:
        return []

    # devolve arestas originais presentes em 'edges'
    path_orig: List[Edge] = []
    for nu, nv in reversed(path_rev):
        e = edge_norm_to_orig.get((nu, nv))
        if e:
            path_orig.append(e)
    return path_orig

# canonical_name opcional (fallback seguro)
try:
    from services.genres_kb import canonical_name
except Exception:
    def canonical_name(x: str) -> str: return (x or "").strip()

def build_label_adjacency(children_index):
    adj = defaultdict(set)
    for pref, kids in children_index.items():
        if not pref: continue
        parent = canonical_name(pref[-1])
        for k in kids:
            if k: adj[parent].add(canonical_name(k))
    return adj

def build_reverse_adjacency(adj):
    rev = defaultdict(set)
    for parent, childs in adj.items():
        for c in childs:
            if c: rev[canonical_name(c)].add(canonical_name(parent))
    return rev

def bfs_down_labels(adj, root: str, depth: int):
    root = canonical_name(root)
    nodes = {root}; edges = []; level = {root: 0}; q = deque([root])
    while q:
        u = q.popleft()
        if level[u] >= depth: continue
        for v in sorted(adj.get(u, set()), key=str.lower):
            v = canonical_name(v); edges.append((u, v))
            if v not in nodes:
                nodes.add(v); level[v] = level[u] + 1; q.append(v)
    ordered = sorted(nodes, key=lambda n: (level[n], n.lower()))
    return ordered, edges, level

def bfs_up_labels(adj_up, root: str, depth: int):
    root = canonical_name(root)
    nodes = {root}; edges = []; level = {root: 0}; q = deque([root])
    while q:
        u = q.popleft()
        if abs(level[u]) >= depth: continue
        for p in sorted(adj_up.get(u, set()), key=str.lower):
            p = canonical_name(p); edges.append((p, u))
            if p not in nodes:
                nodes.add(p); level[p] = level[u] - 1; q.append(p)
    ordered = sorted(nodes, key=lambda n: (level[n], n.lower()))
    return ordered, edges, level

def _path_edges(edges, start: str, target: str):
    g = defaultdict(list)
    for a, b in edges: g[a].append(b)
    parent = {start: None}; q = deque([start])
    while q:
        u = q.popleft()
        for v in g.get(u, []):
            if v not in parent: parent[v] = u; q.append(v)
    if target not in parent: return []
    path, cur = [], target
    while parent[cur]:
        p = parent[cur]; path.append((p, cur)); cur = p
    path.reverse(); return path



#     return fig
def branch_sankey(
    nodes, edges, level, root, focus,
    branch_only=False, is_mobile=False,
    height_override=None, font_size_override=None
):
    # 🎨 TEMA (dark) — igual ao original
    DARK_BG = "#0b0f19"
    FONT_CLR = "#e5e7eb"
    TEXT_CLR = "#f9fafb"
    LINK_GREY = "rgba(255,255,255,0.28)"
    TONE_ROOT_DIRECT = "rgba(255,255,255,0.55)"
    NODE_LINE = "rgba(255,255,255,0.08)"
    # 🔵 Azul-celeste para destaque
    HILITE_HEX  = "#4FC3F7"
    HILITE_LINK = "rgba(79,195,247,0.95)"
    BLUE_LEFT   = "rgba(59,130,246,0.50)"   # upstream

    PALETTE = px.colors.qualitative.Dark24

    # -------- normalização p/ lookups robustos --------
    def _norm(s: str) -> str:
        if s is None:
            return ""
        return (str(s)
                .replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
                .replace("–", "-").replace("—", "-").replace("\xa0", " ")
                .strip().casefold())

    # mapa de níveis mutável; inclui chaves normalizadas para fallback
    level_mut = dict(level)  # cópia
    level_norm = { _norm(k): v for k, v in level.items() }

    def get_lvl(name: str, default=None):
        if name in level_mut:
            return level_mut[name]
        n = _norm(name)
        if n in level_norm:
            return level_norm[n]
        return default

    # --- calibração p/ links finos (como no original) ---
    CALIBRATE_THIN = True
    DUMMY_A = "\u200b"; DUMMY_B = "\u200c"
    if CALIBRATE_THIN and DUMMY_A not in nodes:
        nodes = nodes + [DUMMY_A, DUMMY_B]
        last_lvl = max(level_mut.values()) if level_mut else 0
        level_mut[DUMMY_A] = last_lvl + 1
        level_mut[DUMMY_B] = last_lvl + 2
        level_norm[_norm(DUMMY_A)] = level_mut[DUMMY_A]
        level_norm[_norm(DUMMY_B)] = level_mut[DUMMY_B]

    # 1) Inferir níveis que faltam a partir das arestas originais
    edges0 = list(edges)
    for _ in range(len(nodes) + 3):
        changed = False
        for a, b in edges0:
            la = get_lvl(a); lb = get_lvl(b)
            if la is not None and lb is None:
                level_mut[b] = la + 1; level_norm[_norm(b)] = la + 1; changed = True
            elif lb is not None and la is None:
                level_mut[a] = lb - 1; level_norm[_norm(a)] = lb - 1; changed = True
        if not changed:
            break

    # 2) Orientar L→R apenas quando ambos os níveis existem e estão trocados
    def _orient_edges_lr(E):
        out = []
        for a, b in E:
            la, lb = get_lvl(a), get_lvl(b)
            out.append((b, a) if (la is not None and lb is not None and la > lb) else (a, b))
        return out

    edges = _orient_edges_lr(edges0)

    # ⬅⬅⬅ MUDANÇA IMPORTANTE AQUI
    # Em vez de depender de níveis contíguos, obtemos o caminho root→focus
    # diretamente sobre as arestas orientadas (BFS simples).
    path_edges = set(_path_edges(edges, root, focus))

    # posições x (por nível) e y (espalhamento)
    idx = {n: i for i, n in enumerate(nodes)}
    uniq_lvls = sorted({get_lvl(n, 0) for n in nodes})
    pos_map = ({uniq_lvls[0] if uniq_lvls else 0: 0.5}
               if len(uniq_lvls) <= 1 else {lv: float(x) for lv, x in zip(uniq_lvls, np.linspace(0.10, 0.90, len(uniq_lvls)))})
    xs = [pos_map.get(get_lvl(n, 0), 0.5) for n in nodes]

    ys_map = {}
    for lv in uniq_lvls:
        col = [n for n in nodes if n not in {DUMMY_A, DUMMY_B} and get_lvl(n, 0) == lv]
        if not col:
            continue
        ys_lv = np.linspace(0.20, 0.80, num=len(col))
        for n, y in zip(sorted(col, key=str.lower), ys_lv):
            ys_map[n] = float(y)
    ys_map[DUMMY_A] = ys_map.get(DUMMY_A, 0.5)
    ys_map[DUMMY_B] = ys_map.get(DUMMY_B, 0.5)
    ys = [ys_map.get(n, 0.5) for n in nodes]

    reps = (len(nodes) // len(PALETTE)) + 1
    ncolors = (PALETTE * reps)[:len(nodes)]

    # mapeamento de ramos a partir do root (inalterado)
    children_map = defaultdict(list)
    for a, b in edges:
        if get_lvl(a, 0) >= 0 and get_lvl(b, 0) > 0:
            children_map[a].append(b)
    firsthop = {}
    dq = deque(children_map.get(root, []))
    for ch in children_map.get(root, []):
        firsthop[ch] = ch
    while dq:
        u = dq.popleft()
        for v in children_map.get(u, []):
            if v not in firsthop:
                firsthop[v] = firsthop[u]; dq.append(v)

    BRANCH_TONES = {
        "Alternative rock": "rgba(255,255,255,0.34)",
        "Hard rock":        "rgba(255,255,255,0.34)",
        "Punk rock":        "rgba(255,255,255,0.34)",
        "Pop rock":         "rgba(255,255,255,0.34)",
        "Funk":             "rgba(255,255,255,0.34)",
        "Hip hop":          "rgba(255,255,255,0.34)",
        "Dark wave":        "rgba(255,255,255,0.34)",
        "Ethereal wave":    "rgba(255,255,255,0.34)",
    }

    # nós no caminho (garante root/focus)
    path_nodes = {root, focus} | {a for a, _ in path_edges} | {b for _, b in path_edges}
    for i, n in enumerate(nodes):
        if n in path_nodes:
            ncolors[i] = HILITE_HEX
    if CALIBRATE_THIN:
        ncolors[idx[DUMMY_A]] = "rgba(0,0,0,0)"
        ncolors[idx[DUMMY_B]] = "rgba(0,0,0,0)"

    # ligações
    src, dst, val, lcol = [], [], [], []
    for a, b in edges:
        if a not in idx or b not in idx:
            continue
        src.append(idx[a]); dst.append(idx[b]); val.append(1)

        la, lb = get_lvl(a, 0), get_lvl(b, 0)
        is_left_edge = (la < 0 and lb <= 0)  # upstream (à esquerda)
        on_path = (a, b) in path_edges

        if on_path:
            lcol.append(HILITE_LINK)
        elif is_left_edge:
            lcol.append(BLUE_LEFT)
        else:
            if la == 0 and lb == 1:
                lcol.append(TONE_ROOT_DIRECT)
            elif la >= 0 and lb > 0:
                fh = canonical_name(firsthop.get(b) or firsthop.get(a) or "")
                lcol.append(BRANCH_TONES.get(fh, LINK_GREY))
            else:
                lcol.append("rgba(0,0,0,0)" if branch_only else LINK_GREY)

    if CALIBRATE_THIN:
        CAL_FACTOR = 7
        src.append(idx[DUMMY_A]); dst.append(idx[DUMMY_B]); val.append(max(40, CAL_FACTOR * len(edges)))
        lcol.append("rgba(0,0,0,0)")

    few = len(nodes) <= 8
    node_thickness = (10 if is_mobile else (14 if few else 22))
    node_pad = (8 if is_mobile else (10 if few else 18))

    visible = [n for n in nodes if n not in {DUMMY_A, DUMMY_B}]
    uniq_lvls_vis = sorted({get_lvl(n, 0) for n in visible}) if visible else [0]
    max_per_level = max(sum(1 for n in visible if get_lvl(n, 0) == lv) for lv in uniq_lvls_vis) if visible else 1

    base_h = 180 if is_mobile else 320
    chart_height = int(min(680, max(300, base_h + 26 * max_per_level)))
    if height_override:
        chart_height = int(height_override)

    font_size = (13 if is_mobile else 15)
    if font_size_override:
        font_size = int(font_size_override)
    hover_size = max(10, font_size - 1)

    fig = go.Figure(go.Sankey(
        arrangement="fixed",
        node=dict(
            label=nodes, x=xs, y=ys, pad=node_pad, thickness=node_thickness,
            color=ncolors, line=dict(color=NODE_LINE, width=0.5)
        ),
        link=dict(source=src, target=dst, value=val, color=lcol),
    ))

    fig.update_layout(
        paper_bgcolor=DARK_BG, plot_bgcolor=DARK_BG,
        margin=dict(l=0, r=0, t=0, b=0), height=chart_height,
        font=dict(
            family="Segoe UI, Roboto, Helvetica, Arial, sans-serif",
            size=font_size, color=FONT_CLR
        ),
        hoverlabel=dict(
            bgcolor="rgba(17,24,39,0.92)",
            bordercolor="rgba(255,255,255,0.15)",
            font=dict(
                family="Segoe UI, Roboto, Helvetica, Arial, sans-serif",
                size=hover_size, color=FONT_CLR
            )
        )
    )
    fig.update_traces(
        selector=dict(type="sankey"),
        textfont=dict(
            family="Segoe UI, Roboto, Helvetica, Arial, sans-serif",
            size=font_size, color=TEXT_CLR
        )
    )
    return fig
