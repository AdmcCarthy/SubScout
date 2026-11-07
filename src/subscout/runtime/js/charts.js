// SubScout chart components (d3 v7, global `d3`). Each returns { draw(width, state, {animate}) }.
// Colours are CSS variables, so charts follow theme and data-palette changes without redrawing.
// Rules baked in: one y-axis, bars from zero, recessive grid, direct labels, keyed joins
// (object constancy), staged transitions, hover tooltips, colour follows the entity.

import { motion, fmt, tooltip, UNITS, units } from "./subscout.js";

const v = (name) => `var(--ss-${name})`;
let tip;
const getTip = () => (tip ??= tooltip());

function frame(el, W, H, label) {
  return d3.select(el).selectAll("svg").data([0]).join("svg")
    .attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", label);
}
const T = (sel, animate, delay = 0, dur) => {
  const mo = motion();
  return sel.transition().delay(animate ? delay : 0).duration(animate ? (dur ?? mo.base) : 0).ease(d3.easeCubicInOut);
};
function yAxis(svg, y, m, W, animate, format = d3.format(",")) {
  T(svg.selectAll("g.ss-grid").data([0]).join("g").attr("class", "ss-grid").attr("transform", `translate(${m.l},0)`), animate)
    .call(d3.axisLeft(y).ticks(5).tickSize(-(W - m.l - m.r)).tickFormat(""));
  T(svg.selectAll("g.ss-y").data([0]).join("g").attr("class", "ss-axis ss-y").attr("transform", `translate(${m.l},0)`), animate)
    .call(d3.axisLeft(y).ticks(5).tickSize(0).tickPadding(6).tickFormat(format));
}
const catCount = (el) => parseInt(getComputedStyle(el).getPropertyValue("--ss-data-cat-count")) || 5;
const unitF = () => UNITS[units.get()].factor;

/** Rounded data-end bar path (r at the value end, square at the baseline). */
function vbar(x0, w, y0, y1, r = 4) {
  if (y0 - y1 < r) return `M${x0},${y0}V${y1}H${x0 + w}V${y0}Z`;
  return `M${x0},${y0}V${y1 + r}Q${x0},${y1} ${x0 + r},${y1}H${x0 + w - r}Q${x0 + w},${y1} ${x0 + w},${y1 + r}V${y0}Z`;
}
function hbar(x0, x1, y, h, r = 4) {
  const left = x1 < x0;
  const [a, b] = left ? [x1, x0] : [x0, x1];
  if (b - a < r) return `M${a},${y}H${b}V${y + h}H${a}Z`;
  return left
    ? `M${b},${y}H${a + r}Q${a},${y} ${a},${y + r}V${y + h - r}Q${a},${y + h} ${a + r},${y + h}H${b}Z`
    : `M${a},${y}H${b - r}Q${b},${y} ${b},${y + r}V${y + h - r}Q${b},${y + h} ${b - r},${y + h}H${a}Z`;
}

