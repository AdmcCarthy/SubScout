// Export page runtime: draws one figure on a fixed artboard (size, state, theme, units from the URL or
// the toolbar), signals readiness for the renderer, and links the pre-rendered high-resolution PNGs.
import { theme, units, UNITS, bindSeg, refreshUnits, onSchemeChange } from "./subscout.js";
import { lineChart, stackedBars, bubbles, heatmap, divergingBars, barChart, dotStrip, geoMap, networkChart } from "./charts.js";

const P = JSON.parse(document.getElementById("ss-payload").textContent);
const q = new URLSearchParams(location.search);
const bare = q.has("bare");
document.body.classList.toggle("is-bare", bare);
const sizes = Object.keys(P.sizes);
let size = sizes.includes(q.get("size")) ? q.get("size") : sizes[0];
let si = Math.min(P.states.length - 1, Math.max(0, +(q.get("state") ?? P.states.length - 1)));  // default: the final, fullest view
if (q.get("theme")) theme.set(q.get("theme"));
else if (theme.get() === "system") theme.set(matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
if (q.get("units")) units.set(q.get("units"));
else if (P.units && !localStorage.getItem?.call(localStorage, "ss:units")) units.set(P.units);
refreshUnits();

const board = document.getElementById("board");
const el = document.getElementById("ex-chart");
const legendEl = board.querySelector(".ex-legend");
const spec = P.fig.spec;
const U = () => UNITS[units.get()];
const height = () => el.clientHeight;
const o = { label: spec.title?.replace(/<[^>]+>/g, "") ?? "", legendEl, spec, groups: spec.groups || P.groups,
  unitLabel: () => (spec.unit_label ? spec.unit_label.replace("{unit}", U().short) : ""), height, export: true };

async function makeChart() {
  const data = P.fig.data;
  switch (spec.type) {
    case "line": return lineChart(el, data, { ...o, yFormat: spec.y_format, unitScaled: !!spec.volume });
    case "stack": return stackedBars(el, data, { ...o, colours: spec.colours, unitScaled: !!spec.volume });
    case "bubble": return bubbles(el, data, spec.groups || [], o);
    case "heat": return heatmap(el, data, { ...o, valueLabel: spec.value_label ?? "" });
    case "diverging": return divergingBars(el, data, o);
    case "bars": return barChart(el, data, o);
    case "dots": return dotStrip(el, data, o);
    case "map": return geoMap(el, spec, P.datasets, o);
    case "network": return networkChart(el, data, o);
    case "custom": {
      const names = [].concat(spec.data ?? []);
      const ds = Object.fromEntries(names.map((n) => [n, P.datasets[n]]));
      const m = await import(new URL(`../../${spec.module}`, location.href).href);
      return (m.default ?? m.create)(el, ds, { ...o, units: U, states: P.states.map((s) => s.state) });
    }
    default: return null;
  }
}

function fit() {
  const { w, h } = P.sizes[size];
  board.style.width = `${w}px`;
  board.style.height = `${h}px`;
  if (bare) { board.style.transform = ""; return; }
  const avail = document.querySelector(".ex-stage").clientWidth - 48;  // preview scales down to fit, never up
  const k = Math.min(1, avail / w);
  board.style.transform = k < 1 ? `scale(${k})` : "";
  board.parentElement.style.height = `${h * k + 48}px`;
}

let chart = null;
async function draw() {
  fit();
  document.body.dataset.ready = "0";
  const st = P.states[si];
  const t = st.state.title;
  if (t) document.getElementById("ex-title").innerHTML = t;
  if (!chart) chart = await makeChart();
  chart?.draw(el.clientWidth, st.state, { animate: false });
  await document.fonts.ready;
  requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(() => (document.body.dataset.ready = "1"), 150)));
  links();
}

// toolbar
const sizeSel = document.getElementById("t-size"), stateSel = document.getElementById("t-state");
sizeSel.innerHTML = sizes.map((k) => `<option value="${k}">${P.sizes[k].label} · ${P.sizes[k].w * P.scale} × ${P.sizes[k].h * P.scale}</option>`).join("");
stateSel.innerHTML = P.states.map((s, i) => `<option value="${i}">${s.name}</option>`).join("");
sizeSel.value = size; stateSel.value = String(si);
if (P.states.length < 2) stateSel.parentElement.hidden = true;
sizeSel.onchange = () => { size = sizeSel.value; chart = null; el.innerHTML = ""; draw(); };
stateSel.onchange = () => { si = +stateSel.value; draw(); };
bindSeg(document.getElementById("t-theme"), theme);
bindSeg(document.getElementById("t-units"), units);
units.subscribe(() => { refreshUnits(); chart?.repaint ? chart.repaint() : draw(); });
onSchemeChange(() => (chart?.repaint ? chart.repaint() : draw()));
addEventListener("resize", () => fit());

let renders = null;
fetch("renders.json").then((r) => (r.ok ? r.json() : [])).then((r) => { renders = r; links(); }).catch(() => { renders = []; links(); });
function links() {
  const dl = document.getElementById("t-dl");
  if (!dl || renders === null) return;
  const th = document.documentElement.getAttribute("data-colour-scheme") || "light";
  if (units.get() !== (P.units || "sm3")) { dl.innerHTML = `<span>PNG files use ${UNITS[P.units || "sm3"].label}; switch units back to download</span>`; return; }
  const r = renders.find((x) => x.size === size && x.theme === th && x.state === si);
  dl.innerHTML = r ? `<span>${r.px[0]} × ${r.px[1]} px</span><a href="${r.file}" download>Download PNG</a>`
    : `<span>High-resolution PNGs are rendered with <code>subscout export</code></span>`;
}
theme.subscribe(() => setTimeout(links, 0));
draw();
