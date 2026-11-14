"""The fit gate of deck mode: every slide of a built deck holds on one screen.

`subscout fit <site>` serves the built site, visits every slide of every category page at each screen size and
fails when text overflows its box, the page scrolls, a figure does not draw or is taller than its box, or the
console reports an error. A slide's text steps down in size to fit (to a floor of 0.8); slides that needed
more than a little of that are listed, as the ones to shorten. Needs Playwright (a development dependency) and uses
its Chromium, or the installed Chrome when that is not there.
"""

from __future__ import annotations

import functools
import http.server
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

SIZES = ("1366x768", "1600x900", "1920x1080")
SMALL = 0.88  # text stepped down below this share of its size is reported

PROBE = """() => {
  const slide = document.getElementById('slide'), prose = document.getElementById('prose');
  const on = document.querySelector('.fig-layer.on');
  const svg = on && on.querySelector('svg, canvas');
  const box = svg && svg.getBoundingClientRect();
  const chart = on && on.querySelector('.ss-chart').getBoundingClientRect();
  return {
    layout: slide.dataset.layout,
    overflow: prose.scrollHeight > prose.clientHeight + 1 || prose.scrollWidth > prose.clientWidth + 1,
    fs: prose.style.getPropertyValue('--fs') || '1',
    page: document.documentElement.scrollHeight > window.innerHeight + 1,
    fig: on ? (box ? [Math.round(box.width), Math.round(box.height)] : null) : 'none',
    spill: box && chart ? box.height > chart.height + 2 || box.width > chart.width + 2 : false,
  };
}"""


@dataclass
class Result:
    slides: int = 0
    problems: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    small: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems and not self.errors


def serve(directory: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def parse_range(text: str | None, n: int) -> list[int]:
    """'1,5-9' as slide numbers within 1..n; nothing given means every slide."""
    if not text:
        return list(range(1, n + 1))
    out: list[int] = []
    for part in text.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    return [s for s in out if 1 <= s <= n]


def _launch(p, channel: str | None):
    if channel:
        return p.chromium.launch(channel=channel)
    try:
        return p.chromium.launch()
    except Exception:  # Playwright's own Chromium is not installed: the machine's Chrome will do
        return p.chromium.launch(channel="chrome")


def check(
    site: Path,
    sizes: tuple[str, ...] = SIZES,
    pages: list[str] | None = None,
    slides: str | None = None,
    dark: bool = False,
    shots: Path | None = None,
    wait: int = 1100,
    channel: str | None = None,
) -> Result:
    """Visit the slides of the deck built at `site`. Screenshots go to `shots`, one folder per size if several."""
    from playwright.sync_api import sync_playwright

    site = Path(site)
    report = json.loads((site / "build-report.json").read_text(encoding="utf-8"))
    if report.get("mode") != "deck":
        raise ValueError(f"{site} is not a deck (build-report.json has mode '{report.get('mode')}')")
    todo = [pg for pg in report["pages"] if not pages or pg["slug"] in pages]
    res = Result()
    # a deck built beside a shared runtime (runtime_href "../runtime") is served from the folder that holds both
    shared = not (site / "runtime").exists() and (site.parent / "runtime").exists()
    srv, url = serve(site.parent if shared else site)
    if shared:
        url += f"{site.name}/"
    try:
        with sync_playwright() as p:
            browser = _launch(p, channel)
            for size in sizes:
                w, h = (int(v) for v in size.split("x"))
                errors: list[str] = []
                page = browser.new_page(
                    viewport={"width": w, "height": h}, color_scheme="dark" if dark else "light"
                )
                page.on("console", lambda m, e=errors: m.type == "error" and e.append(m.text))
                page.on("pageerror", lambda x, e=errors: e.append(str(x)))
                page.on("response", lambda r, e=errors: r.status >= 400 and e.append(f"{r.status} {r.url}"))
                folder = None
                if shots:
                    folder = Path(shots) / size if len(sizes) > 1 else Path(shots)
                    folder.mkdir(parents=True, exist_ok=True)
                pre = "dark-" if dark else ""
                if not pages:
                    for name in ("index", "basis"):
                        page.goto(f"{url}{name}.html", wait_until="networkidle")
                        page.wait_for_timeout(500)
                        if folder:
                            page.screenshot(path=str(folder / f"{pre}{name}.png"), full_page=name == "index")
                for pg in todo:
                    page.goto(f"{url}{pg['slug']}.html", wait_until="networkidle")
                    page.wait_for_timeout(600)
                    for s in parse_range(slides, pg["slides"]):
                        # arrive as a reader does where possible: one press of the arrow from the slide before
                        at = page.evaluate("() => parseInt(location.hash.slice(1) || '1', 10)")
                        if s == at + 1:
                            page.keyboard.press("ArrowRight")
                        elif s != at:
                            page.evaluate(f"() => {{ location.hash = '#{s}'; }}")
                        page.wait_for_timeout(wait)
                        r = page.evaluate(PROBE)
                        res.slides += 1
                        tag = f"{pg['slug']} {s:02d} at {size}"
                        if r["overflow"]:
                            res.problems.append(
                                f"{tag}: text overflows its box (master {r['layout']}, size factor {r['fs']})"
                            )
                        elif float(r["fs"]) < SMALL:
                            res.small.append(f"{pg['slug']} {s:02d} ({r['fs']} at {size})")
                        if r["page"]:
                            res.problems.append(f"{tag}: the page scrolls")
                        if r["fig"] is None:
                            res.problems.append(f"{tag}: the figure did not draw")
                        if r["spill"]:
                            res.problems.append(f"{tag}: the figure is larger than its box ({r['fig']})")
                        if folder:
                            page.screenshot(path=str(folder / f"{pre}{pg['slug']}-{s:02d}.png"))
                page.close()
                # a 404 with no failed page response is the browser asking for a favicon
                if not any(e[:3].isdigit() for e in errors):
                    errors = [e for e in errors if "Failed to load resource" not in e]
                res.errors += [f"{size}: {e}" for e in errors]
            browser.close()
    finally:
        srv.shutdown()
    return res
