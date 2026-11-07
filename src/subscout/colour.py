"""SubScout colour engine.

Generates every colour from `tokens/colour.toml`. The scale method is a port of
the Equinor Design System colour palette generator (MIT, (c) Equinor ASA):

    colour(step) = oklch(L[step], gaussian(L[step]) * C_anchor, H_anchor)

followed by CSS Color 4 style gamut mapping into sRGB. Data palettes
(sequential, diverging, generated categorical) follow the same generator's
`dataviz.ts`. Contrast is APCA-W3 0.0.98G; colour-vision deficiency (CVD) is
simulated with Brettel (protan, deutan) and Brettel (tritan).
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from typing import Literal

from coloraide import Color

Scheme = Literal["light", "dark"]
SCHEMES: tuple[Scheme, ...] = ("light", "dark")
CVD_TYPES = ("protan", "deutan", "tritan")


# ------------------------------------------------------------------ config


@cache
def load_config(path: str | None = None) -> dict:
    """Read the colour TOML (the packaged one unless a path is given)."""
    if path:
        return tomllib.loads(Path(path).read_text(encoding="utf-8"))
    text = resources.files("subscout").joinpath("tokens/colour.toml").read_text("utf-8")
    return tomllib.loads(text)


# ------------------------------------------------------------------ primitives


def gaussian(x: float, mean: float = 0.6, std_dev: float = 2.0) -> float:
    """EDS chroma curve: exp(-25/std_dev * (x - mean)^2)."""
    return math.exp((-25 / std_dev) * (x - mean) ** 2)


def oklch_to_srgb(l: float, c: float, h: float) -> Color:
    """OKLCH -> sRGB, reducing chroma (CSS Color 4 method) when out of gamut."""
    return Color("oklch", [l, c, h]).fit("srgb", method="minde-chroma").convert("srgb")


def to_hex(colour: Color) -> str:
    return colour.convert("srgb").clip().to_string(hex=True)


def _apca_y(colour: Color) -> float:
    r, g, b = (min(1.0, max(0.0, v)) for v in colour.convert("srgb").coords())
    y = 0.2126729 * r**2.4 + 0.7151522 * g**2.4 + 0.0721750 * b**2.4
    return y if y > 0.022 else y + (0.022 - y) ** 1.414


def apca(fg: Color | str, bg: Color | str) -> float:
    """APCA-W3 0.0.98G lightness contrast |Lc| of text `fg` on background `bg`."""
    fg, bg = Color(fg), Color(bg)
    yt, yb = _apca_y(fg), _apca_y(bg)
    if abs(yb - yt) < 0.0005:
        return 0.0
    if yb > yt:  # dark text on light background
        c = (yb**0.56 - yt**0.57) * 1.14
        return 0.0 if c < 0.1 else (c - 0.027) * 100
    c = (yb**0.65 - yt**0.62) * 1.14  # light text on dark background
    return 0.0 if c > -0.1 else abs((c + 0.027) * 100)


def simulate_cvd(colour: Color | str, kind: str) -> Color:
    return Color(colour).filter(kind, method="brettel").convert("srgb")


def delta_e_ok(a: Color | str, b: Color | str) -> float:
    return Color(a).delta_e(Color(b), method="ok")


def worst_case_delta_e(a: Color | str, b: Color | str) -> float:
    """Smallest OK deltaE between two colours across normal vision and 3 CVD types."""
    ds = [delta_e_ok(a, b)]
    ds += [delta_e_ok(simulate_cvd(a, k), simulate_cvd(b, k)) for k in CVD_TYPES]
    return min(ds)


# ------------------------------------------------------------------ scales


def hue_names(cfg: dict | None = None) -> list[str]:
    return list((cfg or load_config())["hues"])


def scale(hue: str, scheme: Scheme, cfg: dict | None = None) -> list[Color]:
    """The 15-step scale for a named hue in a scheme."""
    cfg = cfg or load_config()
    _, chroma, h = cfg["hues"][hue]["anchor"]
    g = cfg["scale"]["gaussian"][scheme]
    return [oklch_to_srgb(l, gaussian(l, g["mean"], g["std_dev"]) * chroma, h) for l in cfg["scale"][scheme]]


def scale_hex(hue: str, scheme: Scheme, cfg: dict | None = None) -> list[str]:
    return [to_hex(c) for c in scale(hue, scheme, cfg)]


def tone_hue(tone: str, scheme: Scheme, cfg: dict | None = None) -> str:
    return (cfg or load_config())["tones"][scheme][tone]


def role_colour(tone: str, role: str, scheme: Scheme, cfg: dict | None = None) -> Color:
    cfg = cfg or load_config()
    step = cfg["roles"][role]
    return scale(tone_hue(tone, scheme, cfg), scheme, cfg)[step - 1]


def step_colour(hue: str, step: int, scheme: Scheme, cfg: dict | None = None) -> Color:
    return scale(hue, scheme, cfg)[step - 1]


# ------------------------------------------------------------------ contrast audit


@dataclass(frozen=True)
class ContrastResult:
    scheme: Scheme
    tone: str
    fg: str
    bg: str
    target: float
    lc: float

    @property
    def passed(self) -> bool:
        return self.lc >= self.target


def contrast_audit(cfg: dict | None = None) -> list[ContrastResult]:
    """Check every [[contrast]] rule for every tone it applies to, in both schemes."""
    cfg = cfg or load_config()
    out = []
    for scheme in SCHEMES:
        tones = list(cfg["tones"][scheme])
        for rule in cfg["contrast"]:
            applies = tones if rule["tones"] == "all" else rule["tones"]
            for tone in applies:
                fg = role_colour(tone, rule["fg"], scheme, cfg)
                bg = role_colour(tone, rule["bg"], scheme, cfg)
                out.append(ContrastResult(scheme, tone, rule["fg"], rule["bg"], rule["lc"], apca(fg, bg)))
    return out


# ------------------------------------------------------------------ data palettes


def _hue_angle(hue: str, cfg: dict) -> float:
    return cfg["hues"][hue]["anchor"][2]


def _hue_chroma(hue: str, cfg: dict) -> float:
    return cfg["hues"][hue]["anchor"][1]


def sequential(name: str, scheme: Scheme, cfg: dict | None = None) -> list[str]:
    """Single-hue ramp, low -> high, low values near the page background.

    Monotonic lightness, gaussian chroma (EDS dataviz.ts generateSequentialScale).
    """
    cfg = cfg or load_config()
    spec = cfg["data"]["sequential"][name]
    h = _hue_angle(spec["hue"], cfg)
    start, end = spec[f"range_{scheme}"]
    mean = cfg["scale"]["gaussian"][scheme]["mean"]
    n = spec["steps"]
    out = []
    for i in range(n):
        l = start + (end - start) * (i / (n - 1))
        c = spec["chroma_peak"] * gaussian(l, mean, 2)
        out.append(to_hex(oklch_to_srgb(l, c, h)))
    return out


def diverging(name: str, scheme: Scheme, cfg: dict | None = None) -> list[str]:
    """Two hue ends meeting at a neutral near the background (EDS generateDivergingScale)."""
    cfg = cfg or load_config()
    spec = cfg["data"]["diverging"][name]
    lo, hi = _hue_angle(spec["low"], cfg), _hue_angle(spec["high"], cfg)
    n_l, e_l = spec[f"neutral_{scheme}"], spec[f"end_{scheme}"]
    n = spec["steps"]
    out = []
    for i in range(n):
        p = i / (n - 1)
        d = abs(p - 0.5) * 2
        out.append(to_hex(oklch_to_srgb(n_l + (e_l - n_l) * d, spec["chroma"] * d, lo if p <= 0.5 else hi)))
    return out


def preset_names(cfg: dict | None = None) -> list[str]:
    return list((cfg or load_config())["presets"])


def preset(name: str | None = None, cfg: dict | None = None) -> dict:
    """A data-colour preset (default if `name` is None)."""
    cfg = cfg or load_config()
    return cfg["presets"][name or cfg["data"]["default_preset"]]


def _entries(entries: list, scheme: Scheme, cfg: dict) -> list[str]:
    idx = 1 if scheme == "light" else 2
    return [to_hex(step_colour(e[0], e[idx], scheme, cfg)) for e in entries]


def story(scheme: Scheme, name: str | None = None, cfg: dict | None = None) -> list[str]:
    """Quiet on-identity palette (1-3 series beside grey context). Always direct-label."""
    cfg = cfg or load_config()
    return _entries(preset(name, cfg)["story"], scheme, cfg)


def categorical(scheme: Scheme, name: str | None = None, cfg: dict | None = None) -> list[str]:
    """Identity palette in fixed order. Passes the six checks."""
    cfg = cfg or load_config()
    return _entries(preset(name, cfg)["categorical"], scheme, cfg)


def highlight(scheme: Scheme, name: str | None = None, cfg: dict | None = None) -> str:
    cfg = cfg or load_config()
    return _entries([preset(name, cfg)["highlight"]], scheme, cfg)[0]


# Six-checks thresholds for identity palettes (dataviz method; Machado 2009 CVD).
BAND = {"light": (0.43, 0.77), "dark": (0.48, 0.67)}
CHROMA_FLOOR = 0.10
CVD_TARGET, CVD_FLOOR = 8.0, 6.0  # OKLab deltaE x100, adjacent pairs, protan/deutan
NORMAL_FLOOR = 15.0
CONTRAST_MIN = 3.0  # WCAG 2 vs surface


def categorical_checks(colours: list[str], scheme: Scheme, surface: str) -> dict:
    """Run the identity-palette checks; returns per-check values and an overall `ok`."""
    lch = [Color(c).convert("oklch") for c in colours]
    lo, hi = BAND[scheme]
    adj = list(zip(colours[:-1], colours[1:], strict=True))

    def de(a: str, b: str, kind: str | None = None) -> float:
        ca, cb = Color(a), Color(b)
        if kind:
            ca, cb = ca.filter(kind, method="machado"), cb.filter(kind, method="machado")
        return ca.delta_e(cb, method="ok") * 100

    res = {
        "band": all(lo <= c["lightness"] <= hi for c in lch),
        "chroma": min(c["chroma"] for c in lch),
        "cvd": min(de(a, b, k) for a, b in adj for k in ("protan", "deutan")),
        "normal": min(de(a, b) for a, b in adj),
        "contrast": min(Color(c).contrast(surface, method="wcag21") for c in colours),
    }
    res["ok"] = (
        res["band"]
        and res["chroma"] >= CHROMA_FLOOR
        and res["cvd"] >= CVD_FLOOR
        and res["normal"] >= NORMAL_FLOOR
        and res["contrast"] >= CONTRAST_MIN
    )
    return res


def context(scheme: Scheme, cfg: dict | None = None) -> str:
    """Grey for context/background series (shared by all presets)."""
    cfg = cfg or load_config()
    spec = cfg["data"]["context"]
    return to_hex(step_colour(spec["hue"], spec[scheme], scheme, cfg))


def generate_categorical(
    count: int,
    scheme: Scheme,
    seed_hues: list[str] | None = None,
    chroma: float = 0.14,
    lightness: float | None = None,
    cfg: dict | None = None,
) -> list[str]:
    """Generated categorical palette for when a chart genuinely needs many series.

    Port of EDS generateCategoricalPalette: hues from seeds, or evenly spaced
    round the OKLCH wheel phase-aligned to the first seed; greedy farthest-point
    ordering under worst-case CVD distance; then a lightness ramp whose amplitude
    is chosen to maximise worst-case CVD separation (also greyscale-legible).
    """
    cfg = cfg or load_config()
    base_l = lightness if lightness is not None else (0.62 if scheme == "light" else 0.72)
    seed_names = seed_hues or ["fjord", "haematite", "ochre", "malachite", "cobalt"]
    seeds = [_hue_angle(h, cfg) for h in seed_names]
    if count <= len(seeds):
        hues = seeds[:count]
    else:
        hues = [(seeds[0] + 360 / count * i) % 360 for i in range(count)]

    flat = [oklch_to_srgb(base_l, chroma, h) for h in hues]
    order = [0]
    remaining = list(range(1, len(hues)))
    while remaining:
        best = max(remaining, key=lambda i: min(worst_case_delta_e(flat[i], flat[o]) for o in order))
        order.append(best)
        remaining.remove(best)
    ordered = [hues[i] for i in order]

    def build(amp: float) -> list[Color]:
        n = len(ordered)
        out = []
        for i, h in enumerate(ordered):
            t = i / (n - 1) if n > 1 else 0.5
            out.append(oklch_to_srgb(min(0.85, max(0.35, base_l + amp * (t - 0.5) * 2)), chroma, h))
        return out

    def worst(cols: list[Color]) -> float:
        return min(
            (worst_case_delta_e(a, b) for i, a in enumerate(cols) for b in cols[i + 1 :]),
            default=math.inf,
        )

    best_cols = max((build(a) for a in (0.1, 0.16, 0.22, 0.28)), key=worst)
    return [to_hex(c) for c in best_cols]


def palette_audit(colours: list[str], background: str) -> dict:
    """Worst-case pairwise CVD deltaE and lowest APCA contrast against a background."""
    pairs = [(worst_case_delta_e(a, b), a, b) for i, a in enumerate(colours) for b in colours[i + 1 :]]
    worst = min(pairs) if pairs else (math.inf, None, None)
    return {
        "min_cvd_delta_e": worst[0],
        "closest_pair": worst[1:],
        "min_lc_on_background": min(apca(c, background) for c in colours),
    }


# ------------------------------------------------------------------ surfaces

SURFACE_ROLES = ("canvas", "surface", "raised")


def surface_names(cfg: dict | None = None) -> list[str]:
    return list((cfg or load_config())["surfaces"].keys() - {"default"})


def surfaces(name: str, scheme: Scheme, cfg: dict | None = None) -> dict[str, str]:
    """Canvas/surface/raised hexes for a surface option (EDS baseline if no override)."""
    cfg = cfg or load_config()
    spec = cfg["surfaces"][name].get(scheme)
    if not spec:
        return {
            "canvas": to_hex(role_colour("neutral", "fill-muted", scheme, cfg)),
            "surface": to_hex(role_colour("neutral", "surface", scheme, cfg)),
            "raised": to_hex(role_colour("neutral", "fill-muted-hover", scheme, cfg)),
        }
    h = _hue_angle(spec["hue"], cfg)
    return {r: to_hex(oklch_to_srgb(spec[r][0], spec[r][1], h)) for r in SURFACE_ROLES}


def surface_audit(cfg: dict | None = None) -> list[dict]:
    """Contrast of text (canvas and surface) and every data colour (surface) for each surface option."""
    cfg = cfg or load_config()
    rows = []
    for name in surface_names(cfg):
        for scheme in SCHEMES:
            bgs = surfaces(name, scheme, cfg)
            text = {
                "text": (role_colour("neutral", "text-strong", scheme, cfg), 90),
                "text-subtle": (role_colour("neutral", "text-subtle", scheme, cfg), 75),
                "text-muted": (role_colour("neutral", "text-muted", scheme, cfg), 60),
                "context": (context(scheme, cfg), 30),
            }
            for p in preset_names(cfg):
                text[f"{p}:highlight"] = (highlight(scheme, p, cfg), 45)
                for i, c in enumerate(story(scheme, p, cfg), 1):
                    text[f"{p}:story-{i}"] = (c, 30)
                for i, c in enumerate(categorical(scheme, p, cfg), 1):
                    text[f"{p}:cat-{i}"] = (c, 30)
            # text must read on canvas and surface; data marks sit on figure surfaces only
            data_keys = {k for k in text if ":" in k or k == "context"}
            for bg_role in ("canvas", "surface"):
                for what, (fg, target) in text.items():
                    if bg_role == "canvas" and what in data_keys:
                        continue
                    lc = apca(fg, bgs[bg_role])
                    rows.append(
                        {
                            "surface": name,
                            "scheme": scheme,
                            "bg": bg_role,
                            "fg": what,
                            "lc": lc,
                            "target": target,
                        }
                    )
    return rows
