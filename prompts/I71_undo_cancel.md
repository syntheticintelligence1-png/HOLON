# I71: UNDO's third sub-form, cancel (I33's catalog key)

The plan is row I71 of `docs/BUILD_PLAN.md`, section 3. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (C1-C11) are in the docstring of `tests_m3/test_undo_cancel.py`; the instrument is `tests_m3/_i71.py`; the key is I71 in `spec/M3/predictions.json`.

## Why

- **I27's gap G5.** M1's `L_undo_cancel` says that pausing cancels an open challenge: after `challengeState` and `setPause(true)` the system behaves as after `setPause(true)` alone. I27's back-test maps it to the extracted pair (challengeState, setPause), which rules U3 and U4 cannot see:
  - setPause writes `inChallenge` back to 0 only under `_status && inChallenge`, so there is no U3 restore;
  - its guards read only `_owner` and `_paused`, so there is no U4 criterion.
- **I33 needs a scope law.** The O12 intent contract on M3 marks a REFUTED UNDO law whose divergence the contract bounds. No M3 law is the analogue of `L_undo_cancel` today.

## What I71 does

- **Two rules, computed apart from U3 and U4 (C1-C2).**
  - U3', the cancel restore: a's whole, fresh, final, unconditional write of a register pinned to a literal is written back by ā, outside any loop, under a condition whose conjuncts are ā's parameters or the register's own reading.
  - U4', the criterion `cond`: some conjunct of that condition reads the register.
- **Residues and class (C3).** U5's residues; D1-D3 with no context. No residue law comes from a cancellation.
- **The analysis document (C4)** gains `cancellations` and `rejected_cancellations`. I27's keys keep their content.
- **The catalog (C5).** `holon-rules/1.7` = I28's `holon-rules/1.6` plus UNDO's separate `cancel` producer. `undo.PRODUCERS` stays {pair, residue}.
- **The law (C6).** `L_undo_cancel_<contract>_<a>_<undo>`, undo id `<model>:cancel:<a>:<undo>`. The IR schema's undo-id pattern admits `cancel`, and the Q4 adoption copy follows.
- **The template (C7).** It compares `obs(t, after(after(s, x), y))` with `obs(t, after(s, y))`, with x succeeding from s, y from s1 and from s, and the restore premise.
- **Deciding (C8).** The UNDO search compares x;y;t with y;t. The replay runs both on the real contract. No proof generator: an unrefuted cancel law is UNKNOWN.
- **The back-test (C9).** A pair spec's analogue is the pair law, else the cancel law of the same (a, ā). G5 closes.
- **The recipe (C10).** It runs after I28's build is on the lead. The catalog bump re-makes every M3 record, as I26's and I28's bumps did, except I27's eight UNDO records (stale since I26). The M1, M2 and T32 records are re-stamped.
- **Earlier tests (C11).** I27's counts are narrowed to its sub-forms, with four amendment lines.

## Predictions (all counted)

- **P1.** holon's analysis gives the instrument's cancellations on the Rollup, the mutant, the toys and the planted variants.
- **P2.** derive emits exactly the cancel law as C6 states it. Every other law file changes in `rule_catalog_version` only, each change logged as a catalog_rederivation line.
- **P3.** REFUTED: the counter-law is checked by bend2 and BendTT, and the replay passes with the calls agreeing. x = challengeState, y = setPause(true).
- **P4.** The divergence is the refund: msg.value ≥ 1, and claimReward succeeds after x;y but reverts after y alone.
- **P5.** The back-test's gaps are [], and L_undo_cancel has an analogue with the same status.
- **P6.** The classification agrees: static live, kernel live.

## Regressions

R1, the catalog; R2, the other M3 statuses; R3, earlier milestones change in stamps only; R4, I27's analysis is unchanged; R5, the new code names no target; R6, the schema admits cancel.

## Questions for the human (also in the key)

- **H1.** The template's premise "y succeeds from s".
- **H2.** No proof generator for cancel laws.
- **H3.** The re-make cost of the catalog bump. I27's UNDO records stay stale until I68.
- **H4.** U3' accepts only parameter conjuncts and the register's own reading.
