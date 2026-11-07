# Performance

Buttery smooth, no compromise, enforced in CI rather than hoped for.

## Budgets

| Measure | Budget |
|---|---|
| Frames during scroll, transitions and deck steps | p95 ≤ 16.7 ms (60 fps); aim ≈ 8 ms for 120 Hz |
| Long animation frames | none > 50 ms |
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
- **Fonts:** stories self-host the chosen pairing only (Ledger), subset, `woff2`, preloaded.
- **Pinned libraries** from cdnjs with exact versions.

## Enforcement

The Playwright snapshot script grows into a performance test: scroll the whole story and step through
Present mode with the CPU throttled 4×, record Long Animation Frames, and fail the build if any frame
exceeds 50 ms or the p95 frame exceeds 16.7 ms. Zero console errors are already required.