// ------------------------------------------------------------------ line
/** data: {x: number[], series: [{name, vals}]}, state: {focus: [name], note?: {name, x, text}} */
export function lineChart(el, data, { label = "Line chart", unitLabel = () => "", yFormat = null, unitScaled = true } = {}) {
  const yf = yFormat === "pct" ? (d) => `${fmt(d * (Math.abs(d) <= 1 ? 100 : 1))}%` : d3.format(",");
  function draw(W, state = {}, { animate = false } = {}) {
    const f = unitScaled ? unitF() : 1;
    const focus = state.focus ?? [];
    const H = Math.round(Math.max(220, Math.min(360, W * 0.6)));
    const m = { t: 30, r: W < 420 ? 58 : 70, b: 24, l: 34 };
    const x = d3.scaleLinear(d3.extent(data.x), [m.l, W - m.r]);
    const y = d3.scaleLinear([0, d3.max(data.series, (d) => d3.max(d.vals)) * f], [H - m.b, m.t]).nice();
    const svg = frame(el, W, H, label);
    yAxis(svg, y, m, W, animate, yf);
    svg.selectAll("g.ss-x").data([0]).join("g").attr("class", "ss-axis ss-x").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(W < 420 ? 4 : 6).tickFormat(d3.format("d")).tickSizeOuter(0));
    const line = d3.line().defined((d) => d > 0).x((_, i) => x(data.x[i])).y((d) => y(d * f)).curve(d3.curveMonotoneX);
    const rank = (d) => focus.indexOf(d.name);
    const ordered = [...data.series].sort((a, b) => rank(a) - rank(b));
    const paths = svg.selectAll("path.series").data(ordered, (d) => d.name).join("path").attr("class", "series")
      .attr("fill", "none").attr("stroke-linejoin", "round").attr("stroke-linecap", "round").attr("d", (d) => line(d.vals));
    paths.order();
    T(paths, animate).style("stroke", (d) => (rank(d) >= 0 ? v(`data-story-${rank(d) + 1}`) : v("data-context")))
      .attr("stroke-width", (d) => (rank(d) >= 0 ? 2.5 : 1.25));
    // direct labels for focus series, de-overlapped vertically
    const labs = focus.map((n) => data.series.find((d) => d.name === n)).filter(Boolean)
      .map((d) => ({ name: d.name, y: y(d.vals.at(-1) * f) + 4 }));
    labs.sort((a, b) => a.y - b.y).forEach((d, i, a) => { if (i && d.y - a[i - 1].y < 14) d.y = a[i - 1].y + 14; });
    const lt = svg.selectAll("text.flab").data(labs, (d) => d.name);
    lt.exit().remove();
    T(lt.enter().append("text").attr("class", "flab ss-label ss-halo").style("opacity", 0).merge(lt)
      .attr("x", W - m.r + 6).text((d) => d.name), animate, animate ? motion().base : 0)
      .style("opacity", 1).attr("y", (d) => d.y);
    svg.selectAll("text.others").data([0]).join("text").attr("class", "others ss-note ss-halo")
      .attr("x", W - m.r + 6).attr("y", H - m.b - 8).text(focus.length && focus.length < data.series.length ? "Others" : "");
    // note: highlight marker + text
    const n = state.note && data.series.find((d) => d.name === state.note.name);
    const nd = n ? [{ ...state.note, cx: x(state.note.x), cy: y(n.vals[data.x.indexOf(state.note.x)] * f) }] : [];
    const g = svg.selectAll("g.note").data(nd, (d) => d.text);
    g.exit().remove();
    const ge = g.enter().append("g").attr("class", "note").style("opacity", 0);
    ge.append("circle").attr("r", 5).style("fill", v("data-highlight")).style("stroke", v("surface")).attr("stroke-width", 2);
    ge.append("text").attr("class", "ss-label ss-halo").attr("text-anchor", "middle").attr("y", -12);
    const gm = ge.merge(g).attr("transform", (d) => `translate(${d.cx},${d.cy})`);
    gm.select("text").text((d) => d.text);
    T(gm, animate, animate ? motion().base * 1.3 : 0).style("opacity", 1);
    // hover
    const cross = svg.selectAll("line.cross").data([0]).join("line").attr("class", "cross")
      .attr("y1", m.t).attr("y2", H - m.b).style("stroke", v("border-strong")).attr("stroke-dasharray", "3 3").attr("opacity", 0);
    svg.selectAll("rect.hit").data([0]).join("rect").attr("class", "hit").attr("fill", "transparent")
      .attr("x", m.l).attr("y", m.t).attr("width", W - m.l - m.r).attr("height", H - m.t - m.b)
      .on("pointermove", (e) => {
        const xv = Math.round(x.invert(d3.pointer(e)[0]));
        const i = data.x.indexOf(xv);
        if (i < 0) return;
        cross.attr("x1", x(xv)).attr("x2", x(xv)).attr("opacity", 1);
        const rows = [...data.series].sort((a, b) => b.vals[i] - a.vals[i]).map((d) =>
          `<tr><td>${focus.includes(d.name) ? `<b>${d.name}</b>` : d.name}</td><td class="ss-num" style="text-align:right;padding-left:12px">${d.vals[i] ? (yFormat === "pct" ? yf(d.vals[i]) : fmt(d.vals[i] * f, 1)) : "–"}</td></tr>`).join("");
        getTip().show(`<b>${xv}</b> <span class="ss-k">${unitLabel()}</span><table>${rows}</table>`, e.clientX, e.clientY);
      })
      .on("pointerleave", () => { cross.attr("opacity", 0); getTip().hide(); });
  }
  return { draw };
}

// ------------------------------------------------------------------ stacked bars
/** data: {x: [label], series: [{name, vals}]} ordered largest first; overflow folds into "Other". */
export function stackedBars(el, data, { label = "Stacked bar chart", legendEl = null, unitLabel = () => "", colours = null, unitScaled = true } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const f = unitScaled ? unitF() : 1;
    const n = colours ? colours.length : catCount(el);
    const keep = data.series.slice(0, n);
    const rest = data.series.slice(n);
    const series = rest.length
      ? [...keep, { name: `Other (${rest.length})`, other: true, vals: data.x.map((_, i) => d3.sum(rest, (s) => s.vals[i])) }]
      : keep;
    const col = (s, i) => (s.other ? v("data-context") : colours ? v(colours[i]) : v(`data-cat-${i + 1}`));
    if (legendEl) legendEl.innerHTML = series.map((s, i) => `<span><i style="background:${col(s, i)}"></i>${s.name}</span>`).join("");
    const H = Math.round(Math.max(220, Math.min(340, W * 0.58)));
    const m = { t: 10, r: 6, b: 24, l: 38 };
    const x = d3.scaleBand(data.x, [m.l, W - m.r]).padding(data.x.length > 16 ? 0.15 : 0.25);
    const totals = data.x.map((_, i) => d3.sum(series, (s) => s.vals[i]) * f);
    const y = d3.scaleLinear([0, d3.max(totals)], [H - m.b, m.t]).nice();
    const svg = frame(el, W, H, label);
    yAxis(svg, y, m, W, animate);
    svg.selectAll("g.ss-x").data([0]).join("g").attr("class", "ss-axis ss-x").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickValues(data.x.filter((_, i) => i % Math.max(1, Math.ceil(data.x.length / (W < 420 ? 5 : 11))) === 0)));
    const segs = [];
    data.x.forEach((xl, i) => {
      let acc = 0;
      series.forEach((s, k) => {
        const val = s.vals[i] * f;
        segs.push({ key: `${s.name}|${xl}`, s, k, xl, y0: acc, y1: acc + val, val, top: k === series.length - 1 });
        acc += val;
      });
    });
    const mo = motion();
    const p = svg.selectAll("path.seg").data(segs, (d) => d.key).join("path").attr("class", "seg")
      .on("pointermove", (e, d) => getTip().show(`<b>${d.s.name}</b> · ${d.xl}<br>${fmt(d.val, 1)} <span class="ss-k">${unitLabel()}</span>`, e.clientX, e.clientY))
      .on("pointerleave", () => getTip().hide());
    p.style("fill", (d) => col(d.s, d.k));
    T(p, animate, 0, mo.base).delay((d) => (animate ? d.k * mo.stagger * 2 : 0))
      .attr("d", (d) => {
        // 2px surface gap between stacked segments; rounded end only on the top segment
        const yb = y(d.y0) - (d.k ? 1 : 0), yt = y(d.y1) + (d.top ? 0 : 1);
        return d.top ? vbar(x(d.xl), x.bandwidth(), yb, Math.min(yt, yb)) : `M${x(d.xl)},${yb}V${Math.min(yt, yb)}H${x(d.xl) + x.bandwidth()}V${yb}Z`;
      });
  }
  return { draw };
}

