# I27: UNDO rule and static deadness, decided on the extracted real code

Rendered from `docs/BUILD_PLAN.md` §4 I27. Milestone M3. Whitepaper §5.2 (UNDO: undo pairs, residues, the obligation), §10.6 (deadness as a static check and as a certificate), Thm 6.9 (an undo residue is observable iff live), §8.4 and §10.4 (the UNDO law schema and proof route), App. E (UNDO row), App. F (the `undo_bvh` sketch), §2.3 (the residue table), §11.6 D5 and §11.8 (`L_undo_CSR`, `L_undo_BD`, `L_undo_BVH`, `L_undo_cancel`). Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` and `docs/BEND_NOTES.md` first, then `docs/iterations/I20.md`, `I22.md`, `I60.md` and their catalog reviews, and the contracts of I24 and I30 (the docstrings of `tests_m3/test_derive_par.py` and `tests_m3/test_sort_types.py`).

**The docstring of `tests_m3/test_undo.py` is the contract.** It fixes the registers and terms (U1), the undo pairs (U2–U4), the residues and residue bases (U5, U6), the static deadness rules (D1–D3), the analysis document and its CLI, the laws (L1, L2, the IR, the `undo` term, the semantics of `obs`, `NZ` and `uhit`), the decision procedure, the replay report, the records, the classification and the back-test, the sensitivity checks and the gaps.

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in `spec/M3/amendments.jsonl`):
- `spec/M3/lib/undo.json`: the UNDO sidecar (the I30 model sidecar it builds on, the observation, the `nz` premise, the search budget, the frozen back-test map);
- `spec/M3/lib/undo_basis.json`: every pair, residue, classification, law and predicted outcome on the rollup document, and the mutant's analysis. It was computed by `tests_m3/test_undo.py::undo_basis_doc`, which writes the rules out a second time, independently of `holon/`;
- `tests_m3/fixtures/undo/`:
  - the planted `ToyUndo` (`src/`) and its drop variant (`drop/src/`, the same file without its one `delete pins[i];` line);
  - their extraction sidecars and the documents holon's frontend extracted at the prereg;
  - their bindings, the I30-format sidecars (`sort_types_toy.json`) and the UNDO sidecars (`undo_toy.json`), and the toy harness `HolonToyUndoStep.t.sol`;
  - `mutant/`: the pinned Rollup without line 447, its extraction sidecar and its extracted document;
- `tests_m3/fixtures/undo/harness/*.txt`: byte copies of the I20 step harness taken at the prereg, for the test's independent replay.

## Why this iteration matters

The M1 UNDO laws are statements over the hand abstraction. I20 re-decided them over `gen/M2/extracted/m1_view.json`: the hand abstraction minus the guard_missing requires. Both independent catalog reviews of the mutation track (`docs/iterations/I22_catalog_review.json`, `I60_catalog_review.json`) found what follows from that. No law reads the real code's writes, so every drop_delete and swap_cursor mutant of the real Rollup is unkillable by construction, and the mutation rate measures its own design.

I27 decides UNDO on the extracted real code (Q19):
- the pairs, residues and static classes are computed from the extracted transitions (written values, deletes, guards, events);
- each law is stated over I30's typed model with `Reach`;
- the M3 pipeline decides it;
- every REFUTED law's witness replays on the real contract.

A real-code defect such as a dropped delete must move a law. The Sensitivity clause makes that a test twice: on a planted toy, at the kernel and on the real toy, and on the real Rollup, statically.

## What the extracted side shows (computed at the prereg; the contract has the rules)

- **Undo pairs.** There are five:
  - (commitBatch, revertBatch), (commitState, revertBatch) and (commitBatchWithProof, revertBatch). All three criteria of §5.2 fire for each:
    - revertBatch's guard reads the committedBatches entry that commit allocates;
    - it moves the lastCommittedBatchIndex cursor back by the 1 that commit added;
    - it emits RevertBatch(uint256,bytes32) against CommitBatch(uint256,bytes32).
  - (addChallenger, removeChallenger) and its reverse, through the guard criterion.

  Two candidates restore a register but meet no criterion: (challengeState, proveState) and (commitBatch, finalizeBatch). (challengeState, setPause), the pair of M1's L_undo_cancel, is not even a candidate: setPause writes inChallenge and challenges only under `_status && inChallenge`.
- **Residues at lastCommittedBatchIndex + 1.** revertBatch leaves batchBlobVersionedHashes, batchDataStore and committedStateRoots behind commitBatch, which is the plan's {CSR, BD, BVH}. The plan's fourth residue, the tag, is I30's generated ghost, not a register (gap G2).
- **Static classes.**
  - committedStateRoots is dead. Every reader's key is the cursor.
  - batchBlobVersionedHashes is live. Its 17 readers start with commitBatch's guard :261.
  - **batchDataStore is live**, through one reader: the declared view `batchInsideChallengeWindow` returns `batchDataStore[i].finalizeTimestamp > block.timestamp` (Rollup.sol:709-711). Every transactional reader is excluded (D1–D3).

  The plan, the whitepaper's D5 and M1's `L_undo_BD` (PROVED) all say BD is dead. On the real code a declared view exposes it, and Thm 6.9 observes outputs. Compiler-generated getters stay unobserved, as in M1 (gap G4).
- **Laws.** 8: five pair laws and three residue laws. Predicted: 3 PROVED (the CSR residue and the two challenger pairs) and 5 REFUTED.

## Goal and deliverables (summary; the contract has the details)

- **`holon/rules/undo.py`** (U1–U6) and **`holon/analysis/deadness.py`** (D1–D3), generic. `python -m holon undo` writes `gen/<M>/undo/<model>.json`, with `--facts` for planted documents, `--classify` and `--backtest`.
- **Rule UNDO** in the rules registry, with subforms `pair` and `residue` and catalog **holon-rules/1.3**. That catalog holds holon-rules/1.1's PAR and I30's SORT producers, as the same objects. M3 derives with it, and test milestones take it through `--catalog`.
- **The trace section** `gen/M3/undo/models/<model>.bend` over I30's typed model. It holds:
  - the return data of every action whose document records returns;
  - `obs` and `run`;
  - `set_<family>`;
  - per law, `undo_<x>` and `uhit_<x>`.

  The IR term `undo`, hashed through the ref `undo:<id>`, is an additive change to the IR 0.3 schema.
- **Index-relative noninterference.** The proof generator for dead residues builds bisimulation step lemmas per action for the relation "equal outside F at k, with k above the cursor and the cleared markers zero". The map lemmas `set_d`/`nth_d` go into the core library, proved, never assumed. A separate restore proof covers pairs without residue.
- **Refutation and replay.** Pair and residue witnesses use I30's search with the sidecar's budget, plus continuations. A residue witness is realized by one of its pairs, and the model checks that the divergence is F's alone. Both runs (with and without the pair) replay on the real contract through the I20 step harness (`replay/M3/undo/report.json`). G6 binds every REFUTED UNDO record to a passed entry.
- **Records**, the static/kernel classification with a gate warning `GUNDO` on any disagreement, and the back-test against the M1 UNDO laws.
- **The sensitivity checks:** the toy at T271/T272, and the Rollup mutant (static).
- **`docs/iterations/I27.md`**, with a prediction table.

## Predictions (key I27 in `spec/M3/predictions.json`)

| id | claim (short; the key has the full text) |
|---|---|
| P1 | Exactly 5 undo pairs: the three commit pairs with criteria [cursor, event, guard] restoring committedBatches (zero; pin :311) and lastCommittedBatchIndex (cursor), and the two challenger pairs (guard). Exactly 2 rejected: (challengeState, proveState) and (commitBatch, finalizeBatch). |
| P2 | Residues: commitBatch {BVH, BD, CSR}, commitState {BD, CSR} (its BVH write is an identity copy), commitBatchWithProof {BVH, BD, CSR}, challengers none. 3 residue bases (revertBatch; cursors [LCI]; zero [challenges, committedBatches]). |
| P3 | Static: CSR dead (4 readers, all D1), BVH live (17 readers, first commitBatch :261), BD live through exactly the view batchInsideChallengeWindow (15 others excluded: 6 D1, 6 D2, 3 D3). |
| P4 | Exactly 8 UNDO laws with the ids, bases, binders, claim and refs of the contract. |
| P5 | CSR residue PROVED and inhabited; BVH residue REFUTED (divergence at a commit); BD residue REFUTED (batchInsideChallengeWindow returns true vs false). |
| P6 | The three commit pair laws REFUTED (divergence at a reader of a live residue); the two challenger pair laws PROVED. 3 PROVED, 5 REFUTED, 0 UNKNOWN. |
| P7 | All 5 REFUTED witnesses replay on the real Rollup (holon's report passed; the independent replay agrees). |
| P8 | Exit: static and kernel classes agree on all 8; `holon gate --milestone M3 --checks G1` (on a copy) lists no GUNDO warning. |
| P9 | Back-test: L_undo_BD's analogue REFUTED where M1 had PROVED; L_undo_cancel has no analogue (an open rule gap). |
| P10 | Toy: T271 has 3 laws, all PROVED; T272 (one delete dropped) has the same pair law REFUTED and a new pins residue law REFUTED; both witnesses replay on the real drop toy, first differing at a commit that reverts "pinned" with the pair and succeeds without it. |
| P11 | Rollup mutant without :447: committedBatches becomes a fourth, live residue (14 readers, among them :311); the guard criterion drops; BD's live readers grow from 1 to 6; CSR stays dead. |

**Regressions.**
- R1: Gates M0–M2 pass. The M1 UNDO records and I20's differential are unchanged.
- R2: the analogues of L_undo_CSR (PROVED) and L_undo_BVH (REFUTED) keep their outcomes.
- R3: the PAR and SORT laws keep their statuses and change only in `rule_catalog_version`.
- R4, R5: construction checks, among them:
  - Bend, run by the test on a copy of `gen/M3`, accepts every UNDO proof, nonvac proof and counter-law, each importing its one-law `LAWS.bend`; no escape hatch;
  - the exit's "or the gate warns": a copy whose CSR residue record is made UNKNOWN gets that law, and only it, as a disagreement that blocks shadow and window, and exactly one GUNDO warning from `holon gate --milestone M3 --checks G1`. Every M3 gate report carries a `warnings` list;
  - no file under `holon/` names an I27 law id, undo id or `undo:` ref.

## Deviations from the plan, decided at the prereg (state them in the report)

1. **BD is predicted live, not dead.** The plan's "statically, CSR and BD are dead" and its regression "L_undo_BD keeps its outcome" were written over the hand abstraction, which has no view functions. On the extracted document the declared view `batchInsideChallengeWindow` returns the residue. The observation is Thm 6.9's (outputs, success or revert), so including the view's return is the stricter choice; excluding it would choose a weaker observation to fit the plan. The BD analogue is therefore a prediction of difference (P9), not a regression. Compiler-generated getters stay excluded, as M1 excluded them (every family is public, so including them would make every residue live by construction).
2. **The tag is not a residue** (gap G2). It is a ghost of I30's typed model (Prop 6.19: never read by real code). O26 is decided by I30's as_member laws.
3. **Index-relative residue laws, not M1's whole-family form.** M1's `L_undo_CSR` states that the entire committedStateRoots family is noninterfering. That is true of the hand model, which never reads CSR. It is false of the real code, whose commit reads `committedStateRoots[lastCommittedBatchIndex]` (Rollup.sol:314). The residue law relates states that differ at one key above the cursor, as the plan's deliverable ("index-relative noninterference using the set_d and nth_d core lemmas") requires. The back-test compares outcomes by the frozen map, not α-equivalence: no α-equivalent of the M1 statements holds on the real code.
4. **The `nz` premise.** Unwritten slots read 0, and revertBatch's `committedBatches[i] == keccak256(header)` admits a header whose hash is 0. With hashes as law parameters (I30), a hash table that maps some key to 0 would let revertBatch move the cursor past a residue. Every UNDO law therefore assumes that no hash its steps compute is the zero word. This is a local, satisfiable premise like CF(h, S) (Cor 6.16), and every real witness satisfies it.
5. **A planted mutant of the real Rollup is a static check only.** Deciding laws on it would need a mutated deployment in the step harness. The kernel-level flip, with replay, is the toy's.
6. **L_undo_cancel is a back-test miss** (gap G5), as the plan foresaw ("otherwise it is a back-test miss").

## Rules

- **AGENTS.md is binding.**
  - Never edit `facts/`, `spec/M1/`, `spec/M2/facts/`, `spec/M2/lib/`, `laws/M0`–`M2`, `gen/M0`–`M2`, `results/M0`–`M2`, `replay/M1`, `replay/M2` or a frozen file.
  - I20's differential over `m1_view` is not re-decided.
- **Q19.** No hand-written fact document is read by `holon undo`, `derive`, `run` or `replay` for UNDO. The back-test alone reads `laws/M1/L_undo_*` and `results/M1/L_undo_*`.
- **No special-casing.** `holon/rules/undo.py` and `holon/analysis/deadness.py` name no action, family, contract, span or law id.
- **The real contract decides replay.** A witness that does not replay is a model defect (§9.6), never a pass.
- **No tuning, no skips.**
  - The sidecars and the search budget are fixed.
  - A missed prediction is a Surprise with its evidence.
  - A static/kernel disagreement is a Surprise, and it blocks window and shadow generation for that law.

## Outcome paths, narrowly

`laws/M3/L_undo_`, `results/M3/L_undo_`, `gen/M3/laws/L_undo_`, `gen/M3/proofs/L_undo_`, `gen/M3/L_undo_`, `gen/M3/undo/`, `results/M3/undo/` and `replay/M3/undo/`. Every commit that writes any of them must descend from this prereg commit.

Files several M3 keys write are not I27's outcome paths, and the audit does not order them for I27:
- `laws/M3/REGISTRY.json` and `laws/M3/DERIVATION.json`;
- `results/M3/summary.json`, `deps.json`, `metrics.json`, `metrics_timing.json`, `gate_report.json` and `gate_timing.json`;
- `spec/bindings/M3.json`, `gen/M3/coverage.json` and `gen/M3/core/` (the map lemmas);
- the typed model `gen/M3/sorts/models/` (I30's path), if the model generator must change;
- the IR 0.3 and record v2 schemas (the additive `undo` term and record fields).

Merge them by hand with I24, I30 and I31.

## Coordination

- **I24 and I30 merge before I27 builds.** I27 binds to their preregistered contracts, not to their outcomes:
  - the M3 catalog (`holon-rules/1.1`, and I30's SORT catalog);
  - I30's typed model, `Reach`, refuter, witness format, step-harness replay and test-milestone sidecars.

  Adding UNDO bumps the M3 catalog, so every PAR and SORT law's `rule_catalog_version`, which is hashed, changes. Record those statement changes as the statement lifecycle requires (R3 checks that nothing else changes), and report them.
- **Don't edit `tests_m3/_m3.py`** (I24's). I27's helpers live in its test file.

## Risks and fallbacks

- **The CSR noninterference proof** quantifies over every continuation of the 33-action extracted model, with words and maps. If the generator cannot close it, the law stays UNKNOWN with the attempts. P5, P8 and R2 then miss and are reported; the proof is never weakened by adding a premise.
- **The commitState pair** can diverge only through the view, at a timestamp between the two commits' windows. If the search budget does not reach it, the law is UNKNOWN with its bound and P6 misses. Never widen the budget after a result.
- **Kernel cost.** As for I30: a counter-law that Bend accepts but BendTT cannot check within budget is recorded with its kernels as they are, and the miss is reported.

## Questions for the human (raised by the prereg)

1. **View outputs as observations.** Thm 6.9 observes outputs, so a declared view's return counts and BD is live. Should UNDO observe transaction outcomes only (status, revert data, logs, external calls), as M1's "transaction outcomes" wording may be read? Under that reading, BD would be predicted dead and P3, P5, P8 and P9 would change. This prereg takes the stricter reading, and the build follows it unless the human answers otherwise before the build starts. The predictions are not edited either way: a different answer becomes an amendment in `spec/M3/amendments.jsonl`, and the affected predictions are reported as misses caused by the answer.
2. **Self pairs** (gap G1). Should a later iteration split an action by the branches its arguments select, so that setPause(true)/setPause(false), the pause and its undo, is detected? It would also give L_undo_cancel a route.
3. **Catalog churn.** Each new M3 rule bumps the catalog version, and with it every earlier M3 law's statement hash. Should a law instead carry the catalog version that introduced its (rule, subform)?
4. **The `nz` premise.** Is a nonzero-hash premise per law acceptable in the assumption ledger, beside CF?

## Before committing

Run every suite: `tests`, `tests_m1`, `tests_m2` and `tests_m3`. Then run `holon gate` for M0, M1, M2 and M3, `python tools/freeze.py check`, and `python -m holon audit prereg` for M2 and M3.

Write the report in `docs/iterations/I27.md`, with Done, Surprises, Questions for the human and Not done. Include:
- the pair, residue and classification tables;
- the law outcome table, with witnesses, replays and kernel times;
- the back-test;
- the toy and mutant sensitivity;
- the classification file;
- the gate lines.
