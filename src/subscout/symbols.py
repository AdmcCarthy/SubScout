"""Symbols for wells, wellbores and installations: parse, validate and generate the runtime data.

The source is `tokens/symbols.toml` (vocabulary and shapes, after the Sodir Geostandard 3.4 and 3.5).
`subscout symbols` writes `runtime/js/symbols-data.js` and `runtime/js/symbols.json`; the drawing code is
`runtime/js/symbols.js`, which only composes layers and draws five primitives (circle, line, rectangle, path,
text). Generated files are committed and CI fails if they are stale, as for tokens.

Wells are composed: `layers_for(well)` returns the layer keys, in drawing order, for one well description.
The JavaScript mirrors it and `scripts/symbols_check.py` asserts they agree on every example.
"""

from __future__ import annotations

import json
import math
import re
import tomllib
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "tokens" / "symbols.toml"
RUNTIME_JS = HERE / "runtime" / "js"

FLUIDS = ("oil", "gas", "condensate")
QUALIFIERS = ("proven", "minor", "trace")
KINDS = {"c", "C", "l", "r", "R", "p", "P", "rays", "w", "W", "t"}
PATH_RE = re.compile(r"[MLAZ]|-?\d+(?:\.\d+)?")


class SymbolError(ValueError):
    pass


def load_config() -> dict:
    with SOURCE.open("rb") as f:
        return tomllib.load(f)


def _nums(args: list[str], n: int, where: str) -> list[float]:
    if len(args) != n:
        raise SymbolError(f"{where}: expected {n} numbers, got {len(args)}")
    try:
        return [float(a) for a in args]
    except ValueError as e:
        raise SymbolError(f"{where}: {e}") from None


def _sector(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    p = lambda a: (cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a)))  # noqa: E731
    (x0, y0), (x1, y1) = p(a0), p(a1)
    large = 1 if (a1 - a0) % 360 > 180 else 0
    return f"M{cx:g} {cy:g} L{x0:.2f} {y0:.2f} A{r:g} {r:g} 0 {large} 1 {x1:.2f} {y1:.2f} Z"


def parse_part(s: str, where: str = "") -> list[dict]:
    """One drawing string to primitives. Rays become lines and sectors paths: the runtime draws five kinds."""
    dash = s.startswith("~")
    tok = s[1:] if dash else s
    kind, _, rest = tok.partition(" ")
    if kind not in KINDS:
        raise SymbolError(f"{where}: unknown primitive {kind!r} in {s!r}")
    args = rest.split()
    d = {"dash": True} if dash else {}
    if kind in ("c", "C"):
        cx, cy, r = _nums(args, 3, where)
        return [{"k": "circle", "cx": cx, "cy": cy, "r": r, "fill": kind == "C", **d}]
    if kind == "l":
        x1, y1, x2, y2 = _nums(args, 4, where)
        return [{"k": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2, **d}]
    if kind in ("r", "R"):
        x, y, w, h = _nums(args, 4, where)
        return [{"k": "rect", "x": x, "y": y, "w": w, "h": h, "fill": kind == "R", **d}]
    if kind in ("p", "P"):
        if re.sub(r"[MLAZ\s,]|-?\d+(?:\.\d+)?", "", rest):
            raise SymbolError(f"{where}: path may use absolute M, L, A, Z only: {rest!r}")
        return [{"k": "path", "d": re.sub(r"\s+", " ", rest).strip(), "fill": kind == "P", **d}]
    if kind == "rays":
        cx, cy, r0, r1, a0, da, n = _nums(args, 7, where)
        out = []
        for i in range(int(n)):
            a = math.radians(a0 + i * da)
            out.append(
                {
                    "k": "line",
                    "x1": round(cx + r0 * math.cos(a), 2),
                    "y1": round(cy + r0 * math.sin(a), 2),
                    "x2": round(cx + r1 * math.cos(a), 2),
                    "y2": round(cy + r1 * math.sin(a), 2),
                    **d,
                }
            )
        return out
    if kind in ("w", "W"):
        cx, cy, r, a0, a1 = _nums(args, 5, where)
        return [
            {
                "k": "path",
                "d": _sector(cx, cy, r, a0, a1),
                "fill": kind == "W",
                "ext": max(abs(cx), abs(cy)) + r,
                **d,
            }
        ]
    if kind == "t":
        x, y, size, *text = rest.split(" ", 3)
        return [
            {"k": "text", "x": float(x), "y": float(y), "size": float(size), "text": text[0] if text else ""}
        ]
    raise SymbolError(where)


def parse_parts(parts: list[str], where: str) -> list[dict]:
    return [p for s in parts for p in parse_part(s, f"{where}: {s}")]


def path_points(d: str) -> list[tuple[float, float]]:
    """Absolute points of a path made of M, L, A, Z (arc end points; arc extent is bounded by its radius)."""
    toks, pts, i, cmd = PATH_RE.findall(d), [], 0, ""
    while i < len(toks):
        t = toks[i]
        if t in "MLAZ":
            cmd, i = t, i + 1
            continue
        if cmd in ("M", "L"):
            pts.append((float(toks[i]), float(toks[i + 1])))
            i += 2
        elif cmd == "A":
            rx = float(toks[i])
            pts.append((float(toks[i + 5]), float(toks[i + 6])))
            pts += [
                (pts[-1][0] + rx, pts[-1][1]),
                (pts[-1][0] - rx, pts[-1][1]),
            ]  # conservative: radius around the end point
            i += 7
        else:
            raise SymbolError(f"path number without a command: {d!r}")
    return pts


