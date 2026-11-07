# Performance

Buttery smooth, no compromise, enforced in CI rather than hoped for.

## Budgets

| Measure | Budget |
|---|---|
| Frames during scroll, transitions and deck steps | p95 ≤ 16.7 ms (60 fps); aim ≈ 8 ms for 120 Hz |
| Long animation frames during scroll, transitions and deck steps | none > 50 ms |
| A discrete action (e.g. entering Present mode) | longest frame ≤ 200 ms (as INP) |
| INP (input to next paint) | ≤ 200 ms; aim < 100 ms |
| LCP (main content visible) | ≤ 2.5 s |
| CLS (layout shift) | 0: chart space is reserved |
| Page weight | budget per story, checked in CI |

## How

- **Renderer by mark count:** SVG to ~1–2k marks, Canvas beyond, WebGL (MapLibre/deck.gl) for very
  large sets. On Canvas, d3 still drives interpolation; hit-testing uses `d3-delaunay` or a quadtree,
  not a hidden canvas. Scale canvases for device pixel ratio.
- **Heavy work at build time in Python:** simplify and quantise geometry, aggregate, sort, precompute
  layouts. The browser never parses Parquet; large arrays ship as compact binary.
- **Draw near the viewport only** (IntersectionObserver); pause offscreen animation.
- **Compositor-friendly CSS:** animate transform and opacity only; batch DOM reads and writes; throttle
  ResizeObserver work to animation frames.
- **Fonts:** load the chosen pairing only (Ledger). *Planned:* self-host, subset, `woff2`, preloaded (v0.1 loads Ledger from Google Fonts).
- **Pinned libraries** from cdnjs with exact versions.

## Enforcement

`scripts/perf.py` runs in CI: it scrolls the whole story and steps through Present mode with the CPU
throttled 4×, records Long Animation Frames and frame deltas, and fails the build on any long frame
over 50 ms during animation, a p95 frame over budget, or a discrete action over 200 ms. Headless
Chromium reports frames in whole display refreshes, so the p95 check allows 25% (20.9 ms); a page
at a steady 60 fps measures 16.7–16.8 ms.

Patterns that keep pages inside the budget:

- **Pre-draw every chart once at load**, so a step or slide only transitions existing marks instead of
  building DOM mid-animation.
- **On resize, redraw only the visible chart on the next frame**; hidden layers redraw in idle time
  (`idle()` in subscout.js).
- Zero console errors are required.

## Readability (scrolly)

Every step must be readable as a reader meets it, on phones and on desktop: the active text card fully
visible and uncovered, and its chart on screen, uncovered and at least a fifth of the screen high.
`scripts/readability.py` checks this on 360×740, 390×844 and 414×896 phones and 1280×800 and 1440×900
desktops, judging each step at the best moment a reader gets while it is active. It runs in CI on the
demo; run it on every story before publishing.

On phones the figure is pinned at the top of the screen, opaque and compact (title, legend, chart and a
one-line source; subtitle and notes stay in the appendix), and the text scrolls up beneath it, one card
at a time. A step becomes active when its card enters the text area (`--ss-trigger`, a percentage of the
viewport height). Keep step text short enough to fit beneath the figure on a 360×740 screen.
