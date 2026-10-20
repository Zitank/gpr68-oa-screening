# ml_audit

Q-003 on AID 2060853 only (39 active / 13 inactive). Endpoints were not pooled. Logged run `m4-ml-audit` (study M4, seed 20261004).

Morgan random forest, scaffold holdout versus stratified random holdout, 80 repeats, test fraction 0.25. Scaffold ROC-AUC median 0.773, 95% interval 0.290–0.970 (includes 0.5). Random median 0.833, interval 0.533–1.000. The real median sits above the Y-scramble null (null 95% 0.285–0.670). The learning curve does not yield a required n. Applicability domain uses a ChEMBL lead-like substitute for the missing MCE library: 0 of 108 property-matched molecules at Tanimoto >= 0.40.

Verdict: not sufficient. See `results/ml_audit/q003_verdict.json`.

Assumptions: A13–A19. Values are in the module docstrings.
