"""Export pages and the export contract.

A chart block opts in with `export:` (true, or `{sizes: [slide, portrait, square], themes: [light, dark]}`).
The build writes, for each such figure, `export/<figure id>/`:

- `index.html`   the figure alone on a fixed artboard with header, legend and footer (source, units,
                 confidence, link) and a toolbar for size, story state, theme and units. A proof page.
- `payload.json` the **export contract** (version `CONTRACT_VERSION`): everything a renderer needs to draw the
                 figure again at any size: spec and data, story states, units, palette, surface, kicker, the
                 footer facts and credit. Schema in docs/export-contract.md.

High-resolution output (PDF, PNG at physical paper sizes, A4 to A0) is rendered by **Plate**
(github.com/AdmcCarthy/Plate: `plate render <site>`), which reads `payload.json`. SubScout no longer renders.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

SIZES = {  # artboard in CSS px; PNGs are rendered at `scale` x these
    "slide": {"label": "Slide 16:9", "w": 1600, "h": 900},
    "portrait": {"label": "Portrait 4:5", "w": 1200, "h": 1500},
    "square": {"label": "Square", "w": 1200, "h": 1200},
}
THEMES = ["light", "dark"]
CONTRACT_VERSION = 1
PREVIEW_SCALE = 3  # the proof page quotes pixel sizes at this density


def export_options(spec: dict) -> dict | None:
    e = spec.get("export")
    if not e:
        return None
    e = {} if e is True else dict(e)
    sizes = [s for s in e.get("sizes", list(SIZES)) if s in SIZES]
    themes = [t for t in e.get("themes", THEMES) if t in THEMES]
    return {"sizes": sizes or list(SIZES), "themes": themes or THEMES}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "state"


def states_for(
    fig_id: str, base_state: dict, figures: list, steps_meta: list, base_step: int | None
) -> list[dict]:
    """The figure's own state, then each `use:` step that changes it, named after that step."""

    def step_name(i: int | None, fallback: str) -> str:
        if i is None or i >= len(steps_meta):
            return fallback
        st = steps_meta[i]
        if st["attrs"].get("kicker"):
            return st["attrs"]["kicker"]
        m = re.search(r"^###\s+(.+)$", st["md"], re.M)
        return m.group(1).strip() if m else fallback

    out = [{"name": step_name(base_step, "Default"), "state": base_state}]
    for f in figures:
        if f.kind == "state" and f.spec.get("use") == fig_id:
            out.append(
                {
                    "name": step_name(f.step, f"State {len(out) + 1}"),
                    "state": {**base_state, **{k: v for k, v in f.spec.items() if k != "use"}},
                }
            )
    seen, uniq = set(), []
    for s in out:  # keep each distinct state once
        k = json.dumps(s["state"], sort_keys=True)
        if k not in seen:
            seen.add(k)
            uniq.append(
                {
                    **s,
                    "slug": slug(s["name"])
                    + (f"-{len(uniq) + 1}" if slug(s["name"]) in {u["slug"] for u in uniq} else ""),
                }
            )
    return uniq


def write_export_page(
    out: Path,
    fig,
    payload_fig: dict,
    datasets: dict,
    states: list[dict],
    opts: dict,
    fm: dict,
    sources: dict,
    credit: str,
    runtime_href: str,
) -> Path:
    spec = fig.spec
    src = sources.get(spec.get("source"), {})
    d = out / "export" / fig.id
    d.mkdir(parents=True, exist_ok=True)
    accessed = f", {src['accessed']}" if src.get("accessed") else ""
    labels = {"observed": "Observed", "derived": "Derived", "interpreted": "Interpreted"}
    facts = [("Source", f"{src.get('name', spec.get('source', ''))}{accessed}")]
    if spec.get("unit"):
        facts.append(("Units", spec["unit"]))
    facts.append(("Confidence", labels.get(spec.get("confidence"), "")))
    payload = {
        # the export contract (docs/export-contract.md); the proof page embeds the same object
        "contract": {"name": "subscout-export", "version": CONTRACT_VERSION},
        "id": fig.id,
        "story": {
            "title": fm.get("title", ""),
            "kicker": fm.get("kicker", ""),
            "palette": fm.get("palette", "tide"),
            "surface": fm.get("surface", "nordic-cool"),
            "byline": fm.get("byline", ""),
            "url": fm.get("url", ""),
        },
        "meta": {
            "title": spec.get("title", ""),
            "subtitle": spec.get("subtitle", ""),
            "source": src.get("name", spec.get("source", "")),
            "accessed": src.get("accessed", ""),
            "unit": spec.get("unit", ""),
            "confidence": spec.get("confidence", ""),
            "confidence_label": labels.get(spec.get("confidence"), ""),
            "notes": spec.get("notes", ""),
            "exception": spec.get("exception") or None,
        },
        "facts": [[k, v] for k, v in facts],
        "credit": credit,
        "runtime": runtime_href,
        "fig": payload_fig,
        "datasets": datasets,
        "states": states,
        "units": fm.get("units", "sm3"),
        "sizes": {k: SIZES[k] for k in opts["sizes"]},
        "themes": opts["themes"],
        "scale": PREVIEW_SCALE,
        "groups": fm.get("groups"),
    }
    import jinja2

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"), autoescape=False
    )
    page = env.get_template("export.html.j2").render(
        fm=fm,
        spec=spec,
        facts=facts,
        credit=credit,
        rt=f"../../{runtime_href}",
        esc=html.escape,
        plain_title=re.sub("<[^>]+>", "", spec.get("title", "")),
        payload=json.dumps(payload, ensure_ascii=False, default=str).replace("</", "<\\/"),
    )
    (d / "index.html").write_text(page, encoding="utf-8")
    (d / "payload.json").write_text(json.dumps(payload, ensure_ascii=False, default=str), encoding="utf-8")
    return d