// ------------------------------------------------------------------ bubble timeline
/** data: [{name, year, size, group}], groups: [name] in categorical order. state: {highlight: [name]} */
export function bubbles(el, data, groups, { label = "Bubble timeline", legendEl = null, unitLabel = () => "" } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const f = unitF();
    const n = catCount(el);
    const col = (g) => { const i = groups.indexOf(g); return i < n ? v(`data-cat-${i + 1}`) : v("data-context"); };
    if (legendEl) legendEl.innerHTML = groups.map((g) => `<span><i style="background:${col(g)};border-radius:50%"></i>${g}</span>`).join("");
    const H = Math.round(Math.max(240, Math.min(360, W * 0.6)));
    const m = { t: 16, r: 12, b: 24, l: 96 };
    const yb = d3.scaleBand(groups, [m.t, H - m.b]).padding(0.1);
    const rMax = Math.min(26, yb.bandwidth() / 2.2);
    const r = d3.scaleSqrt([0, d3.max(data, (d) => d.size)], [0, rMax]);
    const x = d3.scaleLinear(d3.extent(data, (d) => d.year), [m.l + rMax + 6, W - m.r - rMax / 2]).nice();
    const svg = frame(el, W, H, label);
    svg.selectAll("g.ss-x").data([0]).join("g").attr("class", "ss-axis ss-x").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(W < 420 ? 4 : 7).tickFormat(d3.format("d")).tickSizeOuter(0));
    svg.selectAll("line.lane").data(groups).join("line").attr("class", "lane")
      .attr("x1", m.l).attr("x2", W - m.r).attr("y1", (g) => yb(g) + yb.bandwidth() / 2).attr("y2", (g) => yb(g) + yb.bandwidth() / 2)
      .style("stroke", v("grid"));
    svg.selectAll("text.lane").data(groups).join("text").attr("class", "lane ss-label")
      .attr("x", m.l - 10).attr("y", (g) => yb(g) + yb.bandwidth() / 2 + 4).attr("text-anchor", "end").text((g) => g);
    const hl = new Set(state.highlight ?? []);
    const dim = hl.size > 0;
    const sorted = [...data].sort((a, b) => b.size - a.size);
    const c = svg.selectAll("circle.b").data(sorted, (d) => d.name).join("circle").attr("class", "b")
      .attr("cx", (d) => x(d.year)).attr("cy", (d) => yb(d.group) + yb.bandwidth() / 2 + d.jit * yb.bandwidth() * 0.18)
      .style("stroke", v("surface")).attr("stroke-width", 1.5)
      .on("pointermove", (e, d) => getTip().show(`<b>${d.name}</b> · ${d.group}<br>Discovered ${d.year}<br>${fmt(d.size * f)} <span class="ss-k">${unitLabel()}</span>`, e.clientX, e.clientY))
      .on("pointerleave", () => getTip().hide());
    T(c, animate).attr("r", (d) => r(d.size)).style("fill", (d) => (dim && !hl.has(d.name) ? v("data-context") : col(d.group)))
      .style("fill-opacity", (d) => (dim && !hl.has(d.name) ? 0.45 : 0.85));
    const labs = data.filter((d) => hl.has(d.name));
    const t = svg.selectAll("text.blab").data(labs, (d) => d.name);
    t.exit().remove();
    T(t.enter().append("text").attr("class", "blab ss-label ss-halo").attr("text-anchor", "middle").style("opacity", 0).merge(t)
      .attr("x", (d) => x(d.year)).attr("y", (d) => yb(d.group) + yb.bandwidth() / 2 + d.jit * yb.bandwidth() * 0.18 - r(d.size) - 6)
      .text((d) => d.name), animate, animate ? motion().base : 0).style("opacity", 1);
  }
  return { draw };
}

