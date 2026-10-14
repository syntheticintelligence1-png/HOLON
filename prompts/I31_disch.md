# I31: DISCH I: guard conjuncts, the enableable write closure, blocking and external dependence

Rendered from `docs/BUILD_PLAN.md` §4 I31. Milestone M3. Whitepaper §5.7 (the enableable write closure Write*_X and external dependence), Thm 6.10 (blocking), §11.5 (Write*_sub excludes enq[P]), §8.3 ("principal class"), §8.4 and App. E (the DISCH row: "the blocked theorem is the obstruction"), §2.12 (an existential law is never REFUTED). Closes the closure half of V13. Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` and `docs/BEND_NOTES.md` first, then the reports of I20 and I30 (`docs/iterations/I20.md`, `I30.md`) and the M1 DISCH laws (`laws/M1/L_disch_*.json`).

**The docstring of `tests_m3/test_disch.py` is the contract**: the inputs, rules D1-D12 (checks, principal classes, abstract values, dead actions, the closure, kinds, blocked conditions, exclusions, signs and unsafe writers, laws, statements, catalog and DERIVATION), the CLIs, the proof routes, the refutation and witness search, records, replay and the gate.

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in `spec/M3/amendments.jsonl`):
- `spec/M3/lib/disch.json`: the documents, the model sidecar (I30's), the binding, the deployment's abstraction `r0` with its provenance, the component hypotheses, the search budget and `expected` (every class, closure, kind, external component, basis element and law the rules give, computed at the prereg);
- `tests_m3/_i31.py`: rules D1-D12 written out a second time, independently of `holon/`;
- `tests_m3/_i31r.py` and `tests_m3/fixtures/disch/harness/`: the independent replay, with a byte copy of the I20 step harness;
- `tests_m3/fixtures/disch/{a,b}/`: the planted contract `src/ToyGate.sol` in two variants on the same lines (b restricts `unjam` to the admin), extracted by holon's Solidity frontend at the prereg, with an I30-format model sidecar and a DISCH sidecar each (test milestones T311 and T312).

## Goal

Compute, generically and from the extracted document alone, who can unblock what:
- every guard conjunct of every action, classified (permission, external, input, loop, panic, never, time, state);
- the principal classes the extractor found (a modifier, or a body guard on the caller) and, for each class X, the enableable write closure Write*_X as a fixpoint from the binding's deployment;
- for each blocked condition B of a state conjunct and each class X whose actions carry it, the blocking law (Thm 6.10's invariant over X's closure under B), the revert law (every action that carries the conjunct reverts while B holds: the generalized `chain_revert`), and, for every other class Y whose actions can move B's registers, the external-dependence pair: an existential law (a reachable blocked state and a step of Y after which the guard holds) and its separately generated forall-negation.

Every law is stated over I30's typed model of the extracted rollup (Reach from the binding's deployment) and decided by Bend; every witness replays on the real contract.

## What exists, and what the extracted side lacks

- **M1's DISCH laws** (`laws/M1/L_disch_stale`, `L_disch_stale_commit`, the four delay laws) are hand-stated over the hand-written facts: one guard shape, a syntactic `perm`, no computed Write*_X (BUILD_PLAN §1 row 6: "partial"). I20's differential re-ran them on the extracted model; they are not M3 laws.
- **The extracted document** (`spec/M2/facts/morph_rollup.extracted.json`, A19) carries every guard reach, panic, implicit check, call and write, and I19's principal records (`principal: {modifier, predicate}`). It carries no class, no closure and no blocked condition.
- **I30's typed model** (`gen/M3/sorts/models/morph_rollup.extracted.bend`) has Reach, Act, the per-step environment and `chk_`/`step_`/`post_` per action, but no DISCH term. I31 adds a DISCH section that imports it (`gen/M3/disch/models/<model>.disch.bend`); it never copies it.
- **The queue, the verifier and the submitter registry are not extracted.** Their answers are environment terms (A-env). Conjuncts that read them are recorded per component in `gen/M3/disch/conjuncts.json` with the M2 hypothesis that stands for the component (and I21's verdict); they get no law here (I36 and I37 link those models).

## Deliverables

- **`holon/analysis/closure.py`**: checks (D1), principal classes (D2), abstract values and the deployment (D3), dead actions (D4), the enableable write closure (D5), kinds and external components (D6), blocked conditions and basis elements (D7), exclusions (D8), signs and unsafe writers (D9). `x_closure` is built on `perm_X`.
- **`python -m holon disch`**, writing `gen/M3/disch/closure.json` and `conjuncts.json` (formats in the contract; `--check`; exit codes 0, 1, 2, 3).
- **`holon/rules/disch.py`**: `SUBFORMS = ("blocking", "revert", "external", "external_none")` and `PRODUCERS`, registered under `holon-rules/1.4` beside every earlier M3 producer (the same objects); `holon derive --milestone M3` emits the DISCH laws with their DERIVATION entries and refuses stale `gen/M3/disch` files.
- **The `disch` IR term**, added additively to `spec/schemas/law_ir_0_3.schema.json`, rendered by `holon.ir.render_term`, hashed through the ref `disch:<ID>` (the contract gives the ref document).
- **The DISCH section generator** and the proof generators, one per route (frame, transport with time monotonicity, `chain_revert`, witness evaluation), over core lemmas that are proved, never assumed.
- **Refutation and witness search** with I30's stages S1-S3 and the sidecar's budget; counter-laws checked by Bend and BendTT; non-vacuity inhabitants for PROVED blocking, revert and external_none laws.
- **Records** `results/M3/L_disch_*.json` (v1 and v2 valid, v2 gaining `disch` additively), **replay** `replay/M3/disch/report.json` through the I20 binding (every replay file under `replay/M3/disch/`; records carry `checker` and `kernels`, bend2 and bendtt), and the **gate**: G1 regenerates `gen/M3/disch` and the DISCH laws, G6 binds every witness to a passed replay, G11V covers the PROVED non-existential laws, G4 adds one `disch_writer` canary per PROVED blocking law with a named class.
- **`docs/iterations/I31.md`** with the prediction table.

## Predictions (key I31)

| id | claim |
|---|---|
| P1 | Six principal classes over the 24 actions with writes: onlyOwner (13), onlyActiveSubmitter (commitBatch, commitState, proveState), onlyChallenger (challengeState), anyone (5), caller_rollup_210 (initialize4), caller_rollup_674 (claimReward); 19 permission checks. |
| P2 | initialize is the one dead action. anyone's closure writes 21 paths (rollupDelayPeriod among them); onlyActiveSubmitter's excludes proveState, writes the same 21 paths, and Write*_sub excludes enq[P]: its one effect on another component is the queue pop that moves P; onlyChallenger 23 paths; onlyOwner 17 actions, 33 paths. |
| P3 | 295 checks: 22 state, 31 external, 210 input, 19 permission, 11 panic, 1 loop, 1 never. External components: IL1MessageQueue 18 (13 delay-guard reads of the enqueue time), IRollupVerifier 2, ISubmitter 8, address 2, code 1. |
| P4 | 15 basis elements over 8 blocked conditions; 11 blocked, 4 self; onlyOwner and onlyActiveSubmitter are the named classes; never onlyChallenger. |
| P5 | Exactly 35 DISCH laws: 15 blocking, 8 revert, 6 external, 6 external_none. |
| P6 | The stale challenge's blocking law for onlyActiveSubmitter is REFUTED: proveState's timeout branch ends it; the witness replays. |
| P7 | O31: the existential laws for the active submitter (proveState) and the owner (revertBatch, setPause or updateProofWindow) are PROVED, their negations REFUTED; all four replay. |
| P8 | The revert request and the pause: PROVED blocking laws for every class but the owner; the owner's existential laws PROVED, negations REFUTED; revert laws PROVED (7 and 6 actions). |
| P9 | The open challenge: blocking PROVED for onlyChallenger and caller_rollup_210; the existential pairs for onlyActiveSubmitter and onlyOwner PROVED and REFUTED; revert PROVED. |
| P10 | The three reinitializers' blocking laws PROVED with inhabitants (initialize2's by transport; initialize3's and initialize4's by chain_revert: their writers revert under B); the genesis guard: UNKNOWN with a bound (a key argument); the four revert laws PROVED. |
| P11 | All 13 witnesses (7 REFUTED laws, 6 PROVED existential laws) replay on the real Rollup, in holon's report and in the independent instrument. |
| P12 | The plan's O32 (the BVH pin, read as the whitepaper's O32) is not realized: the pin checks commitBatch :261 and commitState :279 are kind input, in no basis element, and no DISCH law reads batchBlobVersionedHashes. A predicted plan miss. |

**Regressions.**
- R1 (BUILD_PLAN I31): the L_disch_stale and L_disch_stale_commit analogues, `L_disch_blk_rollup_363_e11d8bb2_anyone` and `L_disch_rev_rollup_363_e11d8bb2`, are PROVED with checked inhabitants. Together with P6-P10: 27 PROVED, 7 REFUTED, 1 UNKNOWN.
- R2: M1's DISCH records and I20's differential DISCH rows are unchanged, and no commit that writes an I31 outcome path touches an M0-M2 output, `spec/M1/`, `spec/M2/facts/`, `spec/M2/lib/` or `gen/M3/sorts/`.
- R3: every pre-I31 M3 record keeps its status, and its law changes only in `rule_catalog_version`.

The construction checks in the test file (the instruments, the CLI, the catalog, the IR and registry, derive's reproduction, the toy's flip, the renaming check, the static sensitivity check, the gate with its canaries, generic code) are not predictions; they must pass.

## Rules

- **AGENTS.md is binding.** Generate, never hand-write: laws come only from `holon/rules` with `DERIVATION.json`.
- **Q19.** No hand-written fact document (`spec/M1/facts/`, `facts/`) and nothing computed from one is read by `holon disch`, derive's DISCH producers, or run and replay for a DISCH law. The deployment is configuration: the sidecar's `r0` transcribes it, and the tests compare it with I30's capture.
- **Generic code.** No target name, span, law id, class id or check id in `holon/rules/disch.py`, `holon/analysis/closure.py` or the DISCH section generator; renaming the toy's identifiers renames its laws and nothing else.
- **No tuning.** The budget, `r0` and the rules are fixed. A law neither proved nor refuted is UNKNOWN with its bound; a miss is a Surprise with its evidence. Never widen a closure, add a route (the routes are frame, transport, chain_revert and witness evaluation, fixed at the prereg), place an agent proof for a DISCH law, or drop an action to make a prediction hold.
- **Never edit** `spec/M1/`, `spec/M2/facts/`, `spec/M2/lib/`, `laws/M0`-`M2`, `gen/M0`-`M2`, `results/M0`-`M2`, `replay/M1`, `replay/M2`, `gen/M3/sorts/` or a frozen file.

## Decisions for the lead (state them in the report; none blocks the build)

- **The catalog bump re-hashes the earlier M3 laws.** `rule_catalog_version` is part of every M3 statement, so `holon-rules/1.4` changes each PAR, SORT (and UNDO) statement in that field alone, and the registry sees a statement change for each. I31 treats it as a mechanical change (R3 checks that nothing else moved). If G2 or the prereg audit counts it as a statement edit, that is a Question for the human, not a reason to keep the old version.
- **Catalog numbering.** `holon-rules/1.4` assumes I27 takes `holon-rules/1.3` (I27 is merged before I31). If I27 is not merged first, M3's catalog still becomes `holon-rules/1.4` and `holon-rules/1.3` stays unused.
- **Deployment-relative facts.** On the binding's deployment `_initialized` is 1, so initialize2 and initialize3 are callable once by anyone; the closure says so (anyone can set `rollupDelayPeriod` once). That is a property of the binding's deployment, not a finding about the deployed Morph proxy.
- **The proof routes are fixed (P10).** Blocking laws use frame, transport and chain_revert per action of the closure (an action that reverts under B cannot be enabled there: Thm 6.10's enablement, BUILD_PLAN I31's risk clause), plus time monotonicity. No other generator route is added in I31, and no agent proof for a DISCH law goes into the intake inbox: the outcomes must follow from the fixed routes. The genesis guard stays UNKNOWN because its writer moves another key (keys are not reasoned about); that is the predicted bound, not a reason to add a route.
- **O32 is not realized (P12).** BUILD_PLAN I31 asks for O32's blocking invariant and `chain_revert`; read as the whitepaper's O32 (the BVH pin), its conjunct reads the batch index from calldata, so D6 makes it an input check and no law exists. This is a predicted miss of the plan, for the lead: keyed conjuncts (the pin's key equals lastCommittedBatchIndex + 1 only through a later check) need I32's profiles or a later rule.
- **The active submitter rests on A-env.** onlyActiveSubmitter's predicate is ISubmitter.isActive(caller), an environment answer; every law for or naming the class (P6, P7, P9) assumes an active caller exists, and the witnesses take the binding's stand-in answers. I21 found Hyp-ISubmitter false (F-M2-40: the registry's owner can leave no submitter active), so the submitter's ability to unblock is itself externally dependent on the registry. It is recorded (conjuncts.json "external"), not decided, until I36.
- **External components.** A conjunct that reads another contract's state gets a record, never a law, until that contract's model is linked (I36, I37).
- **§5.7's Morph instances.** The stale challenge (external: submitters or owner) is P6, P7 and R1. The BVH pin is P12 (not realized). The delay guard (mixed) and challenge gas (self-controlled) belong to I32: the delay guard reads the queue, so here it is an external conjunct, and the gas is the loop check at :489. The replay budget (external: owner) lives in the messenger, which is not extracted.

## Coordination

- **Outcome paths are narrow and I31's own:** `laws/M3/L_disch_`, `results/M3/L_disch_`, `gen/M3/laws/L_disch_`, `gen/M3/proofs/L_disch_`, `gen/M3/L_disch_`, `gen/M3/disch/`, `replay/M3/disch/`. Every commit that writes any of them must descend from this prereg commit.
- **Files several M3 keys write are not I31's outcome paths:** `laws/M3/REGISTRY.json`, `laws/M3/DERIVATION.json`, the re-versioned earlier M3 laws, `results/M3/summary.json`, `deps.json`, `metrics.json`, `gate_report.json`, `spec/bindings/M3.json`, `gen/M3/coverage.json`, `gen/M3/core/`, `spec/schemas/law_ir_0_3.schema.json`, `spec/schemas/result_record_v2.schema.json`. Merge them by hand with I24, I27, I30 and I41.
- **Shared code.** DISCH laws import I30's typed model; no copy of it under `gen/M3/disch/` or `gen/M3/model/`.

## Risks and fallbacks

- **An action whose enablement cannot be certified** (BUILD_PLAN I31) is excluded from the closure and recorded: a dead action in `closure.json`'s `dead`, an excluded action certified by the revert law of its blocked condition.
- **Kernel cost.** If BendTT cannot check a counter-law within the gate's budget, record it as it is; a law not checked by both kernels misses its prediction.
- **No witness within the budget.** The law is UNKNOWN with its bound; never widen the budget after seeing a result.

## Before committing

Run every suite (`tests`, `tests_m1`, `tests_m2`, `tests_m3`), `holon gate` for M0, M1, M2 and M3, `python tools/freeze.py check`, and `python -m holon audit prereg` for M2 and M3. Write `docs/iterations/I31.md` with Done, Surprises, Questions for the human and Not done, including the class table, the closures, the basis table (blocked condition, class, status, named classes, writers), the outcome table with witnesses and replays, and the canary lines.
