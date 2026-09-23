"""Programmatic SVG diagram generation for image-based question-bank items.

Every diagram is built from the same parameters that determine the question's correct
answer, so the candidate genuinely needs to read the image - never a decorative stock
picture. Kept as plain SVG (not PNG) so it needs no image library and renders crisply
at any size; the object store serves it with ``image/svg+xml`` like any other upload.
"""

from __future__ import annotations

from dataclasses import dataclass

_FONT = "font-family='Segoe UI, Arial, sans-serif'"
_PALETTE = ["#4f46e5", "#0f9b8e", "#e05252", "#d97706", "#6366f1", "#0ea5e9", "#818cf8"]


def _header(w: int, h: int) -> str:
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
        f"viewBox='0 0 {w} {h}'><rect width='{w}' height='{h}' fill='#ffffff'/>"
    )


def _box(x: int, y: int, w: int, h: int, label: str, fill: str = "#eef2ff", stroke: str = "#4f46e5") -> str:
    return (
        f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='6' fill='{fill}' stroke='{stroke}' stroke-width='1.5'/>"
        f"<text x='{x + w / 2}' y='{y + h / 2 + 4}' text-anchor='middle' {_FONT} font-size='12' fill='#1e1b2e'>{label}</text>"
    )


def _text(x: int, y: int, label: str, size: int = 12, anchor: str = "middle", weight: str = "normal", color: str = "#1e1b2e") -> str:
    return f"<text x='{x}' y='{y}' text-anchor='{anchor}' {_FONT} font-size='{size}' font-weight='{weight}' fill='{color}'>{label}</text>"


def _line(x1: int, y1: int, x2: int, y2: int, color: str = "#4f46e5", width: float = 1.5, dash: str = "") -> str:
    d = f" stroke-dasharray='{dash}'" if dash else ""
    return f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='{color}' stroke-width='{width}'{d}/>"


def _arrow_marker() -> str:
    return (
        "<defs><marker id='arrow' markerWidth='8' markerHeight='8' refX='6' refY='3' "
        "orient='auto'><path d='M0,0 L6,3 L0,6 Z' fill='#4f46e5'/></marker></defs>"
    )


def _arrow(x1: int, y1: int, x2: int, y2: int) -> str:
    return f"<line x1='{x1}' y1='{y1}' x2='{x2}' y2='{y2}' stroke='#4f46e5' stroke-width='1.5' marker-end='url(#arrow)'/>"


def _circle(cx: int, cy: int, r: int, fill: str, label: str = "") -> str:
    out = f"<circle cx='{cx}' cy='{cy}' r='{r}' fill='{fill}' stroke='#1e1b2e' stroke-width='1'/>"
    if label:
        out += _text(cx, cy + 4, label, size=11, color="#ffffff")
    return out


def _footer() -> str:
    return "</svg>"


@dataclass
class Diagram:
    svg: str
    kind: str


# ---------------------------------------------------------------------------
# Operating Systems
# ---------------------------------------------------------------------------

def os_process_state(states: list[str], highlight: int) -> str:
    """A process-state transition diagram with one state highlighted."""
    w, h = 560, 220
    out = [_header(w, h), _arrow_marker()]
    xs = [60, 200, 340, 480]
    ys = [60, 150, 60, 150]
    for i, s in enumerate(states[:4]):
        fill = "#fde68a" if i == highlight else "#eef2ff"
        out.append(_box(xs[i], ys[i], 100, 44, s, fill=fill))
    pairs = [(0, 1), (1, 0), (1, 2), (2, 3), (2, 1)]
    for a, b in pairs:
        if a < len(states) and b < len(states):
            out.append(_arrow(xs[a] + 50, ys[a] + 44 if ys[a] < ys[b] else ys[a], xs[b] + 50, ys[b] if ys[a] < ys[b] else ys[b] + 44))
    out.append(_footer())
    return "".join(out)


