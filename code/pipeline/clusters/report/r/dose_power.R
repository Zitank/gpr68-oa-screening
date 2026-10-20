# Calcium dose-response power. Exploratory simulation, not a measured ogerin curve.
# Interval choice: ED(..., interval = "tfls") keeps the EC50 on the dose scale.
# EDcomp(..., interval = "fls") exponentiates that scale again in drc 3.0-1, so the
# ratio uses Fieller. A failed self-check stops the script.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1L) {
  stop("usage: Rscript dose_power.R config.json")
}

suppressPackageStartupMessages(library(drc))
suppressPackageStartupMessages(library(jsonlite))

cfg <- jsonlite::fromJSON(args[[1L]], simplifyVector = FALSE)
required <- c(
  "seed", "n_mc", "sd", "ec50", "shift", "upper", "lower", "slope",
  "ci_fold_limit", "designs", "replicates", "out_dir"
)
missing <- setdiff(required, names(cfg))
if (length(missing) > 0L) {
  stop(paste("dose config missing keys:", paste(missing, collapse = ", ")))
}

RNGkind(kind = "Mersenne-Twister", normal.kind = "Inversion", sample.kind = "Rejection")
set.seed(as.integer(cfg$seed))

out_dir <- cfg$out_dir
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)

mean_response <- function(dose, ec50) {
  cfg$lower + (cfg$upper - cfg$lower) / (1 + exp(cfg$slope * (log(dose) - log(ec50))))
}

fct_for <- function(fixed) {
  if (fixed) LL.4(fixed = c(NA, cfg$lower, cfg$upper, NA)) else LL.4()
}

one_curve <- function(doses, reps, ec50, sd, fixed) {
  dose <- rep(doses, each = reps)
  dat <- data.frame(dose = dose, response = mean_response(dose, ec50) + rnorm(length(dose), 0, sd))
  fit <- try(drm(response ~ dose, data = dat, fct = fct_for(fixed), control = drmc(noMessage = TRUE)), silent = TRUE)
  if (inherits(fit, "try-error")) {
    return(list(ok = FALSE, error = as.character(fit)))
  }
  ed <- try(ED(fit, 50, interval = "tfls", display = FALSE), silent = TRUE)
  if (inherits(ed, "try-error")) {
    return(list(ok = FALSE, error = as.character(ed)))
  }
  est <- unname(ed[1L, "Estimate"])
  lo <- unname(ed[1L, "Lower"])
  hi <- unname(ed[1L, "Upper"])
  ci_ok <- is.finite(est) && is.finite(lo) && is.finite(hi) && lo > 0 && hi > lo
  list(
    ok = TRUE,
    error = "",
    ci_ok = ci_ok,
    est = est,
    fold = if (ci_ok) hi / lo else NA_real_,
    cover = isTRUE(ci_ok && lo <= ec50 && hi >= ec50),
    fold_le = isTRUE(ci_ok && (hi / lo) <= cfg$ci_fold_limit)
  )
}

two_curves <- function(doses, reps, sd) {
  draw <- function(ec50, label) {
    dose <- rep(doses, each = reps)
    data.frame(
      dose = dose,
      response = mean_response(dose, ec50) + rnorm(length(dose), 0, sd),
      compound = label
    )
  }
  dat <- rbind(draw(cfg$ec50, "ref"), draw(cfg$ec50 * cfg$shift, "test"))
  dat$compound <- factor(dat$compound, levels = c("ref", "test"))
  fit <- try(
    drm(response ~ dose, curveid = compound, data = dat, fct = fct_for(TRUE), control = drmc(noMessage = TRUE)),
    silent = TRUE
  )
  if (inherits(fit, "try-error")) {
    return(list(ok = FALSE, error = as.character(fit)))
  }
  comp <- try(EDcomp(fit, c(50, 50), interval = "fieller", display = FALSE), silent = TRUE)
  if (inherits(comp, "try-error")) {
    return(list(ok = TRUE, fieller = FALSE, error = as.character(comp), excludes = FALSE, covers = FALSE, est = NA_real_))
  }
  label <- rownames(comp)[[1L]]
  if (!grepl("ref", label) || !grepl("test", label)) {
    stop(paste("unexpected EDcomp row name:", label))
  }
  est <- unname(comp[1L, "Estimate"])
  lo <- unname(comp[1L, "Lower"])
  hi <- unname(comp[1L, "Upper"])
  finite <- is.finite(est) && is.finite(lo) && is.finite(hi)
  list(
    ok = TRUE,
    fieller = finite,
    error = "",
    est = est,
    excludes = isTRUE(finite && (hi < 1 || lo > 1)),
    covers = isTRUE(finite && lo <= (1 / cfg$shift) && hi >= (1 / cfg$shift))
  )
}

assert_close <- function(estimate, truth, what) {
  if (!is.finite(estimate) || estimate <= 0) {
    stop(paste(what, "self-check estimate was not a positive finite number"))
  }
  if (estimate < truth / 1.5 || estimate > truth * 1.5) {
    stop(paste(what, "self-check estimate", estimate, "is not within 1.5-fold of", truth))
  }
}

