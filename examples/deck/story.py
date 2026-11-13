"""Metrics for the deck demo: those of the demo story, on the same synthetic data, and one card thumbnail."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("demo_story", Path(__file__).parents[1] / "demo" / "story.py")
_demo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_demo)

metrics = _demo.metrics


def thumbnails(d):
    """Cards of the landing page: `{slug: svg}`. A category without one shows its number."""
    p = d["production"]
    c = p[p.field == "Field C"].sort_values("year")
    w, h = 300, 130
    x0, x1, top = c.year.min(), c.year.max(), c.kboed.max()
    pts = " ".join(
        f"{6 + (y - x0) / (x1 - x0) * (w - 12):.1f},{h - 6 - v / top * (h - 12):.1f}"
        for y, v in zip(c.year, c.kboed, strict=True)
    )
    line = f'<polyline points="{pts}" fill="none" stroke="var(--ss-data-highlight)" stroke-width="2"/>'
    return {
        "production": f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" aria-hidden="true">{line}</svg>'
    }
