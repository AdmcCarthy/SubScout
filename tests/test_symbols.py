"""Symbols: vocabulary parses, shapes fit the box, wells compose from existing layers, files are current."""

import itertools
import re
from pathlib import Path

import pytest

from subscout import symbols as S

RUNTIME = Path(S.RUNTIME_JS)
# Geostandard 3.5, pages 3-14 and 3-15 (planned = same shape, muted), plus the disused flare platform
INSTALLATIONS = set(
    """
    dead_man_anchor diverless_latch start_end_point anchor buoy_general buoy_loading buoy_midline buoy_stl
    buoy_weather central_distribution_unit clamp clump_weight concrete_block counteract crossing_point flange
    flare_platform hang_off junction_point land_valve_station manifold pile pipe_connection pipeline_end_plem
    pipeline_end_plet platform riser_base rig ship subsea_object_other subsea_template subsea_valve tank
    terminal_supply_base touchdown_point transponder unknown flare_platform_disused
    """.split()
)


@pytest.fixture(scope="module")
def data():
    return S.build()


def test_every_shape_fits_the_box_and_has_a_label(data):
    box = data["meta"]["box"]
    for kind in ("layers", "installations"):
        for key, v in data[kind].items():
            assert v["label"], key
            assert v["parts"] or key in ("tech.proposed",), f"{kind} {key} draws nothing"
            # sectors are checked at build time with their true extent; every other primitive is checked here
            plain = [p for p in v["parts"] if p["k"] != "path"]
            assert S.extent(plain) <= box + 0.01, key


def test_parts_use_the_five_runtime_primitives_only(data):
    kinds = {p["k"] for kind in ("layers", "installations") for v in data[kind].values() for p in v["parts"]}
    assert kinds <= {"circle", "line", "rect", "path", "text"}


def test_bad_drawing_strings_are_rejected():
    for bad in ("zz 1 2 3", "c 1 2", "p M0 0 C1 1 2 2 3 3", "rays 0 0 1 2 3"):
        with pytest.raises(S.SymbolError):
            S.parse_part(bad)


def test_layers_cite_the_geostandard_section(data):
    cited = {v["std"] for v in data["layers"].values()}
    assert cited <= {"3.4.2", "3.4.3", "3.4.4", "3.4.5", "3.4.7", "3.4.9"}
    assert {"3.4.2", "3.4.4", "3.4.7", "3.4.9"} <= cited


def test_installations_are_the_standards_list(data):
    assert set(data["installations"]) == INSTALLATIONS


def test_every_example_composes_from_existing_layers_and_is_unique(data):
    seen = {}
    for ex in data["examples"]:
        layers = S.layers_for(ex["well"])
        assert all(k in data["layers"] for k in layers), ex["label"]
        sig = (tuple(layers), ex["well"].get("code"))
        assert sig not in seen or ex["label"] == seen[sig], f"{ex['label']!r} duplicates {seen[sig]!r}"
        seen[sig] = ex["label"]
    assert len(data["examples"]) >= 45


def test_any_combination_of_fluids_status_and_function_composes(data):
    # the standard shows a selection and says the rest follow the same principle: all of them must compose
    by = data["vocabulary"]["qualifiers_by_fluid"]
    assert by == {
        "oil": ["proven", "minor", "trace"],
        "gas": ["proven", "minor", "trace"],
        "condensate": ["proven", "minor"],
    }
    options = [[None, *by[f]] for f in ("oil", "gas", "condensate")]
    for o, g, c in itertools.product(*options):
        fluids = [[f, q] for f, q in (("oil", o), ("gas", g), ("condensate", c)) if q]
        for tech in data["vocabulary"]["technical"]:
            for fn in (None, *data["vocabulary"]["functions"]):
                well = {"fluids": fluids or None, "technical": tech, "fn": {"kind": fn} if fn else None}
                assert all(k in data["layers"] for k in S.layers_for(well)), well
    for fl in ("dry", "coal"):
        assert all(k in data["layers"] for k in S.layers_for({"fluids": fl}))


def test_fluids_draw_in_a_fixed_order_whatever_order_they_arrive():
    a = S.layers_for({"fluids": [["gas", "minor"], ["oil", "proven"]]})
    b = S.layers_for({"fluids": [["oil", "proven"], ["gas", "minor"]]})
    assert a == b == ["base", "fluid.oil.proven", "fluid.gas.minor"]


def test_plugged_and_abandoned_oil_is_the_oil_layer_plus_the_status_layer():
    assert S.layers_for({"fluids": [["oil", "proven"]], "technical": "plugged_abandoned"}) == [
        "base",
        "fluid.oil.proven",
        "tech.plugged_abandoned",
    ]


def test_active_exploration_markers_replace_the_base_circle():
    assert S.layers_for({"exploration": "wildcat"}) == ["explore.wildcat"]


def test_vocabulary_lists_what_the_standard_distinguishes(data):
    v = data["vocabulary"]
    assert {"abandoned_technical", "temporarily_abandoned", "plugged_abandoned", "not_observed"} <= set(
        v["technical"]
    )
    assert {"production", "injection", "observation", "dual_completion", "shut_in", "converted"} <= set(
        v["functions"]
    )
    assert {"water", "cuttings", "co2"} <= set(v["injected_fluids"])
    assert set(v["classes"]) == {"development", "exploratory", "injector", "non_hydrocarbon"}


def test_trajectories_have_three_distinct_line_styles(data):
    dashes = {k: v["dash"] for k, v in data["trajectories"].items()}
    assert set(dashes) == {"actual", "approximate", "planned"} and len(set(dashes.values())) == 3


def test_geostandard_colours_are_an_optional_preset_with_a_warning(data):
    assert "colour-vision" in data["colours"]["note"]


def test_symbol_code_has_no_raw_colours():
    # colour comes from tokens at draw time; the standard's own colours live in the data, not in the code
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", (RUNTIME / "symbols.js").read_text(encoding="utf-8"))


def test_generated_runtime_files_are_up_to_date(tmp_path):
    S.write(tmp_path)
    for name in ("symbols-data.js", "symbols.json"):
        assert (tmp_path / name).read_text(encoding="utf-8") == (RUNTIME / name).read_text(
            encoding="utf-8"
        ), f"{name} is stale: run `uv run subscout symbols`"
