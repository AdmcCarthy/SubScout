"""Which layout a scrolly section gets.

`side`: text left, figure right. `lane`: the figure spans the page, the cards scroll in a lane at its left.
`full`: the figure at full width, text below it. A `layout=` on the section's steps wins; otherwise the
figures decide.

A figure wants `full` when its detail needs width: a map, a network, a heatmap, a custom figure that
declares `detail: high` or a `min_width` the side column cannot give, a wide `aspect`, or a bar, dot or
diverging chart with many rows. Any one such figure takes the whole section, so the figure does not
change size between steps.
"""

from __future__ import annotations

LAYOUTS = ("side", "lane", "full")
ALIASES = {"wide": "lane"}
SIDE_WIDTH = 650  # px a figure gets in the side column of a 1,100 px page
MAX_SIDE_ROWS = 12  # more rows than this wants the room
WIDE_ASPECT = 1.6
ALWAYS_FULL = {"map", "network", "heat"}
ROW_CHARTS = {"bars", "dots", "diverging"}


def normalise(value: str | None) -> str | None:
    """The layout named on a step (`wide` is the old name for `lane`), or None; unknown names raise."""
    if not value:
        return None
    v = ALIASES.get(value, value)
    if v not in LAYOUTS:
        raise ValueError(f"layout '{value}' is not one of {list(LAYOUTS) + sorted(ALIASES)}")
    return v


def _rows(spec: dict, payload) -> int:
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict) and "rows" in payload:
        return len(payload["rows"])
    return 0


def wants_full(spec: dict, payload=None) -> str | None:
    """Why this figure needs the full width, or None."""
    t = spec.get("type")
    if t in ALWAYS_FULL:
        return f"a {t} needs the width"
    if spec.get("detail") == "high":
        return "it declares high detail"
    if float(spec.get("min_width") or 0) > SIDE_WIDTH:
        return f"it needs {spec['min_width']} px and the side column gives {SIDE_WIDTH}"
    if float(spec.get("aspect") or 0) >= WIDE_ASPECT:
        return f"its aspect ratio is {spec['aspect']}:1"
    if t in ROW_CHARTS and _rows(spec, payload) > MAX_SIDE_ROWS:
        return f"it has {_rows(spec, payload)} rows"
    return None


def choose(explicit: str | None, figures: list[tuple[dict, object]]) -> tuple[str, str]:
    """(layout, reason) for one section. `figures` is each figure's (spec, prepared payload)."""
    if explicit:
        return explicit, "set on the step"
    for spec, payload in figures:
        why = wants_full(spec, payload)
        if why:
            return "full", why
    return "side", "simple figures read well beside the text"
