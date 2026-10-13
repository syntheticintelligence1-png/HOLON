# I41: untrusted prover intake

Rendered from `docs/BUILD_PLAN.md` §4 I41. It realizes these parts of the whitepaper:
- §9.1, "Provers (untrusted: tactic generators, agents) → PROOF/";
- §9.2(3), the proof loop;
- §9.4, "Provers have no write access to LAWS/";
- §10.4, "Agents ... fill the remaining goals. The only thing they can produce that matters is a proof file the kernel accepts";
- §12, L14.

It depends on I10's prover separation and statement lifecycle. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact inbox format, decision order, CLI, record fields and rules are in the docstring of `tests_m3/test_intake.py`, which is the contract.

The human answered Q14c **yes**, through an intake: Bend checks every agent proof, and the intake never trusts one (`docs/HUMAN_ANSWERS.md`). AGENTS rule 4 ("proofs come from proof generators") still holds for every law a generator decides. The intake opens a door only for laws the generators left UNKNOWN.

## Goal

An agent can turn a law that the generators left UNKNOWN into PROVED, and only by one route: placing a proof file in `proofs/inbox/<law_id>/`. That file must never be able to touch a statement. Acceptance needs four things:
- the law is eligible;
- G1 shows every law file, and the model and the core, unchanged;
- every applicable kernel checks the proof against the law file the intake regenerated itself;
- G3 is clean and the check stays within budget.

Records say who proved what: `prover: generator | agent:<session>`.

## Deliverables (summary; the contract has the details)

- **`holon/intake.py`:**
  - `REASONS`, the eleven refusal reasons in check order;
  - `required_kernels(M, root)`;
  - `python -m holon intake [--milestone M] [--root DIR] [--inbox DIR] [--law ID ...] [--budget-s S] [--json]`, read-only;
  - `python -m holon intake --list [--milestone M] [--root DIR] [--json]`.

  It names no law id and no target, and never imports `tests/reference`.
- **`holon run` integration** (`holon/mpipeline.py`, state-machine milestones). After the generators and the refuter, a law they leave UNKNOWN with a submission in `proofs/inbox/` is decided:
  - **accepted:** the record becomes PROVED with `prover: agent:<session>`. The proof is copied byte for byte to `gen/<M>/proofs/<law_id>/PROOF.bend`, and the generators' law file is written. The generators' attempts are kept, and an `intake` attempt is added last.
  - **refused:** the record stays UNKNOWN, with one more attempt that carries the reason.

  G1 therefore regenerates agent-proved records from the committed inbox. G3, G5, G7 and G11 re-check the copied proof like any other.
- **Records.** Every record gains `prover`. M0 (`holon/pipeline.py`) only gains the field. `spec/schemas/result_record_v2.schema.json` requires the field with the pattern `^(generator|agent:[A-Za-z0-9][A-Za-z0-9_.-]{0,63})$`. Regenerate results/M0, M1 and M2 **in one commit** that changes nothing but the new field. The only exception is `generator_sha256` of M1 and M2, which changes because `holon/records.py` and the pipelines are in their generator set (`holon.records.generator_files`).
- **`docs/iterations/I41.md`**, with a prediction table.

## Eligible laws today

At this prereg's base `f8fa447` there are 34 records: M0 8, M1 16, M2 10. Exactly two are UNKNOWN, both M2 SORT-site laws of the form ∀ s: Reach, a: Act, agg:
- `L_sort_site_def_lci_356891e4`;
- `L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17`.

For both, `coercion_guard` does not apply, `reach_invariant` refuses with "needs exactly one forall Reach binder and no premises", and the SORT-site search finds no witness.

The positive fixture is a fixture law, `L_i41_x_any_act` on a copy of the I8 toy reach machine (test milestone T41). It is UNKNOWN for the same reason.
- **Why not a real law:** a real proof would need a Reach induction across the 10 actions of the 7044-line rollup model. That is a research result in itself, and the plan's positive prediction is meant to test the intake, not whether such a proof can be found in two days.
- **Where the real laws are used:** every negative control (P4, P5) and the end-to-end path to the kernel (P8).
- **Optional:** proving them through the intake is welcome, but it is not predicted.

## Predictions (key I41)

