# Story format (v0.1)

A story is a folder:

```
my-story/
├── story.md     narrative: front matter + Markdown + steps + chart/table blocks
├── story.py     optional: metrics (numbers for the prose) and derived datasets
└── data/        inputs: CSV, Parquet, JSON, GeoJSON
```

Build it with `uv run subscout build my-story --out _site`. The build fails on errors (unknown
metric, missing source, figure without confidence…) and prints warnings (untraced numbers, missing
beats).

## Front matter

```yaml
---
title: Close to home
dek: Norway's latest licensing round was about filling gaps.
kicker: NCS · APA 2025 · granted 20 March 2026
byline: Adam McCarthy
date: 2026-11-07
arc: scqa                 # see arcs.md; steps are checked against its beats
register: section         # core | section | outcrop
palette: tide             # data-colour preset
surface: nordic-cool      # room
units: sm3                # starting unit; the reader can toggle
horizon: true             # horizon motif in the hero
kpis:                     # hero ledger: metric + label
  - { metric: n_licences, label: production licences granted }
sources:
  sodir: { name: Sodir FactMaps, url: "https://factmaps.sodir.no", accessed: 2026-11-06 }
data:
  awards: data/awards.json          # name: path (csv, parquet, json, geojson)
  history: data/history.csv
---
```

## Numbers in prose

Write `{{ metric }}` or `{{ metric | filter | filter }}`. Metrics come from `story.py`; every one
used appears in the appendix numbers ledger with its value, method, source and confidence.

| Filter | Effect |
|---|---|
| `int` | 1,234 |
| `round:1` | 12.3 |
| `pct` | 0.63 → 63% (a share in 0–1) |
| `about` | rounds to two significant figures and prefixes "about" |
| `signed` | +3.4 / −2.1 |
| `volume` | Sm³ value, shown in the reader's unit (Sm³ ⇄ boe toggle) |
| `km`, `km2` | appends the unit |
| `cite:<source>` | a literal external figure, cited (use for numbers not computed here) |
| `param` | a literal threshold or definition chosen for the story (`{{ 25 \| param }} km`); listed in the ledger as a parameter |

Digits typed directly in prose (other than years and labels such as "PL 1313") are reported as
**untraced** warnings.

## story.py

```python
from subscout import metric


def datasets(d):  # optional: add derived datasets (pandas DataFrames or dicts)
    return {"by_area": d["awards"].groupby("area_name").size().reset_index(name="n")}


def metrics(d):  # numbers the prose may use
    a = d["awards"]
    return {
        "n_licences": metric(
            len(a), "Count of licences in round TFO2025", source="sodir", confidence="observed"
        ),
        "near_1km": metric(
            (a.dist_km <= 1).sum(),
            "Licences ≤ 1 km from a producing field",
            source="sodir",
            confidence="derived",
        ),
    }
```

GeoJSON loads as a dict; when its features have properties, a DataFrame of those properties is also
available as `<name>_props`.

## Steps

Consecutive steps form one scrolly sequence that also plays as a deck in Present mode. Put `layout=wide` on the
first step (`::: step {beat=… layout=wide}`) for a showpiece figure: its frame spans the page and the
step cards scroll in a lane inside it (phones and Present mode are unchanged). Each step may
contain one chart block; a block with `use: <id>` changes the state of an earlier chart, so it
transitions instead of being replaced.

````markdown
::: step {beat=situation}
### 56 new licences among hundreds of old ones
Prose…

```chart
id: shelf
type: map
…
```
:::
````

Text outside steps flows as normal article content; chart and table blocks there render inline.

## Chart blocks

Common keys: `id`, `type`, `data`, `title` (an action title), `subtitle`, `source`, `confidence`
(`observed | derived | interpreted`), `notes`, `register`, `exception: {rule, reason}`, `unit`.

| `type` | Data | Encoding keys | State keys (for `use:`) |
|---|---|---|---|
| `line` | tidy table | `x`, `y`, `series` | `focus: [series]`, `note: {series, x, text}` |
| `bars` | table | `label`, `value`, optional `part` (stack), `colour_by` | `highlight: [labels]`, `sort` |
| `stack` | tidy table | `x`, `y`, `series` | — |
| `dots` | table | `row`, `value`, `label`, `flag`, `scale: linear | sqrt | symlog` | `highlight: [labels]` |
| `map` | GeoJSON layers | `layers: [{data, role, colour_by}]`, `labels` | `view: [w, s, e, n]`, `filter: {prop: value}`, `colour_by` |
| `heat` | tidy table | `x`, `y`, `value`, `rows` (list, or `data` for data order), `value_label` | — |
| `diverging` | table | `label`, `value` | `sort` |
| `custom` | any datasets (`data: name` or a list) | `module: figures/x.js` (a story-supplied ES module) | anything in `state:`; `use:` steps pass their keys through |

**Export pages.** Add `export: true` (or `export: {sizes: [slide, portrait, square], themes: [light, dark]}`)
to a detailed figure that readers will want as an image. The build writes `export/<id>/`: the figure alone on
a fixed artboard (slide 1600×900, portrait 1200×1500, square 1200×1200) with title, legend, source, units,
confidence and byline, a toolbar for size, view (the figure's own state and every `use:` step, named after
the step), theme and units, and download links. `uv run subscout export _site` (needs `subscout[export]`
and `playwright install chromium`) renders every combination at 3× in headless Chromium, e.g. 4800×2700
for a slide, and lists them in `renders.json`; run it in the Pages workflow after the build. Custom figures
receive `opts.export` and `opts.height()` and should fill that height. The figure's footer links to the page.

**Custom figures.** When no built-in form fits, a story can supply its own figure as an ES module. It
exports `default (el, datasets, opts) => ({ draw(width, state, { animate }), repaint() })`; `datasets`
holds the named data, `opts.units()` the reader's unit, `opts.states` every state the story will ask
for (its own `state:`, then each `use:` step: prepare them ahead to keep steps smooth), and it may import SubScout helpers from
`../runtime/js/subscout.js`. The module's folder is copied into the site. A custom figure still needs
an action title, source and confidence, and should declare how it departs from the rules
(`exception:` or `notes:`); the truth gate still applies.
| `network` | node table + `edges` table | `frame`, `node`, `size`, `weight`, `colour_by`, `size_label`, `weight_label`, `frame_label`, `label_top`, `tooltip` | `frame`, `highlight: [nodes]` |

**Networks.** `data` is a node table (one row per node per frame) and `edges` an edge table with
columns `a`, `b`, the `frame` column and the `weight` column. Layouts are computed at build time
(`subscout/layout.py`): each frame is warm-started from the previous one and all frames share one
scale, so a node stays roughly in place and a smaller network looks smaller. Steps switch frames
with `use: <id>` and `frame: <value>`; nodes and edges are keyed, so the change is a staged
transition (leaving edges fade, nodes move, new edges appear), not a live force simulation. Dot area
and line width share one scale across frames.

## Table blocks

````markdown
```table
kind: league            # league | ledger
data: awards_props
columns:
  - { field: name, label: Licence }
  - { field: km2, label: Area, unit: km², bar: true, format: int }
sort: -km2
highlight: { operator: Aker BP }
fold: 10
title: The largest licences went to the Norwegian Sea
source: sodir
confidence: observed
```
````

## Appendix (generated)

"How we know" collects: sources, the numbers ledger, every figure's source and confidence, declared
exceptions, the arc and units conventions, and any `::: appendix` content you add.
