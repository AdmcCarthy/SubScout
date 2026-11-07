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

/** Read a colour token, e.g. token("data-context"). */
export const token = (name) => getComputedStyle(root).getPropertyValue(`--ss-${name}`).trim();

// ---------------------------------------------------------------- simple observable prefs
function pref(key, attr, fallback, onApply) {
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
export const surfaceOption = pref("surface", "data-surface", "baseline");

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
 * story(el, {render}) wires one .ss-story: .ss-steps > .ss-step (one state each) and .ss-graphic.
 * render(index, {animate, mode}) is called on every state change, in either mode.
 */
export function story(el, { render }) {
  const steps = [...el.querySelectorAll(".ss-step")];
  let current = -1;
  let mode = "read";

  const go = (i, animate = true) => {
    i = Math.max(0, Math.min(steps.length - 1, i));
    if (i === current) return;
    current = i;
    steps.forEach((s, k) => s.classList.toggle("is-active", k === i));
    dots.forEach((d, k) => d.setAttribute("aria-current", String(k === i)));
    if (counter) counter.textContent = `${i + 1} / ${steps.length}`;
    render(i, { animate: animate && !reducedMotion(), mode });
  };

  // Read mode: the step crossing the viewport middle is active.
  const io = new IntersectionObserver(
    (entries) => {
      if (mode !== "read") return;
      entries.forEach((en) => en.isIntersecting && go(steps.indexOf(en.target)));
    },
    { rootMargin: "-50% 0px -50% 0px" },
  );
  steps.forEach((s) => io.observe(s));

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
    if (act === "prev") go(current - 1);
    if (act === "next") go(current + 1);
    if (act === "exit") setMode("read");
  });

  const onKey = (e) => {
    if (mode !== "present") return;
    if (["ArrowRight", "PageDown", " ", "Enter"].includes(e.key)) { e.preventDefault(); go(current + 1); }
    if (["ArrowLeft", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); go(current - 1); }
    if (e.key === "Home") go(0);
    if (e.key === "End") go(steps.length - 1);
    if (e.key === "Escape") setMode("read");
  };
  document.addEventListener("keydown", onKey);

  // swipe
  let x0 = null;
  el.addEventListener("touchstart", (e) => (x0 = e.touches[0].clientX), { passive: true });
  el.addEventListener("touchend", (e) => {
    if (mode !== "present" || x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 40) go(current + (dx < 0 ? 1 : -1));
    x0 = null;
  });

  function setMode(m) {
    const at = current;
    mode = m;
    if (m === "present") {
      root.setAttribute("data-mode", "present");
      el.requestFullscreen?.().catch(() => {});
    } else {
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
