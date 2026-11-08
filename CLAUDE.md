# SubScout: working rules

**The style guide in `styleguide/` is the authority** for voice, rules, registers, language,
uncertainty, arcs, tables, maps, motion and performance. Read the relevant file before building a
story or component. This file summarises the engineering side.

@../../shared/idiom/CORE.md

Voice and structure of written work (README, docs, published pages) follow Idiom's CORE.md and house style: British English, impersonal, one creative headline then plain varied headings, a section ends on its last point. The import is harmless when the file is absent (CI).

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
- Confidence levels: **Observed** (measured or published, cited), **Derived** (calculated from observed data, method
  stated), **Interpreted** (depends on a model or judgement; give the range or assumption). Balance beauty
  and communication with key information; this is not a full EDA report, but never hide uncertainty.

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
- Chart components live in `runtime/js/charts.js` (line, stacked bars, bubbles, heatmap, diverging bars, bars, dots, map, network). Network layouts are
  precomputed at build time in `layout.py`; the browser only transitions between settled frames.
- Readability gate: `uv run python scripts/readability.py <site> [path]` scrolls every step on three phone
  and two desktop sizes and checks (by what is on top on screen) that the active text card and its chart are
  both fully readable, uncovered and on screen. Phones pin the figure at the top (opaque, compact: title,
  legend, chart, one-line source) and the text scrolls up beneath it; `--ss-trigger` sets where a card
  activates. Custom figures must size themselves for that panel on narrow screens (about 30-36 % of vh).
- Export pages and the export contract: `export:` on a chart block -> `export/<id>/index.html` (a proof artboard) and
  `export/<id>/payload.json` (the contract, version 1, schema in docs/export-contract.md). Rendering to PDF/PNG at real
  paper sizes (A4-A0) is **Plate's** job (`plate render <site>`); SubScout no longer renders and `subscout export` only
  points there. Dependencies run one way: Plate -> SubScout. Changing the contract means bumping `CONTRACT_VERSION`.
- Visual check before calling a page done: `uv run python scripts/build_pages.py && uv run python
  scripts/snapshot.py _site _snapshots [path]` then look at the screenshots; 0 console errors required.
- Symbols (`styleguide/wellbores.md`): well, wellbore and installation symbols after the Sodir Geostandard 3.4 and
  3.5, redrawn. Source of truth `src/subscout/tokens/symbols.toml`; after editing it run `uv run subscout symbols`
  (generated `runtime/js/symbols-data.js` and `symbols.json` are committed, CI fails if stale). Shape carries meaning,
  never colour; wells are composed from layers (base, fluid, technical status, function), not listed one by one.
  Review sheet at `site/symbols/`; `uv run python scripts/symbols_check.py _site` after `scripts/build_pages.py`.
  Source-specific vocabulary (Sodir purpose, status, content) is translated by the data pipeline that owns the source,
  never in SubScout.
- Stories must have tests for every number quoted in the prose (pattern from Viz_demo_generic).

## Idiom (private repo)

Idiom is Adam McCarthy's private repo (`github.com/AdmcCarthy/Idiom`; `gh repo clone AdmcCarthy/Idiom` with access, normally linked at
`../../shared/idiom`) of voice, house style, working rules and the lookup tables agents use first: `DIRECTORY.md` says which repo already
does a job, `DATASETS.md` gives every dataset's terms, attribution line and status. Read the relevant one before choosing a repo or
using data, and update it when you learn something new. Never copy anything from its `personal/` or `working/` folders into this repo
or quote it in public output; if the folder is not available, say so and carry on with this file.
