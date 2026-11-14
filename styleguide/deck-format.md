# Deck format

SubScout builds a story folder in one of two modes. **Story** mode is for a data story told as journalism: one
argument, read once from top to bottom on one scrolling page ([story-format.md](story-format.md)). **Deck** mode is
for presentation and teaching material: a body of knowledge in categories, entered at any point and returned to,
in which each view is one slide the size of the screen.

| | Story | Deck |
|---|---|---|
| For | one argument, read once | a subject taught in parts, presented to a room or stepped through alone |
| Output | one page: text scrolls beside a pinned figure; Read and Present views | a landing page of categories, one page of slides per category, a basis page |
| Length | holds to about 30 or 40 steps | grows by adding categories |
| Heading of a view | an action title: the finding | the point being taught, with the figure's own title beneath |
| Structure checked | the narrative arc and its beats | every section in exactly one category |
| Layout gate | readability of each step card, phone and desktop (`scripts/readability.py`) | fit: no slide scrolls, no text overflows (`subscout fit`) |
| Screens | phone and desktop | desktop only |

The truth gate, sources, confidence grades, `{{ metric }}` numbers and the numbers ledger are the same in both modes.
A story that has grown past about 40 steps, or that readers enter in the middle, is a sign that it is a deck.

## The folder

```
basin-deck/
├── story.md     front matter with `mode: deck`, then sections, steps and chart/table blocks
├── deck.yaml    the categories
├── story.py     optional: metrics, derived datasets, card thumbnails
├── figures/     optional: custom figure modules
└── data/
```

Build it with `uv run subscout build basin-deck --out _site`, and check it with `uv run subscout fit _site`.
`--mode deck` on the command line overrides the front matter.

The Markdown is the story format unchanged: front matter, `::: step` blocks, `chart` and `table` blocks, `use:` to
show another state of an earlier figure, `::: appendix`. A folder can therefore be built in either mode. Deck mode
does not read `arc`, `register`, `horizon` or a step's `beat=` and `layout=`.

## deck.yaml

```yaml
brand: Basin fundamentals            # top-left name; default: short_title, then title
start: Start with heat               # label of the first button on the landing page
noindex: true                        # ask search engines not to index the pages
labels:                              # what the two counters on the landing page say
  views: views, each a state of a computed figure
  figures: figures computed from their equations
footer: One line of Markdown for the foot of the landing page (credits, terms).
full: [figures/section.js]           # custom modules drawn across the slide
categories:
  - slug: heat                       # the page is heat.html
    title: Heat from below
    blurb: One sentence for the card and the cover.
    sections: ["Heat from below"]    # `##` headings of story.md
```

Every `##` section of story.md belongs to exactly one category, and the categories keep the order of the file; the
build fails on a section that is missing or claimed twice and warns when the order differs.

## How the Markdown becomes slides

- Text before the first `##` is the lead of the landing page.
- Each category page opens on a **cover**: its number, title, blurb and a list of its topics, each a link.
- Each `::: step` is one slide. A `### heading` inside a step names a **topic**: it is the slide's heading, and it
  carries to the steps after it until the next one. The figure's own `title` and `subtitle` sit above the figure.
- Text between steps is a slide of text alone, used to open a section. A `chart` or `table` block between steps is
  a slide of its own, headed by its title.
- Consecutive slides that show the same figure (`use:`) keep it on screen and move it between states.
- `::: appendix` content goes to the basis page.

## Masters

A slide has one of three masters.

| Master | Used for | Text |
|---|---|---|
| `side` | a figure that is as tall as it is wide: curves, columns, bars | beside the figure, in a column at the right |
| `full` | a figure wider than it is high: a section, a map, a heatmap, a chart on a long axis | beneath the figure, in two columns |
| text | the opening of a section, a table | alone |

A figure's master is, in order: `master: side | full` on its block; `full` if its module is listed under `full` in
deck.yaml; `full` for a map, a network, a heatmap or a declared `aspect` of 1.6 or more; otherwise `side`. A
chart of many rows stays `side`: the side master is the tall one.

**Custom figures** receive `opts.layout` (`side` or `full`) and `opts.vhShare`, the share of the screen's height
the slide gives them, read on every draw, and should fill it. `opts.states` lists every state the deck will ask
for. **Built-in chart forms** keep their own proportions and are scaled into the box.

## The concept card

A topic that teaches a named process can carry a card: the name the literature gives the process, its governing
relation, and what the symbols stand for. The card heads the text of every slide of the topic, so the relation
stays in view while the figure moves between states.

````
::: step
### At rest, each component obeys its own barometric law

```concept
name: Gravity and chemical equilibrium
formula:
  - 'f_i(h) = f_i(h_0)\,\exp\!\left(-\dfrac{M_i g (h-h_0)}{RT}\right)'
where: '$f_i$ fugacity of component i, $M_i$ its molar mass, $h$ height'
```

Prose of the slide.
:::
````

- `name`: the academic name, shown small above the formula. The `###` heading stays the point being taught.
- `formula`: LaTeX, one string or a list. It is turned into MathML when the deck is built; the page loads no
  mathematics script. Single-quoted YAML keeps the backslashes as written.
- `where`: one line of text; symbols between dollar signs are set as mathematics.
- The card lasts until the next `###` topic. A later step of the same topic may carry a card of its own, which
  replaces it from that step on.
- The card takes room from the prose, and the fit gate applies to both. Two formulas and one line of symbols is
  about what a slide beside a figure holds.
- On the full master the card is one strip across both columns of text, name and formulas side by side, and the
  line of symbols is left out; the text beneath has the height it has without a card.

A fenced `concept` block is read in deck mode only.

## Text must fit

Nothing on a slide scrolls. Text that does not fit its box steps down in size, to a floor of 0.8 of its size, and
what still overflows fails the fit gate. Prose written for a scrolling page is usually too long for a slide:
two or three sentences beside a figure, four or five beneath one. `subscout fit` lists the slides whose text had
to shrink below 0.88, as the ones to shorten first. A table shows its first `fold` rows and says how many there
are; it does not unfold.

## Pages and movement

- `index.html`: title, lead, counters and KPIs, a card per category. `story.py` may draw the cards:
  `thumbnails(data) -> {slug: "<svg …>"}`; a category without one shows its number.
- `<slug>.html`: the slides. Arrow keys, Page Up and Page Down, space, Home and End move; a bar of ticks grouped
  by topic shows the position; `i` opens the figure's source, units, confidence and notes, which are not on the
  slide itself. Each slide has an address (`heat.html#4`, `#last`). The last slide leads to the next category.
- `basis.html`: the appendix text, sources, every figure with its source and confidence, every number in the text.

## The fit gate

`uv run subscout fit _site` serves the built deck, visits every slide at 1366×768, 1600×900 and 1920×1080 and
fails on text that overflows, a page that scrolls, a figure that did not draw or is larger than its box, or a
console error. `--size`, `--pages`, `--slides` and `--dark` narrow or change the run; `--shots <folder>` keeps a
screenshot of every slide visited. It needs Playwright among the development dependencies.

## Not yet in deck mode

- Export pages (`export:` on a block is ignored), the units toggle and a phone layout.
- Speaker notes, a presenter view, and export of the slides to PDF or PowerPoint.
- Teaching parts: what a category sets out to teach, what it assumes, questions at its end, a glossary.
- A word limit per master checked at build time; the fit gate is the only check on length.
