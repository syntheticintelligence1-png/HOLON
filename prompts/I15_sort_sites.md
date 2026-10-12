# I15: Sorts II, per-site SORT laws and the rules registry

Rendered from `docs/BUILD_PLAN.md` §4, I15. Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first, then `docs/BEND_NOTES.md`. Milestone M2. These are the **first generated M2 laws**. Whitepaper §5.6 (SORT), §7.2, §7.3 (obligation coherence), §7.8 (sorts compiled to Bend types: `realize` needs a non-negativity proof), Thm 6.18 (localization; the freezing condition), App. E (SORT basis), §8.6, §9.4.

The acceptance tests are `tests_m2/test_sort_sites.py` (builder A) and `tests_m2/test_sort_site_outcomes.py` (builder B). **The docstring of `tests_m2/test_sort_sites.py` is the contract**: CLI, law IR, the site term, hit-point rules R7–R11, `DERIVATION.json`, `REGISTRY.json`, `obstructions.json`, the derive diff and the instrumented model. The docstring of `test_sort_site_outcomes.py` adds B's part: proofs, refutation per entry point, records, replay report and the M2 gate. `tests_m2/_i15.py`, `tests_m2/fixtures/sort_sites/` and `spec/M2/lib/sort_sites.json` are instruments fixed at the prereg. Do not edit them; if one is wrong, it is a Question and an amendment in `spec/M2/amendments.jsonl`, reported under Surprises.

## Goal

One obligation per subtraction site realized in unsigned arithmetic, **whether or not a human modelled a require**. Every `-` site of the frozen I13 assignment gets one IR 0.3 law: for every reachable state `s` and action `a`, every evaluation of the site's subtraction while `a` runs from `s` has minuend ≥ subtrahend. Failures localize to a site (Thm 6.18): the :363 underflow (O27) becomes one law with one witness per entry point, each replaying as Panic 0x11 at that line. Coherence obstructions (§7.3) surface at the guard sites that read a cursor written by another action family.

## Inputs that exist (do not change them)

- `gen/M2/sorts/assignment.json` (I13, frozen): 10 sites keyed by span, each with `expr`, `sort`, `obligation`, `occurrences` (action + `guards[i].require|expr` or `effects.<f>`, or `defs.<d>.body`), and the writer `provenance` of `qpend`, `qlen`, `Entry.tot`, `Entry.n`. Its `sorts_sha256` goes into the registry.
- The M2 fact documents are I13's: `facts/morph_header.json` (0.1, no sites), `spec/M1/facts/morph_rollup.json` and `spec/M1/facts/morph_batchdata.json`. All 10 sites are in `morph_rollup`. **Never edit `spec/M1/facts/*.json`.**
- `spec/M2/lib/sort_sites.json` (new, prereg): `realization_check_reasons = ["panic:0x11"]`.
- IR 0.3 (`holon/ir.py`, `spec/schemas/law_ir_0_3.schema.json`, `holon/gen/mlaws.py`), refs (`holon/gen/refs.py`), Reach and the core library (`holon/gen/core.py`, `mproofs.CORE_MODE`), prover separation (`mpipeline.layout`, `write_pair`), oracle tables (`holon/gen/oracles.py`), the refuter (`holon/js/explore.mjs`, `spec/M1/policy_hints.mjs`), the M1 trace harness (`replay/M1/solidity/HolonTraceReplay.t.sol`, `holon/mreplay.py`), `spec/M1/mutations.json`.

## The ten sites and what is predicted for each (spec/M2/predictions.json, key I15)

