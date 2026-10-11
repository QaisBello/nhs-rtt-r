# data/clean -> headline figures (data/clean/summary.json) and the funnel-plot table
# Run from the repo root:  Rscript scripts/02_analyse.R

source("R/rtt.R")
library(jsonlite)

ts <- read_csv("data/clean/england_timeseries.csv", show_col_types = FALSE)
spec <- read_csv("data/clean/specialty_summary.csv", show_col_types = FALSE)
prov <- read_csv("data/clean/provider_summary.csv", show_col_types = FALSE)

latest <- ts |> filter(month == max(month))
last_met <- ts |> filter(pct_within_18 >= 92) |> filter(month == max(month))
peak <- ts |> filter(waiting == max(waiting))
pre_covid <- ts |> filter(month == as.Date("2020-02-01"))

# funnel plot: NHS trusts with 500+ waiting, % within 18 weeks against list size
nhs <- prov |> filter(!independent, !small)
fo <- funnel_overdispersed(nhs$within_18, nhs$waiting)
p0 <- fo$p0
funnel <- nhs |>
  mutate(p = within_18 / waiting,
         z_binomial = (p - p0) / sqrt(p0 * (1 - p0) / waiting),
         z = fo$z_adj,
         band = case_when(z > 3.09 ~ "Above 99.8% limit", z < -3.09 ~ "Below 99.8% limit",
                          abs(z) > 1.96 ~ "Outside 95% limit", TRUE ~ "Within limits"))
write_csv(funnel, "data/clean/funnel_trusts.csv")

ind <- prov |> filter(independent, !small)
named <- spec |> filter(waiting >= 50000, !str_starts(specialty, "Other"))
worst_spec <- named |> arrange(pct_within_18) |> slice(1)
best_spec <- named |> arrange(desc(pct_within_18)) |> slice(1)

summary <- list(
  month = format(latest$month, "%B %Y"),
  waiting = latest$waiting, waiting_with_estimates = latest$waiting_with_estimates,
  pct_within_18 = round(latest$pct_within_18, 1), median_weeks = round(latest$median_weeks, 1),
  p92_weeks = round(latest$p92_weeks, 1), over_52 = latest$over_52, over_65 = latest$over_65,
  last_met_92 = format(last_met$month, "%B %Y"), last_met_waiting = last_met$waiting,
  peak_month = format(peak$month, "%B %Y"), peak_waiting = peak$waiting,
  pre_covid_waiting = pre_covid$waiting,
  trusts = nrow(nhs), national_rate = round(100 * p0, 1),
  trusts_above_998 = sum(funnel$band == "Above 99.8% limit"), trusts_below_998 = sum(funnel$band == "Below 99.8% limit"),
  trusts_within_95 = sum(funnel$band == "Within limits"),
  trusts_outside_binomial = sum(abs(funnel$z_binomial) > 3.09),
  overdispersion_phi = round(fo$phi, 1), tau = round(100 * sqrt(fo$tau2), 1),
  trusts_at_65 = sum(funnel$p >= 0.65), trusts_at_70 = sum(funnel$p >= 0.70),
  worst_specialty = worst_spec$specialty, worst_specialty_pct = round(worst_spec$pct_within_18, 1),
  best_specialty = best_spec$specialty, best_specialty_pct = round(best_spec$pct_within_18, 1),
  independent_pct = round(100 * sum(ind$within_18) / sum(ind$waiting), 1),
  nhs_pct = round(100 * p0, 1), independent_share = round(100 * sum(ind$waiting) / sum(prov$waiting), 1)
)
write_json(summary, "data/clean/summary.json", auto_unbox = TRUE, pretty = TRUE)
print(toJSON(summary, auto_unbox = TRUE, pretty = TRUE))
