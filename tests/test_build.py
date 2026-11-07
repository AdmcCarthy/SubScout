"""Story build: the demo builds cleanly, and the checks catch what they should."""

import json
import shutil
from pathlib import Path

import pytest

from subscout.build import about, build, untraced_numbers

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo"


def test_demo_builds_without_errors_or_warnings(tmp_path):
    rep = build(DEMO, tmp_path / "out")
    assert rep.errors == [] and rep.warnings == []
    html = (tmp_path / "out" / "index.html").read_text()
    report = json.loads((tmp_path / "out" / "build-report.json").read_text())
    assert "How we know" in html
    assert "{{" not in html.split('id="ss-payload"')[0], "unrendered expression in page"
    assert {r["name"] for r in report["ledger"]} >= {"n_fields", "longest_plateau", "wells_drop"}
    assert all(f["confidence"] in ("observed", "derived", "interpreted") for f in report["figures"])


def _story(tmp_path, body, front="", py=""):
    d = tmp_path / "s"
    (d / "data").mkdir(parents=True)
    shutil.copy(DEMO / "data" / "decades.csv", d / "data" / "decades.csv")
    (d / "story.md").write_text(
        "---\ntitle: T\nsources: { s: { name: S } }\ndata: { decades: data/decades.csv }\n"
        + front
        + "---\n"
        + body
    )
    (d / "story.py").write_text(
        "from subscout import metric\ndef metrics(d):\n    return {'n': metric(len(d['decades']), 'count', 's', 'observed')}\n"
        + py
    )
    return d


def test_unknown_metric_is_an_error(tmp_path):
    rep = build(_story(tmp_path, "We found {{ nope }} things."), tmp_path / "o")
    assert any("unknown metric 'nope'" in e for e in rep.errors)


def test_untraced_numbers_are_warned(tmp_path):
    rep = build(_story(tmp_path, "There were {{ n }} decades and 37 surprises in 1999."), tmp_path / "o")
    assert any("untraced" in w and "37" in w for w in rep.warnings)
    assert not any("1999" in w for w in rep.warnings)


def test_figure_needs_source_confidence_and_title(tmp_path):
    body = "```chart\ntype: bars\ndata: decades\nlabel: decade\nvalue: discoveries\n```\n{{ n }}"
    rep = build(_story(tmp_path, body), tmp_path / "o")
    joined = " ".join(rep.errors)
    assert "action title" in joined and "source is required" in joined and "confidence" in joined


@pytest.mark.parametrize("rule", ["dual-axis", "area-scaling", "lie-factor"])
def test_truth_gate_rules_cannot_be_excepted(tmp_path, rule):
    body = (
        "```chart\ntype: bars\ndata: decades\nlabel: decade\nvalue: discoveries\ntitle: T\nsource: s\n"
        f"confidence: observed\nexception: {{ rule: {rule}, reason: because }}\n```\n{{{{ n }}}}"
    )
    rep = build(_story(tmp_path, body), tmp_path / "o")
    assert any("truth-gate" in e for e in rep.errors)


def test_arc_beats_are_checked(tmp_path):
    body = "::: step {beat=but}\n{{ n }}\n:::\n"
    rep = build(_story(tmp_path, body, front="arc: abt\n"), tmp_path / "o")
    assert any("missing beat" in w for w in rep.warnings)


def test_about_rounds_to_two_significant_figures():
    assert about(1_834_500_000) == "about 1.8 billion"
    assert about(15_000_000) == "about 15 million"
    assert about(487) == "about 490"


def test_untraced_ignores_years_and_identifiers():
    assert untraced_numbers("In 2025, PL 1313 lay 106 km away.") == ["106"]


def test_numbers_round_half_up_with_true_minus():
    from subscout.build import fmt_num

    assert fmt_num(62.5) == "63"
    assert fmt_num(1.65, 1) == "1.7"
    assert fmt_num(-4.25, 1) == "−4.3"
    assert fmt_num(1234567) == "1,234,567"


def test_appendix_expressions_are_rendered(tmp_path):
    body = "Text {{ n }}.\n\n::: appendix\nThere were {{ n }} decades.\n:::\n"
    out = tmp_path / "o"
    rep = build(_story(tmp_path, body), out)
    assert rep.errors == []
    page = (out / "index.html").read_text()
    assert "{{" not in page.split('id="ss-payload"')[0]
