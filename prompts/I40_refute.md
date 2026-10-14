# I40: refutation engines, Appendix D encodings, BMC over the extracted TRANS edges, filter recomputation

Rendered from `docs/BUILD_PLAN.md` §4 I40. Milestone M3.

Whitepaper sources:
- §10.5 (the three refutation engines; every candidate re-encoded as a counter-law and checked by evaluation);
- Appendix D (the corrected encodings), Thm 6.15 (global hash injectivity is inconsistent), Cor 6.16 (local premises: the solver's ground injectivity is CF(h, S_query)), Thm 6.17 (two-sided soundness: UNKNOWN carries no conclusion);
- §10.2 (layout facts emitted as solver queries), §10.9 (witness concretization: BMC over the TRANS edges with environment moves and principal constraints, the path emitted as a Foundry or Go test, replay success a finding, failure a model defect), §9.6 (the finding filter: finding, model defect, known limitation), §8.6 (records), §10.11 (refutation budgeted per obligation, exhaustion recorded as UNKNOWN).

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` and `docs/BEND_NOTES.md` first. Then read:
- `docs/iterations/I15.md` (the site laws and S1-S3), `I20.md` (the extracted model, its step refinement and its 120 unfalsified reaches, the width laws, the differential and its view), `I21.md` (T1, T2, F-M2-38..42), `I24.md` (the PAR laws and the three PAR-weak UNKNOWNs) and `I4.md` (the provisional filter);
- the contract of I30 (`tests_m3/test_sort_types.py`, prereg `499c70b`): its typed model, Reach, witness format, counter-laws, test milestones and replay. I40 binds to that contract, never to I30's outputs;
- `holon/filter.py`, `tests_m2/_i4.py`, `holon/mreplay.py` (the M1/M2 replays and `m0_commit_sides`), `replay/M1/solidity/HolonTraceReplay.t.sol` and `replay/M2/solidity/` (the hand op tables I40 replaces).

**The docstring of `tests_m3/test_refute.py` is the contract.** It fixes the engines, the encodings, the questions Q1-Q7, the concretization rules K1-K4, the emitted tests, the replay, the final filter F1-F4, the record fields and shared files, the fixture, the CLI, the output formats, the rules, the gate and the expected amendments.

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in `spec/M3/amendments.jsonl`):
- `spec/M3/lib/refute.json`: the solver pin, the encodings, H, the environment moves, the principal table, the answer table, the concretization targets, the I21 split, the current refuter's depth and the fixture; and, computed by `tests_m3/_i40.py::sidecar_doc` on the prereg tree, the 26 witness classes, the 88 codec laws, the 8 UNKNOWN records, the 24 REFUTED records with their concretization kinds and the 120 unfalsified reaches;
- `tests_m3/_i40.py`: those computations, the final filter rule written out a second time (`expected_final_bin`), the toy replay (`toy_run`) and the hand-built rollup paths of the instrument checks;
- `tests_m3/fixtures/refute/`: `src/ToyLock.sol` in two variants on the same lines (b adds a guard on line 52), extracted at the prereg by holon-frontend-solidity/0.3, their I30-format model sidecars (test milestones T401, T402) and I40 sidecars, a byte copy of `HolonStepBase.sol` and the toy's concrete harness.

## Why this iteration matters

Every refutation HOLON has found so far came from short searches: compiled-model fills for codecs, and for the machines I15's S1-S3 (at most three prefix steps before the entry step, or two steps inserted into another entry point's witness). I20's step refinement left 120 guard reaches unfalsified, 76 of them because every targeting step ended at an earlier reach: the states behind them need several steps (a pending revert request needs a commit, a challenge and a timed-out proof; a second reinitializer call needs a first). Defects that sit behind a longer chain are invisible to the current refuter. I40 is the deep-witness engine: SMT over the Appendix D encodings, BMC over the extracted TRANS edges, and fuzzing, all of them proposers whose candidates count only through Bend-checked counter-laws on the compiled model and replays on the real code.

It also closes the filter. I4's bins are provisional: `known_limitation` was never assigned, because only BMC can show that no public path exists. I40 recomputes every record's bin.

## What the committed artifacts give (computed at the prereg)

- **26 REFUTED witness classes** (`refute.json` classes): M0 3 (L_dom_hdr domain; L_par_hdr_ssvh and L_par_hdr_v2 codec), M1 8, M2 4 (the :363 law at its three entry points, :636), the view's 7 (`results/M2/extracted_m1`), M3 4 (three cross-component codec laws differing at bytes 185..216, the sequencer-set hash; one domain law). Kinds: 5 codec, 2 domain, 19 trace.
- **88 codec laws** (M0's 8, the M3 PAR laws' 80): 78 PROVED, 7 REFUTED, 3 UNKNOWN.
- **8 UNKNOWN records**: I15's `L_sort_site_def_lci_356891e4` and `L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17`; I20's `L_sort_width_batchheadercodecv0_144_1abeb29c` and `_166_8ad80b42`; I24's three `L_par_weak_*`; I20's not-run view record `L_tag_BVH`.
- **24 REFUTED records** and their kinds by K1-K4: 14 direct, 5 commit_class, 4 bmc (L_dom_hdr, M1 and view L_nat_eta2, M3 L_par_dom), 1 go_only (L_own_txspayload). Bins at the prereg: 13 finding, 11 pending.
- **The real side, run at the prereg** (`TestInstruments`): on the real Rollup the prefix [commitBatch, challengeState, proveState after the proof window] followed by any of the six nonReqRevert actions reverts with "pending revert request"; initialize2 or initialize3 called twice reverts the second time with "Initializable: contract is already initialized"; a version-1 commit with no blob stores ZERO_VERSIONED_HASH. On the real ToyLock the seven-step chain ends in Panic 0x11 (variant a) or "late" (variant b), and fire after three steps reverts with "fire".

## Goal and deliverables (summary; the contract has the details)

- **`holon/smt/encode.py`, `holon/smt/run.py`**: the pinned z3 (4.16.0, `random_seed` 0, rlimit budgets), Appendix D's E1-E7 and NZ, all ground; layout queries for the extracted header functions; templates for the 26 classes; codec agreement queries; SMT over the hand machines for the M2 UNKNOWNs. `config/holon.json` gains the "z3" pin.
- **`holon/fuzz.py`** and **`holon/bmc.py`** (H = 8 from R0, deepening, cone-of-influence slicing, the environment moves, principal table and answer table of the sidecar; witnesses in I30's format).
- **`holon/gen/foundry.py`, `holon/gen/gotest.py`**: per-witness tests from calldata and the document's action interface, replacing the hand op tables; `gen/M3/tests/` with its manifest, regenerated byte for byte.
- **`holon/filter.py` final** (`final_bin`), records gaining `concretization`, the v2 schema gaining `known_limitation` and `concretization`, G6 over the final rule.
- **`python -m holon refute`** with the stages layouts, smt, fuzz, bmc, emit, replay, filter, `--check`, and the test-milestone options.
- **The outputs** under `gen/M3/refute/`, `results/M3/refute/`, `replay/M3/refute/` and `gen/M3/tests/`, the recomputed bins in the shared record files, and `docs/iterations/I40.md`.

## Predictions (key I40 in `spec/M3/predictions.json`)

| id | claim (short; the key has the full text) |
|---|---|
| P1 | SMT re-finds all 26 witness classes from their templates; every first candidate's counter-law is accepted by Bend and BendTT on the law's own model, with the class's signature. |
| P2 | On the 88 codec laws the solver agrees with every status: sat with an accepted candidate on exactly the 7 REFUTED, unsat on the 78 PROVED and the 3 PAR-weak. |
| P3 | Every candidate is accounted for, and 0 candidates are discarded on the 26 templates (the encodings agree with the compiled models). |
| P4 | I15's lci and 325 site laws stay UNKNOWN: SMT to 8 steps of their model is unsat (bound {steps: 8}, rlimit 200,000,000), fuzz finds nothing (both obligations hold in every reachable state). |
| P5 | I20's two width laws stay UNKNOWN: BMC shows no path to a stored value >= 2^64 within H = 8. |
| P6 | I24's three PAR-weak laws stay UNKNOWN: SMT unsat (BlobCommitHash dispatches to exactly the two getters), fuzz finds nothing. |
| P7 | The final bins: 16 finding, 4 known_limitation (L_dom_hdr, L_par_dom, M1 and view L_nat_eta2), 1 model_defect (the view's L_disch_delay_nofree), 3 pending (M1 and view L_fact_Z, L_own_txspayload), with the kinds and BMC results of the table. |
| P8 | BMC falsifies 8 of I20's unfalsified reaches (six "pending revert request" in 4 steps, two reinitializer reaches in 2) with replaying paths, and shows 22 closed reaches unreachable within H. |
| P9 | Sensitivity: on the planted ToyLock the current refuter leaves the sign-site law UNKNOWN; BMC refutes it with the seven-step chain, checked and replayed (Panic 0x11 at :53); the guarded variant has no path. |
| P10 | I21: T2's EVM half has a 1-step path that replays (ok, ZERO_VERSIONED_HASH stored at batch 1); T1's EVM half and F-M2-42 have no path within H (largest_k 8); T1's and T2's Go halves (node derivation: I39, which does not exist) and F-M2-38..41 are out of scope. |
| P11 | The emitted tests reproduce the 16 public-schedule and library sides of the 13 records the hand harnesses replayed. |

**Regressions.**
- R1: gates M0, M1 and M2 pass; M0-M2 statuses, statement hashes and witnesses are unchanged; no PROVED record changes status. (The full M3 gate fails at the prereg: its G6 finds no target commit in the linked codec document and its G4 no canary over the linked model. Its passing, after I30's gate wiring and I40's G6, is a construction check under R4.)
- R2: the M0-M2 records change only in `filter_bin`, `concretization`, `generator_sha256` and timing; no commit writing an I40 outcome path touches M0-M2 laws, models, replays, `spec/M1/`, `spec/M2/facts/`, `spec/M2/lib/`, `gen/M3/sorts/`, a frozen root or an I40 instrument, and every record file (M3's included) such a commit changes differs from its parent only in those fields (checked from git).
- R3: `holon.filter.bin_of` is still I4's rule; `final_bin` agrees with `tests_m3/_i40.py::expected_final_bin`; the only amendments are the two expected I4 ones.
- R4: the construction checks (instruments, engines, determinism, generic code, records and schema, concretization at HEAD, manifest, reach verdicts).
- R5: the view's L_tag_BVH stays UNKNOWN and not run.

## Decisions fixed at the prereg (state them in the report)

1. **NZ joins E1.** Appendix D lists ground injectivity only. Without "every K term is non-zero" an empty mapping slot authenticates any byte string in the solver, so every BMC target behind a `committedBatches` check would get a spurious path. NZ is the nz premise I26 and I27 state; it is ground and has CF's negligible-probability reading.
2. **QF_AUFBV.** §10.5 names QF_UFBV; storage maps and byte strings need arrays. No query holds a quantifier.
3. **Budgets are z3 rlimits, not seconds.** A timeout must be reproducible for the outputs to regenerate byte for byte. 200,000,000 per query.
4. **H = 8 transactions.** Environment moves (time, blobs, value, caller) are per step and do not count. The deepest existing rollup witness (I15's :363 commitState entry; I26's O25 chain) has 5 transactions.
5. **The environment is the binding's deployment.** Callers are the harness's principal table, never the proxy admin. External answers are the stand-ins' and the empty queue's. No message is enqueued (the queue is not extracted). So BMC's no_path is relative to R0, H and these tables, and says so.
6. **Concretization targets are fixed** for the four records whose witness rests on a construction (an internal-harness decoder input, an emulated reinitialization): `dom_v0_long` and `eta2_state`. The build may not choose an easier target.
7. **Known limitation is relative to the pinned code and the binding's deployment.** L_dom_hdr becomes known_limitation although I21's T1 shows 2954 mainnet commits whose 281-byte version-0 parents the chain accepted: those headers were committed by earlier implementations (deployment history, I28), and the node-side reachability is Go (I39). See Question 1.
8. **Existing laws are decided on their own models.** The re-find and the M2 UNKNOWNs read the documents their models were compiled from; no M3 law reads a hand-written fact document.
9. **The re-find runs on templates.** A class's template fixes its witness's action skeleton; the free search is BMC's. P1 measures the encodings' fidelity on every shape that has a refutation.

## Rules

- **AGENTS.md is binding.** Never edit `facts/`, `spec/M1/`, `spec/M2/facts/`, `spec/M2/lib/`, `laws/M0`-`M2`, `gen/M0`-`M2`, `replay/M0`-`M2`, `gen/M3/sorts/` or a frozen file. Do not edit another key's instruments (`tests_m3/_m3.py`, `_i24*.py`, `_i26.py`, `_i31*.py`).
- **The checker's word is final.** A solver, fuzzer or BMC candidate counts only through a counter-law Bend accepts on the law's compiled model, and a finding only through a replay on the real code. A budget exhausted is UNKNOWN with the budget and the reason.
- **Q19.** BMC runs over the extracted document; no I40 command reads `spec/M1/facts/` for an M3 question.
- **Generic code.** No target action, contract, family, law id or class id in the engines or the test generators.
- **No tuning.** H, the rlimit, the seed, the environment, the principals, the answers and the targets are fixed. A miss is a Surprise with its evidence.
- **Every BMC path obeys the environment.** At most H steps; callers only from the principal table; block.timestamp never 0, at least the deployment's clock and non-decreasing; blob hashes non-zero with top byte 0x01, at most blob_count_max; msg.value at most 100 ether. A BMC path whose replay shows an external call answering otherwise than the answer table is discarded as `env_mismatch` (verdict unknown with that reason), never a finding and never a model defect.
- **A record side fails when its replay differs.** An emitted test of a record side passes only when every step's outcome is the witness's and the claimed obstruction is checked; any difference, an external call of the real deployment answering otherwise than the record's model included, is `failed` (a model defect: the record's model chose that answer). This is what makes the view's L_disch_delay_nofree a model defect (P7).
- **Exact attempt formats.** unknowns.json states each attempt's bound and budget exactly as the contract lists them, its candidates, accepted and discarded (with the checker's output), so that no candidate is dropped silently.

## Outcome paths, narrowly

`gen/M3/refute/`, `results/M3/refute/`, `replay/M3/refute/`, `gen/M3/tests/` and the report `docs/iterations/I40.md`. Every commit that writes any of them must descend from this prereg commit, and touches no I40 instrument (`spec/M3/lib/refute.json`, `spec/M3/lib/sort_types.json`, `spec/M3/predictions.json`, this prompt, `tests_m3/test_refute.py`, `tests_m3/_i40.py`, `tests_m3/fixtures/refute/`): commit code and amendments separately from outputs.

Shared files, changed only as the contract says (not outcome paths; merge them by hand with the other M3 keys):
- the REFUTED record files of `results/{M0,M1,M2,M2/extracted_m1,M3}` (`filter_bin`, `concretization`; `generator_sha256` and timing may churn). The git test checks every commit that writes an I40 outcome path: each record file it changes differs from its parent only in those fields, and it adds or deletes no record;
- `results/casestudy_coverage.json`, `docs/CASESTUDY.md`, the bin-derived fields of `results/<M>/metrics.json`;
- `spec/schemas/result_record_v2.schema.json`, `config/holon.json` ("z3"), `spec/M2/amendments.jsonl`;
- `results/M3/summary.json`, `deps.json`, `metrics.json`, `gate_report.json`.

## Expected amendments

The final filter replaces the provisional bins on two M0/M1 records (L_dom_hdr and L_nat_eta2 become known_limitation), which two of I4's preregistered tests pin: `tests_m2/test_filter.py::TestBins::test_records_follow_the_rule` and `::test_bins_of_recorded_replays`. Each gets one `foundation_conflict` line in `spec/M2/amendments.jsonl` (iteration I4) that narrows it to I4's provisional rule on the sides, and the I40 tests check the final bins instead. Any other amendment is a Surprise. `tests_m2/test_i4_review.py`'s tamper tests rebin L_dom_hdr and L_nat_eta2 with I4's rule but assert only that G6 fails with a given reason, so they are expected to pass unchanged; if one does not, it is a Surprise.

## Coordination

- I40 depends on I30's build (the typed model, Reach, the counter-law generator, the test milestones). Build after I30 merges; until then the fixture tests and every rollup BMC witness check cannot run.
- Every REFUTED record at the build's HEAD gets a final bin, including records I25-I31 add; those are construction checks, not predictions.
- `tests_m3/_m3.py` is I24's; I40's helpers live in `tests_m3/_i40.py` and the test file.

## Risks and fallbacks

- **Solver capacity.** A BMC query over the extracted Rollup may exhaust its rlimit at some k. The result is unknown, with the largest k decided, and a predicted no_path or path misses. Never raise the rlimit or lower H after a result.
- **Encoding drift.** A candidate whose counter-law Bend rejects is discarded, and P3 misses; the encoding is fixed in the generator, never by special-casing the class.
- **I30's pipeline.** If I30's test milestones cannot run the toy, P9 is not decided and the report says so.
- **Query volume.** Every query is committed under `gen/M3/refute/smt/`. If their volume is a problem, report it; never drop queries, lower H or raise the rlimit to fix it.

## Questions for the human (raised by the prereg)

1. **Known limitation versus history.** L_dom_hdr's witness class (a version-0 header longer than 249 bytes) has no public path from the binding's deployment of the pinned code, yet I21's T1 shows 2954 such parents accepted on mainnet, committed by earlier implementations. The prereg keeps the whitepaper's reading (a construction no public entry point produces, relative to the pinned deployment) and records the history beside it. Should historical on-chain instances override known_limitation once I28 models the versioned machines?
2. **NZ.** Is adding the ground non-zero premise to E1 acceptable as part of "Appendix D exactly", given that I26 and I27 state it as a law premise?
3. **The queue.** BMC keeps the deployment's queue empty because the queue is not extracted. Paths that need an L1 message (the delay-guard reaches, L_disch_delay_nofree's class) are outside BMC's environment until I36 links the queue. Is that the intended boundary?

## Before committing

Run every suite: `tests`, `tests_m1`, `tests_m2` and `tests_m3`. Then run `holon gate` for M0, M1, M2 and M3, `python tools/freeze.py check`, and `python -m holon audit prereg` for M2 and M3.

Write `docs/iterations/I40.md`, with Done, Surprises, Questions for the human and Not done. Include:
- the re-find table (class, record, result, candidate, checker);
- the codec agreement counts;
- the UNKNOWN table with every engine's bound, budget and reason;
- the bins table (before, kind, result, after);
- the reach verdicts (all 120, with the 8 paths and their replays);
- the fixture's before and after;
- the I21 split;
- the emitted-test inventory;
- the gate lines.
