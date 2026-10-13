# I30: Sorts III: nominal types, hole-free coercions, generated ghost tags

Rendered from `docs/BUILD_PLAN.md` §4 I30. Milestone M3; SORT enters M3 with I30 (lead decision). Whitepaper §7.8 (sorts compiled to Bend types), Thm 6.18 (sorts as types: freezing, one type per sort, coercion proofs, localization), Prop 6.19 (ghost-tag augmentation and exactness), §5.6 (SORT), §7.1–§7.4 and §7.7 (grammar, affine rules, writer provenance, unions, inference), §8.3 ("union register → ghost-tagged sum"). Closes V3. Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` and `docs/BEND_NOTES.md` first, then the reports of I13, I15 and I20 (`docs/iterations/I13.md`, `I15.md`, `I20.md`).

**The docstring of `tests_m3/test_sort_types.py` is the contract**: inputs, the sort pass over extracted documents (E1–E5), the nominal types (N1–N9), generated ghost tags and taint (G1–G4), member reads (M1–M4), realizations (Z1), coherence (C1–C3), law ids, the `coerce` IR term, the derivation, the typed model and its ghost section, the CLIs, proofs and refutation, records, replay, the refinement of the typed model and the gate.

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in `spec/M3/amendments.jsonl`):
- `spec/M3/lib/sort_types.json`: the documents I30 types, the seeds, the binding and the search budget;
- `spec/M3/lib/sort_seeds.json`: the only seeds of the sort pass over extracted documents (EVM semantics only);
- `spec/M3/lib/term_size.json`: the term-size measures, the budget of 1,000 terms and the 1.5× cone ratio;
- `tests_m3/fixtures/sort_types/`: toy contracts (`src/ToyTypes.sol`, `src/ToyClock.sol`) extracted at the prereg by holon's Solidity frontend, their sidecars and seeds, and a byte copy of the I20 step harness for the test's independent replay.

## Why this is a redraft

The first I30 prereg (held, never merged) decided every M3 law over the hand-written `spec/M1/facts`. That violates BUILD_PLAN §2.3 and the delegated answer Q19 (`docs/HUMAN_ANSWERS.md`): extracted facts are the input of every M3 law, and a waiver never applies where an extracted document exists. I20 (merged at `04e2293`) adopted the A19 extraction of the rollup, `spec/M2/facts/morph_rollup.extracted.json`. This prereg binds I30 to that document and to the model I20 compiles from it, and keeps every tightening the first prereg's reviewer made: the exact PROOF.bend set of the term budget, the model import of the cone ratio, the replay-entry checks, the Panic checked on both sides, toy witnesses of designed shapes, typed operations named, the escape-hatch scan of `gen/M3`, the taint mutation in both directions and exact corpus counts.

## Goal

Infer refined sorts on the extracted rollup document and compile them into its model: one nominal Bend type per refined sort, typed affine operations allowed only by the §7.2 table, and coercions that return `Maybe` instead of carrying a hole:
- `realize : SDur → Maybe Dur` at every sign site (the model reverts with Panic 0x11 on `None` where the code's arithmetic is checked);
- `as_member : Tagged → Tag → Maybe σ` at every read of a union family that the code copies into a write that assumes a member;
- `reinterpret : Idx_fin → Idx_inc → Maybe Idx_inc` where a guard reads a cursor written by another action family.

Each coercion premise becomes one per-site law, ∀s ∈ Reach. is_some(coercion), so every SORT failure is localized to a site (Thm 6.18). Ghost tags are generated from the frozen unions, never hand-written, and a taint check proves that no ghost reaches real code (Prop 6.19: the augmentation adds no behaviour).

## What exists, and what the extracted side lacks

- **The document** (`spec/M2/facts/morph_rollup.extracted.json`, sha256 `a38d416c…`): 33 actions over 31 raw storage families, every guard reach, implicit check, panic, call, write, memory store, event and loop record, in I19/A19's term language. It has no hand-written ghost.
- **I20's model** (`gen/M2/extracted/model.bend`, `holon.machine` and `holon.machine_bend`): `chk_`/`post_`/`step_` per action over `HStore` and an environment `HEnv`. Bend checks it, but it states no law. **It lacks what I30 needs:**
  - **No Reach predicate.** I20's width laws stayed UNKNOWN for this reason.
  - **Writes inside loop records are not compiled.** `step_revertBatch` and `step_challengeState` return the state unchanged. Both the O26 witnesses (a commit, its revert, the recommit) and the :363 witnesses (a challenge, then a late commit) need them.
  - **Words are single Nats, and the kernel normalizes them in unary.** At this prereg, `Nat.div(Nat.pow(2n, 192n), Nat.pow(2n, 190n)) == 4n` by `{==}` did not finish in 300 s under the pinned bend. Every commit reads a header word of about 2^192. No counter-law over that representation can be checked.
  - **Loops and memory are left to the environment.** The model's `unk` table holds 21 terms (listed in its header): loop outcomes, carried and count values, and memory regions built by loops. Among them are the blob-hash region and count that the version-2 aggregate hashes. A Reach over that environment admits transitions the code cannot make. The M3 model computes them; only what A-env makes free stays in the environment.
- **I13's sorts are over the hand facts.** I13's pass has adapters for holon-facts/0.1 and 0.2 only. An extracted document needs a holon-facts/0.3 adapter. I13's frozen documents (`gen/M2/sorts/`) are not an input of I30: they rest on hand-written facts.
- **The queue is not extracted.** The delay guards read `IL1MessageQueue.getFirstUnfinalizedMessageEnqueueTime()`, an environment term (A-env). The finalization cursor that I15's coherence obstruction typed is another contract's storage, and no adopted document holds it. The window declaration marks `qpend`, `qlen` and `enq` as external.

So I30 builds, generically, both the substrate and the typing. Nothing below names Morph.

## Deliverables

**A. The extracted substrate** (none of it names a target):
- **The holon-facts/0.3 adapter of `holon sorts`** (E1–E5): `gen/M3/sorts/{constraints,assignment,conflicts,unions,unresolved}.json` over the sidecar's documents, with the frozen M3 seeds. I13's solver, cores, unions and writer labels are reused. Writing the assignment is `holon sorts`' job alone, before typing.
- **The M3 model of a transitions document** (`holon model --milestone M3`; N8, N9):
  - words the kernel evaluates in polynomial time;
  - every loop record computed (its checks, carried values, writes and memory), and only A-env terms in the environment;
  - `Reach` from the binding's deployment, with the hash functions as law parameters;
  - the initial state, with the deployment's preimages (`<model>.init.json`).
  
  `--untyped` writes the same machine without the sort section; it is P8's baseline. The M2 model is not regenerated: M2 outputs stay byte-identical.
- **Refutation over the typed model:** I15's stages S1–S3 with the key's budget. Witnesses are steps with arguments, calldata and environment, plus real hash tables. Counter-laws are checked by Bend and BendTT.
- **Replay of raw witnesses** on the real contract through the I20 step harness (`replay/M3/sorts/report.json`), comparing outcomes and every external call's answer.
- **The typed model as an evaluator** for `holon fragments` (R5: `results/M3/sorts/refinement.json`).

**B. Typing and the laws:**
- **`holon/rules/sort.py`:** the producers of the subforms `realize`, `as_member` and `reinterpret`, registered for M3 and later and for test milestones T<n> with n ≥ 30. M2 keeps I15's SORT/site and I20's SORT/width, and `laws/M2` reproduces byte for byte.
- **The sort section of the M3 model generator:**
  - the nominal types;
  - the typed operations;
  - the `Maybe` coercions;
  - the generated companions, with their ghost steps below the marker;
  - no `tags_exact`.
- **`holon types`:** writes `gen/M3/sorts/types.json` and `taint.json`. An ill-sorted operation or a taint violation is a `FactsError`, exit 2.
- **`mproofs.tag_exact`:** an induction over Reach relating each union companion to its member function.
- **The `coerce` IR term:**
  - its schema entry, `render_term` and the `coerce:<id>` ref;
  - the ghost section `coerce_<x>`/`chit_<x>`.
- **`holon termsize`:** writes `gen/M3/sorts/term_size.json` and the untyped baseline under `gen/M3/sorts/untyped/`.
- **The outputs:**
  - the M3 records `results/M3/L_sort_*.json`;
  - the replay report;
  - the refinement record;
  - the gate M3 wiring (G1 regenerates the sorts, types, derivation, models and term size).
- **`docs/iterations/I30.md`.**

The build may run in two halves, as I20 did: A (substrate), then B (typing and laws), with an integrator.

## Predictions (key I30 in `spec/M3/predictions.json`)

| id | claim |
|---|---|
| P1 | The as_member law at commitState's recommit read (`L_sort_tag_rollup_279_e01ea84a`: first read at Rollup.sol:279, used at :285, copied into the write site :359) is REFUTED. Its witness is a checked counter-law: an O26 path from the deployment (the first commit of the batch may carry a blob or not: App. F2), with real hashes, the key of every header the trace loads among them. It replays on the real contract with every step succeeding and every external call agreeing. |
| P2 | The as_member law at commitBatchWithProof's recommit read (`L_sort_tag_rollup_406_e01ea84a`: :406 inside the if at :405, assigned at :407) is REFUTED on an O26 path through the stored branch, and its witness replays. |
| P3 | The plan's delay-guard reinterpretation is not derivable on the adopted extracted documents. The guards read the queue only through an external call, so there is no coherence obstruction on the rollup and no `L_sort_reinterpret_` law over it. `types.json` lists exactly the three external guards (commitBatch guards[8] :265, commitBatchWithProof guards[2] :398, commitState guards[9] :283). |
| P4 | The derivation finds exactly two member reads, with the contract's bases, site :359, hits `writes[2]` and member function `version == 2 ? Dig[Agg] : Dig[VH]`. It derives exactly three I30 laws on the rollup. commitBatch's :261 read, finalizeBatch's delete and importGenesisBatch's write are not member reads. |
| P5 | The sort pass with EVM seeds only gives `batchBlobVersionedHashes` the union `Dig[Agg] + Dig[VH]`, with one union entry. It gives `proofWindow` Dur and `challenges.startTime` Time, and an empty provenance. Exactly one sign site exists: `…:Rollup.sol:363:4a64383b`, SDur, checked, entry points the three commits. |
| P6 | Taint violations: 0. The document has no hand-written ghost. It has exactly one generated companion, and nothing above the ghost marker names it. `taint.json` names the committed model and its sha256. |
| P7 | Every I30 law over the rollup has at most 1,000 law terms (the sidecar's measure: a literal list counts as one term). The report lists exactly the PROOF.bend files that discharge each law; they import only Base, the typed model, `gen/M3/core` and their law, so no proof module escapes the measure. |
| P8 | The typed :363 realize law's cone is at most 1.5× the cone of the same site's untyped obligation over the untyped M3 model: `gen/M3/sorts/untyped/laws/L_sort_site_rollup_363_4a64383b/LAWS.bend`, one law naming `M.site_rollup_363_4a64383b`, against one law naming `M.coerce_realize_rollup_363_4a64383b`. |

**Regressions.**
- **R1:** L_tag_BVH (M1) is untouched, together with its `b_tags_exact` binding and its UNKNOWN in I20's differential.
- **R2:** its analogue (P1's law) is REFUTED, with a three-step witness of L_tag_BVH's shape: commitBatch (with or without a blob), revertBatch of batch 1, commitState, with the versions on different sides of 2.
- **R3:** the :363 realize law is REFUTED at the three commits, with Panic 0x11 located at Rollup.sol:363 on the real contract, and on the model as the failure of that realization check (`model_check` `<action>#…Rollup.sol:363#1` in the replay entry).
- **R4:** M0, M1 and M2 are not regenerated, and their gates pass.
- **R5:** the typed model, used as `holon fragments`' evaluator, reproduces I20's refinement exactly: 460 traces, 3013 steps, 8894 storage comparisons, 0 disagreements, the same per-action statuses and I20's panics (:363 on 27 steps, :368 on 2, :439 on 2, :636 on 6); the record's `evaluator_sha256` is the committed typed model's.
- **R6:** the construction checks of the contract.

