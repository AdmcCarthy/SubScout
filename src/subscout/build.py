"""Build a SubScout story folder (story.md + story.py + data/) into a static page.

Pipeline: front matter → data → story.py (datasets, metrics) → {{ expressions }} → blocks
(chart/table) → steps → Markdown → template → checks → output. See styleguide/story-format.md.
"""

from __future__ import annotations

import html
import importlib.util
import json
import math
import re
import shutil
import sys
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

import jinja2
import pandas as pd
import yaml
from markdown_it import MarkdownIt

from . import colour as C
from .advice import style_advice
from .layout import network_layout

PKG = Path(__file__).parent
CONFIDENCE = ("observed", "derived", "interpreted")
CONFIDENCE_ALIASES = {"reported": "observed", "estimated": "interpreted"}
# Knowledge-store grades and the reader level each becomes: the table in Idiom's house/confidence.md, read from the
# vendored copy at build time. This fallback must match it (tests/test_build.py checks).
STORE_GRADES = {
    "exact": "observed",
    "official": "observed",
    "verified": "derived",
    "published": "interpreted",
    "contested": "interpreted",
    "inferred": "interpreted",
    "placeholder": "interpreted",
}
CONFIDENCE_DOC = PKG.parent.parent / "vendor" / "idiom" / "house" / "confidence.md"
REGISTERS = ("core", "section", "outcrop")
TRUTH_GATE = {"dual-axis", "area-scaling", "source", "confidence", "lie-factor"}
CHART_TYPES = {"line", "bars", "stack", "dots", "map", "heat", "diverging", "network", "custom"}
TABLE_KINDS = {"league", "ledger"}
ARCS = {
    "abt": ["and", "but", "therefore"],
    "scqa": ["situation", "complication", "question", "answer", "support"],
    "sparkline": ["what-is", "what-could-be", "call-to-action", "new-bliss"],
    "martini": ["stem", "open"],
    "drill-down": ["overview", "instance"],
    "zoom": ["moment", "context"],
    "reveal": ["claim", "evidence", "twist"],
    "petroleum-system": ["source", "migration", "reservoir", "trap", "seal", "timing", "therefore"],
    "pre-post-drill": ["prediction", "result", "lessons"],
    "deep-time": ["rift", "burial", "uplift", "today"],
    "creaming-curve": ["early-giants", "long-tail", "whats-left"],
    "lifecycle": ["prospect", "discovery", "development", "plateau", "decline", "decommissioning"],
}


# ------------------------------------------------------------------ metrics


@dataclass
class Metric:
    value: Any
    method: str = ""
    source: str | None = None
    confidence: str = "derived"
    unit: str | None = None


def metric(
    value, method: str = "", source: str | None = None, confidence: str = "derived", unit=None
) -> Metric:
    """A number the prose may quote, with how it was obtained."""
    return Metric(_py(value), method, source, confidence, unit)


def _py(v):
    """numpy/pandas scalars → plain Python, so values serialise and compare cleanly."""
    if hasattr(v, "item"):
        try:
            return v.item()
        except (ValueError, AttributeError):
            pass
    return v


# ------------------------------------------------------------------ report


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    advice: list[str] = field(
        default_factory=list
    )  # style advice (repetition habits): shown, never fails a build

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


class BuildError(Exception):
    pass


# ------------------------------------------------------------------ loading


def split_front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, re.S)
    if not m:
        return {}, text
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def load_data(root: Path, spec: dict, report: Report) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for name, rel in (spec or {}).items():
        p = (root / rel).resolve()
        if not p.exists():
            report.error(f"data '{name}': file not found: {rel}")
            continue
        ext = p.suffix.lower()
        if ext == ".csv":
            out[name] = pd.read_csv(p)
        elif ext == ".parquet":
            out[name] = pd.read_parquet(p)
        elif ext in (".json", ".geojson"):
            obj = json.loads(p.read_text(encoding="utf-8"))
            out[name] = obj
            if isinstance(obj, dict) and obj.get("type") == "FeatureCollection":
                props = [f.get("properties") or {} for f in obj["features"]]
                if props and props[0]:
                    out[f"{name}_props"] = pd.DataFrame(props)
            elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
                out[name] = pd.DataFrame(obj)
        else:
            report.error(f"data '{name}': unsupported format {ext}")
    return out


HEADER_KEYS = {"data", "highlight", "height", "label"}


