# data/raw -> data/clean, logging every check to data/clean/data_quality_log.csv
# Run from the repo root:  Rscript scripts/01_clean.R

source("R/rtt.R")
dir.create("data/clean", showWarnings = FALSE)
log <- list()
note <- function(source, check, rows, finding, action) {
  log[[length(log) + 1]] <<- tibble(source = source, check = check, rows_affected = rows, finding = finding, action = action)
}

# ---------------------------------------------------------------- time series
ts_path <- list.files("data/raw", pattern = "^RTT-Overview-Timeseries.*\\.xlsx$", full.names = TRUE)[1]
ts <- read_timeseries(ts_path)
note("timeseries", "Months read", nrow(ts), sprintf("%s to %s", format(min(ts$month), "%b %Y"), format(max(ts$month), "%b %Y")),
     "One row per month; title block, two-row header and footnotes dropped")
note("timeseries", "Not collected ('-')", sum(is.na(ts$over_65)),
     "Waits over 65, 78 and 104 weeks were not collected in early years", "Kept as missing, not zero")
note("timeseries", "92nd percentile off the scale ('52+')", sum(ts$p92_off_scale),
     "Early months record the 92nd percentile as text '52+'", "Set to missing with a flag column")
note("timeseries", "Mislabelled column", nrow(ts),
     "'Total waiting (mil)' holds counts of pathways, not millions", "Read as a count")
write_csv(ts, "data/clean/england_timeseries.csv")

# ---------------------------------------------------------------- the August extract
zip_path <- list.files("data/raw", pattern = "^Full-CSV.*\\.zip$", full.names = TRUE)[1]
d <- read_extract(zip_path)
note("extract", "Rows read", nrow(d), sprintf("%s rows, %d columns, period %s", format(nrow(d), big.mark = ","), ncol(d), unique(d$Period)), "-")
wl <- waiting_list(d)
note("extract", "Incomplete pathways", nrow(wl), "Part 2 rows: people still waiting (other parts are completed pathways and new referrals)", "Kept")
b <- band_cols(wl)
stopifnot(length(b) == 105)
note("extract", "Weekly bands", length(b), "0-1 weeks to 103-104 weeks, then 104+", "Summed per group; percentiles interpolated within bands")
note("extract", "Empty 'Total' column", sum(is.na(wl$Total)), "Part 2 leaves 'Total' blank; 'Total All' holds the row total", "Totals recomputed from the bands")
stopifnot(all(abs(rowSums(wl[b], na.rm = TRUE) - wl$`Total All`) < 1e-9))

tot <- wl |> filter(specialty_code == "C_999")
spec <- wl |> filter(specialty_code != "C_999")
note("extract", "Specialty 'Total' rows", nrow(tot), "Each provider-commissioner pair has a 'Total' row (C_999) as well as its specialty rows",
     "Totals used for England and trust figures; specialty rows for specialty figures, so nothing is counted twice")
stopifnot(abs(sum(tot$`Total All`) - sum(spec$`Total All`)) < 1)

nonc <- tot |> filter(commissioner_code == "NONC")
note("extract", "Non-English commissioners (NONC)", sum(nonc$`Total All`),
     "Patients treated in England but commissioned elsewhere (e.g. Wales)",
     "Excluded from England figures (commissioner basis, as published); kept in trust figures (provider basis)")

eng <- summarise_waits(tot |> filter(commissioner_code != "NONC"))
pub <- ts |> filter(month == max(month))
ok <- abs(eng$waiting - pub$waiting) == 0 && abs(eng$median_weeks - pub$median_weeks) < 0.05 &&
  abs(eng$p92_weeks - pub$p92_weeks) < 0.05 && abs(eng$over_52 - pub$over_52) == 0
note("reconciliation", "England, August 2026", 1,
     sprintf("Extract: %s waiting, median %.2f, 92nd %.2f, %s over 52 weeks. Published: %s, %.2f, %.2f, %s",
             format(eng$waiting, big.mark = ","), eng$median_weeks, eng$p92_weeks, format(eng$over_52, big.mark = ","),
             format(pub$waiting, big.mark = ","), pub$median_weeks, pub$p92_weeks, format(pub$over_52, big.mark = ",")),
     if (ok) "Matches" else "Investigate")

specialty <- summarise_waits(spec |> filter(commissioner_code != "NONC"), specialty_code, specialty) |> arrange(desc(waiting))
write_csv(specialty, "data/clean/specialty_summary.csv")

provider <- summarise_waits(tot, provider_code, provider) |> arrange(desc(waiting))
small <- provider$waiting < 500
note("extract", "Small providers", sum(small), "Providers with fewer than 500 people waiting (mostly independent sector clinics)",
     "Kept in the data; left out of the funnel plot, where tiny lists dominate the scale")
provider <- provider |> mutate(independent = !str_detect(provider, "NHS"), small = small)
write_csv(provider, "data/clean/provider_summary.csv")

ps <- summarise_waits(spec, provider_code, provider, specialty_code, specialty)
write_csv(ps, "data/clean/provider_specialty.csv")
note("output", "Clean tables", 4, "england_timeseries, specialty_summary, provider_summary, provider_specialty", "Written to data/clean")

bind_rows(log) |> write_csv("data/clean/data_quality_log.csv")
print(bind_rows(log), n = 50, width = 200)