## Expected witnesses (context, not scored)

- **P1/R2:** `[commitBatch(version 0 or 1, one blob or none, parent = genesis), revertBatch(batch 1, 1)]`, then `commitState(version 2, no blob, parent = genesis)`. The callers come from the deployment: an active submitter, and the owner for the revert. The answers come from the deployment's dependencies.
  - The test's instrument replayed exactly this trace, as raw calls, at the prereg: ok, ok, ok.
  - That is L_tag_BVH's M1 witness, already replayed in M1, so it adds no new information.
- **P2:** `[commitBatch(version 2, one blob), revertBatch(batch 1, 1)]`, then `commitBatchWithProof(version 0 or 1, no blob)`.
  - The last step comes after the rollup delay, so that `rollupDelay` holds.
  - It passes the header the commit builds and a proof the deployment's verifier accepts.
- **R3:**
  - commitBatch: `[commitBatch, challengeState(1)]`, then `commitBatch` after start + W.
  - commitBatchWithProof: the same, at a time that also passes the delay.
  - commitState: by S3. A commit and its revert are inserted, so that a stored hash exists for the recommitted batch.

## The toy (`tests_m3/fixtures/sort_types/`, test milestone T30)

`ToyTypes.sol` has five laws, known by construction:

| law | site | expected |
|---|---|---|
| `L_sort_tag_toytypes_72_6ff34ce4` | recommit under any version | REFUTED |
| `L_sort_tag_toytypes_83_33f98e53` | keepg, guarded by `v == vg[k]` | PROVED by `tag_exact` |
| `L_sort_realize_toytypes_100_941d10c2` | `W + start - block.timestamp` | REFUTED |
| `L_sort_realize_toytypes_107_f64bac2d` | `block.timestamp - start` after its require | PROVED by `coercion_guard` |
| `L_sort_reinterpret_toytypes_133_01841ea6` | `pendingQueueIndex` read by commitQ's delay guard | REFUTED |

