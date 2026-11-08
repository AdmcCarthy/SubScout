# Export contract (version 1)

For each chart block with `export:`, the build writes `export/<figure id>/payload.json`. A renderer (Plate) needs nothing
else from the story to draw the figure again at any size, in any theme. SubScout's proof page embeds the same object.

```jsonc
{
  "contract": { "name": "subscout-export", "version": 1 },
  "id": "journey",                       // figure id
  "story": { "title", "kicker", "palette", "surface", "byline", "url" },
  "meta":  { "title", "subtitle", "source", "accessed", "unit",
             "confidence": "derived", "confidence_label": "Derived", "notes", "exception": {rule, reason} | null },
  "facts": [["Source", "Sodir, ..., 2026-11-07"], ["Units", "..."], ["Confidence", "Derived"]],  // footer strip
  "credit": "Adam McCarthy · https://...",
  "runtime": "runtime",                  // site-relative folder with css/ and js/ (tokens, charts, subscout.js)
  "fig":   { "spec": {...}, "data": ... },   // figure spec as in story.md, with resolved numbers in titles
  "datasets": { "name": [...] },         // for custom and map figures
  "states": [ { "name", "slug", "state": {...} } ],   // the figure's own state, then each `use:` step that changes it
  "units": "sm3",                        // story default unit
  "sizes": { "slide": {label, w, h}, ... }, "themes": ["light", "dark"], "scale": 3, "groups": null
}
```

Rules:
- Additive changes keep the version; renaming or removing a key bumps `CONTRACT_VERSION` and is a breaking release.
- Rendering code must load figure modules and chart code from `<site>/<runtime>` and `<site>/<spec.module>`; it must not
  assume anything else about the page.
- Custom figures receive `opts.export` (always), `opts.height()` and, under Plate, `opts.print` and `opts.pixelRatio`.
