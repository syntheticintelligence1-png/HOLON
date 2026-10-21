# I64 (= I33a): intent contracts and G10

Rendered from `docs/BUILD_PLAN.md` §4 I33 (whitepaper §5.9 intent contracts, §5.8's volatile-view exception, §9.3 G10), and from human answers Q4 (schema adoption) and Q15 (gate semantics) in `docs/HUMAN_ANSWERS.md`. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (K1-K10), commands and exit codes are in the docstring of `tests_m3/test_contracts.py`.

## Why a separate key

BUILD_PLAN I33 has two parts:
- **The machinery:**
  - `@intended(rule, scope, L_weak)` contracts as frozen artifacts, with their registry;
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

- **Contracts.** Each is a frozen file `laws/CONTRACTS/<id>.json` (K1), pinned by a registry hash (K2). There are two kinds:
  - `intended`: names the laws it covers (its scope) and a weaker law L_weak;
  - `volatile_view`: names a Go function's result that may alias a buffer.
- **`holon contracts derive`** turns each intended contract's L_weak into an ordinary law, `laws/<M>/L_contract_<id>.json` (K3), which `holon run` decides like any other law (K4).
- **The run's last step** (K5) marks every REFUTED record in a proved contract's scope as `intended_bounded`. The mark names the contract and keeps the bin it replaces, so `holon contracts apply` can take it off again. A contract whose L_weak is not proved, or whose proof predates the current facts, marks nothing.
- **G10** (K6) is the gate's check that contracts are proved, current and registered, and that the marks are exactly the ones they license. It is not applicable on M0 and M1 (Q15), and passes, saying so, on a milestone with no contract.
- **The v2 result-record schema** admits `intended_bounded` (K8). The frozen v1 `triage` is untouched (Q4).
- **Volatile views** are validated against the Go document's slice results (K9). OWN (I35) reads them.
- **The Q4 adoption package** (K10): the two v2 schema files and the human's exact steps to freeze them, including the CI digest pin Q40 added.

**The test milestone T64** (`tests_m3/fixtures/contracts/`) is O12 in miniature:
- one pending batch with deadline `e`;
- `challenge` adds `W = 3` to `e` and counts itself in the ghost `n`. Unlike `challengeState`, it has no guard, so a second challenge extends the deadline again;
- `cancel` closes the challenge but leaves the extension;
- `finalize(now)` needs `e <= now`.

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
- **The toy was shaped for a generator, by reading its code only.**
  - Reading `holon/gen/mproofs.py`, no proof class can use a premise such as `challenged(s) == false` to decide an action's guard: none case-splits a Bool field of the state.
  - With a guard on `challenge`, the +3 holds only from states with no open challenge, so the L_weak would need that premise.
  - So `challenge` has no guard, and the L_weak is a premise-free claim over one `Reach` binder: the shape `reach_invariant` takes, closed by computation in every case. Nothing was run to check this.
- **Code read:**
  - `holon/gen/mproofs.py` (the class list, `reach_invariant`) and `holon/mpipeline.py` (the order it tries them in);
  - `holon/gate.py` (the report format, the typed-milestone dispatch to `holon/sorts/gate3.py`, and the checks that recompute a record's `filter_bin` from the replay report);
  - `holon/filter.py` and `holon/records.py` (a REFUTED record's `filter_bin`);
  - I41's T41 fixture flow;
  - I27's back-test (`spec/M3/lib/undo_basis.json`: gaps `[L_undo_cancel]`);
  - M1's `L_undo_cancel` (REFUTED on the hand model);
  - `Rollup.sol` at the head (challengeState, commitBatch, commitBatchWithProof, finalizeBatch).

## Predictions (key I64 in `spec/M3/predictions.json`)

- **P1.** On T64 the existing generators and refuters decide:
  - `L_t64_cancel` REFUTED;
  - `L_t64_flag` REFUTED;
  - `L_contract_C_t64_ext` (C_t64_ext's L_weak) PROVED.
- **P2.** The marking, against a run with no contract:
  - `L_t64_cancel`'s record is marked `intended_bounded` by C_t64_ext, keeps the bin it had there, and is otherwise the same;
  - `L_t64_flag`'s record is the same;
  - G10 passes on T64.
- **P3.** With C_t64_zero instead:
  - its L_weak is REFUTED;
  - nothing is marked;
  - G10 fails naming it.
- **P4.** A facts change makes G10 fail as stale.
  - After a change that leaves the toy's behaviour, a new derive and run make it pass, with the mark back.
  - After W changes to 4, the +3 L_weak is REFUTED, nothing is marked, and G10 still fails.

**Regressions:**
- **R1:** no contract on M0-M3, and no M0-M3 record marked. G10 is not applicable on M0 and M1, and passes with no contract on M2 and M3.
- **R2:** the gates and the frozen suite pass. Outcome commits touch no M0-M3 law, record or generated file, and no frozen root.
- **R3:** construction checks.

## Deliverables

- **`holon/contracts.py`** and `python -m holon contracts derive|apply --milestone M [--check]`.
- **The run's last step**, wired into `holon run`.
- **G10** in `holon/gate.py` and in the typed milestones' gate (`holon/sorts/gate3.py`). It is in the default checks, and CI's gate lists include it.
- **`spec/schemas/result_record_v2.schema.json`:** `intended_bounded` and the field `intended`.
- **`laws/CONTRACTS/`:** an empty registry. No real contract yet.

**Not in I64:** the gate checks that recompute a REFUTED record's `filter_bin` from the replay report (`want_bin` in `holon/gate.py`, and `holon/refute_m3.py`'s final filter) stay as they are. A marked M2 or M3 record would fail them. I33 marks the first real record, so I33 makes them read `intended.replaces`.
- **`docs/adoption/Q4/`:** `README.md` and `schemas/`.
- **`docs/iterations/I64.md`:** the report.
- **One fresh build review.**

## Rules

- AGENTS.md throughout. Never write under `schemas/` or another frozen root, and never run `tools/freeze.py write` (Q4: the human runs the freeze).
- No contract on M0-M3 in I64. I33 brings the O12 contract.
- The instrument and the fixture are fixed at this commit. A wrong instrument is a Question plus an amendment line, never a silent edit.
- A missed prediction is a result.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