// ------------------------------------------------------------------ heatmap (sequential)
/** data: {cols: [label], rows: [label], vals: number[row][col]} */
export function heatmap(el, data, { label = "Heatmap", legendEl = null, valueLabel = "" } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const m = { t: 6, r: 6, b: 24, l: 34 };
    const cw = (W - m.l - m.r) / data.cols.length;
    const ch = Math.max(14, Math.min(34, cw * 1.6));
    const H = Math.round(m.t + m.b + ch * data.rows.length);
    const max = d3.max(data.vals.flat());
    const q = d3.scaleQuantize([0, max], d3.range(1, 8));
    if (legendEl) {
      const th = q.thresholds();
      legendEl.innerHTML = `<span style="gap:2px">${d3.range(1, 8).map((i) => `<i style="background:${v(`data-seq-${i}`)};border-radius:0;width:22px"></i>`).join("")}</span><span>0 → ${fmt(max)} ${valueLabel}${th.length ? "" : ""}</span>`;
    }
    const svg = frame(el, W, H, label);
    const cells = data.rows.flatMap((r, ri) => data.cols.map((c, ci) => ({ key: `${r}|${c}`, r, c, ri, ci, val: data.vals[ri][ci] })));
    const mo = motion();
    const rect = svg.selectAll("rect.cell").data(cells, (d) => d.key).join("rect").attr("class", "cell")
      .attr("x", (d) => m.l + d.ci * cw + 1).attr("y", (d) => m.t + d.ri * ch + 1).attr("width", cw - 2).attr("height", ch - 2).attr("rx", 2)
      .on("pointermove", (e, d) => getTip().show(`<b>${d.c} ${d.r}</b><br>${fmt(d.val)} ${valueLabel}`, e.clientX, e.clientY))
      .on("pointerleave", () => getTip().hide());
    T(rect, animate, 0, mo.base).delay((d) => (animate ? d.ci * mo.stagger * 0.6 : 0)).style("fill", (d) => v(`data-seq-${q(d.val)}`));
    svg.selectAll("text.rl").data(data.rows).join("text").attr("class", "rl").attr("x", m.l - 6).attr("y", (_, i) => m.t + i * ch + ch / 2 + 4)
      .attr("text-anchor", "end").text((d) => d);
    const every = Math.ceil(data.cols.length / (W < 420 ? 5 : 10));
    svg.selectAll("text.cl").data(data.cols).join("text").attr("class", "cl").attr("text-anchor", "middle")
      .attr("x", (_, i) => m.l + i * cw + cw / 2).attr("y", H - 6).text((d, i) => (i % every === 0 ? d : ""));
  }
  return { draw };
}

// ------------------------------------------------------------------ diverging bars
/** data: [{name, val}] (percent change). */
export function divergingBars(el, data, { label = "Diverging bar chart", legendEl = null } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const rows = state.sort ? [...data].sort((a, b) => b.val - a.val) : data;
    const bh = 22, gap = 8, m = { t: 4, r: 44, b: 22, l: W < 420 ? 112 : 128 };
    const H = m.t + m.b + rows.length * (bh + gap);
    const ext = d3.max(data, (d) => Math.abs(d.val));
    const pad = 44; // room for value labels beyond the longest bar
    const x = d3.scaleLinear([-ext, ext], [m.l + pad, W - m.r]).nice();
    // magnitude picks the step: steps 1-4 negative (cobalt end), 6-9 positive (ochre end)
    const step = (val) => (val < 0 ? 4 - Math.min(3, Math.floor((-val / ext) * 3.999)) : 6 + Math.min(3, Math.floor((val / ext) * 3.999)));
    if (legendEl) legendEl.innerHTML = `<span style="gap:2px">${d3.range(1, 10).map((i) => `<i style="background:${v(`data-div-${i}`)};border-radius:0;width:18px"></i>`).join("")}</span><span>fall ← 0 → rise</span>`;
    const svg = frame(el, W, H, label);
    svg.selectAll("g.ss-x").data([0]).join("g").attr("class", "ss-axis ss-x").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).ticks(5).tickFormat((d) => `${d > 0 ? "+" : ""}${d}%`).tickSizeOuter(0));
    const y = (i) => m.t + i * (bh + gap);
    const g = svg.selectAll("g.row").data(rows, (d) => d.name).join((en) => en.append("g").attr("class", "row").attr("transform", (_, i) => `translate(0,${y(i)})`));
    T(g, animate).attr("transform", (_, i) => `translate(0,${y(i)})`);
    g.selectAll("path").data((d) => [d]).join("path").style("fill", (d) => v(`data-div-${step(d.val)}`)).attr("d", (d) => hbar(x(0), x(d.val), 0, bh))
      .on("pointermove", (e, d) => getTip().show(`<b>${d.name}</b><br>${d.val > 0 ? "+" : ""}${fmt(d.val, 1)}%`, e.clientX, e.clientY))
      .on("pointerleave", () => getTip().hide());
    g.selectAll("text.n").data((d) => [d]).join("text").attr("class", "n ss-label").attr("x", m.l - 8).attr("y", bh / 2 + 4).attr("text-anchor", "end").text((d) => d.name);
    g.selectAll("text.v").data((d) => [d]).join("text").attr("class", "v ss-value").attr("y", bh / 2 + 4)
      .attr("x", (d) => x(d.val) + (d.val < 0 ? -6 : 6)).attr("text-anchor", (d) => (d.val < 0 ? "end" : "start"))
      .text((d) => `${d.val > 0 ? "+" : ""}${fmt(d.val, 1)}%`);
    svg.selectAll("line.zero").data([0]).join("line").attr("class", "zero").attr("x1", x(0)).attr("x2", x(0)).attr("y1", 0).attr("y2", H - m.b)
      .style("stroke", v("axis"));
  }
  return { draw };
}

