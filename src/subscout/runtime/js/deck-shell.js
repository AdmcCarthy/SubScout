// Deck mode: what every page of a deck shares, the colour scheme control.
import { theme, bindSeg } from "./subscout.js";

bindSeg(document.getElementById("ctl-theme"), theme);
