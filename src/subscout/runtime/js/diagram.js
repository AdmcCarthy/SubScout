// A labelled diagram: the set-up a graph assumes, drawn to one scale on both axes and moved between states.
// Data: { box: [x0, y0, x1, y1] with y upward, shapes: [{id, kind, group, ...}] }
//   poly:   { pts, fill, opacity, stroke, dash, width }     a closed outline, filled
//   line:   { pts, colour, dash, width }                    an open line
//   arrow:  { from, to, colour, width, double }             a line with a head (two heads if double)
//   circle: { c, r, fill, opacity, stroke, width }          r in the units of the box
//   text:   { at, text, anchor, size, colour, italic, bold, rotate, dx, dy }
// State: { show: [groups], focus: [groups] }. The geometry is computed in Python; nothing here is physics.
import { token, onSchemeChange, motion, reducedMotion } from "./subscout.js";

const NAMED = { c1: "data-cat-1", c2: "data-cat-2", c3: "data-cat-3", c4: "data-cat-4", c5: "data-cat-5", context: "data-context", highlight: "data-highlight" };
export default function diagram(el, datasets, opts = {}) {
  const D = Object.values(datasets)[0];
  const svg = d3.select(el).append("svg").attr("role", "img").attr("aria-label", opts.label || "Diagram");
  const defs = svg.append("defs");
  const gShapes = svg.append("g"), gText = svg.append("g");
  const uid = Math.random().toString(36).slice(2, 8);
  let last = null, lastW = 0;

  const has = (list, s) => !list || s.group === undefined || list.includes(s.group) || list.includes(s.id);
  const raw = (name) => (name === "text" ? token("text") || "currentColor" : name === "muted" ? token("text-muted") || "#888" : name === "surface" ? token("surface") || "#fff" : token(NAMED[name] ?? name) || "currentColor");
  const dur = (animate, k = 1) => (animate && !reducedMotion() ? (motion().slow || 600) * k : 0);

  function height(width) {
    if (opts.export && opts.height) return opts.height();
    const vh = window.innerHeight;
    if (opts.vhShare) return Math.round(vh * opts.vhShare);
    return Math.round(Math.min(Math.max(width * 0.66, 280), vh * 0.6));
  }

  function draw(width, state = {}, { animate } = {}) {
    last = [width, state];
    const resized = width !== lastW;
    lastW = width;
    const T = dur(animate && !resized, 0.7);
    const H = height(width);
    const m = { l: 8, r: 8, t: 8, b: 8 };
    svg.attr("viewBox", `0 0 ${width} ${H}`).attr("width", width).attr("height", H);
    const [x0, y0, x1, y1] = D.box;
    const k = Math.min((width - m.l - m.r) / (x1 - x0), (H - m.t - m.b) / (y1 - y0));
    const ox = m.l + (width - m.l - m.r - k * (x1 - x0)) / 2, oy = m.t + (H - m.t - m.b - k * (y1 - y0)) / 2;
    const X = (v) => ox + k * (v - x0), Y = (v) => oy + k * (y1 - v);
    const px = (pts) => pts.map((p) => [X(p[0]), Y(p[1])]);
    const d = (pts, closed) => "M" + pts.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join("L") + (closed ? "Z" : "");
    const visible = (s) => has(state.show, s);
    const dim = (s) => (state.focus && !has(state.focus, s) ? 0.25 : 1);
    const tr = (sel) => (T ? sel.transition().duration(T).ease(d3.easeCubicInOut) : sel);

    const ink = raw;
    defs.selectAll("*").remove();

    function marker(name) {
      const id = `sch-${uid}-${name}`;
      if (defs.select(`#${id}`).empty()) {
        defs.append("marker").attr("id", id).attr("viewBox", "0 0 10 10").attr("refX", 8.5).attr("refY", 5).attr("markerWidth", 6.5).attr("markerHeight", 6.5).attr("orient", "auto-start-reverse")
          .append("path").attr("d", "M0,0.8 L10,5 L0,9.2 z").attr("fill", ink(name));
      }
      return `url(#${id})`;
    }

    function build(g, s) {
      g.selectAll("*").remove();
      {
        if (s.kind === "poly") {
          g.append("path").attr("d", d(px(s.pts), true)).attr("fill", s.fill ? ink(s.fill) : "none").attr("fill-opacity", s.opacity ?? 0.5)
            .attr("stroke", s.stroke === "none" ? "none" : ink(s.stroke || "text")).attr("stroke-width", s.width ?? 1.2).attr("stroke-dasharray", s.dash ? "5 4" : null);
        } else if (s.kind === "line") {
          g.append("path").attr("d", d(px(s.pts), false)).attr("fill", "none").attr("stroke", ink(s.colour || "text")).attr("stroke-width", s.width ?? 1.4).attr("stroke-dasharray", s.dash ? "5 4" : null).attr("stroke-linecap", "round");
        } else if (s.kind === "arrow") {
          const c = s.colour || "text";
          g.append("path").attr("d", d(px([s.from, s.to]), false)).attr("fill", "none").attr("stroke", ink(c)).attr("stroke-width", s.width ?? 1.8)
            .attr("marker-end", marker(c)).attr("marker-start", s.double ? marker(c) : null);
        } else if (s.kind === "circle") {
          g.append("circle").attr("cx", X(s.c[0])).attr("cy", Y(s.c[1])).attr("r", Math.max(0.5, k * s.r)).attr("fill", s.fill ? ink(s.fill) : "none").attr("fill-opacity", s.opacity ?? 0.5)
            .attr("stroke", s.stroke === "none" ? "none" : ink(s.stroke || "text")).attr("stroke-width", s.width ?? 1.2);
        }
      }
    }

    const geom = D.shapes.filter((s) => s.kind !== "text");
    gShapes.selectAll("g.sh").data(geom, (s) => s.id).join((enter) => enter.append("g").attr("class", "sh").attr("opacity", 0))
      .each(function (s) { build(d3.select(this), s); })
      .call((sel) => tr(sel).attr("opacity", (s) => (visible(s) ? dim(s) : 0)));

    const base = Math.max(13.5, Math.min(19, width / 46));
    gText.selectAll("text").data(D.shapes.filter((s) => s.kind === "text"), (s) => s.id).join((enter) => enter.append("text").attr("opacity", 0))
      .text((s) => s.text)
      .attr("x", (s) => X(s.at[0]) + (s.dx || 0)).attr("y", (s) => Y(s.at[1]) + (s.dy || 0))
      .attr("text-anchor", (s) => s.anchor || "start").attr("dominant-baseline", "middle")
      .attr("font-size", (s) => base * (s.size || 1)).attr("font-style", (s) => (s.italic ? "italic" : null)).attr("font-weight", (s) => (s.bold ? 600 : null))
      .style("fill", (s) => ink(s.colour || "text"))
      .attr("transform", (s) => (s.rotate ? `rotate(${-s.rotate},${X(s.at[0])},${Y(s.at[1])})` : null))
      .call((sel) => tr(sel).attr("opacity", (s) => (visible(s) ? dim(s) : 0)));
  }
  onSchemeChange(() => last && draw(last[0], last[1], { animate: false }));
  return { draw, repaint: () => last && draw(last[0], last[1], { animate: false }) };
}
