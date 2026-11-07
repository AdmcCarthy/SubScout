"""Export pages: a figure on its own, on a fixed artboard, for high-resolution image export.

A chart block opts in with `export:` (true, or `{sizes: [slide, portrait, square], themes: [light, dark]}`).
The build writes `export/<figure id>/index.html`: the figure alone with a header, legend and footer
(source, units, confidence, link), a toolbar to pick size, story state, theme and units, and download links
for pre-rendered PNGs. `subscout export <site>` renders those PNGs in headless Chromium at 3x pixel
density (a 1600 x 900 slide becomes 4800 x 2700) and lists them in `renders.json`.
"""

from __future__ import annotations

import functools
import html
import http.server
import json
import re
import threading
from pathlib import Path
from typing import Any

SIZES = {  # artboard in CSS px; PNGs are rendered at `scale` x these
    "slide": {"label": "Slide 16:9", "w": 1600, "h": 900},
    "portrait": {"label": "Portrait 4:5", "w": 1200, "h": 1500},
    "square": {"label": "Square", "w": 1200, "h": 1200},
}
THEMES = ["light", "dark"]
SCALE = 3


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
    payload = {
        "fig": payload_fig,
        "datasets": datasets,
        "states": states,
        "units": fm.get("units", "sm3"),
        "sizes": {k: SIZES[k] for k in opts["sizes"]},
        "themes": opts["themes"],
        "scale": SCALE,
        "groups": fm.get("groups"),
    }
    accessed = f", {src['accessed']}" if src.get("accessed") else ""
    labels = {"observed": "Observed", "derived": "Derived", "interpreted": "Interpreted"}
    facts = [("Source", f"{src.get('name', spec.get('source', ''))}{accessed}")]
    if spec.get("unit"):
        facts.append(("Units", spec["unit"]))
    facts.append(("Confidence", labels.get(spec.get("confidence"), "")))
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
    if not (d / "renders.json").exists():
        (d / "renders.json").write_text("[]")  # filled by `subscout export`
    return d


# ---------------------------------------------------------------------------- rendering (Playwright)


def _serve(directory: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:
            pass

    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def render(site: Path, scale: int = SCALE, only: list[str] | None = None) -> list[Path]:
    """Render every export page x size x state x theme to PNG; write renders.json beside each page."""
    from playwright.sync_api import sync_playwright

    pages = sorted(p.parent for p in (site / "export").glob("*/index.html"))
    if only:
        pages = [p for p in pages if p.name in only]
    srv, url = _serve(site)
    written: list[Path] = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for d in pages:
                text = (d / "index.html").read_text(encoding="utf-8")
                payload = json.loads(
                    text.split('id="ss-payload">')[1].split("</script>")[0].replace("<\\/", "</")
                )
                (d / "png").mkdir(exist_ok=True)
                renders = []
                for size, dim in payload["sizes"].items():
                    for theme in payload["themes"]:
                        ctx = b.new_context(
                            viewport={"width": dim["w"], "height": dim["h"]}, device_scale_factor=scale
                        )
                        pg = ctx.new_page()
                        for i, st in enumerate(payload["states"]):
                            pg.goto(f"{url}export/{d.name}/?bare=1&size={size}&state={i}&theme={theme}")
                            pg.wait_for_function("document.body.dataset.ready === '1'", timeout=30000)
                            name = f"{size}-{theme}-{st['slug']}.png"
                            pg.locator("#board").screenshot(path=str(d / "png" / name))
                            renders.append(
                                {
                                    "size": size,
                                    "theme": theme,
                                    "state": i,
                                    "file": f"png/{name}",
                                    "px": [dim["w"] * scale, dim["h"] * scale],
                                }
                            )
                            written.append(d / "png" / name)
                        ctx.close()
                (d / "renders.json").write_text(json.dumps(renders, indent=1))
            b.close()
    finally:
        srv.shutdown()
    return written