def check_header(fm: dict, data: dict, report: Report) -> dict | None:
    """The hero's header band, if the front matter asks for one.

    ``horizon: true`` keeps the procedural motif (returns ``None``). ``horizon: {data:
    name, highlight: surface, height: px, label: bool}`` names a dataset in the
    ``header`` contract (docs/header-contract.md): a dict with ``kind: header``, an
    attribution, 8-bit amplitudes and the surfaces at the section's traces. Errors go
    on the report; the dict returned feeds the template and the appendix.
    """
    spec = fm.get("horizon")
    if not isinstance(spec, dict):
        return None
    extra = set(spec) - HEADER_KEYS
    if extra:
        report.error(f"horizon: unexpected key(s) {sorted(extra)}; allowed {sorted(HEADER_KEYS)}")
    name = spec.get("data")
    if not isinstance(name, str) or name not in data:
        report.error(f"horizon: 'data' must name a dataset in the front matter data block, got {name!r}")
        return None
    P = data[name]
    if not isinstance(P, dict) or P.get("kind") != "header":
        report.error(f"horizon: dataset '{name}' is not a header export (kind: header)")
        return None
    for key in ("amp_b64", "n_traces", "n_samples", "samples", "surfaces"):
        if key not in P:
            report.error(f"horizon: dataset '{name}' lacks '{key}'")
    if not str(P.get("attribution", "")).strip():
        report.error(f"horizon: dataset '{name}' has no attribution; a real section must say whose it is")
    labels = [s.get("label") for s in P.get("surfaces") or []]
    highlight = spec.get("highlight", P.get("highlight"))
    if highlight is not None and highlight not in labels:
        report.error(f"horizon: highlight '{highlight}' is not one of the surfaces {labels}")
    height = spec.get("height", 150)
    if not isinstance(height, int) or not 80 <= height <= 400:
        report.error(f"horizon: height must be a whole number of pixels from 80 to 400, got {height!r}")
        height = 150
    dom = P.get("domain") or {}
    domain = (
        f"{'TWT' if dom.get('vertical') == 'time' else dom.get('vertical', '')} [{dom.get('vertical_unit', '')}]"
        if dom
        else ""
    )
    text = P.get("label") or ""
    return {
        "name": name,
        "highlight": highlight,
        "height": height,
        "label": bool(spec.get("label", True)),
        "text": text,
        "attribution": str(P.get("attribution", "")).strip(),
        "source_file": P.get("source_file", ""),
        "domain": domain,
        "polarity": P.get("polarity", ""),
        "aria": f"{text or 'seismic section'}. {str(P.get('attribution', '')).strip()}",
    }


def copy_header_data(root: Path, out: Path, fm: dict, header: dict | None) -> None:
    """The header export goes to the site as ``data/<name>.json``, fetched by the page
    after first paint (it is not inlined in the payload: a section is a few hundred kB)."""
    if not header:
        return
    src = (root / fm["data"][header["name"]]).resolve()
    dest = out / "data" / f"{header['name']}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def load_story_module(root: Path):
    p = root / "story.py"
    if not p.exists():
        return None
    spec = importlib.util.spec_from_file_location(f"subscout_story_{abs(hash(str(root)))}", p)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(root))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(root))
    return mod


# ------------------------------------------------------------------ number formatting


def fmt_num(v: float, digits: int = 0) -> str:
    """British number style with half-up rounding (62.5 → 63, not Python's banker's 62) and a true minus."""
    q = Decimal(str(abs(v))).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)
    return ("−" if v < 0 and q != 0 else "") + f"{q:,.{digits}f}"


def about(v: float) -> str:
    if v == 0:
        return "0"
    for div, word in ((1e9, "billion"), (1e6, "million")):
        if abs(v) >= div:
            x = v / div
            d = max(0, 1 - int(math.floor(math.log10(abs(x)))))
            return f"about {fmt_num(round(x, d), d)} {word}"
    mag = 10 ** (int(math.floor(math.log10(abs(v)))) - 1)
    return f"about {fmt_num(round(v / mag) * mag)}"


def apply_filters(
    name: str, m: Metric, filters: list[tuple[str, str | None]], report: Report
) -> tuple[str, dict]:
    """Return (display text, extra data attributes)."""
    v = m.value
    text: str | None = None
    attrs: dict[str, str] = {}
    for f, arg in filters:
        if f == "int":
            text = fmt_num(v, 0)
        elif f == "round":
            text = fmt_num(v, int(arg or 0))
        elif f == "pct":
            pv = v * 100 if abs(v) <= 1 else v
            text = f"{fmt_num(pv, int(arg or 0))}%"
        elif f == "about":
            text = about(v)
        elif f == "signed":
            text = ("+" if v > 0 else "") + fmt_num(v, int(arg or 1))
        elif f == "km":
            text = f"{text or fmt_num(v, int(arg or 0))} km"
        elif f == "km2":
            text = f"{text or fmt_num(v, int(arg or 0))} km²"
        elif f == "volume":
            scale = "M" if abs(v) >= 1e6 else ""
            attrs = {"data-ss-value": str(v), "data-ss-scale": scale, "data-ss-digits": arg or "0"}
            text = f"{fmt_num(v / (1e6 if scale else 1), int(arg or 0))}{' million' if scale else ''}"
            attrs["unit"] = "1"
        elif f in ("cite", "param"):
            pass
        else:
            report.error(f"{{{{ {name} }}}}: unknown filter '{f}'")
    if text is None:
        text = fmt_num(v, 0) if isinstance(v, int) or (isinstance(v, float) and v.is_integer()) else str(v)
        if isinstance(v, float) and not v.is_integer():
            text = fmt_num(v, 1)
    return text, attrs


