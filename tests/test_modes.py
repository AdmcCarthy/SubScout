"""Modes: a folder is built as a story or as a deck, and deck mode checks what it must."""

import json
import re
import shutil
from pathlib import Path

from subscout.build import build
from subscout.cli import main
from subscout.modes import MODES

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
DECK = EXAMPLES / "deck"


def _payload(page: Path) -> dict:
    text = page.read_text(encoding="utf-8")
    raw = re.search(r'<script type="application/json" id="deck-data">(.*?)</script>', text, re.S).group(1)
    return json.loads(raw.replace("<\\/", "</"))


def _deck(tmp_path, body=None, config=None, front="mode: deck\n"):
    d = tmp_path / "d"
    (d / "data").mkdir(parents=True)
    shutil.copy(EXAMPLES / "demo" / "data" / "decades.csv", d / "data" / "decades.csv")
    chart = (
        "```chart\nid: finds\ntype: bars\ndata: decades\nlabel: decade\nvalue: avg_msm3\ntitle: Finds shrink\n"
        "source: s\nconfidence: derived\n```\n"
    )
    body = body or (
        "Lead.\n\n## One\n\nOpening text.\n\n::: step\n### First topic\n\n{{ n }} decades.\n\n"
        + chart
        + ":::\n\n::: step\nSecond view.\n\n```chart\nuse: finds\nhighlight: [2020s]\ntitle: Latest decade\n```\n:::\n\n"
        "## Two\n\n::: step\n### Other topic\n\nText.\n\n```chart\nuse: finds\n```\n:::\n"
    )
    (d / "story.md").write_text(
        f"---\n{front}title: T\nsources: {{ s: {{ name: S }} }}\ndata: {{ decades: data/decades.csv }}\n---\n{body}",
        encoding="utf-8",
    )
    (d / "story.py").write_text(
        "from subscout import metric\ndef metrics(d):\n"
        "    return {'n': metric(len(d['decades']), 'count', 's', 'observed')}\n",
        encoding="utf-8",
    )
    if config is not False:
        (d / "deck.yaml").write_text(
            config
            or "categories:\n  - { slug: one, title: One, sections: [One] }\n  - { slug: two, title: Two, sections: [Two] }\n",
            encoding="utf-8",
        )
    return d


def test_a_folder_without_a_mode_is_a_story(tmp_path):
    rep = build(EXAMPLES / "demo", tmp_path / "o")
    assert rep.errors == []
    assert json.loads((tmp_path / "o" / "build-report.json").read_text(encoding="utf-8"))["mode"] == "story"
    assert set(MODES) == {"story", "deck"}


def test_unknown_mode_is_an_error(tmp_path):
    rep = build(_deck(tmp_path, front="mode: poster\n"), tmp_path / "o")
    assert any("mode 'poster'" in e for e in rep.errors)


def test_deck_demo_builds_without_errors_or_warnings(tmp_path):
    out = tmp_path / "o"
    rep = build(DECK, out)
    assert rep.errors == [] and rep.warnings == []
    report = json.loads((out / "build-report.json").read_text(encoding="utf-8"))
    assert report["mode"] == "deck" and [p["slug"] for p in report["pages"]] == ["production", "finds"]
    assert {r["name"] for r in report["ledger"]} >= {"n_fields", "longest_plateau", "wells_drop"}
    for name in ("index", "basis", "production", "finds"):
        page = (out / f"{name}.html").read_text(encoding="utf-8")
        assert "{{" not in page.split('id="deck-data"')[0], f"unrendered expression in {name}"
        assert "Built with" in page or name in ("production", "finds")
    assert (out / "runtime" / "js" / "deck.js").exists() and (out / "runtime" / "css" / "deck.css").exists()


def test_deck_slides_follow_the_story(tmp_path):
    out = tmp_path / "o"
    assert build(DECK, out).errors == []
    p = _payload(out / "production.html")
    kinds = [s["kind"] for s in p["slides"]]
    assert kinds == ["cover", "text", "view", "view", "view", "table"]
    assert [s.get("topic") for s in p["slides"][2:5]] == [
        "Ramp, plateau and decline",
        "A long plateau is the exception",
        "A tie-back fills spare capacity",
    ]
    # a `use:` step is a state of the same figure, so the figure moves and is not redrawn
    assert {s["fig"] for s in p["slides"][2:5]} == {"production"}
    assert (
        p["slides"][3]["state"]["focus"] == ["Field C"]
        and p["slides"][4]["state"]["note"]["name"] == "Field F"
    )
    assert p["figures"]["production"]["master"] == "side"
    assert p["prev"] is None and p["next"]["slug"] == "finds"
    f = _payload(out / "finds.html")
    assert f["multi"] is True and f["figures"]["wells"]["master"] == "full"  # a heatmap goes across the slide


