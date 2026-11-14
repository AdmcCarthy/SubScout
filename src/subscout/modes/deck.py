"""Deck mode: presentation and teaching material as a site of screen-sized slides.

The folder is a story folder with one more file, `deck.yaml`, which groups the `##` sections of story.md into
categories. The build writes `index.html` (a card per category), `<slug>.html` per category (a cover, then one
slide per step) and `basis.html` (sources, every figure, every number). Nothing on a slide scrolls: the page
script steps text down to a floor, and `subscout fit` fails a deck whose text still overflows.
See styleguide/deck-format.md.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

import jinja2
import pandas as pd
import yaml
from latex2mathml.converter import convert as latex_to_mathml
from markdown_it import MarkdownIt

from ..build import (
    APPENDIX,
    BLOCK,
    CHART_TYPES,
    PKG,
    STEP,
    TABLE_KINDS,
    Figure,
    Report,
    Story,
    _py,
    _records,
    check_block,
    copy_custom_modules,
    custom_data_names,
    exact,
    open_story,
    payload_json,
    prepare,
    substitute,
    table_html,
)
from ..layouts import ALWAYS_FULL, WIDE_ASPECT

CONF = {"observed": "Observed", "derived": "Derived", "interpreted": "Interpreted", "parameter": "Parameter"}
MASTERS = ("side", "full")  # a figure beside its text, or across the slide with the text beneath
STATE_KEYS = ("focus", "note", "highlight", "sort", "view", "filter", "frame")
TOPIC = re.compile(r"(?m)^### (.+)\n")
CONCEPT = re.compile(r"^```concept\s*\n(.*?)\n```\s*$", re.S | re.M)
CONCEPT_KEYS = {"name", "formula", "where"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RESERVED = {"index", "basis"}
CONFIG_KEYS = {"brand", "categories", "full", "labels", "start", "footer", "noindex"}
CATEGORY_KEYS = {"slug", "title", "blurb", "sections"}


def plain(s: str) -> str:
    return re.sub("<[^>]+>", "", s or "")


def load_config(root: Path, report: Report) -> dict:
    """deck.yaml: the categories and what the pages say around them."""
    p = root / "deck.yaml"
    if not p.exists():
        report.error("deck mode needs a deck.yaml beside story.md (see styleguide/deck-format.md)")
        return {}
    try:
        cfg = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        report.error(f"deck.yaml: YAML error: {e}")
        return {}
    extra = set(cfg) - CONFIG_KEYS
    if extra:
        report.error(f"deck.yaml: unexpected key(s) {sorted(extra)}")
    cats = cfg.get("categories") or []
    if not cats:
        report.error("deck.yaml: 'categories' is required")
    seen: set[str] = set()
    for c in cats:
        slug = str(c.get("slug", ""))
        for k in ("slug", "title", "sections"):
            if not c.get(k):
                report.error(f"deck.yaml: category '{slug or c.get('title')}' needs '{k}'")
        if set(c) - CATEGORY_KEYS:
            report.error(f"deck.yaml: category '{slug}': unexpected key(s) {sorted(set(c) - CATEGORY_KEYS)}")
        if slug and (not SLUG.match(slug) or slug in RESERVED):
            report.error(
                f"deck.yaml: slug '{slug}' must be lower-case letters, digits and hyphens, not a page name"
            )
        if slug in seen:
            report.error(f"deck.yaml: slug '{slug}' is used twice")
        seen.add(slug)
    return cfg


class Deck:
    """The story parsed into slides, with the figures and datasets they use."""

    def __init__(self, src: Story, cfg: dict, report: Report) -> None:
        self.src, self.report = src, report
        self.sources, self.data, self.metrics = src.sources, src.data, src.metrics
        self.full = set(cfg.get("full") or [])
        self.used: dict = {}
        self.md = MarkdownIt("commonmark", {"html": True, "typographer": True}).enable("table")
        self.figs: dict[str, dict] = {}
        self.figures: list[Figure] = []
        self.concepts: list[dict] = []
        body = src.body
        self.appendix = "\n\n".join(m.group(1) for m in APPENDIX.finditer(body))
        body = APPENDIX.sub("", body)
        lead, *rest = re.split(r"(?m)^## (.+)$", body)
        self.lead = self.render(lead, "lead")
        self.sections: dict[str, list[dict]] = {}
        self.n_steps = 0
        for title, chunk in zip(rest[::2], rest[1::2], strict=True):
            if title.strip() in self.sections:
                report.error(f"section '{title.strip()}' appears twice; a deck needs each `##` heading once")
            self.sections[title.strip()] = self.walk(title.strip(), chunk)

    # ---------------------------------------------------------------- text
    def sub(self, text: str, where: str) -> str:
        return substitute(text, self.metrics, self.used, self.report, where)

    def render(self, md_text: str, where: str) -> str:
        return self.md.render(self.sub(md_text, where)) if md_text.strip() else ""

    def concept(self, text: str, where: str) -> str:
        """A `concept` block as the card that heads a slide's text: the name the literature gives the process, its
        governing relation set as mathematics, and what the symbols stand for. `formula` is LaTeX, one string or a
        list of them; it is turned into MathML here, so the page needs no script to show it."""
        try:
            spec = yaml.safe_load(text) or {}
        except yaml.YAMLError as e:
            self.report.error(f"{where}: concept: YAML error: {e}")
            return ""
        if not isinstance(spec, dict) or set(spec) - CONCEPT_KEYS:
            self.report.error(f"{where}: a concept block takes {sorted(CONCEPT_KEYS)}")
            return ""
        out = []
        if spec.get("name"):
            out.append(f'<p class="concept-name">{html.escape(str(spec["name"]))}</p>')
        formulas = spec.get("formula") or []
        for f in [formulas] if isinstance(formulas, str) else formulas:
            try:
                out.append(f'<div class="concept-formula">{latex_to_mathml(str(f), display="block")}</div>')
            except Exception as e:  # the converter raises its own errors for malformed LaTeX
                self.report.error(f"{where}: concept: formula not understood ({e}): {f}")
        if spec.get("where"):
            # symbols between dollar signs are set as mathematics, so that they match the formula above
            parts = re.split(r"\$(.+?)\$", str(spec["where"]))
            try:
                text = "".join(
                    latex_to_mathml(p) if i % 2 else self.md.renderInline(p) for i, p in enumerate(parts)
                )
            except Exception as e:
                self.report.error(f"{where}: concept: symbol not understood ({e})")
                text = ""
            out.append(f'<p class="concept-where">{text}</p>')
        self.concepts.append({"name": str(spec.get("name", "")), "where": where})
        return f'<div class="concept">{"".join(out)}</div>' if out else ""

    # ---------------------------------------------------------------- figures
    def master(self, spec: dict, where: str) -> str:
        """Which master a figure's slides use: `master:` on the block, then deck.yaml's `full` list, then its form.

        The side master is tall and the full master wide, so only a figure that is wider than it is high goes
        across the slide: a map, a network, a heatmap, or one that declares a wide `aspect`. A chart of many rows
        stays beside its text, unlike in a story, where the side column is narrow.
        """
        named = spec.get("master")
        if named:
            if named not in MASTERS:
                self.report.error(f"{where}: master '{named}' is not one of {list(MASTERS)}")
            return named if named in MASTERS else "side"
        wide = spec.get("type") in ALWAYS_FULL or float(spec.get("aspect") or 0) >= WIDE_ASPECT
        return "full" if wide or spec.get("module") in self.full else "side"

    def figure(self, kind: str, spec: dict, where: str) -> dict | None:
        """Register a chart or table block, or resolve a `use:` block against its base. Returns the view it gives."""
        for key in ("title", "subtitle", "notes"):
            if isinstance(spec.get(key), str):
                spec[key] = self.sub(spec[key], where)
        if "use" in spec:
            base = self.figs.get(spec["use"])
            if not base:
                self.report.error(f"{where}: use '{spec['use']}' refers to no earlier chart")
                return None
            state = {
                **base["state"],
                **{k: v for k, v in spec.items() if k not in ("use", "title", "subtitle")},
            }
            return {
                "fig": base["id"],
                "state": state,
                "title": spec.get("title") or base["title"],
                "subtitle": spec.get("subtitle") or base["subtitle"],
            }
        fid = spec.get("id") or f"fig{len(self.figs) + 1}"
        check_block(spec, fid, where, self.sources, self.report)
        where = f"{where} ({fid})"
        src = self.sources.get(spec.get("source")) or {}
        fig = {
            "id": fid,
            "kind": kind,
            "type": spec.get("type") or spec.get("kind", "league"),
            "title": spec.get("title", ""),
            "subtitle": spec.get("subtitle", ""),
            "state": {},
            "facts": {
                "source": src.get("name") or spec.get("source"),
                "url": src.get("url"),
                "accessed": src.get("accessed"),
                "unit": spec.get("unit"),
                "confidence": spec["confidence"],
                "notes": spec.get("notes"),
                "exception": spec.get("exception"),
            },
        }
        if kind == "table":
            if spec.get("kind", "league") not in TABLE_KINDS:
                self.report.error(f"{where}: kind must be one of {sorted(TABLE_KINDS)}")
            fig["html"] = table_html(spec, self.data, self.report, where)
        elif spec.get("type") not in CHART_TYPES:
            self.report.error(f"{where}: type must be one of {sorted(CHART_TYPES)}")
            return None
        else:
            payload = prepare(spec, self.data, self.report, where)
            if spec["type"] == "custom":
                names = custom_data_names(spec)
                fig.update(module=spec.get("module"), state=dict(spec.get("state") or {}))
            else:
                names = [ly["data"] for ly in spec.get("layers", [])] if spec["type"] == "map" else []
                fig.update(spec=spec, payload=payload, state={k: spec[k] for k in STATE_KEYS if k in spec})
            fig.update(data=names, master=self.master(spec, where))
            self.figures.append(Figure(fid, spec, "chart"))
        self.figs[fid] = fig
        return {"fig": fid, "state": fig["state"], "title": fig["title"], "subtitle": fig["subtitle"]}

    def blocks(self, chunk: str, where: str) -> tuple[str, list[dict]]:
        """Take the chart and table blocks out of a chunk; return the text left and the views they give."""
        views: list[dict] = []

        def repl(m: re.Match) -> str:
            try:
                spec = yaml.safe_load(m.group(2)) or {}
            except yaml.YAMLError as e:
                self.report.error(f"{where}: YAML error: {e}")
                return ""
            v = self.figure(m.group(1), spec, where)
            if v:
                views.append(v)
            return ""

        return BLOCK.sub(repl, chunk), views

    # ---------------------------------------------------------------- slides
    def walk(self, section: str, chunk: str) -> list[dict]:
        """One section as slides: a slide per step, and one for each run of text or figure between steps."""
        slides: list[dict] = []
        topic = None
        concept = ""  # the card of the current topic: it stays until the next topic or the next card
        last_view = None

        def loose(text: str) -> None:
            # text between steps, with any figure or table it carries: each block closes a slide
            pos = 0
            where = f"section '{section}'"
            for m in BLOCK.finditer(text):
                rest, views = self.blocks(text[pos : m.end()], where)
                if views:
                    slides.append(
                        {
                            "kind": "view",
                            "section": section,
                            "topic": None,
                            "html": self.render(rest, section),
                            **views[0],
                        }
                    )
                pos = m.end()
            if text[pos:].strip():
                slides.append(
                    {
                        "kind": "text",
                        "section": section,
                        "topic": topic,
                        "html": self.render(text[pos:], section),
                    }
                )

        pos = 0
        for m in STEP.finditer(chunk):
            loose(chunk[pos : m.start()])
            self.n_steps += 1
            where = f"step {self.n_steps}"
            raw = m.group(2)
            card = CONCEPT.search(raw)
            if card:
                raw = raw.replace(card.group(0), "", 1)
            content, views = self.blocks(raw, where)
            t = TOPIC.search(content + "\n")
            if t:
                topic = t.group(1).strip()
                content = content.replace(t.group(0).rstrip("\n"), "", 1)
                concept = ""
            if card:
                concept = self.concept(card.group(1), where)
            view = views[-1] if views else last_view
            if not view:
                self.report.warn(f"{where} has no chart")
                view = {}
            last_view = view
            slides.append(
                {
                    "kind": "view",
                    "section": section,
                    "topic": topic,
                    "step": self.n_steps,
                    "html": concept + self.render(content, where),
                    **view,
                }
            )
            pos = m.end()
        loose(chunk[pos:])
        return slides

    # ---------------------------------------------------------------- ledgers
    def ledger(self) -> list[dict]:
        return [
            {
                "name": k,
                "value": exact(u["metric"].value),
                "unit": u["metric"].unit,
                "shown": sorted(set(u["shown"])),
                "method": u["metric"].method,
                "source": (self.sources.get(u["metric"].source) or {}).get("name") or u["metric"].source,
                "confidence": u["metric"].confidence,
            }
            for k, u in self.used.items()
        ]


def _thumbnails(src: Story, report: Report) -> dict:
    """story.py may draw the cards of the landing page: `thumbnails(data) -> {slug: "<svg…>"}`."""
    fn = getattr(src.module, "thumbnails", None)
    if not fn:
        return {}
    out = fn(src.data) or {}
    if not isinstance(out, dict):
        report.error("story.py: thumbnails() must return a dict of slug -> SVG text")
        return {}
    return out


def _remove_old_pages(out: Path) -> None:
    """Pages of an earlier build of this deck whose category has since gone would otherwise stay in the site."""
    rep = out / "build-report.json"
    if not rep.exists():
        return
    try:
        old = json.loads(rep.read_text(encoding="utf-8"))
    except ValueError:
        return
    if old.get("mode") != "deck":
        return
    for p in old.get("pages", []):
        (out / f"{p['slug']}.html").unlink(missing_ok=True)


def build(root: Path, out: Path, runtime_href: str = "runtime") -> Report:
    root, out = Path(root).resolve(), Path(out).resolve()
    report = Report()
    src = open_story(root, report)
    cfg = load_config(root, report)
    if report.errors:
        return report
    deck = Deck(src, cfg, report)
    fm = src.fm
    cats = cfg["categories"]
    claimed = [s for c in cats for s in c["sections"]]
    for s in deck.sections:
        if claimed.count(s) != 1:
            report.error(f"deck.yaml: section '{s}' is in {claimed.count(s)} categories; it must be in one")
    for s in claimed:
        if s not in deck.sections:
            report.error(f"deck.yaml: no section '{s}' in story.md")
    if not report.errors and list(deck.sections) != claimed:
        report.warn("deck.yaml: the categories do not keep the order of the sections in story.md")
    thumbs = _thumbnails(src, report)
    for slug in thumbs:
        if slug not in {c["slug"] for c in cats}:
            report.warn(f"story.py: thumbnails() draws '{slug}', which is not a category")
    if report.errors:
        return report

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(PKG / "templates" / "deck"), autoescape=False)
    labels = cfg.get("labels") or {}
    shell = {
        "fm": fm,
        "brand": cfg.get("brand") or fm.get("short_title") or fm["title"],
        "palette": fm.get("palette", "tide"),
        "surface": fm.get("surface", src.cfg["surfaces"]["default"]),
        "runtime": runtime_href,
        "noindex": bool(cfg.get("noindex")),
        "esc": html.escape,
        "conf_label": CONF,
    }

    # each category: a cover, then its sections as slides
    nav = []
    pages = []
    for n, c in enumerate(cats, 1):
        slides: list[dict] = []
        groups = []
        for sec in c["sections"]:
            topics: list[dict] = []
            for s in deck.sections[sec]:
                slides.append(s)
                label = s["topic"] or ("Introduction" if s["kind"] == "text" else plain(s.get("title", "")))
                if not topics or topics[-1]["title"] != label:
                    topics.append({"title": label, "index": len(slides) + 1})  # 1-based, after the cover
            groups.append({"title": sec, "topics": topics})
        fig_ids = list(dict.fromkeys(s["fig"] for s in slides if s.get("fig")))
        c = {
            **c,
            "num": f"{n:02d}",
            "n_slides": len(slides),
            "n_figs": sum(1 for f in fig_ids if deck.figs[f]["kind"] == "chart"),
            "groups": groups,
            "thumb_svg": thumbs.get(c["slug"], ""),
        }
        nav.append(
            {k: c.get(k, "") for k in ("slug", "title", "num", "blurb", "n_slides", "n_figs", "thumb_svg")}
        )
        pages.append((c, slides, fig_ids))

    out.mkdir(parents=True, exist_ok=True)
    _remove_old_pages(out)
    for i, (c, slides, fig_ids) in enumerate(pages):
        cover = env.get_template("cover.html.j2").render(c=c, **shell)
        show = [{"kind": "cover", "section": c["title"], "topic": None, "html": cover}]
        for s in slides:
            d = {
                k: s.get(k)
                for k in ("kind", "section", "topic", "html", "fig", "state", "title", "subtitle", "step")
            }
            if s.get("fig") and deck.figs[s["fig"]]["kind"] == "table":
                d["kind"] = "table"
            show.append(d)
        figs, names = {}, set()
        for fid in fig_ids:
            f = deck.figs[fid]
            keys = ("kind", "type", "title", "module", "data", "master", "spec", "payload", "html", "facts")
            figs[fid] = {k: f[k] for k in keys if k in f}
            names |= set(f.get("data") or [])
        payload = {
            "slug": c["slug"],
            "num": c["num"],
            "title": c["title"],
            "multi": len(c["sections"]) > 1,
            "slides": show,
            "figures": figs,
            "datasets": {
                k: (_records(src.data[k]) if isinstance(src.data[k], pd.DataFrame) else src.data[k])
                for k in sorted(names)
                if k in src.data
            },
            "units": fm.get("units", "sm3"),
            "groups": fm.get("groups"),
            "prev": {"slug": nav[i - 1]["slug"], "title": nav[i - 1]["title"]} if i else None,
            "next": {"slug": nav[i + 1]["slug"], "title": nav[i + 1]["title"]} if i + 1 < len(nav) else None,
        }
        page = env.get_template("deck.html.j2").render(
            c=c, nav=nav, total=len(nav), payload=payload_json(payload, report), **shell
        )
        (out / f"{c['slug']}.html").write_text(page, encoding="utf-8")

    # landing page and basis
    kpis = []
    for k in fm.get("kpis") or []:
        if k.get("metric") not in deck.metrics:
            report.error(f"kpis: unknown metric '{k.get('metric')}'")
            continue
        expr = "{{ " + k["metric"] + (" | " + k["filter"] if k.get("filter") else "") + " }}"
        kpis.append({"html": deck.sub(expr, "kpis"), "label": k.get("label", "")})
    n_figs = sum(1 for f in deck.figs.values() if f["kind"] == "chart")
    counts = [
        {
            "html": str(deck.n_steps),
            "label": labels.get("views", "views, each one slide the size of the screen"),
        },
        {"html": str(n_figs), "label": labels.get("figures", "figures, each with its source and confidence")},
    ]
    footer = deck.md.renderInline(deck.sub(cfg["footer"], "footer")) if cfg.get("footer") else ""
    (out / "index.html").write_text(
        env.get_template("index.html.j2").render(
            nav=nav,
            kpis=counts + kpis,
            lead=deck.lead,
            start=cfg.get("start") or "Start",
            footer=footer,
            **shell,
        ),
        encoding="utf-8",
    )
    figure_list = [
        {"id": f["id"], "kind": f["kind"], "title": plain(f["title"]), "type": f["type"], **f["facts"]}
        for f in deck.figs.values()
    ]
    ledger = deck.ledger()
    (out / "basis.html").write_text(
        env.get_template("basis.html.j2").render(
            nav=nav,
            sources=src.sources,
            appendix=deck.render(deck.appendix, "appendix"),
            ledger=ledger,
            figure_list=figure_list,
            **shell,
        ),
        encoding="utf-8",
    )
    unused = sorted(set(deck.metrics) - set(deck.used))
    if unused:
        report.warn(f"metrics defined but not used: {', '.join(unused)}")
    if report.errors:
        return report

    copy_custom_modules(root, out, deck.figures, report)
    if runtime_href == "runtime":
        from .. import tokens

        tokens.write()
        if (out / "runtime").exists():
            shutil.rmtree(out / "runtime")
        shutil.copytree(PKG / "runtime", out / "runtime")
    (out / ".nojekyll").touch()
    (out / "build-report.json").write_text(
        json.dumps(
            {
                "mode": "deck",
                "errors": report.errors,
                "warnings": report.warnings,
                "advice": report.advice,
                "pages": [
                    {
                        "slug": c["slug"],
                        "title": c["title"],
                        "slides": c["n_slides"] + 1,
                        "figures": c["n_figs"],
                    }
                    for c, _, _ in pages
                ],
                "steps": deck.n_steps,
                "ledger": ledger,
                "figures": figure_list,
            },
            indent=1,
            ensure_ascii=False,
            default=_py,
        ),
        encoding="utf-8",
    )
    return report
