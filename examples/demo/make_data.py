"""Generate the demo story's synthetic data. Not real fields, operators or volumes.

Usage: uv run python examples/demo/make_data.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pandas as pd

OUT = Path(__file__).parent / "data"
rng = random.Random(42)


def profile(peak, start, plateau, decline, years):
    out = []
    for y in years:
        t = y - start
        if t < 0:
            v = 0.0
        elif t < 3:
            v = peak * (0.04 + 0.96 * t / 3)
        elif t < 3 + plateau:
            v = peak
        else:
            v = peak * math.exp(-decline * (t - 3 - plateau))
        out.append(round(v, 2))
    return out


def main() -> None:
    OUT.mkdir(exist_ok=True)
    years = list(range(2000, 2026))
    fields = [  # name, peak (k Sm3 o.e./d), start, plateau years, decline, operator
        ("Field A", 52, 1998, 2, 0.13, "Operator A"),
        ("Field B", 38, 2001, 3, 0.16, "Operator B"),
        ("Field C", 44, 2004, 14, 0.12, "Operator A"),
        ("Field D", 27, 2006, 2, 0.18, "Operator C"),
        ("Field E", 31, 2011, 3, 0.15, "Operator B"),
        ("Field F", 22, 2013, 9, 0.10, "Operator D"),
        ("Field G", 18, 2016, 2, 0.20, "Operator E"),
    ]
    rows, summary = [], []
    for name, peak, start, plateau, decline, op in fields:
        vals = profile(peak, start, plateau, decline, years)
        rows += [{"year": y, "field": name, "kboed": v} for y, v in zip(years, vals, strict=True)]
        summary.append(
            {
                "field": name,
                "operator": op,
                "start": max(start, 2000),
                "peak_kboed": peak,
                "plateau_years": plateau,
                "kboed_2025": vals[-1],
                "cum_msm3": round(sum(vals) * 365 / 1000, 1),
            }
        )
    pd.DataFrame(rows).to_csv(OUT / "production.csv", index=False)
    pd.DataFrame(summary).to_csv(OUT / "fields.csv", index=False)

    decades = ["1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"]
    pd.DataFrame(
        {
            "decade": decades,
            "discoveries": [4, 26, 41, 52, 47, 38, 19],
            "avg_msm3": [410, 230, 96, 47, 30, 22, 15],
        }
    ).to_csv(OUT / "decades.csv", index=False)

    price = {
        2005: 0.8,
        2006: 0.9,
        2007: 1,
        2008: 1.2,
        2009: 0.8,
        2010: 0.95,
        2011: 1.15,
        2012: 1.2,
        2013: 1.18,
        2014: 1.05,
        2015: 0.6,
        2016: 0.5,
        2017: 0.6,
        2018: 0.75,
        2019: 0.8,
        2020: 0.5,
        2021: 0.75,
        2022: 1.1,
        2023: 0.95,
        2024: 0.9,
    }
    wells = [
        {"year": y, "quarter": q, "wells": max(0, round(11 * p * s + rng.gauss(0, 1.2)))}
        for y, p in price.items()
        for q, s in zip(["Q1", "Q2", "Q3", "Q4"], [0.8, 1.05, 1.15, 1.0], strict=True)
    ]
    pd.DataFrame(wells).to_csv(OUT / "wells.csv", index=False)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