def test_deck_mode_from_the_command_line_overrides_the_front_matter(tmp_path, capsys):
    d = _deck(tmp_path, front="")
    assert main(["build", str(d), "--out", str(tmp_path / "o"), "--mode", "deck"]) == 0
    assert "as a deck" in capsys.readouterr().out
    assert (tmp_path / "o" / "one.html").exists() and (tmp_path / "o" / "two.html").exists()


def test_deck_needs_its_config(tmp_path):
    rep = build(_deck(tmp_path, config=False), tmp_path / "o")
    assert any("deck.yaml" in e for e in rep.errors)


def test_every_section_belongs_to_one_category(tmp_path):
    missing = "categories:\n  - { slug: one, title: One, sections: [One] }\n"
    rep = build(_deck(tmp_path, config=missing), tmp_path / "o")
    assert any("section 'Two' is in 0 categories" in e for e in rep.errors)
    unknown = "categories:\n  - { slug: one, title: One, sections: [One, Two, Three] }\n"
    rep = build(_deck(tmp_path / "b", config=unknown), tmp_path / "o2")
    assert any("no section 'Three'" in e for e in rep.errors)


def test_slugs_are_checked(tmp_path):
    bad = "categories:\n  - { slug: index, title: One, sections: [One] }\n  - { slug: Two!, title: Two, sections: [Two] }\n"
    rep = build(_deck(tmp_path, config=bad), tmp_path / "o")
    assert sum("slug" in e for e in rep.errors) == 2


def test_deck_figures_pass_the_same_gate_as_a_story(tmp_path):
    body = "## One\n\n::: step\n{{ n }}\n\n```chart\ntype: bars\ndata: decades\nlabel: decade\nvalue: discoveries\n```\n:::\n\n## Two\n\nText.\n"
    rep = build(_deck(tmp_path, body=body), tmp_path / "o")
    joined = " ".join(rep.errors)
    assert "action title" in joined and "source is required" in joined and "confidence" in joined


def test_master_can_be_named_on_a_block_or_in_the_config(tmp_path):
    body = (
        "## One\n\n::: step\n{{ n }}\n\n```chart\nid: a\ntype: bars\ndata: decades\nlabel: decade\nvalue: discoveries\n"
        "master: full\ntitle: T\nsource: s\nconfidence: observed\n```\n:::\n\n## Two\n\nText.\n"
    )
    out = tmp_path / "o"
    assert build(_deck(tmp_path, body=body), out).errors == []
    assert _payload(out / "one.html")["figures"]["a"]["master"] == "full"
    rep = build(_deck(tmp_path / "b", body=body.replace("master: full", "master: tall")), tmp_path / "o2")
    assert any("master 'tall'" in e for e in rep.errors)


def test_a_category_that_goes_takes_its_page_with_it(tmp_path):
    d, out = _deck(tmp_path), tmp_path / "o"
    assert build(d, out).errors == [] and (out / "two.html").exists()
    (d / "deck.yaml").write_text(
        "categories:\n  - { slug: all, title: All, sections: [One, Two] }\n", encoding="utf-8"
    )
    assert build(d, out).errors == []
    assert (out / "all.html").exists() and not (out / "two.html").exists() and not (out / "one.html").exists()


def test_fit_refuses_a_story(tmp_path, capsys):
    assert build(EXAMPLES / "demo", tmp_path / "o").errors == []
    assert main(["fit", str(tmp_path / "o")]) == 2
    assert "not a deck" in capsys.readouterr().out


CHART = "```chart\nid: finds\ntype: bars\ndata: decades\nlabel: decade\nvalue: avg_msm3\ntitle: Finds shrink\nsource: s\nconfidence: derived\n```\n"


