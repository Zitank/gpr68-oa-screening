# KIT — Project S from Project N

This repo is the GPR68 (OGR1) osteoarthritis screening sprint. The method is a research pipeline adapted from an earlier audit kit (Project N), written for a spiking-network wiring-cost audit, then copied through a domain-neutral skeleton and filled for this question. A reviewer should be able to see which pieces are inherited controls and which pieces are this project's science.

## Kept

The audit machinery is the point of the port.

- **Frozen config and hash.** `core/config.py` defines a pydantic `ExperimentConfig` with `frozen=True` and `extra="forbid"`. `config_hash` is the sha256 hex of canonical JSON (`core/hashing.py` `sha256_json`: sorted keys, no insignificant whitespace, `allow_nan=False`). A null `study_id` is omitted from the hashed dict, so an unset id does not move the hash.
- **Append-only ledger.** `core/ledger.py` `run_logged()` is the only writer of `governance/run_ledger.jsonl`. One JSON object per line. A failed call is still appended (`status="failed"`) and re-raised. `tools/check_ledger.py` rejects a rewritten prefix. Hand-editing the file is a breach.
- **Human gates.** `governance/gates.md` lists six stops only the human may pass: adding `governance/references.bib`, marking an item verified, unfreezing a spec, signing a prereg, ruling on a finding, and promoting a result to a claim. Agents do not pass them.
- **Assumption register.** `governance/assumptions.md`. Every `## [ASSUMPTION: Ax]` tag in code has a row. Status stays `ASSUMPTION` until a human adds a verified card and a bib key. No row in this file is `cited`.
- **Code tags.** `tools/lint_tags.py` scans `core/`, `clusters/`, `tools/`, `studies/`, `governance/`, and `smoke.py`. The tags this sprint uses are `## [ASSUMPTION: Ax]`, `## [EXPLORATORY]`, and `## [NEEDS-SOURCE: …]`. Also recognised: `CITE`, `HYP`, `DECISION`, `VERIFIED-BY`, `SPECULATION`, `IMPROVE`. A `CITE` fails while `governance/references.bib` is absent. A `SPECULATION` is quarantined unless the file sits under `explore/` or the same file carries `## [EXPLORATORY]`.
- **Tier 0.** `just tier0` is format, ruff, pyright, fast pytest, and the ledger check. Tiers 1–3 print "not implemented in Phase 0".
- **Roles and questions.** `AGENTS.md` keeps the Project N role table. The question cards are Q-001 (the seniors' question), Q-002 (docking enrichment), and Q-003 (ligand-based generalisation). The idea registry and the L0 literature tools (`tools/lit/`, `literature/PROTOCOL.md`) are the same kit.

## Generalised

Project N's `ExperimentConfig` embedded `ModelConfig`, `DataConfig`, and `CostModelRef`, and `condition_code` was only `A|B|C|D`. Those sat beside `core/types.py` (grid layout, spike stats, cost in arbitrary units). This repo has one frozen config: `name`, `seed`, `mode`, a free `condition_code` string, and `params: dict[str, float | int | str]` with `default_factory` so the dict is not shared. Pocket boxes, run specs, activity rows, and splits stay inside their clusters.

Clusters follow the question. Project N had `snn_training` and `cost_accounting`. This repo has `ligand_data`, `pocket`, `docking`, and `ml_audit`.

The assumption ids were replaced. Project N's A1–A9 were energy constants in arbitrary units, an SHD holdout, a bit-width, and a pruning threshold. Here A1 is the cubic docking-box edge, 24.0 Å. A2 is smina exhaustiveness 16. A3 is decoy Tanimoto < 0.3. A4 is a screening-funnel prior whose bounds are not set. A5 is pH 6.8 as the primary protomer and pH 7.4 as the comparison. Further ids were reserved from A10 (data and ML) and A20 (statistics and reporting). At the governance sweep that reservation had already failed: docking tagged A6–A10, and A10 is also the Morgan fingerprint in ligand data. `governance/assumptions.md` records the collision and does not renumber either use.

Dependencies changed with the domain. torch, snnTorch, and optional Tonic are gone. rdkit, meeko, gemmi, scikit-learn, pandas, matplotlib, and seaborn are in. Python stays on uv (`pyproject.toml`, still named `research-mvp`). External binaries are pixi (`pixi.toml`: smina 2017.11.9, R, Quarto, OpenBabel). That split is decision D-5. Project N had no pixi manifest.

The quote checker root is configurable. Set `EVIDENCE_ROOT` or pass `--root`. Otherwise the default is the parent of this pipeline when that parent contains `sources/` and `lit/`, and this pipeline directory when it does not. The five reading notes are not included in this published repository. Bibliography keys are read from `<root>/refs/*.bib` and, when present, from `governance/references.bib`. The tool does not create either file.

## Dropped, and why

- **SNN science.** `core/types.py`, LIF fields, conditions A–D, SHD, torch. The question is a GPCR pocket and a bioactivity table.
- **Programme layer.** `programme/`, `studies/` (S01–S06), `tools/study_lint.py`, `tools/studies.py`, `just/programme.just`. This sprint is one exploratory phase. Study sealing can be added later; it is not Phase 0.
- **Project N's literature corpus.** Queries A–K, `seed_records.jsonl`, `reading_plan.md`, and the neuromorphic extracts (`yan2024reconsidering` and the rest). The GPR68 seeds are five frozen extracts already on disk: `@huang2015allosteric` (green-OA author manuscript, `oa-other`), `@matsingos2023elucidating` (bioRxiv preprint, `oa-other`, `is_preprint: true`), `@krivak2018p2rank` (`oa-cc`), `@chen2019hidden` (`oa-cc`), `@hyde2026joint` (`oa-cc`, a review). `literature/queries/` is still `TEMPLATE.yaml`. `literature/corpus/` has a schema and no records. That is unfinished librarian work.
- **The kit's example cluster.** `clusters/example` (a numpy line fit) was removed when the four science clusters were added. `smoke.py` runs a small logged linear fit in this file and checks that the ledger grows by two identical lines. It does not call smina. The phase exit is the eight docking runs, recorded by `run_logged()`.
- **GNINA as a local engine.** D-1 is smina on this CPU. The only GNINA v1.3.3 artifact found for this machine is a CUDA binary, and there is no discrete GPU (`COMPUTE.md`). GPU replay is a later run of shipped command files, on another machine.

## Literature chain

Zotero, edited by the human → Better BibTeX export at `<vault>/refs/library.bib` → frozen text at `<vault>/sources/<citekey>.md` → reading note `<vault>/lit/@<citekey>.md` (quote callouts and `### ID` evidence cards) → `uv run python tools/check_evidence.py`.

A second file, `governance/references.bib`, is the in-repo allow-list for `## [CITE: key]` tags. `lint_tags.py` reads it. `check_evidence.py` reads it too once it exists. Agents do not write it. It is not in the tree.

Legal `access` values, and only these: `oa-cc`, `oa-arxiv`, `oa-other`, `ieee-no-ai`, `paywalled-no-ai`. For `ieee-no-ai` and `paywalled-no-ai` the checker fails if `sources/<key>.md` exists, requires a page locator (`p. 6`), and allows only status `human-read`. For the three OA labels the quote must occur verbatim in the frozen extract after the normaliser (NFKC, quote and dash folding, de-hyphenation across line breaks, markdown emphasis stripped, whitespace collapsed, case folded).

Card status moves to `quote-verified` or `human-read` only when the human has read the source. An agent extract is `ai-extracted` at most, and the checker warns on that status. The five notes have empty card sections. The checker reporting zero verified cards is the correct result. Do not add cards to make it pass.

`just lit-fetch` still looks for `../vault/tools/fetch_arxiv.py`. That path is not in this folder. Project N fetched with `Project_N/tools/fetch_arxiv.py`. The five extracts here were frozen by hand. Fetch stays optional. IEEE and paywalled full text is never requested, parsed, or stored under `sources/`.

## Unfinished on purpose

No assumption is `cited`. No `references.bib`. No verified card. Tiers 1–3 are stubs. Exploratory mode: the test split stays sealed, and nothing in this tree is a claim. The ledger's append-only rule binds from the first real `run_logged()` line after the example lines were cleared (`LOG.md`).