// ------------------------------------------------------------------ horizon motif
/**
 * A horizon line over a seabed profile with strata beneath: the Nordic "building on the horizon"
 * motif, and a seismic horizon. Decorative, so it lives outside plot areas (Few rule 1).
 * `profile` is an array of depths 0..1 (e.g. from bathymetry or a picked horizon); if omitted, a
 * smooth illustrative profile is generated from `seed`.
 */
export function horizon(el, { profile = null, seed = 7, layers = 4, height = 120, label = "Horizon motif" } = {}) {
  function draw(W) {
    const n = 160;
    const rnd = d3.randomLcg(seed);
    const ph = d3.range(4).map(() => rnd() * Math.PI * 2);
    const prof = profile ?? d3.range(n).map((i) => {
      const t = i / (n - 1);
      return 0.5 + 0.18 * Math.sin(t * 3.1 + ph[0]) + 0.09 * Math.sin(t * 7.3 + ph[1]) + 0.04 * Math.sin(t * 17 + ph[2]);
    });
    const x = d3.scaleLinear([0, prof.length - 1], [0, W]);
    const top = 0.28 * height, seabedMin = 0.42 * height, seabedMax = 0.72 * height;
    const yb = (v) => seabedMin + (seabedMax - seabedMin) * v;
    const svg = d3.select(el).selectAll("svg").data([0]).join("svg")
      .attr("viewBox", `0 0 ${W} ${height}`).attr("role", "img").attr("aria-label", label)
      .attr("preserveAspectRatio", "none").style("display", "block").style("width", "100%").style("height", `${height}px`);
    // strata: each layer follows the seabed, thinning with depth; fills step down the shale ladder
    const steps = [3, 4, 5, 7].slice(0, layers);
    const band = (k) => d3.area().curve(d3.curveBasis).x((_, i) => x(i))
      .y0((v) => Math.min(height, yb(v) + (k + 1) * (height - seabedMax) / (layers + 0.4) + (v - 0.5) * 6 * (k + 1)))
      .y1((v) => (k === 0 ? yb(v) : Math.min(height, yb(v) + k * (height - seabedMax) / (layers + 0.4) + (v - 0.5) * 6 * k)));
    svg.selectAll("path.stratum").data(steps).join("path").attr("class", "stratum")
      .attr("d", (_, k) => band(k)(prof)).style("fill", (s) => `var(--ss-shale-${s})`).style("opacity", 0.55);
    svg.selectAll("path.seabed").data([0]).join("path").attr("class", "seabed").attr("fill", "none")
      .attr("d", d3.line().curve(d3.curveBasis).x((_, i) => x(i)).y(yb)(prof))
      .style("stroke", "var(--ss-fjord-9)").attr("stroke-width", 1.25);
    svg.selectAll("line.horizon").data([0]).join("line").attr("class", "horizon")
      .attr("x1", 0).attr("x2", W).attr("y1", top).attr("y2", top).style("stroke", "var(--ss-border)").attr("stroke-width", 1);
  }
  return { draw };
}

// ------------------------------------------------------------------ entity colours
/** Colour follows the entity: groups[i] → data-cat-(i+1) while slots last, else context grey. */
export function groupColour(el, groups) {
  const n = catCount(el);
  return (g) => {
    const i = groups ? groups.indexOf(g) : -1;
    return i >= 0 && i < n ? v(`data-cat-${i + 1}`) : v("data-context");
  };
}

