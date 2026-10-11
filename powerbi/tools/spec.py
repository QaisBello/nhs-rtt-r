"""Power BI version of the RTT waiting list project. Run from powerbi/:

    python tools/spec.py        # writes RTT_Waiting_List.pbip and its folders
    python tools/validate.py    # schema and reference checks
    python tools/expected.py    # what the visuals should show, checked against data/clean/summary.json from the R analysis

Medians and 92nd percentiles come from the R cleaning (interpolated within weekly bands, NHS England's method) and are
shown at the grain they were calculated: they cannot be added up, so the model never sums them.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pbikit import C, M, build, card, color, lit, series_colors, slicer, text_box, visual  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "RTT_Waiting_List"
TEAL, ORANGE, GREY, BLUE, INK, PINK = "#0F766E", "#C2410C", "#9AA3A0", "#2443D6", "#13201B", "#C2367A"

TABLES = {
    "England": dict(
        file="england_timeseries.csv",
        description="England each month since August 2007 (NHS England RTT overview time series). Excludes pathways commissioned "
                    "outside England, as NHS England's headline figures do.",
        columns=[("month", "dateTime", {"isKey": True, "formatString": "mmm yyyy"}), ("median_weeks", "double", {"formatString": "0.0"}),
                 ("within_18", "int64", {}), ("pct_within_18", "double", {"isHidden": True}), ("over_18", "int64", {}),
                 ("over_52", "int64", {}), ("over_65", "int64", {}), ("over_78", "int64", {}), ("over_104", "int64", {}),
                 ("waiting", "int64", {}), ("waiting_with_estimates", "int64", {}), ("p92_off_scale", "boolean", {"isHidden": True}),
                 ("p92_weeks", "double", {"formatString": "0.0"})]),
    "Providers": dict(
        file="provider_summary.csv",
        description="Every provider in the August 2026 extract (NHS trusts and independent sector).",
        columns=[("provider_code", "string", {"isKey": True, "isHidden": True}), ("provider", "string", {}),
                 ("waiting", "int64", {"isHidden": True}), ("within_18", "int64", {"isHidden": True}), ("over_52", "int64", {"isHidden": True}),
                 ("over_65", "int64", {"isHidden": True}), ("median_weeks", "double", {"formatString": "0.0"}),
                 ("p92_weeks", "double", {"formatString": "0.0"}), ("pct_within_18", "double", {"isHidden": True}),
                 ("pct_over_52", "double", {"isHidden": True}), ("independent", "boolean", {"isHidden": True}), ("small", "boolean", {"isHidden": True})],
        added=[("Sector", "string", {})],
        m_extra='''
            #"Sector" = Table.AddColumn(#"Filtered Rows", "Sector", each if [independent] then "Independent sector" else "NHS trust", type text)
        ''', m_last="Sector"),
    "Specialties": dict(
        file="specialty_summary.csv", description="Treatment functions, England totals (August 2026).",
        columns=[("specialty_code", "string", {"isKey": True, "isHidden": True}), ("specialty", "string", {}),
                 ("waiting", "int64", {"isHidden": True}), ("within_18", "int64", {"isHidden": True}), ("over_52", "int64", {"isHidden": True}),
                 ("over_65", "int64", {"isHidden": True}), ("median_weeks", "double", {"formatString": "0.0"}),
                 ("p92_weeks", "double", {"formatString": "0.0"}), ("pct_within_18", "double", {"isHidden": True}),
                 ("pct_over_52", "double", {"isHidden": True})]),
    "Waiting by Provider": dict(
        file="provider_specialty.csv",
        description="Pathways waiting by provider and treatment function, August 2026. Includes the 31,049 pathways commissioned outside "
                    "England, so totals here are 0.4% above the England headline.",
        columns=[("provider_code", "string", {"isHidden": True}), ("provider", "string", {"isHidden": True}),
                 ("specialty_code", "string", {"isHidden": True}), ("specialty", "string", {"isHidden": True}),
                 ("waiting", "int64", {}), ("within_18", "int64", {}), ("over_52", "int64", {}), ("over_65", "int64", {}),
                 ("median_weeks", "double", {"isHidden": True}), ("p92_weeks", "double", {"isHidden": True}),
                 ("pct_within_18", "double", {"isHidden": True}), ("pct_over_52", "double", {"isHidden": True})]),
    "Funnel": dict(
        file="funnel_trusts.csv",
        description="The 139 NHS trusts in the funnel plot, with the R analysis's z-scores and bands (binomial and overdispersed).",
        columns=[("provider_code", "string", {"isKey": True, "isHidden": True}), ("provider", "string", {}),
                 ("waiting", "int64", {"isHidden": True}), ("within_18", "int64", {"isHidden": True}), ("over_52", "int64", {"isHidden": True}),
                 ("over_65", "int64", {"isHidden": True}), ("median_weeks", "double", {"formatString": "0.0"}),
                 ("p92_weeks", "double", {"formatString": "0.0"}), ("pct_within_18", "double", {"isHidden": True}),
                 ("pct_over_52", "double", {"isHidden": True}), ("independent", "boolean", {"isHidden": True}), ("small", "boolean", {"isHidden": True}),
                 ("p", "double", {"isHidden": True}), ("z_binomial", "double", {"formatString": "0.0"}),
                 ("z", "double", {"formatString": "0.00"}), ("band", "string", {})]),
}

RELATIONSHIPS = [
    (("Waiting by Provider", "provider_code"), ("Providers", "provider_code"), {}),
    (("Waiting by Provider", "specialty_code"), ("Specialties", "specialty_code"), {}),
]

LATEST = "VAR _last = CALCULATE ( MAX ( England[month] ), REMOVEFILTERS ( England ) )\n"
E, W, F, SP = "England", "Waiting by Provider", "Funnel", "Specialties"
MEASURES = [
    ("Latest Month", E, "England", "mmmm yyyy", "CALCULATE ( MAX ( England[month] ), REMOVEFILTERS ( England ) )", "Latest month of data."),
    ("Waiting List", E, "England", "#,0", "SUM ( England[waiting] )", "Incomplete pathways (people waiting), reported providers only."),
    ("Waiting List with Estimates", E, "England", "#,0", "SUM ( England[waiting_with_estimates] )",
     "Including NHS England's estimates for trusts that did not report."),
    ("% Within 18 Weeks", E, "England", "0.0%", "DIVIDE ( SUM ( England[within_18] ), SUM ( England[waiting] ) )",
     "Share waiting less than 18 weeks (the constitutional standard is 92%)."),
    ("92% Standard", E, "England", "0%", "0.92", "The constitutional standard."),
    ("70% Target", E, "England", "0%", "0.70", "The March 2027 interim target."),
    ("Latest Waiting List", E, "England", "#,0", LATEST + "RETURN CALCULATE ( [Waiting List], REMOVEFILTERS ( England ), England[month] = _last )",
     "Waiting list in the latest month."),
    ("Latest % Within 18 Weeks", E, "England", "0.0%", LATEST + "RETURN CALCULATE ( [% Within 18 Weeks], REMOVEFILTERS ( England ), England[month] = _last )",
     "Share within 18 weeks in the latest month."),
    ("Latest Median Wait", E, "England", "0.0", LATEST + "RETURN CALCULATE ( MAX ( England[median_weeks] ), REMOVEFILTERS ( England ), England[month] = _last )",
     "Median wait in weeks, latest month (interpolated within weekly bands)."),
    ("Latest 92nd Percentile", E, "England", "0.0", LATEST + "RETURN CALCULATE ( MAX ( England[p92_weeks] ), REMOVEFILTERS ( England ), England[month] = _last )",
     "92nd percentile wait in weeks: the standard says 92% should wait less than 18."),
    ("Latest Over 52 Weeks", E, "England", "#,0", LATEST + "RETURN CALCULATE ( SUM ( England[over_52] ), REMOVEFILTERS ( England ), England[month] = _last )",
     "Pathways waiting more than a year."),
    ("Peak Waiting List", E, "England", "#,0", "CALCULATE ( MAX ( England[waiting] ), REMOVEFILTERS ( England ) )", "Largest list on record."),
    ("Peak Month", E, "England", "mmmm yyyy", """VAR _peak = [Peak Waiting List]
