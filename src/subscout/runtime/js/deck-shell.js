// Deck mode: what every page of a deck shares: the colour scheme control and the drawing style.
import { theme, drawing, bindSeg } from "./subscout.js";

bindSeg(document.getElementById("ctl-theme"), theme);

// Pencil: every figure is redrawn as graphite on paper. The filter wobbles each line and breaks it and the fills
// into fine strokes; the palette is set in deck.css. Paper is light, so the page is held in the light scheme.
const FILTER = `<svg width="0" height="0" style="position:absolute" aria-hidden="true"><filter id="ss-pencil" x="-3%" y="-3%" width="106%" height="106%" color-interpolation-filters="sRGB"><feTurbulence type="fractalNoise" baseFrequency="0.028" numOctaves="2" seed="4" result="slow"/><feDisplacementMap in="SourceGraphic" in2="slow" scale="2.6" xChannelSelector="R" yChannelSelector="G" result="wob"/><feTurbulence type="fractalNoise" baseFrequency="0.55 0.045" numOctaves="2" seed="11" result="grain"/><feColorMatrix in="grain" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  2.6 0 0 0 -0.62" result="strokes"/><feComposite in="wob" in2="strokes" operator="in" result="drawn"/><feComponentTransfer in="wob" result="wash"><feFuncA type="linear" slope="0.5"/></feComponentTransfer><feMerge><feMergeNode in="wash"/><feMergeNode in="drawn"/></feMerge></filter></svg>`;
const seg = document.getElementById("ctl-drawing");
if (seg) {
  document.body.insertAdjacentHTML("beforeend", FILTER);
  bindSeg(seg, drawing);
  const paper = () => (drawing.get() === "pencil" ? document.documentElement.setAttribute("data-colour-scheme", "light") : theme.set(theme.get()));
  drawing.subscribe(paper);
  theme.subscribe(() => drawing.get() === "pencil" && document.documentElement.setAttribute("data-colour-scheme", "light"));
  if (drawing.get() === "pencil") paper();
}
