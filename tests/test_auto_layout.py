from pathlib import Path

from subscout.build import build

STORY = """---
title: T
byline: B
date: 2026-01-01
sources:
  s: {name: S, url: "https://example.org", accessed: 2026-01-01}
data:
  d: d.csv
---

::: step {beat=situation%s}
Text.

```chart
id: a
type: %s
data: d
x: x
y: y
series: g
label: x
value: y
row: x
title: A title
source: s
confidence: observed
```
:::
"""


def _build(tmp_path: Path, chart: str, attr: str = "") -> str:
    (tmp_path / "d.csv").write_text("x,y,g\n1,2,a\n2,3,a\n")
    (tmp_path / "story.md").write_text(STORY % (attr, chart), encoding="utf-8")
    out = tmp_path / "_site"
    rep = build(tmp_path, out)
    assert not rep.errors, rep.errors
    return (out / "index.html").read_text(encoding="utf-8")


def test_a_line_chart_stays_beside_the_text(tmp_path):
    page = _build(tmp_path, "line")
    assert 'data-layout="side"' in page and "ss-scrolly--full" not in page


def test_a_layout_named_on_the_step_wins(tmp_path):
    assert 'data-layout="full"' in _build(tmp_path, "line", " layout=full")
    assert "ss-scrolly--wide" in _build(tmp_path, "line", " layout=wide")


def test_an_unknown_layout_is_a_build_error(tmp_path):
    (tmp_path / "d.csv").write_text("x,y,g\n1,2,a\n")
    (tmp_path / "story.md").write_text(STORY % (" layout=huge", "line"), encoding="utf-8")
    assert build(tmp_path, tmp_path / "_site").errors
