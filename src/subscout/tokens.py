"""Build design tokens (CSS custom properties + JSON) from the colour config.

Naming
------
--ss-<hue>-<step>       raw scale, e.g. --ss-fjord-9          (avoid in stories)
--ss-<tone>-<role>      semantic, e.g. --ss-accent-fill-emphasis
--ss-<alias>            page-level shortcuts: --ss-canvas, --ss-text, ...
--ss-data-*             chart colours: context, highlight, story-N, cat-N, seq-N, div-N (from the
                        active preset) and named ramps seq-<name>-N, div-<name>-N

Theme switching follows EDS: `data-colour-scheme="light|dark"` on <html>,
falling back to the reader's system preference.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import colour as C

# page-level aliases -> (tone, role)
ALIASES = {
    "canvas": ("neutral", "fill-muted"),
    "surface": ("neutral", "surface"),
    "surface-raised": ("neutral", "fill-muted-hover"),
    "text": ("neutral", "text-strong"),
    "text-subtle": ("neutral", "text-subtle"),
    "text-muted": ("neutral", "text-muted"),
    "border-subtle": ("neutral", "border-subtle"),
    "border": ("neutral", "border"),
    "border-strong": ("neutral", "border-strong"),
    "accent": ("accent", "fill-emphasis"),
    "accent-soft": ("accent", "fill-muted"),
    "on-accent": ("accent", "text-on-emphasis"),
    "link": ("accent", "fill-emphasis-pressed"),
    "focus": ("info", "fill-emphasis"),
    "grid": ("structure", "border-subtle"),
    "axis": ("structure", "border"),
}


def scheme_tokens(scheme: C.Scheme, cfg: dict | None = None) -> dict[str, str]:
    cfg = cfg or C.load_config()
    t: dict[str, str] = {}
    scales = {h: C.scale_hex(h, scheme, cfg) for h in C.hue_names(cfg)}
    for hue, steps in scales.items():
        for i, hx in enumerate(steps, 1):
            t[f"{hue}-{i}"] = hx
    for tone, hue in cfg["tones"][scheme].items():
        for role, step in cfg["roles"].items():
            t[f"{tone}-{role}"] = scales[hue][step - 1]
    for alias, (tone, role) in ALIASES.items():
        t[alias] = t[f"{tone}-{role}"]
    t.update(surface_tokens(cfg["surfaces"]["default"], scheme, cfg))  # default room
    t["data-context"] = C.context(scheme, cfg)
    for name in cfg["data"]["sequential"]:
        for i, hx in enumerate(C.sequential(name, scheme, cfg), 1):
            t[f"data-seq-{name}-{i}"] = hx
    for name in cfg["data"]["diverging"]:
        for i, hx in enumerate(C.diverging(name, scheme, cfg), 1):
            t[f"data-div-{name}-{i}"] = hx
    t.update(preset_tokens(None, scheme, cfg))
    return t


def preset_tokens(name: str | None, scheme: C.Scheme, cfg: dict | None = None) -> dict[str, str]:
    """Data tokens that a preset sets: highlight, story-N, cat-N, seq-N, div-N."""
    cfg = cfg or C.load_config()
    p = C.preset(name, cfg)
    t = {"data-highlight": C.highlight(scheme, name, cfg), "data-cat-count": str(len(p["categorical"]))}
    for i, hx in enumerate(C.story(scheme, name, cfg), 1):
        t[f"data-story-{i}"] = hx
    cat = C.categorical(scheme, name, cfg)
    for i in range(1, MAX_CAT + 1):
        # unused slots fall back to context grey ("Other")
        t[f"data-cat-{i}"] = cat[i - 1] if i <= len(cat) else C.context(scheme, cfg)
    for i, hx in enumerate(C.sequential(p["sequential"], scheme, cfg), 1):
        t[f"data-seq-{i}"] = hx
    for i, hx in enumerate(C.diverging(p["diverging"], scheme, cfg), 1):
        t[f"data-div-{i}"] = hx
    return t


MAX_CAT = 5


def _block(selector: str, tokens: dict[str, str], scheme: str, indent: str = "") -> str:
    lines = [f"{indent}{selector} {{", f"{indent}  color-scheme: {scheme};"]
    lines += [f"{indent}  --ss-{k}: {v};" for k, v in tokens.items()]
    lines.append(f"{indent}}}")
    return "\n".join(lines)


def _vars(selector: str, tokens: dict[str, str], indent: str = "") -> str:
    lines = [f"{indent}{selector} {{"] + [f"{indent}  --ss-{k}: {v};" for k, v in tokens.items()]
    return "\n".join([*lines, f"{indent}}}"])


def _preset_blocks(cfg: dict) -> list[str]:
    """Per-preset overrides. Work on <html> or any container; dark rules out-rank light ones."""
    out = ['/* data-colour presets: data-palette="<name>" on <html> or any container */']
    for name in C.preset_names(cfg):
        sel = f'[data-palette="{name}"]'
        light, dark = preset_tokens(name, "light", cfg), preset_tokens(name, "dark", cfg)
        not_light = ':root:not([data-colour-scheme="light"])'
        forced = '[data-colour-scheme="dark"]'
        out += [
            _vars(f"{sel}, :root{sel}", light),
            "@media (prefers-color-scheme: dark) {\n"
            + _vars(f"{not_light} {sel}, {not_light}{sel}", dark, "  ")
            + "\n}",
            _vars(f"{forced} {sel}, {forced}{sel}", dark),
        ]
    return out


SURFACE_ALIASES = {"canvas": "canvas", "surface": "surface", "raised": "surface-raised"}


def surface_tokens(name: str, scheme: C.Scheme, cfg: dict | None = None) -> dict[str, str]:
    """Alias values a surface option sets (the EDS baseline sets its generated values explicitly)."""
    cfg = cfg or C.load_config()
    return {SURFACE_ALIASES[r]: hx for r, hx in C.surfaces(name, scheme, cfg).items()}


def _surface_blocks(cfg: dict) -> list[str]:
    """Surface overrides. Order and specificity let a light or dark panel sit inside either theme."""
    out = ['/* surfaces: data-surface="<name>" on <html> or any container */']
    nl = ':root:not([data-colour-scheme="light"])'
    for name in C.surface_names(cfg):
        light, dark = surface_tokens(name, "light", cfg), surface_tokens(name, "dark", cfg)
        sel = f'[data-surface="{name}"]'
        out += [
            _vars(f"{sel}, :root{sel}", light),
            "@media (prefers-color-scheme: dark) {\n" + _vars(f"{nl} {sel}, {nl}{sel}", dark, "  ") + "\n}",
            _vars(f'[data-colour-scheme="dark"] {sel}, [data-colour-scheme="dark"]{sel}', dark),
            _vars(f':root [data-colour-scheme="light"]{sel}, :root[data-colour-scheme="light"]{sel}', light),
        ]
    return out


def build_css(cfg: dict | None = None) -> str:
    cfg = cfg or C.load_config()
    light, dark = scheme_tokens("light", cfg), scheme_tokens("dark", cfg)
    return (
        "\n\n".join(
            [
                "/* SubScout colour tokens. GENERATED by `subscout tokens` from tokens/colour.toml. */",
                _block(
                    ':root, :root[data-colour-scheme="light"], [data-colour-scheme="light"]', light, "light"
                ),
                "@media (prefers-color-scheme: dark) {\n"
                + _block(':root:not([data-colour-scheme="light"])', dark, "dark", "  ")
                + "\n}",
                _block(':root[data-colour-scheme="dark"], [data-colour-scheme="dark"]', dark, "dark"),
                *_preset_blocks(cfg),
                *_surface_blocks(cfg),
            ]
        )
        + "\n"
    )


def build_json(cfg: dict | None = None) -> dict:
    cfg = cfg or C.load_config()
    return {
        "light": scheme_tokens("light", cfg),
        "dark": scheme_tokens("dark", cfg),
        "default_preset": cfg["data"]["default_preset"],
        "default_surface": cfg["surfaces"]["default"],
        "surfaces": {
            n: {
                "label": cfg["surfaces"][n]["label"],
                "note": cfg["surfaces"][n]["note"],
                "light": C.surfaces(n, "light", cfg),
                "dark": C.surfaces(n, "dark", cfg),
            }
            for n in C.surface_names(cfg)
        },
        "presets": {
            n: {
                "label": cfg["presets"][n]["label"],
                "note": cfg["presets"][n]["note"],
                "categorical_count": len(cfg["presets"][n]["categorical"]),
                "light": preset_tokens(n, "light", cfg),
                "dark": preset_tokens(n, "dark", cfg),
            }
            for n in C.preset_names(cfg)
        },
    }


def default_out() -> Path:
    return Path(__file__).parent / "runtime" / "css"


def write(out_dir: Path | None = None, cfg: dict | None = None) -> list[Path]:
    out_dir = Path(out_dir or default_out())
    out_dir.mkdir(parents=True, exist_ok=True)
    css, js = out_dir / "tokens.css", out_dir / "tokens.json"
    css.write_text(build_css(cfg), encoding="utf-8")
    js.write_text(json.dumps(build_json(cfg), indent=1) + "\n", encoding="utf-8")
    return [css, js]
