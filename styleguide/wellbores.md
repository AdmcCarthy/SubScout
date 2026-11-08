# Wellbores, wells and installations

Point symbols for wells and installations on maps. Vocabulary and meaning follow the **Sodir Geostandard v22.00 (2022), sections 3.4 and 3.5**
(<https://www.sodir.no/globalassets/2-force/2022/dokumenter/geostandard-ekstern.pdf>). The shapes are redrawn for SubScout, not copied.
The data is `src/subscout/tokens/symbols.toml`; `uv run subscout symbols` generates `runtime/js/symbols.js` data and JSON; the review sheet
is `site/symbols/` (every symbol beside the standard's wording). Choropleths and other map forms are in [maps.md](maps.md).

## Rules

1. **Shape carries meaning; colour never does.** Every symbol reads in one ink, on light or dark, for any reader. The standard's colours
   (oil green, gas red) are an optional layer for exchange outputs, off by default, and not colour-vision safe (oil against gas is the
   red-green pair the colour rules forbid). If a map turns them on it says so in the legend.
2. **Compose, do not collect.** A well is a base circle, a layer per fluid, technical status and function. "Oil well, plugged and
   abandoned" is the oil layer plus the plugged-and-abandoned layer. The standard shows a selection of combinations and says the rest follow
   the same principle; the data is built that way, and every combination composes.
3. **Status applies to the well as a whole**, unless the legend says it applies to the mapped zone. If a map shows status for a zone, say so
   in the legend (the standard asks for this).
4. **Define every code in the legend.** The letter codes (F flowing, P pumping, W, R, G, S, E shut-in reasons, T, NC, F/NR/NP for unobserved
   units) are the standard's, and a map may define more. A map's legend lists each symbol and each code it uses, nothing it does not use.
5. **Fit symbols to the scale.** Below 18 px the letter code drops; below 10 px a symbol is a plain dot and the legend says so. Never shrink
   a symbol below legibility to avoid overplotting: thin the wells or show a density instead.
6. **Planned is muted, not a new shape.** The standard draws a planned installation as the same symbol in grey; SubScout uses the muted
   text tone. A planned well keeps its status shape (a proposed or planned well is an open circle).
7. **Trajectories use line style**: solid for the drilled path, dotted for an approximate path, dashed for a planned one. Mark the surface
   location with the well symbol and the bottom-hole end with a tick.
8. **Do not interpret what the data does not say.** Unknown status, fluid or function stays unknown (the plain base circle), never a guess.
9. **Attribute.** A map that uses these symbols credits the Geostandard in its source line, and well data with its own source and licence.

## What a record says

A well record, after the source's own vocabulary has been translated (in the data pipeline, not here):

| Field | Values | Standard |
|---|---|---|
| `fluids` | `"dry"`, `"coal"`, or pairs of fluid and qualifier: oil, gas with `proven`, `minor`, `trace`; condensate with `proven`, `minor` | 3.4.2, 3.4.3 |
| `technical` | `open` (default), `proposed`, `abandoned_technical`, `temporarily_abandoned`, `plugged_abandoned`, `not_observed` | 3.4.2 |
| `fn.kind` | `production`, `injection`, `converted`, `observation`, `dual_completion`, `shut_in` | 3.4.4 |
| `fn.fluid` | for injection: `water`, `cuttings`, `co2` (gas injection is the gas layer) | 3.4.4 |
| `zone` | `above`, `below`: the function applies shallower or deeper than the mapped zone | 3.4.4 |
| `exploration` | `wildcat`, `appraisal`: active exploration wells replace the base circle | 3.4.7 |
| `code` | a short letter code shown beside the symbol | 3.4.4 |
| `planned` | draws muted | 3.4.4, 3.5 |

Fluid qualifiers: **proven** is the main fluid; **minor** is minor amounts or uncertain producibility; **trace** is residual or immobile, traces.
Condensate has no trace form in the standard. Class (3.4.9: development or service, exploratory, injector, non-hydrocarbon) and the 38
installation types of 3.5 are separate symbol sets.

## Where SubScout departs from, or adds to, the standard

- **Class markers get a shape.** The standard shows well class as coloured dots only (3.4.9); SubScout gives each a shape (disc, diamond,
  triangle, square) so class does not rest on colour. Tagged *SubScout shape* on the sheet.
- **Oil and gas colours are optional**, as above.
- **Simplified drawings.** Where a symbol is simplified from the standard's drawing (condensate lobes, residual gas, the shallow borehole,
  coal, anchor, buoys, clamp, flange, ship, tank, transponder, unknown installation, and a few injection variants) the data says
  `simplified = true` and the sheet tags it. Redraw them closer to the standard when a use needs it; the tests keep the vocabulary stable.
- **Installations are monochrome by default.** The standard colours some (platform red, anchor red, start and end point light blue, rig
  blue); that colour is available as part of the optional Geostandard preset.
- **Not yet covered** (they belong with vector layers, not point symbols): fault, contour and fold-axis line styles (1.3), oriented dip
  readings (3.4.6), seismic acquisition areas (3.4.8), and the standard's block and licence colours (6.14, 6.25).

## Using it

```js
import { wellSpec, symbolSvg, drawSymbol, legend, describe } from "./runtime/js/symbols.js";

const well = { fluids: [["oil", "proven"], ["gas", "minor"]], technical: "plugged_abandoned", fn: { kind: "production" }, code: "F" };
el.innerHTML = symbolSvg(wellSpec(well), { size: 24 });            // an SVG string, drawn in currentColor
drawSymbol(ctx, wellSpec(well), x, y, 18);                           // Canvas: ink from the --ss-text token by default
legend([well, ...others]).map(({ spec, label }) => ...);            // rows for the legend, in first-use order
```

Meaning in words: `describe(well)` returns the standard's own wording when the combination is one of its examples, otherwise the layers
joined. Translating a source's vocabulary (for example Sodir's purpose, status and content) into this record is the job of the data pipeline
that owns the source, so that SubScout carries no source-specific code.

## Checks

`tests/test_symbols.py` checks the data (every shape inside its box, every standard installation present, every one of the standard's
examples and every combination composes, generated files current). `scripts/symbols_check.py` runs in CI: the JavaScript composition
equals the Python one on every example and about a thousand combinations, and every symbol draws to SVG and to Canvas.