// ------------------------------------------------------------------ horizontal bars
/** data: [{label, value, parts?: {a, b}, group?}] (sorted). spec: parts, parts_labels, groups. state: {highlight} */
export function barChart(el, data, { label = "Bar chart", legendEl = null, spec = {}, groups = null } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const col = spec.colour_by ? groupColour(el, spec.groups || groups) : () => v("data-story-1");
    const parts = spec.part || null;
    if (legendEl) {
      legendEl.innerHTML = parts && spec.parts_labels
        ? parts.map((p, i) => `<span><i style="background:var(--ss-text-subtle);opacity:${i ? 0.35 : 1}"></i>${spec.parts_labels[i] ?? p}</span>`).join("")
        : "";
    }
    const hl = new Set(state.highlight ?? []);
    const rows = state.sort === "label" ? [...data].sort((a, b) => String(a.label).localeCompare(b.label)) : data;
    const bh = 20, gap = 7, m = { t: 4, r: 40, b: 8, l: W < 420 ? 96 : 124 };
    const H = m.t + m.b + rows.length * (bh + gap);
    const max = d3.max(rows, (d) => d.value) || 1;
    const x = d3.scaleLinear([0, max], [m.l, W - m.r]);
    const svg = frame(el, W, H, label);
    const g = svg.selectAll("g.row").data(rows, (d) => d.label)
      .join((en) => en.append("g").attr("class", "row").attr("transform", (_, i) => `translate(0,${m.t + i * (bh + gap)})`));
    T(g, animate).attr("transform", (_, i) => `translate(0,${m.t + i * (bh + gap)})`)
      .style("opacity", (d) => (hl.size && !hl.has(d.label) ? 0.35 : 1));
    g.each(function (d) {
      const segs = parts ? parts.map((p, i) => ({ p, i, v: d.parts?.[p] ?? 0 })) : [{ p: "value", i: 0, v: d.value }];
      let acc = 0;
      segs.forEach((s) => { s.x0 = acc; acc += s.v; s.x1 = acc; s.last = false; });
      const nonzero = segs.filter((s) => s.v > 0);
      if (nonzero.length) nonzero.at(-1).last = true;
      d3.select(this).selectAll("path.seg").data(segs, (s) => s.p).join("path").attr("class", "seg")
        .style("fill", col(d.group ?? d.label)).style("fill-opacity", (s) => (s.i ? 0.35 : 1))
        .attr("d", (s) => {
          if (s.v <= 0) return "";
          const a = x(s.x0) + (s.i ? 1 : 0), b = x(s.x1);
          return s.last ? hbar(a, b, 0, bh) : `M${a},0H${b}V${bh}H${a}Z`;
        })
        .on("pointermove", (e) => getTip().show(`<b>${d.label}</b><br>${segs.map((s) => `${spec.parts_labels?.[s.i] ?? s.p}: ${fmt(s.v)}`).join("<br>")}`, e.clientX, e.clientY))
        .on("pointerleave", () => getTip().hide());
    });
    g.selectAll("text.n").data((d) => [d]).join("text").attr("class", "n ss-label").attr("x", m.l - 8).attr("y", bh / 2 + 4)
      .attr("text-anchor", "end").text((d) => d.label);
    g.selectAll("text.v").data((d) => [d]).join("text").attr("class", "v ss-value").attr("y", bh / 2 + 4)
      .attr("x", (d) => x(d.value) + 6).text((d) => fmt(d.value));
    svg.selectAll("line.base").data([0]).join("line").attr("class", "base").attr("x1", x(0)).attr("x2", x(0))
      .attr("y1", 0).attr("y2", H - m.b).style("stroke", v("axis"));
  }
  return { draw };
}

// ------------------------------------------------------------------ dot strip
/** data: [{row, value, label?, flag?, group?}]. spec: rows (order), scale, value_label, flag_label, groups. */
export function dotStrip(el, data, { label = "Dot strip", legendEl = null, spec = {}, groups = null } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const col = groupColour(el, spec.groups || groups);
    const rows = spec.rows || [...d3.rollup(data, (v) => v.length, (d) => d.row)].sort((a, b) => b[1] - a[1]).map((d) => d[0]);
    if (legendEl && spec.flag_label) {
      legendEl.innerHTML = `<span><i style="background:var(--ss-text-subtle);border-radius:50%"></i>${spec.value_label ?? "one dot per item"}</span>`
        + `<span><i style="border:2px solid var(--ss-text-subtle);border-radius:50%;width:10px;height:10px"></i>${spec.flag_label}</span>`;
    }
    const rh = 28, m = { t: 8, r: 14, b: 28, l: W < 420 ? 96 : 124 };
    const H = m.t + m.b + rows.length * rh;
    const max = d3.max(data, (d) => d.value) || 1;
    const x = (spec.scale === "symlog" ? d3.scaleSymlog().constant(1) : spec.scale === "sqrt" ? d3.scaleSqrt() : d3.scaleLinear())
      .domain([0, max]).range([m.l + 6, W - m.r]).nice();
    const y = d3.scaleBand(rows, [m.t, H - m.b]).padding(0.1);
    const svg = frame(el, W, H, label);
    const ticks = spec.scale === "symlog" ? [0, 1, 2, 5, 10, 25, 50, 100, 250].filter((t) => t <= x.domain()[1]) : x.ticks(6);
    svg.selectAll("g.ss-grid").data([0]).join("g").attr("class", "ss-grid").attr("transform", `translate(0,${m.t})`)
      .call(d3.axisBottom(x).tickValues(ticks).tickSize(H - m.t - m.b).tickFormat(""));
    svg.selectAll("g.ss-x").data([0]).join("g").attr("class", "ss-axis ss-x").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickValues(ticks).tickFormat((d) => fmt(d)).tickSizeOuter(0));
    svg.selectAll("text.row").data(rows).join("text").attr("class", "row ss-label")
      .attr("x", m.l - 10).attr("y", (r) => y(r) + y.bandwidth() / 2 + 4).attr("text-anchor", "end").text((r) => r);
    const hl = new Set(state.highlight ?? []);
    const jit = (i) => ((Math.sin(i * 12.9898) * 43758.5453) % 1);
    const c = svg.selectAll("circle.d").data(data.map((d, i) => ({ ...d, i })), (d) => d.label ?? d.i).join("circle").attr("class", "d")
      .attr("r", 5).attr("stroke-width", 2)
      .on("pointermove", (e, d) => getTip().show(`<b>${d.label ?? ""}</b> · ${d.row}<br>${fmt(d.value, 1)} ${spec.unit ?? ""}${d.flag ? `<br>${spec.flag_label ?? "flagged"}` : ""}`, e.clientX, e.clientY))
      .on("pointerleave", () => getTip().hide());
    T(c, animate).attr("cx", (d) => x(d.value)).attr("cy", (d) => y(d.row) + y.bandwidth() / 2 + jit(d.i) * y.bandwidth() * 0.28)
      .style("fill", (d) => (d.flag ? v("surface") : col(d.group ?? d.row)))
      .style("stroke", (d) => (d.flag ? col(d.group ?? d.row) : v("surface")))
      .style("opacity", (d) => (hl.size && !hl.has(d.row) && !hl.has(d.label) ? 0.25 : 1));
  }
  return { draw };
}

