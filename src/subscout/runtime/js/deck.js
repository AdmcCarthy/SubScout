// Deck mode, a category page: one slide the size of the screen at a time. Reads the build payload, keeps one live
// figure per figure id, and moves it between states as the slides change.
import "./deck-shell.js";
import { onSchemeChange, units, UNITS } from "./subscout.js";

const P = JSON.parse(document.getElementById("deck-data").textContent);
const S = P.slides;
const $ = (id) => document.getElementById(id);
const slideEl = $("slide"), layersEl = $("layers"), proseEl = $("prose"), factsEl = $("facts");
const CONF = { observed: "Observed", derived: "Derived", interpreted: "Interpreted", parameter: "Parameter" };
const U = () => UNITS[units.get()];

// The built-in chart forms, as in a story page. Each returns { draw(width, state, { animate }) }.
function builtIn(C, el, F, o) {
  const spec = F.spec, data = F.payload;
  const unitLabel = () => (spec.unit_label ? spec.unit_label.replace("{unit}", U().short) : "");
  o = { ...o, unitLabel, groups: spec.groups || P.groups };
  switch (F.type) {
    case "line": return C.lineChart(el, data, { ...o, yFormat: spec.y_format, unitScaled: !!spec.volume });
    case "stack": return C.stackedBars(el, data, { ...o, colours: spec.colours, unitScaled: !!spec.volume });
    case "heat": return C.heatmap(el, data, { ...o, valueLabel: spec.value_label ?? "" });
    case "diverging": return C.divergingBars(el, data, o);
    case "bars": return C.barChart(el, data, o);
    case "dots": return C.dotStrip(el, data, o);
    case "map": return C.geoMap(el, spec, P.datasets, o);
    case "network": return C.networkChart(el, data, o);
    default: throw new Error(`no chart form '${F.type}'`);
  }
}

// ------------------------------------------------------------------ figures
const figs = new Map(); // id -> { layer, chartEl, impl, state, drawn: "w×h" }

function statesOf(id) {
  return S.filter((s) => s.fig === id).map((s) => s.state ?? {});
}

function ensure(id) {
  if (figs.has(id)) return figs.get(id);
  const F = P.figures[id];
  const layer = document.createElement("div");
  layer.className = "fig-layer";
  layer.dataset.type = F.type;
  layer.innerHTML = '<div class="ss-legend"></div><div class="ss-chart"></div>';
  layersEl.append(layer);
  const chartEl = layer.querySelector(".ss-chart"), legendEl = layer.querySelector(".ss-legend");
  const rec = { layer, chartEl, impl: null, state: {}, drawn: "", pending: null };
  const opts = {
    label: (F.title ?? "").replace(/<[^>]+>/g, ""), legendEl, spec: F.spec ?? {}, layout: F.master, states: statesOf(id), units: U,
    // the figure fills the box the slide gives it: its height as a share of the screen, read on every draw
    get vhShare() { return Math.max(chartEl.clientHeight, 200) / window.innerHeight; },
  };
  const ready = (impl) => { rec.impl = impl; if (rec.pending) { const a = rec.pending; rec.pending = null; impl.draw(...a); } };
  if (F.type === "custom") {
    const data = Object.fromEntries(F.data.map((n) => [n, P.datasets[n]]));
    import(new URL(F.module, document.baseURI).href).then((m) => ready((m.default ?? m.create)(chartEl, data, opts))).catch((e) => console.error(`figure ${F.module}:`, e));
  } else {
    import("./charts.js").then((m) => ready(builtIn(m, chartEl, F, opts))).catch((e) => console.error(`figure ${id}:`, e));
  }
  figs.set(id, rec);
  new ResizeObserver(() => { if (rec.layer.classList.contains("on")) draw(rec, false); }).observe(chartEl);
  return rec;
}

