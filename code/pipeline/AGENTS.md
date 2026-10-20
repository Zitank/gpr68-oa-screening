# Research pipeline: operating rules

## Mission

This sprint asks whether smina docking on apo GPR68 (PDB 8Z68 chain R, prepared at pH 6.8) enriches known modulators at the proton-sensing pocket above chance and above the lipid-facing groove, and whether the public bioactivity tables can train a ligand-based model that generalises across chemical series. Controls are pocket 2, property-matched decoys, the 13 experimental inactives in PubChem AID 2060853, scaffold split against random split, and a Y-scrambling null. A null result is valid: it is a reason not to buy compounds. Correctness and auditability outrank speed. The work is exploratory only.

## Universal rules (all roles)

1. Fail loudly. Raise typed errors (`core.errors`). No silent fallbacks or coercion.
2. Never invent citations. Cite only keys in `governance/references.bib` with a vault-verified location. Else `## [NEEDS-SOURCE: …]` and stop.
3. Never invent constants, formulas or APIs. Verified citation or `## [ASSUMPTION: Ax]`.
4. Never edit frozen specs or the ledger by hand. Ledger lines come only from `run_logged()`.
5. Never touch the test split in exploratory mode. Train/val only until confirmatory.
6. Stay inside your role's write paths. Needs outside scope are a written request.
7. One phase per session. Do not build ahead of the current phase exit criterion.
8. Show exit-command output. Report uncertainty; 'I don't know' is valid.
9. Human gates (below) stop work. Only the human may pass them.

## Roles

| Role | May write |
| --- | --- |
| Architect | Specs, decisions, hypotheses; no production code |
| Cluster lead | `CLUSTER.md`, integration tests; not component internals |
| Manager | Dispatches the coder (`dispatch_coder.py` later); `LOG.md` |
| Coder | `src/` of one component (`explore/` if exploratory); never tests |
| Challenger | `governance/findings/*.md` only (flaw, evidence, exposing test, severity) |
| Integrity | Pass/fail from scripts; agents cannot override |
| Scout | SEED cards, landscape proposals, search logs; leads not facts |
| Test-Author | Tests from SPEC/CONTRACT/golden values; never reads `src/` |

## Human gates (stop and ask)

Adding a source to `references.bib`; marking a verified item; unfreezing a spec;
signing a prereg; ruling on a finding; promoting a result to a claim.

## Modes

`exploratory`: find questions; no prereg; cannot enter claims; tier 0 only; test split sealed.
`confirmatory`: one preregistered hypothesis; tiers 0–3; test split is a capability object.

## Phase 0 fixed decisions

- **D-1** smina is the Vina-level docking engine. GNINA command files are shipped for GPU replay. Do not relitigate this inside a packet.
- **D-2** Pocket 1 is the primary site. Pocket 2 is the lipid-facing negative control.
- **D-3** Bioactivity endpoints are never pooled.
- **D-4** This sprint is exploratory only. Nothing promotes to a claim.
- **D-5** uv owns Python dependencies. pixi owns external binaries (smina, R, Quarto, OpenBabel).

## Where things live

`docs/PHASE0.md` (packets, exit criterion) · `governance/` (ledger, gates, human-owned files) · `clusters/` (the work) · `tools/` (checks). No frozen SPEC tree yet. `docs/PHASE0.md` is the phase packet and wins on conflict with cluster notes until a human freezes a spec under the unfreezing gate (`governance/decisions/` once that tree exists).

Frozen paper text and reading notes sit outside this repo, in `../sources/` and `../lit/` (five papers). `tools/check_evidence.py` checks quotes against those extracts. `governance/references.bib` does not exist until the human adds it. How this tree was adapted from Project N is `KIT.md`.

The DeepSeek key lives in env var `DEEPSEEK_API_KEY` only; never write it to disk.
