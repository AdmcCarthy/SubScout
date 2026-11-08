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
    assert "Basis of analysis" in html and "How we know" not in html
    assert 'id="basis-of-analysis"' in html and 'id="how-we-know"' in html  # the old anchor still resolves
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


def test_custom_figure_module_is_checked_and_copied(tmp_path):
    body = (
        "```chart\nid: c\ntype: custom\nmodule: figures/c.js\ndata: decades\ntitle: A custom figure\n"
        "source: s\nconfidence: observed\nnotes: Bespoke form.\nstate: { mode: a }\n```\n"
    )
    d = _story(tmp_path, body)
    (d / "figures").mkdir()
    (d / "figures" / "c.js").write_text("export default () => ({ draw() {} });\n")
    rep = build(d, tmp_path / "out")
    assert rep.errors == []
    assert (tmp_path / "out" / "figures" / "c.js").exists()
    html = (tmp_path / "out" / "index.html").read_text()
    payload = json.loads(html.split('id="ss-payload"')[1].split(">", 1)[1].split("</script>")[0])
    assert "decades" in payload["datasets"]
    assert payload["figures"]["c"]["spec"]["state"] == {"mode": "a"}


def test_custom_figure_needs_existing_module(tmp_path):
    body = "```chart\nid: c\ntype: custom\nmodule: figures/missing.js\ndata: decades\ntitle: T\nsource: s\nconfidence: observed\nnotes: n\n```\n"
    rep = build(_story(tmp_path, body), tmp_path / "out")
    assert any("not found" in e for e in rep.errors)


def test_wide_layout_marks_the_scrolly_section(tmp_path):
    body = "::: step {layout=wide}\n### A\nText.\n:::\n"
    out = tmp_path / "out"
    rep = build(_story(tmp_path, body), out)
    assert rep.errors == []
    assert 'class="ss-scrolly ss-scrolly--wide"' in (out / "index.html").read_text()


def test_nan_in_page_data_becomes_null_with_a_warning(tmp_path):
    from subscout.build import Report, payload_json

    rep = Report()
    text = payload_json({"datasets": {"x": [1.0, float("nan")]}}, rep)
    assert json.loads(text) == {"datasets": {"x": [1.0, None]}}
    assert any("NaN" in w for w in rep.warnings)


def test_export_page_lists_every_view(tmp_path):
    body = (
        '::: step {kicker="First"}\n### A\nText.\n\n```chart\nid: c\ntype: custom\nmodule: figures/c.js\ndata: decades\n'
        "title: A figure\nsource: s\nconfidence: observed\nnotes: n\nexport: true\nstate: { era: 0 }\n```\n:::\n\n"
        '::: step {kicker="Second"}\n### B\nMore.\n\n```chart\nuse: c\nera: 1\n```\n:::\n'
    )
    d = _story(tmp_path, body)
    (d / "figures").mkdir()
    (d / "figures" / "c.js").write_text("export default () => ({ draw() {} });\n")
    out = tmp_path / "out"
    rep = build(d, out)
    assert rep.errors == []
    page = (out / "export" / "c" / "index.html").read_text()
    payload = json.loads(page.split('id="ss-payload">')[1].split("</script>")[0].replace("<\\/", "</"))
    assert [s["name"] for s in payload["states"]] == ["First", "Second"]
    assert [s["state"] for s in payload["states"]] == [{"era": 0}, {"era": 1}]
    assert set(payload["sizes"]) == {"slide", "portrait", "square"}
    assert not (out / "export" / "c" / "renders.json").exists()  # rendering moved to Plate
    contract = json.loads((out / "export" / "c" / "payload.json").read_text())
    assert contract["contract"] == {"name": "subscout-export", "version": 1}
    assert contract["id"] == "c" and contract["runtime"] == "runtime"
    assert contract["meta"]["confidence"] == "observed" and contract["meta"]["notes"] == "n"
    assert [k for k, _ in contract["facts"]] == ["Source", "Confidence"]
    assert contract["story"]["palette"] and contract["fig"]["spec"]["module"] == "figures/c.js"
    assert contract["states"] == payload["states"]
    assert 'href="export/c/"' in (out / "index.html").read_text()


def test_export_command_points_to_plate(capsys):
    from subscout.cli import main

    assert main(["export", "_site"]) == 2
    assert "plate render _site" in capsys.readouterr().out
