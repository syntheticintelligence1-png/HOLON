# I65 (= I33b): the O12 intent contract on M2's window view

Rendered from `docs/BUILD_PLAN.md` §4 I33 (whitepaper §5.9 intent contracts, §9.3 G10) and `docs/CASESTUDY.md` N2 (O12: "Cancelling a challenge leaves the +W extensions it applied to other batches. An intent contract (§5.9) can bound this as designed behaviour."). It builds on I64 (= I33a, `prompts/I64_contracts.md`), whose machinery it uses unchanged except where the rules below say. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact rules (O1-O9), commands and exit codes are in the docstring of `tests_m3/test_o12.py`.

## Why a separate key, and why M2's view

I64 left three things for I33's O12 contract: a ghost counter, a proof class for linear bounds over Reach, and an M3 analogue of `L_undo_cancel` (I27 gap G5). On M3 each is large:
- the M3 model is the 15,000-line extracted Rollup over 256-bit words (eight 32-bit limbs), and no Reach-inductive proof has been checked on it;
- the UNDO pair needs a new rule criterion, a catalog bump that collides with the other lane's I26.

M2's window view of the same Rollup (`gen/M2/extracted/m1_view.json`, built by `holon differential`: the M1 abstraction with the requires the extracted code lacks removed) is a Nat model of 22 state fields and 10 actions. There, `L_undo_cancel` is already REFUTED (`results/M2/extracted_m1/L_undo_cancel.json`), and `holon.gen.mproofs` already proves trace inductions and linear Nat comparisons. So the human chose (2026-10-22, recorded in `docs/HUMAN_ANSWERS.md`) to put O12's contract on M2's view first, under its own key, as I59 was for I23, I63 for I28 and I64 for I33. I33 keeps its number for the O12 contract on M3. It reuses I65's ghost term, class and integration, and adds the word-level lemmas and the UNDO analogue after I26.

## What I65 does

