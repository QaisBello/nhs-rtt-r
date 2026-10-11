# Run from the repo root:  Rscript -e 'testthat::test_dir("tests/testthat")'
root <- normalizePath(file.path(testthat::test_path(), "..", ".."))
source(file.path(root, "R/rtt.R"))
clean <- function(f) read_csv(file.path(root, "data/clean", f), show_col_types = FALSE)

test_that("percentiles interpolate within one-week bands", {
  counts <- c(10, rep(0, 104))                    # everyone waits 0-1 weeks
  expect_equal(wait_percentile(counts, 0.5), 0.5)
  counts <- c(5, 5, rep(0, 103))                  # half in week 0-1, half in week 1-2
  expect_equal(wait_percentile(counts, 0.5), 1)
  expect_equal(wait_percentile(counts, 0.92), 1.84)
  counts <- c(rep(0, 104), 7)                     # all in the open-ended 104+ band
  expect_equal(wait_percentile(counts, 0.5), 104)
  expect_true(is.na(wait_percentile(rep(0, 105), 0.5)))
})

test_that("rebuilt England figures match NHS England's published ones", {
  dq <- clean("data_quality_log.csv")
  expect_equal(dq$action[dq$check == "England, August 2026"], "Matches")
})

test_that("time series is tidy: one row per month, no text left in numbers", {
  ts <- clean("england_timeseries.csv")
  expect_false(any(duplicated(ts$month)))
  expect_true(all(diff(ts$month) > 0))
  expect_true(all(ts$pct_within_18 > 0 & ts$pct_within_18 <= 100))
  expect_true(all(ts$within_18 + ts$over_18 == ts$waiting))
  expect_equal(format(max(ts$month[ts$pct_within_18 >= 92]), "%Y-%m"), "2016-02")
})

test_that("specialties add up to the England total without double counting", {
  spec <- clean("specialty_summary.csv"); ts <- clean("england_timeseries.csv")
  expect_equal(sum(spec$waiting), ts$waiting[ts$month == max(ts$month)])
  expect_false("Total" %in% spec$specialty)
})

test_that("overdispersion widens the funnel only when trusts vary more than chance", {
  set.seed(1)
  n <- rep(c(2000, 5000, 20000, 80000), 25)
  y_binom <- rbinom(length(n), n, 0.65)
  expect_lt(funnel_overdispersed(y_binom, n)$tau2, 1e-4)
  y_spread <- round(n * plogis(qlogis(0.65) + rnorm(length(n), 0, 0.3)))
  expect_gt(funnel_overdispersed(y_spread, n)$tau2, 1e-3)
})