- `sweep` writes inside a loop.
- `ToyClock.sol` holds `block.timestamp + block.timestamp`, which `holon types` must refuse.
- The toy's seeds add one lexical seed on family names ending in `QueueIndex`. That is the only way its cursors become indices: on M3 no seed names anything.

## Rules

- **AGENTS.md is binding.**
  - Generate, never hand-write: laws come only from `holon/rules`, with `DERIVATION.json`, and fixes go into generators.
  - Never special-case a law id, span, action, family or register. `TestGenericCode` checks this, including the toy's and the rollup document's identifiers.
  - Witnesses come from the compiled model. No holes, `@unsafe`, `def f?` or foreign imports.
- **Q19.**
  - No I30 command reads `spec/M1/facts/`, `facts/`, `spec/M1/lib/` or `gen/M2/sorts/` for M3.
  - The binding's deployment parameters (read by `replay/M2/fragments.json` from the M1 facts' initial values) are configuration of the replay deployment, not facts. Say so in the report.
  - Do not write a waiver.
- **Freezing (Thm 6.18).**
  - `gen/M3/sorts/assignment.json` is written by `holon sorts` only.
  - A type error is reported, never fixed by an assignment or a seed.
  - Never edit `gen/M2/sorts/`.
- **No tuning.**
  - The seeds, search stages and budgets are the sidecar's and the key's.
  - A miss is a Surprise reported with its evidence.
  - Do not edit the sidecars, the toys or the harness copy.
