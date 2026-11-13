"""`subscout` command line."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import colour as C
from . import tokens
from .fit import SIZES as DECK_SIZES


def cmd_tokens(args: argparse.Namespace) -> int:
    for p in tokens.write(Path(args.out) if args.out else None):
        print(f"wrote {p}")
    return 0


def cmd_symbols(args: argparse.Namespace) -> int:
    from . import symbols

    try:
        for p in symbols.write(Path(args.out) if args.out else None):
            print(f"wrote {p}")
    except symbols.SymbolError as e:
        print(f"symbols.toml: {e}")
        return 1
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

    rep = build(Path(args.story), Path(args.out), mode=args.mode)
    for w in rep.warnings:
        print(f"warning: {w}")
    for a in rep.advice:
        print(f"advice: {a}")
    for e in rep.errors:
        print(f"error: {e}")
    if rep.errors:
        print(f"build failed: {len(rep.errors)} error(s)")
        return 1
    built = json.loads((Path(args.out) / "build-report.json").read_text(encoding="utf-8"))
    for pg in built.get("pages", []):
        print(f"  {pg['slug']:<16}{pg['slides']:>3} slides {pg['figures']:>3} figures  {pg['title']}")
    print(f"built {args.story} -> {args.out} as a {built['mode']} ({len(rep.warnings)} warning(s))")
    return 0


def cmd_fit(args: argparse.Namespace) -> int:
    from . import fit

    try:
        res = fit.check(
            Path(args.site),
            sizes=tuple(args.size.split(",")),
            pages=args.pages.split(",") if args.pages else None,
            slides=args.slides,
            dark=args.dark,
            shots=Path(args.shots) if args.shots else None,
            wait=args.wait,
            channel=args.channel,
        )
    except ImportError:
        print("`subscout fit` needs Playwright among the development dependencies (uv add --dev playwright)")
        return 2
    except (ValueError, FileNotFoundError) as e:
        print(f"error: {e}")
        return 2
    for e in res.errors:
        print(f"error: {e}")
    for q in res.problems:
        print(f"problem: {q}")
    if res.small:
        print(
            f"text stepped down below {fit.SMALL:g} of its size (shorten these first): {', '.join(res.small)}"
        )
    print(
        f"{res.slides} slide views checked; {len(res.problems)} layout problem(s); {len(res.errors)} error(s)"
    )
    return 0 if res.ok else 1


def cmd_export(args: argparse.Namespace) -> int:
    print(
        "`subscout export` has moved to Plate (print-grade PDF and PNG at A4 to A0).\n"
        f"  uv run plate render {args.site}   (github.com/AdmcCarthy/Plate)\n"
        "SubScout still writes export/<id>/ pages and payload.json (the export contract) "
        "for figures with `export:`."
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="subscout", description="SubScout data-narrative framework")
    sub = p.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tokens", help="generate CSS/JSON design tokens")
    t.add_argument("--out", help="output directory (default: packaged runtime/css)")
    t.set_defaults(func=cmd_tokens)
    y = sub.add_parser("symbols", help="generate the well and installation symbol data (JS and JSON)")
    y.add_argument("--out", help="output directory (default: packaged runtime/js)")
    y.set_defaults(func=cmd_symbols)
    a = sub.add_parser("audit", help="check colour contrast and CVD separation")
    a.add_argument("--all", action="store_true", help="show passing rules too")
    a.set_defaults(func=cmd_audit)
    b = sub.add_parser("build", help="build a story folder in its mode: a story page, or a deck of slides")
    b.add_argument("story", help="folder containing story.md")
    b.add_argument("--out", default="_site", help="output directory")
    b.add_argument("--mode", choices=["story", "deck"], help="override `mode:` in the front matter")
    b.set_defaults(func=cmd_build)
    f = sub.add_parser("fit", help="deck mode: check that every slide of a built deck holds on one screen")
    f.add_argument("site", nargs="?", default="_site", help="the built deck")
    f.add_argument(
        "--size", default=",".join(DECK_SIZES), help="screen sizes, e.g. 1600x900 or several with commas"
    )
    f.add_argument(
        "--pages", help="category slugs, with commas (default: all, and the landing and basis pages)"
    )
    f.add_argument("--slides", help="slide numbers within each page, e.g. 1,5-9")
    f.add_argument("--dark", action="store_true", help="check the dark scheme")
    f.add_argument("--shots", help="folder for a screenshot of every slide visited")
    f.add_argument("--wait", type=int, default=1100, help="ms to let a slide settle")
    f.add_argument(
        "--channel", help="browser channel, e.g. chrome (default: Playwright's Chromium, else Chrome)"
    )
    f.set_defaults(func=cmd_fit)
    e = sub.add_parser("export", help="moved to Plate (prints where)")
    e.add_argument("site", nargs="?", default="_site")
    e.set_defaults(func=cmd_export)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
