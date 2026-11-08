# Voice

## The thesis

Interpreting the subsurface is honest persuasion. Geoscientists build confident cases from sparse,
indirect evidence (wells are pinpricks, seismic is an echo) while keeping observation separate from
interpretation. No dataviz author owns that discipline; this one does.

**The voice is the interpreter's voice: confident about the mechanism, explicit about the
uncertainty.**

## Between two traditions

SubScout sits between data journalism and the executive case. It takes the deck's confidence (an
answer, a recommendation, a call to action) and the newsroom's accountability (sources, methods,
uncertainty, corrections). Framing, ordering and emphasis always persuade; SubScout makes those
choices **deliberate and declared** (see the disclosure rule in [rules.md](rules.md)).

## Norwegian restraint

Inspired by Norwegian architecture and interiors rather than a generic "Scandinavian" label.

| Principle | In SubScout |
|---|---|
| Function first, made to last | Few and Tufte at the core; timeless type, stable tokens, no trend effects |
| *Lagom*: just enough | One accent, one highlight; registers as three measures of "enough" |
| Truth to materials | Observed / Derived / Interpreted; the rock itself is the texture, never imitation |
| The horizon (Sverre Fehn) | Horizontal compositions, strong baselines, the horizon motif; a seismic horizon is an interpreted surface |
| The platform in the landscape (Fehn; the Scenic Routes) | Annotation as a viewpoint: frame the data, don't dominate it. One dramatic platform per story at most |
| Democratic design (Oslo Opera House roof) | Accessible, open, readable on a phone, free to read; glossary for domain terms |
| Restraint, never cold | One warm light in a cool room: the ochre highlight, *koselig* |
| Light as a scarce resource | Light mode is summer light; dark mode is *mørketid*, deep blue-grey, never black |
| Craft and humility | Tabular figures, true minus (−), units in a lighter weight, careful spacing |

## Signature elements

1. **Observed / Derived / Interpreted** as the confidence system (see [language.md](language.md)).
2. **Depth as a narrative axis:** depth points down; scrolling is drilling (a well-path progress
   indicator); geological time runs vertically in stratigraphic columns.
3. **"Cut the map":** a line drawn across a map opens a cross-section beneath it.
4. **The composite log** as a chart form: depth- or time-aligned tracks, Tufte's micro/macro display.
5. **Imagery derived from data:** bathymetry hillshade, structure-map contours, seismic wiggle traces,
   drawn in shale and fjord. Kept outside plot areas. Photographs are optional and always captioned
   honestly ("Illustrative photo" unless it is the actual place).
6. **Lithology patterns as texture:** sandstone dots, shale dashes, limestone bricks as the secondary
   encoding for colour-blind readers and print.
7. **Reference palettes from standards:** ICS chronostratigraphic colours, fluid conventions (oil,
   gas, water). Exempt from presets, still contrast-checked.
8. **Uncertainty is native:** P90/P50/P10, chance of success, pre-drill vs post-drill.
9. **Geology-native arcs** (see [arcs.md](arcs.md)).
10. **Kickers as core-box labels:** `NCS · 34/7 · TFO2025`.

## Lineage

The rigour of Few and Tufte; the honesty of Cairo, expressed as observation versus interpretation;
the delight of Bremer and Wu, drawn from the subject itself (strata, seismic, contours) rather than
from decoration.

## Variety: one device does not run the whole piece

A catchy headline is a device, and a device works because it is rare. Adam's rule: **the article headline may be creative;
the same technique must not be repeated in every text box and sub-story.** The same applies to structure.

- **Headings.** Sub-story, panel and box headings are plain and say what is there. Do not give every one a clipped headline
  ("Quicker wells", "Close to home"), a label and an image ("APA 2008: a mesh of partners"), a year lead, or a comma and a
  twist. Two in a row of one construction is the most a reader should meet. Keep a catchy line for the one or two places it
  earns its keep.
- **Shape.** Do not build every step the same way: heading, one short paragraph of about fifty words, figure. Let some steps
  run longer, merge neighbours, let some carry no heading of their own. A long chain of identical sub-sections reads as a
  list, whatever the headings say.
- **Paragraphs.** One idea each, three at most in a step; vary how they open. Do not start consecutive paragraphs or
  headings with the same word.
- **Checked by the build as advice** (`advice:` lines and `advice` in `build-report.json`; never an error): a run of
  three or more headings built the same way, one device over 60% of headings, a run of headings opening with the same word,
  five or more steps of one shape, more than twelve sub-sections, more than three paragraphs in a step. Thresholds are in
  `src/subscout/advice.py`.

