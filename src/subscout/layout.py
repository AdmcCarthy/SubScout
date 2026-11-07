"""Build-time network layout: deterministic force-directed positions for a sequence of frames.

Each frame (e.g. a licensing round) is laid out with a Fruchterman-Reingold style simulation,
warm-started from the previous frame's positions so the same node stays roughly in place and the
reader can follow it from frame to frame. All frames share one scale, so a smaller network looks
smaller. Output coordinates are in width units: x in [0, 1], y in [0, 1 / aspect], y down, so the
renderer scales both by the plot width. Overlaps are resolved after scaling, against the same dot
radius the renderer draws (`rmax` x sqrt(size / largest size), in width units).
"""

from __future__ import annotations

import hashlib
import math

import numpy as np


def _angle(key: str) -> float:
    h = int(hashlib.md5(key.encode()).hexdigest()[:8], 16)
    return (h / 0xFFFFFFFF) * 2 * math.pi


def _simulate(
    ids: list[str],
    sizes: np.ndarray,
    edges: list[tuple[int, int, float]],
    init: np.ndarray,
    warm: bool,
    aspect: float,
    iters: int = 400,
) -> np.ndarray:
    n = len(ids)
    pos = init.copy()
    if n <= 1:
        return np.zeros((n, 2))
    k = 1.0  # ideal spacing, fixed across frames so extent follows node count
    r = 0.22 * np.sqrt(sizes / sizes.max())  # radius in layout units, for collision
    ei = np.array([[a, b] for a, b, _ in edges], dtype=int).reshape(-1, 2)
    ew = np.array([w for *_, w in edges], dtype=float)
    ew = np.sqrt(ew / ew.max()) if len(ew) else ew
    t0 = 0.35 if warm else 1.2
    stretch = np.array([1.0, aspect])  # gravity pulls harder vertically on wide canvases
    for it in range(iters):
        t = t0 * (1 - it / iters) + 0.01
        d = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((d**2).sum(-1)) + 1e-9
        np.fill_diagonal(dist, np.inf)
        rep = (k * k / dist**2)[:, :, None] * d
        disp = rep.sum(1)
        if len(ei):
            dv = pos[ei[:, 0]] - pos[ei[:, 1]]
            dl = np.sqrt((dv**2).sum(-1)) + 1e-9
            f = (dl / k * (0.4 + ew))[:, None] * dv
            np.add.at(disp, ei[:, 0], -f)
            np.add.at(disp, ei[:, 1], f)
        disp -= 0.14 * pos * stretch * np.sqrt(sizes / sizes.mean())[:, None]
        ln = np.sqrt((disp**2).sum(-1)) + 1e-9
        pos += disp / ln[:, None] * np.minimum(ln, t)[:, None]
        # collisions: push overlapping discs apart
        d = pos[:, None, :] - pos[None, :, :]
        dist = np.sqrt((d**2).sum(-1)) + 1e-9
        np.fill_diagonal(dist, np.inf)
        need = r[:, None] + r[None, :] + 0.08
        over = np.clip(need - dist, 0, None)
        pos += 0.5 * ((over / dist)[:, :, None] * d).sum(1)
    return pos - pos.mean(0)


def network_layout(
    frames: list[str],
    nodes: dict[str, list[dict]],
    edges: dict[str, list[dict]],
    aspect: float = 1.5,
    rmax: float = 0.04,
    pad: float = 0.006,
) -> dict[str, dict[str, tuple[float, float]]]:
    """nodes[frame] = [{id, size}], edges[frame] = [{a, b, w}] -> {frame: {id: (x, y)}}."""
    prev: dict[str, np.ndarray] = {}
    raw: dict[str, dict[str, np.ndarray]] = {}
    for fr in frames:
        ns = nodes.get(fr, [])
        ids = [str(d["id"]) for d in ns]
        idx = {k: i for i, k in enumerate(ids)}
        sizes = np.array([max(float(d["size"]), 1e-6) for d in ns]) if ns else np.zeros(0)
        es = [
            (idx[e["a"]], idx[e["b"]], float(e["w"]))
            for e in edges.get(fr, [])
            if e["a"] in idx and e["b"] in idx
        ]
        nbr: dict[int, list[tuple[float, int]]] = {}
        for a, b, w in es:
            nbr.setdefault(a, []).append((w, b))
            nbr.setdefault(b, []).append((w, a))
        init = np.zeros((len(ids), 2))
        known = [i for i, k in enumerate(ids) if k in prev]
        rad = math.sqrt(len(ids)) * 0.9
        for i, key in enumerate(ids):
            if key in prev:
                init[i] = prev[key]
                continue
            anchor = next((ids[j] for _, j in sorted(nbr.get(i, []), reverse=True) if ids[j] in prev), None)
            a = _angle(key)
            if anchor is not None:
                init[i] = prev[anchor] + 0.6 * np.array([math.cos(a), math.sin(a)])
            else:
                rr = rad * (0.5 if not known else 1.1)
                init[i] = rr * np.array([math.cos(a), math.sin(a)])
        pos = _simulate(ids, sizes, es, init, bool(known), aspect)
        raw[fr] = {k: pos[i] for i, k in enumerate(ids)}
        prev = {**prev, **raw[fr]}

    # one shared scale across frames, each frame centred on its bounding box
    def span(i):  # trimmed, so one stray leaf does not shrink every frame; strays are clamped below
        q = [np.percentile([p[i] for p in r.values()], [3, 97]) for r in raw.values() if r]
        return max((b - a for a, b in q), default=1) * 1.08 or 1

    s = min(0.88 / span(0), 0.88 / (aspect * span(1)))
    smax = max((float(d["size"]) for ns in nodes.values() for d in ns), default=1) or 1
    out = {}
    for fr, r in raw.items():
        if not r:
            out[fr] = {}
            continue
        ids = list(r)
        p = np.array([r[k] for k in ids])
        p = (p - np.median(p, 0)) * s + np.array([0.5, 0.5 / aspect])
        size = {str(d["id"]): float(d["size"]) for d in nodes[fr]}
        rad = np.array([rmax * math.sqrt(max(size[k], 0) / smax) for k in ids]) + pad
        lo, hi = rad[:, None], np.array([1.0, 1.0 / aspect]) - rad[:, None]
        p = np.clip(p, lo, hi)
        for _ in range(120):
            d = p[:, None, :] - p[None, :, :]
            dist = np.sqrt((d**2).sum(-1)) + 1e-9
            np.fill_diagonal(dist, np.inf)
            over = np.clip(rad[:, None] + rad[None, :] - dist, 0, None)
            if not over.any():
                break
            p += 0.5 * ((over / dist)[:, :, None] * d).sum(1)
            p = np.clip(p, lo, hi)
        out[fr] = {k: (round(float(p[i, 0]), 4), round(float(p[i, 1]), 4)) for i, k in enumerate(ids)}
    return out