RETURN
    CALCULATE ( MAX ( England[month] ), REMOVEFILTERS ( England ), England[waiting] = _peak )""", "Month of the largest list."),
    ("Last Month 92% Was Met", E, "England", "mmmm yyyy",
     "CALCULATE ( MAX ( England[month] ), REMOVEFILTERS ( England ), England[within_18] >= 0.92 * England[waiting] )",
     "The last month England met the 92% standard."),
    ("Gap to 70%", E, "England", '0.0" points"', "100 * ( [70% Target] - [Latest % Within 18 Weeks] )", "Percentage points still to go."),
    ("Pathways", W, "Providers", "#,0", "SUM ( 'Waiting by Provider'[waiting] )", "Pathways waiting (provider extract)."),
    ("Provider % Within 18 Weeks", W, "Providers", "0.0%", "DIVIDE ( SUM ( 'Waiting by Provider'[within_18] ), [Pathways] )",
     "Share within 18 weeks for any provider, specialty or sector in context."),
    ("Provider Over 52 Weeks", W, "Providers", "#,0", "SUM ( 'Waiting by Provider'[over_52] )", "Pathways over a year."),
    ("Share of List", W, "Providers", "0.0%", "DIVIDE ( [Pathways], CALCULATE ( [Pathways], REMOVEFILTERS ( Providers ) ) )",
     "Share of all pathways in the extract (within any specialty filter)."),
    ("Specialty % Within 18 Weeks", SP, "Specialties", "0.0%", "DIVIDE ( SUM ( Specialties[within_18] ), SUM ( Specialties[waiting] ) )",
     "England figure per treatment function (excludes non-English commissioners)."),
    ("Specialty Over 52 Weeks", SP, "Specialties", "#,0", "SUM ( Specialties[over_52] )", "Pathways over a year, by treatment function."),
    ("Funnel List Size", F, "Funnel", "#,0", "SUM ( Funnel[waiting] )", "Trust waiting list (funnel x axis)."),
    ("Funnel % Within 18 Weeks", F, "Funnel", "0.0%", "DIVIDE ( SUM ( Funnel[within_18] ), SUM ( Funnel[waiting] ) )", "Trust performance (funnel y axis)."),
    ("Trusts Better Than Chance", F, "Funnel", "#,0", 'CALCULATE ( COUNTROWS ( Funnel ), Funnel[band] = "Above 99.8% limit" )',
     "Above the overdispersed 99.8% limit."),
    ("Trusts Worse Than Chance", F, "Funnel", "#,0", 'CALCULATE ( COUNTROWS ( Funnel ), Funnel[band] = "Below 99.8% limit" )',
     "Below the overdispersed 99.8% limit."),
    ("Binomial Outliers", F, "Funnel", "#,0", "CALCULATE ( COUNTROWS ( Funnel ), ABS ( Funnel[z_binomial] ) > 3.09 )",
     "Trusts outside plain binomial 99.8% limits: nearly all of them, which is why overdispersion matters."),
]

p1, p2, p3 = "england", "providers", "funnel"
pct, std, tgt = M(E, "% Within 18 Weeks", "Within 18 weeks"), M(E, "92% Standard", "92% standard"), M(E, "70% Target", "70% target")
wl, wle = M(E, "Waiting List", "Waiting list"), M(E, "Waiting List with Estimates", "With estimates")
PAGES = [
    (p1, "England", [
        text_box(p1, "title", 24, 12, 1232, 52, "England's waiting list (Referral to Treatment), August 2007 to August 2026", 18),
        card(p1, "wl", 24, 76, 236, 96, M(E, "Latest Waiting List", "Waiting, Aug 2026")),
        card(p1, "pct", 272, 76, 236, 96, M(E, "Latest % Within 18 Weeks", "Within 18 weeks")),
        card(p1, "med", 520, 76, 236, 96, M(E, "Latest Median Wait", "Median wait (weeks)")),
        card(p1, "p92", 768, 76, 236, 96, M(E, "Latest 92nd Percentile", "92nd percentile (weeks)")),
        card(p1, "o52", 1016, 76, 240, 96, M(E, "Latest Over 52 Weeks", "Waiting over a year")),
        visual(p1, "list", "lineChart", 24, 184, 610, 400, {"Category": [C(E, "month", "Month")], "Y": [wl, wle]},
               "People waiting", objects={"dataPoint": series_colors([wl, wle], [INK, GREY])}, z=10),
        visual(p1, "pctline", "lineChart", 646, 184, 610, 400, {"Category": [C(E, "month", "Month")], "Y": [pct, std, tgt]},
               "Share within 18 weeks, against the 92% standard and the 70% target",
               objects={"dataPoint": series_colors([pct, std, tgt], [PINK, ORANGE, BLUE])}, z=11),
        card(p1, "peak", 24, 596, 400, 112, M(E, "Peak Month", "Largest list on record")),
        card(p1, "met", 436, 596, 400, 112, M(E, "Last Month 92% Was Met", "Last time 92% was met")),
        card(p1, "gap", 848, 596, 408, 112, M(E, "Gap to 70%", "Still to go to 70%")),
    ]),
    (p2, "Specialties and providers", [
        text_box(p2, "title", 24, 12, 860, 52, "Who waits longest: specialties and providers, August 2026", 18),
        slicer(p2, "sector", 900, 8, 356, 64, C("Providers", "Sector"), None),
        visual(p2, "spec", "clusteredBarChart", 24, 76, 560, 632,
               {"Category": [C(SP, "specialty", "Specialty")], "Y": [M(SP, "Specialty % Within 18 Weeks", "Within 18 weeks")]},
               "Share within 18 weeks by specialty (England)", objects={"dataPoint": [{"properties": {"fill": color(PINK)}}],
                                                                          "labels": [{"properties": {"show": lit(True)}}]},
               sort=(M(SP, "Specialty % Within 18 Weeks"), "Ascending"), z=10),
        visual(p2, "prov", "tableEx", 600, 76, 656, 632,
               {"Values": [C("Providers", "provider", "Provider"), C("Providers", "Sector"), M(W, "Pathways", "Waiting"),
                           M(W, "Share of List", "Share"), M(W, "Provider % Within 18 Weeks", "Within 18 wks"),
                           M(W, "Provider Over 52 Weeks", "Over 52 wks")]},
               "Providers, largest lists first (click a specialty bar to filter)", sort=(M(W, "Pathways"), "Descending"), z=11),
    ]),
    (p3, "Funnel plot", [
        text_box(p3, "title", 24, 12, 1232, 52, "Which trusts are really different? 139 NHS trusts, overdispersed funnel (from the R analysis)", 18),
        card(p3, "binom", 24, 76, 400, 96, M(F, "Binomial Outliers", "Outliers on plain binomial limits")),
        card(p3, "better", 436, 76, 400, 96, M(F, "Trusts Better Than Chance", "Better than chance (overdispersed)")),
        card(p3, "worse", 848, 76, 408, 96, M(F, "Trusts Worse Than Chance", "Worse than chance (overdispersed)")),
        visual(p3, "scatter", "scatterChart", 24, 184, 760, 524,
               {"Category": [C(F, "provider", "Trust")], "Series": [C(F, "band", "Band")],
                "X": [M(F, "Funnel List Size", "Waiting list")], "Y": [M(F, "Funnel % Within 18 Weeks", "Within 18 weeks")]},
               "Trust size against performance, coloured by funnel band", z=10),
        visual(p3, "table", "tableEx", 800, 184, 456, 524,
               {"Values": [C(F, "provider", "Trust"), C(F, "band", "Band"), M(F, "Funnel % Within 18 Weeks", "Within 18"), C(F, "z", "z (overdispersed)")]},
               "Trusts and their z-scores", sort=(C(F, "z"), "Descending"), z=11),
    ]),
]

SPEC = dict(name=NAME, root=ROOT, tables=TABLES, measures=MEASURES, relationships=RELATIONSHIPS, pages=PAGES,
            base_url="https://raw.githubusercontent.com/QaisBello/nhs-rtt-r/main/data/clean/",
            base_desc="Folder of cleaned CSVs from this repo (data/clean). Point it at a local folder or another branch to test.")

if __name__ == "__main__":
    build(SPEC)
