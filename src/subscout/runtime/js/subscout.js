// SubScout runtime: state engine (Read = scroll, Present = deck), theme, type and units.
// Plain ES module, no build step. Charts register a render(stateIndex, {animate}) callback;
// both modes drive the same ordered state sequence, so transitions are written once.

const root = document.documentElement;
const store = (k, v) => {
  try {
    if (v === undefined) return localStorage.getItem(`ss:${k}`);
    localStorage.setItem(`ss:${k}`, v);
  } catch {
    /* storage unavailable: preferences just don't persist */
  }
  return null;
};

export const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** Motion tokens from CSS, in ms, so d3 transitions match CSS ones. */
export function motion() {
  const cs = getComputedStyle(root);
  const ms = (name) => parseFloat(cs.getPropertyValue(name)) || 0;
  return { fast: ms("--ss-dur-fast"), base: ms("--ss-dur"), slow: ms("--ss-dur-slow"), stagger: ms("--ss-stagger") };
}

/** Run work when the main thread is idle (falls back to a short timeout). */
export const idle = (fn) => (window.requestIdleCallback ? requestIdleCallback(fn, { timeout: 600 }) : setTimeout(fn, 60));

/** Is the element (or its layer) currently shown? Hidden layers can redraw later, in idle time. */
export const isShown = (el) => !el.closest(".ss-layer") || el.closest(".ss-layer").classList.contains("is-on");

/** Read a colour token, e.g. token("data-context"). */
export const token = (name) => getComputedStyle(root).getPropertyValue(`--ss-${name}`).trim();

// ---------------------------------------------------------------- simple observable prefs
export function pref(key, attr, fallback, onApply) {
  const subs = new Set();
  let value = store(key) ?? fallback;
  const apply = () => {
    if (attr) {
      if (value === "system") root.removeAttribute(attr);
      else root.setAttribute(attr, value);
    }
    onApply?.(value);
    subs.forEach((f) => f(value));
  };
  apply();
  return {
    get: () => value,
    set(v) {
      value = v;
      store(key, v);
      apply();
    },
    subscribe(f) {
      subs.add(f);
      return () => subs.delete(f);
    },
  };
}

export const theme = pref("theme", "data-colour-scheme", "system");
export const typePairing = pref("type", "data-type", "ledger");
export const palettePreset = pref("palette", "data-palette", "tide");
export const surfaceOption = pref("surface", "data-surface", "nordic-cool");

// Re-render charts when the effective colour scheme changes (system or manual).
const schemeSubs = new Set();
export const onSchemeChange = (f) => schemeSubs.add(f);
theme.subscribe(() => requestAnimationFrame(() => schemeSubs.forEach((f) => f())));
window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => schemeSubs.forEach((f) => f()));

// ---------------------------------------------------------------- units
// Values are stored in the base unit (Sm³ o.e.); display converts. 1 Sm³ o.e. = 6.29 boe.
export const UNITS = {
  sm3: { label: "Sm³ o.e.", short: "Sm³", factor: 1 },
  boe: { label: "boe", short: "boe", factor: 6.29 },
};
/** Re-write every [data-ss-value] number and [data-ss-unit] label under `scope` for the current unit. */
let currentUnit = "sm3";
export function refreshUnits(scope = document, u = currentUnit) {
  scope.querySelectorAll("[data-ss-value]").forEach((el) => {
    const v = parseFloat(el.dataset.ssValue) * UNITS[u].factor;
    const scale = el.dataset.ssScale || ""; // e.g. "M" for millions
    const div = { "": 1, k: 1e3, M: 1e6, G: 1e9 }[scale];
    const digits = el.dataset.ssDigits ? +el.dataset.ssDigits : 0;
    el.textContent = `${fmt(v / div, digits)}${scale ? " " + (scale === "M" ? "million" : scale) : ""}`;
  });
  scope.querySelectorAll("[data-ss-unit]").forEach((el) => (el.textContent = UNITS[u].label));
}
export const units = pref("units", null, "sm3", (u) => {
  currentUnit = UNITS[u] ? u : "sm3";
  refreshUnits(document, currentUnit);
});

/** British number formatting: 12,345.6 */
export function fmt(v, digits = 0) {
  return v.toLocaleString("en-GB", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

// ---------------------------------------------------------------- segmented controls
/** Wire a .ss-seg group: buttons with data-value bound to a pref. */
export function bindSeg(el, p) {
  const sync = (v) => el.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.value === v)));
  el.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-value]");
    if (b) p.set(b.dataset.value);
  });
  p.subscribe(sync);
  sync(p.get());
}

// ---------------------------------------------------------------- the story engine
/**
 * story(el, {render, onEdge, numbering}) wires one .ss-story: .ss-steps > .ss-step (one state each) and .ss-graphic.
 * render(index, {animate, mode}) is called on every state change, in either mode.
 * A page holds one .ss-story per scrolly sequence; present mode runs them as one deck. onEdge(dir) is called when the
 * reader steps past the last step (dir 1) or before the first (dir -1), so the page can hand over to the next or
 * previous sequence; numbering() returns { offset, total } so the counter numbers the whole story.
 */
