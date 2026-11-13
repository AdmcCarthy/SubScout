"""Story mode: one argument on one scrolling page, with its Read and Present views.

Pipeline: front matter → data → story.py (datasets, metrics) → {{ expressions }} → blocks
(chart/table) → steps → Markdown → template → checks → output. See styleguide/story-format.md.
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
from markdown_it import MarkdownIt

from ..advice import style_advice
from ..build import (
    APPENDIX,
    ARCS,
    BLOCK,
    CHART_TYPES,
    PKG,
    REGISTERS,
    STEP,
    TABLE_KINDS,
    Figure,
    Report,
    _py,
    _records,
    check_block,
    check_header,
    copy_custom_modules,
    copy_header_data,
    custom_data_names,
    exact,
    open_story,
    parse_attrs,
    payload_json,
    prepare,
    substitute,
    table_html,
    write_exports,
)
from ..layouts import choose as choose_layout
from ..layouts import normalise as normalise_layout


def build(root: Path, out: Path, runtime_href: str = "runtime") -> Report:
    root, out = Path(root).resolve(), Path(out).resolve()
    report = Report()
    src = open_story(root, report)
    fm, body, sources, data, metrics, cfg = src.fm, src.body, src.sources, src.data, src.metrics, src.cfg
    register = fm.get("register", "section")
    if register not in REGISTERS:
        report.error(f"front matter: register '{register}' not one of {REGISTERS}")
    header = check_header(fm, data, report)

    used: dict = {}
    # appendix content
    extra_appendix = "\n\n".join(m.group(1) for m in APPENDIX.finditer(body))
    body = APPENDIX.sub("", body)

    figures: list[Figure] = []
    by_id: dict[str, Figure] = {}

    def take_blocks(chunk: str, step_index: int | None) -> tuple[str, list[str]]:
        ids = []

        def repl(m: re.Match) -> str:
            kind = m.group(1)
            where = f"{kind} block {len(figures) + 1}"
            try:
                spec = yaml.safe_load(m.group(2)) or {}
            except yaml.YAMLError as e:
                report.error(f"{where}: YAML error: {e}")
                return ""
            for key in ("title", "subtitle", "notes"):
                if isinstance(spec.get(key), str):
                    spec[key] = substitute(spec[key], metrics, used, report, where)
            if "use" in spec:
                base = by_id.get(spec["use"])
                if not base:
                    report.error(f"{where}: use '{spec['use']}' refers to no earlier chart")
                    return ""
                fid = f"{spec['use']}@{len(figures)}"
                fig = Figure(fid, spec, "state", step_index)
                figures.append(fig)
                ids.append(fid)
                return ""
            fid = spec.get("id") or f"fig{len(figures) + 1}"
            check_block(spec, fid, where, sources, report)
            if kind == "chart":
                if spec.get("type") not in CHART_TYPES:
                    report.error(f"{where} ({fid}): type must be one of {sorted(CHART_TYPES)}")
                    return ""
                fig = Figure(fid, spec, "chart", step_index, prepare(spec, data, report, f"{where} ({fid})"))
            else:
                if spec.get("kind", "league") not in TABLE_KINDS:
                    report.error(f"{where} ({fid}): kind must be one of {sorted(TABLE_KINDS)}")
                fig = Figure(
                    fid, spec, "table", step_index, html=table_html(spec, data, report, f"{where} ({fid})")
                )
            figures.append(fig)
            by_id[fid] = fig
            ids.append(fid)
            return f"\n\n<!--SSFIG:{fid}-->\n\n" if step_index is None else ""

        return BLOCK.sub(repl, chunk), ids

    md = MarkdownIt("commonmark", {"html": True, "typographer": True}).enable("table")

    # walk the body: alternate prose and runs of consecutive steps
    sections: list[dict] = []
    pos = 0
    steps_meta: list[dict] = []
    beats: list[str] = []
    for m in STEP.finditer(body):
        before = body[pos : m.start()]
        if before.strip():
            sections.append({"kind": "prose", "md": take_blocks(before, None)[0]})
        attrs = parse_attrs(m.group(1))
        if attrs.get("beat"):
            beats.append(attrs["beat"])
        idx = len(steps_meta)
        content, ids = take_blocks(m.group(2), idx)
        step = {"index": idx, "attrs": attrs, "md": content, "figs": ids}
        steps_meta.append(step)
        if sections and sections[-1]["kind"] == "scrolly" and not before.strip():
            sections[-1]["steps"].append(step)
        else:
            sections.append({"kind": "scrolly", "steps": [step]})
        pos = m.end()
    if body[pos:].strip():
        sections.append({"kind": "prose", "md": take_blocks(body[pos:], None)[0]})
    report.advice.extend(style_advice(body))

    # render
    for s in sections:
        if s["kind"] == "prose":
            chunk = substitute(s["md"], metrics, used, report, "prose")
            h = md.render(chunk)
            for f in figures:
                h = h.replace(f"<!--SSFIG:{f.id}-->", f'<div class="ss-inline-fig" data-fig="{f.id}"></div>')
            s["html"] = h
        else:
            for st in s["steps"]:
                st["html"] = md.render(substitute(st["md"], metrics, used, report, f"step {st['index'] + 1}"))
                if not st["figs"]:
                    report.warn(f"step {st['index'] + 1} has no chart; it will keep the previous view")
            s["figs"] = list(dict.fromkeys(f.split("@")[0] for st in s["steps"] for f in st["figs"]))
            named = []
            for st in s["steps"]:
                try:
                    named.append(normalise_layout(st["attrs"].get("layout")))
                except ValueError as e:
                    report.error(f"step {st['index'] + 1}: {e}")
            base = []
            for fid in s["figs"]:
                f = by_id.get(fid)
                f = by_id.get(f.spec.get("use"), f) if f is not None and f.kind == "state" else f
                if f is not None and f.kind == "chart":
                    base.append((f.spec, f.payload))
            s["layout"], why = choose_layout(next((n for n in named if n), None), base)
            report.advice.append(
                f"scrolly starting at step {s['steps'][0]['index'] + 1}: layout {s['layout']} ({why})"
            )

    # arc check
    arc = fm.get("arc")
    if arc:
        if arc not in ARCS:
            report.error(f"front matter: unknown arc '{arc}' (one of {sorted(ARCS)})")
        else:
            expected = ARCS[arc]
            missing = [b for b in expected if b not in beats and b not in ("support", "instance", "open")]
            unknown = [b for b in beats if b not in expected]
            if missing:
                report.warn(f"arc '{arc}': missing beat(s) {missing}")
            if unknown:
                report.warn(f"arc '{arc}': beat(s) {unknown} are not part of this arc")
            order = [expected.index(b) for b in beats if b in expected]
            if order != sorted(order):
                report.warn(f"arc '{arc}': beats out of order: {beats}")

    appendix_html = (
        md.render(substitute(extra_appendix, metrics, used, report, "appendix")) if extra_appendix else ""
    )

    # KPIs
    kpis = []
    for k in fm.get("kpis") or []:
        extra = set(k) - {"metric", "label", "filter"}
        if extra:
            report.error(
                f"kpis: unexpected key(s) {sorted(extra)} for '{k.get('metric')}' (quote labels that contain commas)"
            )
        m = metrics.get(k.get("metric"))
        if not m:
            report.error(f"kpis: unknown metric '{k.get('metric')}'")
            continue
        shown = substitute(
            "{{ " + k["metric"] + (" | " + k["filter"] if k.get("filter") else "") + " }}",
            metrics,
            used,
            report,
            "kpis",
        )
        kpis.append({"html": shown, "label": k.get("label", "")})

    if report.errors:
        return report

    # payload
    used_data: set[str] = set()
    figs_payload = {}
    for f in figures:
        if f.kind == "chart":
            figs_payload[f.id] = {"spec": f.spec, "data": f.payload}
            if f.spec.get("type") == "map":
                used_data |= {ly["data"] for ly in f.spec.get("layers", [])}
            if f.spec.get("type") == "custom":
                used_data |= set(custom_data_names(f.spec))
        elif f.kind == "state":
            figs_payload[f.id] = {
                "use": f.spec["use"],
                "state": {k: v for k, v in f.spec.items() if k != "use"},
            }
    datasets = {n: (_records(data[n]) if isinstance(data[n], pd.DataFrame) else data[n]) for n in used_data}
    steps_payload = [{"figs": st["figs"]} for st in steps_meta]

    ledger = [
        {
            "name": k,
            "value": exact(u["metric"].value),
            "unit": u["metric"].unit,
            "shown": sorted(set(u["shown"])),
            "method": u["metric"].method,
            "source": u["metric"].source,
            "confidence": u["metric"].confidence,
        }
        for k, u in used.items()
    ]
    unused = sorted(set(metrics) - set(used))
    if unused:
        report.warn(f"metrics defined but not used: {', '.join(unused)}")
    figure_list = [
        {
            "id": f.id,
            "kind": f.kind,
            "title": re.sub("<[^>]+>", "", f.spec.get("title", "")),
            "type": f.spec.get("type") or f.spec.get("kind"),
            "source": f.spec.get("source"),
            "confidence": f.spec.get("confidence"),
            "notes": f.spec.get("notes"),
            "exception": f.spec.get("exception"),
        }
        for f in figures
        if f.kind in ("chart", "table")
    ]

    env = jinja2.Environment(loader=jinja2.FileSystemLoader(PKG / "templates"), autoescape=False)
    tpl = env.get_template("story.html.j2")
    ctx = dict(
        fm=fm,
        header=header,
        sections=sections,
        figures={f.id: f for f in figures},
        kpis=kpis,
        sources=sources,
        ledger=ledger,
        figure_list=figure_list,
        extra_appendix=appendix_html,
        arc=arc,
        arc_beats=ARCS.get(arc, []),
        register=register,
        runtime=runtime_href,
        palette=fm.get("palette", "tide"),
        surface=fm.get("surface", cfg["surfaces"]["default"]),
        has_scrolly=any(s["kind"] == "scrolly" for s in sections),
        payload=payload_json(
            {
                "figures": figs_payload,
                "datasets": datasets,
                "steps": steps_payload,
                "units": fm.get("units", "sm3"),
                "groups": fm.get("groups"),
            },
            report,
        ),
        esc=html.escape,
        conf_label={
            "observed": "Observed",
            "derived": "Derived",
            "interpreted": "Interpreted",
            "parameter": "Parameter",
        },
    )
    macros = tpl.make_module(ctx)
    for s in sections:
        if s["kind"] == "prose":
            for f in figures:
                ph = f'<div class="ss-inline-fig" data-fig="{f.id}"></div>'
                if ph in s["html"]:
                    s["html"] = s["html"].replace(ph, f'<div class="ss-inline-fig">{macros.figure(f)}</div>')
    page = tpl.render(**ctx)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    copy_custom_modules(root, out, figures, report)
    copy_header_data(root, out, fm, header)
    write_exports(out, figures, figs_payload, data, steps_meta, fm, sources, runtime_href, report)
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
                "mode": "story",
                "errors": report.errors,
                "warnings": report.warnings,
                "advice": report.advice,
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