def exact(v) -> str:
    """Exact value for the ledger: full precision for integers, six significant figures otherwise."""
    if isinstance(v, float) and not v.is_integer():
        return f"{v:.6g}"
    if isinstance(v, float):
        return f"{int(v):,}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


EXPR = re.compile(r"\{\{\s*(.+?)\s*\}\}")


def substitute(text: str, metrics: dict[str, Metric], used: dict, report: Report, where: str) -> str:
    def repl(mt: re.Match) -> str:
        parts = [p.strip() for p in mt.group(1).split("|")]
        name, filters = parts[0], []
        for p in parts[1:]:
            k, _, a = p.partition(":")
            filters.append((k.strip(), a.strip() or None))
        if re.fullmatch(r"-?\d[\d,.]*", name):  # literal: cited external figure or stated parameter
            cite = next((a for k, a in filters if k == "cite"), None)
            is_param = any(k == "param" for k, _ in filters)
            num = float(name.replace(",", ""))
            if is_param:
                m = Metric(num, "Threshold or definition chosen for this story", None, "parameter")
                key = f"{name} (parameter)"
            else:
                if not cite:
                    report.error(f"{where}: literal {name} needs '| cite: <source>' or '| param'")
                m = Metric(num, "Cited external figure", cite, "observed")
                key = f"{name} (cited)"
        else:
            m = metrics.get(name)
            key = name
            if m is None:
                report.error(f"{where}: unknown metric '{name}'")
                return html.escape(mt.group(0))
        shown, attrs = apply_filters(name, m, filters, report)
        used.setdefault(key, {"metric": m, "shown": []})["shown"].append(shown)
        with_unit = attrs.pop("unit", None)
        a = " ".join(f'{k}="{html.escape(v)}"' for k, v in attrs.items())
        tip = f"{key}: {exact(m.value)}{' ' + m.unit if m.unit else ''} · {m.confidence}"
        span = f'<span class="ss-n" data-ledger="{html.escape(key)}" title="{html.escape(tip)}" {a}>{shown}</span>'
        return span + (' <span data-ss-unit class="ss-unit">Sm³ o.e.</span>' if with_unit else "")

    return EXPR.sub(repl, text)


UNTRACED = re.compile(r"(?<![\w/#.\-–])(\d[\d,]*(?:\.\d+)?)(?![\w\-])")


def untraced_numbers(md: str) -> list[str]:
    """Digits in prose that are not years or identifiers."""
    clean = re.sub(r"```.*?```", "", md, flags=re.S)
    clean = EXPR.sub("", clean)
    clean = re.sub(r"\{[^}]*\}", "", clean)  # step attributes
    clean = re.sub(
        r"\b(PL|APA|TFO|Q|block|Block|quadrant|step|Step|licence|licences|EPSG:?)\s*\d+(?:/\d+)?(?:\s[A-Z]\b)?",
        "",
        clean,
    )
    months = "January|February|March|April|May|June|July|August|September|October|November|December"
    clean = re.sub(rf"\b\d{{1,2}}\s+({months})\b", "", clean)
    found = []
    for m in UNTRACED.finditer(clean):
        s = m.group(1)
        n = s.replace(",", "")
        if re.fullmatch(r"(19|20)\d\d", n):
            continue
        found.append(s)
    return found


# ------------------------------------------------------------------ blocks and steps


BLOCK = re.compile(r"^```(chart|table)\s*\n(.*?)\n```\s*$", re.S | re.M)
STEP = re.compile(r"^:::\s*step\s*(\{[^}]*\})?\s*\n(.*?)\n:::\s*$", re.S | re.M)
APPENDIX = re.compile(r"^:::\s*appendix\s*\n(.*?)\n:::\s*$", re.S | re.M)


def parse_attrs(s: str | None) -> dict:
    return {k: q or b for k, q, b in re.findall(r'(\w[\w-]*)=(?:"([^"]*)"|([\w\-]+))', s or "")}


def store_grades(doc: Path = CONFIDENCE_DOC) -> dict[str, str]:
    """Store grade → reader level, from the grade table in Idiom's confidence.md; the built-in table if it is absent."""
    try:
        text = doc.read_text(encoding="utf-8")
    except OSError:
        return dict(STORE_GRADES)
    rows = re.findall(r"^\|\s*`(\w+)`\s*\|[^|]*\|\s*(Observed|Derived|Interpreted)", text, re.M)
    return {g: lv.lower() for g, lv in rows} or dict(STORE_GRADES)


GRADES = store_grades()


def norm_conf(c: str | None) -> str | None:
    """A reader level from a level, an alias or a knowledge-store grade (`verified` → derived, `inferred` → interpreted)."""
    c = (c or "").lower() or None
    return GRADES.get(c) or CONFIDENCE_ALIASES.get(c, c)


def grade_of(c: str | None) -> str | None:
    """The store grade if `c` is one (so the page can say `placeholder`, `published`...), else None."""
    c = (c or "").lower()
    return c if c in GRADES else None


# ------------------------------------------------------------------ data preparation per chart type


