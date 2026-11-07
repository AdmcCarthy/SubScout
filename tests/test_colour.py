"""Colour engine: parity with EDS, contrast rules, data palette separation."""

import pytest

from subscout import colour as C
from subscout import tokens


def test_parity_with_eds_generator():
    # Values shown by the EDS palette generator's contrast page for Moss Green.
    light = C.scale_hex("fjord", "light")
    assert light[12] == "#1e383a"  # step 13, text primary
    assert light[14] == "#ffffff"  # step 15, surface


def test_every_hue_has_15_steps_in_both_schemes():
    for hue in C.hue_names():
        for scheme in C.SCHEMES:
            assert len(C.scale_hex(hue, scheme)) == 15


def test_light_ladder_is_monotonic_through_text_steps():
    ladder = C.load_config()["scale"]["light"]
    assert all(a > b for a, b in zip(ladder[:12], ladder[1:13], strict=True))


@pytest.mark.parametrize("result", C.contrast_audit(), ids=lambda r: f"{r.scheme}-{r.tone}-{r.fg}")
def test_contrast_rules(result):
    assert result.passed, f"Lc {result.lc:.1f} < {result.target}"


PRESET_CASES = [(s, n) for s in C.SCHEMES for n in C.preset_names()]


@pytest.mark.parametrize(("scheme", "name"), PRESET_CASES)
def test_categorical_palette_passes_six_checks(scheme, name):
    surface = C.to_hex(C.role_colour("neutral", "surface", scheme))
    checks = C.categorical_checks(C.categorical(scheme, name), scheme, surface)
    assert checks["ok"], checks
    assert checks["cvd"] >= C.CVD_TARGET, checks  # target, not just the floor


@pytest.mark.parametrize(("scheme", "name"), PRESET_CASES)
def test_story_palette_is_cvd_separable_and_visible(scheme, name):
    surface = C.to_hex(C.role_colour("neutral", "surface", scheme))
    audit = C.palette_audit(C.story(scheme, name), surface)
    assert audit["min_cvd_delta_e"] >= 0.06, audit
    assert audit["min_lc_on_background"] >= 30, audit


@pytest.mark.parametrize(("scheme", "name"), PRESET_CASES)
def test_context_and_highlight_are_visible(scheme, name):
    surface = C.role_colour("neutral", "surface", scheme)
    assert C.apca(C.context(scheme), surface) >= 30
    assert C.apca(C.highlight(scheme, name), surface) >= 45


def test_presets_reference_defined_ramps():
    cfg = C.load_config()
    for name in C.preset_names():
        p = C.preset(name)
        assert p["sequential"] in cfg["data"]["sequential"]
        assert p["diverging"] in cfg["data"]["diverging"]
        assert 3 <= len(p["categorical"]) <= 5


@pytest.mark.parametrize("scheme", C.SCHEMES)
def test_sequential_is_monotonic_in_lightness(scheme):
    for name in C.load_config()["data"]["sequential"]:
        ls = [C.Color(h).convert("oklch")["lightness"] for h in C.sequential(name, scheme)]
        diffs = [b - a for a, b in zip(ls[:-1], ls[1:], strict=True)]
        assert all(d > 0 for d in diffs) or all(d < 0 for d in diffs), (name, ls)


@pytest.mark.parametrize("scheme", C.SCHEMES)
def test_diverging_is_symmetric_in_lightness(scheme):
    # gamut mapping may shift lightness slightly (< 0.01, below a JND)
    for name in C.load_config()["data"]["diverging"]:
        ls = [C.Color(h).convert("oklch")["lightness"] for h in C.diverging(name, scheme)]
        assert all(abs(a - b) < 0.01 for a, b in zip(ls, ls[::-1], strict=True)), name


def test_adding_a_hue_needs_only_an_anchor():
    cfg = dict(C.load_config())
    cfg["hues"] = {**cfg["hues"], "jasper": {"anchor": [0.55, 0.15, 330.0], "group": "highlight"}}
    steps = C.scale_hex("jasper", "light", cfg)
    assert len(steps) == 15 and steps[14] == "#ffffff"


def test_generated_categorical_reaches_large_counts():
    pal = C.generate_categorical(10, "light")
    assert len(set(pal)) == 10


def test_tokens_css_has_both_schemes_and_aliases():
    css = tokens.build_css()
    assert css.count("--ss-canvas:") >= 3  # light, media-dark, forced-dark (+ surface options)
    assert ':root[data-colour-scheme="dark"]' in css
    assert "--ss-data-story-4:" in css and "--ss-data-cat-5:" in css and "--ss-data-div-9:" in css
    for name in C.preset_names():
        assert f'[data-palette="{name}"]' in css


@pytest.mark.parametrize(
    "row", C.surface_audit(), ids=lambda r: f"{r['surface']}-{r['scheme']}-{r['bg']}-{r['fg']}"
)
def test_surface_options_keep_contrast(row):
    assert row["lc"] >= row["target"], row


def test_surface_blocks_generated():
    css = tokens.build_css()
    for name in C.surface_names():
        if name != "baseline":
            assert f'[data-surface="{name}"]' in css
    assert (
        '[data-colour-scheme="dark"] {' in css
        or '[data-colour-scheme="dark"] {\n' in css
        or ', [data-colour-scheme="dark"] {' in css
    )