export function story(el, { render, onEdge = null, numbering = null }) {
  const steps = [...el.querySelectorAll(".ss-step")];
  let current = -1;
  let mode = "read";

  const label = (i) => {
    const n = numbering?.() ?? { offset: 0, total: steps.length };
    return `${n.offset + i + 1} / ${n.total}`;
  };
  const go = (i, animate = true) => {
    i = Math.max(0, Math.min(steps.length - 1, i));
    if (i === current) return;
    current = i;
    steps.forEach((s, k) => s.classList.toggle("is-active", k === i));
    dots.forEach((d, k) => d.setAttribute("aria-current", String(k === i)));
    if (counter) counter.textContent = label(i);
    render(i, { animate: animate && !reducedMotion(), mode });
  };
  // present-mode stepping: past either end, hand over to the neighbouring sequence when there is one
  const step = (delta) => {
    const t = current + delta;
    if ((t < 0 || t >= steps.length) && onEdge) onEdge(delta < 0 ? -1 : 1);
    else go(t);
  };

  // Read mode: the step whose card crosses the trigger line is active. The line sits where the reader's
  // eye is: the middle on desktop, inside the text area below the pinned figure on phones
  // (CSS custom property --ss-trigger, a percentage of the viewport height).
  let io = null;
  const watch = () => {
    io?.disconnect();
    const t = parseFloat(getComputedStyle(el).getPropertyValue("--ss-trigger")) || 50;
    io = new IntersectionObserver(
      (entries) => {
        if (mode !== "read") return;
        entries.forEach((en) => en.isIntersecting && go(steps.indexOf(en.target.closest(".ss-step"))));
      },
      { rootMargin: `-${t}% 0px -${100 - t}% 0px` },
    );
    steps.forEach((s) => io.observe(s.querySelector(".ss-step-card") ?? s));
  };
  watch();
  let lastT = null;
  window.addEventListener("resize", () => {
    const t = getComputedStyle(el).getPropertyValue("--ss-trigger");
    if (t !== lastT) { lastT = t; watch(); }
  });

  // Present mode: deck bar with dots, counter, exit.
  const bar = document.createElement("div");
  bar.className = "ss-deck-bar";
  bar.innerHTML = `<div class="ss-dots" role="tablist"></div><span class="ss-num" aria-live="polite"></span>
    <div class="ss-controls"><button class="ss-btn" data-act="prev" aria-label="Previous">←</button>
    <button class="ss-btn" data-act="next" aria-label="Next">→</button>
    <button class="ss-btn" data-act="exit">Exit · Esc</button></div>`;
  el.append(bar);
  const dotsEl = bar.querySelector(".ss-dots");
  const dots = steps.map((_, k) => {
    const d = document.createElement("button");
    d.setAttribute("aria-label", `Slide ${k + 1}`);
    d.addEventListener("click", () => go(k));
    dotsEl.append(d);
    return d;
  });
  const counter = bar.querySelector(".ss-num");
  bar.addEventListener("click", (e) => {
    const act = e.target.closest("[data-act]")?.dataset.act;
    if (act === "prev") step(-1);
    if (act === "next") step(1);
    if (act === "exit") setMode("read");
  });

  // Only the sequence being presented listens: the others are in read mode.
  // A handled key stops here, so a sequence that has just been handed present mode does not act on the same key press.
  const onKey = (e) => {
    if (mode !== "present") return;
    const keys = { next: ["ArrowRight", "PageDown", " ", "Enter"], prev: ["ArrowLeft", "PageUp", "Backspace"] };
    if (keys.next.includes(e.key)) step(1);
    else if (keys.prev.includes(e.key)) step(-1);
    else if (e.key === "Home") go(0);
    else if (e.key === "End") go(steps.length - 1);
    else if (e.key === "Escape") setMode("read");
    else return;
    e.preventDefault();
    e.stopImmediatePropagation();
  };
  document.addEventListener("keydown", onKey);

  // swipe
  let x0 = null;
  el.addEventListener("touchstart", (e) => (x0 = e.touches[0].clientX), { passive: true });
  el.addEventListener("touchend", (e) => {
    if (mode !== "present" || x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 40) step(dx < 0 ? 1 : -1);
    x0 = null;
  });

  // setMode(m, {at, handoff}): `at` is the step to open on (-1 for the last); `handoff` passes present mode to another
  // sequence without leaving it (the page stays in present mode and full screen, nothing scrolls).
  function setMode(m, { at = current, handoff = false } = {}) {
    if (at === -1) at = steps.length - 1;
    mode = m;
    el.classList.toggle("is-presenting", m === "present");
    if (m === "present") {
      root.setAttribute("data-mode", "present");
      if (!document.fullscreenElement) root.requestFullscreen?.().catch(() => {});
    } else if (!handoff) {
      root.removeAttribute("data-mode");
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      steps[Math.max(at, 0)].scrollIntoView({ block: "center" });
    }
    current = -1;
    go(Math.max(at, 0), false);
    modeSubs.forEach((f) => f(m));
  }
  document.addEventListener("fullscreenchange", () => {
    if (!document.fullscreenElement && mode === "present") setMode("read");
  });

  const modeSubs = new Set();
  go(0, false);
  return {
    go,
    setMode,
    el,
    get length() { return steps.length; },
    get mode() { return mode; },
    get index() { return current; },
    onMode: (f) => modeSubs.add(f),
    rerender: () => render(current, { animate: false, mode }),
  };
}

// ---------------------------------------------------------------- tooltip
export function tooltip() {
  const tip = document.createElement("div");
  tip.className = "ss-tip";
  tip.setAttribute("role", "status");
  document.body.append(tip);
  return {
    show(html, x, y) {
      tip.innerHTML = html;
      const r = tip.getBoundingClientRect();
      const left = Math.min(window.innerWidth - r.width - 12, x + 14);
      const top = y - r.height - 12 < 8 ? y + 16 : y - r.height - 12;
      tip.style.left = `${Math.max(8, left)}px`;
      tip.style.top = `${top}px`;
      tip.style.opacity = 1;
    },
    hide() {
      tip.style.opacity = 0;
    },
  };
}