def _df(data: dict, name: str, report: Report, where: str) -> pd.DataFrame | None:
    obj = data.get(name)
    if obj is None:
        report.error(f"{where}: unknown data '{name}'")
        return None
    if not isinstance(obj, pd.DataFrame):
        report.error(f"{where}: data '{name}' is not a table")
        return None
    return obj


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", force_ascii=False))


def custom_data_names(spec: dict) -> list[str]:
    d = spec.get("data")
    return [d] if isinstance(d, str) else list(d or [])


def prepare_custom(spec: dict, data: dict, report: Report, where: str) -> Any:
    """A story-supplied figure module. Checks the spec; the module itself is copied at the end of the build."""
    mod = spec.get("module")
    if not isinstance(mod, str) or not mod.endswith(".js"):
        report.error(f"{where}: custom figure needs 'module: path/to/figure.js'")
    elif Path(mod).is_absolute() or ".." in Path(mod).parts:
        report.error(f"{where}: module must be a relative path inside the story folder")
    for n in custom_data_names(spec):
        if n not in data:
            report.error(f"{where}: unknown data '{n}'")
    if not spec.get("exception") and not spec.get("notes"):
        report.warn(f"{where}: custom figure should state how it departs from the rules (exception or notes)")
    return {"datasets": custom_data_names(spec)}


def prepare(spec: dict, data: dict, report: Report, where: str) -> Any:
    t = spec["type"]
    if t == "map":
        layers = []
        for ly in spec.get("layers", []):
            if ly.get("data") not in data:
                report.error(f"{where}: unknown map layer data '{ly.get('data')}'")
            layers.append(ly)
        return {"layers": layers}
    if t == "network":
        return prepare_network(spec, data, report, where)
    if t == "custom":
        return prepare_custom(spec, data, report, where)
    df = _df(data, spec.get("data", ""), report, where)
    if df is None:
        return None
    need = {
        "line": ("x", "y", "series"),
        "stack": ("x", "y", "series"),
        "heat": ("x", "y", "value"),
        "bars": ("label", "value"),
        "dots": ("row", "value"),
        "diverging": ("label", "value"),
    }[t]
    missing = [k for k in need if k not in spec or spec[k] not in df.columns]
    if missing:
        report.error(f"{where}: {t} needs columns for {missing} (have {list(df.columns)})")
        return None
    if t in ("line", "stack"):
        xs = sorted(df[spec["x"]].unique().tolist())
        order = spec.get("series_order") or list(dict.fromkeys(df[spec["series"]].tolist()))
        series = []
        for s in order:
            sub = df[df[spec["series"]] == s].set_index(spec["x"])[spec["y"]]
            series.append(
                {"name": str(s), "vals": [_py(sub.get(x, 0)) if pd.notna(sub.get(x, 0)) else 0 for x in xs]}
            )
        return {"x": [_py(x) if t == "line" else str(_py(x)) for x in xs], "series": series}
    if t == "heat":
        cols = sorted(df[spec["x"]].unique().tolist())
        rows = spec.get("rows") or sorted(df[spec["y"]].unique().tolist())
        if rows == "data":  # keep the order rows first appear in the data
            rows = list(dict.fromkeys(df[spec["y"]].tolist()))
        piv = df.pivot_table(index=spec["y"], columns=spec["x"], values=spec["value"], aggfunc="sum").reindex(
            rows
        )
        return {
            "cols": [str(c) for c in cols],
            "rows": [str(r) for r in rows],
            "vals": [[_py(piv.loc[r, c]) if pd.notna(piv.loc[r, c]) else 0 for c in cols] for r in rows],
        }
    if t == "diverging":
        return [{"name": str(r[spec["label"]]), "val": _py(r[spec["value"]])} for r in _records(df)]
    if t == "bars":
        recs = []
        for r in _records(df):
            item = {"label": r[spec["label"]], "value": r[spec["value"]]}
            if spec.get("part"):
                item["parts"] = {p: r.get(p, 0) for p in spec["part"]}
            if spec.get("colour_by"):
                item["group"] = r.get(spec["colour_by"])
            recs.append(item)
        recs.sort(key=lambda d: -d["value"])
        return recs
    if t == "dots":
        # build each record field by field: row and colour_by may name the same column
        out_keys = {"row": spec["row"], "value": spec["value"]}
        for k, name in (("label", "label"), ("flag", "flag"), ("colour_by", "group")):
            if spec.get(k):
                out_keys[name] = spec[k]
        return [{name: r.get(col) for name, col in out_keys.items()} for r in _records(df)]
    return None


