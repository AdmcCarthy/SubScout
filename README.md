# SubScout

A framework for consistent, themed data narratives. One Markdown story and its data are built in one
of two modes:

- **Story**: a data story told as journalism. One argument on one page, with two views: **Read**, a
  scrollytelling article with charts and maps that change as you scroll, and **Present**, the same
  story stepped through on a screen.
- **Deck**: presentation and teaching material. A landing page of categories and one page per
  category, in which each view is a slide the size of the screen and nothing scrolls.

The look, colour logic, chart defaults, number tracing and truth checks are shared by both modes, so
each new dataset comes out in the same house style. Stories are published on GitHub Pages.

```bash
uv run subscout build my-story --out _site   # the mode is `mode:` in the front matter; a story by default
uv run subscout fit _site                    # deck mode: every slide holds on one screen
```

The formats are set out in [styleguide/story-format.md](styleguide/story-format.md) and
[styleguide/deck-format.md](styleguide/deck-format.md); `examples/demo` is a story and `examples/deck` a
deck, on the same synthetic data.

> Status: early. v0.1 is the colour engine and design tokens; layout, charts, the state engine and
> the build follow.

## Colour

All colours are generated from [`src/subscout/tokens/colour.toml`](src/subscout/tokens/colour.toml):

- **Seven anchor hues.** Core: `fjord`, `shale`, `slate`, `cobalt`. Highlights: `malachite`, `ochre`, `haematite`.
- **One 15-step lightness ladder per scheme** (light and dark), shared by every hue.
- **A gaussian chroma curve**, so colours are richest in the mid-tones.
- **Fixed step roles**: fills, borders, text, surface.
- **APCA contrast rules**, checked by the test suite for every hue in both schemes.

To add a colour you only add an anchor (hue and chroma). The new colour gets the ladder, roles and
contrast checks automatically.

```bash
uv run subscout tokens   # regenerate src/subscout/runtime/css/tokens.{css,json}
uv run subscout audit    # contrast and colour-vision-deficiency report
uv run pytest
```

Data palettes use the "context in grey, story in colour" approach, plus:

- a curated categorical order, checked for colour-vision-deficiency separation
- sequential ramps (`fjord`, `cobalt`, `shale`)
- a cobalt ↔ ochre diverging scale

## The header band

A story's hero can open on the seismic itself instead of the drawn horizon motif: a window of a real
section with its interpreted surfaces, the story's own surface in the highlight colour, drawn in the
page's tokens (`runtime/js/horizon-band.js`). The story supplies one JSON file in the contract of
[docs/header-contract.md](docs/header-contract.md) and names it in the front matter
(`horizon: { data: header, highlight: ... }`); the build reserves the band's height, copies the file
to the site and lists it in the appendix with its attribution and confidence. `horizon: true` keeps
the motif.

## Symbols

Well, wellbore and installation symbols after the [Sodir Geostandard](https://www.sodir.no/globalassets/2-force/2022/dokumenter/geostandard-ekstern.pdf)
(3.4 and 3.5), redrawn: shape-first, composed from layers, one ink on any background. Rules in [styleguide/wellbores.md](styleguide/wellbores.md),
data in [`symbols.toml`](src/subscout/tokens/symbols.toml), review sheet at `site/symbols/`.

```bash
uv run subscout symbols   # regenerate src/subscout/runtime/js/symbols-data.js and symbols.json
```

## Credits

The palette method (lightness ladder, gaussian chroma, step roles, APCA targets and the data-palette
algorithms) is ported from the [Equinor Design System colour palette generator](https://github.com/equinor/design-system/tree/main/apps/eds-color-palette-generator),
© Equinor ASA, MIT licence. SubScout is an independent project and is not affiliated with or endorsed
by Equinor.

## Licence and acknowledgement

MIT License with Acknowledgement ([LICENSE](LICENSE)): the MIT terms plus one condition. Anything built with this work says so,
visibly and in plain words, and does not imply endorsement: "Built with SubScout by Adam McCarthy (https://github.com/AdmcCarthy/SubScout)". The wording is custom, so
the licence is not OSI-approved. Third-party data and vendored code keep their own terms.