def extent(prims: list[dict]) -> float:
    """Largest absolute coordinate a set of primitives reaches (for the box check)."""
    m = 0.0
    for p in prims:
        k = p["k"]
        if k == "circle":
            m = max(m, abs(p["cx"]) + p["r"], abs(p["cy"]) + p["r"])
        elif k == "line":
            m = max(m, *(abs(p[c]) for c in ("x1", "y1", "x2", "y2")))
        elif k == "rect":
            m = max(m, abs(p["x"]), abs(p["y"]), abs(p["x"] + p["w"]), abs(p["y"] + p["h"]))
        elif k == "path":
            m = max(m, p["ext"] if "ext" in p else max(max(abs(x), abs(y)) for x, y in path_points(p["d"])))
        elif k == "text":
            m = max(m, abs(p["x"]) + p["size"] / 2, abs(p["y"]) + p["size"] / 2)
    return m


def _strip(prims: list[dict]) -> list[dict]:
    return [{k: v for k, v in p.items() if k != "ext"} for p in prims]


def vocabulary(cfg: dict) -> dict:
    """What a record may say. Layer keys give it: `fluid.<f>.<q>`, `tech.<t>`, `fn.<k>`, `fn.injected.<f>`,
    `zone.<z>` and `explore.<e>`."""
    keys = list(cfg["layer"])
    pick = lambda prefix: sorted({k[len(prefix) :].split(".")[0] for k in keys if k.startswith(prefix)})  # noqa: E731
    return {
        "fluids": list(FLUIDS),
        "qualifiers": list(QUALIFIERS),
        # condensate has no "trace" form in the standard
        "qualifiers_by_fluid": {
            f: [q for q in QUALIFIERS if f"fluid.{f}.{q}" in cfg["layer"]] for f in FLUIDS
        },
        "also_fluids": ["dry", "coal"],
        "technical": ["open", *pick("tech.")],
        "functions": [k for k in pick("fn.") if k != "injected"],
        "injected_fluids": sorted(k.rsplit(".", 1)[1] for k in keys if k.startswith("fn.injected.")),
        "zones": pick("zone."),
        "exploration": pick("explore."),
        "classes": pick("class."),
        "installations": list(cfg["installation"]),
        "trajectories": list(cfg["trajectory"]),
    }


def layers_for(well: dict) -> list[str]:
    """Layer keys, in drawing order, for one well description.

    well: fluids ("dry" | "coal" | [[fluid, qualifier], ...]), technical, fn {kind, fluid}, zone, exploration,
    code, planned. Active exploration wells (wildcat, appraisal) replace the base circle with their marker.
    Fluids draw in the order oil, gas, condensate.
    """
    out = [f"explore.{well['exploration']}" if well.get("exploration") else "base"]
    fl = well.get("fluids")
    if fl == "dry":
        out.append("fluid.dry")
    elif fl == "coal":
        out.append("fluid.coal")
    elif fl:
        have = {f: q for f, q in fl}
        out += [f"fluid.{f}.{have[f]}" for f in FLUIDS if f in have]
    t = well.get("technical")
    if t and t != "open" and t != "proposed":
        out.append(f"tech.{t}")
    fn = well.get("fn")
    if fn:
        out.append(f"fn.{fn['kind']}")
        if fn["kind"] == "injection" and fn.get("fluid"):
            out.append(f"fn.injected.{fn['fluid']}")
    if well.get("zone"):
        out.append(f"zone.{well['zone']}")
    return out


def build(cfg: dict | None = None) -> dict:
    """Validate and expand the source into the data the runtime reads."""
    cfg = cfg or load_config()
    box = cfg["meta"]["box"]
    layers, errors = {}, []
    for key, v in cfg["layer"].items():
        try:
            prims = parse_parts(v["parts"], f"layer {key}")
        except SymbolError as e:
            errors.append(str(e))
            continue
        if extent(prims) > box + 0.01:
            errors.append(f"layer {key}: reaches {extent(prims):g}, outside the +-{box} box")
        layers[key] = {k: v[k] for k in ("label", "std", "simplified") if k in v} | {"parts": _strip(prims)}
    installs = {}
    for key, v in cfg["installation"].items():
        try:
            prims = parse_parts(v["parts"], f"installation {key}")
        except SymbolError as e:
            errors.append(str(e))
            continue
        if extent(prims) > box + 0.01:
            errors.append(f"installation {key}: reaches {extent(prims):g}, outside the +-{box} box")
        installs[key] = {k: v[k] for k in ("label", "std_colour", "simplified") if k in v} | {
            "parts": _strip(prims)
        }
    if errors:
        raise SymbolError("\n".join(errors))
    vocab = vocabulary(cfg)
    for ex in cfg["example"]:
        for key in layers_for(ex["well"]):
            if key not in layers:
                raise SymbolError(f"example {ex['label']!r} needs layer {key!r}, which does not exist")
    return {
        "meta": {**cfg["meta"], "source": cfg["meta"]["source"]},
        "layers": layers,
        "installations": installs,
        "trajectories": cfg["trajectory"],
        "colours": cfg["colours"]["geostandard"],
        "vocabulary": vocab,
        "examples": cfg["example"],
    }


def write(out: Path | None = None) -> list[Path]:
    """Write symbols.json and symbols-data.js (default: the packaged runtime/js)."""
    out = out or RUNTIME_JS
    out.mkdir(parents=True, exist_ok=True)
    data = build()
    text = json.dumps(data, indent=1, ensure_ascii=False)
    js = out / "symbols-data.js"
    js.write_text(
        "/* SubScout symbol data. GENERATED by `subscout symbols` from tokens/symbols.toml. Do not edit. */\n"
        f"export default {text};\n",
        encoding="utf-8",
    )
    j = out / "symbols.json"
    j.write_text(text + "\n", encoding="utf-8")
    return [js, j]
