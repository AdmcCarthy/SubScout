import json

from subscout.advice import device, paragraphs, style_advice
from subscout.build import build

STEP = '::: step {{kicker="k"}}\n### {h}\n\n{p}\n\n```chart\nid: f{i}\ntype: bars\ndata: d\n```\n:::\n\n'


def story(headings, para="Some text about the point, in one paragraph. " * 3):
    return "".join(STEP.format(h=h, p=para, i=i) for i, h in enumerate(headings))


def test_devices_are_classified_by_construction():
    assert device("1995: the giants still full") == "number-led"
    assert device("APA 2008: a mesh of partners") == "label: tail"
    assert device("Who operates the licences?") == "question"
    assert device("Quicker wells") == "clipped"
    assert device("More hits, then a giant") == "comma twist"
    assert device("Success rates have held while the size of each find fell") == "plain"
    assert device("{{ n_licences }} new licences among hundreds of old ones") == "plain"


def test_a_run_of_one_device_is_flagged_and_varied_headings_are_not():
    flagged = style_advice(story(["Quicker wells", "Close to home", "Fewer finds", "Bigger gaps"]))
    assert any("same device (clipped)" in a for a in flagged)
    varied = [
        "Success rates have held while each find got smaller",
        "Quicker wells",
        "Who drills close to a platform?",
        "Licences in mature acreage are held by design",
        "1995: the giants still full",
    ]
    assert not any("device" in a for a in style_advice(story(varied)))


def test_same_opening_word_run_and_dominant_device():
    a = style_advice(
        story(["APA 2008: a mesh", "APA 2013: the peak", "APA 2019: thinning", "APA 2025: a hub"])
    )
    assert any("begin 'apa'" in x for x in a)
    many = style_advice(
        story(
            [
                "Quicker wells",
                "Close to home",
                "Fewer finds",
                "Bigger gaps",
                "Odd one out here, with commas",
                "A longer plain heading describing what this step shows",
                "Small finds",
                "Late giants",
            ]
        )
    )
    assert any("headings use the same device" in x and "%" in x for x in many)


def test_identical_step_shapes_and_subsection_count_are_flagged():
    heads = [f"A plain heading number {i} describing a different thing {i * 7}" for i in range(14)]
    a = style_advice(story(heads))
    assert any("steps in a row have one shape" in x for x in a)
    assert any("14 sub-sections" in x for x in a)
    assert not any("sub-sections" in x for x in style_advice(story(heads[:6])))


def test_many_paragraphs_in_a_step_are_flagged():
    md = "::: step\n### Plain heading for a long step\n\nOne.\n\nTwo.\n\nThree.\n\nFour.\n:::\n"
    assert paragraphs("One.\n\nTwo.\n\n```chart\nid: x\n```\n\n- list\n\nThree.") == 3
    assert any("4 paragraphs" in x for x in style_advice(md))


def test_advice_is_in_the_report_and_never_an_error(tmp_path):
    d = tmp_path / "s"
    d.mkdir()
    (d / "data").mkdir()
    (d / "data" / "d.csv").write_text("label,value\na,1\nb,2\n")
    (d / "story.md").write_text(
        "---\ntitle: T\nsources:\n  s: {name: S, accessed: 2026-01-01}\ndata:\n  d: data/d.csv\n---\n\n"
        + story(["Quicker wells", "Close to home", "Fewer finds"]).replace(
            "type: bars\ndata: d",
            "type: bars\ndata: d\nlabel: label\nvalue: value\nsource: s\nconfidence: observed\ntitle: t",
        )
    )
    out = tmp_path / "out"
    rep = build(d, out)
    assert rep.errors == [] and rep.advice
    assert json.loads((out / "build-report.json").read_text())["advice"] == rep.advice
