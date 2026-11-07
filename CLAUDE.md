# SubScout: working rules

SubScout is a framework for **journalistic data narratives**: one Markdown story plus data produces a themed
web page with two modes, **Read** (scrollytelling article) and **Present** (in-browser deck). Published on
GitHub Pages. Owner: Adam McCarthy, a petroleum geoscience domain expert. Write for an informed reader.

## Scope
- SubScout does theming, layout, charts, maps, the state engine and the build. It does **not** do heavy
  ingestion: data arrives as Parquet/CSV/GeoJSON from separate pipelines. Demo-specific fetch/clean logic
  lives in each demo repo (e.g. `APA_awards`), not here.
- Keep a single lightweight demo story inside this repo (`examples/`). Bigger stories are separate repos.

## Language and units
- British English (colour, licence (noun), visualise, metre). Sentence-case headings.
- Metric first (Sm³, km, °C), boe alongside or via the page-wide units toggle. Oil: 1 Sm³ = 6.29 bbl;
  oil-equivalent conversions follow Sodir (1 Sm³ o.e.). State the convention used on the page.
- Every figure carries: title, units, source (with date), confidence level, notes where needed.
- Confidence levels: **Reported** (published figure, cited), **Derived** (our calculation from reported data,
  method stated), **Estimated** (assumption-dependent; say which assumption). Balance beauty and
  communication with key information; this is not a full EDA report, but never hide uncertainty.

## Colour (see `src/subscout/tokens/colour.toml`)
- Method ported from the Equinor Design System palette generator (MIT, credited). SubScout is **not**
  Equinor-branded: own hue names, no Equinor typeface/logo, and **never use `fjord` for an operator**.
- Every colour = anchor hue/chroma + shared 15-step lightness ladder + gaussian chroma. To add a colour, add
  an anchor only. Pages use **tone/alias tokens** (`--ss-text`, `--ss-accent-fill-emphasis`), never raw hex.
- Core hues: fjord (accent), shale (neutral surfaces/text), slate (chart structure), cobalt (secondary data).
  Highlights only: malachite, ochre, haematite; for annotation/change/status, never large areas.
- Data colours come in **presets** (`[presets.*]` in colour.toml: tide, signal, frost; default in
  `data.default_preset`). Switch with `data-palette="<name>"` on `<html>` or a container. Every preset is
  tested. Within a preset, two palettes for two jobs:
  - **story** (`--ss-data-story-N`, default): grey context (`--ss-data-context`) + 1-3 quiet core colours,
    plus `--ss-data-highlight` for the one thing to look at. Low chroma, so **always direct-label**.
  - **categorical** (`--ss-data-cat-1..N`, N = `--ss-data-cat-count`): identity of 3-5 entities (operators etc.), fixed order, passes
    the six dataviz checks. More than 5: fold into "Other" (context grey) or small multiples; never add hues.
  - Colour follows the entity, never its rank. One y-axis per chart (no dual axes).
- Diverging is cobalt ↔ ochre; never red ↔ green.
- **Chosen defaults (2026-11-07): Ledger type, Tide palette, Nordic cool room** (shale-white by day,
  mørketid by night: deep blue-grey, never black) **with the horizon motif**. Surfaces live in
  `[surfaces]` in colour.toml (`data-surface`); every option is contrast-tested. The horizon motif is
  decorative and stays outside plot areas.
- After editing colour.toml: `uv run subscout tokens && uv run subscout audit && uv run pytest`.
  Generated `runtime/css/tokens.*` are committed; CI fails if they are stale.

## Charts and motion
- Label axes and units; bars start at zero; minimise decimals; remove non-data ink; don't rely on colour alone
  (direct labels, patterns, position). No pie/donut by default.
- 3D is allowed when it is the right encoding (surfaces, structure, trajectories); state why in the story.
- Motion follows d3 practice, not EDS: animate **state changes that carry meaning**, keep object constancy
  (keyed joins), stage transitions (axes → marks → labels), use the duration/easing tokens, and honour
  `prefers-reduced-motion`. Read and Present modes drive the same state sequence.

## Engineering
- Python ≥3.12 via uv. `uv run pytest`, `uv run ruff check . && uv run ruff format .`
- Browser runtime is plain ES modules + CSS, no Node build. D3 from cdnjs with exact pinned versions.
- Theme attribute: `data-colour-scheme="light|dark"` on `<html>`, falling back to system preference.
  Type pairing: `data-type="ledger|survey|core"` (also works on containers).
- Chart components live in `runtime/js/charts.js` (line, stacked bars, bubbles, heatmap, diverging bars).
- Visual check before calling a page done: `uv run python scripts/build_pages.py && uv run python
  scripts/snapshot.py _site _snapshots [path]` then look at the screenshots; 0 console errors required.
- Stories must have tests for every number quoted in the prose (pattern from Viz_demo_generic).