pilot_doses <- unlist(cfg$designs[[1L]]$doses)
fixed_pilot <- one_curve(pilot_doses, 8L, cfg$ec50, sd = 2, fixed = TRUE)
free_pilot <- one_curve(pilot_doses, 8L, cfg$ec50, sd = 2, fixed = FALSE)
if (!isTRUE(fixed_pilot$ok) || !isTRUE(free_pilot$ok)) {
  stop(paste("dose self-check fit failed", fixed_pilot$error, free_pilot$error))
}
assert_close(fixed_pilot$est, cfg$ec50, "fixed-asymptote EC50")
assert_close(free_pilot$est, cfg$ec50, "free-asymptote EC50")
shift_pilot <- two_curves(pilot_doses, 8L, sd = 2)
if (!isTRUE(shift_pilot$fieller)) {
  stop(paste("shift self-check failed", shift_pilot$error))
}
assert_close(shift_pilot$est, 1 / cfg$shift, "EC50 ratio ref/test")

last_error <- function(results) {
  messages <- vapply(results, function(x) as.character(x$error %||% ""), character(1L))
  # `%||%` may not exist. Use an explicit helper below if this fails.
  kept <- messages[nzchar(messages)]
  if (length(kept) == 0L) "" else substr(kept[[length(kept)]], 1L, 180L)
}

`%||%` <- function(x, y) if (is.null(x)) y else x

numeric_or_na <- function(x) if (length(x) == 0L || all(!is.finite(x))) NA_real_ else as.numeric(x[[1L]])

summarise_single <- function(results, design, reps, asymptotes) {
  n_mc <- length(results)
  n_ok <- sum(vapply(results, function(x) isTRUE(x$ok), logical(1L)))
  if (n_ok == 0L) {
    stop(paste("every", asymptotes, design$id, "replicate failed:", last_error(results)))
  }
  folds <- vapply(results, function(x) if (isTRUE(x$ci_ok)) x$fold else NA_real_, numeric(1L))
  ests <- vapply(results, function(x) if (isTRUE(x$ci_ok)) x$est else NA_real_, numeric(1L))
  data.frame(
    design_id = paste0(design$id, "-r", reps),
    design_id_base = design$id,
    n_conc = length(design$doses),
    n_rep = reps,
    asymptotes = asymptotes,
    n_mc = n_mc,
    n_converged = n_ok,
    frac_converged = n_ok / n_mc,
    coverage = sum(vapply(results, function(x) isTRUE(x$cover), logical(1L))) / n_mc,
    median_estimate = median(ests, na.rm = TRUE),
    median_fold = median(folds, na.rm = TRUE),
    q25_fold = as.numeric(quantile(folds, 0.25, na.rm = TRUE, names = FALSE)),
    q75_fold = as.numeric(quantile(folds, 0.75, na.rm = TRUE, names = FALSE)),
    frac_fold_le_3 = sum(vapply(results, function(x) isTRUE(x$fold_le), logical(1L))) / n_mc,
    last_error = last_error(results),
    stringsAsFactors = FALSE
  )
}

summarise_shift <- function(results, design, reps) {
  n_mc <- length(results)
  n_ok <- sum(vapply(results, function(x) isTRUE(x$ok), logical(1L)))
  ests <- vapply(results, function(x) if (isTRUE(x$fieller)) x$est else NA_real_, numeric(1L))
  data.frame(
    design_id = paste0(design$id, "-r", reps),
    design_id_base = design$id,
    n_conc = length(design$doses),
    n_rep = reps,
    asymptotes = "fixed",
    n_mc = n_mc,
    n_converged = n_ok,
    frac_converged = n_ok / n_mc,
    n_fieller = sum(vapply(results, function(x) isTRUE(x$fieller), logical(1L))),
    power = sum(vapply(results, function(x) isTRUE(x$excludes), logical(1L))) / n_mc,
    ratio_coverage = sum(vapply(results, function(x) isTRUE(x$covers), logical(1L))) / n_mc,
    median_ratio = median(ests, na.rm = TRUE),
    last_error = last_error(results),
    stringsAsFactors = FALSE
  )
}

single_rows <- list()
shift_rows <- list()
for (design in cfg$designs) {
  for (reps in unlist(cfg$replicates)) {
    message("dose ", design$id, " replicates ", reps)
    fixed <- replicate(cfg$n_mc, one_curve(unlist(design$doses), reps, cfg$ec50, cfg$sd, TRUE), simplify = FALSE)
    free <- replicate(cfg$n_mc, one_curve(unlist(design$doses), reps, cfg$ec50, cfg$sd, FALSE), simplify = FALSE)
    shift <- replicate(cfg$n_mc, two_curves(unlist(design$doses), reps, cfg$sd), simplify = FALSE)
    single_rows[[length(single_rows) + 1L]] <- summarise_single(fixed, design, reps, "fixed")
    single_rows[[length(single_rows) + 1L]] <- summarise_single(free, design, reps, "free")
    shift_rows[[length(shift_rows) + 1L]] <- summarise_shift(shift, design, reps)
  }
}

utils::write.csv(do.call(rbind, single_rows), file.path(out_dir, "dose_single.csv"), row.names = FALSE, na = "")
utils::write.csv(do.call(rbind, shift_rows), file.path(out_dir, "dose_shift.csv"), row.names = FALSE, na = "")
message("dose tables written")
