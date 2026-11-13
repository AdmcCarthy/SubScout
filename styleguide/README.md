# SubScout style guide

How a SubScout story or deck looks, reads and argues. Agreed 2026-11-07 after a research phase covering
Few, Cairo, Tufte, Bremer, Wu, Schwabish, Segel & Heer, Minto, Duarte, Olson, cartographic practice
and Norwegian design. Where a rule can be checked by the build, the file says so.

| File | Covers |
|---|---|
| [voice.md](voice.md) | The thesis, the interpreter's voice, Norwegian restraint, signature elements |
| [rules.md](rules.md) | The truth gate, functional rules, colour rules, declared exceptions, review checklist |
| [registers.md](registers.md) | Core / Section / Outcrop: how much ornament and how custom a form may be |
| [language.md](language.md) | British English, units, numbers, confidence wording, glossary |
| [uncertainty.md](uncertainty.md) | P90 / P50 / P10, ranges, chance of success |
| [arcs.md](arcs.md) | Narrative arcs, general and geology-native |
| [story-format.md](story-format.md) | Story mode: the folder, front matter, steps, chart and table blocks |
| [deck-format.md](deck-format.md) | Deck mode: categories, slides, masters, the fit rule; when a story is a deck |
| [tables.md](tables.md) | Tables as a narrative element |
| [maps.md](maps.md) | Choropleths and alternatives, map storytelling, map technology |
| [wellbores.md](wellbores.md) | Well, wellbore and installation symbols after the Sodir Geostandard: composition, codes, scale, what is not covered |
| [motion.md](motion.md) | When and how things move |
| [performance.md](performance.md) | Budgets and techniques; enforced in CI |

## Tiers: what binds

Every rule here is one of two tiers, and some files also hold reference. **[Law]** is never bent and never excepted. **[Default]**
is house style: follow it, or declare the exception on the page (`exception:` in a block) with the reason. Untagged rules are
Defaults. The agent-facing source of this arrangement is the maintainer's private Idiom repo; the tags below are its public form.

| Tier | Where it appears in this guide |
|---|---|
| **[Law]** | The truth gate (`rules.md` section 1, choropleth honesty in `maps.md`); Observed / Derived / Interpreted on every figure; British English, sentence case and the impersonal voice (`language.md`); Interpreted values never without a range or assumption |
| **[Default]** | Functional and colour rules, review checklist, registers, arcs, tables, map forms, motion, performance, variety (`voice.md`), units and number style, the symbol set (`wellbores.md`) |
| Reference | The Sodir Geostandard departures in `wellbores.md`, the P90 / P50 / P10 conventions in `uncertainty.md`: facts about the domain that inform, and bind only once promoted to a Default |

A build check that fails (the truth gate) is Law enforced. A build check that only advises (`advice:`, untraced numbers) enforces a
Default.

## In one paragraph

An interpreter's honesty, expressed with Norwegian restraint. Confident about the mechanism,
explicit about the uncertainty. Function first, just enough, true to its materials, built along the
horizon, with one warm light. Every number traces to data, every figure states its source, units and
confidence, and every persuasive choice is declared.

## Chosen defaults

- **Type:** Ledger (Newsreader, Instrument Sans, JetBrains Mono)
- **Data palette:** Tide (fjord story colour, ochre highlight, ochre-led identity palette)
- **Room:** Nordic cool (shale-white by day, mørketid by night) with the horizon motif
- **Register:** Section
- **Units:** Sm³ first, boe via the page toggle (1 Sm³ o.e. = 6.29 boe)
