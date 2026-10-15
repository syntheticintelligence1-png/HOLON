# I43: theory core II; Lean for the promoted set

Rendered from `docs/BUILD_PLAN.md` §4 I43 (whitepaper §5.3, §5.4, §6 Thm 6.6 and Thm 6.7, §8.8, §8.9, §10.3 steps 4–5, §10.8) and the human answers in `docs/HUMAN_ANSWERS.md`: Q14b (Thm 6.4, 6.6 and 6.7 may be proved once, by hand, in Lean, and kernel-checked) and the delegated Q8 (every PROVED law is promoted to Lean; a law Lean cannot check within budget stays I1 with its reason: timeout, recursion depth, or unsupported form; cross-kernel coverage is a metric; a cross-kernel disagreement is a blocking finding). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then `docs/iterations/I9.md` (Lean for M0) and I42's report and contract (merged into the integration line at `512e6f3`: `docs/iterations/I42.md`, `tests_m3/test_theory_core.py`).

The exact outputs, formats and rules are in two contract docstrings:
- **Part A, theory core II:** `tests_m3/test_theory_core2.py` (rules C1–C5, gaps TC-G1–TC-G7, the `holon theory2` CLI);
- **Part B, Lean for the promoted set:** `tests_m3/test_lean_promoted.py` (rules L0–L11, gaps LP-G1–LP-G10, the `holon lean` CLI).

The instruments are fixed at this prereg:
- `tests_m3/_i43.py`: both contracts' rules written out a second time, independently of `holon/`.
  - The frozen Bend and Lean core II texts; the scope; the Lean model interfaces; the Lean statement of every in-scope law rendered from its IR; the file rules.
  - The differential samples, whose values the compiled Bend models compute.
  - The perturb canaries with their Bend evidence, and the site canaries, whose mutated Bend models holon's own Bend side builds.
  - The readers the tests judge with, none taken from `holon/lean.py` (which you edit): the Lean toolchain resolution (Lean 4.34.0 and its fingerprint, frozen in the instrument), the banned words and file rules, the Lean check with a random sentinel and the axiom audit, the semantic-rejection and resource-limit readings with their probes, the Python import reader, and the first review's cheat files as fixtures.
- `spec/M3/lib/theory_core2.json` (part A) and `spec/M3/lib/lean_promoted.json` (part B): every predicted value, computed by the instrument from the inputs it lists (files by sha256, records by status and witnesses).

