# I82 (= I46a): the blind pack, the comparison generator and the agreement metric

Rendered from `docs/BUILD_PLAN.md` §3 (row I82) and §4 I46. Milestone M3. I46 keeps its number for the blind rerun and
the M3 exit; this key builds the tooling so that I46's blind rerun and generated comparison can run the moment the last
M3 iteration lands.

Whitepaper sources:
- §11.7 and §11.8 (the comparison with the manual analysis, and the preregistered predictions for the mechanized
  rerun);
- §11.3, §11.4, §11.6 and Appendix A (the O, N, D and F ids the comparison maps to law ids);
- §12 L8 (hindsight; the blind rerun by fresh agents without Appendix A) and §15.2 M3 (the published comparison).

Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. Then read:
- BUILD_PLAN I46's protocol (what the sealed bundle contains and excludes) and row I82;
- `tools/casestudy.py` and `docs/iterations/I4.md` (I4's case-study coverage: the precedent for parsing §11 and
  Appendix A, and for the `maps_to` ledger `spec/ledger/maps_to.json`);
- `holon/backtest.py` and the back-test tables `results/M3/backtest.json`, `results/M3/undo/backtest.json` and
  `results/M3/fact/backtest.json` (I24, I27, I26: M3 laws paired with M0 and M1 laws);
- `holon/rules/par.py` (rule P11's alpha-normal form, `canonical`), whose idea the metric reuses without the facts path;
- `holon/gate.py` G1 and `holon/metrics.py` (how a derived output is regenerated and compared under G1).

**The docstring of `tests_m3/test_blind.py` is the contract** (rules K1-K9, L1-L6, A1-A9, G1, B1-B6 and R).

Fixed at the prereg (do not edit them; a wrong instrument is a Question and an `instrument_inconsistency` line in
`spec/M3/amendments.jsonl`):
- `tests_m3/_i82.py`, written without holon/;
- `spec/M3/lib/blind_pack.json` (the pack's protocol: include roots, the protocol's exclusions, the redaction, the leak
  classes);
- `spec/M3/lib/appendixA.json` (the record sets compared, the back-test tables, and the curated links, each citing the
  committed text, written before the law's outcome, that ties the law to the item).

## Deliverables

1. `tools/blind_pack.py`: the sealed bundle of I46's protocol, `bundle.tar` byte-identical for a given commit, with
   `manifest.json` (every member's sha256, the exclusions by rule, the redactions) and `leaks.json` (the leak list,
   never filtered). The target code is packed from the pinned commit's git objects; the tooling from the packed
   commit's.
2. `holon/report.py` and `python -m holon report --milestone M3 [--check] [--results SET=DIR]`: writes
   `spec/M3/appendixA_map.json` and `docs/M3_COMPARISON.md` from the records. G1 regenerates both
   (`holon.report.regenerate_check`).
3. `holon/blind.py` and `python -m holon compare --blind DIR [--lead DIR] [--milestone ..] [--out FILE] [--threshold X]`:
   `blind_agreement` over the statuses of alpha-equivalent statements, with the matched-statement fraction; and
   `python -m holon compare --snapshot SRC --into DST`, the committed projection of a scratch tree.
4. The dry run, under `audit/blind/dryrun/`: the lead's own records regenerated into a scratch tree (M0 and M1 in
   full, M3's PAR laws outside PAR-init), projected, and compared with the lead's projection at the same base.
5. `docs/iterations/I82.md`, the report.

## The dry run (P8), step by step

1. `base` = the commit the dry run starts from (the build's code commit, clean tree).
2. Scratch `S`: copy `laws/M0`, `laws/M1` and `laws/M3` to `S/laws/`.
3. With `HOLON_BUILD_DIR=S/build`: `holon run --milestone M0 --out S/results/M0 --gen-dir S/gen/M0`; the same for M1;
   `holon run --milestone M3 --laws <every PAR law of laws/M3 whose subform is not init_chain> --out S/results/M3
   --gen-dir S/gen/M3`. Confirm that the repository's `results/` and `gen/` did not change (`git status`).
4. `holon compare --snapshot S --into audit/blind/dryrun/tree --milestone M0,M1,M3` and
   `holon compare --snapshot . --into audit/blind/dryrun/lead --milestone M0,M1,M3`.
5. `holon compare --blind audit/blind/dryrun/tree --lead audit/blind/dryrun/lead --milestone M0,M1,M3 --out
   audit/blind/dryrun/compare.json`; write `audit/blind/dryrun/dryrun.json` (base, milestones, m3_laws, the commands).

## Rules of this key

- Never special-case a law id in holon/: every law id the map names comes from data (maps_to, the ledger, the back-test
  tables, §11.8's names) or from the sidecar.
- No generator closure file changes, so no record is re-made; the outputs are deterministic.
- A leak is reported, never fixed by editing holon/ broadly: if holon/ itself leaks case-study answers, that is a
  Surprise and a Question.
- When the lead moves, merge it (a merge commit, append-only logs lead-first) and regenerate
  `docs/M3_COMPARISON.md` and the map; whoever merges second regenerates.
