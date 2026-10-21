# I64 (= I33a): intent contracts and G10

Rendered from `docs/BUILD_PLAN.md` §4 I33 (whitepaper §5.9 intent contracts, §5.8's volatile-view exception, §9.3 G10), from §2 invariant 10 (a check with no meaning for a milestone is listed under `not_applicable`; Q15, gate semantics, is still open), and from human answer Q4 (schema adoption) in `docs/HUMAN_ANSWERS.md`. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (K1-K10), commands and exit codes are in the docstring of `tests_m3/test_contracts.py`.

This prereg was revised after an independent review of its first draft (`docs/iterations/I64_prereg_review.json`: no sign-off, 5 major and 7 minor findings, all folded in). The revision:
- re-checks every decided T64 record with Bend and has the gate re-decide T64 (F1);
- decides every G10 verdict by the instrument as well as the gate, and drives G10 to fail on each rule (F3);
- reads P4's L_weak status (F2);
- makes the refusal test fail without a build (F4);
- tests the schema on a marked record (F5), and `apply`, `derive --check`, removal and the least-id rule (F6);
- hardens the instrument (F7);
- and corrects the disclosure, the citations and the scope notes (F8-F12).

A verification review of that revision (`docs/iterations/I64_prereg_verification.json`) also refused sign-off: F1 was only partly resolved, with 2 major and 4 minor findings. Their stated fixes are folded in too:
- the Bend re-check now requires the proof to import exactly its law file and to state no law of its own (V1);
- the run's last step stays out of every generator closure, so no M0-M3 record's `generator_sha256` changes, and R2's history test checks every commit of I64's own for that (V2);
- the texts the tests compare are spelled out in the contract (V3);
- the instrument validates an L_weak as IR 0.3, and catches non-relative paths, malformed registry entries and non-JSON records (V4);
- the baseline copy is removed (V5);
- `apply`'s refusals are tested (V6).

These folds were not reviewed a third time; the build review reads them.

## Why a separate key

BUILD_PLAN I33 has two parts:
- **The machinery:**
  - `@intended(rule, scope, L_weak)` contracts as pinned artifacts, with their registry;
  - `holon/contracts.py`;
  - G10;
  - `intended_bounded` as a v2 `filter_bin` value;
  - the volatile-view contract type OWN needs;
  - the Q4 adoption step.
- **The O12 contract on the real model:** its L_weak `f_j <= commit_j + F + W * #challenges` PROVED, and the `L_undo_cancel` analogue marked `intended_bounded`.

The second part cannot be built now, for three reasons:
1. **No generator proves the bound.** `reach_invariant` proves conjunctions of equalities that every action preserves by computation or by the hypothesis as it stands. It cannot rewrite with the hypothesis, so `e + W == c + F + W * (n + 1)` from `e == c + F + W * n` is out of reach. A proof class for linear bounds over Reach is new generator work.
2. **No ghost counter.** The M3 model has none. Adding it changes the M3 model, which regenerates every M3 record while the other lane's I26 is in flight.
3. **No `L_undo_cancel` analogue.** I27 derived no M3 analogue of `L_undo_cancel` (I27's gap G5: no (challengeState, setPause) pair), so there is no M3 record to mark.

Facts the real O12 contract will also have to state:
- the owner can change `proofWindow` and `finalizationPeriodSeconds`;
- `commitBatch` adds `proveRemainingTime` (at most W) while a challenge is open (`Rollup.sol:361-363`).

So the machinery goes first, under its own key, as I59 did for I23 and I63 for I28. I33 keeps its number for the O12 contract.

## What I64 does

- **Contracts.** Each is a file `laws/CONTRACTS/<id>.json` (K1), pinned by its registry hash (K2). The pin is self-certified, not frozen, until the human adds `laws/CONTRACTS` to `FROZEN_ROOTS` (Q1). There are two kinds:
  - `intended`: names the laws it covers (its scope) and a weaker law L_weak;
  - `volatile_view`: names a Go function's result that may alias a buffer.
- **`holon contracts derive`** turns each intended contract's L_weak into an ordinary law, `laws/<M>/L_contract_<id>.json` (K3), which `holon run` decides like any other law (K4).
- **The run's last step** (K5) marks every REFUTED record in a proved contract's scope as `intended_bounded`. The mark names the contract and keeps the bin it replaces, so `holon contracts apply` can take it off again. A contract whose L_weak is not proved, or whose proof predates the current facts, marks nothing.
- **G10** (K6) is the gate's check that contracts are proved, current and registered, and that the marks are exactly the ones they license. It is listed under `not_applicable` on M0 and M1 (invariant 10; Q15 still open), and passes, saying so, on a milestone with no contract.
- **The v2 result-record schema** admits `intended_bounded` and the mark's field `intended` on REFUTED records (K8). The frozen v1 `triage` is untouched (Q4).
- **Volatile views** are validated against the Go document's slice results (K9). OWN (I35) reads them.
- **The Q4 adoption package** (K10): the two v2 schema files and the human's exact steps to freeze them, including the CI digest pin Q40 added.

**The test milestone T64** (`tests_m3/fixtures/contracts/`) is O12 in miniature:
- one pending batch with deadline `e`;
- `challenge` adds `W = 3` to `e`. Unlike `challengeState`, it has no guard, so a second challenge extends the deadline again;
- `cancel` closes the challenge but leaves the extension;
- `finalize(now)` needs `e <= now`.

The toy has no ghost counter: no law or contract of it would read one.

**The laws and contracts:**
- `L_t64_cancel` is the undo pair (challenge, cancel): every later schedule observes the same as from the state itself.
- `L_t64_flag` is a planted false invariant that no contract names, the out-of-scope control.
- `C_t64_ext` is the intended contract. Its L_weak: from every reachable state, after (challenge, cancel), the deadline is exactly 3 later, no challenge is open, and the commit time and the flag are as before.
- `C_t64_zero` is a planted false contract (no residue on the deadline).
- `V_t64_view` declares `TxsPayloadV2`'s result 0 volatile (the §5.8 case).
- `V_t64_bad` names a function that does not exist.

I64 registers no contract on M0-M3 and changes no M0-M3 law or record.

## What was known before this prereg (disclosed)

- **The fixture validates.**
  - The fixture laws, and the two contracts' L_weak rendered as laws, validate against `spec/schemas/law_ir_0_3.schema.json`.
  - The toy facts construct a `holon.gen.machine.Machine` with actions commit, challenge, cancel, finalize and raise.
  - Both checks are well-formedness only. No generator, refuter, `holon run` or gate was run on T64 or on any fixture law.
- **The toy was shaped for a generator, by reading its code only.** Nothing was run to check it.
  - `reach_invariant` refuses any premise outright (`holon/gen/mproofs.py:965-967`).
  - Of the other classes, only `chain_revert` (and the `deadline` classes it shares a parser with) uses a premise to decide an action's guard, and only for its (State, Act) shape with two Bool premises. No class case-splits a Bool field of the state to use a premise such as `challenged(s) == false`.
  - With a guard on `challenge`, the +3 holds only from states with no open challenge, so the L_weak would need that premise.
  - So `challenge` has no guard, and the L_weak is a premise-free claim over one `Reach` binder, the shape `reach_invariant` takes, closed by computation in every case.
  - **What this costs P1.** The L_weak holds of every state, reachable or not. The Reach induction is therefore decorative, and P1's PROVED half is near-certain by construction. It says nothing about O12's cumulative bound `f <= c + F + W * n`, which needs the proof class I33 must build. P1 is not the question I64 asks; the machinery is.
- **Code read:**
  - `holon/gen/mproofs.py` (the class list, `reach_invariant`, `chain_revert`) and `holon/mpipeline.py` (the order it tries them in, and how a record names the generator that decided it);
  - `holon/gate.py` (the report format, G1's regeneration through `holon run`, the typed-milestone dispatch to `holon/sorts/gate3.py`, and the checks that recompute a record's `filter_bin` from the replay report);
  - `holon/filter.py` and `holon/records.py` (a REFUTED record's `filter_bin`), `holon/schema.py` (the keywords G9's validator supports), `holon/ir.py` (the statement hash includes the law id);
  - I41's T41 fixture flow, and its Bend re-check of records;
  - I27's back-test (`spec/M3/lib/undo_basis.json`: gaps `[L_undo_cancel]`);
  - M1's `L_undo_cancel` (REFUTED on the hand model);
  - `Rollup.sol` at the head (challengeState, commitBatch, commitBatchWithProof, finalizeBatch);
  - the base's CI run 39650731101: its M3 partial gate fails only G11V, on `L_disch_rev_initializable_120_d9a34b48` (Q36).

## Predictions (key I64 in `spec/M3/predictions.json`)

- **P1.** On T64 the existing generators and refuters decide:
  - `L_t64_cancel` REFUTED;
  - `L_t64_flag` REFUTED;
  - `L_contract_C_t64_ext` (C_t64_ext's L_weak) PROVED.

  Each decision is re-checked by Bend in the test, from a generator or refuter that existed at the prereg. Gate checks G1, G3, G5 and G11 pass on T64.
- **P2.** The marking, against a run with no contract:
  - `L_t64_cancel`'s record is marked `intended_bounded` by C_t64_ext, keeps the bin it had there, and is otherwise the same;
  - `L_t64_flag`'s record is the same;
  - G10 passes on T64, from the gate and from the instrument.
- **P3.** With C_t64_zero instead:
  - its L_weak is REFUTED (re-checked by Bend);
  - nothing is marked;
  - G10 fails naming it, from the gate and from the instrument.
- **P4.** A facts change makes G10 fail as stale.
  - After a change that leaves the toy's behaviour, a new derive and run prove the L_weak again and make G10 pass, with the mark back.
  - After W changes to 4, the +3 L_weak is REFUTED (re-checked by Bend), nothing is marked, and G10 still fails.
  - At every step the gate and the instrument agree.

**Regressions:**
- **R1:** no contract on M0-M3, and no M0-M3 record marked or carrying `intended`. G10 is not applicable on M0 and M1, and passes with no contract on M2 and M3.
- **R2:**
  - Gates M0, M1 and M2 pass, with G10 added.
  - The M3 partial gate passes every check but G11V. G11V fails only on `L_disch_rev_initializable_120_d9a34b48`, the base's (Q36), and G10 passes.
  - The frozen suite and the prereg audits pass.
  - I64's own commits (the build branch's first-parent chain from the prereg to the report) touch no M0-M3 law, record or generated file, no frozen root and no file of a generator closure.
- **R3:** construction checks. They include G10 failing on each of twelve tampers, `apply` and `derive` with `--check`, `apply`'s refusals, and the least-id rule. The tamper and `apply` tests start from the baseline's passing G10, and the least-id test decides a copy of C_t64_ext's L_weak, so they fail with P2 or P1.

## Deliverables

- **`holon/contracts.py`** and `python -m holon contracts derive|apply --milestone M [--check]`.
- **The run's last step:** `holon/contracts.py`, called from `holon/__main__.py` once the run's dispatch returns 0, so that every runner gets it. No module of a generator closure imports it, and I64 changes no file of one (K5): every M0-M3 record keeps its `generator_sha256`.
- **G10** in `holon/gate.py` and in the typed milestones' gate (`holon/sorts/gate3.py`). It is in both default orders, `holon.gate.CHECK_ORDER` and a module-level `holon.sorts.gate3.CHECK_ORDER`, and CI's explicit gate lists include it.
- **`spec/schemas/result_record_v2.schema.json`:** `intended_bounded` and the field `intended`, using only the keywords `holon/schema.py` supports.
- **`laws/CONTRACTS/`:** an empty registry. No real contract yet.
- **`docs/adoption/Q4/`:** `README.md` and `schemas/`.
- **`docs/iterations/I64.md`:** the report.
- **One fresh build review.**

## Not in I64 (I33's, when it registers the first real contract)

- **Marks on M2/M3 records.** The gate checks that recompute a REFUTED record's `filter_bin` from the replay report stay as they are: `want_bin` in `holon/gate.py`, and `holon/refute_m3.py`'s final filter, which also rewrites `filter_bin` and would erase a mark. A marked M2 or M3 record would fail them. I33 makes them read `intended.replaces`, and makes `refute_m3` keep marks.
- **Derived laws on M2/M3.** A law `laws/M2/L_contract_*.json` or `laws/M3/L_contract_*.json` cannot live there yet:
  - `holon derive` deletes every `laws/<M>/L*.json` it does not produce, and rewrites `REGISTRY.json`;
  - G1 (`holon/gate.py`) and G2 (`holon/sorts/gate3.py`) require `laws/<M>` to be its output byte for byte;
  - `holon run` with the registry refuses a law `REGISTRY.json` does not list.

  I33 makes `holon derive` emit or carry the derived laws and their registry hashes. T64 avoids all of this: its tests run with `--no-registry`, and a registry the harness writes.
- **The last step on the typed runners.** `holon.undo.run` and `holon.disch.run` reach it through the same call site in `holon/__main__.py`, but T64 runs through `holon.pipeline` only. I33's contract on M3 exercises them.

## Rules

- AGENTS.md throughout. Never write under `schemas/` or another frozen root, and never run `tools/freeze.py write` (Q4: the human runs the freeze).
- No contract on M0-M3 in I64. I33 brings the O12 contract.
- The instrument and the fixture are fixed at this commit. A wrong instrument is a Question plus an amendment line, never a silent edit.
- A missed prediction is a result.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