function draw(rec, animate, force = false) {
  const w = Math.round(rec.chartEl.clientWidth), h = Math.round(rec.chartEl.clientHeight);
  if (!w || !h) return;
  const key = `${w}×${h}`;
  if (!force && key === rec.drawn) return; // the resize observer after a draw at the same size
  rec.drawn = key;
  const args = [w, rec.state, { animate }];
  if (rec.impl) rec.impl.draw(...args);
  else rec.pending = args;
}

// ------------------------------------------------------------------ slides
let at = -1;

function facts(F) {
  const f = F?.facts;
  if (!f) return "";
  const src = (f.url ? `<a href="${f.url}">${f.source}</a>` : f.source ?? "") + (f.accessed ? `, ${f.accessed}` : "");
  return `<dl><div><dt>Source</dt><dd>${src}</dd></div>${f.unit ? `<div><dt>Units</dt><dd>${f.unit}</dd></div>` : ""}`
    + `<div><dt>Confidence</dt><dd><span class="ss-conf" data-level="${f.confidence}">${CONF[f.confidence] ?? f.confidence}</span></dd></div>`
    + `${f.notes ? `<div><dt>Note</dt><dd>${f.notes}</dd></div>` : ""}`
    + `${f.exception ? `<div><dt>Exception</dt><dd>${f.exception.rule}: ${f.exception.reason}</dd></div>` : ""}</dl>`;
}

// Text that does not fit its box steps down in size, to a floor; the build check lists what still overflows.
// Text set in columns spills sideways into a further column, not downwards, so both directions are tested.
const spills = () => proseEl.scrollHeight > proseEl.clientHeight + 1 || proseEl.scrollWidth > proseEl.clientWidth + 1;
function fit() {
  proseEl.style.removeProperty("--fs");
  let fs = 1;
  while (spills() && fs > 0.8) {
    fs -= 0.04;
    proseEl.style.setProperty("--fs", fs.toFixed(2));
  }
  slideEl.dataset.overflow = spills() ? "1" : "0";
}

function go(n, { animate = true } = {}) {
  n = Math.max(0, Math.min(S.length - 1, n));
  const s = S[n], before = S[at];
  const F = s.fig ? P.figures[s.fig] : null;
  const chart = F && F.kind === "chart";
  const layout = s.kind === "cover" ? "cover" : !chart ? "text" : F.master;
  slideEl.dataset.layout = layout;
  slideEl.dataset.kind = s.kind;
  $("kicker").textContent = [P.num, P.title, P.multi && s.kind !== "cover" ? s.section : null].filter(Boolean).join(" · ");
  $("title").innerHTML = s.topic ?? s.title ?? s.section;
  $("fig-title").innerHTML = (s.topic && s.title) || "";
  $("fig-sub").innerHTML = s.subtitle ?? "";
  proseEl.innerHTML = s.kind === "table" ? `${s.html}<div class="table-slide">${F.html}</div>` : s.html;
  proseEl.scrollTop = 0;
  if (s.kind === "table") {
    // nothing on a slide unfolds: a folded table shows its first rows and says how many there are
    const more = proseEl.querySelector(".ss-fold");
    if (more) more.outerHTML = `<p class="table-more">The first ${more.dataset.fold} of ${proseEl.querySelectorAll("tbody tr").length} rows.</p>`;
    // the slide's heading is the table's title when no topic is given; the caption would repeat it
    proseEl.querySelector("caption")?.toggleAttribute("hidden", !s.topic);
  }
  factsEl.innerHTML = facts(F);
  $("facts-btn").hidden = !F;
  if (!F) showFacts(false);

  figs.forEach((r, id) => r.layer.classList.toggle("on", chart && id === s.fig));
  if (chart) {
    const rec = ensure(s.fig);
    rec.layer.classList.add("on");
    rec.state = s.state ?? {};
    // geometry is read after the new text is in place, so one draw lands on the final size
    draw(rec, animate && before?.fig === s.fig, true);
  }
  fit();

  $("count").textContent = `${n + 1} / ${S.length}`;
  document.querySelectorAll("#ticks button").forEach((b, i) => { b.setAttribute("aria-selected", i === n); b.classList.toggle("done", i < n); });
  $("prev").disabled = n === 0 && !P.prev;
  const next = $("next");
  if (n === S.length - 1) {
    next.innerHTML = P.next ? `Next: ${P.next.title} <span aria-hidden="true">→</span>` : "Back to the overview";
    next.href = P.next ? `${P.next.slug}.html` : "index.html";
    next.dataset.leave = "1";
  } else {
    next.innerHTML = n === 0 ? 'Start <span aria-hidden="true">→</span>' : 'Next <span aria-hidden="true">→</span>';
    next.href = `#${n + 2}`;
    delete next.dataset.leave;
  }
  at = n;
  if (location.hash !== `#${n + 1}`) history.replaceState(null, "", `#${n + 1}`);
  // have the next slide's figure loaded before it is asked for
  const ahead = S[n + 1];
  if (ahead?.fig && P.figures[ahead.fig].kind === "chart") ensure(ahead.fig);
}

