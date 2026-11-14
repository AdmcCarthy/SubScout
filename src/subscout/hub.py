"""A hub: one landing page over several built decks.

`subscout hub hub.yaml --out _hub` reads a small config and the decks it names, each already built with
`subscout build`, and writes a self-contained site: `index.html`, and a copy of each deck under its key whose own
landing page is replaced by a redirect to the hub. Nothing is computed: categories, slide counts and links come from
the built pages, and every dataset of a deck shaped as a diagram (`{box, shapes}`) is drawn as static SVG on a wall
of tiles. The page is a board in three columns: what was measured, the method, and what is known.
See styleguide/deck-format.md.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

import yaml

INK = {
    "c1": "var(--d1)",
    "c2": "var(--d2)",
    "c3": "var(--d3)",
    "c4": "var(--d4)",
    "c5": "var(--d5)",
    "context": "var(--dc)",
    "text": "var(--ink)",
    "muted": "var(--muted)",
    "surface": "var(--module)",
}
PAYLOAD = re.compile(r'<script type="application/json" id="deck-data">(.*?)</script>', re.S)
REDIRECT = (
    '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=../index.html#learn">'
    '<title>{name}</title><a href="../index.html#learn">{name}</a>\n'
)
REQUIRED = ("title", "headline", "decks")


def is_diagram(d) -> bool:
    return isinstance(d, dict) and "box" in d and isinstance(d.get("shapes"), list)


def read_deck(deck: dict, base: Path) -> dict:
    """Categories, slide counts, named relations and diagrams of one built deck, from its pages alone."""
    site = (base / deck["site"]).resolve()
    if not (site / "index.html").exists():
        raise FileNotFoundError(f"deck '{deck['key']}': no built deck at {site} (run `subscout build` first)")
    deck["path"], deck["href"] = site, f"{deck['key']}/"
    pages = []
    for f in sorted(site.glob("*.html")):
        m = PAYLOAD.search(f.read_text(encoding="utf-8"))
        if m:
            pages.append(json.loads(m.group(1).replace("<\\/", "</")))
    pages.sort(key=lambda p: int(p["num"]))
    deck["categories"], deck["where"], deck["diagrams"], named = [], {}, {}, set()
    for p in pages:
        figs = {s["fig"] for s in p["slides"] if s.get("fig")}
        deck["categories"].append(
            {
                "n": int(p["num"]),
                "slug": p["slug"],
                "title": p["title"],
                "slides": len(p["slides"]) - 1,
                "figures": len(figs),
            }
        )
        deck["diagrams"].update({k: v for k, v in p.get("datasets", {}).items() if is_diagram(v)})
        for k, s in enumerate(p["slides"], 1):
            name = re.search(r'class="concept-name">(.*?)<', s.get("html", ""))
            if name:
                named.add((p["slug"], s.get("topic")))
            data = (p["figures"].get(s.get("fig") or "") or {}).get("data") or []
            for key in data if isinstance(data, list) else [data]:
                if key in deck["diagrams"] and key not in deck["where"]:
                    deck["where"][key] = {
                        "href": f"{deck['href']}{p['slug']}.html#{k}",
                        "name": html.unescape(name.group(1)) if name else "",
                        "title": re.sub("<[^>]+>", "", s.get("title") or ""),
                    }
    deck["slides"] = sum(c["slides"] for c in deck["categories"])
    deck["figures"] = sum(c["figures"] for c in deck["categories"])
    deck["cards"] = len(named)
    return deck


def svg(d, text=True, uid="m"):
    """A diagram dataset as static SVG, by the rules of figures/schematic.js; labels left out for a tile."""
    x0, y0, x1, y1 = d["box"]
    w, h = x1 - x0, y1 - y0

    def X(v):
        return round(v - x0, 3)

    def Y(v):
        return round(y1 - v, 3)

    u = w / 520  # one screen pixel at a nominal width, in box units

    def pts(p):
        return " ".join(f"{X(a)},{Y(b)}" for a, b in p)

    out, marks = [], set()
    for s in d["shapes"]:
        k = s["kind"]
        if k == "poly":
            stroke = "none" if s.get("stroke") == "none" else INK[s.get("stroke", "text")]
            out.append(
                f'<polygon points="{pts(s["pts"])}" fill="{INK[s["fill"]] if s.get("fill") else "none"}" fill-opacity="{s.get("opacity", 0.5)}" stroke="{stroke}" stroke-width="{s.get("width", 1.2) * u:.3f}"{dash(s, u)}/>'
            )
        elif k == "line":
            out.append(
                f'<polyline points="{pts(s["pts"])}" fill="none" stroke="{INK[s.get("colour", "text")]}" stroke-width="{s.get("width", 1.4) * u:.3f}" stroke-linecap="round"{dash(s, u)}/>'
            )
        elif k == "arrow":
            c = s.get("colour", "text")
            marks.add(c)
            ends = f' marker-end="url(#a-{uid}-{c})"' + (
                f' marker-start="url(#a-{uid}-{c})"' if s.get("double") else ""
            )
            out.append(
                f'<line x1="{X(s["from"][0])}" y1="{Y(s["from"][1])}" x2="{X(s["to"][0])}" y2="{Y(s["to"][1])}" stroke="{INK[c]}" stroke-width="{s.get("width", 1.8) * u:.3f}"{ends}/>'
            )
        elif k == "circle":
            stroke = "none" if s.get("stroke") == "none" else INK[s.get("stroke", "text")]
            out.append(
                f'<circle cx="{X(s["c"][0])}" cy="{Y(s["c"][1])}" r="{s["r"]}" fill="{INK[s["fill"]] if s.get("fill") else "none"}" fill-opacity="{s.get("opacity", 0.5)}" stroke="{stroke}" stroke-width="{s.get("width", 1.2) * u:.3f}"/>'
            )
        elif k == "text" and text:
            size = 11.5 * u * s.get("size", 1)
            anchor = {"start": "start", "middle": "middle", "end": "end"}[s.get("anchor", "start")]
            rot = (
                f' transform="rotate({-s["rotate"]},{X(s["at"][0])},{Y(s["at"][1])})"'
                if s.get("rotate")
                else ""
            )
            style = ("font-weight:600;" if s.get("bold") else "") + (
                "font-style:italic;" if s.get("italic") else ""
            )
            out.append(
                f'<text x="{X(s["at"][0])}" y="{Y(s["at"][1])}" font-size="{size:.3f}" text-anchor="{anchor}" dominant-baseline="middle" fill="{INK[s.get("colour", "text")]}" style="{style}"{rot}>{html.escape(s["text"])}</text>'
            )
    defs = "".join(
        f'<marker id="a-{uid}-{c}" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M0,0.8 L10,5 L0,9.2 z" fill="{INK[c]}"/></marker>'
        for c in sorted(marks)
    )
    return f'<svg viewBox="0 0 {w:.3f} {h:.3f}" preserveAspectRatio="xMidYMid meet" aria-hidden="true"><defs>{defs}</defs>{"".join(out)}</svg>'


def dash(s, u):
    return f' stroke-dasharray="{5 * u:.3f} {4 * u:.3f}"' if s.get("dash") else ""


CSS = """
:root{--bg:#e6e8eb;--panel:#eff1f3;--module:#fafbfc;--ink:#1b1e23;--muted:#757c86;--line:#cdd2d8;--accent:#e4572e;--accent-soft:#f6c9bb;--glow:rgba(228,87,46,.18);
--d1:#e4572e;--d2:#3f8fcf;--d3:#c0264d;--d4:#7a5cab;--d5:#1f8a80;--dc:#9aa1aa;--shadow:0 1px 0 #fff inset,0 18px 40px -22px rgba(20,24,30,.35),0 2px 6px -2px rgba(20,24,30,.18);
--mono:ui-monospace,"SF Mono","JetBrains Mono","Cascadia Mono",Consolas,monospace;--sans:"Inter","Segoe UI Variable Text","Segoe UI",system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#121418;--panel:#181b20;--module:#22262c;--ink:#e9ecef;--muted:#8b929c;--line:#343941;--accent:#ff7a52;--accent-soft:#5a2e22;--glow:rgba(255,122,82,.2);
--d1:#ff8a63;--d2:#6fb1e6;--d3:#ef6a8a;--d4:#a990d6;--d5:#4fc0b4;--dc:#6c737d;--shadow:0 1px 0 rgba(255,255,255,.05) inset,0 18px 40px -22px #000,0 2px 6px -2px #000}}
:root[data-theme=dark]{--bg:#121418;--panel:#181b20;--module:#22262c;--ink:#e9ecef;--muted:#8b929c;--line:#343941;--accent:#ff7a52;--accent-soft:#5a2e22;--glow:rgba(255,122,82,.2);
--d1:#ff8a63;--d2:#6fb1e6;--d3:#ef6a8a;--d4:#a990d6;--d5:#4fc0b4;--dc:#6c737d;--shadow:0 1px 0 rgba(255,255,255,.05) inset,0 18px 40px -22px #000,0 2px 6px -2px #000}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);line-height:1.5;-webkit-font-smoothing:antialiased;
background-image:linear-gradient(var(--line) 1px,transparent 1px),linear-gradient(90deg,var(--line) 1px,transparent 1px);background-size:56px 56px;background-position:-1px -1px;background-attachment:fixed}
body::before{content:"";position:fixed;inset:0;background:radial-gradient(1200px 700px at 50% 0,transparent,var(--bg) 78%);pointer-events:none;z-index:0}
a{color:inherit}main,header,footer{position:relative;z-index:1}
.wrap{max-width:1320px;margin:0 auto;padding:0 28px}
.mono{font-family:var(--mono);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
header{display:flex;align-items:center;justify-content:space-between;padding:22px 0}
.brand{display:flex;gap:10px;align-items:center;font-weight:600;font-size:1.05rem;text-decoration:none}
.brand i{width:14px;height:14px;border:2px solid var(--accent);transform:rotate(45deg);border-radius:3px;display:block}
nav{display:flex;gap:26px;align-items:center}nav a{text-decoration:none;font-size:.9rem;color:var(--muted)}nav a:hover{color:var(--ink)}
.theme{font-family:var(--mono);font-size:.7rem;letter-spacing:.1em;border:1px solid var(--line);background:var(--module);color:var(--muted);border-radius:999px;padding:6px 12px;cursor:pointer}
/* ---------------------------------------------------------------- the board */
.board{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:34px 0;box-shadow:var(--shadow);overflow:hidden}
.board::after{content:"";position:absolute;inset:10px;border:1px dashed var(--line);border-radius:14px;pointer-events:none}
.grid{position:relative;display:grid;grid-template-columns:4% 26% 7% 26% 7% 26% 4%;min-height:600px}
.col{display:grid;gap:22px;z-index:2}
.col.l{grid-column:2}.col.c{grid-column:4;grid-template-rows:1fr !important}.col.r{grid-column:6}
.traces{position:absolute;inset:0;width:100%;height:100%;z-index:1}
.traces path{fill:none;stroke:var(--line);stroke-width:5;stroke-linecap:round}
.traces path.live{stroke:var(--accent);stroke-width:2.2;stroke-dasharray:3 9;animation:flow 1.6s linear infinite}
@keyframes flow{to{stroke-dashoffset:-24}}
.mod{position:relative;background:var(--module);border:1px solid var(--line);border-radius:14px;padding:16px 18px;box-shadow:var(--shadow);display:flex;flex-direction:column;justify-content:space-between;text-decoration:none;transition:transform .25s,border-color .25s}
a.mod:hover{transform:translateY(-3px);border-color:var(--accent)}
.mod .led{position:absolute;top:14px;right:14px;width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px var(--glow)}
.mod.k .led{background:var(--d5);box-shadow:0 0 0 4px color-mix(in srgb,var(--d5) 22%,transparent)}
.chip{display:inline-flex;gap:6px;align-items:center;background:var(--ink);color:var(--module);border-radius:6px;padding:4px 8px;font-family:var(--mono);font-size:.66rem;letter-spacing:.08em;width:max-content}
.mod h3{margin:10px 0 2px;font-size:1rem;letter-spacing:.01em}.mod p{margin:0;font-size:.84rem;color:var(--muted)}
.mod .num{font-family:var(--mono);font-size:.74rem;color:var(--ink);margin-top:10px;letter-spacing:.04em}
.core{padding:22px;border-radius:20px;gap:14px;justify-content:flex-start}
.core h1{margin:6px 0 0;font-size:clamp(1.5rem,2.3vw,2.15rem);line-height:1.08;letter-spacing:.01em;text-transform:uppercase;font-weight:650}
.core .tag{font-family:var(--mono);font-size:.82rem;color:var(--muted);line-height:1.55}
.screen{position:relative;flex:1;min-height:230px;border:1px solid var(--line);border-radius:12px;background:var(--panel);overflow:hidden}
.screen figure{position:absolute;inset:10px;margin:0;opacity:0;transition:opacity .6s;display:flex}.screen figure.on{opacity:1}
.screen svg{width:100%;height:100%}
.sel{display:grid;grid-template-columns:40px 1fr 40px;gap:8px;align-items:stretch}
.sel button{border:1px solid var(--line);background:var(--panel);color:var(--muted);border-radius:8px;cursor:pointer;font-size:1rem}
.sel a{background:var(--ink);color:var(--module);border-radius:8px;padding:11px 12px;font-family:var(--mono);font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;text-align:center;text-decoration:none;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.colhead{position:absolute;top:-22px;font-family:var(--mono);font-size:.66rem;letter-spacing:.16em;color:var(--muted)}
/* ---------------------------------------------------------------- sections */
section{padding:74px 0 0}h2{font-size:clamp(1.5rem,2.4vw,2.1rem);margin:8px 0 10px;letter-spacing:-.01em;max-width:22em}
.lead{color:var(--muted);max-width:46em;margin:0 0 26px}
.wall{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));grid-auto-rows:118px;grid-auto-flow:dense;gap:12px}
.tile{position:relative;background:var(--module);border:1px solid var(--line);border-radius:12px;padding:10px;display:flex;text-decoration:none;overflow:hidden;transition:transform .25s,border-color .25s,box-shadow .25s}
.tile.w{grid-column:span 2}.tile.t{grid-row:span 2}
.tile svg{width:100%;height:100%;transition:transform .5s}
.tile span{position:absolute;left:0;right:0;bottom:0;padding:18px 10px 8px;font-family:var(--mono);font-size:.62rem;letter-spacing:.08em;text-transform:uppercase;color:var(--ink);background:linear-gradient(transparent,var(--module) 55%);opacity:0;transition:opacity .25s}
.tile:hover,.tile:focus-visible{border-color:var(--accent);box-shadow:0 0 0 4px var(--glow);transform:translateY(-2px)}.tile:hover span,.tile:focus-visible span{opacity:1}.tile:hover svg{transform:scale(1.04)}
.tile b{position:absolute;top:8px;left:10px;font-family:var(--mono);font-size:.58rem;color:var(--muted);font-weight:500;letter-spacing:.1em}
.map{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px 18px 10px;overflow-x:auto}
.map svg{width:100%;min-width:980px;height:auto;display:block}
.map .stage{font-family:var(--mono);font-size:11px;letter-spacing:.16em;fill:var(--muted)}
.map .edge{fill:none;stroke-width:1.3;opacity:.38;transition:opacity .2s,stroke-width .2s}
.map .node rect:first-of-type{fill:var(--module);stroke:var(--line);stroke-width:1;transition:stroke .2s}
.map .node text{font-size:11.5px;fill:var(--ink);font-family:var(--sans)}.map .node{text-decoration:none;cursor:pointer}
.map.lit .edge{opacity:.06}.map.lit .node{opacity:.28}.map.lit .edge.on{opacity:.95;stroke-width:2.2}.map.lit .node.on{opacity:1}
.map.lit .node.me rect:first-of-type{stroke:var(--accent);stroke-width:2}
.legend{display:flex;flex-wrap:wrap;gap:6px 18px;margin:0 0 10px;font-size:.78rem;color:var(--muted)}.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.find{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.card{background:var(--module);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow)}
a.card{text-decoration:none;display:block;transition:transform .25s,border-color .25s}a.card:hover{transform:translateY(-3px);border-color:var(--accent)}.find.src .mod{min-height:150px}.card .big{font-size:1.9rem;font-weight:650;letter-spacing:-.02em;line-height:1.1;margin:10px 0 6px}.card p{margin:0;color:var(--muted);font-size:.9rem}
.grade{display:inline-block;font-family:var(--mono);font-size:.62rem;letter-spacing:.12em;text-transform:uppercase;border:1px solid currentColor;border-radius:999px;padding:2px 8px}
.grade.disagrees{color:var(--d3)}.grade.reproduced{color:var(--d5)}.grade.derived{color:var(--d2)}.grade.tested{color:var(--accent)}
.decks{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:22px}@media (max-width:980px){.decks{grid-template-columns:1fr}}
.deck{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px}
.deck h3{font-size:1.35rem;margin:6px 0 4px}.deck>p{color:var(--muted);margin:0 0 16px;font-size:.92rem}
.cats{display:grid;gap:6px}
.cat{display:grid;grid-template-columns:34px 1fr auto;gap:12px;align-items:baseline;padding:9px 12px;border-radius:10px;text-decoration:none;border:1px solid transparent}
.cat:hover{background:var(--module);border-color:var(--line)}.cat i{font-family:var(--mono);font-style:normal;font-size:.7rem;color:var(--muted)}
.cat em{font-family:var(--mono);font-style:normal;font-size:.66rem;color:var(--muted);letter-spacing:.06em}
.cat span{font-weight:600}.cat small{display:block;font-weight:400;font-size:.8rem;line-height:1.4;color:var(--muted);margin-top:2px}
.set{display:contents}.set[hidden]{display:none}.set .mod{animation:pop .45s ease both}@keyframes pop{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.set .mod{animation:none}}
.go{display:inline-block;margin-top:16px;background:var(--ink);color:var(--module);border-radius:10px;padding:10px 16px;text-decoration:none;font-size:.88rem}
.steps{display:grid;grid-template-columns:repeat(5,1fr);gap:0;border:1px solid var(--line);border-radius:14px;overflow:hidden;background:var(--module)}
.steps div{padding:18px;border-right:1px solid var(--line)}.steps div:last-child{border:0}.steps b{display:block;margin:8px 0 4px}.steps p{margin:0;font-size:.84rem;color:var(--muted)}
@media (max-width:980px){.steps{grid-template-columns:1fr}.steps div{border-right:0;border-bottom:1px solid var(--line)}}
footer{padding:60px 0 50px;color:var(--muted);font-size:.8rem}
@media (prefers-reduced-motion:reduce){.traces path.live{animation:none}.screen figure{transition:none}}
@supports (animation-timeline:view()){.rise{animation:rise linear both;animation-timeline:view();animation-range:entry 0% cover 22%}@keyframes rise{from{opacity:0;transform:translateY(22px)}to{opacity:1;transform:none}}}
"""

JS = """
const figs=[...document.querySelectorAll('.screen figure')],link=document.getElementById('sel');let i=0,timer;
function show(n){if(!figs.length)return;i=(n+figs.length)%figs.length;figs.forEach((f,k)=>f.classList.toggle('on',k===i));link.textContent=figs[i].dataset.name;link.href=figs[i].dataset.href;document.querySelectorAll('.set').forEach(e=>e.hidden=+e.dataset.i!==i);}
function play(){clearInterval(timer);if(!matchMedia('(prefers-reduced-motion: reduce)').matches)timer=setInterval(()=>show(i+1),document.querySelector('.set')?7000:4200);}
if(figs.length){document.getElementById('prev').onclick=()=>{show(i-1);play()};document.getElementById('next').onclick=()=>{show(i+1);play()};show(0);play();}
const root=document.documentElement,btn=document.getElementById('theme');
btn.onclick=()=>{const dark=root.dataset.theme?root.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;root.dataset.theme=dark?'light':'dark';try{localStorage.setItem('hub-theme',root.dataset.theme)}catch(e){}};
try{const t=localStorage.getItem('hub-theme');if(t)root.dataset.theme=t}catch(e){}
document.querySelectorAll('.map').forEach(m=>{const E=[...m.querySelectorAll('.edge')],N=[...m.querySelectorAll('.node')];
function walk(id,from,to,seen){E.forEach(e=>{if(e.dataset[from]===id){e.classList.add('on');const nx=e.dataset[to];if(!seen.has(nx)){seen.add(nx);walk(nx,from,to,seen)}}})}
function light(id){const seen=new Set([id]);E.forEach(e=>e.classList.remove('on'));walk(id,'b','a',seen);walk(id,'a','b',seen);N.forEach(n=>{n.classList.toggle('on',seen.has(n.dataset.id));n.classList.toggle('me',n.dataset.id===id)});m.classList.add('lit')}
N.forEach(n=>{n.addEventListener('mouseenter',()=>light(n.dataset.id));n.addEventListener('focus',()=>light(n.dataset.id));n.addEventListener('mouseleave',()=>m.classList.remove('lit'));n.addEventListener('blur',()=>m.classList.remove('lit'))})});
"""


def traces(n_left: int, n_right: int) -> str:
    """The traces of the board, in a 1000 x 600 box stretched to the grid: one from each module of the left column
    into the core, and one from the core to each module of the right."""

    def lanes(n):
        ys = [600 * (2 * i + 1) / (2 * n) for i in range(n)]
        mids = [300 + 45 * (i - (n - 1) / 2) for i in range(n)]
        return list(zip(ys, mids, strict=True))

    out = []
    for y, m in lanes(n_left):
        d = f"M300,{y:.0f} H322 L352,{m:.0f} H370"
        out.append(f'<path d="{d}"/><path class="live" d="{d}"/>')
    for y, m in lanes(n_right):
        d = f"M630,{m:.0f} H648 L678,{y:.0f} H700"
        out.append(f'<path d="{d}"/><path class="live" d="{d}"/>')
    return f'<svg class="traces" viewBox="0 0 1000 600" preserveAspectRatio="none" aria-hidden="true">{"".join(out)}</svg>'


MAP_INK = ["#3f8fcf", "#e4572e", "#1f8a80", "#7a5cab", "#c0264d", "#b8860b", "#5a8f3c", "#6b7280"]


def ontology(spec: dict, decks: list[dict], name: str) -> tuple[str, dict]:
    """The map of what depends on what: quantities as boxes in columns (one column per stage, from what is measured
    to what is decided), a line for every relation that turns one into another. Each box links to the page that
    teaches it; pointing at one lights everything it rests on and everything that rests on it.

    `spec` is {stages: [names], nodes: [{id, label, stage, deck, href}], relations: [{from: [ids], to: id, by: name}]}.
    The layout is computed here; the page only highlights."""
    stages, nodes, rels = spec.get("stages") or [], spec.get("nodes") or [], spec.get("relations") or []
    ids = [n["id"] for n in nodes]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{name}: map: node ids must be unique")
    by_id = {n["id"]: n for n in nodes}
    keys = [d["key"] for d in decks]
    edges = []
    for r in rels:
        for a in r.get("from") or []:
            if a not in by_id or r.get("to") not in by_id:
                raise ValueError(f"{name}: map: relation '{r.get('by')}' names an unknown node")
            if by_id[a]["stage"] > by_id[r["to"]]["stage"]:
                raise ValueError(f"{name}: map: relation '{r.get('by')}' runs backwards ({a} to {r['to']})")
            edges.append((a, r["to"], r.get("by", "")))
    for n in nodes:
        if n.get("deck") not in keys:
            raise ValueError(f"{name}: map: node '{n['id']}' names an unknown deck '{n.get('deck')}'")
    esc = html.escape
    w, bw, bh, gap, top = 1260, 196, 30, 9, 40
    cols = [[n for n in nodes if n["stage"] == s] for s in range(len(stages))]
    for col in cols:
        col.sort(key=lambda n: keys.index(n["deck"]))
    # two sweeps that pull each box towards the mean height of what it is joined to, keeping decks together
    height = top + max(len(c) for c in cols) * (bh + gap) + 10
    pos = {}

    def place():
        for s, col in enumerate(cols):
            x = (w - bw) * s / max(len(cols) - 1, 1)
            free = height - top - 10 - len(col) * bh
            step = free / (len(col) + 1)
            for i, n in enumerate(col):
                pos[n["id"]] = (x, top + step * (i + 1) + bh * i)

    place()
    for _ in range(3):
        for col in cols:

            def pull(n):
                ys = [pos[b][1] for a, b, _ in edges if a == n["id"]] + [
                    pos[a][1] for a, b, _ in edges if b == n["id"]
                ]
                return (keys.index(n["deck"]), sum(ys) / len(ys) if ys else pos[n["id"]][1])

            col.sort(key=pull)
        place()
    out = [
        f'<svg viewBox="0 0 {w} {height:.0f}" role="img" aria-label="Map of dependencies between quantities">'
    ]
    for s, label in enumerate(stages):
        x = (w - bw) * s / max(len(cols) - 1, 1)
        out.append(
            f'<text class="stage" x="{x + bw / 2:.0f}" y="16" text-anchor="middle">{esc(str(label).upper())}</text>'
        )
    for a, b, by in edges:
        (xa, ya), (xb, yb) = pos[a], pos[b]
        x0, y0, x1, y1 = xa + bw, ya + bh / 2, xb, yb + bh / 2
        mid = (x0 + x1) / 2
        if by_id[a]["stage"] == by_id[b]["stage"]:  # within one column: an arc round the right-hand side
            x1 = x0
            mid = x0 + 34 + 0.12 * abs(y1 - y0)
        colour = MAP_INK[keys.index(by_id[b]["deck"]) % len(MAP_INK)]
        out.append(
            f'<path class="edge" data-a="{esc(a)}" data-b="{esc(b)}" stroke="{colour}" d="M{x0:.0f},{y0:.0f} C{mid:.0f},{y0:.0f} {mid:.0f},{y1:.0f} {x1:.0f},{y1:.0f}"><title>{esc(by)}</title></path>'
        )
    for n in nodes:
        x, y = pos[n["id"]]
        colour = MAP_INK[keys.index(n["deck"]) % len(MAP_INK)]
        made = "; ".join(sorted({by for _, b, by in edges if b == n["id"] and by}))
        tip = f"{n['label']}" + (f": {made}" if made else ": measured")
        out.append(
            f'<a class="node" data-id="{esc(n["id"])}" href="{esc(n.get("href", "#"))}"><title>{esc(tip)}</title>'
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{bw}" height="{bh}" rx="7"/><rect x="{x:.0f}" y="{y:.0f}" width="5" height="{bh}" rx="2" fill="{colour}" stroke="none"/>'
            f'<text x="{x + 13:.0f}" y="{y + bh / 2 + 4:.0f}">{esc(n["label"])}</text></a>'
        )
    out.append("</svg>")
    used = [k for k in keys if any(n["deck"] == k for n in nodes)]
    names = {d["key"]: d["name"] for d in decks}
    legend = "".join(
        f'<span><i style="background:{MAP_INK[keys.index(k) % len(MAP_INK)]}"></i>{esc(names[k])}</span>'
        for k in used
    )
    body = f'<div class="map rise"><div class="legend">{legend}</div>{"".join(out)}</div>'
    return body, {"nodes": len(nodes), "relations": len(rels), "links": len(edges)}


def build_hub(config: Path, out: Path) -> dict:
    """Write the hub. Returns counts for the caller to print."""
    config = Path(config)
    hub = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
    missing = [k for k in REQUIRED if not hub.get(k)]
    if missing:
        raise ValueError(f"{config.name}: missing {missing}")
    keys = [d.get("key") for d in hub["decks"]]
    if len(set(keys)) != len(keys) or not all(k and re.fullmatch(r"[a-z0-9][a-z0-9-]*", k) for k in keys):
        raise ValueError(
            f"{config.name}: each deck needs its own `key` of lower-case letters, digits and hyphens"
        )
    decks = [read_deck(dict(d), config.parent) for d in hub["decks"]]
    esc = html.escape
    tiles, screen = [], []
    wide, on_screen = set(hub.get("wide") or []), list(hub.get("screen") or [])
    n = 0
    for deck in decks:
        for name, data in deck["diagrams"].items():
            w = deck["where"].get(name)
            if not w:
                continue
            n += 1
            uid = f"{deck['key']}{n}"
            cls = "tile rise" + (" w" if name in wide else "")
            label = w["name"] or w["title"]
            tiles.append(
                (
                    name,
                    f'<a class="{cls}" href="{w["href"]}" title="{esc(w["title"])}"><b>{n:02d}</b>'
                    f"{svg(data, text=False, uid=uid)}<span>{esc(label)}</span></a>",
                )
            )
            if name in on_screen or (not on_screen and len(screen) < 8):
                rank = on_screen.index(name) if name in on_screen else n
                screen.append(
                    (
                        rank,
                        f'<figure data-name="{esc(label)}" data-href="{w["href"]}">{svg(data, text=False, uid="s" + uid)}</figure>',
                    )
                )
    order = {k: i for i, k in enumerate(hub.get("order") or [])}
    tiles.sort(key=lambda t: order.get(t[0], 999))
    screen.sort()

    def module(m, kind):
        tag, href = ("a", f' href="{esc(m["href"])}"') if m.get("href") else ("div", "")
        return (
            f'<{tag} class="mod {kind}"{href}><i class="led"></i><div><span class="chip">{esc(m.get("chip", ""))}</span>'
            f"<h3>{esc(m['title'])}</h3><p>{esc(m.get('text', ''))}</p></div>"
            f'<div class="num">{esc(m.get("num", ""))}</div></{tag}>'
        )

    def column(key, default_head, default_modules):
        c = hub.get(key) or {}
        return c.get("head", default_head), c.get("modules") or default_modules

    by_deck = [
        {
            "chip": f"DECK {i:02d}",
            "title": d["name"],
            "text": d.get("line", ""),
            "num": f"{d['slides']} slides" + (f" · {d['cards']} relations named" if d["cards"] else ""),
            "href": f"{d['href']}{d['categories'][0]['slug']}.html",
        }
        for i, d in enumerate(decks, 1)
    ]
    left_head, left = column("left", "", [])
    right_head, right = column("right", "DECKS", by_deck)
    rows = max(len(left), len(right), 1)
    left_html = "".join(module(m, "d") for m in left)
    right_html = "".join(module(m, "k") for m in right)
    # revolving examples: each shows one diagram in the core with what goes into it on the left and what it
    # gives on the right; the two columns change with the diagram
    examples = hub.get("examples") or []
    if examples:
        by_key = {d["key"]: d for d in decks}
        screen, ins, outs = [], [], []
        for k, ex in enumerate(examples):
            d = by_key.get(ex.get("deck"))
            w = d and d["where"].get(ex.get("diagram"))
            if not w:
                raise ValueError(
                    f"{config.name}: example {k + 1}: no diagram '{ex.get('diagram')}' in deck '{ex.get('deck')}'"
                )
            label = ex.get("name") or w["name"] or w["title"]
            fig = svg(d["diagrams"][ex["diagram"]], text=False, uid=f"e{k}")
            screen.append((k, f'<figure data-name="{esc(label)}" data-href="{w["href"]}">{fig}</figure>'))
            hide = "" if k == 0 else " hidden"
            ins.append(
                f'<div class="set" data-i="{k}"{hide}>{"".join(module(m, "d") for m in ex.get("in") or [])}</div>'
            )
            outs.append(
                f'<div class="set" data-i="{k}"{hide}>{"".join(module(m, "k") for m in ex.get("out") or [])}</div>'
            )
        rows = max(
            max(len(ex.get("in") or []) for ex in examples),
            max(len(ex.get("out") or []) for ex in examples),
            1,
        )
        left_n = right_n = rows
        left_html, right_html = "".join(ins), "".join(outs)
        left_head, right_head = hub.get("in_head", "WHAT GOES IN"), hub.get("out_head", "WHAT IT EXPLAINS")
    else:
        left_n, right_n = len(left), len(right)

    def sub(d, c):
        text = ((hub.get("subtitles") or {}).get(d["key"]) or {}).get(c["slug"])
        return f"<small>{esc(text)}</small>" if text else ""

    deck_html = []
    for d in decks:
        cats = "".join(
            f'<a class="cat" href="{d["href"]}{c["slug"]}.html"><i>{c["n"]:02d}</i><span>{esc(c["title"])}{sub(d, c)}</span>'
            f"<em>{c['slides']} slides</em></a>"
            for c in d["categories"]
        )
        count = f"{d['slides']} slides · {d['figures']} figures" + (
            f" · {len(d['where'])} diagrams" if d["where"] else ""
        )
        deck_html.append(
            f'<div class="deck rise" id="{d["key"]}"><span class="mono">{count}</span><h3>{esc(d["name"])}</h3>'
            f'<p>{esc(d.get("line", ""))}</p><div class="cats">{cats}</div>'
            f'<a class="go" href="{d["href"]}{d["categories"][0]["slug"]}.html">Start at the beginning →</a></div>'
        )
    total = sum(d["slides"] for d in decks)

    def section(id_, kicker, key, body):
        s = hub.get(key) or {}
        if not body:
            return ""
        return (
            f'<section id="{id_}"><span class="mono">{esc(kicker)}</span><h2>{esc(s.get("title", ""))}</h2>'
            f'<p class="lead">{esc(s.get("text", ""))}</p>{body}</section>'
        )

    def cards(key):
        items = (hub.get(key) or {}).get("items") or []
        body = "".join(
            f'<{"a" if f.get("href") else "div"} class="card rise"{" href=" + chr(34) + esc(f["href"]) + chr(34) if f.get("href") else ""}>'
            f'<span class="grade {esc(f["grade"])}">{esc(f["grade"])}</span>'
            f'<div class="big">{esc(f["big"])}</div><p>{esc(f["text"])}</p></{"a" if f.get("href") else "div"}>'
            for f in items
        )
        return f'<div class="find">{body}</div>' if body else ""

    map_html, map_kicker, map_counts = "", "", {}
    if (hub.get("map") or {}).get("file"):
        spec = yaml.safe_load((config.parent / hub["map"]["file"]).read_text(encoding="utf-8")) or {}
        map_html, map_counts = ontology(spec, decks, config.name)
        map_kicker = f"{map_counts['nodes']} quantities · {map_counts['relations']} relations"
    steps = "".join(
        f'<div><span class="mono">{i:02d}</span><b>{esc(s["title"])}</b><p>{esc(s["text"])}</p></div>'
        for i, s in enumerate((hub.get("how") or {}).get("items") or [], 1)
    )
    src = "".join(module(m, "d") for m in (hub.get("sources") or {}).get("items") or [])
    # the reader who comes to learn is served first: where to go, then what the topics look like; how the material
    # was checked, what is left to follow up, the method and the data come after, as support
    parts = [
        (
            "learn",
            "Learn",
            section(
                "learn",
                f"{len(decks)} decks · {total} slides",
                "learn",
                f'<div class="decks">{"".join(deck_html)}</div>',
            ),
        ),
        ("map", "Map", section("map", map_kicker, "map", map_html)),
        (
            "diagrams",
            "Diagrams",
            section(
                "diagrams",
                f"{n} diagrams",
                "wall",
                f'<div class="wall">{"".join(t for _, t in tiles)}</div>' if tiles else "",
            ),
        ),
        (
            "verified",
            "Verified",
            section("verified", "Reproduced and verified", "verified", cards("verified")),
        ),
        (
            "followup",
            "Follow-up",
            section("followup", "Disagreements and open points", "followup", cards("followup")),
        ),
        (
            "method",
            "Method",
            section("method", "Method", "how", f'<div class="steps rise">{steps}</div>' if steps else ""),
        ),
        (
            "sources",
            "Data",
            section(
                "sources", "Measured data", "sources", f'<div class="find src">{src}</div>' if src else ""
            ),
        ),
    ]
    sections = [p[2] for p in parts]
    nav = "".join(f'<a href="#{i}">{label}</a>' for i, label, body in parts if body)
    selector = (
        '<div class="sel"><button id="prev" type="button" aria-label="Previous diagram">‹</button><a id="sel" href="#"></a>'
        '<button id="next" type="button" aria-label="Next diagram">›</button></div>'
        if screen
        else ""
    )
    panel = f'<div class="screen">{"".join(f for _, f in screen)}</div>' if screen else ""
    page = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>{esc(hub["title"])}</title><style>{CSS}.col{{grid-template-rows:repeat({rows},1fr)}}</style></head><body><div class="wrap">
<header><a class="brand" href="#top"><i></i>{esc(hub.get("brand") or hub["title"])}</a><nav>{nav}<button class="theme" id="theme" type="button">LIGHT / DARK</button></nav></header>
<main id="top">
<div class="board"><div class="grid">{traces(left_n, right_n)}
<div class="col l"><span class="colhead" style="left:4%">{esc(left_head)}</span>{left_html}</div>
<div class="col c"><div class="mod core"><span class="mono">{esc(hub.get("kicker", ""))}</span><h1>{esc(hub["headline"])}</h1>{panel}
<p class="tag">{esc(hub.get("tagline", ""))}</p>{selector}</div></div>
<div class="col r"><span class="colhead" style="left:70%">{esc(right_head)}</span>{right_html}</div>
</div></div>
{"".join(sections)}
</main><footer>{esc(hub.get("footer", ""))}</footer></div><script>{JS}</script></body></html>"""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.iterdir():  # emptied, not removed: a web server may be serving the folder
        shutil.rmtree(old) if old.is_dir() else old.unlink()
    for d in decks:
        shutil.copytree(d["path"], out / d["key"])
        (out / d["key"] / "index.html").write_text(
            REDIRECT.format(name=esc(d["name"])), encoding="utf-8", newline="\n"
        )
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")
    return {
        "decks": len(decks),
        "diagrams": n,
        "slides": total,
        **({"map": map_counts} if map_counts else {}),
    }