- **The ghost counter (O1).** A new IR 0.3 term, `{"ghost": A, "add": E, "over": T, "from": S}`: the sum of `E` (evaluated in the state before the step) over the steps of `T` from `S` that are `A` and succeed.
  - It is a history variable, emitted as two statement helpers in `LAWS.bend`, `gh1_<hash>` (one step's share) and `gh_<hash>` (the sum), the way I24's expr terms are. The refuter evaluates it through the same helpers.
  - It changes no model and no facts document. A law without a ghost term gets the files and record it got before, `generator_sha256` aside.
- **The proof class `trace_bound` (O2).** It proves a conjunction of linear Nat comparisons, read through expr terms with ghost binds, as an inductive invariant of every run from `s0`:
  - the Nat binders are quantified inside the invariant, and the ghost's running sum is a parameter;
  - the initial state by computation;
  - one lemma per action, over the result of the action's decision: it walks the decide chain one guard at a time, keeping each guard's equation. That is how the commits' payload `prt` (W + start - t under an open challenge) gets known on the Ok branch;
  - each comparison carried through the action's effects by Nat and list lemmas, all proved in the law's `PROOF.bend`. The builtins without a kind (`bump_f`, `clear_chs`) are described by a pointwise sidecar, `spec/M1/lib/morph_rollup.pointwise.json`, which is in the generator closures. Its statements are proved, never assumed;
  - induction on the trace.

  It is appended to `GENERATORS`, and changes no existing class.
- **The contract `C_o12` (O3).** Scope `L_undo_cancel`, over the view. Its L_weak, over `p: Trace` and `k: Nat` from `s0`, with `g` the ghost (challengeState, W):
  - (a) at window position `k`, `bdf <= bdo + F + g`;
  - (b) `!inch || W <= g`;
  - (c) `!inch || nth_ch(chs, bc).s <= t`.

  (b) and (c) are the facts (a)'s induction needs. A batch committed while a challenge is open gets `W + start - t` (`Rollup.sol:360-364`), which is at most W because the challenge started in the past, and a challenge is open only after one succeeded. A second fixture, `C_o12_open` ((b) and (c) over `p` alone), is never registered in the tree. It is a construction check that the class proves a second claim too.
- **Integration into a real milestone (O4-O7):**
  - **The law.** The derived law `L_contract_C_o12` is an ordinary M2 law: registry, bindings, statement-change log, every check of the M2 gate.
    - `holon derive` writes the contract laws after the rules' laws, through `holon/contracts.py`, which stays outside every generator closure. `holon/rules/` does not change.
  - **The view anchored to its abstraction.**
    - It takes the abstraction's target libraries and search hints, as the differential's runs do.
    - Its ledger bundle is generated from the abstraction's bundle when a record's facts are the view itself, so the record is `exact`. The view records keep their `derived` bundle.
  - **GEVID** enforces on the derived law as on every M2 law, with no exemption: I14's rule stands (`tests_m2/test_evidence.py`: from M2 on, an uncovered law, or metadata evidence its computed levels lack, fails). The law carries its contract's evidence, `E2`, copied by I64's K3, and I64's K1 requires every intended contract to claim at least one level, so GEVID is where that claim is checked. M2's evidence set models no window view, so the law is uncovered until a separately preregistered key models the view in `gen/M2/evidence.json`, as I20 covered its adopted documents. That key is Q62 to the human. I65's build does not merge while GEVID fails on the law. (The first fold exempted such laws instead; Codex's P1 finding on PR #43 showed that exemption suppresses the check AGENTS rule 2 protects, and it was withdrawn.)
  - **Lean.** The law's lean4 entry comes from M2's own Lean directory: `not_run`, `unsupported_form` (no Lean twin of the ghost term). By I43's rule L4 the directory still holds a model file for the Bend model its law uses, `gen/M2/lean/models/m1_view.lean`, emitted and checked like any model, with its Lean twin library taken from the view's abstraction.
  - **Marks** reach `results/M2/extracted_m1`, licensed only on a record over the contract's own facts.
  - **Keeping the mark.** `holon differential` ends with the last step. `holon refute`'s final filter and the gate's recomputed bin keep a mark, the filter's bin going into `intended.replaces`.
  - **G10** covers both directories.

## What was known before this prereg (disclosed)

- **Nothing was run on the subject.** No generator, refuter, `holon run`, `holon derive`, `holon differential`, gate or Bend check was run on C_o12, C_o12_tight, C_o12_open, a law derived from them, or the view's model. What was run: the law IR schema with the ghost term, which admits the three fixtures and refuses five malformed terms; and Bend on a toy file unrelated to the subject, to see how it reports a wrong `{==}` value (`- expected : <computed>`, `- observed : <claimed>`).
- **Build code begun before this prereg** (unpushed, in a separate worktree, never run on the subject): the ghost term's schema, emission, statement refs and search evaluation; marks over both record directories with the facts condition and ambiguity; the differential's last step; marks kept by `holon refute` and the gate. It also made `holon/rules` import `holon/contracts` for the derive step, the design O4 now forbids (it would put `holon/contracts.py` into the generator closures); the build drops that change. It is rebased onto the merged prereg and reviewed with the rest of the build.
- **The L_weak was written by reading the view's actions** (their guards and effects in `gen/M2/extracted/m1_view.json`, the target library `spec/M1/lib/morph_rollup.lib.json`, and the generated model `gen/M2/extracted/m1/model/m1_view.bend`). Per action:
  - challengeState bumps the other unfinalized entries by W while the ghost adds W;
  - the three commits append an entry with `bdf = t + F + prt` (or `t`, for commitBatchWithProof);
  - revertBatch takes, finalizeBatch drops, setPause and proveState leave the window, and wait only raises `t`.

  (b) and (c) were added because (a) alone is not inductive at a commit made while a challenge is open. The independent prereg review checked every action again and found (a)-(c) true and inductive. `C_o12_open` was added after that review: I checked it by the same reading, and the verification review found (b) and (c) each inductive on its own.
- **What this costs P1.** The L_weak was shaped to be inductive, and the class is built for this shape, so P1 is partly true by construction, as I64's was. What it still risks:
  - my reading of the view is wrong somewhere, and the bound is false (then the refuter should find it, and P1 misses with REFUTED);
  - or the class cannot be built to Bend's satisfaction within I65 (P1 misses with UNKNOWN).

  `C_o12_open` and the grep that holon names no I65 id guard against a class fitted to one claim, but do not remove the construction bias.
- **The ghost cases** in `tests_m3/test_o12.py` (GHOST_CASES) and the two commits they use were computed by hand from the guards, not by running the model. The review recomputed them in the compiled model's guard order.
- **The mark's evidence and design intent.** The view record of `L_undo_cancel` reads `replay: not_run` (no replay report entry). Its real-code evidence is I40's concretization (its `public_schedule` side passed on the real Rollup), not an I20 or I43 replay. That the extensions are designed behaviour rests on `docs/CASESTUDY.md` N2 and the human's I33 plan (BUILD_PLAN: `f_j <= commit_j + F + W * #challenges`), not on anything I65 shows. The contract's evidence tag `E2` is a level of the evidence calculus, copied into the derived law by I64's K3, not evidence of intent.
- **The bound is loose.** `g` counts W for every challenge that ever succeeded, so a batch committed after n challenges has n·W of slack it can never use. The bound shows "at most W per challenge ever", not a per-batch bound on the extensions a batch received. A per-batch ghost is left for I33.
- **Two bins for one law.** After I65, `results/M1/L_undo_cancel.json` stays `finding` (M1's own model is not the view), while the view's record is `intended_bounded`.
- **Code read:**
  - `holon/contracts.py`, `holon/gen/mproofs.py` (`deadline_linear`'s transport, `reach_invariant`, `expr_open`), `holon/gen/mlaws.py` (expr terms and their helpers), `holon/mpipeline.py` (`run_m1`: per-facts machines, the generator loop, the trace search, the Lean key), `holon/js/explore.mjs` (expr terms in the search), `holon/gen/targetlib.py` (where a facts document's libraries come from);
  - `holon/differential.py`, `holon/gate.py` (G1's regeneration, which compares `laws/M2` with `holon.rules.compute` and only four differential outputs; G2; G7's Lean rules; G9), `holon/refute3.py` and `holon/refute_m3.py` (the final filter over `M2/extracted_m1`), `holon/records.py` (bundle lookup, generator closures), `holon/diagram/evidence.py` (GEVID), `holon/lean.py` (Lean directories, `dir_key_for`), `holon/gen/lean_common.py` (allowed not_run reasons);
  - `holon/audit/prereg.py` (amendments, outcome order);
  - the tests of I15, I23, I24, I26, I31, I40, I43, I61-I64 that read M2's laws or records, or that scope commits by outcome paths.

## Risks (stated before the build)

- **The search.** P3 and P4(b) need a depth-3 successful prefix (two commits and a challenge). The search keeps at most 3000 prefixes of depth 3, deduplicated by state, while a ghost term depends on the trace: two traces reaching one state with different ghost values are one prefix. The refuter's own witness for `L_undo_cancel` needed a similar prefix, which is why I expect it to be found.
- **The ledger and the view.** If anchoring the view to its abstraction changes the libraries or hints any existing run reads, records move and R2 misses. The anchor applies only to documents that are window views. The view records' laws have M1's facts, and their run passes the anchor already.
- **GEVID and the build's merge.** Until a key models the window view in M2's evidence set (Q62), GEVID fails on the derived law: uncovered, with `E2` not computed. The build can be made and reviewed, but it merges only after that key, or after the human rules otherwise. Once the view is modelled, `E2` must be among the law's computed levels: I read the committed evidence model of the view's abstraction (`gen/M2/evidence.json`, `morph_rollup`), which has 35 E2 atoms at `TRANS.challengeState`. That holds only if a ghost term names its action's TRANS edge in the evidence calculus' rule L2, as an act term does, which that key or the build adds. The view's own model is not computed before then.
- **The view's Lean model in M2's directory** is a `machine_oracle` model with no oracle parameter, a case no committed Lean directory has yet. G7 checks it, so a Lean failure there fails gate-M2 and R1.
- **A known gap in the intake** (verification review N7): `holon/intake.py` treats every law of rule UNDO as I27's typed UNDO law. The derived law takes its contract's rule, UNDO. This does not matter while the law is PROVED. If it ends UNKNOWN, the intake would refuse it with a false reason, and the build fixes that before reporting.
- **Shared files with I26** (the other lane): `spec/schemas/law_ir_0_3.schema.json` (each adds a term), `docs/adoption/Q4/schemas/` (byte-equal to it), `holon/gen/mproofs.py`, `tests_m3/test_lean_promoted.py` (I26's catalog bump moves sha-pinned laws/M3 inputs) and the regenerated M1 and M2 records. Whichever lands second merges the other, keeps both terms, refreshes the Q4 copy and regenerates what the merge makes stale.

## Predictions (key I65 in `spec/M3/predictions.json`)

- **P1.** `L_contract_C_o12` is PROVED over the view, by `trace_bound`, and re-checked by Bend in the test. G2, G3, G5 and G9 pass on M2. GEVID is R1's.
- **P2.** Exactly one record of M0-M3 is marked:
  - `results/M2/extracted_m1/L_undo_cancel.json`, by C_o12, replacing `finding`;
  - unmarked, it is its prereg self but for `generator_sha256` and wall-clock fields;
  - G10 on M2 passes, from the gate and the instrument: `C_o12 proved, marks L_undo_cancel`.
- **P3.** C_o12_tight (one second per challenge instead of W), registered beside C_o12:
  - its L_weak is REFUTED by the existing refuter (`counter`, its search evaluating ghost terms by O1), with a Bend re-check;
  - it marks nothing, and C_o12's mark stays;
  - G10 fails naming it.
- **P4.** A change to the view makes C_o12 stale; G10 fails.
  - After a doc-only change, derive and run prove the L_weak again. The view record, decided over the old view, is no longer licensed: nothing is marked and G10 passes.
  - With challengeState extending by W + 1, the L_weak is REFUTED (Bend re-check), nothing is marked and G10 fails.

**Regressions:**
- **R1.** G10 is not applicable on M0 and M1, and passes on M3 with no contract. Gates M0, M1 and M2 pass in full on the build head, which merges only once M2's evidence set models the window view (GEVID enforces on the derived law, Q62). The M3 gate's failing items are those of the base the build stands on (at the prereg only G11V's Q36 item), I65 adding none. The frozen suite, freeze-check and both prereg audits pass.
- **R2.** No commit of I65's own (the non-merge commits of `git log --first-parent <prereg>..<end>`, end the first commit adding `docs/iterations/I65.md`) deletes a law or record, or adds one but I65's own (`L_contract_C_o12`'s, `laws/CONTRACTS/C_o12.json`, `results/M2/contracts.json`), which P1 and P2 judge at HEAD. Each other record such a commit changes keeps its status and differs from its parent's version only in `generator_sha256`, wall-clock fields, `prover` from absent to `generator`, and P2's mark. `laws/M2/REGISTRY.json` changes only by that law's statement hash and the view's facts file.
- **R3.** No commit of I65's own changes a frozen root, a law, record or generated file of M3, an M0 record or generated file, or a law of M0 or M1. I64-R1 as amended at this prereg holds.
- **R4.** The construction checks of `tests_m3/test_o12.py` (pins, schema, ghost values, contract and law, the second claim, no I65 id in holon/, ambiguity, licensing, G10's mark checks, the differential and the filter keeping the mark). Each needs the built tree.

## Earlier tests, amended in this prereg (O8)

Each amended test is narrowed to I65's outcomes, with its line in its own key's amendments file. At the prereg, no law is `intended_weak` and no record is marked, so each checks what it checked before.
- **I64-R1** (`spec/M3/amendments.jsonl`): a contract may name M2 exactly when the I65 key lists its id.
- **I40** (`spec/M3/amendments.jsonl`): three bin tests read a marked record's `intended.replaces`; I40-R2 lets a record gain `intended` when its filter_bin is `intended_bounded`.
- **I43** (`spec/M3/amendments.jsonl`): laws of subform `intended_weak` are outside the promoted set. The sidecar is recomputed over the tree without them, the live PROVED set and the metrics count leave them out, and their records may carry a lean4 entry. A Lean directory may also hold the model file of such a law's Bend model (R3 and R9), held to the model file rules.
- **I15** (`spec/M2/amendments.jsonl`, a later commit of this prereg's pull request, since a prereg commit may not touch `tests_m2/`): an `intended_weak` law is no SORT-site law and is not in DERIVATION.json; the registry's primary facts are the rules' laws'; I15-P3's derivation test leaves such laws out of the site laws it reads.

Some of these tests already fail at the base, and at the prereg, on unrelated records: I40-P7's six recorded MISSes, I43-R1's and the I43 sidecar test's baselines for three typed M3 records the G11 follow-up regenerated, and I40's v2 schema test on the view records' `derived` ledger_match. The amendments neither cause nor hide that, and those failures are not I65's.

No other earlier test is amended. One that fails on I65's outcomes is a miss, reported.

## Deliverables

- **The ghost term (O1):**
  - `spec/schemas/law_ir_0_3.schema.json`, with `docs/adoption/Q4/schemas/` following it;
  - `holon/ir.py`, `holon/gen/mlaws.py`, `holon/gen/refs.py`, `holon/records.py` (validation, emission, statement refs);
  - `holon/js/explore.mjs` and `holon/mpipeline.py` (evaluation in the search).
- **The class `trace_bound` (O2):** a module under `holon/gen/`, appended to `mproofs.GENERATORS`; the pointwise sidecar `spec/M1/lib/morph_rollup.pointwise.json`, added to the generator closures.
- **The integration (O4-O7):**
  - `holon/contracts.py`: record directories, the facts condition, ambiguity, and the derive step;
  - `holon/__main__.py` and `holon/gate.py`: derive keeps the contract laws, G1 regenerates them, marks are kept;
  - `holon/differential.py`: the last step;
  - `holon/refute_m3.py`: marks kept;
  - the view's anchor (`holon/gen/targetlib.py` and the bundle lookup in `holon/records.py`);
  - the Lean key of a law of `results/M2` (`holon/mpipeline.py`, `holon/lean.py`), the emitters' `Unsupported` on a ghost term (`holon/gen/lean_mlaws.py`), and the view's Lean twin library taken from its abstraction (`holon/gen/lean_machine.py` `lib_twin`, `holon/lean.py`).
- **Outcomes:**
  - `laws/CONTRACTS/C_o12.json` and its registry entry;
  - `laws/M2/L_contract_C_o12.json` and its record;
  - the mark;
  - regenerated: `laws/M2/REGISTRY.json`, `spec/bindings/M2.json`, `results/M2/metrics.json`, `results/M2/historical/laws.json`, `gen/M2/model/m1_view.*`, `gen/M2/lean/`, and the M1 and M2 records (`generator_sha256`);
  - `docs/iterations/I65.md`.
- **One fresh build review.**

## Not in I65 (I33's)

- **The O12 contract on M3:**
  - the word-level lemmas (eight-limb addition and comparison) that `trace_bound` needs over the extracted model;
  - the UNDO analogue of `L_undo_cancel` (a cancellation criterion in the UNDO rule, a catalog bump after I26);
  - the typed runners' ghost terms.
- **A per-batch ghost**, which would bound the extensions one batch received rather than W per challenge ever.
- **A Lean twin of the ghost term and of `trace_bound`.** The derived law's lean4 entry is `not_run` with reason `unsupported_form`, which G7 allows. Q8's promotion of every PROVED law to Lean is then not met for this one law, and the report says so.
- **The mark's replay.** I65 re-runs neither I40's concretization nor a replay of `L_undo_cancel`'s witness.

## Rules

- AGENTS.md throughout. Never write under `schemas/` or another frozen root, and never run `tools/freeze.py write`.
- The instruments (`tests_m3/_i65.py`, and I64's `tests_m3/_i64.py`, which it imports) and the fixture are fixed at this commit. A wrong instrument is a Question plus an amendment line, never a silent edit.
- Earlier keys' tests change only as O8 says, each with its line in its own key's amendments file (`spec/M2/amendments.jsonl` for an M2 key, `spec/M3/amendments.jsonl` for an M3 key).
- A missed prediction is a result.
- Never fetch, clone or read `scroll-tech/*` or `spec/heldout/`.
