"""What the Power BI report should show, recomputed in pandas and checked against the R analysis (data/clean/summary.json).
Run from powerbi/:

    python tools/expected.py        # writes docs/expected_values.md; exit code 1 on any disagreement
"""
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(os.path.dirname(ROOT), "data", "clean")
S = json.load(open(os.path.join(CLEAN, "summary.json")))
e = pd.read_csv(os.path.join(CLEAN, "england_timeseries.csv"), parse_dates=["month"])
sp = pd.read_csv(os.path.join(CLEAN, "specialty_summary.csv"))
ps = pd.read_csv(os.path.join(CLEAN, "provider_specialty.csv"))
pv = pd.read_csv(os.path.join(CLEAN, "provider_summary.csv"))
f = pd.read_csv(os.path.join(CLEAN, "funnel_trusts.csv"))
problems = []


def check(label, got, want, tol=0):
    ok = abs(got - want) <= tol
    print(("PASS " if ok else "FAIL ") + f"{label}: {got} vs R {want}")
    if not ok:
        problems.append(label)


last = e.iloc[-1]
pct = last.within_18 / last.waiting
check("Waiting list", int(last.waiting), S["waiting"])
check("% within 18 weeks", round(100 * pct, 1), S["pct_within_18"])
check("Median weeks", round(last.median_weeks, 1), S["median_weeks"])
check("92nd percentile", round(last.p92_weeks, 1), S["p92_weeks"])
check("Over 52 weeks", int(last.over_52), S["over_52"])
peak = e.loc[e.waiting.idxmax()]
check("Peak waiting list", int(peak.waiting), S["peak_waiting"])
met = e[e.within_18 >= 0.92 * e.waiting].month.max()
check("Last month 92% met", met.strftime("%B %Y") == S["last_met_92"], True)
check("Better than chance", int((f.band == "Above 99.8% limit").sum()), S["trusts_above_998"])
check("Worse than chance", int((f.band == "Below 99.8% limit").sum()), S["trusts_below_998"])
check("Binomial outliers (|z| > 3.09)", int((f.z_binomial.abs() > 3.09).sum()), S["trusts_outside_binomial"])
worst = sp.assign(p=sp.within_18 / sp.waiting).sort_values("p").iloc[0]
check("Worst specialty", worst.specialty == S["worst_specialty"], True)
gap_nonc = ps.waiting.sum() - last.waiting

lines = ["# Expected values", "", "From `tools/expected.py`: recomputed in pandas and checked against the R analysis (`data/clean/summary.json`): "
         f"**{'all agree' if not problems else 'DISAGREEMENTS: ' + ', '.join(problems)}**.", "",
         "## Page 1 cards", "", "| Card | Expected |", "|---|---:|",
         f"| Waiting, Aug 2026 | {last.waiting:,.0f} |", f"| Within 18 weeks | {pct:.1%} |", f"| Median wait (weeks) | {last.median_weeks:.1f} |",
         f"| 92nd percentile (weeks) | {last.p92_weeks:.1f} |", f"| Waiting over a year | {last.over_52:,.0f} |",
         f"| Largest list on record | {peak.month:%B %Y} |", f"| Last time 92% was met | {met:%B %Y} |", f"| Still to go to 70% | {100 * (0.70 - pct):.1f} points |",
         "", "## Page 2", "",
         f"The provider table totals **{ps.waiting.sum():,}** pathways: {gap_nonc:,} more than the England headline, because the provider "
         "extract includes pathways commissioned outside England.", "",
         "Five lowest specialties:", "", "| Specialty | Within 18 weeks |", "|---|---:|"]
lines += [f"| {r.specialty} | {r.within_18 / r.waiting:.1%} |" for r in sp.assign(p=sp.within_18 / sp.waiting).sort_values("p").head(5).itertuples()]
g = pv.assign(sector=pv.independent.map({True: "Independent sector", False: "NHS trust"})).groupby("sector")[["waiting", "within_18"]].sum()
lines += ["", "| Sector | Pathways | Within 18 weeks |", "|---|---:|---:|"]
lines += [f"| {k} | {r.waiting:,} | {r.within_18 / r.waiting:.1%} |" for k, r in g.iterrows()]
lines += ["", "## Page 3 cards", "", "| Card | Expected |", "|---|---:|",
          f"| Outliers on plain binomial limits | {(f.z_binomial.abs() > 3.09).sum()} |",
          f"| Better than chance | {(f.band == 'Above 99.8% limit').sum()} |", f"| Worse than chance | {(f.band == 'Below 99.8% limit').sum()} |"]
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
open(os.path.join(ROOT, "docs", "expected_values.md"), "w").write("\n".join(lines) + "\n")
sys.exit(1 if problems else 0)