- **Hash tables are parameters.**
  - keccak256 and sha256 are binders of the law, one table per trace, never per-step environment.
  - A witness's table holds the real hash of each key, and the test checks it.
- **The environment of a witness is the deployment's.**
  - Every external-call answer must be what the deployment's dependencies answer; the replay and the test compare them.
  - A search may propose answers it saw in I20's corpus run (hints, never evidence).
- **M0, M1 and M2 do not change.**
  - `gen/M0` and `gen/M1` are byte-identical, and so is `gen/M2/extracted/model.bend`.
  - `holon derive --milestone M2` reproduces `laws/M2`.
  - The M1 model keeps its `tags_exact`, bound by `spec/bindings/M1.json`.
- **Determinism.** Sorted keys, fixed seeds, no timestamps, byte-identical regeneration.

## Risks and fallbacks

- **Kernel cost.** The I20 model's whole-Reach cone is 717 of its 799 kernel entries and 6,860,920 characters (`spec/M3/lib/term_size.json`, context). That is 40 times the hand model's :363 law, and BendTT's cost is superlinear in this size (`docs/BEND_NOTES.md` §3).
  - If a counter-law checks under Bend but BendTT cannot check it within the gate's budget, record it with its kernels as they are. A law that is not checked by both kernels misses P1, P2 or R3; report it under Surprises.
  - Slicing Reach by the actions a witness uses is a generic option, if Bend can state it soundly.
