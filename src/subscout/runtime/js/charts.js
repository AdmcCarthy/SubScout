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
export function lineChart(el, data, { label = "Line chart", unitLabel = () => "" } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const f = unitF();
    const focus = state.focus ?? [];
    const H = Math.round(Math.max(220, Math.min(360, W * 0.6)));
    const m = { t: 30, r: W < 420 ? 58 : 70, b: 24, l: 34 };
    const x = d3.scaleLinear(d3.extent(data.x), [m.l, W - m.r]);
    const y = d3.scaleLinear([0, d3.max(data.series, (d) => d3.max(d.vals)) * f], [H - m.b, m.t]).nice();
    const svg = frame(el, W, H, label);
    yAxis(svg, y, m, W, animate);
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
      .attr("x", W - m.r + 6).attr("y", H - m.b - 8).text(focus.length ? "Others" : "");
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
          `<tr><td>${focus.includes(d.name) ? `<b>${d.name}</b>` : d.name}</td><td class="ss-num" style="text-align:right;padding-left:12px">${d.vals[i] ? fmt(d.vals[i] * f, 1) : "–"}</td></tr>`).join("");
        getTip().show(`<b>${xv}</b> <span class="ss-k">${unitLabel()}</span><table>${rows}</table>`, e.clientX, e.clientY);
      })
      .on("pointerleave", () => { cross.attr("opacity", 0); getTip().hide(); });
  }
  return { draw };
}

// ------------------------------------------------------------------ stacked bars
/** data: {x: [label], series: [{name, vals}]} ordered largest first; overflow folds into "Other". */
export function stackedBars(el, data, { label = "Stacked bar chart", legendEl = null, unitLabel = () => "" } = {}) {
  function draw(W, state = {}, { animate = false } = {}) {
    const f = unitF();
    const n = catCount(el);
    const keep = data.series.slice(0, n);
    const rest = data.series.slice(n);
    const series = rest.length
      ? [...keep, { name: `Other (${rest.length})`, other: true, vals: data.x.map((_, i) => d3.sum(rest, (s) => s.vals[i])) }]
      : keep;
    const col = (s, i) => (s.other ? v("data-context") : v(`data-cat-${i + 1}`));
    if (legendEl) legendEl.innerHTML = series.map((s, i) => `<span><i style="background:${col(s, i)}"></i>${s.name}</span>`).join("");
    const H = Math.round(Math.max(220, Math.min(340, W * 0.58)));
    const m = { t: 10, r: 6, b: 24, l: 38 };
    const x = d3.scaleBand(data.x, [m.l, W - m.r]).padding(0.25);
    const totals = data.x.map((_, i) => d3.sum(series, (s) => s.vals[i]) * f);
    const y = d3.scaleLinear([0, d3.max(totals)], [H - m.b, m.t]).nice();
    const svg = frame(el, W, H, label);
    yAxis(svg, y, m, W, animate);
    svg.selectAll("g.ss-x").data([0]).join("g").attr("class", "ss-axis ss-x").attr("transform", `translate(0,${H - m.b})`)
      .call(d3.axisBottom(x).tickSizeOuter(0).tickValues(W < 420 ? data.x.filter((_, i) => i % 2 === 0) : data.x));
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