def test_a_concept_card_heads_the_text_of_its_topic(tmp_path):
    card = "```concept\nname: Exponential decline\nformula: 'q = q_0\\,e^{-Dt}'\nwhere: '$q$ rate, $D$ decline'\n```\n"
    body = (
        "Lead.\n\n## One\n\n::: step\n### First topic\n\n" + card + "\nText.\n\n" + CHART + ":::\n\n"
        "::: step\nSecond view.\n\n```chart\nuse: finds\n```\n:::\n\n"
        "::: step\n### Second topic\n\nNo card.\n\n```chart\nuse: finds\n```\n:::\n\n"
        "## Two\n\n::: step\n### Other topic\n\nText.\n\n```chart\nuse: finds\n```\n:::\n"
    )
    out = tmp_path / "o"
    assert build(_deck(tmp_path, body=body), out).errors == []
    views = [s for s in _payload(out / "one.html")["slides"] if s["kind"] == "view"]
    # the card is set as MathML at build time and stays with its topic, not beyond it
    assert all(
        'class="concept-name">Exponential decline' in s["html"] and "<math" in s["html"] for s in views[:2]
    )
    assert "concept" not in views[2]["html"]
    assert views[0]["html"].count("<math") == 3  # one formula and two symbols


def test_a_concept_card_is_checked(tmp_path):
    for bad, said in (
        ("```concept\nname: X\nequation: 'a = b'\n```\n", "a concept block takes"),
        ("```concept\nname: a: b\n```\n", "concept: YAML error"),
    ):
        body = (
            "Lead.\n\n## One\n\n::: step\n### T\n\n"
            + bad
            + "\n"
            + CHART
            + ":::\n\n## Two\n\n::: step\n### U\n\n```chart\nuse: finds\n```\n:::\n"
        )
        report = build(_deck(tmp_path / said[:4].strip(), body=body), tmp_path / "o")
        assert any(said in e for e in report.errors), report.errors


def test_a_hub_stands_over_built_decks_and_replaces_their_landing_pages(tmp_path):
    from subscout.hub import build_hub

    site = tmp_path / "site"
    assert build(DECK, site).errors == []
    cfg = tmp_path / "hub.yaml"
    cfg.write_text(
        "title: T\nheadline: H\ndecks:\n  - { key: one, site: site, name: One deck, line: A line }\n"
        "data:\n  - { chip: D, title: Data, text: measured, num: '3' }\n",
        encoding="utf-8",
    )
    res = build_hub(cfg, tmp_path / "hub")
    assert res["decks"] == 1 and res["slides"] > 0 and res["diagrams"] == 0
    page = (tmp_path / "hub" / "index.html").read_text(encoding="utf-8")
    # every category of the deck is linked, under the deck's key
    for slug in ("production", "finds"):
        assert f'href="one/{slug}.html"' in page and (tmp_path / "hub" / "one" / f"{slug}.html").exists()
    assert (
        "Exponential decline" not in page and "1 relations named" in page
    )  # the one concept card of the example is counted
    # the deck's own landing page gives way to the hub
    assert "url=../index.html#decks" in (tmp_path / "hub" / "one" / "index.html").read_text(encoding="utf-8")
    assert 'id="diagrams"' not in page  # no diagrams, so no wall


def test_a_hub_draws_the_diagrams_of_its_decks(tmp_path):
    from subscout import hub

    d = {
        "box": [0, 0, 10, 5],
        "shapes": [
            {"id": "p", "kind": "poly", "group": "g", "pts": [[1, 1], [9, 1], [9, 4]], "fill": "c1"},
            {
                "id": "a",
                "kind": "arrow",
                "group": "g",
                "from": [1, 4],
                "to": [5, 4],
                "colour": "c3",
                "double": True,
            },
            {"id": "t", "kind": "text", "group": "g", "at": [5, 2], "text": "label"},
        ],
    }
    assert hub.is_diagram(d) and not hub.is_diagram({"x": {}, "series": []})
    tile = hub.svg(d, text=False, uid="u")
    assert tile.startswith('<svg viewBox="0 0 10.000 5.000"') and "<polygon" in tile and "label" not in tile
    assert tile.count("url(#a-u-c3)") == 2 and "label" in hub.svg(d, text=True)
    assert hub.traces(3, 2).count('class="live"') == 5


def test_hub_config_is_checked(tmp_path, capsys):
    cfg = tmp_path / "hub.yaml"
    cfg.write_text(
        "title: T\nheadline: H\ndecks:\n  - { key: one, site: nowhere, name: One }\n", encoding="utf-8"
    )
    assert main(["hub", str(cfg), "--out", str(tmp_path / "o")]) == 2
    assert "no built deck" in capsys.readouterr().out
    cfg.write_text("title: T\n", encoding="utf-8")
    assert main(["hub", str(cfg), "--out", str(tmp_path / "o")]) == 2