def prepare_network(spec: dict, data: dict, report: Report, where: str) -> Any:
    """Nodes and edges per frame, with build-time layout (see layout.py)."""
    nd = _df(data, spec.get("data", ""), report, where)
    ed = _df(data, spec.get("edges", ""), report, where + " edges")
    if nd is None or ed is None:
        return None
    fk, nk, sk = spec.get("frame"), spec.get("node", "id"), spec.get("size")
    wk = spec.get("weight")
    missing = [k for k, c in (("frame", fk), ("node", nk), ("size", sk)) if not c or c not in nd.columns]
    missing += [f"edges.{c}" for c in (fk, "a", "b", wk) if not c or c not in ed.columns]
    if missing:
        report.error(
            f"{where}: network needs columns for {missing} (nodes have {list(nd.columns)}, edges {list(ed.columns)})"
        )
        return None
    frames = spec.get("frames") or sorted(nd[fk].unique().tolist())
    frames = [str(_py(f)) for f in frames]
    extra = [c for c in (spec.get("tooltip") or []) if c in nd.columns]
    cb = spec.get("colour_by")
    nodes, edges = {}, {}
    for fr in frames:
        sub = nd[nd[fk].astype(str) == fr]
        nodes[fr] = [
            {
                "id": str(r[nk]),
                "size": _py(r[sk]),
                **({"group": r.get(cb)} if cb else {}),
                **{c: r.get(c) for c in extra},
            }
            for r in _records(sub)
        ]
        es = ed[ed[fk].astype(str) == fr]
        edges[fr] = [{"a": str(r["a"]), "b": str(r["b"]), "w": _py(r[wk])} for r in _records(es)]
    pos = network_layout(
        frames, nodes, edges, aspect=float(spec.get("aspect", 1.5)), rmax=float(spec.get("node_scale", 0.04))
    )
    for fr in frames:
        for d in nodes[fr]:
            d["x"], d["y"] = pos[fr][d["id"]]
    return {"frames": frames, "nodes": nodes, "edges": edges}


def table_html(spec: dict, data: dict, report: Report, where: str) -> str:
    df = _df(data, spec.get("data", ""), report, where)
    if df is None:
        return ""
    cols = spec.get("columns") or [{"field": c} for c in df.columns]
    for c in cols:
        if c["field"] not in df.columns:
            report.error(f"{where}: table column '{c['field']}' not in data")
            return ""
    sort = spec.get("sort")
    if sort:
        key = sort.lstrip("-")
        df = df.sort_values(key, ascending=not sort.startswith("-"), kind="stable")
    hl = spec.get("highlight") or {}
    fold = int(spec.get("fold") or 0)
    maxes = {c["field"]: float(df[c["field"]].abs().max() or 1) for c in cols if c.get("bar")}
    head = "".join(
        f'<th scope="col" data-field="{c["field"]}" class="{"num" if pd.api.types.is_numeric_dtype(df[c["field"]]) else ""}"'
        f' aria-sort="{"descending" if sort == "-" + c["field"] else "ascending" if sort == c["field"] else "none"}">'
        f"{html.escape(c.get('label', c['field']))}{' <small>' + html.escape(c['unit']) + '</small>' if c.get('unit') else ''}</th>"
        for c in cols
    )
    rows = []
    for i, r in enumerate(_records(df)):
        is_hl = any(r.get(k) == v or (isinstance(v, list) and r.get(k) in v) for k, v in hl.items())
        cells = []
        for c in cols:
            val = r.get(c["field"])
            if c.get("format") in ("int", "round1", "round2") and isinstance(val, (int, float)):
                d = {"int": 0, "round1": 1, "round2": 2}[c["format"]]
                shown = fmt_num(val, d)
                num = True
            else:
                shown = "" if val is None else html.escape(str(val))
                num = isinstance(val, (int, float))
            bar = ""
            if c.get("bar") and isinstance(val, (int, float)):
                w = 100 * abs(val) / maxes[c["field"]]
                bar = f'<span class="ss-tbar" style="width:{w:.1f}%"></span>'
            cells.append(
                f'<td class="{"num" if num else ""}" data-v="{html.escape(str(val))}">{bar}<span>{shown}</span></td>'
            )
        cls = " ".join(x for x in ("is-hl" if is_hl else "", "is-folded" if fold and i >= fold else "") if x)
        rows.append(f'<tr class="{cls}">{"".join(cells)}</tr>')
    more = (
        f'<button class="ss-fold" type="button" data-fold="{fold}">Show all {len(df)}</button>'
        if fold and len(df) > fold
        else ""
    )
    cap = html.escape(spec.get("title", ""))
    return (
        f'<div class="ss-table-wrap"><table class="ss-table" data-kind="{spec.get("kind", "league")}">'
        f'<caption class="ss-visually-hidden">{cap}</caption><thead><tr>{head}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>{more}</div>"
    )


# ------------------------------------------------------------------ build


@dataclass
class Figure:
    id: str
    spec: dict
    kind: str  # chart | table
    step: int | None = None
    payload: Any = None
    html: str = ""


