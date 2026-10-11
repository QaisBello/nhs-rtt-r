# Functions for cleaning and summarising NHS England Referral to Treatment (RTT) waiting times.
# Sourced by scripts/01_clean.R, scripts/02_analyse.R, the report and the tests.

suppressPackageStartupMessages({
  library(dplyr)
  library(tidyr)
  library(readr)
  library(readxl)
  library(stringr)
})

# ---------------------------------------------------------------- waiting time percentiles from weekly bands
# The extract counts patients in one-week bands (0-1, 1-2, ... 103-104 weeks, then 104+).
# NHS England estimates the median and 92nd percentile by assuming waits are spread evenly within a band
# and interpolating. `counts` is a numeric vector of length 105 in band order.
wait_percentile <- function(counts, p) {
  counts[is.na(counts)] <- 0
  n <- sum(counts)
  if (n == 0) return(NA_real_)
  target <- p * n
  cum <- cumsum(counts)
  i <- which(cum >= target)[1]                     # band holding the target patient
  before <- if (i == 1) 0 else cum[i - 1]
  lower <- i - 1                                   # band i covers (i-1, i] weeks
  if (i == length(counts)) return(lower)           # open-ended 104+ band: report its lower bound
  lower + (target - before) / counts[i]
}

# ---------------------------------------------------------------- the monthly time series (Excel)
# The overview workbook has a title block, a two-row header (group + measure), a year column that is only filled
# on the first month of each financial year, "-" for "not collected", "52+" where the 92nd percentile was off the
# scale, and footnotes under the table. This returns one tidy row per month.
read_timeseries <- function(path) {
  raw <- read_excel(path, sheet = 1, col_names = FALSE, .name_repair = "minimal")
  raw <- as.data.frame(raw)
  # readxl drops the empty rows above the table, so find the measure header row by its content
  hr <- which(apply(raw, 1, function(r) any(r %in% "Median wait (weeks)")))[1]
  head2 <- as.character(unlist(raw[hr, ]))
  # columns are found by header text (the first block of measures is incomplete pathways), not position
  j <- function(label) {
    k <- which(head2 == label)[1]
    if (is.na(k)) stop("column not found: ", label)
    k
  }
  mcol <- j("Median wait (weeks)") - 1                 # the month sits just left of the first measure
  month <- suppressWarnings(as.Date(as.numeric(raw[[mcol]]), origin = "1899-12-30"))
  keep <- !is.na(month) & seq_len(nrow(raw)) > hr
  col <- function(label) {
    v <- as.character(raw[[j(label)]])[keep]
    v[v %in% c("-", "")] <- NA
    v
  }
  num <- function(label) suppressWarnings(as.numeric(col(label)))
  out <- tibble(
    month = month[keep],
    median_weeks = num("Median wait (weeks)"),
    p92_weeks_text = col("92nd percentile (weeks)"),
    within_18 = num("No. within 18 weeks"),
    pct_within_18 = 100 * num("% within 18 weeks"),
    over_18 = num("No. > 18 weeks"),
    over_52 = num("No. > 52 weeks"),
    over_65 = num("No. > 65 weeks"),
    over_78 = num("No. > 78 weeks"),
    over_104 = num("No. > 104 weeks"),
    waiting = num("Total waiting (mil)"),
    waiting_with_estimates = num("Total waiting (mil) with estimates for missing data")
  )
  out |>
    mutate(p92_off_scale = p92_weeks_text %in% "52+",
           p92_weeks = suppressWarnings(as.numeric(p92_weeks_text))) |>
    select(-p92_weeks_text) |>
    filter(!is.na(waiting))
}

# ---------------------------------------------------------------- the full monthly extract (zipped CSV)
read_extract <- function(zip_path) {
  inner <- unzip(zip_path, list = TRUE)$Name[1]
  read_csv(unz(zip_path, inner), show_col_types = FALSE, guess_max = 200000, progress = FALSE)
}

band_cols <- function(d) grep("^Gt ", names(d), value = TRUE)

# incomplete pathways (people still waiting), one row per provider x commissioner x specialty
waiting_list <- function(d) {
  d |>
    filter(`RTT Part Type` == "Part_2") |>
    rename(provider_code = `Provider Org Code`, provider = `Provider Org Name`,
           commissioner_code = `Commissioner Org Code`, specialty_code = `Treatment Function Code`,
           specialty = `Treatment Function Name`)
}

# summary measures for any grouping, computed from the summed weekly bands
summarise_waits <- function(wl, ...) {
  b <- band_cols(wl)
  wl |>
    group_by(...) |>
    summarise(across(all_of(b), \(x) sum(x, na.rm = TRUE)), .groups = "drop") |>
    rowwise() |>
    mutate(
      waiting = sum(c_across(all_of(b))),
      within_18 = sum(c_across(all_of(b[1:18]))),
      over_52 = sum(c_across(all_of(b[53:length(b)]))),
      over_65 = sum(c_across(all_of(b[66:length(b)]))),
      median_weeks = wait_percentile(c_across(all_of(b)), 0.5),
      p92_weeks = wait_percentile(c_across(all_of(b)), 0.92)
    ) |>
    ungroup() |>
    mutate(pct_within_18 = 100 * within_18 / waiting, pct_over_52 = 100 * over_52 / waiting) |>
    select(-all_of(b))
}

# ---------------------------------------------------------------- funnel plot with overdispersion
# With lists of 100,000 patients, plain binomial limits are so narrow that almost every trust is an "outlier".
# Following Spiegelhalter (2005), an additive random-effects term tau^2 is estimated from winsorised z-scores
# and added to each trust's sampling variance, so the limits allow for genuine between-trust variation.
funnel_overdispersed <- function(y, n, winsor = 0.1) {
  p0 <- sum(y) / sum(n)
  s2 <- p0 * (1 - p0) / n
  z <- (y / n - p0) / sqrt(s2)
  q <- quantile(z, c(winsor, 1 - winsor))
  zw <- pmin(pmax(z, q[1]), q[2])
  k <- length(z)
  phi <- mean(zw^2)
  w <- 1 / s2
  tau2 <- if (k * phi > k - 1) max(0, (k * phi - (k - 1)) / (sum(w) - sum(w^2) / sum(w))) else 0
  list(p0 = p0, phi = phi, tau2 = tau2,
       limits = function(nn, zc) p0 + zc * sqrt(p0 * (1 - p0) / nn + tau2),
       z_adj = (y / n - p0) / sqrt(s2 + tau2))
}
