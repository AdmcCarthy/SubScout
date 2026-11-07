// Synthetic, illustrative data for the Compare page. Not real fields, operators or volumes.
// Deterministic (seeded) so screenshots and reviews are stable.

const rng = d3.randomLcg(42);
const normal = d3.randomNormal.source(rng)(0, 1);

// Production profiles, thousand Sm³ o.e. per day
const years = d3.range(2000, 2026);
const prof = (peak, start, plateau, decline) => years.map((y) => {
  const t = y - start;
  if (t < 0) return 0;
  if (t < 3) return peak * (0.04 + 0.96 * (t / 3));
  if (t < 3 + plateau) return peak;
  return peak * Math.exp(-decline * (t - 3 - plateau));
});
export const production = {
  x: years,
  series: [
    { name: "Field A", vals: prof(52, 1998, 2, 0.13) },
    { name: "Field B", vals: prof(38, 2001, 3, 0.16) },
    { name: "Field C", vals: prof(44, 2004, 14, 0.12) },
    { name: "Field D", vals: prof(27, 2006, 2, 0.18) },
    { name: "Field E", vals: prof(31, 2011, 3, 0.15) },
    { name: "Field F", vals: prof(22, 2013, 9, 0.1) },
    { name: "Field G", vals: prof(18, 2016, 2, 0.2) },
  ],
};

// Production by operator, thousand Sm³ o.e. per day; largest first
const opYears = d3.range(2016, 2026).map(String);
const op = (base, trend) => opYears.map((_, i) => Math.max(1, base * (1 + trend * i) + normal() * base * 0.04));
export const byOperator = {
  x: opYears,
  series: [
    { name: "Operator A", vals: op(120, 0.01) },
    { name: "Operator B", vals: op(64, 0.04) },
    { name: "Operator C", vals: op(41, 0.02) },
    { name: "Operator D", vals: op(28, -0.02) },
    { name: "Operator E", vals: op(19, 0.05) },
    { name: "Operator F", vals: op(9, 0.0) },
    { name: "Operator G", vals: op(6, 0.03) },
  ],
};

// Discoveries: year, basin, size (million Sm³ o.e.)
const trees = ["Alder", "Birch", "Cedar", "Damson", "Elder", "Fir", "Gean", "Hazel", "Ivy", "Juniper", "Larch", "Maple",
  "Nettle", "Oak", "Pine", "Quince", "Rowan", "Sorrel", "Teak", "Upas", "Vetch", "Willow", "Yew", "Zelkova"];
export const basins = ["North Sea", "Norwegian Sea", "Barents Sea"];
export const discoveries = d3.range(64).map((i) => {
  const basin = i < 34 ? "North Sea" : i < 52 ? "Norwegian Sea" : "Barents Sea";
  const start = { "North Sea": 1967, "Norwegian Sea": 1981, "Barents Sea": 1984 }[basin];
  const year = Math.round(start + rng() * (2024 - start));
  const age = (year - 1965) / 60;
  const size = Math.max(2, Math.exp(5.4 - 3.3 * age + normal() * 0.8));
  return { name: `${trees[i % trees.length]}${i >= trees.length ? " " + (Math.floor(i / trees.length) + 1) : ""}`, year, group: basin, size, jit: rng() * 2 - 1 };
});
export const biggest = [...discoveries].sort((a, b) => b.size - a.size).slice(0, 3).map((d) => d.name);

// Exploration wells per quarter
const wy = d3.range(2005, 2025);
const price = { 2005: 0.8, 2006: 0.9, 2007: 1, 2008: 1.2, 2009: 0.8, 2010: 0.95, 2011: 1.15, 2012: 1.2, 2013: 1.18, 2014: 1.05,
  2015: 0.6, 2016: 0.5, 2017: 0.6, 2018: 0.75, 2019: 0.8, 2020: 0.5, 2021: 0.75, 2022: 1.1, 2023: 0.95, 2024: 0.9 };
export const wells = {
  cols: wy.map(String),
  rows: ["Q1", "Q2", "Q3", "Q4"],
  vals: [0.8, 1.05, 1.15, 1.0].map((season) => wy.map((y) => Math.max(0, Math.round(11 * price[y] * season + normal() * 1.2)))),
};

// Change in remaining resources vs previous year, %
export const revisions = [
  { name: "North Sea north", val: -6.8 }, { name: "North Sea central", val: 3.4 }, { name: "North Sea south", val: -11.2 },
  { name: "Norwegian Sea north", val: 8.6 }, { name: "Norwegian Sea south", val: -2.1 }, { name: "Barents Sea west", val: 5.2 },
  { name: "Barents Sea east", val: 1.1 },
];