| law id | site | what it is in the real code | predicted |
|---|---|---|---|
| `L_sort_site_rollup_363_1fc7f88a` | `W + cstart - t`, Rollup.sol:363 | checked `proofWindow + startTime - block.timestamp` | **REFUTED**, witnesses for commitBatch, commitBatchWithProof, commitState, each Panic 0x11 at :363 (P3) |
| `L_sort_site_rollup_636_e68daf06` | `idx - 1`, Rollup.sol:636 | checked `finalizedStateRoots[_batchIndex - 1]` | **REFUTED** by finalizeBatch(idx 0) at lfi 0, Panic 0x11 at :636 (P4; the plan expected PROVED) |
| `L_sort_site_rollup_644_660_e68daf06` | `idx - 1`, effect of finalizeBatch | checked deletes at :657–660, after :636 passed | PROVED, coercion_guard (P1) |
| `L_sort_site_rollup_441_b4cd5068` | `idx - lfi`, revertBatch | window offset (no code subtraction) | PROVED, coercion_guard, guard `idx > lfi` (P1) |
| `L_sort_site_rollup_485_495_b4cd5068` | `idx - lfi`, challengeState effect | window offset | PROVED, coercion_guard, guard `lfi < idx` (P1) |
| `L_sort_site_def_w_b4cd5068` | def `w`: `idx - lfi` | window offset | PROVED, coercion_guard, path condition `in_win` (P1) |
| `L_sort_site_def_bvh_at_6126d1f1` | def `bvh_at`: `idx - lci` | shadow offset | PROVED, coercion_guard, path condition `!(idx <= lci)` (P1) |
| `L_sort_site_def_bvh_at_e064679d` | def `bvh_at`: `(idx - lci) - 1` | shadow offset | PROVED, coercion_guard, same condition (P1) |
| `L_sort_site_l1messagequeuewithgaspriceoracle_325_f89daf17` | `btot - bn`, finalizeBatch | Rollup.sol:742, inside `unchecked` | UNKNOWN: needs `tot >= n` on every window entry (P2) |
| `L_sort_site_def_lci_356891e4` | def `lci`: `lfi + len(win) - 1` | storage variable in the code | UNKNOWN: needs a non-empty window (P2) |

Plus: P5 (MUT2: the :363 law loses commitBatchWithProof in the derive diff, stays REFUTED through the two others, and a new :360–364 law is REFUTED through commitBatchWithProof) and P6 (exactly three coherence obstructions, at the `enq_first` call sites of the delay guard, registers `qlen` and `qpend`).

The rule that decides P4 is R8 (contract): a require whose span is the site's span and whose reason is a realization-check reason (`panic:0x11`) is the facts' **model of the code's own checked subtraction**. The obligation is evaluated just before it, so a human-modelled check never discharges the obligation it models. That is what makes :363 refutable, and it applies to :636 the same way. Do not special-case either site. The `site` annotations on the :363 guards, guard `note`s and docs are hand-written hints: holon must not read them (I13's honesty rule carries over).

## Builder split

Two sequential agents. A's outputs are fixed by the contract, so B can start from them.

### Builder A: rules registry, derive, sites, instrumented model, obstructions

Owns: `holon/rules/__init__.py`, `holon/sorts/sites.py`, `holon/sorts/check.py`, the `derive` subcommand in `holon/__main__.py`, the site term in `spec/schemas/law_ir_0_3.schema.json` and `holon/ir.py` (`render_term`), the `site:<id>` ref in `holon/gen/refs.py`, the site term's emission in `holon/gen/mlaws.py` (`M.site_<x>(a, s, ..tables)`), `laws/M2/`, `gen/M2/sorts/obstructions.json`.

