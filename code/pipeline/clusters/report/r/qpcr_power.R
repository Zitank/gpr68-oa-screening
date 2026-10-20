# Delta-Ct power for the chondrocyte panel. Analytical pwr::pwr.t.test, not a simulation.
# ## [EXPLORATORY]
# ## [ASSUMPTION: A28] ## [ASSUMPTION: A29] ## [ASSUMPTION: A30]

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) {
  stop("usage: Rscript qpcr_power.R config.json")
}

suppressPackageStartupMessages(library(pwr))
suppressPackageStartupMessages(library(jsonlite))

cfg <- jsonlite::fromJSON(args[[1L]], simplifyVector = FALSE)
required <- c("sd_grid", "n_grid", "alpha", "alpha_bonferroni", "fold", "power", "out_dir", "seed")
missing <- setdiff(required, names(cfg))
if (length(missing) > 0L) {
  stop(paste("qPCR config missing keys:", paste(missing, collapse = ", ")))
}

# pwr's classic two-sample n for d = 0.5 at 80% power is about 63.8. Refuse a wrong call.
check <- pwr.t.test(d = 0.5, sig.level = 0.05, power = 0.8, type = "two.sample", alternative = "two.sided")
if (!is.finite(check$n) || check$n < 60 || check$n > 70) {
  stop(paste("pwr self-check returned n =", check$n))
}

dir.create(cfg$out_dir, recursive = TRUE, showWarnings = FALSE)

detectable_fold <- function(n, sd, alpha) {
  effect <- pwr.t.test(
    n = n,
    sig.level = alpha,
    power = cfg$power,
    type = "two.sample",
    alternative = "two.sided"
  )$d
  2^(effect * sd)
}

minimum_n <- function(sd, alpha, alternative) {
  effect <- log2(cfg$fold) / sd
  if (!is.finite(effect) || effect <= 0) {
    stop("fold-change effect size must be positive")
  }
  for (n in 2:200) {
    achieved <- pwr.t.test(
      n = n,
      d = effect,
      sig.level = alpha,
      type = "two.sample",
      alternative = alternative
    )$power
    if (achieved >= cfg$power) {
      return(list(n = n, power = achieved))
    }
  }
  stop(paste("no n <= 200 reaches", cfg$power, "for SD", sd, "alpha", alpha))
}

rows <- list()
add <- function(quantity, sd, alpha, n, fold, power) {
  rows[[length(rows) + 1L]] <<- data.frame(
    quantity = quantity,
    sd_ct = sd,
    alpha = alpha,
    n_per_group = n,
    fold = fold,
    power = power,
    stringsAsFactors = FALSE
  )
}

for (sd in unlist(cfg$sd_grid)) {
  for (alpha in c(cfg$alpha, cfg$alpha_bonferroni)) {
    for (n in unlist(cfg$n_grid)) {
      add("detectable_fold", sd, alpha, n, detectable_fold(n, sd, alpha), cfg$power)
    }
    found <- minimum_n(sd, alpha, "two.sided")
    add("minimum_n", sd, alpha, found$n, cfg$fold, found$power)
    one_sided <- minimum_n(sd, alpha, "greater")
    add("minimum_n_one_sided", sd, alpha, one_sided$n, cfg$fold, one_sided$power)
  }
}

# The seed is recorded so the logged config matches the other runs. pwr does not use it.
if (!is.numeric(cfg$seed)) {
  stop("qPCR seed must be numeric")
}

utils::write.csv(do.call(rbind, rows), file.path(cfg$out_dir, "qpcr_power.csv"), row.names = FALSE)
message("qPCR table written")