def write_exports(out, figures, figs_payload, data, steps_meta, fm, sources, runtime_href, report) -> None:
    """Export pages for figures that opt in with `export:` (see export.py)."""
    from . import export as ex

    for f in figures:
        if f.kind != "chart":
            continue
        opts = ex.export_options(f.spec)
        if not opts:
            continue
        names = (
            custom_data_names(f.spec)
            if f.spec.get("type") == "custom"
            else [ly["data"] for ly in f.spec.get("layers", [])]
        )
        datasets = {
            n: (_records(data[n]) if isinstance(data[n], pd.DataFrame) else data[n])
            for n in names
            if n in data
        }
        base = (
            {k: v for k, v in (f.spec.get("state") or {}).items()}
            if f.spec.get("type") == "custom"
            else {
                k: f.spec[k]
                for k in ("focus", "note", "highlight", "sort", "view", "filter", "frame")
                if k in f.spec
            }
        )
        states = ex.states_for(f.id, base, figures, steps_meta, f.step)
        credit = " · ".join(x for x in [fm.get("byline"), fm.get("url")] if x)
        ex.write_export_page(
            out, f, figs_payload[f.id], datasets, states, opts, fm, sources, credit, runtime_href
        )


def copy_custom_modules(root: Path, out: Path, figures: list, report: Report) -> None:
    """Copy each custom figure's module folder (so modules can import siblings) into the site."""
    done: set[Path] = set()
    for f in figures:
        if f.kind != "chart" or f.spec.get("type") != "custom" or not isinstance(f.spec.get("module"), str):
            continue
        rel = Path(f.spec["module"])
        src = (root / rel).resolve()
        if not src.is_file() or root not in src.parents:
            report.error(f"figure {f.id}: module '{rel}' not found in the story folder")
            continue
        top = rel.parts[0] if len(rel.parts) > 1 else None
        if top is None:
            shutil.copy2(src, out / rel)
        elif top not in done:
            shutil.copytree(root / top, out / top, dirs_exist_ok=True)
            done.add(top)


