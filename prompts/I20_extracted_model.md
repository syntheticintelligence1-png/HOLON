# I20: extracted rollup model: refinement, width, optional hevm

Rendered from `docs/BUILD_PLAN.md` §4 I20 (whitepaper §8.7, §7.6, §10.1 translators, L1). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact outputs and rules are in the docstring of `tests_m2/test_extracted_refinement.py`.

## Goal

Compile I19's extracted rollup state machine into a Bend model, with raw storage families plus a window view. Show on the replay corpus that it refines the real contract. Generate width obligations. Re-run the M1 rollup laws on it, explaining every status difference mechanically. Re-derive I15's site laws on the extracted facts through the re-extraction channel.

## Deliverables (summary; the contract has the details)

- **`machine.py`** compiles holon-facts/0.3 transitions documents, and `holon model` writes `gen/M2/extracted/model.bend`. The extracted guard terms (I17's W4 language) are translated to the model DSL, including the inherited storage the guards read.
- **The window view**, plus `gen/M2/extracted/window_check.json` comparing it with the hand abstraction. The raw model is authoritative.
- **`holon/replay_fragments.py`:** refinement of the extracted transitions against the real contract on the I16 corpus plus a boundary corpus. The result goes to `results/M2/refinement/extracted.json`.
- **Rule SORT-width:** width-site laws through `holon derive`, run like the I15 site laws.
- **`holon differential`,** writing `gen/M2/abstraction_diff.json` (mechanical deltas) and `results/M2/differential.json`.
- **Re-extraction acceptance in `holon/statement_diff.py`,** with STATEMENT_DIFF entries for I15's 10 site laws re-derived on the extracted facts.
- **Optional hevm** (Q16 allows the install): run, or recorded as `not_run`.
- **`docs/iterations/I20.md`,** with a prediction table.

## Predictions (key I20)

| id | claim |
|---|---|
| P1 | There are 0 unexplained disagreements between the extracted model and the real contract on the 300-trace and boundary corpus. |
| P2 | The width-site law at the totalL1MessagePopped store (the `unchecked` accumulator at Rollup.sol:324) is UNKNOWN: bounded, with no witness. |
| P3 | The width-site law at the batchIndex store is UNKNOWN: bounded, with no witness. |
| P4 | The reextraction entries for I15's re-derived site laws validate unsigned. |
| P5 | All 15 rollup M1 laws are re-run on the extracted model. Every status difference links to a mechanical delta in `gen/M2/abstraction_diff.json`. |
| P6 | L_sort_remaining, L_undo_BVH and L_undo_cancel stay REFUTED on the extracted model. |
| P7 | L_tag_BVH reads the ghost tag. It differs from its M1 status on the extracted model, and a `ghost` delta explains the difference. |

**Regressions.** Gates M0, M1 and M2 pass. I15's site-law outcomes are unchanged after re-extraction: 6 PROVED, 2 UNKNOWN, 2 REFUTED. M1 statuses on M1 itself are unchanged.

## Rules

- **AGENTS.md is binding.** Never edit `facts/`, `spec/M1/facts/` or `laws/M1/`.
- **Deltas are mechanical:** each one is a concrete difference between the documents, touching the law's cone. Prose never explains a status difference.
- **No tuning, no skips.** A miss is a Surprise reported with its evidence.

## Contract tightening (2026-10-13, before the build)

Clauses 7 to 10 of the contract docstring were added after the prereg and before any outcome existed. They are additive and leave the key and predictions unchanged.
- **Clause 7: observables.** Each refinement step compares status, revert data (reason, custom-error selector or Panic code), every touched storage slot (read with `vm.load` at the document's layout) and emitted events.
- **Clause 7: guard coverage.** The boundary corpus targets every guard reach and implicit check. Each one is falsified on both sides, or listed with a reason.
- **Clause 8:** every modelled action both succeeds and reverts in the corpus.
- **Clause 9:** both sides Panic 0x11 at Rollup.sol:363 on I15's witnesses.
- **Clause 10:** `holon model` and `holon differential` are deterministic.

Compile every guard reach, implicit check and event that the extracted document records (I19 follow-up A19), not only the first reach of each guard.
