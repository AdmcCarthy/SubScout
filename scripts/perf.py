"""Performance gate: scroll a built story and step through Present mode with the CPU throttled,
recording Long Animation Frames (LoAF) and requestAnimationFrame deltas.

Usage: uv run python scripts/perf.py <site_dir> <path> [--rate 4] [--json out.json]
Fails (exit 1) if any long animation frame exceeds MAX_LOAF_MS or the p95 frame exceeds P95_MS.
Budgets come from styleguide/performance.md.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import statistics
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

MAX_LOAF_MS = 50.0  # during animation and scrolling
MAX_INTERACTION_MS = 200.0  # a discrete action (entering Present mode), like INP
P95_MS = 16.7 * 1.25  # headless frame pacing jitters; 20.9 ms ≈ 48 fps floor at p95

OBSERVER = """
window.__perf = { loaf: [], frames: [], on: false };
try {
  new PerformanceObserver((l) => { if (window.__perf.on) for (const e of l.getEntries())
    window.__perf.loaf.push({ d: e.duration, block: e.blockingDuration,
      scripts: (e.scripts || []).slice(0, 3).map((s) => `${s.sourceFunctionName || ''} ${s.sourceURL || ''}:${s.sourceCharPosition}`) }); })
    .observe({ type: 'long-animation-frame', buffered: false });
} catch (e) { window.__perf.noLoaf = true; }
let last = performance.now();
(function tick(t) { if (window.__perf.on) window.__perf.frames.push(t - last); last = t; requestAnimationFrame(tick); })(last);
"""


def serve(directory: Path):
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def p95(xs: list[float]) -> float:
    return statistics.quantiles(xs, n=20)[-1] if len(xs) >= 20 else max(xs or [0])


def run(site: Path, path: str, rate: float) -> dict:
    srv, url = serve(site)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 860})
        page.add_init_script(OBSERVER)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url + path, wait_until="networkidle")
        page.wait_for_timeout(800)
        cdp = page.context.new_cdp_session(page)
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": rate})
        page.evaluate("window.__perf.on = true")
        # Read mode: scroll the whole story in small increments
        height = page.evaluate("document.documentElement.scrollHeight")
        y = 0
        while y < height:
            page.mouse.wheel(0, 240)
            page.wait_for_timeout(60)
            y += 240
        page.wait_for_timeout(800)
        read = page.evaluate("({loaf: window.__perf.loaf.splice(0), frames: window.__perf.frames.splice(0)})")
        # Present mode: step through every slide
        present = {"loaf": [], "frames": []}
        enter = []
        if page.locator("#present-btn").count():
            page.evaluate("window.scrollTo(0, 0)")
            page.click("#present-btn")
            page.wait_for_timeout(600)
            enter = page.evaluate("window.__perf.loaf.splice(0).map((x) => x.d)")
            page.evaluate("window.__perf.frames.splice(0)")
            for _ in range(page.locator(".ss-step").count()):
                page.keyboard.press("ArrowRight")
                page.wait_for_timeout(1400)
            present = page.evaluate(
                "({loaf: window.__perf.loaf.splice(0), frames: window.__perf.frames.splice(0)})"
            )
        no_loaf = page.evaluate("!!window.__perf.noLoaf")
        browser.close()
    srv.shutdown()

    def summarise(m):
        loaf = [x["d"] for x in m["loaf"]]
        return {
            "frames": len(m["frames"]),
            "p95_frame_ms": round(p95(m["frames"]), 1),
            "max_frame_ms": round(max(m["frames"] or [0]), 1),
            "long_frames": len(loaf),
            "max_loaf_ms": round(max(loaf or [0]), 1),
            "worst": sorted(m["loaf"], key=lambda x: -x["d"])[:3],
        }

    return {
        "path": path,
        "cpu_rate": rate,
        "read": summarise(read),
        "present": summarise(present),
        "enter_present_ms": round(max(enter or [0]), 1),
        "errors": errors,
        "loaf_supported": not no_loaf,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("site")
    ap.add_argument("path", nargs="?", default="")
    ap.add_argument("--rate", type=float, default=4)
    ap.add_argument("--json")
    a = ap.parse_args()
    r = run(Path(a.site), a.path, a.rate)
    if a.json:
        Path(a.json).write_text(json.dumps(r, indent=1))
    ok = not r["errors"]
    for mode in ("read", "present"):
        m = r[mode]
        bad = m["max_loaf_ms"] > MAX_LOAF_MS or m["p95_frame_ms"] > P95_MS
        ok &= not bad
        print(
            f"{'FAIL' if bad else 'ok  '} {mode:7} p95 frame {m['p95_frame_ms']} ms (budget {P95_MS:.1f}), "
            f"max frame {m['max_frame_ms']} ms, long frames {m['long_frames']} (max {m['max_loaf_ms']} ms, budget {MAX_LOAF_MS})"
        )
        for w in m["worst"] if bad else []:
            print(f"       {w['d']:.0f} ms: {'; '.join(w['scripts'])}")
    bad = r["enter_present_ms"] > MAX_INTERACTION_MS
    ok &= not bad
    print(
        f"{'FAIL' if bad else 'ok  '} enter Present: longest frame {r['enter_present_ms']} ms (budget {MAX_INTERACTION_MS:.0f}, as INP)"
    )
    for e in r["errors"]:
        print(f"FAIL page error: {e}")
    if not r["loaf_supported"]:
        print("note: Long Animation Frames API unavailable; only frame deltas checked")
    print(f"{'PASS' if ok else 'FAIL'} {a.path or '/'} at {a.rate}x CPU throttle")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
