"""results/method_comparison.md: one row per method from its standard protocol run.

Reads methods/*/results/[<detector>/]<[protocol] results_dir>/protocol.json and the main rule's saved
outputs (our matching rule, the protocol route). Run at the end of every protocol run.

Usage: python -m common.evaluation.method_comparison   (from replication/)
"""
import json

import pandas as pd

from . import REPO, load_config
from .report import GROUPS, md_table, write_ascii

OUT = REPO / "results"


def rows(cfg):
    rd = cfg["protocol"]["results_dir"]
    out = []
    found = REPO.glob(f"methods/*/results/{rd}/protocol.json")
    found = [*found, *REPO.glob(f"methods/*/results/*/{rd}/protocol.json")]
    for pj in sorted(found):
        meta = json.loads(pj.read_text())
        rule, mr, route = meta["main_rule"], meta["matching_rule"], meta["routes"][0]
        d = pj.parent / rule
        s = pd.read_csv(d / "summary.csv")
        s = s[(s.rule == mr) & (s.route == route)].set_index("stratum")
        a = pd.read_csv(d / "recovery_agreement.csv")
        a = a[(a.rule == mr) & (a.route == route) & (a.stratum == "overall")
              & (a.feature == "recovery_time_min")].iloc[0]
        o = s.loc["overall"]
        sens = [s.loc[g, "sensitivity"] for g in GROUPS]
        out.append(dict(method=meta["method"], title=meta["title"], date=meta["date"], rule=rule,
                        note=meta.get("comparison_note", ""),
                        route=route, participants=int(o.participants), days=int(o.days),
                        sensitivity=o.sensitivity, precision=o.precision, F2=o.F2,
                        FP_per_day=o.FP_per_day, delay_median=o.delay_median,
                        sens_range_pp=100 * (max(sens) - min(sens)),
                        recovery_time_ICC=a.ICC_A1, recovery_time_n=int(a.n),
                        readme=str((pj.parent / "README.md").relative_to(REPO))))
    return pd.DataFrame(out)


def write(cfg=None):
    cfg = cfg or load_config()
    df = rows(cfg)
    OUT.mkdir(exist_ok=True)
    df.round(4).to_csv(OUT / "method_comparison.csv", index=False)
    rd, pc = cfg["protocol"]["results_dir"], cfg["protocol"]
    L = ["# Method comparison (standard protocol)", "",
         f"One row per method. Protocol {rd}: main adjacent rule {pc['adjacent_rules'][0]}, "
         f"Route {pc['routes'][0]}, our matching rule (-30 to +120 min), test data (5 held-out folds pooled). "
         "CIs and all other rules are in each method README.", ""]
    if len(df):
        t = pd.DataFrame({
            "Method": [f"[{r.title}]({'../' + r.readme})" for r in df.itertuples()],
            "Sens %": (100 * df.sensitivity).map("{:.1f}".format),
            "Prec %": (100 * df.precision).map("{:.1f}".format),
            "F2": df.F2.map("{:.3f}".format),
            "FP/day": df.FP_per_day.map("{:.2f}".format),
            "Delay median (min)": df.delay_median.map("{:.0f}".format),
            "Sens range (pp)": df.sens_range_pp.map("{:.1f}".format),
            "Recovery-time ICC": df.recovery_time_ICC.map("{:.2f}".format)})
        L += md_table(t, list(t.columns))
        L += ["", "Sens range = max minus min sensitivity across healthy, prediabetes and T2D. "
              "Recovery-time ICC = ICC(A,1), detector vs logged-meal anchor, excursion segmentation.", "",
              "Run dates: " + "; ".join(f"{r.method} {r.date}" for r in df.itertuples()) + "."]
        notes = [f"- {r.title}: {r.note}" for r in df.itertuples() if r.note]
        if notes:
            L += ["", "Notes:", ""] + notes
    else:
        L.append("No method has a protocol run yet.")
    L += ["", "With 95 % CIs, the comparison with Hochsmann 2026, grid boundary hits and findings: "
          "`docs/results_summary.md`.",
          "", "Rebuilt by `common/run_protocol.py` at the end of every method run."]
    write_ascii(OUT / "method_comparison.md", "\n".join(L) + "\n")
    print(f"wrote {(OUT / 'method_comparison.md').relative_to(REPO)} ({len(df)} methods)")
    return df


if __name__ == "__main__":
    write()
