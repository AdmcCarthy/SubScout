"""The modes of SubScout: what is made of a story folder.

- `story`: a data story told as journalism. One argument on one scrolling page, with its Read and Present views.
- `deck`: presentation and teaching material. A landing page of categories and one page per category, in which
  each view is a slide the size of the screen.

A folder names its mode in the front matter of story.md (`mode: deck`); without one it is a story. Each mode is a
function `(root, out, runtime_href) -> Report`. Parsing, numbers, confidence and figure preparation are shared and
live in `subscout.build`; a mode owns its templates, its page script and its own checks.
"""

from __future__ import annotations

from pathlib import Path

from ..build import Report, split_front_matter
from . import deck, story

MODES = {"story": story.build, "deck": deck.build}
DEFAULT = "story"


def mode_of(root: Path, override: str | None, report: Report) -> str:
    """The mode a story folder is built in: the one asked for, else `mode:` in its front matter, else story."""
    name = override
    if name is None:
        md = Path(root) / "story.md"
        if not md.exists():
            report.error(f"no story.md in {root}")
            return DEFAULT
        name = split_front_matter(md.read_text(encoding="utf-8"))[0].get("mode", DEFAULT)
    if name not in MODES:
        report.error(f"mode '{name}' is not one of {sorted(MODES)}")
        return DEFAULT
    return name
