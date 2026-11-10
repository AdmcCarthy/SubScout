import pytest

from subscout.layouts import MAX_SIDE_ROWS, choose, normalise, wants_full


def test_wide_is_the_old_name_for_lane():
    assert normalise("wide") == "lane" and normalise("full") == "full" and normalise(None) is None


def test_unknown_layout_is_refused():
    with pytest.raises(ValueError):
        normalise("huge")


@pytest.mark.parametrize("t", ["map", "network", "heat"])
def test_maps_networks_and_heatmaps_take_the_width(t):
    assert wants_full({"type": t})


def test_simple_charts_stay_beside_the_text():
    figs = [({"type": "line"}, None), ({"type": "bars"}, [{}] * MAX_SIDE_ROWS)]
    assert choose(None, figs)[0] == "side"


def test_many_rows_take_the_width():
    assert wants_full({"type": "bars"}, [{}] * (MAX_SIDE_ROWS + 1))
    assert wants_full({"type": "heat"}, {"rows": ["a"]})


def test_custom_figures_declare_what_they_need():
    assert wants_full({"type": "custom", "detail": "high"})
    assert wants_full({"type": "custom", "min_width": 900})
    assert not wants_full({"type": "custom", "min_width": 600})
    assert wants_full({"type": "custom", "aspect": 2})
    assert not wants_full({"type": "custom"})


def test_one_detailed_figure_takes_the_whole_section():
    assert choose(None, [({"type": "line"}, None), ({"type": "map"}, None)])[0] == "full"


def test_a_named_layout_wins():
    assert choose("side", [({"type": "map"}, None)]) == ("side", "set on the step")