// ------------------------------------------------------------------ canvas map
/**
 * Canvas map with smooth camera moves. Geometry is projected once into Path2D objects (one combined
 * path per uniformly styled layer, one per colour group for the focus layer), so a frame is a
 * handful of fill/stroke calls; camera moves interpolate with d3.interpolateZoom.
 * layers: [{data, role: land|area|context|grid|lines|focus|points, colour_by?, groups?, label?, tooltip?}]
 * state: {view: [w, s, e, n], filter: {prop: value | [values]}}
 */
export function geoMap(el, spec, datasets, { label = "Map", legendEl = null, groups = null } = {}) {
  const host = d3.select(el).classed("ss-map", true);
  const canvas = host.selectAll("canvas").data([0]).join("canvas").attr("role", "img").attr("aria-label", label).node();
  const ctx = canvas.getContext("2d");
  const hitCtx = document.createElement("canvas").getContext("2d");
  const layers = spec.layers.map((ly) => ({ ...ly, fc: datasets[ly.data] }));
  const frameLayer = layers.find((l) => l.role === (spec.frame || "area")) || layers[0];
  const proj = d3.geoConicConformal().parallels([60, 72]).rotate([-14, 0]);
  proj.fitSize([1000, 1000], frameLayer.fc);
  const path = d3.geoPath(proj);
  const focusGroups = groups || spec.groups;
  // pre-build Path2D
  for (const ly of layers) {
    if (ly.role === "points") {
      ly.pts = (ly.fc.features ?? ly.fc).map((f) => {
        const c = f.geometry ? f.geometry.coordinates : [f.x, f.y];
        return { p: proj(c), name: f.properties?.[ly.label || "name"] ?? f.n ?? "" };
      });
      continue;
    }
    if (ly.role === "focus") {
      ly.items = ly.fc.features.map((f) => ({ f, path: new Path2D(path(f)) }));
    } else {
      const all = new Path2D();
      for (const f of ly.fc.features) all.addPath(new Path2D(path(f)));
      ly.all = all;
    }
  }
  let W = 0, H = 0, cur = null, timer = null, state = {}, transform = { k: 1, x: 0, y: 0 };

  const viewToZoom = (view) => {
    let b;
    if (view) {
      const [w, s, e, n] = view;
      const pts = [[w, s], [w, n], [e, s], [e, n], [(w + e) / 2, n], [(w + e) / 2, s]].map((c) => proj(c));
      b = [[d3.min(pts, (p) => p[0]), d3.min(pts, (p) => p[1])], [d3.max(pts, (p) => p[0]), d3.max(pts, (p) => p[1])]];
    } else b = path.bounds(frameLayer.fc);
    return [(b[0][0] + b[1][0]) / 2, (b[0][1] + b[1][1]) / 2, Math.max(b[1][0] - b[0][0], (b[1][1] - b[0][1]) * (W / H))];
  };
  const zoomToTransform = ([cx, cy, w]) => { const k = (W / w) * 0.94; return { k, x: W / 2 - cx * k, y: H / 2 - cy * k }; };
  const matches = (props) => {
    const flt = state.filter;
    if (!flt) return true;
    return Object.entries(flt).every(([k, val]) => (Array.isArray(val) ? val.includes(props[k]) : props[k] === val));
  };

  function paint() {
    const cs = getComputedStyle(el);
    const c = (name) => cs.getPropertyValue(`--ss-${name}`).trim();
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = c("info-fill-muted");
    ctx.fillRect(0, 0, W, H);
    const { k, x, y } = transform;
    ctx.setTransform(dpr * k, 0, 0, dpr * k, dpr * x, dpr * y);
    const px = 1 / k;
    const colourOf = (g) => {
      const i = focusGroups ? focusGroups.indexOf(g) : -1;
      return i >= 0 && i < (parseInt(c("data-cat-count")) || 5) ? c(`data-cat-${i + 1}`) : c("data-context");
    };
    for (const ly of layers) {
      if (ly.role === "land") { ctx.fillStyle = c("neutral-fill-muted-pressed"); ctx.fill(ly.all); }
      else if (ly.role === "area") { ctx.fillStyle = c("accent-fill-muted"); ctx.globalAlpha = 0.9; ctx.fill(ly.all); ctx.globalAlpha = 1; }
      else if (ly.role === "context") {
        ctx.fillStyle = c("data-context"); ctx.globalAlpha = 0.32; ctx.fill(ly.all); ctx.globalAlpha = 1;
        ctx.strokeStyle = c("surface"); ctx.lineWidth = 0.6 * px; ctx.stroke(ly.all);
      } else if (ly.role === "grid") { ctx.strokeStyle = c("grid"); ctx.lineWidth = 0.6 * px; ctx.stroke(ly.all); }
      else if (ly.role === "lines") { ctx.strokeStyle = c("border"); ctx.setLineDash([4 * px, 3 * px]); ctx.lineWidth = 1 * px; ctx.stroke(ly.all); ctx.setLineDash([]); }
      else if (ly.role === "focus") {
        for (const it of ly.items) {
          const on = matches(it.f.properties);
          ctx.fillStyle = on ? colourOf(it.f.properties[ly.colour_by]) : c("data-context");
          ctx.globalAlpha = on ? 0.95 : 0.25;
          ctx.fill(it.path);
        }
        ctx.globalAlpha = 1;
        ctx.strokeStyle = c("surface"); ctx.lineWidth = 0.8 * px;
        for (const it of ly.items) ctx.stroke(it.path);
      }
    }
    // labels in screen space
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const font = cs.getPropertyValue("--ss-font-body");
    for (const ly of layers.filter((l) => l.role === "points")) {
      ctx.font = `500 11px ${font}`;
      for (const pt of ly.pts) {
        const sx = pt.p[0] * k + x, sy = pt.p[1] * k + y;
        if (sx < 0 || sy < 0 || sx > W || sy > H) continue;
        ctx.fillStyle = c("text-subtle"); ctx.beginPath(); ctx.arc(sx, sy, 2.2, 0, Math.PI * 2); ctx.fill();
        ctx.lineWidth = 3; ctx.strokeStyle = c("info-fill-muted"); ctx.strokeText(pt.name, sx + 5, sy + 4);
        ctx.fillStyle = c("text-subtle"); ctx.fillText(pt.name, sx + 5, sy + 4);
      }
    }
  }

  function legend() {
    if (!legendEl) return;
    const focus = layers.find((l) => l.role === "focus");
    const ctxLayer = layers.find((l) => l.role === "context");
    const n = catCount(el);
    const shown = (focusGroups || []).slice(0, n);
    legendEl.innerHTML = shown.map((g, i) => `<span><i style="background:var(--ss-data-cat-${i + 1})"></i>${g}</span>`).join("")
      + (focusGroups && focusGroups.length > n ? `<span><i style="background:var(--ss-data-context)"></i>${spec.other_label ?? "Other"}</span>` : "")
      + (ctxLayer ? `<span><i style="background:var(--ss-data-context);opacity:.35"></i>${ctxLayer.legend ?? "Context"}</span>` : "")
      + (focus && !focusGroups ? "" : "");
  }

  function resize(nw) {
    W = nw;
    H = Math.round(Math.min(nw * (spec.aspect ?? 0.95), (window.innerHeight || 800) * 0.7));
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(W * dpr); canvas.height = Math.round(H * dpr);
    canvas.style.height = `${H}px`;
  }

  function draw(nw, st = {}, { animate = false } = {}) {
    if (nw !== W) resize(nw);
    state = st;
    legend();
    const target = viewToZoom(st.view);
    if (timer) timer.stop();
    if (!animate || !cur) {
      cur = target; transform = zoomToTransform(cur); paint(); return;
    }
    const interp = d3.interpolateZoom(cur, target);
    const dur = Math.max(motion().slow, interp.duration * 0.6);
    timer = d3.timer((t) => {
      const u = d3.easeCubicInOut(Math.min(1, t / dur));
      cur = interp(u); transform = zoomToTransform(cur); paint();
      if (u >= 1) timer.stop();
    });
  }

  // hover
  canvas.addEventListener("pointermove", (e) => {
    const r = canvas.getBoundingClientRect();
    const bx = (e.clientX - r.left - transform.x) / transform.k, by = (e.clientY - r.top - transform.y) / transform.k;
    const focus = layers.find((l) => l.role === "focus");
    const hit = focus?.items.find((it) => hitCtx.isPointInPath(it.path, bx, by));
    if (!hit) return getTip().hide();
    const p = hit.f.properties;
    const fields = focus.tooltip || Object.keys(p).slice(0, 4);
    getTip().show(`<b>${p[focus.label || "name"] ?? ""}</b><br>${fields.map((k) => `<span class="ss-k">${k.replace(/_/g, " ")}</span> ${p[k] ?? "–"}`).join("<br>")}`, e.clientX, e.clientY);
  });
  canvas.addEventListener("pointerleave", () => getTip().hide());
  return { draw, repaint: () => W && paint() };
}
