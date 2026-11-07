"""`subscout` command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import colour as C
from . import tokens


def cmd_tokens(args: argparse.Namespace) -> int:
    for p in tokens.write(Path(args.out) if args.out else None):
        print(f"wrote {p}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    results = C.contrast_audit()
    bad = [r for r in results if not r.passed]
    palette_failed = False
    for r in results if args.all else bad:
        mark = "ok  " if r.passed else "FAIL"
        print(f"{mark} {r.scheme:5} {r.tone:10} {r.fg:>16} on {r.bg:<14} Lc {r.lc:5.1f} (min {r.target:g})")
    print(f"{len(results) - len(bad)}/{len(results)} contrast rules pass")
    for scheme in C.SCHEMES:
        surface = C.to_hex(C.role_colour("neutral", "surface", scheme))
        for name in C.preset_names():
            a = C.palette_audit(C.story(scheme, name), surface)
            k = C.categorical_checks(C.categorical(scheme, name), scheme, surface)
            print(
                f"{scheme:5} {name:7} story CVD dE {a['min_cvd_delta_e']:.3f}"
                f" Lc {a['min_lc_on_background']:.0f}"
                f" | categorical {'PASS' if k['ok'] else 'FAIL'}: chroma {k['chroma']:.3f},"
                f" CVD dE {k['cvd']:.1f}, normal dE {k['normal']:.1f}, contrast {k['contrast']:.2f}:1"
            )
            palette_failed |= not k["ok"]
    return 1 if bad or palette_failed else 0


def cmd_build(args: argparse.Namespace) -> int:
    from .build import build

    rep = build(Path(args.story), Path(args.out))
    for w in rep.warnings:
        print(f"warning: {w}")
    for e in rep.errors:
        print(f"error: {e}")
    if rep.errors:
        print(f"build failed: {len(rep.errors)} error(s)")
        return 1
    print(f"built {args.story} -> {args.out} ({len(rep.warnings)} warning(s))")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from .export import render

    try:
        files = render(Path(args.site), scale=args.scale, only=args.figure or None)
    except ImportError:
        print(
            "subscout export needs Playwright: install subscout[export] and run `playwright install chromium`"
        )
        return 1
    print(f"rendered {len(files)} PNG(s) at {args.scale}x into {args.site}/export/*/png")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="subscout", description="SubScout data-narrative framework")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tokens", help="generate CSS/JSON design tokens")
    t.add_argument("--out", help="output directory (default: packaged runtime/css)")
    t.set_defaults(func=cmd_tokens)
    a = sub.add_parser("audit", help="check colour contrast and CVD separation")
    a.add_argument("--all", action="store_true", help="show passing rules too")
    a.set_defaults(func=cmd_audit)
    b = sub.add_parser("build", help="build a story folder into a static page")
    b.add_argument("story", help="folder containing story.md")
    b.add_argument("--out", default="_site", help="output directory")
    b.set_defaults(func=cmd_build)
    e = sub.add_parser("export", help="render export pages to high-resolution PNGs (needs Playwright)")
    e.add_argument("site", help="built site folder (after `subscout build`)")
    e.add_argument(
        "--scale", type=int, default=3, help="pixel density (default 3: a 1600 x 900 slide -> 4800 x 2700)"
    )
    e.add_argument("--figure", action="append", help="only this figure id (repeatable)")
    e.set_defaults(func=cmd_export)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