def _no_nan(o):
    if isinstance(o, float) and (o != o or o in (float("inf"), float("-inf"))):
        return None
    if isinstance(o, dict):
        return {k: _no_nan(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_no_nan(v) for v in o]
    return o


def payload_json(obj: dict, report: Report) -> str:
    """Serialise the page payload. NaN and infinity are not valid JSON in the browser: they become null,
    with a warning so the data can be fixed at source."""
    try:
        text = json.dumps(obj, ensure_ascii=False, default=_py, allow_nan=False)
    except ValueError:
        report.warn("page data contained NaN or infinity; written as null (fix it in the data or story.py)")
        text = json.dumps(
            _no_nan(json.loads(json.dumps(obj, ensure_ascii=False, default=_py))), ensure_ascii=False
        )
    return text.replace("</", "<\\/")


def build(root: Path, out: Path, runtime_href: str = "runtime") -> Report:
    root, out = Path(root).resolve(), Path(out).resolve()
    report = Report()
    text = (root / "story.md").read_text(encoding="utf-8")
    fm, body = split_front_matter(text)
    for k in ("title", "sources"):
        if not fm.get(k):
            report.error(f"front matter: '{k}' is required")
    sources = fm.get("sources") or {}
    register = fm.get("register", "section")
    if register not in REGISTERS:
        report.error(f"front matter: register '{register}' not one of {REGISTERS}")
    cfg = C.load_config()
    if fm.get("palette", "tide") not in cfg["presets"]:
        report.error(f"front matter: unknown palette '{fm.get('palette')}'")
    if fm.get("surface", cfg["surfaces"]["default"]) not in cfg["surfaces"]:
        report.error(f"front matter: unknown surface '{fm.get('surface')}'")

    data = load_data(root, fm.get("data"), report)
    header = check_header(fm, data, report)
    mod = load_story_module(root)
    if mod and hasattr(mod, "datasets"):
        data.update(mod.datasets(data) or {})
    metrics: dict[str, Metric] = {}
    if mod and hasattr(mod, "metrics"):
        metrics = {
            k: (v if isinstance(v, Metric) else metric(v)) for k, v in (mod.metrics(data) or {}).items()
        }
    for k, m in metrics.items():
        if grade_of(m.confidence) == "placeholder":
            report.warn(
                f"metric '{k}': a placeholder waits for data; keep it out of headline figures and KPIs"
            )
        m.confidence = norm_conf(m.confidence) or "derived"
        if m.confidence not in CONFIDENCE:
            report.error(f"metric '{k}': confidence '{m.confidence}' invalid")
        if m.source and m.source not in sources:
            report.error(f"metric '{k}': source '{m.source}' not in front matter sources")

    # untraced numbers (before substitution)
    nums = untraced_numbers(body)
    if nums:
        report.warn(
            f"{len(nums)} untraced number(s) in prose: {', '.join(nums[:12])}{' …' if len(nums) > 12 else ''}"
        )

    used: dict = {}
    # appendix content
    extra_appendix = "\n\n".join(m.group(1) for m in APPENDIX.finditer(body))
    body = APPENDIX.sub("", body)

    figures: list[Figure] = []
    by_id: dict[str, Figure] = {}

    def take_blocks(chunk: str, step_index: int | None) -> tuple[str, list[str]]:
        ids = []

        def repl(m: re.Match) -> str:
            kind = m.group(1)
            where = f"{kind} block {len(figures) + 1}"
            try:
                spec = yaml.safe_load(m.group(2)) or {}
            except yaml.YAMLError as e:
                report.error(f"{where}: YAML error: {e}")
                return ""
            for key in ("title", "subtitle", "notes"):
                if isinstance(spec.get(key), str):
                    spec[key] = substitute(spec[key], metrics, used, report, where)
            if "use" in spec:
                base = by_id.get(spec["use"])
                if not base:
                    report.error(f"{where}: use '{spec['use']}' refers to no earlier chart")
                    return ""
                fid = f"{spec['use']}@{len(figures)}"
                fig = Figure(fid, spec, "state", step_index)
                figures.append(fig)
                ids.append(fid)
                return ""
            fid = spec.get("id") or f"fig{len(figures) + 1}"
            if grade_of(spec.get("confidence")) == "placeholder":
                report.warn(
                    f"{where} ({fid}): a placeholder waits for data; label it so and keep it out of headlines"
                )
            spec["confidence"] = norm_conf(spec.get("confidence"))
            if not spec.get("title"):
                report.error(f"{where} ({fid}): an action title is required")
            if not spec.get("source"):
                report.error(f"{where} ({fid}): source is required")
            elif spec["source"] not in sources:
                report.error(f"{where} ({fid}): source '{spec['source']}' not in front matter")
            if spec["confidence"] not in CONFIDENCE:
                report.error(f"{where} ({fid}): confidence must be one of {CONFIDENCE}")
            if spec.get("register") and spec["register"] not in REGISTERS:
                report.error(f"{where} ({fid}): register '{spec['register']}' invalid")
            exc = spec.get("exception")
            if exc:
                if exc.get("rule") in TRUTH_GATE:
                    report.error(
                        f"{where} ({fid}): '{exc.get('rule')}' is a truth-gate rule and cannot be excepted"
                    )
                if not exc.get("reason"):
                    report.error(f"{where} ({fid}): an exception needs a reason")
            if kind == "chart":
                if spec.get("type") not in CHART_TYPES:
                    report.error(f"{where} ({fid}): type must be one of {sorted(CHART_TYPES)}")
                    return ""
                fig = Figure(fid, spec, "chart", step_index, prepare(spec, data, report, f"{where} ({fid})"))
            else:
                if spec.get("kind", "league") not in TABLE_KINDS:
                    report.error(f"{where} ({fid}): kind must be one of {sorted(TABLE_KINDS)}")
                fig = Figure(
                    fid, spec, "table", step_index, html=table_html(spec, data, report, f"{where} ({fid})")
                )
            figures.append(fig)
            by_id[fid] = fig
            ids.append(fid)
            return f"\n\n<!--SSFIG:{fid}-->\n\n" if step_index is None else ""

        return BLOCK.sub(repl, chunk), ids

    md = MarkdownIt("commonmark", {"html": True, "typographer": True}).enable("table")

    # walk the body: alternate prose and runs of consecutive steps
    sections: list[dict] = []
    pos = 0
    steps_meta: list[dict] = []
    beats: list[str] = []
    for m in STEP.finditer(body):
        before = body[pos : m.start()]
        if before.strip():
            sections.append({"kind": "prose", "md": take_blocks(before, None)[0]})
        attrs = parse_attrs(m.group(1))
        if attrs.get("beat"):
            beats.append(attrs["beat"])
        idx = len(steps_meta)
        content, ids = take_blocks(m.group(2), idx)
        step = {"index": idx, "attrs": attrs, "md": content, "figs": ids}
        steps_meta.append(step)
        if sections and sections[-1]["kind"] == "scrolly" and not before.strip():
            sections[-1]["steps"].append(step)
        else:
            sections.append({"kind": "scrolly", "steps": [step]})
        pos = m.end()
    if body[pos:].strip():
        sections.append({"kind": "prose", "md": take_blocks(body[pos:], None)[0]})
    report.advice.extend(style_advice(body))

    # render
    for s in sections:
        if s["kind"] == "prose":
            chunk = substitute(s["md"], metrics, used, report, "prose")
            h = md.render(chunk)
            for f in figures:
                h = h.replace(f"<!--SSFIG:{f.id}-->", f'<div class="ss-inline-fig" data-fig="{f.id}"></div>')
            s["html"] = h
        else:
            for st in s["steps"]:
                st["html"] = md.render(substitute(st["md"], metrics, used, report, f"step {st['index'] + 1}"))
                if not st["figs"]:
                    report.warn(f"step {st['index'] + 1} has no chart; it will keep the previous view")
            s["figs"] = list(dict.fromkeys(f.split("@")[0] for st in s["steps"] for f in st["figs"]))

    # arc check
    arc = fm.get("arc")
    if arc:
        if arc not in ARCS:
            report.error(f"front matter: unknown arc '{arc}' (one of {sorted(ARCS)})")
        else:
            expected = ARCS[arc]
            missing = [b for b in expected if b not in beats and b not in ("support", "instance", "open")]
            unknown = [b for b in beats if b not in expected]
            if missing:
                report.warn(f"arc '{arc}': missing beat(s) {missing}")
            if unknown:
                report.warn(f"arc '{arc}': beat(s) {unknown} are not part of this arc")
            order = [expected.index(b) for b in beats if b in expected]
            if order != sorted(order):
                report.warn(f"arc '{arc}': beats out of order: {beats}")

    appendix_html = (
        md.render(substitute(extra_appendix, metrics, used, report, "appendix")) if extra_appendix else ""
    )

    # KPIs
    kpis = []
    for k in fm.get("kpis") or []:
        extra = set(k) - {"metric", "label", "filter"}
        if extra:
            report.error(
                f"kpis: unexpected key(s) {sorted(extra)} for '{k.get('metric')}' (quote labels that contain commas)"
            )
        m = metrics.get(k.get("metric"))
        if not m:
            report.error(f"kpis: unknown metric '{k.get('metric')}'")
            continue
        shown = substitute(
            "{{ " + k["metric"] + (" | " + k["filter"] if k.get("filter") else "") + " }}",
            metrics,
            used,
            report,
            "kpis",
        )
        kpis.append({"html": shown, "label": k.get("label", "")})

    if report.errors:
        return report

    # payload
    used_data: set[str] = set()
    figs_payload = {}
    for f in figures:
        if f.kind == "chart":
            figs_payload[f.id] = {"spec": f.spec, "data": f.payload}
            if f.spec.get("type") == "map":
                used_data |= {ly["data"] for ly in f.spec.get("layers", [])}
            if f.spec.get("type") == "custom":
                used_data |= set(custom_data_names(f.spec))
        elif f.kind == "state":
            figs_payload[f.id] = {
                "use": f.spec["use"],
                "state": {k: v for k, v in f.spec.items() if k != "use"},
            }
    datasets = {n: (_records(data[n]) if isinstance(data[n], pd.DataFrame) else data[n]) for n in used_data}
    steps_payload = [{"figs": st["figs"]} for st in steps_meta]

    ledger = [
        {
            "name": k,
            "value": exact(u["metric"].value),
            "unit": u["metric"].unit,
            "shown": sorted(set(u["shown"])),
            "method": u["metric"].method,
            "source": u["metric"].source,
            "confidence": u["metric"].confidence,
        }
        for k, u in used.items()
    ]
    unused = sorted(set(metrics) - set(used))
    if unused:
        report.warn(f"metrics defined but not used: {', '.join(unused)}")
    figure_list = [
        {
            "id": f.id,
            "kind": f.kind,
            "title": re.sub("<[^>]+>", "", f.spec.get("title", "")),
            "type": f.spec.get("type") or f.spec.get("kind"),
            "source": f.spec.get("source"),
            "confidence": f.spec.get("confidence"),
            "notes": f.spec.get("notes"),
            "exception": f.spec.get("exception"),
        }
        for f in figures
        if f.kind in ("chart", "table")
    ]

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(PKG / "templates"), autoescape=False)
    tpl = env.get_template("story.html.j2")
    ctx = dict(
        fm=fm,
        header=header,
        sections=sections,
        figures={f.id: f for f in figures},
        kpis=kpis,
        sources=sources,
        ledger=ledger,
        figure_list=figure_list,
        extra_appendix=appendix_html,
        arc=arc,
        arc_beats=ARCS.get(arc, []),
        register=register,
        runtime=runtime_href,
        palette=fm.get("palette", "tide"),
        surface=fm.get("surface", cfg["surfaces"]["default"]),
        has_scrolly=any(s["kind"] == "scrolly" for s in sections),
        payload=payload_json(
            {
                "figures": figs_payload,
                "datasets": datasets,
                "steps": steps_payload,
                "units": fm.get("units", "sm3"),
                "groups": fm.get("groups"),
            },
            report,
        ),
        esc=html.escape,
        conf_label={
            "observed": "Observed",
            "derived": "Derived",
            "interpreted": "Interpreted",
            "parameter": "Parameter",
        },
    )
    macros = tpl.make_module(ctx)
    for s in sections:
        if s["kind"] == "prose":
            for f in figures:
                ph = f'<div class="ss-inline-fig" data-fig="{f.id}"></div>'
                if ph in s["html"]:
                    s["html"] = s["html"].replace(ph, f'<div class="ss-inline-fig">{macros.figure(f)}</div>')
    page = tpl.render(**ctx)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    copy_custom_modules(root, out, figures, report)
    copy_header_data(root, out, fm, header)
    write_exports(out, figures, figs_payload, data, steps_meta, fm, sources, runtime_href, report)
    if runtime_href == "runtime":
        from . import tokens

        tokens.write()
        if (out / "runtime").exists():
            shutil.rmtree(out / "runtime")
        shutil.copytree(PKG / "runtime", out / "runtime")
    (out / ".nojekyll").touch()
    (out / "build-report.json").write_text(
        json.dumps(
            {
                "errors": report.errors,
                "warnings": report.warnings,
                "advice": report.advice,
                "ledger": ledger,
                "figures": figure_list,
            },
            indent=1,
            ensure_ascii=False,
            default=_py,
        ),
        encoding="utf-8",
    )
    return report
