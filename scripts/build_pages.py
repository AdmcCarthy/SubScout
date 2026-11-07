"""Assemble the GitHub Pages site into _site/: site/* plus the packaged runtime.

Usage: uv run python scripts/build_pages.py [out_dir]
Preview: uv run python -m http.server -d _site
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from subscout import tokens

ROOT = Path(__file__).resolve().parents[1]


def main(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(ROOT / "site", out)
    tokens.write()  # make sure the packaged CSS is current
    shutil.copytree(ROOT / "src" / "subscout" / "runtime", out / "runtime")
    (out / ".nojekyll").touch()
    print(f"wrote {out}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site")