- **Term size.** On a blowup, keep the untyped site form for the affected site, labelled "untyped sort obligation" (the plan's fallback). P7 and P8 then miss, and that is reported.
- **No witness within the budget.** The law is UNKNOWN with its bound, and the prediction misses. Never widen the budget after seeing the result.

## Decisions for the lead (state them in the report; none blocks the build)

- **P3 is a preregistered gap**, not the plan's "REFUTED": the queue's cursor is reached only through an external call on the adopted documents.
- **No lexical seeds on M3.** `spec/M3/lib/sort_seeds.json` holds EVM-semantics seeds only, so the rollup gets no `Idx`/`Cnt` sorts and no writer labels; I13's lexical seeds read the docs of hand-written facts, which an extracted document does not carry. Any SORT obligation that needs an index or count sort on the rollup is therefore out of I30's reach; say which ones under Not done.
- **Deployment parameters.** The binding's deployment (Reach's initial state, the real side of every replay) takes F, W, D, t0 and r0 from the M1 facts' initial values; I30 treats them as configuration, not law input.
- **Scope.** The extracted substrate (deliverables A) is part of I30.

## Coordination

- **Outcome paths are narrow and I30's own:**
  - `gen/M3/sorts/`;
  - `laws/M3/L_sort_`, `gen/M3/laws/L_sort_`, `gen/M3/proofs/L_sort_`, `gen/M3/L_sort_`;
  - `results/M3/L_sort_`, `results/M3/sorts/`;
  - `replay/M3/sorts/`.
  
  Every commit that writes any of them must descend from this prereg commit.
- **Files several M3 keys write are not I30's outcome paths:** `laws/M3/REGISTRY.json`, `laws/M3/DERIVATION.json`, `results/M3/summary.json`, `deps.json`, `metrics.json`, `gate_report.json`, `spec/bindings/M3.json`, `gen/M3/coverage.json`, `gen/M3/core/` and, if the build registers a ledger bundle, `spec/M3/ledger.json`. Write nothing else outside I30's outcome paths: in particular no copy of the typed model under `gen/M3/model/` (law files and proofs import it from `gen/M3/sorts/models/`, and the tests check it). Merge them by hand with I24 and I41.
- **Bindings.** `tests_m2/test_target_agnostic.py::TestByteIdentity::test_bindings_unchanged` pins `spec/bindings/` except `M2.json`. The first M3 key that writes `spec/bindings/M3.json` amends it (`foundation_conflict`, as I15 did for M2).
- **Shared code.** The M3 model of the rollup is the typed one. If another M3 key's laws run on the rollup, they import it, and their statuses must not change; report any that do.
- **Don't create `tests_m3/_m3.py`.** It belongs to I24's redraft; I30's helpers live in its test file.

## Before committing

Run every suite: `tests`, `tests_m1`, `tests_m2` and `tests_m3`. Then run `holon gate` for M0, M1, M2 and M3, `python tools/freeze.py check`, and `python -m holon audit prereg` for M2 and M3.

Write the report in `docs/iterations/I30.md`, with Done, Surprises, Questions for the human and Not done. Include:
- the sorts of the extracted rollup, and how they compare with I13's on the hand facts;
- the derivation table (law, subform, site, entry points, hits);
- the types, coercions and companions;
- the taint report;
- the outcome table, with witnesses, replays and kernel times;
- the term-size table, typed against untyped;
- the refinement record;
- the gate lines.

Under Not done, report the delay-guard reinterpretation: it waits for the queue's extraction and a linked model.