def os_gantt_chart(processes: list[tuple[str, int, int]]) -> str:
    """processes: list of (label, start, duration) already scheduled in order."""
    w = 80 + sum(d for _, _, d in processes) * 22 + 40
    h = 140
    out = [_header(w, h)]
    x = 60
    y = 50
    for label, _start, dur in processes:
        width = dur * 22
        color = _PALETTE[hash(label) % len(_PALETTE)]
        out.append(_box(x, y, width, 40, label, fill=color, stroke="#1e1b2e"))
        out.append(_text(x, y + 60, str(_running_total(processes, label)), size=10, color="#4b5563"))
        x += width
    out.append(_line(60, y + 40, x, y + 40, color="#1e1b2e", width=2))
    out.append(_text(60, 30, "Gantt Chart (time units on x-axis)", size=12, anchor="start", weight="bold"))
    out.append(_footer())
    return "".join(out)


def _running_total(processes: list[tuple[str, int, int]], upto_label: str) -> int:
    total = 0
    for label, _start, dur in processes:
        total += dur
        if label == upto_label:
            return total
    return total


def os_memory_allocation(blocks: list[tuple[str, int]]) -> str:
    """blocks: list of (label, size_kb). Drawn as a vertical stacked memory map."""
    w, h = 260, 60 + sum(max(b[1] // 4, 24) for b in blocks)
    out = [_header(w, h)]
    y = 30
    for label, size in blocks:
        bh = max(size // 4, 24)
        color = "#c7d2fe" if label != "Free" else "#e5e7eb"
        out.append(_box(40, y, 180, bh, f"{label} ({size}KB)", fill=color))
        y += bh
    out.append(_footer())
    return "".join(out)


def os_page_table(entries: list[tuple[int, int, bool]]) -> str:
    """entries: list of (page_no, frame_no, valid)."""
    w, h = 320, 40 + 30 * (len(entries) + 1)
    out = [_header(w, h)]
    out.append(_text(160, 24, "Page Table", size=13, weight="bold"))
    out.append(_box(40, 40, 100, 26, "Page #", fill="#c7d2fe"))
    out.append(_box(140, 40, 100, 26, "Frame #", fill="#c7d2fe"))
    out.append(_box(240, 40, 40, 26, "V", fill="#c7d2fe"))
    y = 66
    for page, frame, valid in entries:
        out.append(_box(40, y, 100, 26, str(page), fill="#f9fafb"))
        out.append(_box(140, y, 100, 26, str(frame) if valid else "-", fill="#f9fafb"))
        out.append(_box(240, y, 40, 26, "1" if valid else "0", fill="#fde68a" if not valid else "#dcfce7"))
        y += 26
    out.append(_footer())
    return "".join(out)


# ---------------------------------------------------------------------------
# Computer Networks
# ---------------------------------------------------------------------------

def net_osi_layers(labels: list[str], highlight: int) -> str:
    w, h = 260, 40 + 34 * len(labels)
    out = [_header(w, h)]
    y = 20
    for i, label in enumerate(labels):
        fill = "#fde68a" if i == highlight else "#eef2ff"
        out.append(_box(30, y, 200, 28, f"{len(labels) - i}. {label}", fill=fill))
        y += 34
    out.append(_footer())
    return "".join(out)


def net_topology(kind: str, nodes: int) -> str:
    w, h = 320, 260
    out = [_header(w, h)]
    cx, cy = w // 2, h // 2
    positions = []
    if kind == "star":
        out.append(_circle(cx, cy, 22, "#4f46e5", "SW"))
        for i in range(nodes):
            import math
            ang = 2 * math.pi * i / nodes
            x, y = cx + int(120 * math.cos(ang)), cy + int(100 * math.sin(ang))
            positions.append((x, y))
            out.append(_line(cx, cy, x, y, color="#a1a1b5"))
            out.append(_circle(x, y, 16, "#0f9b8e", f"H{i + 1}"))
    elif kind == "ring":
        import math
        for i in range(nodes):
            ang = 2 * math.pi * i / nodes
            x, y = cx + int(110 * math.cos(ang)), cy + int(100 * math.sin(ang))
            positions.append((x, y))
        for i in range(nodes):
            x1, y1 = positions[i]
            x2, y2 = positions[(i + 1) % nodes]
            out.append(_line(x1, y1, x2, y2, color="#a1a1b5"))
        for i, (x, y) in enumerate(positions):
            out.append(_circle(x, y, 16, "#0f9b8e", f"H{i + 1}"))
    else:  # bus
        out.append(_line(40, cy, w - 40, cy, color="#1e1b2e", width=3))
        step = (w - 80) // max(nodes - 1, 1)
        for i in range(nodes):
            x = 40 + i * step
            out.append(_line(x, cy, x, cy - 40, color="#a1a1b5"))
            out.append(_circle(x, cy - 56, 16, "#0f9b8e", f"H{i + 1}"))
    out.append(_footer())
    return "".join(out)


def net_packet_structure(fields: list[tuple[str, int]]) -> str:
    """fields: list of (name, bytes)."""
    total_width = sum(f[1] for f in fields) * 18
    w, h = max(total_width + 40, 300), 100
    out = [_header(w, h)]
    x = 20
    for name, size in fields:
        fw = size * 18
        out.append(_box(x, 30, fw, 40, f"{name}\n({size}B)".split("\n")[0], fill="#eef2ff"))
        out.append(_text(x + fw / 2, 82, f"{size}B", size=10, color="#4b5563"))
        x += fw
    out.append(_footer())
    return "".join(out)


def net_routing_table(entries: list[tuple[str, str, int]]) -> str:
    """entries: list of (destination, next_hop, metric)."""
    w, h = 340, 40 + 28 * (len(entries) + 1)
    out = [_header(w, h)]
    out.append(_text(170, 22, "Routing Table", size=13, weight="bold"))
    heads = ["Destination", "Next Hop", "Metric"]
    xs = [20, 160, 270]
    for i, head in enumerate(heads):
        out.append(_box(xs[i], 30, [130, 100, 60][i], 24, head, fill="#c7d2fe"))
    y = 56
    for dest, hop, metric in entries:
        out.append(_box(xs[0], y, 130, 24, dest, fill="#f9fafb"))
        out.append(_box(xs[1], y, 100, 24, hop, fill="#f9fafb"))
        out.append(_box(xs[2], y, 60, 24, str(metric), fill="#f9fafb"))
        y += 28
    out.append(_footer())
    return "".join(out)


# ---------------------------------------------------------------------------
# Engineering Mathematics
# ---------------------------------------------------------------------------

def math_matrix(matrix: list[list[float]], label: str = "A") -> str:
    rows, cols = len(matrix), len(matrix[0])
    cell = 50
    w, h = cols * cell + 80, rows * cell + 60
    out = [_header(w, h)]
    out.append(_text(20, 30, f"{label} =", size=16, anchor="start", weight="bold"))
    ox, oy = 70, 20
    out.append(f"<line x1='{ox}' y1='{oy}' x2='{ox}' y2='{oy + rows * cell}' stroke='#1e1b2e' stroke-width='2'/>")
    out.append(f"<line x1='{ox + cols * cell}' y1='{oy}' x2='{ox + cols * cell}' y2='{oy + rows * cell}' stroke='#1e1b2e' stroke-width='2'/>")
    for r in range(rows):
        for c in range(cols):
            cx, cy = ox + c * cell + cell / 2, oy + r * cell + cell / 2 + 5
            out.append(_text(int(cx), int(cy), str(matrix[r][c]), size=14))
    out.append(_footer())
    return "".join(out)


def math_function_plot(points: list[tuple[float, float]], title: str) -> str:
    w, h = 340, 260
    out = [_header(w, h)]
    ox, oy = 50, h - 40
    out.append(_line(ox, 20, ox, oy, color="#1e1b2e"))
    out.append(_line(ox, oy, w - 20, oy, color="#1e1b2e"))
    out.append(_text(w // 2, 16, title, size=12, weight="bold"))
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    xr = max(max(xs) - min(xs), 1e-6)
    yr = max(max(ys) - min(ys), 1e-6)
    path = []
    for x, y in points:
        px = ox + (x - min(xs)) / xr * (w - 90)
        py = oy - (y - min(ys)) / yr * (oy - 40)
        path.append(f"{px:.1f},{py:.1f}")
    out.append(f"<polyline points='{' '.join(path)}' fill='none' stroke='#4f46e5' stroke-width='2'/>")
    out.append(_footer())
    return "".join(out)


def math_geometry_triangle(sides: tuple[float, float, float]) -> str:
    a, b, c = sides
    w, h = 300, 240
    out = [_header(w, h)]
    out.append("<polygon points='60,200 260,200 160,40' fill='#eef2ff' stroke='#4f46e5' stroke-width='2'/>")
    out.append(_text(160, 220, f"c = {c}", size=12))
    out.append(_text(95, 130, f"a = {a}", size=12, anchor="start"))
    out.append(_text(215, 130, f"b = {b}", size=12, anchor="end"))
    out.append(_footer())
    return "".join(out)


def math_vector_diagram(vectors: list[tuple[str, float, float]]) -> str:
    w, h = 300, 300
    cx, cy = w // 2, h // 2
    out = [_header(w, h), _arrow_marker()]
    out.append(_line(20, cy, w - 20, cy, color="#d1d5db"))
    out.append(_line(cx, 20, cx, h - 20, color="#d1d5db"))
    scale = 20
    for label, vx, vy in vectors:
        x2, y2 = cx + vx * scale, cy - vy * scale
        out.append(_arrow(cx, cy, int(x2), int(y2)))
        out.append(_text(int(x2) + 10, int(y2), f"{label}({vx},{vy})", size=11, anchor="start"))
    out.append(_footer())
    return "".join(out)


# ---------------------------------------------------------------------------
# Machine Learning
# ---------------------------------------------------------------------------

def ml_decision_tree(root: str, children: list[tuple[str, str]], leaves: list[str]) -> str:
    w, h = 420, 220
    out = [_header(w, h), _arrow_marker()]
    out.append(_box(160, 20, 100, 40, root, fill="#fde68a"))
    xs = [60, 260]
    for i, (edge_label, node) in enumerate(children):
        out.append(_arrow(210, 60, xs[i] + 50, 110))
        out.append(_text((210 + xs[i] + 50) // 2, 90, edge_label, size=10, color="#4b5563"))
        out.append(_box(xs[i], 110, 100, 40, node, fill="#eef2ff"))
    leaf_xs = [20, 140, 260, 360]
    for i, leaf in enumerate(leaves[:4]):
        lx = leaf_xs[i]
        parent_x = xs[0] + 50 if i < 2 else xs[1] + 50
        out.append(_arrow(parent_x, 150, lx + 40, 180))
        out.append(_box(lx, 180, 80, 32, leaf, fill="#dcfce7"))
    out.append(_footer())
    return "".join(out)


def ml_scatter_plot(points: list[tuple[float, float, int]], n_clusters: int) -> str:
    w, h = 320, 260
    out = [_header(w, h)]
    ox, oy = 40, h - 30
    out.append(_line(ox, 20, ox, oy, color="#1e1b2e"))
    out.append(_line(ox, oy, w - 20, oy, color="#1e1b2e"))
    for x, y, cluster in points:
        color = _PALETTE[cluster % len(_PALETTE)]
        out.append(f"<circle cx='{ox + x * 12}' cy='{oy - y * 12}' r='5' fill='{color}'/>")
    out.append(_text(w // 2, 12, f"{n_clusters} clusters", size=11, weight="bold"))
    out.append(_footer())
    return "".join(out)


def ml_confusion_matrix(tp: int, fp: int, fn: int, tn: int) -> str:
    w, h = 300, 260
    out = [_header(w, h)]
    labels = [("TP", tp, "#dcfce7"), ("FN", fn, "#fee2e2"), ("FP", fp, "#fee2e2"), ("TN", tn, "#dcfce7")]
    xs = [80, 180, 80, 180]
    ys = [70, 70, 130, 130]
    for i, (name, val, color) in enumerate(labels):
        out.append(_box(xs[i], ys[i], 90, 50, f"{name}={val}", fill=color))
    out.append(_text(30, 60, "Actual +", size=10, anchor="start"))
    out.append(_text(30, 120, "Actual -", size=10, anchor="start"))
    out.append(_text(90, 40, "Pred +", size=10))
    out.append(_text(190, 40, "Pred -", size=10))
    out.append(_footer())
    return "".join(out)


def ml_clustering(centroids: list[tuple[float, float]], points: list[tuple[float, float, int]]) -> str:
    w, h = 320, 260
    out = [_header(w, h)]
    ox, oy = 30, h - 30
    for x, y, cluster in points:
        color = _PALETTE[cluster % len(_PALETTE)]
        out.append(f"<circle cx='{ox + x * 14}' cy='{oy - y * 14}' r='4' fill='{color}' opacity='0.7'/>")
    for i, (cx, cy) in enumerate(centroids):
        color = _PALETTE[i % len(_PALETTE)]
        out.append(f"<rect x='{ox + cx * 14 - 6}' y='{oy - cy * 14 - 6}' width='12' height='12' fill='{color}' stroke='#1e1b2e' stroke-width='1.5'/>")
    out.append(_footer())
    return "".join(out)


# ---------------------------------------------------------------------------
# Natural Language Processing
# ---------------------------------------------------------------------------

def nlp_pipeline(steps: list[str]) -> str:
    w = 40 + 140 * len(steps)
    h = 100
    out = [_header(w, h), _arrow_marker()]
    x = 20
    for i, step in enumerate(steps):
        out.append(_box(x, 30, 110, 40, step, fill=_PALETTE[i % len(_PALETTE)], stroke="#1e1b2e"))
        if i < len(steps) - 1:
            out.append(_arrow(x + 110, 50, x + 140, 50))
        x += 140
    out.append(_footer())
    return "".join(out)


def nlp_tokenization(sentence: str, tokens: list[str]) -> str:
    w = max(40 + 70 * len(tokens), 300)
    h = 120
    out = [_header(w, h)]
    out.append(_text(w // 2, 22, f'"{sentence}"', size=12, weight="bold"))
    x = 20
    for tok in tokens:
        tw = max(len(tok) * 9, 40)
        out.append(_box(x, 50, tw, 36, tok, fill="#eef2ff"))
        x += tw + 10
    out.append(_footer())
    return "".join(out)


def nlp_parse_tree(root: str, children: list[str], grandchildren: dict[str, list[str]]) -> str:
    w, h = 420, 220
    out = [_header(w, h), _arrow_marker()]
    out.append(_box(160, 20, 100, 36, root, fill="#fde68a"))
    n = len(children)
    xs = [40 + i * (340 // max(n - 1, 1)) for i in range(n)] if n > 1 else [190]
    for i, child in enumerate(children):
        out.append(_arrow(210, 56, xs[i] + 50, 100))
        out.append(_box(xs[i], 100, 100, 34, child, fill="#eef2ff"))
        gc = grandchildren.get(child, [])
        for j, g in enumerate(gc):
            gx = xs[i] + j * 60
            out.append(_arrow(xs[i] + 50, 134, gx + 30, 170))
            out.append(_box(gx, 170, 60, 30, g, fill="#dcfce7"))
    out.append(_footer())
    return "".join(out)


def nlp_attention_weights(tokens: list[str], weights: list[float]) -> str:
    w = max(60 + 60 * len(tokens), 300)
    h = 140
    out = [_header(w, h)]
    x = 30
    max_w = max(weights)
    for tok, wt in zip(tokens, weights):
        bar_h = int(80 * (wt / max_w))
        out.append(_box(x, 100 - bar_h, 40, bar_h, "", fill=_PALETTE[0]))
        out.append(_text(x + 20, 116, tok, size=10))
        out.append(_text(x + 20, 100 - bar_h - 6, f"{wt:.2f}", size=9, color="#4b5563"))
        x += 60
    out.append(_footer())
    return "".join(out)


# ---------------------------------------------------------------------------
# Artificial Intelligence
# ---------------------------------------------------------------------------

def ai_search_tree(root: str, edges: list[tuple[str, str, int]]) -> str:
    """edges: (parent, child, cost)."""
    nodes = {root: (200, 30)}
    level2 = [e for e in edges if e[0] == root]
    for i, (_p, c, _cost) in enumerate(level2):
        nodes[c] = (80 + i * 140, 110)
    level3 = [e for e in edges if e[0] != root]
    grouped: dict[str, list] = {}
    for p, c, cost in level3:
        grouped.setdefault(p, []).append((c, cost))
    for p, kids in grouped.items():
        px, py = nodes.get(p, (200, 110))
        for j, (c, _cost) in enumerate(kids):
            nodes[c] = (px - 30 + j * 60, 190)
    w, h = 420, 240
    out = [_header(w, h), _arrow_marker()]
    for p, c, cost in edges:
        if p in nodes and c in nodes:
            x1, y1 = nodes[p]
            x2, y2 = nodes[c]
            out.append(_arrow(x1 + 20, y1 + 15, x2 + 20, y2 - 15))
            out.append(_text((x1 + x2) // 2 + 30, (y1 + y2) // 2, str(cost), size=10, color="#e05252"))
    for name, (x, y) in nodes.items():
        out.append(_circle(x + 20, y, 20, "#4f46e5" if name == root else "#0f9b8e", name))
    out.append(_footer())
    return "".join(out)


def ai_minimax_tree(leaves: list[int], level_labels: tuple[str, str]) -> str:
    w, h = 420, 220
    out = [_header(w, h), _arrow_marker()]
    n = len(leaves)
    leaf_xs = [30 + i * (360 // (n - 1)) for i in range(n)] if n > 1 else [190]
    for x, v in zip(leaf_xs, leaves):
        out.append(_circle(x, 190, 18, "#dcfce7" if False else "#eef2ff", str(v)))
    mins = [min(leaves[i:i + 2]) for i in range(0, n, 2)]
    min_xs = [(leaf_xs[i] + leaf_xs[i + 1]) // 2 for i in range(0, n, 2)]
    for x, v in zip(min_xs, mins):
        out.append(_circle(x, 120, 20, "#fee2e2", str(v)))
    maxv = max(mins)
    out.append(_circle(w // 2, 50, 22, "#fde68a", str(maxv)))
    for x in leaf_xs:
        pass
    for lx, mx in zip(leaf_xs, [x for x in min_xs for _ in range(2)]):
        out.append(_line(mx, 140, lx, 172, color="#a1a1b5"))
    for mx in min_xs:
        out.append(_line(w // 2, 70, mx, 100, color="#a1a1b5"))
    out.append(_text(w // 2, 25, f"{level_labels[0]} (top) / {level_labels[1]} (middle)", size=10))
    out.append(_footer())
    return "".join(out)


def ai_state_space(states: list[str], edges: list[tuple[int, int]], start: int, goal: int) -> str:
    import math
    w, h = 340, 280
    cx, cy = w // 2, h // 2
    positions = []
    for i in range(len(states)):
        ang = 2 * math.pi * i / len(states)
        positions.append((cx + int(120 * math.cos(ang)), cy + int(110 * math.sin(ang))))
    out = [_header(w, h)]
    for a, b in edges:
        out.append(_line(*positions[a], *positions[b], color="#a1a1b5"))
    for i, (x, y) in enumerate(positions):
        color = "#4f46e5" if i == start else ("#0f9b8e" if i == goal else "#818cf8")
        out.append(_circle(x, y, 18, color, states[i]))
    out.append(_footer())
    return "".join(out)


def ai_knowledge_graph(triples: list[tuple[str, str, str]]) -> str:
    nodes = []
    for s, _p, o in triples:
        if s not in nodes:
            nodes.append(s)
        if o not in nodes:
            nodes.append(o)
    import math
    w, h = 380, 300
    cx, cy = w // 2, h // 2
    positions = {n: (cx + int(130 * math.cos(2 * math.pi * i / len(nodes))), cy + int(120 * math.sin(2 * math.pi * i / len(nodes)))) for i, n in enumerate(nodes)}
    out = [_header(w, h)]
    for s, p, o in triples:
        x1, y1 = positions[s]
        x2, y2 = positions[o]
        out.append(_line(x1, y1, x2, y2, color="#a1a1b5"))
        out.append(_text((x1 + x2) // 2, (y1 + y2) // 2, p, size=9, color="#4b5563"))
    for n, (x, y) in positions.items():
        out.append(_circle(x, y, 24, "#4f46e5", n))
    out.append(_footer())
    return "".join(out)


# ---------------------------------------------------------------------------
# Deep Learning
# ---------------------------------------------------------------------------

def dl_nn_architecture(layer_sizes: list[int]) -> str:
    w, h = 420, 260
    out = [_header(w, h)]
    layer_x = [40 + i * (340 // max(len(layer_sizes) - 1, 1)) for i in range(len(layer_sizes))]
    positions = []
    for x, n in zip(layer_x, layer_sizes):
        ys = [50 + j * (180 // max(n - 1, 1)) if n > 1 else 130 for j in range(n)]
        positions.append([(x, y) for y in ys])
    for li in range(len(positions) - 1):
        for x1, y1 in positions[li]:
            for x2, y2 in positions[li + 1]:
                out.append(_line(x1, y1, x2, y2, color="#e5e7eb", width=1))
    for li, layer in enumerate(positions):
        for x, y in layer:
            out.append(_circle(x, y, 12, _PALETTE[li % len(_PALETTE)]))
    labels = ["Input"] + ["Hidden"] * (len(layer_sizes) - 2) + ["Output"]
    for x, label, n in zip(layer_x, labels, layer_sizes):
        out.append(_text(x, 245, f"{label} ({n})", size=10))
    out.append(_footer())
    return "".join(out)


def dl_cnn_architecture(layers: list[tuple[str, str]]) -> str:
    """layers: list of (kind, size_label)."""
    w = 40 + 120 * len(layers)
    h = 140
    out = [_header(w, h), _arrow_marker()]
    x = 20
    for kind, size in layers:
        color = {"conv": "#4f46e5", "pool": "#0f9b8e", "fc": "#d97706", "input": "#818cf8", "output": "#e05252"}.get(kind, "#6366f1")
        out.append(_box(x, 40, 100, 44, f"{kind.upper()}\n{size}".split("\n")[0], fill=color, stroke="#1e1b2e"))
        out.append(_text(x + 50, 96, size, size=9, color="#4b5563"))
        if x + 120 < w:
            out.append(_arrow(x + 100, 62, x + 120, 62))
        x += 120
    out.append(_footer())
    return "".join(out)


def dl_convolution_operation(input_grid: list[list[int]], kernel: list[list[int]]) -> str:
    cell = 34
    iw = len(input_grid[0]) * cell
    ih = len(input_grid) * cell
    kw = len(kernel[0]) * cell
    kh = len(kernel) * cell
    w, h = iw + kw + 60, max(ih, kh) + 60
    out = [_header(w, h)]
    out.append(_text(iw // 2, 20, "Input", size=11, weight="bold"))
    for r, row in enumerate(input_grid):
        for c, val in enumerate(row):
            out.append(_box(c * cell, 30 + r * cell, cell, cell, str(val), fill="#eef2ff"))
    ox = iw + 40
    out.append(_text(ox + kw // 2, 20, "Kernel", size=11, weight="bold"))
    for r, row in enumerate(kernel):
        for c, val in enumerate(row):
            out.append(_box(ox + c * cell, 30 + r * cell, cell, cell, str(val), fill="#fde68a"))
    out.append(_footer())
    return "".join(out)


def dl_activation_graph(name: str, points: list[tuple[float, float]]) -> str:
    return math_function_plot(points, f"{name} activation function")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

DIAGRAM_TOPICS: dict[str, list[str]] = {
    "os": ["process_state", "gantt_chart", "memory_allocation", "page_table"],
    "net": ["osi_layers", "topology", "packet_structure", "routing_table"],
    "math": ["matrix", "function_plot", "geometry", "vectors"],
    "ml": ["decision_tree", "scatter_plot", "confusion_matrix", "clustering"],
    "nlp": ["pipeline", "tokenization", "parse_tree", "attention"],
    "ai": ["search_tree", "minimax_tree", "state_space", "knowledge_graph"],
    "dl": ["nn_architecture", "cnn_architecture", "convolution", "activation_graph"],
}