function showFacts(on) {
  factsEl.hidden = !on;
  $("facts-btn").setAttribute("aria-expanded", on);
}

// ticks: one per slide, grouped by topic
{
  let last;
  const ticks = $("ticks");
  S.forEach((s, i) => {
    const key = s.kind === "cover" ? "cover" : `${s.section}|${s.topic ?? s.title ?? ""}`;
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.title = `${i + 1}. ${(s.kind === "cover" ? "Contents" : s.topic ?? s.title ?? s.section).replace(/<[^>]+>/g, "")}`;
    if (i && key !== last) b.classList.add("gap");
    last = key;
    b.addEventListener("click", () => go(i, { animate: Math.abs(i - at) === 1 }));
    ticks.append(b);
  });
}

const fromHash = () => {
  if (location.hash === "#last") return S.length - 1;
  const n = parseInt(location.hash.slice(1), 10);
  return Number.isFinite(n) ? n - 1 : 0;
};
const step = (d) => {
  const n = at + d;
  if (n < 0) { if (P.prev) location.href = `${P.prev.slug}.html#last`; return; }
  if (n >= S.length) { location.href = $("next").href; return; }
  go(n);
};
$("prev").addEventListener("click", () => step(-1));
$("next").addEventListener("click", (e) => { if (!e.currentTarget.dataset.leave) { e.preventDefault(); step(1); } });
$("facts-btn").addEventListener("click", () => showFacts(factsEl.hidden));
window.addEventListener("hashchange", () => { const n = fromHash(); if (n !== at) go(n, { animate: Math.abs(n - at) === 1 }); });
window.addEventListener("resize", () => fit());
onSchemeChange(() => figs.forEach((r) => r.layer.classList.contains("on") && draw(r, false, true)));

// category links and the contents overlay
const catPrev = $("cat-prev"), catNext = $("cat-next"), contents = $("contents");
if (P.prev) { catPrev.href = `${P.prev.slug}.html`; catPrev.title = P.prev.title; } else catPrev.setAttribute("aria-disabled", "true");
if (P.next) { catNext.href = `${P.next.slug}.html`; catNext.title = P.next.title; } else catNext.setAttribute("aria-disabled", "true");
const showContents = (on) => { contents.hidden = !on; };
$("contents-btn").addEventListener("click", () => showContents(contents.hidden));
$("contents-close").addEventListener("click", () => showContents(false));
contents.addEventListener("click", (e) => { if (e.target === contents) showContents(false); });

window.addEventListener("keydown", (e) => {
  if (e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === "Escape") { showContents(false); showFacts(false); return; }
  if (!contents.hidden) return;
  if (["ArrowRight", "PageDown", " "].includes(e.key)) { e.preventDefault(); step(1); }
  else if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); step(-1); }
  else if (e.key === "Home") go(0, { animate: false });
  else if (e.key === "End") go(S.length - 1, { animate: false });
  else if (e.key === "i") showFacts(factsEl.hidden);
});

// first paint once the fonts have settled the text, so the figure is drawn at its final size
(document.fonts?.ready ?? Promise.resolve()).then(() => go(fromHash(), { animate: false }));
