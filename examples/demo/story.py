"""Metrics and derived datasets for the demo story (synthetic data)."""

from subscout import metric


def datasets(d):
    f = d["fields"]
    return {
        "late_plateau": f.assign(share=lambda x: x.plateau_years / x.plateau_years.max()),
    }


def metrics(d):
    f, p, dec, w = d["fields"], d["production"], d["decades"], d["wells"]
    best = f.loc[f.plateau_years.idxmax()]
    peak_dec = dec.loc[dec.discoveries.idxmax()]
    total_2025 = p[p.year == 2025].kboed.sum()
    c_2025 = p[(p.year == 2025) & (p.field == best.field)].kboed.sum()
    trough = w[w.year.isin([2015, 2016])].wells.sum() / 8
    boom = w[w.year.isin([2011, 2012, 2013])].wells.sum() / 12
    return {
        "n_fields": metric(len(f), "Count of fields in the dataset", "synthetic", "observed"),
        "longest_plateau": metric(
            int(best.plateau_years), f"Plateau length of {best.field}, years", "synthetic", "derived", "years"
        ),
        "typical_plateau": metric(
            float(f.plateau_years.median()),
            "Median plateau length across fields, years",
            "synthetic",
            "derived",
            "years",
        ),
        "share_2025_c": metric(
            c_2025 / total_2025, f"{best.field}'s share of 2025 production", "synthetic", "derived"
        ),
        "peak_decade_finds": metric(
            int(peak_dec.discoveries), f"Discoveries in the {peak_dec.decade}", "synthetic", "observed"
        ),
        "size_drop": metric(
            float(dec.avg_msm3.iloc[0] / dec.avg_msm3.iloc[-1]),
            "Average find size, 1960s ÷ 2020s",
            "synthetic",
            "derived",
        ),
        "avg_2020s": metric(
            float(dec.avg_msm3.iloc[-1]) * 1e6,
            "Average discovery size in the 2020s, Sm³ o.e.",
            "synthetic",
            "interpreted",
            "Sm³ o.e.",
        ),
        "wells_drop": metric(
            1 - trough / boom,
            "Fall in quarterly wells, 2011–13 average to 2015–16 average",
            "synthetic",
            "derived",
        ),
    }
