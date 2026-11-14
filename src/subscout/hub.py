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
    '<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=../index.html#decks">'
    '<title>{name}</title><a href="../index.html#decks">{name}</a>\n'
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
.find{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.card{background:var(--module);border:1px solid var(--line);border-radius:14px;padding:18px 20px;box-shadow:var(--shadow)}
.card .big{font-size:1.9rem;font-weight:650;letter-spacing:-.02em;line-height:1.1;margin:10px 0 6px}.card p{margin:0;color:var(--muted);font-size:.9rem}
.grade{display:inline-block;font-family:var(--mono);font-size:.62rem;letter-spacing:.12em;text-transform:uppercase;border:1px solid currentColor;border-radius:999px;padding:2px 8px}
.grade.disagrees{color:var(--d3)}.grade.reproduced{color:var(--d5)}.grade.derived{color:var(--d2)}.grade.tested{color:var(--accent)}
.decks{display:grid;grid-template-columns:1fr 1fr;gap:22px}@media (max-width:980px){.decks{grid-template-columns:1fr}}
.deck{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:24px}
.deck h3{font-size:1.35rem;margin:6px 0 4px}.deck>p{color:var(--muted);margin:0 0 16px;font-size:.92rem}
.cats{display:grid;gap:6px}
.cat{display:grid;grid-template-columns:34px 1fr auto;gap:12px;align-items:baseline;padding:9px 12px;border-radius:10px;text-decoration:none;border:1px solid transparent}
.cat:hover{background:var(--module);border-color:var(--line)}.cat i{font-family:var(--mono);font-style:normal;font-size:.7rem;color:var(--muted)}
.cat em{font-family:var(--mono);font-style:normal;font-size:.66rem;color:var(--muted);letter-spacing:.06em}
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
function show(n){if(!figs.length)return;i=(n+figs.length)%figs.length;figs.forEach((f,k)=>f.classList.toggle('on',k===i));link.textContent=figs[i].dataset.name;link.href=figs[i].dataset.href;}
function play(){clearInterval(timer);if(!matchMedia('(prefers-reduced-motion: reduce)').matches)timer=setInterval(()=>show(i+1),4200);}
if(figs.length){document.getElementById('prev').onclick=()=>{show(i-1);play()};document.getElementById('next').onclick=()=>{show(i+1);play()};show(0);play();}
const root=document.documentElement,btn=document.getElementById('theme');
btn.onclick=()=>{const dark=root.dataset.theme?root.dataset.theme==='dark':matchMedia('(prefers-color-scheme: dark)').matches;root.dataset.theme=dark?'light':'dark';try{localStorage.setItem('hub-theme',root.dataset.theme)}catch(e){}};
try{const t=localStorage.getItem('hub-theme');if(t)root.dataset.theme=t}catch(e){}
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

    know = [
        {
            "chip": f"DECK {i:02d}",
            "title": d["name"],
            "text": d.get("line", ""),
            "num": f"{d['slides']} slides" + (f" · {d['cards']} relations named" if d["cards"] else ""),
            "href": f"{d['href']}{d['categories'][0]['slug']}.html",
        }
        for i, d in enumerate(decks, 1)
    ] + ([hub["store"]] if hub.get("store") else [])
    left = hub.get("data") or []
    rows = max(len(left), len(know), 1)
    deck_html = []
    for d in decks:
        cats = "".join(
            f'<a class="cat" href="{d["href"]}{c["slug"]}.html"><i>{c["n"]:02d}</i><span>{esc(c["title"])}</span>'
            f"<em>{c['slides']} slides</em></a>"
            for c in d["categories"]
        )
        count = f"{d['slides']} slides · {d['figures']} figures" + (
            f" · {len(d['where'])} diagrams" if d["where"] else ""
        )
        deck_html.append(
            f'<div class="deck rise" id="{d["key"]}"><span class="mono">{count}</span><h3>{esc(d["name"])}</h3>'
            f'<p>{esc(d.get("line", ""))}</p><div class="cats">{cats}</div>'
            f'<a class="go" href="{d["href"]}{d["categories"][0]["slug"]}.html">Open the deck →</a></div>'
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

    finds = "".join(
        f'<div class="card rise"><span class="grade {esc(f["grade"])}">{esc(f["grade"])}</span>'
        f'<div class="big">{esc(f["big"])}</div><p>{esc(f["text"])}</p></div>'
        for f in hub.get("findings") or []
    )
    steps = "".join(
        f'<div><span class="mono">{i:02d}</span><b>{esc(s["title"])}</b><p>{esc(s["text"])}</p></div>'
        for i, s in enumerate(hub.get("method") or [], 1)
    )
    ids = ("diagrams", "findings", "decks", "method")
    sections = [
        section(
            "diagrams",
            f"{n} diagrams · {total} slides",
            "wall",
            f'<div class="wall">{"".join(t for _, t in tiles)}</div>' if tiles else "",
        ),
        section(
            "findings",
            "Knowledge set against data",
            "found",
            f'<div class="find">{finds}</div>' if finds else "",
        ),
        section("decks", f"{len(decks)} decks", "sets", f'<div class="decks">{"".join(deck_html)}</div>'),
        section("method", "Method", "how", f'<div class="steps rise">{steps}</div>' if steps else ""),
    ]
    nav = "".join(f'<a href="#{i}">{i.capitalize()}</a>' for i, s in zip(ids, sections, strict=True) if s)
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
<div class="board"><div class="grid">{traces(len(left), len(know))}
<div class="col l"><span class="colhead" style="left:4%">{esc(hub.get("left", "MEASURED DATA"))}</span>{"".join(module(m, "d") for m in left)}</div>
<div class="col c"><div class="mod core"><span class="mono">{esc(hub.get("kicker", ""))}</span><h1>{esc(hub["headline"])}</h1>{panel}
<p class="tag">{esc(hub.get("tagline", ""))}</p>{selector}</div></div>
<div class="col r"><span class="colhead" style="left:70%">{esc(hub.get("right", "KNOWLEDGE"))}</span>{"".join(module(m, "k") for m in know)}</div>
</div></div>
{"".join(sections)}
</main><footer>{esc(hub.get("footer", ""))}</footer></div><script>{JS}</script></body></html>"""
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for d in decks:
        shutil.copytree(d["path"], out / d["key"])
        (out / d["key"] / "index.html").write_text(
            REDIRECT.format(name=esc(d["name"])), encoding="utf-8", newline="\n"
        )
    (out / "index.html").write_text(page, encoding="utf-8", newline="\n")
    return {"decks": len(decks), "diagrams": n, "slides": total}