**Base.** This prereg sits on the integration line `be95d6d` (after I31's DISCH I and F36's Lean lexer). It is the prereg `84c185f` (base `fbd14d3`, pushed before any build), moved twice:
- **The first move,** onto `7fd9755` (the merged I42, as the lead's Q35 asks: "a fresh I43 prereg comes later, on top of the merged I42"), as `c3ed059`. A build followed `84c185f` on `fbd14d3` (branch `claude/brave-wright-2c5d0o-i43`), and merging `7fd9755` into it could not pass `holon audit prereg`: F34's `d0dfac7` writes I43's outcome paths (`gen/M3/laws/`, `results/M3/`) without descending from the prereg. A third independent review folded 2 major and 4 minor findings into `c3ed059`, and a build followed it (branch `claude/brave-wright-2c5d0o-i43v2`, kept as it is).
- **The second move,** onto `be95d6d`, for the same reason: I31's and F36's merges regenerate records under `results/M1`–`M3`, add laws to `gen/M3/laws/` and change `spec/schemas/result_record_v2.schema.json`.
- **The outcomes were known.** Both earlier builds' outcomes were known when this prereg was made. So the moves change only what the base forces, and one scope rule the human chose (below).
- **What this move changed.**
  - **I31's DISCH laws are not attempted (the human's answer).** I31 adds 35 DISCH laws to `results/M3` (13 PROVED, 7 REFUTED, 15 UNKNOWN). They are stated over a `holon-facts/0.3` document, which no Lean emitter reads. Rule L0 ("a PROVED law is attempted always") would have required Lean for them, and I43 has no emitter for them. Asked at this move, the human chose to carve them out, PROVED and REFUTED, like I30's typed and I27's UNDO laws. The instrument names exactly the rule-DISCH laws (`tests_m3/_i43.py::DISCH_NOT_ATTEMPTED`) and still refuses any other PROVED law outside the emitters' kinds. `test_scope_counts` now expects these counts: PROVED 8/6/7/86, of which 8/6/7/73 are attempted; REFUTED 8/2/7/16, of which 8/2/7/4 are attempted. I43-P1 now names the 73 PAR laws it always measured. R1's unregenerated records gain the 35 DISCH records (stricter).
  - **The sidecars,** recomputed by the instrument on `be95d6d`.
    - `theory_core2.json` is byte-identical.
    - In `lean_promoted.json`:
      - the DISCH laws join `laws` (20 entries, not attempted), `statuses` (35), `unregenerated_records` (35), `inputs` (40) and `bend_files` (69 with I31's other `.bend` files);
      - I31's holon-rules/1.4 rebinding changed 83 law-file inputs and 82 law entries' `statement_hash`. Every frozen Lean statement is unchanged.
    - Models, differential samples and canaries are unchanged.
  - **The texts** that describe the base.
- **Earlier.** The first drafts sat on `a0bcdc3`. The move to `fbd14d3` changed only the disclosed generator hashes (F33 regenerated the M1 and M2 records for a changed closure; I27 reran four UNDO laws).

**Reviews.** The prereg was revised twice before any build, after two independent reviews (the commit message lists every finding). Prediction ids changed both times:
- the first fold made the first draft's P3 (M1 8/8, the view 7/7) R11;
- the second fold made theory core II a construction check, R12, because both reviews proved every statement in minutes;
- the predictions are now P1 (M3), P2 (the M2 sites, with a mutation canary) and P3 (no cross-kernel disagreement).

## Disclosure: what was probed before this prereg

A read-only design survey ran before this commit. Nothing of it is committed. In throwaway files it checked:
- six Bend core II laws in the form frozen here and eleven Lean core II theorems;
- M1's 8 PROVED laws and the view's 7, in a Lean model and statements of its own;
- the view's `L_disch_delay_nofree` counter-law at n = 1;
- five M3 PAR laws in Lean, under informal names.

How that shapes the predictions:
- M1 and the view are regression R11.
- The five M3 laws cannot be matched to law ids, so P1 is scored on all 73.
- Every core II statement was proved before this commit: by the first review (the first draft's 14 and 12), by the drafter (the three added at the first fold) and by the second review (all 15 and 14). So part A is regression R12, not a prediction.
- The first review also ran the survey's models on the M1 and M3 differential samples.

## Goal

**Part A.** Formalize, once, the core forms of Thm 6.6 and 6.7 that I29 (NAT) and I34 (SYM) will apply by application. Lemma 6.12 already landed in I25.
- **In Lean 4.34.0:** the textbook form.
  - Stab is a subgroup (`thm_6_6_id`, `_comp`, `_inv`).
  - For partial actions, the symmetries on a domain that keep it form a submonoid (`thm_6_6_id_on`, `_comp_on`) that carries runs from the domain to runs (`_run_on`).
  - Generators suffice (`_word`), as do powers (`_pow`), and symmetries carry runs to runs (`_run`).
  - For Thm 6.7: pasting, vertical composition, consequence along traces, migration sequences, and naturality up to an observation (`thm_6_7_a`, `_b`, `_c`, `_seq`, `_obs`).
- **In Bend 2:** per-step bundles that a proof consumes once (I42's design: Bend function values are affine).
  - `core_eqv_id` (the pointwise identity), `core_eqv_comp`, `core_eqv_inv`, `core_eqv_trace`.
  - A relational word of Data-indexed generators (`WordTo`, `EqvWord`, `core_eqv_word`) and powers (`IterTo`, `EqvPow`, `core_eqv_pow`).
  - `core_nat_paste`, `core_nat_vcomp`, `core_nat_trace`.
  - Naturality up to an observation, `core_nat_obs`. Each step gives its square under `ob` and a congruence step: the new version's step keeps the observation equal, so an unobservable residue stays unobservable.
  - A non-vacuity law per bundle.

**Part B.** Re-check every PROVED law of M1, M2 (including the 7 PROVED laws of the extracted view, `results/M2/extracted_m1`) and M3 in an independent Lean 4 kernel, so that records earn I2.
- **The statements.** Each law's Lean statement is frozen at this prereg, rendered from its IR (rule L3). A Lean theorem weaker than the law would make I2 meaningless.
- **The models.** The data types and statement-level declarations of every model are frozen (rule L2). The model functions are pinned by differential samples computed on the compiled Bend models (rule L7), including each SORT site's raw obligation `ro_<x>`, which the site predicate must use (rule L4). Each PROVED site also has a mutation canary (rule L11): with the site's protection removed from the facts, your re-emitted site predicate must go false where holon's mutated Bend model does.
- **The REFUTED laws.** The 21 REFUTED laws over the same model kinds are attempted as counter-laws. They count for disagreement, not for coverage. Each ends checked or resource-limited (timeout, recursion depth, heartbeats), and a resource claim must reproduce when the test reruns the file within 120 s.
- **The records.** They gain the lean4 entry, I2 exactly when it is checked. A law Lean cannot check stays I1 with its reason. G7 covers the 0.2/0.3 milestones and M3's PAR laws. Coverage is a metric.
- **The judge.** Every Lean file the tests accept passes the instrument's own check:
  - Lean 4.34.0, resolved and fingerprinted by the instrument;
  - exit code 0, no error, no `sorry`;
  - a sentinel theorem with a random name, whose axiom audit (with the checked theorems') must end the output;
  - axioms within {`propext`, `Quot.sound`}.

  No emitted Lean file may hold a `#` anywhere in its code, a word of the instrument's banned list, or an indented line that starts with a command keyword.

## What today's tree holds (computed at the prereg, base `be95d6d`)

| directory | PROVED | REFUTED (attempted) | Bend model | kind | Bend proof classes of the PROVED |
|---|---|---|---|---|---|
| `results/M1` | 8 | 8 (8) | `gen/M1/model/morph_rollup.bend` (and `morph_batchdata.bend` for one REFUTED law) | machine | evaluate, nat_split, noninterference, deadline, chain_revert |
| `results/M2` | 6 | 2 (2) | `gen/M2/model/morph_rollup.bend` (instrumented, oracle parameter `agg`) | machine_oracle | coercion_guard |
| `results/M2/extracted_m1` | 7 | 7 (7) | `gen/M2/extracted/m1/model/m1_view.bend` | machine | the M1 classes |
| `results/M3` | 86 (73 attempted) | 16 (4) | `gen/M3/model/header_length.bend` | linked | open_refl |

Not attempted in M3:
- the 5 REFUTED typed and UNDO laws: I30's `L_sort_realize_rollup_363_4a64383b` and `L_sort_tag_rollup_279_e01ea84a`, and I27's three REFUTED UNDO laws. They run over the typed and UNDO models, outside the Lean emitters' kinds;
- I31's 13 PROVED and 7 REFUTED DISCH laws, over a `holon-facts/0.3` document no emitter reads. These are carved out at the move onto `be95d6d`.

**Stale hashes on the integration line.**
- **Statement hashes.** I31's holon-rules/1.4 rebinding moved `laws/M3/REGISTRY.json` again, without regenerating the records. At `be95d6d`, these carry statement hashes older than the registry's:
  - the 80 M3 PAR records and their 77 `LAWS.bend` files (the three PAR-weak laws have none);
  - I30's 3 typed records and their 3 files;
  - I27's 8 UNDO records and their 8 files.
- **Generator hashes at `be95d6d`.**
  - The M1 and M2 records carry their closures' current hashes: holon-ir/0.2 `1ad5c44b…`, holon-ir/0.3 `3ad5410b…`. F36 regenerated them.
  - The 3 typed records carry `8c224786…`, where run3's closure hashes to `98c5af30…`.
  - The 8 UNDO records carry `03ffc198…`, where the UNDO closure hashes to `50f85e03…`.
  - I31's 35 DISCH records carry `5ceefbd0…` (33) and `2c9d9596…` (2), where the DISCH closure hashes to `d3351397…`.
- **Your edit of `holon/lean.py`.** It sits in the holon-ir/0.2 and 0.3 generator closures and in run3's GEN3 closure, which the UNDO closure contains, so your edit moves all of these again.
- **I42's tests.** I42's merged tests (`tests_m3/test_theory_core.py`) use `holon.lean.check_text` and `FORBIDDEN`, which you edit; keep them passing. I42's R2-R4 and R6 are red at the base until its follow-up (R8).
- What I43 does about it:
  - it regenerates the PAR records (they gain lean4) and brings their 80 statement hashes to the registry (R1);
  - it does **not** regenerate the 3 typed, the 8 UNDO or the 35 DISCH records (gap LP-G9). R1 requires them unchanged.

  Regenerating those records runs run3's typed model and its live replay. That needs the full replay toolchain: forge, solc, sol_deps, the morph checkout and the m3init deployment cache. This environment does not have it, and it is reserved for another stream; CI installs it.

**Differential samples frozen in the sidecar:**

| model | samples |
|---|---|
| M1 `morph_rollup` | 1290 |
| M1 `morph_batchdata` | 28 |
| M2 `morph_rollup` | 4241 |
| the view | 1105 |
| M3 `header_length` | 711 |

Every action constructor of a machine model succeeds in some sample: M2's samples take the M1 laws' traces, which are over the same facts document. Every hit predicate and every raw obligation takes both values.

**Perturb canaries frozen in the sidecar.** Each comes with the compiled Bend model's evidence:
- M1 and M2: `L_disch_delay_pay`, where `ob_lci_of … = 2` becomes `= 3` (M2's comes from the view). Bend evaluates the left side to 2 at the record's witness, which the canary's kept proof fixes.
- M3: `L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BatchIndex_v2`, with the first two cells of its right side swapped. On a seeded record Bend gives the unswapped, differing cells.

**Site canaries frozen in the sidecar** (rule L11): all 6 PROVED M2 sites have one. Each holds the mutation and the sample (a trace and an action) where holon's mutated Bend model makes the site predicate false and the hit predicate true.

**Partial gates.** On a copy of `be95d6d`, `holon gate --checks G3,G7` passes for M0, M1 and M2. For M3, `--checks G3,G5,G7,G11V,GEVID` passes except G11V, which fails on I31's `L_disch_rev_initializable_120_d9a34b48` only ("non-vacuity unknown"; the lead's Q36 labels it pending). So R6's M3 part fails on that item, for a reason outside I43, until I31's follow-up. G9 passes; G11 fails on I30's 3 typed records only (their statement hashes are stale since holon-rules/1.4; Q36). R6's M3 list is `84c185f`'s (see R6): G9 passed on `fbd14d3` already, and G8, in CI's partial M3 gate, needs solc. M1 and M2's G7 says "Lean: not applicable".

## Deliverables (summary; the contracts have the details)

**Part A**
- **`holon/gen/theory2.py`** writes, as fixed text: `gen/M3/theory2/core/{LAWS,PROOF}.bend` (15 laws) and `gen/M3/theory2/lean/TheoryII.lean` (14 theorems). It is generic and imported by no generator closure.
- **`python -m holon theory2 --milestone M3 [--root DIR] [--out DIR] [--kernels] [--check]`**. With `--kernels` it also writes `report.json`.

**Part B**
- **The emitters.** `holon/gen/lean_machine.py`, `lean_mlaws.py`, `lean_mproofs.py` (evaluate, nat_split, noninterference, deadline, chain_revert, counter_decide), `lean_sites.py` (SORT site and hit predicates per R8–R10 over the raw obligations; coercion_guard) and `lean_linked.py` (model, statements, open_refl, counter).
  - Nothing in the transitive import closure of the emitters and `holon/lean.py` imports the Bend emitters, `oracles.py`, `holon/sorts/*` or an instrument.
  - Nothing there uses a dynamic import or reflection: `importlib`, `__import__`, `exec`, `eval`, `getattr`, `vars`, `globals` and `__dict__` are all banned.
  - They read the facts and codec JSON themselves, never the sidecars or `tests_m3/`.
  - They name no target.
- **The target library's Lean twin.** Hand-written target input under `spec/M1/lib/`, in a file not matching `*.lib.json`.
- **`holon/lean.py`, generalized.** It gains:
  - per-law facts and model-kind dispatch;
  - one `report.json` per Lean directory, and model files `models/<stem>.lean`;
  - `kernel_entry` with a reason and detail for `not_run`;
  - `--check`;
  - `--emit-only` (write every file from the documents as they are, run no Lean; the site canary uses it on a mutated copy);
  - `strip_comments` lexing `«…»` atomically (I42 Question 5).

  `holon.lean.applicable` keeps its meaning for the intake (I41-R3 pins it); the set I43 covers is a function of its own.
- **Records** (`holon/records.py`) gain the lean4 entry for M1, M2, `M2/extracted_m1` and the M3 PAR records. Statuses are unchanged. The regeneration steps:
  - `holon run`, `holon lean`, then `holon run` again;
  - for M2, also `holon differential --milestone M2`;
  - for M3, `holon run --milestone M3 --laws <PAR ids>` only (the typed and UNDO records are not regenerated).
- **The schema.** `spec/schemas/result_record_v2.schema.json` gains optional `reason`, `detail` and `reading` on kernel entries.
- **G7** for holon-ir/0.2 and 0.3 (`holon/gate.py`), and a Lean G7 for M3's PAR laws (`holon/sorts/gate3.py`). Each milestone has semantic canaries: flip, and perturb on the sidecar's canary law.
- **Lean G3** scans every Lean directory, `models/` included, and names each offending file.
- **Metrics:** `cross_kernel_coverage`.
- **Report:** `docs/iterations/I43.md`, with the prediction table and the P3 counts by status, result and reason.

## Predictions (key I43 of `spec/M3/predictions.json`)

| id | claim |
|---|---|
| P1 | M3: 73/73 PROVED PAR laws are checked in Lean (I2), each with its frozen statement and elaborated type, re-checked by the instrument within 120 s with allowed axioms. Five were probed under informal names; scored on all 73. |
| P2 | M2: the 6 PROVED SORT-site laws are checked in Lean (I2), as P1, each site predicate reaching its raw obligation, and each passes its mutation canary (rule L11). All 6 are scored. Unprobed. |
| P3 | Zero cross-kernel disagreements over the 115 attempted laws (94 PROVED, 21 REFUTED): no `failed` lean4 entry; each REFUTED checked or `not_run` for timeout, recursion depth or heartbeats only, the limit reproducing within 120 s; every checked REFUTED entry states its frozen counter-law. |

**Regressions and construction checks (not counted):**

- **R1: statuses and Bend are unchanged.**
  - Every Bend file under `gen/M0`–`M3` is byte-identical, except PAR law files' `statement_hash` lines, which may change only to the registry's value.
  - The M3 PAR records carry the registry's hashes.
  - The 3 typed and 8 UNDO records are exactly as at the prereg.
  - No other record gains lean4.
- **R2: the instruments.** Both sidecars are the instrument's computation, and:
  - the Bend core II has 15 open laws, and the Lean core II elaborates with 14 placeholder warnings;
  - the 136 Lean law statements elaborate over the frozen interfaces;
  - the differential samples are well-typed and not trivial;
  - the perturb canaries and the site canaries are evidenced;
  - the instrument rejects the first review's cheat files and accepts a clean file;
  - the semantic and resource-limit readings match Lean's messages (probes);
  - the import reader flags every bypass the reviews found.
- **R3: the CLIs.** They are deterministic, `--check` passes, theory2's report binds every kernel result, and `--check` still passes in a copy without the two sidecars and without `tests_m3/`.
- **R4: the code.** The import closure stays off the Bend side and uses no dynamic import or reflection; the Lean modules are generic; no `holon/` file names the sidecars or the instrument; `theory2.py` is generic and outside the closures; `tests_m2/_i15.py` is pinned by sha256.
- **R5: the records.** lean4 entries are present, I2 exactly when checked, and `not_run` carries an allowed reason and a detail. Every record validates against the schema; for `results/M2/extracted_m1`, whose records are `derived` by design, only the kernel entries and the class are validated. The coverage metric is present.
- **R6: the gates.**
  - The partial gates pass, with G7 reporting coverage per Lean directory.
  - Lean G3 catches a planted `sorry` in a model file of every Lean directory.
  - The full gates of M0–M2 pass. They need the replay toolchain at `config/holon.json`'s paths (`replay.solc`, `replay.forge`), which CI has; here solc is missing, so the test fails naming it.
  - `strip_comments` reads `«…»` whole.
- **R7: M0's Lean outputs.** M0's Lean files and report are byte-identical.
- **R8: I42's outputs.** No I43 commit (one that writes `gen/M3/theory2/`, `gen/<M>/lean/` for M1-M3, `holon/gen/theory2.py` or `holon/gen/lean_*.py`) changes a file under `gen/M3/theory/`. The base holds I42's outputs, so this checks them. `holon basis --milestone M3 --check` already refuses at `be95d6d` (the stale PAR law files). After I43's PAR regeneration the lead, not the I43 build, regenerates I42's `basis/header_length.json`, `report.json` (with `--kernels`) and `spec/M3/lib/theory_core.json`, in a commit that writes nothing else, as the I42 merge note plans.
- **R9: the models agree.** The Lean model files prove every differential sample by `decide` under the instrument's check; every Lean file of every Lean directory, `models/` included, obeys the file rules of its kind; every law file's model section is its model file's.
- **R10: the semantic canaries.** Per milestone, G7 reports flip and the sidecar's perturb canary, each rejected for a semantic reason. The test also builds each perturb canary from the committed law file (statement replaced in the raw source, proof kept) and requires a semantic rejection after elaborating to the end.
- **R11: what the survey probed.** M1 8/8 and the view 7/7 are checked in Lean (I2).
- **R12: theory core II.** The Bend core II is PROVED under bend and `--verdict`, and the Lean core II passes the instrument's check, each within 120 s.

## Outcome paths

- `gen/M3/theory2/`
- `gen/M1/lean/`, `gen/M2/lean/`, `gen/M2/extracted/m1/lean/`, `gen/M3/lean/`
- `gen/M3/laws/` and `gen/M3/proofs/` (statement-hash headers only, R1)
- `results/M1/`, `results/M2/`, `results/M3/`
- `spec/schemas/result_record_v2.schema.json`

I43 writes nothing under `gen/M3/theory/`, `laws/`, `facts/` or `spec/M1/facts/`. No Bend file under `gen/M0`–`M3` changes beyond R1's headers. The typed and UNDO records stay as they are.

## Rules

- **AGENTS.md is binding.**
  - **Frozen inputs.** The sidecars freeze the Bend and Lean core II statements, the Lean law statements, the model interfaces, the differential values and both kinds of canary. A statement that turns out false or unprovable is a MISS, reported with the kernel's output; it is never edited.
  - **A law Lean cannot check** stays I1, with its reason in the allowed set and a detail. A REFUTED law ends checked or resource-limited, and the limit must reproduce.
  - **Any other Lean rejection** (forbidden word, bad axioms, missing theorem) is a `failed` entry. It is a blocking finding, never relabelled.
- **Lean files.**
  - No `#` anywhere in an emitted file's code: no `#eval`, `#exit` or `#print`, and no array or BitVec literal syntax (write `(n : BitVec w)`).
  - No word of `tests_m3/_i43.py::LEAN_BANNED`, and no indented line that starts with a command keyword (`set_option … in`, the tactic form, is allowed).
  - A perturb canary keeps the law's proof. So each canary law's proof must fail on the perturbed statement for a semantic reason: `decide`, `rfl` (term or tactic), `exact rfl`, `Eq.refl` or `fun _ => rfl`, not a `simp` or `omega` that leaves goals.
- **Hand proofs (gap TC-G2).** The core II proofs, in Lean and in the Bend per-step form, are hand-written once, generically, and emitted as fixed text by `holon/gen/theory2.py`. Q14b names 6.6 and 6.7 in Lean; the Bend forms follow I42's reading.
- **Independence.**
  - The Lean emitters import nothing from the Bend side, transitively, and use no reflection.
  - They read the documents themselves, never the sidecars or `tests_m3/`.
  - The Lean twin of the target library is target input (common mode, stated in every lean4 entry's reading).
- **Witnesses come from the records.** Counter-laws use the records' witnesses. Differential values come from the compiled Bend models (AGENTS rule 5).
- **No special-casing.** No law id, target name or source file appears under `holon/`.
- **Budgets** come from `config/holon.json`: 120 s per file per kernel, wall clock.
- **Test edits.** `tests_m3/test_refute.py`'s I40-R2 is already narrowed in this prereg, with its line in `spec/M3/amendments.jsonl`: kernels may gain exactly one lean4 entry, and I1-shared becomes I2 exactly when it is checked. Two more amendments are known at the move, because the first build had to make them; the build makes them again, each with its one amendment line:
  - C1 allows the frozen identifier `eta2` in `holon/gen/theory2.py` (`tests_m2/test_target_agnostic_exhaustive.py`, a path an M3 prereg commit may not change);
  - C2 lets the view's decided records gain I41's `prover` field under I40-R2 (none of the 15 view records has it, and I43 regenerates them).
  No other test changes.

## Questions for the human (raised by the prereg)

1. **Is `results/M2/extracted_m1` in Q8's scope?** I43 counts its 7 PROVED laws as promoted, so the total is 94. They are PROVED records of M2, re-runs of the M1 laws on the extracted model's window view, and Q8 rules out hand-picked subsets.
2. **The Lean twin of the target library.** Is it acceptable?
   - It holds hand-written Lean definitions of the M1 target builtins (`win_at`, `agg`, `bump_f` and the rest), as target input.
   - It lives under `spec/M1/lib/`, in a file that does not match `*.lib.json`, so it stays out of the generator closures' glob.
   - It is pinned by the differential samples (rule L7).
   - It shares its source with the Bend library (common mode; I9 Question 4).
3. **Are these readings acceptable for I2, stated per law in the record's `reading`?**
   - Byte-valued Lean records against Bend's U32 cells, a narrower domain.
   - An oracle parameter read as a Lean function, against Bend's finite tables. Lean's theorem implies Bend's.
   - Premises as hypotheses, against Bend's pins.
4. **M3 PAR record regeneration.** I43 regenerates the 80 M3 PAR records and, as a side effect, fixes their stale statement hashes. Should the lead regenerate them first, separately, so that I43's records change only by the lean4 entry?
5. **The typed, UNDO and DISCH records** (gap LP-G9). I43 does not regenerate I30's 3 typed, I27's 8 UNDO or I31's 35 DISCH records. Their statement or generator hashes are stale already at `be95d6d`, and I43's edit of `holon/lean.py` moves the closures again. R1 keeps them as they are. They should be regenerated after I43, last.
   - Regenerating them builds run3's typed model from the deployment and replays every REFUTED entry on the real contract. That needs the full replay toolchain: forge, solc, sol_deps, the morph checkout and the m3init deployment cache. CI installs it with `.github/ci/install_toolchain.sh`.
   - Will the lead regenerate them with that toolchain, after I43? It must be last: any later edit of anything in run3's GEN3 closure (`holon/lean.py` and what it imports among them) leaves them stale again.
6. **M2's site predicates.** On every PROVED site the site predicate is constantly true, because coercion_guard never uses Reach.
   - What pins it now: the differential pins where a site is hit (`hit_<x>`) and the raw obligation (`ro_<x>`); rule L4 requires the site predicate to use `ro_<x>`; and rule L11's mutation canary requires it to go false, at one sample, when the site loses its protection.
   - What does not: how it behaves elsewhere is pinned only by the Lean proof and the two REFUTED sites. Is one canary sample per site enough?
7. **Heartbeats as a reason.** Q8 names timeout, recursion depth and unsupported form. I43 also allows two more:
   - `heartbeats` (Lean's deterministic timeout, a resource limit like the other two) as a final reason;
   - `no_report` and `toolchain_unavailable` in the schema, as transient states never committed.

   Is `heartbeats` acceptable as a reason a law stays I1?
8. **The view's records and the schema.** `results/M2/extracted_m1`'s records have `ledger_match: "derived"` by design, which v2 rejects (`tests_m2/test_ledger.py` asserts so). One of them, `L_tag_BVH`, is an UNKNOWN stub with no v2 fields. R5 validates only their kernel entries and class. Should derived records get a schema of their own instead?
9. **I42 and R8.** Answered by Q35 (a fresh I43 prereg on top of the merged I42): this prereg sits on `be95d6d`, which holds I42, so R8 checks I42's outputs.
12. **I31's DISCH laws.** Answered at the move onto `be95d6d`: they are not attempted, PROVED or REFUTED. They need a Lean model of the `holon-facts/0.3` document and DISCH proof classes, which is later work. Until then their PROVED verdicts have one kernel only, and `cross_kernel_coverage` for M3 reads 73/86.
10. **Hand proofs beyond Q14b's wording** (as I42 Question 1). The Bend core II proofs are hand-written once. Is that acceptable, or should they come from per-class generators?
11. **Intake-decided records and G7.** `holon.lean.applicable` keeps its holon-ir/0.1 meaning for the intake, as I41-R3 pins, so `required_kernels` for M1 and M2 excludes lean4. A record that the intake later decides PROVED in M1 or M2 then has no lean4 entry until `holon lean` and `holon run` run again, and L9's G7 fails until they do. Should the intake run the Lean step for the 0.2/0.3 milestones? That would need I41-R3 amended.