| id | claim |
|---|---|
| P1 | **A proof that edits its law file is refused by G1.** The agent writes `edits_law/LAWS.bend` over `gen/T41/laws/L_i41_x_any_act/LAWS.bend` (the claim added as a premise, the generated header kept) and submits `edits_law/PROOF.bend`. Bend alone accepts the pair. The intake refuses `law_file_changed`, with `differs` exactly that file, and no kernel runs. |
| P2 | **A valid agent proof is accepted and labelled.** `valid/PROOF.bend` (a hand-written Reach induction) is accepted, with bend2 and bendtt checked and `differs` empty. After `holon run --milestone T41`:<br>• its record is PROVED with `prover: agent:fixture-i41`;<br>• its proof is the inbox file byte for byte, and its law file is the generators' statement, with the same statement hash;<br>• kernels bend2 and bendtt checked, `independence_class` I1-shared, `bound` null, `non_vacuity` inhabited (`gen/T41/L_i41_x_any_act/nonvac/LAWS.bend`, reachable);<br>• the generators' attempts are kept, and the intake attempt is last;<br>• the record differs from the generators' UNKNOWN record in exactly status, prover, artifacts, attempts, bound, checker, kernel, kernels, independence_class and non_vacuity;<br>• the run adds exactly 4 gen/T41 files (law, proof copy, 2 inhabitant files); the other records and every earlier gen/T41 file are unchanged. |
| P3 | **The gate re-decides the agent proof.** On the accepted T41 tree, G1, G3, G5, G7, G9, G11 and G11V pass (at baseline they pass with 2 proofs, 3 records and 1 premised PROVED law inhabited). G1 regenerates the agent-proved record from the committed inbox (3 records identical); G5 and G7 each re-check 3 proofs, the 2 generator proofs and the agent's; G9 validates 3 records with `prover`; G11V inhabits 2 premised PROVED laws. **Negative control:** with the inbox file replaced by the wrong proof and the accepted records left in place, G1 fails and names the target. |
| P4 | **Proofs for decided laws are refused `not_unknown`, before any kernel.** This covers the fixture's PROVED `L_i41_y` (its own generator proof, which Bend accepts) and REFUTED `L_i41_flag`, and every decided M2 law resubmitted with its committed proof. At f8fa447 that is 8 laws: 6 PROVED, among them `L_sort_site_rollup_441_b4cd5068`, and 2 REFUTED, among them `L_sort_site_rollup_363_1fc7f88a`. |
| P5 | **Escape hatches are refused `escape_hatch` before G1 and any kernel, and the decision names the class.** The five fixture variants are `?TODO` and `?name` (both `hole`), `@unsafe`, `def f?(..)` and `import "./ag.c"`. A `?TODO` proof for each real UNKNOWN M2 law is refused the same way, which shows those laws are eligible. |
| P6 | **A proof that checks but lacks its law is refused.** `no_law/PROOF.bend` imports no law, and Bend says ALL PROOFS CHECK on it. The intake refuses it `missing_expected_law`. |
| P7 | **An over-budget proof is refused.** The valid proof plus a true lemma that makes 2^28 calls, under `--budget-s 10`, is refused `over_budget`: bend2 times out and is killed at the budget. The valid proof alone is accepted under the same budget. |
| P8 | **On the real M2 tree, a wrong proof (`{==}`) for each UNKNOWN law reaches the kernel.** It passes every check before the kernels, including G1 over gen/M2 (`differs` is empty). bend2 then rejects it, so the reason is `kernel_rejected`. No tracked file changes. |
| P9 | **A refused submission changes only its target's attempts.** With the wrong strengthening (`y == 1`) in the inbox, `holon run --milestone T41` leaves the target UNKNOWN with `prover: generator`, plus one intake attempt (refused, `kernel_rejected`). Every other field, every other record and every gen/T41 file stay as they were. |

## Regressions

- **R1. Prover-field commit.** The commit that introduces `prover` adds `"prover": "generator"` to every record and changes nothing else. The one exception is `generator_sha256` in M1 and M2: M0's 8 records change by the key alone. `summary.json` and `deps.json` are unchanged. That commit descends from this prereg commit. At HEAD:
  - every record names its prover;
  - `agent:*` appears only on a PROVED record whose proof is its inbox file.
- **R2. Gates.** M0, M1 and M2 pass, and the M0 gate stays under 900 s.
- **R3. Construction checks.** They are listed in the key, and none of them counts as a prediction.

## Outcome paths

The only outcome path is `proofs/`. The records, the schema and the gate reports are written by many parallel lines: I20 is being integrated elsewhere, and I21, I22 and I23 follow. The prereg audit fails an iteration whenever one of its outcome paths is changed by a commit that does not descend from its prereg commit, so those paths are not listed here. R1 checks the record change mechanically, through git, and checks that it descends from this prereg commit.

## Rules

- **AGENTS.md is binding.**
  - The intake changes no statement, adds or drops no premise, special-cases no law id and never imports `tests/reference`.
  - A fix goes into the intake or a generator, never into a generated file.
- **An agent proof is PROVED exactly when a generator proof would be:** Bend accepted the file, and the expected law is in it. No kernel ever reads the tree's own law, model or core files. The intake regenerates them, in a fresh temporary directory with a fresh build directory.
- **Do not depend on I20.** The real-law tests pick laws from the committed records at run time.
- **No tuning, no skips.** A miss is a Surprise reported with its evidence. `TestProverField` reads git: without `.git` it fails, never skips.

## Disclosures by the drafter (before the prereg commit)

These runs make the fixtures valid by construction. None of them exercises the intake, which does not exist yet.
- **The generators on the three fixture laws, in a scratch copy:** `L_i41_x_any_act` UNKNOWN, with reach_invariant's one-binder refusal and no refuter hit; `L_i41_y` PROVED; `L_i41_flag` REFUTED.
- **Bend 2.0.36 on the fixture proofs, in a scratch tree:**
  - `valid/` says ALL PROOFS CHECK, and also with `--verdict`;
  - `no_law/` says ALL PROOFS CHECK;
  - `edits_law/` checks against its edited law file and fails against the generated one;
  - the `{==}` proof for the real UNKNOWN law `L_sort_site_def_lci_356891e4` fails with a type mismatch in 0.4 s;
  - the costly lemma at depth 24 checks in 24 s, and depth 20 takes 2 s.
- **By the reviewer, in scratch copies:**
  - `setup_fixture` (which now also fills the T41 registry's statement hashes and runs `holon metrics`) and the gate on the baseline T41 tree: G1, G3, G5, G7, G9, G11 and G11V pass, with 3 records identical, 2 proofs re-checked, 3 records valid and 1 premised PROVED law inhabited;
  - Bend on `valid/` (exit 0) and on the wrong variant (exit 1) against the generated law text;
  - a proof importing a helper that holds `@unsafe def ag_any(-A: Type) -> A`: Bend refuses it ("2 defs rely on unsafe or foreign code"), so the kernel itself sees unsafe code through imports.
