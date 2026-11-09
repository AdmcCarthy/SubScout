// SubScout story page runtime: reads the build payload, creates charts, wires Read/Present.
import { theme, units, UNITS, bindSeg, story, refreshUnits, onSchemeChange, idle, isShown } from "./subscout.js";
import { lineChart, stackedBars, bubbles, heatmap, divergingBars, barChart, dotStrip, geoMap, horizon, networkChart } from "./charts.js";

const payload = JSON.parse(document.getElementById("ss-payload").textContent);
const U = () => UNITS[units.get()];
if (!localStorage.getItem?.call(localStorage, "ss:units") && payload.units) units.set(payload.units);
bindSeg(document.getElementById("ctl-theme"), theme);
bindSeg(document.getElementById("ctl-units"), units);
refreshUnits();

// ---------------------------------------------------------------- hero horizon
// `horizon: true` draws the procedural motif; `horizon: {data: name}` fetches the story's
// header export after first paint (its height is reserved by the template) and draws
// the real section with its surfaces (horizon-band.js).
const hz = document.getElementById("ss-hero-horizon");
if (hz && hz.dataset.header) {
  (async () => {
    const [{ horizonBand }, r] = await Promise.all([
      import("./horizon-band.js"),
      fetch(new URL(`data/${hz.dataset.header}.json`, document.baseURI)),
    ]);
    if (!r.ok) throw new Error(`header data ${r.status}`);
    const P = await r.json();
    const band = horizonBand(hz, P, {
      height: hz.clientHeight || 150,
      highlight: hz.dataset.highlight || P.highlight,
      caption: hz.dataset.label !== "0",
    });
    let w = 0, queued = false;
    new ResizeObserver(([e]) => {
      const nw = Math.round(e.contentRect.width);
      if (!nw || nw === w || queued) return;
      queued = true;
      requestAnimationFrame(() => { queued = false; band.draw((w = Math.round(hz.clientWidth))); });
    }).observe(hz);
    onSchemeChange(() => band.repaint());
  })().catch((e) => console.error("horizon band:", e));
} else if (hz) {
  const h = horizon(hz, { seed: 7, height: 100, label: "Horizon motif" });
  let w = 0;
  new ResizeObserver(([e]) => { const nw = Math.round(e.contentRect.width); if (nw && nw !== w) h.draw((w = nw)); }).observe(hz);
}

// ---------------------------------------------------------------- charts
const unitLabel = (spec) => () => (spec.unit_label ? spec.unit_label.replace("{unit}", U().short) : "");
function make(figEl, fig) {
  const { spec, data } = fig;
  const el = figEl.querySelector(".ss-chart");
  const legendEl = figEl.querySelector(".ss-legend");
  const o = { label: spec.title?.replace(/<[^>]+>/g, "") ?? "", legendEl, unitLabel: unitLabel(spec), spec, groups: spec.groups || payload.groups };
  switch (spec.type) {
    case "line": return lineChart(el, data, { ...o, yFormat: spec.y_format, unitScaled: !!spec.volume });
    case "stack": return stackedBars(el, data, { ...o, colours: spec.colours, unitScaled: !!spec.volume });
    case "bubble": return bubbles(el, data, spec.groups || [], o);
    case "heat": return heatmap(el, data, { ...o, valueLabel: spec.value_label ?? "" });
    case "diverging": return divergingBars(el, data, o);
    case "bars": return barChart(el, data, o);
    case "dots": return dotStrip(el, data, o);
    case "map": return geoMap(el, spec, payload.datasets, o);
    case "network": return networkChart(el, data, o);
    case "custom": return customChart(el, fig, o, figEl.dataset.fig);
    default: return null;
  }
}

// A story-supplied figure: `module` exports default (el, datasets, opts) => { draw(width, state, {animate}), repaint?() }.
// Loaded on demand; calls made before it arrives are replayed.
function customChart(el, fig, o, id) {
  let impl = null, last = null;
  // every state this figure will show (its own, then each `use:` step), so it can prepare ahead
  const states = [fig.spec.state ?? {}, ...Object.values(payload.figures).filter((f) => f.use === id).map((f) => ({ ...(fig.spec.state ?? {}), ...f.state }))];
  const names = [].concat(fig.spec.data ?? []);
  const data = Object.fromEntries(names.map((n) => [n, payload.datasets[n]]));
  import(new URL(fig.spec.module, document.baseURI).href)
    .then((m) => { impl = (m.default ?? m.create)(el, data, { ...o, units: U, states }); if (last) impl.draw(...last); })
    .catch((e) => console.error(`custom figure ${fig.spec.module}:`, e));
  return {
    draw: (...a) => { last = a; if (impl) impl.draw(...a); },
    repaint: () => { if (impl?.repaint) impl.repaint(); else if (impl && last) impl.draw(last[0], last[1], { animate: false }); },
  };
}

