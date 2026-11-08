"""Browser check for the symbols: JS composition equals the Python one, every symbol draws, no console errors.

Usage: uv run python scripts/build_pages.py _site && uv run python scripts/symbols_check.py [site_dir]

`subscout.symbols.layers_for` and `runtime/js/symbols.js layersFor` are two implementations of one rule. This
asserts they agree on the standard's own examples and on every combination of fluids, technical status and
function. It also draws each symbol to SVG and to a Canvas (blank or NaN output fails) and loads the review
sheet at /symbols/ with console errors treated as failures.
"""

from __future__ import annotations

import functools
import http.server
import itertools
import sys
import threading
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from subscout import symbols as S

ROOT = Path(__file__).resolve().parents[1]

CHECK = """
async (cases) => {
  const m = await import('/runtime/js/symbols.js');
  const bad = { mismatch: [], svg: [], canvas: [] };
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 80;
  const ctx = canvas.getContext('2d');
  for (const [label, well, layers] of cases) {
    if (JSON.stringify(m.layersFor(well)) !== JSON.stringify(layers)) bad.mismatch.push(label);
    const spec = m.wellSpec(well), svg = m.symbolSvg(spec, { size: 40 });
    if (!svg.includes('<svg') || /NaN|undefined/.test(svg)) bad.svg.push(label);
    ctx.clearRect(0, 0, 80, 80);
    m.drawSymbol(ctx, spec, 40, 40, 70, { ink: 'black', mutedInk: 'gray' });
    const px = ctx.getImageData(0, 0, 80, 80).data;
    let ink = 0;
    for (let i = 3; i < px.length; i += 4) if (px[i] > 0) ink++;
    if (!ink) bad.canvas.push(label);
  }
  const inst = Object.keys(m.data.installations);
  const specs = [
    ...inst.flatMap((k) => [m.installationSpec(k), m.installationSpec(k, { planned: true })]),
    ...m.vocabulary.classes.map((c) => m.classSpec(c)),
    m.shallowBoreholeSpec(),
  ];
  for (const spec of specs) {
    const svg = m.symbolSvg(spec, { size: 40 });
    if (!svg.includes('<svg') || /NaN|undefined/.test(svg)) bad.svg.push(spec.layers[0]);
    ctx.clearRect(0, 0, 80, 80); m.drawSymbol(ctx, spec, 40, 40, 70);
    let ink = 0; const px = ctx.getImageData(0, 0, 80, 80).data;
    for (let i = 3; i < px.length; i += 4) if (px[i] > 0) ink++;
    if (!ink) bad.canvas.push(spec.layers[0]);
  }
  return { ...bad, count: cases.length + specs.length };
}
"""


def cases() -> list[list]:
    data = S.build()
    out = [[e["label"], e["well"], S.layers_for(e["well"])] for e in data["examples"]]
    by = data["vocabulary"]["qualifiers_by_fluid"]
    opts = [[None, *by[f]] for f in ("oil", "gas", "condensate")]
    for o, g, c in itertools.product(*opts):
        fluids = [[f, q] for f, q in (("oil", o), ("gas", g), ("condensate", c)) if q]
        for tech in data["vocabulary"]["technical"]:
            for fn in (None, "production", "injection"):
                well = {"fluids": fluids or None, "technical": tech, "fn": {"kind": fn} if fn else None}
                out.append([f"{fluids} {tech} {fn}", well, S.layers_for(well)])
    return out


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):  # noqa: D102
            pass

    srv = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Quiet, directory=str(directory))
    )
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def main(site: Path) -> int:
    srv, base = serve(site)
    errors: list[str] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except PlaywrightError:  # no bundled Chromium: use an installed Edge or Chrome
            browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        page.on(
            "console",
            lambda m: errors.append(m.text) if m.type == "error" and "favicon" not in m.text else None,
        )
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(base + "symbols/index.html")
        page.wait_for_selector("table.ex tbody tr")
        result = page.evaluate(CHECK, cases())
        n_svg = page.evaluate("document.querySelectorAll('#sheet svg').length")
        browser.close()
    srv.shutdown()
    print(f"checked {result['count']} symbols; the sheet draws {n_svg} svgs; {len(errors)} console errors")
    failed = False
    for key in ("mismatch", "svg", "canvas"):
        if result[key]:
            failed = True
            print(f"FAIL {key}: {len(result[key])}, first {result[key][:3]}")
    for e in errors[:3]:
        failed = True
        print("console error:", e)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"))
