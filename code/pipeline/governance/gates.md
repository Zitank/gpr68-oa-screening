# Human gates

Agents stop at each gate. Only the human may pass it. Record the decision in the artifact named at the end of each paragraph.

**`references.bib`.** Triggered when any source is added, removed, or renamed. The human inspects that the citekey matches the Zotero Better BibTeX export and that the work is the intended edition. The decision is the committed `governance/references.bib` itself (agents never write it).

**Marking verified.** Triggered when a formula, constant, table or figure is about to be cited from a paper. The human inspects the original PDF at that location and adds the item to `verified_items` in `vault/<citekey>.md`. The vault note frontmatter is the record; lint then requires every `CITE` location to appear there.

**Unfreezing.** Triggered when a frozen SPEC, CONTRACT or test hash would change. The human inspects the proposed contract change and the reason the existing tests are wrong. The record is a new spec version plus a logged reason (decision record under `governance/decisions/` once that tree exists).

**Signing a prereg.** Triggered before the first confirmatory run of a hypothesis. The human inspects hypotheses, conditions, tolerance, seeds, cost models, tuning budget and analysis plan. Signing hashes the prereg and tags git; the hash is stored on later ledger lines.

**Ruling on a finding.** Triggered when the Challenger writes `governance/findings/*.md`. The human inspects claimed flaw, evidence, and the proposed exposing test, then marks accept, reject (with reason) or defer in that same findings file.

**Promoting a claim.** Triggered when an exploratory or confirmatory result would enter `claims.yaml`. The human inspects the tier 3 report, ledger completeness and the prereg match. The record is a human edit of `claims.yaml`; exploratory results cannot be promoted without a new prereg and a fresh run.
