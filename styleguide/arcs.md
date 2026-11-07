# Narrative arcs

A story declares one `arc:`. Each arc is a list of named **beats**; steps are tagged with a beat
(`::: step {beat=…}`). `subscout new --arc <name>` will generate a skeleton, and the build warns about
missing or out-of-order beats. To test an arc, tell the same dataset two ways and compare.

## General arcs

| Arc | Beats | Suits | Source |
|---|---|---|---|
| `abt` | and → but → therefore | Short pieces, 3–5 steps | Olson |
| `scqa` | situation → complication → question → answer → support… | The executive case, answer first; best in Present | Minto |
| `sparkline` | what-is ⇄ what-could-be (repeat) → call-to-action → new-bliss | Selling a case or investment | Duarte |
| `martini` | stem (guided steps) → open (free exploration) | Data journalism | Segel & Heer |
| `drill-down` | overview → instances (reader-chosen) | Portfolio, field by field | Segel & Heer |
| `zoom` | moment → context → moment | A single event in its full context | |
| `reveal` | claim → evidence → twist | Myth-busting | |

## Geology-native arcs

| Arc | Beats | Suits |
|---|---|---|
| `petroleum-system` | source → migration → reservoir → trap → seal → timing → therefore | Why a prospect works; risk accumulates as a product |
| `pre-post-drill` | prediction → result → lessons | Honest testing of interpretation |
| `deep-time` | rift → burial → uplift → today | Basin history to present opportunity |
| `creaming-curve` | early-giants → long-tail → whats-left | Exploration maturity |
| `lifecycle` | prospect → discovery → development → plateau → decline → decommissioning | A field's life |

## Craft

- One idea per step; the step's figure title is the finding.
- The hook earns attention with data, not decoration.
- The final beat lands on a claim tagged with its confidence level.
- Arcs can nest: an `scqa` story can contain a `pre-post-drill` section.
