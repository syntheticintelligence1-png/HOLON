# I46: the blind rerun from code, the generated comparison, and the M3 exit

Rendered from `docs/BUILD_PLAN.md` §4 I46 and row I46. Milestone M3; this key closes the M3 exit, or records why it
does not close. I82 (= I46a) built the tooling: `tools/blind_pack.py`, `holon report --milestone M3` and
`holon compare --blind`. Its "Not done" list is this key's scope.

Whitepaper sources:
- §11.7 and §11.8: the comparison with the manual analysis;
- §12 L8: hindsight, and the blind rerun by fresh agents without Appendix A;
- §15.2 M3: the published comparison.

Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. Then read:
- `docs/iterations/I82.md` and `tests_m3/test_blind.py`: the pack, the leak scan, the map and the metric;
- `docs/HUMAN_ANSWERS.md` Q9: same-family runs are labelled `same`;
- `holon/land.py`: `jobs_for`, `plan` and `apply`, the runner re-make this key reuses.

**The docstring of `tests_m3/test_blind_rerun.py` is the contract** (rules K, S, B, L, C, E and R).

## Fixed at the prereg

Do not edit these. A wrong one is a Question, plus an `instrument_inconsistency` line in `spec/M3/amendments.jsonl`.
- `spec/M3/lib/blind_rerun.json`, the protocol: the pack commit, the scope set and its strip rules, the session's
  limits, the runner re-makes, the comparison, the exit clauses and the Q9 label.
- `spec/M3/lib/blind_session.md`, the blind session's commands-only brief. It holds no outcome.
- `tests_m3/blind_scope.py`, which makes the scope set: the extraction-scope sidecars, stripped by the protocol's rules.
- `tests_m3/_i46.py`, the instrument. It is written without holon/ and tools/, and it reuses `tests_m3/_i82.py`.

## Stage 1: the prereg

The key, the sidecars, the brief, the scope tool, the instrument and the tests are pushed before anything runs. Then
open a draft PR.

## Stage 2: after the lead lands I70

The coordinator says when. Let `<P>` be `_i46.pack_commit()`, `<S>` a scratch directory outside every checkout, and
`OUT` = `audit/blind/I46/`.

1. **The pack and the scope set.**
   - Run `python tools/blind_pack.py --commit <P> --out <S>/pack` and `python tests_m3/blind_scope.py --commit <P>
     --out <S>/scope`.
   - Commit `manifest.json` and `leaks.json` under `OUT/pack/`, and the whole scope set under `OUT/scope/`.
2. **The blind session.**
   - The coordinator launches it: a fresh agent with only the brief's text and the paths `<S>/pack/bundle.tar`,
     `<S>/scope` and `W`.
   - You do not run it, and you do not read `W` while it runs.
   - Afterwards, the coordinator gives you the session's transcript. Commit:
     - `OUT/session/tool_calls.jsonl`, from `python -m tests_m3._i46 calls <transcript>`;
     - `OUT/session/run.json`: `W`, `pack`, `scope`, `pack_commit`, `family: "same"`, the transcript's sha256 and the
       number of tool calls;
     - `W/blind/log.jsonl`, as `OUT/session/log.jsonl`;
     - every file the session logged as authored, under `OUT/authored/`.
3. **The runner re-makes.**
   - Copy `W` (less `build/`, `cache/` and `pack/`) into a new repository.
   - Make one orphan commit whose message starts "CI only (not for merge)", with no `holon-ci` workflow.
   - In it, run `holon land plan --tag i46-blind-<k> --push`, then `holon land apply --from` its outputs branch onto a
     copy of the tree.
   - Edit nothing of the blind tree by hand. A job that fails is recorded, not retried with changes.
4. **The comparison.**
   - `holon compare --snapshot <the re-made blind tree> --into OUT/tree --milestone <the milestones it holds>`.
   - `holon compare --snapshot <the lead at P> --into OUT/lead --milestone M0,M1,M2,M3`.
   - `holon compare --blind OUT/tree --lead OUT/lead --milestone <the milestones the blind tree holds> --out
     OUT/compare.json`.
   - The per-rule and per-family table is the instrument's `breakdown`.
5. **The report.** `docs/iterations/I46.md` covers:
   - each prediction, held or missed;
   - the leak list, and the scope set's stripped keys;
   - the exit clauses E1-E5, with the claim scoped to the matched set and labelled `same`.

## Rules of this key

- Never special-case a law id in holon/ or tools/.
- No generator closure file changes, so no lead record is re-made.
- A disagreement is a finding about the pipeline. It is reported, never reconciled by hand.
- When the lead moves, merge it (lead-first) and regenerate what the merge makes stale.
