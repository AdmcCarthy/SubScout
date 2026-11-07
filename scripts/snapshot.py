"""Serve a built site and screenshot it headlessly; report console errors.

Usage: uv run python scripts/snapshot.py [site_dir] [out_dir]
Writes desktop light/dark, phone, and Present-mode screenshots.
"""

from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D102
            pass

    handler = functools.partial(Quiet, directory=str(directory))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def main(site: Path, out: Path) -> int:
    out.mkdir(parents=True, exist_ok=True)
    srv, url = serve(site)
    errors: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        shots = [
            ("desktop-light", {"width": 1280, "height": 900}, "light"),
            ("desktop-dark", {"width": 1280, "height": 900}, "dark"),
            ("phone-light", {"width": 390, "height": 844}, "light"),
        ]
        for name, vp, scheme in shots:
            page = browser.new_page(viewport=vp, color_scheme=scheme)
            page.on("console", lambda m, n=name: m.type == "error" and errors.append(f"{n}: {m.text}"))
            page.on("pageerror", lambda e, n=name: errors.append(f"{n}: {e}"))
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(600)
            page.screenshot(path=str(out / f"{name}.png"), full_page=True)
            if name == "desktop-light":
                page.click("#present-btn")
                page.wait_for_timeout(700)
                for k in range(4):
                    page.screenshot(path=str(out / f"present-{k + 1}.png"))
                    page.keyboard.press("ArrowRight")
                    page.wait_for_timeout(1700)
            page.close()
        browser.close()
    srv.shutdown()
    for e in errors:
        print("ERROR", e)
    print(f"screenshots in {out}; {len(errors)} console errors")
    return 1 if errors else 0


if __name__ == "__main__":
    site = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "_snapshots"
    sys.exit(main(site, out))
