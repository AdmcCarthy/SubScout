"""Scrolly readability check: can a reader see both the active text and its figure at every step?

Serves a built site, scrolls each scrolly sequence the way a reader does, and at the moment each step
becomes active measures what is actually on top on screen (document.elementFromPoint on a grid):

- text:   share of the active step card that is on screen and not covered          (>= 0.95)
- chart:  share of the figure's chart area not covered by a step card               (>= 0.95)
- inview: share of the chart area inside the viewport and below the top bar         (>= 0.95)
- size:   chart height as a share of the viewport height                  (>= 0.20)

Each step is judged at the best moment a reader gets while that step is active (they can stop there):
the script keeps scrolling through the step's active window and keeps the best-scoring frame.

Usage: uv run python scripts/readability.py <site_dir> [path] [--json out.json]
Exit code 1 if any step fails on any viewport.
"""

from __future__ import annotations

import functools
import http.server
import json
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = [
    ("phone-360x740", 360, 740),
    ("phone-390x844", 390, 844),
    ("phone-414x896", 414, 896),
    ("desktop-1280x800", 1280, 800),
    ("desktop-1440x900", 1440, 900),
]
LIMITS = {"text": 0.95, "chart": 0.95, "inview": 0.95, "size": 0.20}
PHONE_SIZE = 0.20

MEASURE = """
(i) => {
  const step = document.querySelectorAll('.ss-step')[i];
  const card = step.querySelector('.ss-step-card');
  const story = step.closest('.ss-story');
  const layer = story.querySelector('.ss-layer.is-on') || story.querySelector('.ss-graphic .ss-figure');
  const chart = layer && (layer.querySelector('.ss-chart'));
  const bar = document.querySelector('.ss-topbar');
  const top = bar ? bar.getBoundingClientRect().bottom : 0;
  const H = innerHeight, W = innerWidth;
  function grid(r, n = 9) {
    const pts = [];
    for (let a = 0; a < n; a++) for (let b = 0; b < n; b++)
      pts.push([r.left + (a + 0.5) * r.width / n, r.top + (b + 0.5) * r.height / n]);
    return pts;
  }
  const visible = (x, y) => x >= 0 && x < W && y >= top && y < H;
  const owner = (x, y) => document.elementFromPoint(x, y);
  // text: card points on screen whose topmost element is inside the card
  const cr = card.getBoundingClientRect();
  const tp = grid(cr);
  const text = tp.filter(([x, y]) => visible(x, y) && card.contains(owner(x, y))).length / tp.length;
  if (!chart) return { text, chart: 1, inview: 1, size: 1, nochart: true };
  const r = chart.getBoundingClientRect();
  const cp = grid(r);
  const onScreen = cp.filter(([x, y]) => visible(x, y));
  const inview = onScreen.length / cp.length;
  const covered = onScreen.filter(([x, y]) => {
    const o = owner(x, y);
    return o && o.closest('.ss-step-card');
  }).length;
  const chartOk = onScreen.length ? 1 - covered / onScreen.length : 0;
  return { text, chart: chartOk, inview, size: r.height / H, active: step.classList.contains('is-active') };
}
"""


CARD_TOP = (
    "(i) => document.querySelectorAll('.ss-step')[i]"
    ".querySelector('.ss-step-card').getBoundingClientRect().top"
)
TITLE = "(i) => (document.querySelectorAll('.ss-step')[i].querySelector('h3') || {}).textContent || ''"


def serve(directory: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def check(site: Path, path: str = "") -> list[dict]:
    srv, url = serve(site)
    rows = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, w, h in VIEWPORTS:
            pg = b.new_page(viewport={"width": w, "height": h}, reduced_motion="reduce")
            pg.goto(url + path)
            pg.wait_for_timeout(1200)
            n = pg.locator(".ss-step").count()
            lim = {**LIMITS, "size": PHONE_SIZE} if w < 761 else LIMITS
            for i in range(n):
                act = f"document.querySelectorAll('.ss-step')[{i}].classList.contains('is-active')"
                # scroll down until this step is active and its card has come on screen
                for _ in range(200):
                    if pg.evaluate(act) and pg.evaluate(CARD_TOP, i) < pg.evaluate("innerHeight"):
                        break
                    pg.mouse.wheel(0, 50)
                    pg.wait_for_timeout(25)
                best, window = None, 0
                while pg.evaluate(act) and window < 60:
                    pg.wait_for_timeout(120)
                    m = pg.evaluate(MEASURE, i)
                    score = sum(min(m.get(k, 1) / v, 1) for k, v in lim.items())
                    if best is None or score > best[0]:
                        best = (score, m)
                    if all(m.get(k, 1) >= v for k, v in lim.items()):
                        break
                    pg.mouse.wheel(0, 40)
                    window += 1
                m = best[1] if best else pg.evaluate(MEASURE, i)
                title = pg.evaluate(TITLE, i)
                fails = [k for k, v in lim.items() if m.get(k, 1) < v]
                vals = {k: round(m.get(k, 1), 2) for k in LIMITS}
                row = {"viewport": name, "step": i + 1, "title": title.strip()[:40]}
                rows.append({**row, **vals, "fail": fails})
            pg.close()
        b.close()
    srv.shutdown()
    return rows


def main(argv: list[str]) -> int:
    site = Path(argv[0])
    path = next((a for a in argv[1:] if not a.startswith("--") and not a.endswith(".json")), "")
    rows = check(site, path)
    bad = [r for r in rows if r["fail"]]
    for vp in dict.fromkeys(r["viewport"] for r in rows):
        rs = [r for r in rows if r["viewport"] == vp]
        nb = sum(bool(r["fail"]) for r in rs)
        print(f"{'FAIL' if nb else 'ok  '} {vp}: {len(rs) - nb}/{len(rs)} steps readable")
        for r in rs:
            if r["fail"]:
                vals = ", ".join(f"{k} {r[k]}" for k in LIMITS)
                print(f"       step {r['step']:>2} {r['title']!r}: {vals} -> {', '.join(r['fail'])}")
    if "--json" in argv:
        Path(argv[argv.index("--json") + 1]).write_text(json.dumps(rows, indent=1))
    print("PASS" if not bad else f"FAIL: {len(bad)} step views not readable")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