- **`holon/rules/__init__.py`.** `RULE_CATALOG_VERSION = "holon-rules/1.0"`, `CATALOG = {"SORT": {"site": <holon.sorts.sites>}}`, and `derive(...)` with the CLI `python -m holon derive` of the contract. It writes the laws, `REGISTRY.json`, `DERIVATION.json`, `obstructions.json` and, with `--against`, the derive diff. It checks that the assignment is not stale and refuses otherwise (exit 2). Law ids come from `law_id(site id)`.
- **`holon/sorts/sites.py` (rule SORT-site).**
  - `law_id`.
  - The hit points of R8–R10, from the facts, the I13 site and the sidecar.
  - The IR of each law.
  - The site spec that the `site:<id>` ref hashes.
  - `instrumented_model(facts_path, derivation, root=None)`: the M2 model text, then `GHOST_MARKER`, then one `def site_<x>(a: HAct, s: HSt[, tables]) -> Bool` per law. Each mirrors the decision chain of each entry point up to its hit and evaluates the path condition and `is_le(subtrahend, minuend)` there. It is `True` where the action stops earlier or does not reach the site.
  - Also one `def hit_<x>(a: HAct, s: HSt[, tables]) -> Bool` per law: true iff the evaluation reaches a hit (the at_site premise of the plan's `∀p. at_site(p, s0, ℓ) → nonneg(d_ℓ)`). B states non-vacuity with it: without it, G11V's inhabitant would be Reach alone, which s0 inhabits, and a ghost that never reaches its hit would make every site law PROVED and vacuous.
  - Definition sites get one ghost function per (site, definition reaching it), true for all arguments where the body's own path condition implies the site's non-negativity. Each call site conjoins them.
  - Ghost definitions only; no state field; append-only after the marker.
- **`holon/sorts/check.py`.** The coherence obstructions of R11, from the facts and the frozen assignment's provenance.
- **Toy fixture.** `tests_m2/fixtures/sort_sites/toy_sites.json` is your fast loop: `holon sorts --facts <toy> --out D`, then `holon derive --milestone T15 --facts <toy> --assignment D/assignment.json --out L`. Its expected laws, hits and obstruction are in `TestToyDerivation`. B runs it end to end in `TestToyOutcomes`.
- **Honesty (tested):** `TestDeriveHonesty` reruns I13's strip and rename mutations (`tests_m2/test_sorts_honesty.py`) in a copy and requires the same derivation; `TestGenericCode` forbids site spans, site law ids and site hashes anywhere under `holon/`, and target names or reason text (`panic`) in `holon/rules`, `sites.py` and `check.py`. R8 reads spans, the reasons table and the sidecar, never the hand-written `site` annotations.
- **Commit** the derived `laws/M2/` and `gen/M2/sorts/obstructions.json`. A's tests (`test_sort_sites.py`) must pass before B starts. Report P6, the derivation half of P3, P4 and P5, and the rule-derived tables.

Verified Bend facts for the ghost functions (probes on a toy machine in the prereg scratch; re-verify on your own toy):
- A ghost function must take `a` first and match it first, then call a per-action helper that matches `s` (`match s` before `match a` is rejected: "can't be matched in this position"). Mirror `step`/`step_<a>`.
- A decision helper `gs_<a>_<i>(c: Bool, ..) -> Bool` mirrors `dec_<a>_<i>`. On `False{}` it returns `True{}` (the action stops, no hit). On `True{}` it continues, or evaluates the hit.
- `ite(Bool, cond, x, y)` is fine for path conditions inside a ghost definition.
- Bend definitions see only definitions above them: the ghost section, appended last, cannot be read by the model.

### Builder B: proofs, refutation per entry point, replay, records, gate M2

Owns:
- `mproofs.coercion_guard` and the core catalog lemmas it calls (`holon/gen/core.py`);
- the SORT-site search in `holon/js/explore.mjs` (stages S1–S3), and the at_site inhabitant search it shares;
- the SORT-site inhabitant in `holon/inhabit.py` and its G11V check (non-vacuity);
- the pipeline changes in `holon/mpipeline.py`: per-entry counter-laws, records `site` and `witnesses`, `--laws`, and not deleting other commands' `gen/M2` outputs;
- `holon/records.py` (model_assumptions keeping the ledger cone);
- the M2 path of `holon/replay.py` and `holon/mreplay.py`, with `panic_site` localization;
- `replay/M2/report.json`;
- M2 wiring in `holon/gate.py` (G1, G2, G4, G5, G6, G7, G9 for IR 0.3) and `holon/mcanary.py`;
- `spec/bindings/M2.json`;
- the two optional properties in `spec/schemas/result_record_v2.schema.json`;
- `results/M2/*` (records, summary, deps, splits, metrics, gate report).

- **`coercion_guard`** (contract in the outcomes docstring). It mirrors the ghost chain, and at each hit derives non-negativity from ONE passed condition (never two combined) through `C.` (imported core, F-M2-04): zero or more `and_left`/`and_right` projections of that condition, then one comparison lemma (def `w` needs `and_left` on `in_win`, then `ge -> le`). It never assumes reachability, and holds for every state. Add the lemma shapes to `holon/gen/core.py` `CATALOG`, each proved by its class generator, never by hand:
  - `gt -> le`, `lt -> le`, `ge -> le`;
  - `and_left` (already there);
  - `is_le(a,b) == False -> is_le(b,a)`;
  - `is_le(a,b) == False -> is_le(1, sub(a,b))`.

  Every accepted `PROOF.bend` imports `gen/M2/laws/<id>/LAWS.bend as Laws` and defines `Laws.<law name>` (audit F-M2-07; tested). A guard's equation is `Type`, so it can be used once (`docs/iterations/I8.md`); if one guard serves two hits, derive the Bool fact once and share it.

  The nat2 class needs one more ex-falso candidate, for a hypothesis `{X == False{}}` whose `X` computes to `True{}`: `core_false_ne_true(Equal.sym(Bool, True{}, False{}, e))`. Verified Bend pattern for a guard on a computed Bool: pass the condition as a parameter with its equation and match the parameter. For example, `cg(c: Bool, .., e: {Nat.is_gt(idx, lfi) == c : Bool}) -> {M.gs_..(c, ..) == True{} : Bool}` with `match c`. In the `True{}` case `e` has become `{Nat.is_gt(idx, lfi) == True{}}`, and the caller passes `{==}`. Bend and BendTT both accepted this on the toy.
- **Non-vacuity** (I3 G11V, §12.3 L21; contract in the outcomes docstring). For a SORT-site law, `holon.inhabit` states the at_site premise: `law nv_<id lower>: exs s, its Reach evidence, a. {M.hit_<x>(a, s) == True{} : Bool}`, at a reachable `(s, a)` found by S1/S2 and proved like a counter-law. G11V fails a PROVED site law without it. The toy is your fast loop: every PROVED toy law must be inhabited, and `TestToyOutcomes.test_toy_site_without_its_guard_is_refuted` checks that removing the toy's guard `idx > lfi` turns its PROVED window-offset law REFUTED.
- **Refutation per entry point** (S1 boundary variants, S2 prefixes, S3 neighbourhood; budgets in the key's thresholds). A counter-law for every witness, Bend-checked, in `gen/M2/proofs/<id>/entry_<e>/PROOF.bend`. The Reach witness is `run(prefix, s0)` with its R0/RStep chain (`mlaws.reach_chain`); the toy probe checked this form. Primary witness = first entry point with a checked counter-law.
- **Replay.** `python -m holon replay --milestone M2` replays every REFUTED per-entry witness (prefix ++ [action]) through the M1 harness (`replay/M1/solidity/HolonTraceReplay.t.sol`). Reuse that harness unchanged; the prereg instrument runs a byte copy of it taken at the prereg, so editing it buys nothing. It locates the last step's Panic: the first debug-arena node that reverts with `Panic(uint256)` in a `forge test --debug --dump` of that step, mapped by the frame's runtime source map to the last user-source instruction. Run the prefix in `setUp` so that the dump holds only the last step (see `tests_m2/fixtures/sort_sites/HolonSiteInstrument.t.sol.txt`). Holon's own code must not import or copy the test instrument. Write it yourself. Records get `witnesses[e].replay`.
  - Also run the refinement corpus: the M1 rule (seed 20261011, 300 traces) on the M2 model. The records' `refinement_refs` name `replay/M2/report.json#/refinement/per_action/<a>`.
  - Do not touch I16's `replay/M2/go/`, `replay/M2/solidity/HolonCodec.t.sol` or `replay/M2/implementations.json`.
- **Gate M2.** `holon bind --milestone M2`, `holon run --milestone M2`, `holon replay --milestone M2`, `holon metrics --milestone M2`, then `holon gate --milestone M2` must pass. G1 must regenerate both the run's outputs and the derive outputs and compare them. G4 needs at least 10 canaries of at least 3 kinds over the 0.3 site laws (F-M2-05/06). Examples:
  - a PROVED law with its claim flipped;
  - a coercion proof with its lemma call replaced by `{==}`;
  - an UNKNOWN law's site with a coercion proof forced;
  - LIVE_FIELDS derived from `Machine.reads`.

  Each must be rejected for a semantic reason.

## Foundation this iteration relies on (audit round M2/1, `audit/M2_findings.jsonl`, lane 2)

The lead plans these before I15-A. For each, if it has not landed when you start, implement the part I15's tests need, generically, and say so in the report.

- **F-M2-10, F-M2-02.** G2 must hash IR 0.3 with refs (`check_registry_multi`, any milestone). G1, G9 and G4 must handle 0.3 laws. `gate.g4_machine` must build with `reach=` and the core. Your law ids match `^L_` on purpose, so the existing globs work.
- **F-M2-03.** Refs closure. Your `site:<id>` ref follows the contract. Keep the step ref as the foundation defines it.
- **F-M2-11.** Parametric Morph model. The contract binds whatever oracle tables the M2 model of the rollup threads. With none, the model is the stand-in model and `model_assumptions` must still list the ledger cone. The predictions do not depend on this choice. **Do not decide it yourself.** Follow the lead's decision.
  - **The lead's decision.** I15 builds on the parametric M2 Morph model delivered by the audit-fix lane (FX2). The rollup facts compiled for milestone M2 thread the oracle parameters that `spec/M2/lib/oracles.json` names, and `agg` and every other modelled oracle appear only as the sidecar's concrete instance.
  - The refuter, the inhabitant search and the counter-law witnesses instantiate every oracle parameter with that concrete instance (the I12 design). A witness that needs a stored nonzero blob hash is therefore still found.
  - Sidecar entries that cannot be routed through the facts without new facts are `not_in_scope` with a reason, and stay in the ledger cone.
  - If the parametric model breaks a term-size or C-arity limit for a law, that law is UNKNOWN with the reason (the I12 fallback). It is never moved back to the stand-in model.
- **F-M2-12.** M2 records keep the ledger cone (tested: `abs-nat-tokens`, `scope-rollup-coverage-debt`).
- **F-M2-25.** `holon run --milestone M2` must not delete `gen/M2/diagram`, `gen/M2/sorts`, `gen/M2/oracles` or `gen/M2/evidence.json`. Today `run_m1` runs `shutil.rmtree(gen)` on the whole gen dir. That is a **data-loss hazard**: fix it first, before any M2 run. G1 must compare only what each command regenerates.

## Rules

- **Generate, don't hand-write.** Laws come only from `holon/rules` and `holon/sorts`, with provenance in `DERIVATION.json`. `holon derive` reproduces `laws/M2/` byte for byte. Never edit a generated law, model or proof. A fix goes into the generator.
- **Never tune to a prediction.**
  - A predicted status that does not come out is a Surprise, reported with the attempts and bounds.
  - Do not special-case law ids, sites, spans, actions or the realization reason.
  - Do not edit `spec/M1/policy_hints.mjs` or the sidecar to reach a witness.
  - The search stages and budgets are fixed in the key.
- **Witnesses come from the compiled model.** REFUTED needs a Bend-accepted counter-law. The refuter only proposes.
- **No escape hatches.** No holes, no `@unsafe`, no foreign imports, no laws without proofs.
- **`holon/sorts/*.py` stays under I13's static check** (`tests_m2/test_sorts_unit.py`):
  - only the standard library and `holon` are imported, with no `subprocess`;
  - no Morph identifier from the I6 list, not even in a docstring (`commitBatch`, `finalizeBatch`, `Rollup`, `morph`, ...);
  - no quoted Morph field name (`"win"`, `"lfi"`, `"Entry"`, `"tot"`, ...).

  The I6 grep (`tests_m2/test_target_agnostic.py`) covers `holon/js/explore.mjs`, `holon/mpipeline.py`, `holon/mcanary.py` and the other generic modules too.
- **M0 and M1 do not change.**
  - `gen/M0` and `gen/M1` stay byte-identical (GEN_PIN). Ghost sections and coercion_guard are M2+ only; M0/M1 proofs keep their pasted CORE.
  - M0/M1 records stay unchanged modulo `seconds` and `generator_sha256` (RECORDS_PIN).
  - Gates M0 and M1 pass.
- **Determinism.** Sorted keys, fixed seeds, no timestamps or absolute paths outside timing files.
- **Expected amendment** (append it to `spec/M2/amendments.jsonl` when you make it, and report it):
  - `spec/bindings/M2.json` changes the I6 tree hash of `spec/bindings`. Narrow `tests_m2/test_target_agnostic.py::TestByteIdentity.test_bindings_unchanged` and `tree_sha` to skip `spec/bindings/M2.json`, a new milestone's bindings, new by design. `BINDINGS_PIN` stays unchanged.
  - Any other change to a preregistered test is a Surprise.

## Coordination with I14 (built in parallel, merged by the lead)

- I15 creates `laws/M2/`; I14 never writes there.
- The registry gets `evidence_sha256` from `gen/M2/evidence.json`'s own `evidence_sha256` whenever that file exists. Re-run `holon derive` after the merge.
- Generated laws carry no `evidence` key, so I14's GEVID must read a missing key as the empty set.
- `spec/schemas/result_record_v2.schema.json` and `holon/gate.py` are edited by both iterations, additively: I15 adds `site` and `witnesses` and the M2 wiring; I14 adds its evidence fields and GEVID. Expect a hand merge.
- `holon/__main__.py`: I15 adds `derive` and `run --laws`.
- **Never commit I14's outcome paths.** `results/M0/` and `results/M1/` (their gate reports included) and `gen/M2/evidence.json` are I14's. Run `holon gate --milestone M0|M1` with `--report` to a scratch path, and commit no change under those paths; the lead regenerates the M0/M1 gate reports after the merge.
- I14's `anchors.sites` names a site law's actions from the frozen assignment's site occurrences, so do not re-render `gen/M2/sorts/assignment.json` (I15-R2); if you must (e.g. a sites change, F-M2-27/28), it is a Surprise and the lead regenerates `gen/M2/evidence.json` at the merge.

## Before committing

Run every suite: `tests`, `tests_m1` and `tests_m2`. Then run `holon gate` for M0, M1 and M2, `python tools/freeze.py check` and `python -m holon audit prereg --milestone M2`. In the report (`docs/iterations/I15.md`, with Done, Surprises, Questions for the human and Not done):
- the per-site outcome table;
- the witnesses and where each replayed;
- the obstructions;
- the MUT2 diff;
- the gate lines.