const charts = new Map(); // fig id -> {chart, el, width, state}
const initialState = (spec) => {
  if (spec.type === "custom") return { ...(spec.state ?? {}) };
  const keys = ["focus", "note", "highlight", "sort", "view", "filter", "frame"];
  return Object.fromEntries(keys.filter((k) => spec[k] !== undefined).map((k) => [k, spec[k]]));
};
document.querySelectorAll(".ss-figure[data-fig]").forEach((figEl) => {
  const id = figEl.dataset.fig;
  const fig = payload.figures[id];
  if (!fig?.spec) return; // tables are server-rendered
  const chart = make(figEl, fig);
  if (!chart) return;
  const rec = { chart, el: figEl.querySelector(".ss-chart"), width: 0, state: initialState(fig.spec), figEl };
  charts.set(id, rec);
  let pending = false;
  new ResizeObserver(([e]) => {
    const nw = Math.round(e.contentRect.width);
    if (!nw || nw === rec.width) return;
    rec.width = nw;
    // visible charts redraw on the next frame; hidden layers wait for idle time
    if (pending) return;
    pending = true;
    const go = () => { pending = false; chart.draw(rec.width, rec.state, { animate: false }); };
    isShown(rec.el) || !rec.drawn ? requestAnimationFrame(go) : idle(go);
    rec.drawn = true;
  }).observe(rec.el);
});
// maps: pre-render each camera view used by later steps, in idle time
charts.forEach((rec, id) => {
  if (!rec.chart.prepare) return;
  const views = [payload.figures[id].spec.view, ...Object.values(payload.figures).filter((f) => f.use === id).map((f) => f.state.view)];
  const once = () => (rec.width ? rec.chart.prepare(views) : setTimeout(once, 200));
  once();
});
const redrawAll = () => charts.forEach((r) => r.width && (r.chart.repaint ? r.chart.repaint() : r.chart.draw(r.width, r.state, { animate: false })));
units.subscribe(redrawAll);
onSchemeChange(() => charts.forEach((r, id) => {
  if (!r.chart.repaint) return;
  r.chart.repaint();
  if (r.chart.prepare) r.chart.prepare(Object.values(payload.figures).filter((f) => f.use === id).map((f) => f.state.view));
}));

// ---------------------------------------------------------------- scrolly groups
document.querySelectorAll(".ss-story").forEach((storyEl) => {
  const stepEls = [...storyEl.querySelectorAll(".ss-step")];
  const layers = [...storyEl.querySelectorAll(".ss-layer")];
  // resolve each step to (base figure id, state)
  const plan = stepEls.map((s) => {
    const figs = payload.steps[+s.dataset.step]?.figs ?? [];
    const last = figs.at(-1);
    if (!last) return null;
    const f = payload.figures[last];
    if (f?.use) return { id: f.use, state: f.state };
    return { id: last, state: f?.spec ? initialState(f.spec) : {} };
  });
  for (let i = 1; i < plan.length; i++) if (!plan[i]) plan[i] = plan[i - 1];
  function render(i, { animate }) {
    const p = plan[i];
    if (!p) return;
    layers.forEach((l) => l.classList.toggle("is-on", l.dataset.fig === p.id));
    const rec = charts.get(p.id);
    const base = payload.figures[p.id]?.spec ?? {};
    if (rec) {
      rec.state = { ...initialState(base), ...p.state };
      if (p.state.title) rec.figEl.querySelector(".ss-fig-title").innerHTML = p.state.title;
      else rec.figEl.querySelector(".ss-fig-title").innerHTML = base.title ?? "";
      const sub = rec.figEl.querySelector(".ss-fig-sub");
      if (sub) sub.innerHTML = p.state.subtitle ?? base.subtitle ?? "";
      if (rec.width) rec.chart.draw(rec.width, rec.state, { animate });
    }
  }
  const engine = story(storyEl, { render });
  document.getElementById("present-btn")?.addEventListener("click", () => engine.setMode("present"));
});

// ---------------------------------------------------------------- tables: sort and fold
document.querySelectorAll(".ss-table").forEach((t) => {
  t.parentElement.querySelector(".ss-fold")?.addEventListener("click", (e) => {
    const open = t.classList.toggle("is-unfolded");
    e.target.textContent = open ? "Show fewer" : `Show all ${t.tBodies[0].rows.length}`;
  });
  t.querySelectorAll("th[data-field]").forEach((th, ci) => th.addEventListener("click", () => {
    const desc = th.getAttribute("aria-sort") !== "descending";
    t.querySelectorAll("th").forEach((h) => h.setAttribute("aria-sort", "none"));
    th.setAttribute("aria-sort", desc ? "descending" : "ascending");
    const rows = [...t.tBodies[0].rows];
    const val = (r) => { const s = r.cells[ci].dataset.v; const n = parseFloat(s); return isNaN(n) ? s : n; };
    rows.sort((a, b) => { const x = val(a), y = val(b); return (x > y ? 1 : x < y ? -1 : 0) * (desc ? -1 : 1); });
    const fold = +(t.parentElement.querySelector(".ss-fold")?.dataset.fold || 0);
    rows.forEach((r, i) => { r.classList.toggle("is-folded", !!fold && i >= fold); t.tBodies[0].append(r); });
  }));
});
