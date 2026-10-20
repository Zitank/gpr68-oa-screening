# report

Decision note for the purchase, the calcium assay, and the chondrocyte qPCR.

## Built

- Screening-funnel Monte Carlo (`src/funnel.py`), logged as `screening-funnel`.
- Calcium dose-response power via `drc` (`r/dose_power.R`), logged as `calcium-dose-power`.
- qPCR power via `pwr` (`r/qpcr_power.R`), logged as `qpcr-power`.
- Quarto note `results/report/GPR68_decision_report.qmd`, rendered to HTML.
- Upstream snapshot that reads pocket, docking, ligand, and ML-audit files when they exist.

## Skipped

- No enrichment credit for the WP2 model. The funnel is docking-only.
- pH 7.0 is not a third simulated curve. The pH 7.4 versus 6.8 contrast reuses the 3-fold shift.
- `results/docking/scores.csv` was absent at the last render, so that section stays pending.

## Assumptions

A4 and A20–A31. Values are in the Quarto note. `governance/assumptions.md` was not edited.

## Versions

R 4.5.3, drc 3.0-1, pwr 1.3-0, quarto 1.9.38, through pixi. Python 3.12, numpy 2.5.3. `ED(..., interval = "tfls")` and `EDcomp(..., interval = "fieller")` were checked against a known EC50; `interval = "fls"` was not used because in this drc build it exponentiated an already dose-scale estimate.

## Exploratory

Every probability and sample size in the note is a simulation or an analytical power calculation under those assumptions. None of it is a measured GPR68 result.
