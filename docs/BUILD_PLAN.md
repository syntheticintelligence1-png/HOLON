# HOLON v2: build plan from the whitepaper (revision 2)

**Basis:** `whitepaper.md`, the eight-area gap map (diagram-sorts, rules, theory, substrate, factory, algorithms, casestudy, eval-roadmap), spot checks of the tree, and the critique of revision 1. Every critique point was checked against the repo, the whitepaper, the Morph checkout at `3e44e79` and local Lean 4.34.0 probes before being accepted or rejected (§7).
**Repo:** HEAD `9ffdf77` on branch `claude/holon-v2-bend2-c6z3cd`, as of 2026-10-11.
**Scope:** M2 to M5, plus the M0/M1 debts that must be paid before anything is built on M0/M1.

**What changed from revision 1.**
- §1.1 now answers "no". Its debt list grows from five to nine.
- The meaning of every frozen statement is bound by hash before any generator is refactored (I2 before I6).
- Hashes and oracles become parameters before the first generated law (I12).
- ∃-laws are never REFUTED, and hypothesis splits are law pairs.
- Lean avoids `bv_decide`, which adds an axiom.
- Predictions are separated from regression expectations, and acceptance tests are committed with them.
- M3 facts come from extractors.
- The lossy fragment, every PAR sub-form, prover intake, early audits, the full §13 protocol and the missing case-study laws now have iterations.
- Iterations are renumbered; §3 maps old numbers to new ones.

---

## 0. How to use this plan

- **Iterations.** Each iteration (I1, I2, ...) is one focused session of 1 to 3 days of agent work, and depends only on earlier iterations and on the human answers listed in §0.3. Every iteration states:
  - its milestone and the exit criterion it moves;
  - its goal;
  - the whitepaper sections it realizes;
  - file-level deliverables, prereg commit first;
  - a preregistration, split into predictions and regression expectations;
  - a mechanical exit check;
  - risks, and the UNKNOWN fallback.

### 0.1 Preregistration protocol

1. **Write the key.** Each iteration writes a key `"I<n>"` into `spec/<M>/predictions.json`, validated by `spec/schemas/predictions.schema.json`. The key holds:
   - `predictions`: claims whose outcome is recorded nowhere in the repo when written. Only these count toward prediction accuracy (§13, L8).
   - `regressions`: outcomes expected to stay the same (statuses, hashes, counts or frontiers already in `results/`, `replay/` or `docs/`). They are checked but never counted as predictions.
   - `outcome_paths`: paths whose first change must come after the prereg commit. The default for milestone M is `results/<M>/`, `gen/<M>/`, `laws/<M>/`, `replay/<M>/`, `audit/rounds/<M>/`, `spec/<M>/disagreements.json`, `spec/<M>/equivalent_mutants.json` and every generated `docs/` file. Iterations that touch M0/M1 outputs add `results/M0|M1/` and `replay/M0|M1/`.
   - `tests`: the acceptance tests for the iteration. They are committed in the prereg commit, red.
   - `thresholds`, where the iteration has any.
2. **Prereg commit.** It contains only that key, the sidecar inputs the predictions depend on, the acceptance tests and `prompts/I<n>_<slug>.md`. Push it before implementation starts, so the remote timeline shows the order.
   - **Instruments are inputs.** A schema, oracle or other instrument that decides a prediction goes into the prereg commit as a sidecar input. Otherwise the claim is listed as a regression or a construction check, never as a prediction.
   - **Why this rule exists.** In I1, the v2 record schema and the IR 0.2 schema were written after the prereg. So I1-P5, and the schema halves of I1-P3 and I1-P4, are construction checks and do not count toward prediction accuracy.
3. **Check.** `python -m holon audit prereg --milestone <M>` (added in I1) checks, using read-only `git log` and `git show`:
   - the order of the prereg commit and the outcome-path commits;
   - per-key immutability: each key's value at HEAD equals its value in the commit that introduced it;
   - every acceptance-test function present at the prereg commit is unchanged at HEAD. New tests may be added. A test that must be fixed gets an entry in append-only `spec/<M>/amendments.jsonl` and is reported under Surprises.
4. **It is not a gate check.** The gate runs on `copy_repo` trees, which have no `.git` (`tests/_util.py`). `tests_m2/test_prereg_order.py` runs the tool on the real checkout and **fails, never skips**, when `.git` or the history is missing.
5. **Residual risk, stated plainly.**
   - Local runs made before the prereg commit cannot be detected.
   - The tool, the predictions file and the tests are agent-writable until the human freezes them (Q1), so the protocol is self-certified until then.
   - **What the tool enforces.** The prereg commit changes no outcome path, and every later outcome-path commit descends from it.
   - **What it misses: earlier commits.** Outcome-path commits that are ancestors of the prereg commit are not attributed to any iteration. An outcome committed before its prereg passes, just like an unrecorded local run.
   - **It trusts the local `.git`.** The authoritative audit is a run on a fresh clone of the pushed remote.
   - **Sidecar inputs can change.** They are not immutable after the prereg; changes are reported as notes.
   - **Amendments are broad.** An amendment licenses every later change to what it names.
   - **New code can interfere.** Newly added test modules or helpers can still monkeypatch the suite at import time.
6. **Predictions are never edited.** A miss is reported under Surprises.

### 0.2 Session protocol

1. The prompt `prompts/I<n>_<slug>.md` exists before the session starts. The human writes it, or the coordinator renders it from this plan (the coordinator is built in I45). Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, then that prompt, as AGENTS "Read first" item 3 requires.
2. Make the prereg commit (§0.1) and push it.
3. Implement.
4. Run every suite:
   - `python -m unittest discover -s tests -t . -v`
   - `python -m unittest discover -s tests_m1 -t . -v`
   - `python -m unittest discover -s tests_m2 -t . -v`, and from M3 on also `tests_m3`, and so on.
5. Run `python -m holon gate --milestone <M>` for every milestone that has a registry, then `python tools/freeze.py check` and `python -m holon audit prereg`.
6. Hygiene: no `bunfig.toml` or `.env` anywhere, vendored trees included. No `node_modules` or tool installs inside the repo; tools go under `~/.holon/tools`.
7. End the PR with Done / Surprises / Questions for the human / Not done.

### 0.3 Human answers that block iterations

| Question | Blocks | Default while unanswered |
|---|---|---|
| Q1 (freezing) | nothing | Every protection that rests on an agent-writable file is reported as self-certified |
| Q3 (signing key) | weakening entries only | The gate rejects every weakening; re-extraction and strengthening proceed |
| Q4 (schemas) | `intended_bounded` adoption in I33 | It exists only as a v2 `filter_bin` value; the frozen `triage` is untouched |
| Q5 (historical data) | M2 exit (a) | Recorded as UNKNOWN |
| Q6 (mutation threshold) | I22 | I22 waits. The agent never picks a threshold after results exist |
| Q7 (held-out target) | I49 | Results are labelled unsealed |
| Q9 (auditor family) | I5, I21, I45, I46 | Rounds are labelled same-family and do not count toward convergence |
| Q11 (L6/L9 definitions) | I54, then I56 and I57 | M5 metric work waits |
| Q14a (core catalog) | I8 | Core lemmas are emitted by per-class proof generators, never hand-proved |
| Q14b (meta-theorem proofs) | I42 | Basis sufficiency is labelled "paper proof only" |
| Q14c (agent proofs) | I41 | No intake is built |
| Q19 (M3 hand-written facts) | waivers in I28–I39 | No hand-written facts in M3; unreachable components become coverage debt |

---

### 0.4 Human answers received

The human answered §6 on 2026-10-12; `docs/HUMAN_ANSWERS.md` is the record:
- **Q5** is an unconditional, unbounded yes. On-chain historical replay is the make-or-break result, and data acquisition becomes the priority track `I23a` (prereg key `I59`), which waits only on the environment's network policy.
- **Q6:** 0.80.
- **Q7:** ScrollChain, sealed in `spec/heldout/target.json`.
- **Q9:** the default stands.
- **Q14b** and **Q14c:** yes.
- **Q16:** yes.
- **Q20:** N = 20.
- **Q1:** yes, to be done by the human, with the steps in the record.

## 1. Where we are

### 1.1 Are M0 and M1 done?

**No, not by the strict letter of §15.2, and not as the whitepaper intends.** The individual results hold up. The gaps are in what the exit criteria require, plus nine integrity debts. All of them must be closed before anything is built on top.

**M0 results**
- 8 laws: 5 PROVED (`L_par_hdr_v0`, `L_par_hdr_v1`, `L_rt_go_v0`..`v2`) and 3 REFUTED (`L_par_hdr_v2`, `L_par_hdr_ssvh`, `L_dom_hdr`). 8/8 predictions met.
- All 16 canaries were rejected. Every proof was re-checked by BendTT `--verdict`.

**M1 results**
- 16 laws: 8 PROVED, 8 REFUTED, all matching or explained.
- §11.8 has **10** M1 rows. `spec/M1/predictions.json` turns them into 14 entries; that expansion was the agent's choice (delay → nofree/pay/wait, stale → stale/stale_commit). It adds 2 entries labelled post hoc: `L_nat_eta2` and `L_disch_delay_prove`.
- Refinement corpus: 300 traces (2,432 steps), 0 disagreements. All 21 canaries were rejected.

**Letter check against §15.2**

| Exit criterion | Status | Why |
|---|---|---|
| M0: v0 and v1 PROVED | met | |
| M0: v2 and the domain law REFUTED with the predicted witnesses | met | The Go side is replayed. The Solidity side of the v2 witness is not (D-b). |
| M0: all canaries rejected | met | 16/16 |
| M0: one law dual-kernel | met only by substitution | Frozen `docs/M0_SPEC.md:205` substitutes BendTT `--verdict` ("No Lean export"). §8.8 and §15.1 day 2 step 3 mean a Lean re-proof through the IR. BendTT re-checks bend2's own elaboration, so the two share a failure mode (D-d). |
| M1: all M1 rows of §11.8 match or are explained | met | |
| M1: every REFUTED witness replays as a Foundry test | **in full for 5 of 8** | **Full:** `L_undo_BVH`, `L_undo_cancel`, `L_sort_remaining` and `L_sym_omega`, plus `L_nat_eta2` through emulated storage. **`L_tag_BVH`:** the trace runs, but `replay/M1/report.json` itself says the violation "is invisible on chain by design". `obstruction_reproduced: true` overstates this, and the downstream misread of b57 is not replayed. **`L_fact_Z`:** equal `committedBatches` for different sidecars is shown, but the consumer (derivation) divergence is not. **`L_own_txspayload`:** replays through `go test`, because the code is Go (Q2b). |

**The nine debts**

| # | Debt | Closed in |
|---|---|---|
| D-a | `laws/M1`, `REGISTRY.json`, `spec/M1/{predictions,mutations}.json` and `tests_m1` are not in `FROZEN.sha256`; `tools/freeze.py` `FROZEN_ROOTS` covers only `laws/M0`. History: `9a96037` added 15 M1 law files together with their `results/M1/*` and `spec/M1/facts`. `spec/M1/predictions.json` first appeared in `bfdb5f2`, after that. `L_own_txspayload`'s law, result and prediction entry were all added in `3e9cb2a`. Git therefore cannot single out the 2 post-hoc laws: all 16 statements were committed with or before their results. The `L_tag_BVH` row was broadened after the search ("either direction"). `whitepaper.md` itself was committed at `9ffdf77`, after M1. | I1 (prereg tool), I10 (A3); human: Q1, Q2, Q13 |
| D-b | The Solidity side of the M0 `L_par_hdr_v2` and `L_par_hdr_ssvh` witnesses was never replayed (`not_applicable` in `replay/M0/report.json`). | I4 |
| D-c | G11 checks law names, not premise inhabitants. Four premised PROVED M1 laws (`L_undo_CSR`, `L_undo_BD`, `L_disch_stale`, `L_disch_stale_commit`) and five premised PROVED M0 laws have no inhabitant. | I3 |
| D-d | The "second kernel" is BendTT re-checking bend2's elaboration. No Lean re-proof was done. | I9 |
| D-e | Premises and ledger are wrong. **(1)** A hard-coded `CF(keccak256, headers)` string is appended to every M1 record (`holon/mpipeline.py:233`), including the Go OWN law. **(2)** The zero-blob assumption (Z equals the KZG versioned hash of the zero blob; this is D2) is called "HypZ" in `docs/M1_REPORT.md:108`, which claims an oracle check "at Rollup.sol:24". The constant is at `:25`, no code performs the check, and §8.5 reserves the name HypZ for the compression hypothesis. **(3)** The M0 facts' own assumptions (A-width, A-version, A-cache, A-dirty, A-hash) and several M1 abstractions (the messenger oracle, the window/shadow index specialization, token values, the post-genesis initial state) appear in no record. | I1, I3 |
| D-f | `L_tag_BVH`'s obstruction is not observed on real code, and `L_fact_Z`'s consumer side is not replayed. | I4 |
| D-g | No audit round has ever run. `prompts/P6_audit.md` (output `audit/M0_round1.md`) was never executed, and there is no `audit/` directory. | I5 |
| D-h | Statement meaning depends on names that sit outside the statement hash. The 0.2 hash covers only `facts_sha256`. Generator-defined names (`perm`, `runs_ok`, `no_code`, `cost`, `elapsed`, `last_ok`, `is_<act>`, `view_intact`) and the builtins the observers call (`b_tags_exact`, `b_hdr_of`, `b_win_*`, `agg`) can change while G2 still passes. | I2 (before I6) |
| D-i | The M1 letter says "Foundry test". `L_own_txspayload` targets Go code, so `go test` is the only replay available. | Q2b |

### 1.2 Status by whitepaper section (§4 to §13)

| § | Item | Status | Evidence (brief) |
|---|---|---|---|
| 4 Def 4.3 | Unified diagram 𝔇 | missing | No `holon/diagram/`. Three fact documents in two DSLs: `facts/morph_header.json` (0.1) and `spec/M1/facts/*.json` (0.2). The M1 header is 7 Nat tokens (`b_hdr_of`) and does not use the M0 codec. |
| 4 Def 4.1 | Carriers, classes, σ, R, interfaces | partial | Bend types exist. No carrier class, sort or reachable set, and no interface marking. `L_dom_hdr` is the only R^ext law. |
| 4 Def 4.2 | Edge kinds and TRANS annotations | diverged | Kinds are encoder, predicate, decoder, projection, action, migration and consumer. No HASH, STORE, LOAD or SYM edges. Read sets are per field with no index. Principals are free text. Costs are per-action constants. |
| 4 Def 4.4 | Invertible vs lossy fragments | missing | Nothing classifies edges. keccak is replaced by an injective `agg` (Cantor pairing). |
| 4 Def 4.5 | Evidence E1–E6 | missing | Hand-typed metadata, unhashed (`ir.HASHED_KEYS`), read by no code. Triage comes from `config/triage.json`, keyed by law id. |
| 4 Def 4.7 | 𝔅, refinement records, certificate scope | partial | One Bend model per facts file. No `Reach`. Refinement is per-action agree counts. Certificates list no refinement records. |
| 5 (all) | Rules as obligation generators | missing | All 24 law IR files are hand-written: 8 by the human (frozen), 16 by the agent (not frozen). |
| 5.1 | PAR sub-forms | partial | Round trip, codec agreement and domain coherence exist, header only. Recompute, consumer, branch, cycle, init, totality and weak are missing. |
| 5.2 | UNDO | partial | Generic noninterference generator. Pairs and residues chosen by hand through shadow lists. |
| 5.3 | NAT | partial | Only η₂ native equivalence (post hoc), from a pseudo-migration. |
| 5.4 | SYM | partial | One hand-written ω reorder law. No τ, ι, π or μ, no splits, no promotion routes, no disabling-race class. |
| 5.5 | FACT | diverged | One law. CF is built into the abstraction, and the Z assumption is unstated. |
| 5.6 | SORT | diverged | `L_sort_remaining` checks reachability of reason code 16. `L_tag_BVH` (subform `ghost_tag`) checks the `tags_ok` observer, which calls the `b_tags_exact` builtin. The facts' `site` annotations are read by no code. |
| 5.7 | DISCH | partial | Blocking proved for one κ shape. Profile points are fixed traces from one hand-picked s* (`[sendMessage, commitBatch(n=1), wait 21]`) with no interleaving of other principals. `perm` is a string-prefix match (`holon/gen/machine.py:729`, `holon/gen/mproofs.py:374`). |
| 5.8 | OWN | partial | One alias instance. No lost-write, no volatile-view exception. |
| 5.9, 5.10 | Intent contracts, intent lane | missing | No contract format, no G10. The frozen schemas have no INTENT rule and no `intended_bounded`. |
| 6 | Core library | partial | 10 Nat/Bool lemmas held as a Python string (`mproofs.CORE`) and pasted into 2 of 16 proof files. |
| 6 | Thm 6.4, Cor 6.5, Lemma 6.2, Thm 6.3, Thm 6.6, Thm 6.7 | missing | No graph, holonomy, congruence, equivariance or pasting statements. |
| 6 | Prop 6.11, Lemma 6.12 (lossy fragment, injective pushing) | missing | No lossy-pair enumeration, frozen evidence set or pushing. |
| 6 | Thm 6.9 (i), (ii) | done | (i) `noninterference` proves `L_undo_CSR` and `L_undo_BD`, unbounded, on both kernels. (ii) Divergence BFS plus Foundry replay. |
| 6 | Thm 6.10 blocking | partial | One guard shape. Write*_X not computed. |
| 6 | Thm 6.15, Cor 6.16 | diverged | IR 0.2 has no function binder. Frozen probe `p12` shows Bend supports one; it is unused. |
| 6 | Thm 6.17 | partial | Counter-laws for ∧-laws are unsupported. Under AGENTS rule 6 an ∃-law can never be REFUTED, and the generated ∀¬ law that would show its failure does not exist. |
| 6 | Prop 6.19, Def 6.20, Prop 6.21, Def 6.13 | partial, missing, missing, missing | Ghost tag hand-written. No Pareto search. No measures. |
| 7.1–7.8 | Refined sorts | missing | All values are Nat, Bool or List. Only two code sites carry sign obligations, because a human wrote the requires: Rollup.sol:363, duplicated in the facts for three actions, and :636. The BVH union is handled by hand with `b_tags_exact` (`machine.py:529`). |
| 8.1 | One artifact, executable and provable | done | The same `.bend` is imported by LAWS and compiled to `.mjs`. |
| 8.2 | Parallel or GPU refutation | missing | Single-threaded node BFS. No GPU. clang 18 cannot build Bend `!` calls. |
| 8.3 | Compilation table | partial | Done: records, fuel loops. Missing: refined-sort types, length-indexed bytes, SYM generators, `Reach`, principal classes (caller type plus permission predicate). Diverged: hashes and oracles are concrete stand-ins; encoders use 0xDEAD instead of an option type. |
| 8.4 | Law schemas | mixed | PAR, PAR-domain, OWN done. UNDO, NAT partial. DISCH partial: no "∀ schedule ≤ H". SYM, FACT, SORT diverged. Non-vacuity diverged (name check only). |
| 8.5 | Hypothesis discipline | diverged | CF is a hard-coded string. The Z assumption is misnamed and unchecked. No hypothesis is a premise. |
| 8.6 | Result records | partial | Three statuses correct. Missing: model hash, independence class, refinement records of the edges used, coverage. `scope` derived from status, no horizon. Split: see §1.3 V24. |
| 8.7 | Native replay | diverged | `.mjs` model plus offline `go test` and `forge test`. No C library, no historical inputs, no disagreement classification. |
| 8.8 | Kernel trust | partial | Canaries exist. Version-string pin only. No quarantine, no upgrade procedure. The second kernel shares bend2's front end. |
| 8.9 | Law IR | partial | Quantifiers, premises, hashes done. Missing: types, references to model definitions by hash (D-h), a 0.2 schema, a Lean emitter. |
| 9.2 | Loops | mixed | Proof loop done. Refutation and refinement partial. Obligation loop diverged. Extraction, audit and performance loops missing. |
| 9.3 | Gate | partial | Runs GENV, G1, G2, G3, G4, G5, G7, G11. No G6, G8, G9, G10. G1 skips result records. No CI. |
| 9.4 | Statement freezing | partial | M0 frozen. M1 protected only by an agent-written registry. No STATEMENT_DIFF, no strengthening proofs, no stale tracking. "Provers have no write access to LAWS/" is not enforced. |
| 9.5 | Auditors A1–A4 | mixed | A1 diverged (edits facts, not code). A2 partial. A3 missing. A4 partial. No round ever run. |
| 9.6, 9.7 | Finding filter, TCB | partial | Triage defaults to "finding" whatever the replay. `HOLON_BEND_CMD` and `BENDTT` overrides accepted unchecked. |
| 10.1 | Extraction | missing | All facts hand-written. Nothing extracts deployment history, Go slice headers, Go pipelines or loop bounds. |
| 10.2 | Layout algebra | done (core) | Missing: `calldatacopy`, getter recovery (E1), solver emission. |
| 10.3 | Basis reduction | missing | No spanning tree, cycles, generators, entry points or lossy enumeration. |
| 10.4 | Proof engines | partial | Layout and UNDO done. DISCH narrow. No SYM or NAT engine. No intake for agent proofs. |
| 10.5 | Refutation engines | partial | Enumeration over a hand-written policy. No SMT, fuzzing or GPU. Counter-law discipline done. |
| 10.6–10.11 | Deadness, profiles, splits, concretization, ranking, complexity | missing or partial | See I27, I31, I32, I34, I40, I44, I47. |
| 11 | Case study | partial | Computed since I4 (`tools/casestudy.py`, `docs/CASESTUDY.md`), replacing the earlier hand count. Obstructions: 9 full, 4 partial, 24 none; 6 of the full ones have a law in the provisional `finding` bin (O2, O11, O12, O19, O26, O27). Discharged: 2 full (D2, D5), 1 partial (D1: `L_par_hdr_ssvh` shows it needs ssvh = 0). Appendix A: 1 full (F6), 6 partial. DISCH rows can be at most partial under the rule, which needs a replayed refutation. |
| 12 | Remedies for L3, L7, L15, L21, L22 | missing | No evidenced-pair coverage, no rule admission, no UNKNOWN calibration, non-vacuity by name only, no drift trigger. |
| 12, 13 | Metrics, evaluation protocol | missing | Only canary acceptance (0/37) is computed. No corpus, baselines, controls or ablations. |

### 1.3 Every place M0/M1 diverged from the whitepaper

| # | The whitepaper says | M0/M1 built | Fixed in |
|---|---|---|---|
| V1 | Second kernel: a Lean 4 re-proof from the law IR (§8.8, §8.9, §15.1) | BendTT `--verdict`, which shares bend2's elaboration | I9, then I43 |
| V2 | Obligations generated by rules over 𝔇, then frozen (§5, §9.4, App. E) | 24 hand-written IR files; the 16 M1 files agent-authored and unfrozen | I10 (process), I15 (first generated laws), I24–I35 |
| V3 | Sorts compiled to nominal Bend types with coercions (§7.8, Thm 6.18) | Reason-code reachability laws; a hand-written ghost tag; a Morph builtin for exactness | I13, I15, I30 |
| V4 | Hashes as opaque `h` with `CF(h,S)` premises (§8.5, Cor 6.16) | A concrete `agg` and a pasted CF string | I1 (honest ledger), I12 |
| V5 | Oracles as parameters plus hypothesis predicates (§8.5) | Concrete stand-ins | I12 |
| V6 | One diagram linking all components (§4) | Disjoint fact documents | I11, I19 |
| V7 | Evidence computed from 𝔇 and gating defects (Def 4.5) | Decorative tags | I14 |
| V8 | G11: a checked inhabitant for every premise (§12.3) | A name check | I3, extended in I7, I8, I12, I28 |
| V9 | Native C model, cgo and EVM replay, historical inputs (§8.7) | `.mjs` plus offline tests | I16, I23 |
| V10 | Facts by deterministic extraction (§10.1); hand-written only until M2 (App. H, §15.3) | Hand-transcribed facts | I17–I20 (M2), then I28 and I35–I39 extend the extractors |
| V11 | `Reach` as an inductive predicate (§8.3) | Laws over all states, or over traces from s0 | I8 |
| V12 | Versioned machines with MIG edges (Def 4.3) | One machine plus a `legacy` pseudo-migration | I28 |
| V13 | DISCH: computed Write*_X and a Pareto profile (§5.7, Prop 6.21) | Syntactic `perm` and fixed traces from one s* | I31, I32 |
| V14 | A1 mutates the real code, then re-extracts (§9.5) | Four JSON edits to the facts | I22 |
| V15 | Records with orthogonal fields (§8.6) | `scope` derived from status; one kernel | I1, I7 |
| V16 | Generators that work for any target (App. H) | Morph names in `machine.py`, `mcanary.LIVE_FIELDS`, `policy_lib.mjs`, `mreplay.OPS`, `deadline` | I6 |
| V17 | Length-indexed bytes; partial edges return an option (§8.3) | U32 cells plus 0xDEAD | I17 (facts 0.3) |
| V18 | Predictions frozen before mechanization (§11.8) | M1 predictions committed after the results | I1 (prereg tool), Q1 |
| V19 | Appendix H repository layout | Top-level `facts/`, `laws/`, `gen/`, `results/`, `spec/` | Keep the frozen paths; add the missing components under their Appendix H names; move nothing |
| V20 | HypZ is the compression hypothesis (§8.5, App. D) | The name is used for the D2 zero-blob check, which is itself unimplemented | I1 (rename to `Hyp-Z0-kzg`), I3 (D2 check), I38 (real HypZ) |
| V21 | The IR references model definitions by hash (§8.9) | The 0.2 hash covers `facts_sha256` only | I2 (bindings for 0.1/0.2), I7 (refs in 0.3) |
| V22 | Principal class: caller type plus a permission predicate (§8.3) | Free text and a prefix match | I11, I19, I31 |
| V23 | DISCH profile point: ∃σ. ∀ schedule ≤ H. holds(σ) (§8.4) | Fixed traces from one s* | I32 |
| V24 | Status includes "split" (§8.6) | n/a. AGENTS rule 6 allows only three statuses, and the frozen schema enum has no SPLIT. | Splits become law pairs (I7, I12); Q13 |
| V25 | Certificates list the refinement records of the edges used, and coverage (Def 4.7, §8.6) | Not recorded | I1 (fields), I16, I19 |
| V26 | `bv_decide` suggested for Lean (§8.8) | n/a. It adds an axiom, which conflicts with §8.5's "no axioms". | I9 uses `rfl`, `simp` and per-cell lemmas; Q13 |

### 1.4 Environment realities

| Resource | Status here | Consequence for the plan |
|---|---|---|
| Bend 2.0.36 | `/usr/local/bin/bend`, a bun wrapper over `~/.holon/bend` at `2343aec`. BendTT `--verdict` works. | Primary kernel. I3 adds a checkout fingerprint and `BEND_NO_TELEMETRY=1`. |
| Lean 4.34.0 | `~/.elan/bin` (not on PATH), with `Std.Tactic.BVDecide` and cadical. **Probed locally:** `bv_decide` adds an axiom (`#print axioms` lists `t1._native.bv_decide.ax_1_5`). `rfl` on a 257-element list fails at the default `maxRecDepth` and passes at 20000 with no axioms. `simp` on symbolic byte lists uses only `propext`. `decide +revert` over two free bytes exceeds the default heartbeat budget. | Real second kernel (I9) built on `rfl`, `simp` and per-cell lemmas. `holon/lean.py` prepends PATH. |
| forge 1.5.1, solc 0.8.24, morph at `3e44e79` | At `/root/work/{foundry/forge, solc-0.8.24, morph}`, not on PATH. Solidity deps in `/root/work/holon-replay-m1/solidity/node_modules`, outside the repo. The morph checkout is non-shallow (763 commits, tags `v0.4.6`..`v0.6.3`). `Rollup.sol` has reinitializers 2–4 (:188, :199, :209) and `importGenesisBatch` (:226). | Replay and extraction are feasible. Deployment history can be derived from code (I28). The on-chain upgrade timeline cannot (Q18). |
| Go 1.24.7, node 22, bun, gcc, clang 18, cargo | Present. proxy.golang.org reachable. | go/ssa extraction (I18). Bend emits C (I16). |
| GPU / CUDA | Absent. clang 18 cannot build Bend `!` calls. | Sharded worker_threads and native C on 4 cores. No GPU claims. |
| z3, cvc5, slither, hevm, echidna, halmos | Absent. PyPI and GitHub releases reachable. | Pinned installs to `~/.holon/tools` (never in the repo) via `tools/setup_env.sh` (Q16). |
| Python 3.13, jsonschema 4.26 | Present; networkx absent. | jsonschema for new schemas; union-find by hand. |
| Ethereum RPC, beacon, blob archives, explorers | 403 policy denial. BigQuery reachable, but no credentials. | Historical replay is infeasible in-container (I23, Q5). |
| GitHub clone | Reachable; api.github.com session-restricted. | Corpus and held-out target via `git clone`. |
| gpg | Present; ssh-keygen absent. | STATEMENT_DIFF weakening signatures need a human key (Q3). |
| Frozen test harness | `copy_repo` drops `.git`, `node_modules` and `tmp`, but copies `build/` and other git-ignored directories. `run_holon` times out at 1800 s. | No gate check may read git. G1, G5 and G7 build into temp dirs. The M0 gate must stay under 900 s. |
| Hardware | 4 cores, 15 GB RAM, about 26 GB free. BendTT cost grows superlinearly above about 1000 terms per law. | Instantiate core theorems by application (I42). Measure term size before nominal sorts (I30). |

---

## 2. Invariants every iteration obeys

1. **Frozen means frozen.** Never edit, or add files under, `facts/`, `laws/M0/`, `predictions/`, `schemas/`, `tests/`, `bend/probes/`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md`, `AGENTS.md` or `tools/freeze.py`. Never run `tools/freeze.py write`. New things go in:
   - per milestone: `spec/M<k>/`, `laws/M<k>/`, `gen/M<k>/`, `results/M<k>/`, `tests_m<k>/`;
   - schemas: `spec/schemas/`;
   - probes: `bend/notes/`;
   - sidecars that do not change any facts hash: `spec/ledger/`, `spec/lib/`, `spec/M<k>/lib/`.
2. **Never edit `spec/M1/facts/*.json`.** Its hash is in every M1 statement.
3. **Generate, don't hand-write.**
   - Law IR for M2 and later comes only from `holon/rules/` or `holon/sorts/`, with provenance in `laws/<M>/DERIVATION.json`. `python -m holon derive` reproduces `laws/<M>/` byte for byte.
   - Law ids are a deterministic function of (rule, subform, basis element).
   - Facts for M3 and later are extractor outputs reproduced by G1. A hand-written fact needs a human waiver (Q19), is flagged `hand_written` in coverage, and counts against coverage.
4. **Witnesses come from the compiled model.** Solvers, fuzzers and hints only propose candidates. REFUTED needs a Bend-accepted counter-law. `tests/reference/` is never imported from `holon/`.
5. **No escape hatches.** No holes, `@unsafe`, `def f?`, foreign imports or laws without proofs. In Lean, `sorry`, `axiom`, `native_decide`, `bv_decide`, `ofReduceBool`, `implemented_by` and `@[extern]` are forbidden, and `#print axioms` may list only `propext`, `Quot.sound` and `Classical.choice`.
6. **Determinism.** Sorted iteration, fixed seeds, no timestamps. Timings go only to files G1 excludes (`results/<M>/gate_timing.json`, `results/<M>/metrics_timing.json`).
7. **Never weaken.** A failed prediction is a Surprise. Thresholds, laws and premises never move after results are seen. A re-derived analogue of an earlier law under a new id needs a checked S_new ⇒ S_old, or a signed weakening entry (I10).
8. **Hygiene.** No `bunfig.toml` or `.env` anywhere, vendored trees included. No in-repo `node_modules` or tool installs. Run the checker before every commit.
9. **Backwards compatibility.** IR 0.1 and 0.2 statement hashes stay fixed. New record fields are additive. Never rewrite assertions in `tests_m1`; add checks in `tests_m2` and later.
10. **Frozen-test compatibility.**
    - The v1 `triage` of every M0/M1 record stays equal to its prediction (frozen `tests/test_30_m0_results.py`, `tests_m1/test_m1_results.py`). Evidence-derived or contract-derived values go into v2 fields.
    - Every check reported for M0 must pass on a copy without `.git`, within the 1800 s timeout.
    - A check that has no meaning for a milestone is listed under a top-level `not_applicable` key, with a reason. It never appears as a vacuous pass inside `checks`.
11. **Self-certification is stated.** Any protection that rests on an agent-writable file is described as self-certified until the human freezes it (Q1). This covers registries, `BINDINGS.json`, quarantine, `statement_diff.py`, the prereg tool and `tests_m*`.
12. **Outcome vocabulary.** Exactly PROVED, REFUTED or UNKNOWN.
    - ∃-laws are never REFUTED. Their failure is shown by a separately generated ∀¬ law.
    - A hypothesis split is a pair of laws.
    - A bounded negative search is UNKNOWN, with its bound.

---

## 3. Iteration map

| It. | Rev. 1 | Title | Milestone | Depends on | Blocked by | Moves |
|---|---|---|---|---|---|---|
| I1 | I1 | Prereg tool, honest ledger, v2 records, G1 over records, G6/G9 | M2 entry | — | — | D-a (tool), D-e |
| I2 | (I8 part) | Semantic bindings and dependency index | M2 entry | I1 | — | D-h |
| I3 | I2 | Non-vacuity, D2 zero-blob check, checker pin and upgrade procedure | M2 entry | I1 | — | D-c, D-e(2) |
| I4 | I3 | Replay completion, provisional filter, case-study coverage | M2 entry | I1 | — | D-b, D-f |
| I5 | new | First audit round on M0/M1 | M2 entry | I1–I4 | Q9 (label) | D-g |
| I6 | I4 | Target-agnostic generators, byte-identical | M2 | I2, I5 | — | V16 |
| I7 | I5 | IR 0.3: types, refs by hash, cf/hyp, scope, ∧ counter-laws, ∃ negation, law pairs | M2 | I6 | — | prerequisite for M2/M3 |
| I8 | I6 | Core library and `Reach` | M2 | I7 | Q14a (default) | V11 |
| I9 | I7 | Lean second kernel for M0 | M2 | I7, I3 | — | D-d |
| I10 | I8 | Statement lifecycle, A3, prover separation | M2 | I7, I2 | Q3 (weakening only) | V2 process |
| I11 | I9 | Diagram 𝔇 and principal classes | M2 | I6 | — | V6, V22 |
| I12 | (I21 model half) | Hashes and oracles as parameters | M2 | I7, I11 | — | V4, V5 |
| I13 | I11 | Sorts I | M2 | I11, I7 | — | — |
| I14 | I10 | Evidence calculus (E1–E6) and frozen evidence set | M2 | I13 | — | V7 |
| I15 | I12 | Sorts II: per-site SORT laws, rules registry (first generated laws) | M2 | I13, I10, I12 | — | V3 |
| I16 | I13 | Native C model, refinement records, metrics | M2 | I11 | — | M2 exit (a), corpus part |
| I17 | I14 | Solidity frontend I: layouts | M2 | I16 | — | M2 scope |
| I18 | I15 | Go frontend: codecs, partiality, slice headers, pipelines, loop bounds | M2 | I17 | — | M2 scope |
| I19 | I16 | Solidity frontend II: storage, transitions, cost terms, principals, linking, G8 | M2 | I17, I11 | — | M2 scope |
| I20 | I17 | Extracted rollup model: refinement, width, optional hevm | M2 | I19, I18, I16, I15 | — | M2 exit (a), corpus part |
| I21 | new | A2/A4 audit round on extraction | M2 | I20 | Q9 (label) | — |
| I22 | I18 | A1 mutation adequacy on real code | M2 | I20, I18, I21 | **Q6** | **M2 exit (b)** |
| I23 | I19 | Historical inputs and M2 exit evaluation | M2 | I20 | Q5 | **M2 exit (a)** |
| I24 | I20 | Rules engine and PAR, all sub-forms | M3 | I14, I15, I10 | — | M3 "eight rules" |
| I25 | new | PAR-lossy and injective pushing | M3 | I24, I14, I8 | — | L3 |
| I26 | (I21 rule half) | FACT rule, attribution (O25), F(m,c) | M3 | I24, I12 | — | M3 |
| I27 | I22 | UNDO rule and static deadness | M3 | I24 | — | M3 |
| I28 | I23 | Deployment-history extraction (its history half is I63), versioned machines, PAR-init | M3 | I27, I8, I19, I63 | Q18 | V12 |
| I29 | I24 | NAT rule | M3 | I28 | — | M3 |
| I30 | I25 | Sorts III: nominal types, hole-free coercions, generated ghost tags | M3 | I15, I8, I13 | — | V3 |
| I31 | I26 | DISCH I: closure, blocking, external dependence | M3 | I24, I11 | — | V13 |
| I32 | I27 | DISCH II: ∀-schedule profiles and classification | M3 | I31 | — | V13, V23 |
| I33 | I34 | Intent contracts and G10 (the machinery half is I64; the O12 contract on M2's window view is I65): the O12 contract on M3 | M3 | I27, I64, I65, I26 | Q4 (adoption) | G10 |
| I34 | I28 | SYM rule: families, splits, both promotion routes, races, sentinels | M3 | I30, I28, I33 | — | M3 |
| I35 | I29 | OWN rule from extracted backing identities | M3 | I24, I18, I33 | — | M3 |
| I36 | I30 | Bundle I (extracted): messenger, queue, Merkle, accounting, cutover | M3 | I28, I26, I25, I19, I69 (= I36a: extraction and the linked machine); the Q21 fix key (I68) for the ∀ laws | Q12 | M3 "full bundle" |
| I37 | I31 | Bundle II (extracted): router, public input, HypC, calibrated cost | M3 | I36, I32 | — | M3 |
| I38 | I32 | Go codecs at loop granularity, compression oracle (HypZ) | M3 | I18, I26 | — | M3 |
| I39 | I33 | Go derivation and product machine | M3 | I38, I37 | — | M3 |
| I40 | I35 | Refutation engines, App. D encodings, BMC, filter recomputation | M3 | I12, I20 | — | §9.6, §10.5 |
| I41 | new | Untrusted prover intake | M3 | I10 | **Q14c** | §9.1, §10.4 |
| I42 | I36 | Theory core I | M3 | I8, I24 | **Q14b** | basis sufficiency |
| I43 | I37 | Theory core II; Lean for the promoted set | M3 | I42, I9 | Q8 | V1 |
| I44 | I38 | Measures (all of Def 6.13), ranking | M3 | I32, I36, I37 | — | M3 |
| I45 | I39 | Audit loop, coordinator, rule gaps, rule admission, SYM route (ii) | M3 | I24–I44 | Q9 | M3 "audit loop" |
| I46 | I40 | Blind rerun from code, and generated comparison | M3 | all M3 | Q9 | **M3 exit** |
| I47 | I41 | Target-agnostic factory, parallel checking, performance loop, drift trigger | M4 | I46 | — | L20, L22 |
| I48 | I42 | Evaluation corpus and unsolved controls | M4 | I47 | Q20 | §13 |
| I49 | I44a | Held-out target: extraction | M4 | I47 | Q7 | §13 |
| I50 | I44b | Held-out target: rules, run, replay | M4 | I49 | — | §13 |
| I51 | new | HOLON on corpus pre-fix commits | M4 | I48, I47 | — | recall, precision |
| I52 | I43 | Baselines on Morph, corpus and held-out target | M4 | I48, I50 | Q16 | §13 |
| I53 | I45 | Ablations, UNKNOWN calibration, §13 metrics | M4 | I51, I52 | — | **M4 exit** |
| I54 | (I49 part) | L6/L9/L10 definitions, preregistered | M5 | — | **Q11** | M5 |
| I55 | I46 | Intent lane | M5 | I33, I54 | — | L10 |
| I56 | I47 | Bounded games | M5 | I32, I37, I54 | — | L6 |
| I57 | I48 | Environment modules | M5 | I12, I54 | — | L9 |
| I58 | (I49 part) | M5 report | M5 | I55–I57 | — | **M5 exit** |
| I59 | (I23 part) | **= I23a: on-chain history fetch and first replay on real inputs.** Pulled forward by human answer Q5 and run in the background after I18; numbered I59 only because prereg keys must be plain numbers | M2 | I16, I17 | — | M2 exit (a), data half |
| I60 | I22 replacement | **A1 mutation adequacy, replacement catalog.** I22's catalog was rejected before any run by the delegated independent sign-off (docs/iterations/I22.md): scope tied to the outcome, K2 not localized, the error clause too broad. Preregistered under a new key, as the plan's I22 rule requires | M2 | I20, I18, I21 | — | **M2 exit (b)** |
| I61 | I60 replacement | **A1 mutation adequacy, second replacement catalog.** I60's catalog was not signed off (docs/iterations/I60.md): its enc_sol replay harness does not overlap the refuter's candidates. Preregistered under a new key, as I60's contract requires | M2 | I20, I18, I21 | — | **M2 exit (b)** |
| I62 | I61 rerun | **A1 mutation adequacy, I61's catalog rerun with I61's defects fixed.** I61's run showed five pipeline defects and one gate rule to fix (docs/iterations/I61.md); its gate allows no second attempt after a pass, so the rerun is a new key, as the human chose (docs/HUMAN_ANSWERS.md Q41) | M2 | I61 | — | **M2 exit (b)** |
| I63 | (I28 part) | **= I28a: deployment history from the code, cross-checked on chain.** I28's history half (versions, reinitializers, storage-layout diffs and MIG edges over every tag, the on-chain upgrade timeline: Q18), pulled forward because it needs no rule catalog while I26 holds the next one (the roadmap split of 2026-10-21); numbered I63 only because prereg keys must be plain numbers. I28 keeps its number for the laws half (versioned machines, PAR-init, O9, D4, F12.5, G11V in-flight sets), after I26, reading I63's outputs | M3 | I19, I23, I59 | Q18 | V12 (data half) |
| I64 | (I33 part) | **= I33a: intent-contract machinery and G10, on a toy milestone.** I33's machinery half (contract files and their registry, derivation of L_weak as a law, the run's `intended_bounded` marking, G10, the v2 record field, the volatile-view contract type OWN needs, the Q4 adoption package), exercised on the test milestone T64. Pulled forward because the O12 contract itself needs three things that do not exist yet: a ghost counter in the M3 model, a proof class for linear bounds over Reach, and an UNDO analogue of L_undo_cancel (I27 gap G5). Numbered I64 only because prereg keys must be plain numbers. I33 keeps its number for the O12 contract | M3 | I27 | Q4 (adoption) | G10 (machinery) |
| I65 | (I33 part) | **= I33b: the O12 intent contract on M2's window view.** A ghost counter (an IR 0.3 history term: the sum of an expression over a trace's successful steps of one action), the proof class `trace_bound` for linear bounds over traces, and the first real contract, `C_o12`, whose derived law and mark are integrated into M2 (registry, bindings, every M2 gate check) and into its view records (`results/M2/extracted_m1`, where `L_undo_cancel` is REFUTED and I40 concretized it on the real Rollup). Pulled forward because M3's O12 contract also needs word-level lemmas over the extracted model and the UNDO analogue of `L_undo_cancel`, a catalog change after I26, while M2's Nat view of the same Rollup needs neither; the human chose it (2026-10-22). Numbered I65 only because prereg keys must be plain numbers. I33 keeps its number for the O12 contract on M3 | M2 | I64, I20 | — | G10 on a real milestone |
| I66 | (Q62) | **= the Q62 key: M2's evidence set models window views.** holon.differential's window view of the extracted Rollup (`gen/M2/extracted/m1_view.json`) gets an I11 diagram (its libraries anchored to the abstraction's: the library half of I65's anchor, I65's code) and one model in `gen/M2/evidence.json`, `m1_view`, with I14's atoms; only a target milestone's build from its committed diagrams models a view, so test-milestone and in-memory evidence sets do not change. GEVID then covers a law over the view, I65's derived law first, and no existing law's evidence moves. I65's prereg named the route (GEVID enforces on the derived law with no exemption, so I65's build merges after this key). The M1 and M2 records are re-made for the new generator closures; the M3 records trail them until the next M3 re-make. Numbered I66 only because prereg keys must be plain numbers; filed in spec/M3 beside I65, an M3 key with M2 outcomes | M2 | I65 (prereg), I14, I20 | — | GEVID on window views |
| I67 | (I38 part) | **= I38a: Go codecs at loop granularity, and O4 at the real blob size.** I38's loop half. The Go frontend's opt-in config `holon-go-frontend/0.2` adds a `loop_bodies` section: one iteration of each counted loop as loop-free paths over its symbolic induction variable, the open bound sites included; a 0.1 config extracts byte for byte what it does now. `spec/M3/facts/morph_blob.go.extracted.json` extracts `common/batch` and `common/blob` together (the frontend's `<stem>.go.extracted.json` naming; I38's deliverable list calls it `morph_blob_go.extracted.json`). A Go-op component per interface carrier that the sidecar `spec/M3/lib/go_ops.json` names (every function of the document whose one parameter is that carrier, R^ext in the sense of A2) gives rule PAR's existing producers a diagram (P4 weak, P5 domain coherence, P6 totality, P8 cycles), so the rule catalog does not change. Its laws are decided on a structural Bend model of the loop: the sequence of cells the body reads, consumed one node per iteration, the index a `Nat` and an open bound site a `Nat` threshold, which both kernels check at the real 4096-element size (I38's risk). REFUTED witnesses are replayed on the real Go code. Pulled forward because it needs neither the human's HypZ answers nor I28's catalog. I38 keeps its number for the compression half (HypZ, HypZ_len) and for O5, O6, O28 and D3, which this key does not predict. Numbered I67 only because prereg keys must be plain numbers | M3 | I18, I24, I26 | — | M3 (O4; §5.1 PAR-totality; A2) |
| I72 | (I33 part) | **= I33's evidence key: E2 over the adopted holon-facts/0.3 transitions documents.** I20 covered each transitions document a milestone adopts with a model of anchors only (E1-E6 are defined over facts 0.1 and 0.2 diagrams), so a law over the adopted Rollup document that names an edge has no computed evidence, and I33's M3 contract, which claims E2, would fail GEVID. I72 computes E2 (written via p, read via q) over such a document from its own write records and storage terms: map and member paths, literal and symbolic keys, loop-carried and post-state terms read as threading, not as reads; in gen/M2/evidence.json and gen/M3/evidence.json, for a target milestone's build from the committed diagrams only, so test-milestone and in-memory sets do not change. The walker is a module of its own (holon/diagram/transitions.py), and the evidence schema's atom model and id patterns admit the adopted model's dotted key. No other level, anchor, law or model changes, and no committed law's evidence moves (none over the document names an edge). The M1, M2 and T32 records are re-made for the closures; the M3 records trail them until the next M3 re-make. Numbered I72 because I68-I71 are taken (I68 the Q21 fix, I69/I70 brave-wright's, I71 the UNDO `cancel` catalog key) | M3 | I14, I20, I66 | — | GEVID on the I33 contract law |
| I80 | (I37 part) | **= I37a: Bundle II's extraction and acquisition, no laws.** The verifier router (MultipleVersionRollupVerifier) extracted at the pinned head by I19's frontend and modelled (model3's untyped machine with an additive storage-dynamic-array extension that lives outside every generator closure), linked with the adopted Rollup into one evaluator-level machine in which the Rollup's proof checks run the router and the router's finalization check reads the Rollup, and refined against a forge harness that deploys the real Rollup and router (I20's deployment and corpus, planted router traces, random traces); the zkEVM verifier (ZkEvmVerifierV1 with its SP1 and Plonk bases) extracted only, its debt named: it is the circuit oracle, which I37 states as HypC; the public-input view and the cost sites read from the documents (the inputs of I37's PI = K(...) and of tools/calibrate_gas.py); acquisition notes from committed records and git objects (the router named by the Rollup's initialization receipt in I63's snapshot, the members' blobs at every pinned tag, the head builds under I63's configurations), with no network read. Split from I37 because I37's laws (O3, O23, the calibrated cost, O35) depend on I36 (Bundle I) and I32, while extracting Bundle II's contracts does not; it mirrors I69 (= I36a). No generator closure moves, so no record is re-made. Numbered I80 only because prereg keys must be plain numbers (I80-I89 are this lane's sub-keys). I37 keeps its number, its plan text and its predictions | M3 | I19, I20, I63 | — | M3 (Bundle II extraction half) |
| I81 | (I44 part) | **= I44a: Def 6.13's measures and §10.10's ranking, over the M3 laws that exist today.** I44's computable half. One interface over the five measures (`holon/measures.py`): PAR's holonomy defect size (the witness's differing positions against the layouts' bound), NAT's naturality defect mass, FACT's F(m, c) (I26's `holon/measures_fact.py`, reused), UNDO's residue liveness distance (the first divergent step of the model's observations), DISCH's discharge profile (I32's classes); each law gets a value, a certified bound, "not applicable" (a rule Def 6.13 gives no measure) or "pending <key>" where the rule or its input does not exist yet. §10.10's ranking (`holon/rank.py`): lexicographic by sink class (from the channel on which the witness's two sides diverge), persistence (I32's DISCH classes; a pure-function defect persists until the code changes), reach class (the principal classes the witness schedule needs) and adversary cost (its calls; gas waits on I37's calibrated cost); `results/M3/ranking.json`, regenerated byte for byte by `holon rank`, and `spec/schemas/ranking.schema.json`. Computed sink classes are compared with §11.3's Impact column, and each difference is explained, not fixed. Numbered I81 only because prereg keys must be plain numbers. I44 keeps its number for the measures that wait on later keys: NAT's naturality defect mass (I29), F(PI, parent lbn) (I37) and F(Z, derivation) (I39) | M3 | I26, I27, I28, I32 | — | M3 (Def 6.13, §10.10, §11.3 Impact) |
| I82 | (I46 part) | **= I46a: the blind pack, the comparison generator and the agreement metric; I46 keeps its number for the blind rerun and the M3 exit.** I46's tooling half, built so that its blind rerun and generated comparison can run the moment the last M3 iteration lands: `tools/blind_pack.py` (I46's sealed bundle as a byte-identical tarball for a given commit, with a manifest, sha256s and a computed leak list, never filtered), `holon/report.py` writing `docs/M3_COMPARISON.md` from the records (covered by G1: each §11.8 row, a cell for every F-id F1-F14, "not mechanized" allowed, and Appendix A's items mapped to law ids), the map `spec/M3/appendixA_map.json` (generated from the `maps_to` of the laws and records, the back-test tables and §11.8's law names, plus a sidecar fixed at the prereg, before any blind outcome exists), and the `blind_agreement` metric (`holon compare --blind <dir>`: the statuses of α-equivalent statements, with the matched-statement fraction), dry-run on the lead's own regenerated records and on synthetic perturbations. No law, record or generator closure moves. Numbered I82 only because prereg keys must be plain numbers (I80-I89 are this lane's sub-keys) | M3 | I24, I26, I27, I28, I30, I31, I32 | Q9 | M3 exit (tooling half) |
| I69 | (I36 part) | **= I36a: Bundle I's extraction and acquisition, no laws.** The message queue, the messenger, the whitelist and the Submitter extracted at the pinned head (overloaded actions named by selector, dynamic storage arrays, `abi.encodeWithSignature` and `abi.encodeCall`, packed hashing over loop-carried values, added to the frontend, the evaluator and model3 without moving any earlier output), each member's model refined on the real code; one linked machine in which a call between members runs the callee's extracted transitions instead of a free answer, refined against a forge harness that deploys the real bundle; and Q12's acquisition: the legacy registry L1Staking extracted at v0.6.1 (the last tag that holds it), its proxy found from I63's cutover receipt and its on-chain implementation matched by metadata-stripped bytecode, with the live queue, messenger, Submitter and whitelist matched to their head builds. Split from I36 because I36's eight predictions span five rules, four of which need a new or extended producer, behind two independent blockers (I28's versioned machine for the cutover, Q21's storage keys for the ∀ laws), while extraction and linking need neither (the split of 2026-10-23). Numbered I69 only because prereg keys must be plain numbers. I36 keeps its number for the laws over the current deployment (I36b: O29, O30, O34, D7, D8, D9, Q28's BMC rerun); I70 (= I36c) takes O13 and O20's economic half after I28's build and I29; I68 is the Q21 fix | M3 | I19, I20, I63, I66 (its prereg, merged at a0bfc521: I32-R2 re-scoped to I32's own commits) (I28's tag-tree mechanism shared, either order) | Q12 | M3 "full bundle" (extraction half) |
| I85 | (I39 part) | **= I39a: the Go derivation extracted (ParseBatch as an extracted consumer) and the product machine joining the Solidity commit with Go derivation, refined against a Go replay; no laws.** The derivation document `spec/M3/facts/morph_derivation.extracted.json` is I18's skeleton document of `node/derivation` (I18's frontend and its config, unchanged) plus a consumer section: the SSA of `BatchInfo.ParseBatch` and of every function it reaches by static calls inside the extracted packages, with each callee outside them named as environment (Go standard library semantics, or an answer of the real library: the zstd decompressor and the transaction-stream decoder, the compression hypothesis I38 states and the transaction codec). The consumer is evaluated by an interpreter of that SSA under `holon/derivation/`, outside every generator closure. The product machine is evaluator-level: a commit step runs the adopted Rollup document's `commitBatch` (holon.extracted_eval) and, when it succeeds, the derivation of the same batch, joined field by field as the derivation's own calldata decoder maps the commit's input; the next commit's parent header is the header the Solidity model committed (the cycle of §5.1). The consumer half is refined against a Go replay that runs the real `BatchInfo.ParseBatch` on every corpus batch (product batches, planted batches for each return of ParseBatch, random batches), in a scratch copy of the pinned checkout with the `node/` dependencies from the module cache. Split from I39 because I39's laws need the extracted consumer and the product, while extracting and refining them needs no law; it mirrors I69 (= I36a) and I80 (= I37a). No generator closure moves, so no record is re-made. Numbered I85 only because prereg keys must be plain numbers (I80-I89 are this lane's sub-keys). I39 keeps its number for the laws (O7, the O8 law pair under HypC, O24, the F11 L1-count law) | M3 | I18, I20, I67, I80 | — | M3 (§5.1 consumer and cycle, §5.5, F11; extraction half) |
| I90 | (I38 part) | **= I38b: O28 at 65,536 L1 messages, through the count channels of a Go component.** I38's width half. A Go count component (holon-gocount/0.1) per carrier that the sidecar `spec/M3/lib/go_counts.json` names: every store of a method of the M3 Go document (`spec/M3/facts/morph_blob.go.extracted.json`, unchanged) that records the length of one parameter of that carrier's type is a channel, either the length realized in a narrow unsigned width (`f = f + uintW(len(P))`, a wrap channel) or one fixed-width item appended per element by a range loop over the parameter (an item channel); each channel is one CODEC edge from the carrier to its length count, citing its function. Rule PAR's existing producers derive over the component's diagram (P3: two channels of one function and one parameter are two paths of that function; the P8 cycle element a duplicate), so the rule catalog does not change. The law is decided on a Bend model whose carrier is the parameter's length, a `Nat` (parametric counts, no per-element cells), in both kernels at 65,536 elements, and its REFUTED witness is replayed on the real `BatchData.Append`. D2 (Hyp-Z0-kzg, checked since I3) is the regression. I38's compression half (HypZ, HypZ_len, O5, O6, D3) is I91. Numbered I90 only because prereg keys must be plain numbers | M3 | I18, I24, I67 | — | M3 (O28; §7.6 width obligations, as a PAR law over two channels; D2 regression) |
| I91 | (I38 part) | **= I38c: the compression oracle, HypZ and HypZ_len (§8.5; distinct from Hyp-Z0-kzg), with O5, O6 and D3.** I38's compression half, split from I90 so that O28 lands first: Enc and Dec uninterpreted under HypZ (forall x, k <= K. Dec(Enc x ++ 0^k) = x) and HypZ_len; O5 (PAR-branch: the estimators' fast path assumes non-expansion, and EstimateCompressedSizeWithNewPayload omits the block contexts of the real blob TxsPayloadV2), with a REFUTED witness that also replays on the real zstd; O6 (PAR-recompute: the legacy Go data hash against the on-chain formula for v0, through the preimage); D3 (block-context encode, decode and height; BaseFee normalization). Needs a frontend 0.3 config (a comparison as a Bool term, loop-carried updates per loop-body path) and primitives for encoding/binary and big.Int.FillBytes. Not started: its prereg is a later key | M3 | I67, I90 | the K bound of HypZ; whether zstd's real frame format is in scope | M3 (§8.5; O5, O6, D3) |

**Order in practice (2026-10-12).** Done: I1–I18, with I16 built early because it needs only I11. I59 (= I23a, data fetch only) runs in the background. Next is I19, then strictly I20, I21, I22, I23 and onward. Any other out-of-order step is announced, with its reason, before it starts.

**Order in practice (2026-10-13, parallel mode authorized by the human).** Work now runs in dependency order instead of strictly one iteration at a time. Anything whose dependencies are done starts now, and anything that depends on unfinished work waits for it.
- **I19 follow-up (A19), running:** an audit, a fix and an adversarial verification of the I19 extraction.
- **I20, built in two halves now:** a model side (machine, window, SORT-width, differential, re-extraction) and a real-contract side (Foundry refinement harness, observables, corpus, guard targeting, hevm).
  - Neither half commits outputs that depend on A19.
  - An integrator wires A19's additions and runs I20 once A19 merges.
- **Preregs drafted now:** I21, I22 and I23, which execute after I20; and I24, I30 and I41, which are M3 iterations whose dependencies (I14, I15, I10, I8, I13) are all done.
  - Preregs merge in iteration order.
  - Each build starts when its prereg is merged and its dependencies are finished.
- **I59 (= I23a)** keeps fetching.

**Calendar, honestly.** M2 gets 23 sessions (5 for debts, 18 for foundations and extraction) against a whitepaper budget of about one month. M3 gets 23, M4 7 and M5 5. The plan states plainly that M2 exit (a) cannot be met in this container without data the human supplies, and that M3's blind rerun cannot be fully uncontaminated on the development target.

---

## 4. Iterations

### M2 entry: pay the M0/M1 debts

#### I1. Prereg tool, honest ledger, v2 records, G1 over records, G6/G9 (about 2 days)

- **Milestone.** M2 entry. Closes D-e(1) and D-e(3), and the mechanical half of D-a.
- **Goal.**
  - Each record states exactly the premises of its frozen statement, plus the model assumptions its cone reaches. Every introducer in the cone is classified, so nothing is dropped silently.
  - v2 records have one field for each §8.6 item.
  - The gate regenerates records (G1), checks replay binding (G6) and checks record completeness (G9).
  - The prereg tool exists.
- **Realizes.** §8.5, §8.6, §9.3 G1/G6/G9, §9.4, §11.8.
- **Prereg commit.**
  1. `tests_m2/__init__.py` and `tests_m2/_m2.py`, reusing `tests._util` the way `tests_m1/_m1.py` does.
  2. Acceptance tests, red against the current tree. `tests_m2/test_ledger.py` contains:
     - `test_premises_are_exactly_the_rendered_statement_premises`: every `results/M0|M1/L_*.json` has `premises == holon.ir.premises(law)`. That function exists at `holon/ir.py:93`. `render_term` (`holon/ir.py:71`) is extended from 0.1 terms to 0.2 terms. M0 output stays byte-identical. The CF string is gone.
     - `test_own_record_carries_no_hash_assumption`.
     - `test_fact_Z_carries_Z0`: `Hyp-Z0-kzg` (D2) is among `L_fact_Z`'s `model_assumptions`. The name HypZ is reserved for §8.5.
     - `test_no_assumption_outside_cone`: no extra entries.
     - `test_every_introducer_in_cone_is_classified`: no omissions. Every builtin, param, oracle stand-in and abstraction-backed def in a law's cone has a ledger entry or an explicit `no_assumption` classification. Dropping an entry fails the test.
     - `test_unknown_facts_bundle_is_an_error`: building a record over a facts bundle with no ledger match fails loudly. It never yields empty `model_assumptions`, which covers `--no-registry` and re-extraction runs.

     Also red: `test_records_v2.py` (including `test_schema_covers_8_6`, which maps each of the nine §8.6 items to a required field), `test_gate_g1_g6_g9.py` (tamper cases), `test_ir02_schema.py` and `test_prereg_order.py`.
  3. `spec/ledger/assumptions.json`. Entries have the form `{id, facts_sha256, kind: hash|oracle|abstraction|scope_note, text, introduced_by}`. Seed:
     - M0, from `facts/morph_header.json`: A-width, A-version, A-cache, A-dirty, and A-hash as a `scope_note`.
     - M1: CF-keccak-headers; CF-keccak-blobhashes (via `agg`); Hyp-Z0-kzg (param `Z`); oracle-ISubmitter; oracle-verifier-proof1; oracle-messenger; abs-window-shadow; abs-nat-tokens; abs-post-genesis-initial; go-growth-table-trunc512.
  4. `spec/M2/predictions.json` (I1 key) and `spec/schemas/predictions.schema.json`.
- **Further deliverables.**
  - `spec/schemas/law_ir_0_2.schema.json`.
  - `spec/schemas/result_record_v2.schema.json`, additive. Fields:
    - `model_sha256`, `generator_sha256`, `compiled_sha256`;
    - `model_assumptions`;
    - `scope_v2 {kind, horizon, at_state}` (v1 `scope` untouched);
    - `kernels[]`, `independence_class`;
    - `refinement_refs[]`, which holds `pending:I16` until I16;
    - `coverage`, which holds `pending:I19` until I19;
    - `non_vacuity`, which holds `pending:I3` until I3;
    - `witness_provenance`, `filter_bin`.

    The iteration that fills a field removes its `pending` value from the schema, and asserts that removal in its own acceptance test.
  - `holon/records.py`: v2 builder and cone of influence. Until I2 lands, the cone comes from `Machine.reads`/`fv`; after I2, from `DEFS.json`. It also does the assumption join.
  - `holon/mpipeline.py`: delete the CF append at line 233. `holon/pipeline.py`: add the v2 fields.
  - Gate changes:
    - **G1** also diffs `results/<m>/L_*.json` after recursively stripping `seconds`. No extra stamping step is needed: `holon run` already stamps REFUTED records from the committed replay report (`holon/pipeline.py:131,165`; `holon/mpipeline.py:207,293`).
    - A `HOLON_BUILD_DIR` override in `holon/model_eval.py` and `mpipeline.CompiledMachine`, so G1 and G5 never reuse the copied `build/` cache.
    - **G6**: every REFUTED record has a passed replay, its `witness_sha256` matches the report, and the report's morph commit equals the facts' target commit. A side may be `not_applicable` only with the label `model-only pending replay`.
    - **G9**: every record validates against both the frozen v1 schema and v2.
  - `holon/audit/prereg.py` and the command `python -m holon audit prereg`.
- **Preregister.**
  - Predictions:
    - Per-law `model_assumptions`, computed by hand from the facts before the code runs and listed in the key:
      - `L_own_txspayload` gets exactly `{go-growth-table-trunc512}`;
      - every rollup law whose cone includes a commit action gets CF-keccak-headers;
      - `L_fact_Z` gets Hyp-Z0-kzg;
      - each M0 law gets the subset of A-width, A-version, A-cache (only with a Go encoder in its cone) and A-dirty (only with a Solidity encoder in its cone) that its cone reaches.
    - G6 and G9 PASS for M0 and M1, with the two M0 Solidity sides labelled.
    - Tampering with a record's replay status or witness fails G1; flipping a report's witness hash fails G6.
    - 16/16 M1 IR files validate against the 0.2 schema.
  - Regressions: all 24 statuses and statement hashes unchanged; `summary.json` byte-identical.
- **Exit (mechanical).**
  - All suites green.
  - The gate reports G6 and G9 PASS for M0 and M1, and G1 covers 8 and 16 records.
  - `freeze.py check` OK.
  - `holon audit prereg` and `test_prereg_order` green.
  - M0 gate wall time under 900 s.
- **Risks and fallback.**
  - Frozen `tests/test_40_gate.py` requires every reported check to pass on the M0 copy, which has no `.git`. G6 and G9 must not read git.
  - An IR file that does not fit the 0.2 schema is reported, never "fixed".

#### I2. Semantic bindings and dependency index (about 2 days)

- **Milestone.** M2 entry. Closes D-h. Must land before I6 moves any semantics.
- **Goal.** Bind the meaning of every frozen statement mechanically. Every model definition its cone reaches is hashed, including generator-defined names and builtins. A change marks exactly the dependent results stale, and FAILS G2 until I10 provides an approved channel.
- **Realizes.** §8.9 (references by hash), §9.4 (stale propagation), L22.
- **Deliverables.**
  - Generators emit `gen/<m>/model/DEFS.json`: name → {sha256 of the emitted def text, refs[]}. They already emit per-action `decide_`, `exec_` and `step_` defs separately.
  - `holon/bindings.py` writes `laws/M0/BINDINGS.json` and `laws/M1/BINDINGS.json`: law_id → {statement_hash, cone: {def: sha256}, generator_sha256}. The cone covers `perm`, `runs_ok`, `no_code`, `cost`, `elapsed`, `last_ok`, `is_<act>`, `view_intact`, the observers (`kappa`, `tags_ok`, `new_hdr`, `lci_of`, `csr_last`) and every `b_*` builtin they reach.
  - `holon/deps.py` writes `results/<m>/deps.json`.
  - G2 extension: re-derive the bindings from a fresh generation. A mismatch FAILS, naming the law and the def.
  - `tests_m2/test_bindings.py`: in a copy, change the body of `b_tags_exact`, then of `step_finalizeBatch`. Each time, G2 must FAIL and name exactly the predicted laws.
- **Preregister.**
  - Predictions:
    - The cone of `step_finalizeBatch` is exactly the 15 rollup laws, since each quantifies over or exists over arbitrary traces. It excludes `L_own_txspayload` and every M0 law.
    - The cone of `b_tags_exact` is exactly `{L_tag_BVH}`.
    - The cone of the Go size-class table def is exactly `{L_own_txspayload}`.
  - Regressions: G1 and G2 pass unchanged on M0 and M1; hashes unchanged (BINDINGS is a sidecar).
- **Exit.** G2 reports bindings OK for all 24 laws. Tamper tests green.
- **Risks and fallback.**
  - If the emitted text cannot be split into defs reliably, emit the index from the generator's internal def list.
  - BINDINGS is agent-writable, so this protection is self-certified until Q1.

#### I3. Non-vacuity (G11V), D2 zero-blob check, checker pin and upgrade procedure (about 2 to 3 days)

- **Milestone.** M2 entry. Closes D-c and D-e(2).
- **Goal.**
  - Every premised law has a kernel-checked inhabitant, reachable from s0 where states are involved.
  - The D2 check actually runs.
  - The gate checks the checker that is actually running.
  - A checker upgrade re-checks everything (§8.8).
- **Realizes.** §12.3 and L21, §11.6 D2, §8.8, §9.3 G5, §9.7.
- **Deliverables.**
  - `holon/gen/inhabit.py` writes `gen/<m>/<law>/nonvac/{LAWS.bend, PROOF.bend}`, keeping claims and proofs in separate files as AGENTS and BEND_PRIMER §4 require.
    - `LAWS.bend` states `law nv_<id>: exs <binders>; exs h_i: {premise_i}`. The premise terms are emitted by the same renderer, from the same parent IR, as the parent law's `LAWS.bend`.
    - State binders are `run(p, s0)`. The witness comes from the `explore.mjs` premise search, the proof from `mproofs.evaluate`.
  - Gate check **G11V**, a new key:
    - every premised law needs an accepted inhabitant; a REFUTED witness counts;
    - each `nonvac/LAWS.bend` states exactly `[nv_<id>]` and is excluded from G11's scan, so the frozen meaning of G11 (`docs/M0_SPEC.md:160`) is untouched;
    - a test asserts that the canonical premise list equals the parent's.
  - Record field `non_vacuity {status, witness, reachable, degenerate, parent_statement_hash}`.
  - `holon/oracles/zero_blob.py` (D2) computes `0x01 ‖ sha256(0xc0 ‖ 0^47)[1:]` and compares it with `ZERO_VERSIONED_HASH` (`Rollup.sol:25`) and `EmptyVersionedHash` (`common/blob/payload.go:22`). The result goes to `results/M2/hypotheses.json` as `Hyp-Z0-kzg`.
  - Pin hardening:
    - `holon/bend.py fingerprint()` hashes the checkout HEAD, each `bend2/*.ts` file, `bendtt.lean` and the bun version, checked against `config/holon.json: bend.pinned_fingerprint`;
    - GENV refuses unpinned `HOLON_BEND_CMD` or `BENDTT`, sets `BEND_NO_TELEMETRY=1`, and scans `$HOME/.bunfig.toml` and `$XDG_CONFIG_HOME`;
    - an accepted canary writes `results/quarantine.json`. This is an agent-writable tripwire, labelled as such; the gate report records the event for the human;
    - `bend.budget_s_per_file` (default 120), with timings in `gate_timing.json`.
  - `python -m holon checker-upgrade --to <fingerprint>`: re-runs every milestone's gate and canaries under the candidate checker in a scratch tree, and writes `results/checker_upgrade/<from>-<to>.json` with every record diff. Adoption is a human config change. A changed status is a Surprise.
  - Tests: `test_nonvacuity.py` (a vacuous fixture law must FAIL G11V), `test_zero_blob.py`, `test_pins.py` (with a fake-accept double), `test_checker_upgrade.py`.
- **Preregister.**
  - Predictions:
    - `L_undo_CSR` and `L_undo_BD` inhabitants are non-degenerate: s1 and s2 agree on the premise field and differ in at least one other field.
    - `L_disch_stale` and `L_disch_stale_commit` have reachable κ inhabitants through the prefix [commitBatch, challengeState(1), wait 11] of the `L_sort_remaining` witness, which reaches inChallenge with t > start + W. Revision 1 cited the DISCH s*, which opens no challenge.
    - All 7 premised M0 laws are inhabited by their pin witnesses.
    - D2: the computed hash equals both constants.
    - Every proof file runs under 120 s. The quarantine drill blocks GENV. A `checker-upgrade` dry run to the same fingerprint shows zero diffs.
- **Exit.** G11V PASS for M0 and M1. `test_zero_blob` green. GENV reports fingerprint OK. M0 gate under 900 s.
- **Risks and fallback.**
  - No inhabitant within the bound means `non_vacuity: UNKNOWN (bound ...)` and a G11V FAIL for that law.
  - A D2 mismatch is a finding.
  - G11V is extended in I7 (CF), I8 (`Reach`), I12 (hypotheses) and I28/I29 (in-flight sets).

#### I4. Replay completion, provisional filter, case-study coverage (about 2 to 3 days)

- **Milestone.** M2 entry. Closes D-b and D-f, and makes G6 strict.
- **Goal.** Replay every side the M0 and M1 witnesses claim. Record whether each obstruction was actually observed. Assign provisional finding-filter bins. Generate the O/D/F coverage table from data.
- **Realizes.** §8.7 source 3, §9.6, §10.9 (provenance), §11.7–§11.8, App. G G6.
- **Deliverables.**
  - Linearise the `L_par_hdr_v2` and `L_par_hdr_ssvh` witnesses into `replay/M1/solidity/HolonTraceReplay.t.sol` traces on the commit path. Assert byte 0, the ssvh cell, and `keccak(header) == committedBatches[i]`. Update `replay/M0/report.json`.
  - **`L_tag_BVH` consumer replay.** A Go test at the version-2 consumer, which recomputes the aggregate `keccak(blobhash_0..N-1)`, applied to the stored BVH that `commitState` reused. It shows that a VH sits where an aggregate is expected.
  - **`L_fact_Z` consumer replay.** A Go library-level test showing that derivation outputs differ between the no-blob and zero-blob batches whose `committedBatches` are equal.
  - Every replay side gains an `obstruction_observed` field, set by the harness rather than by hand.
  - `config/holon.json: replay.{forge, solc, morph, sol_deps}` paths with sha256 pins.
  - `holon/filter.py` (provisional):
    - `witness_provenance ∈ {public_schedule, internal_harness, emulated_storage, library_api}`;
    - `filter_bin = finding` only if every applicable side passed, `obstruction_observed` is true, and the provenance is `public_schedule` from a deployed reachable state;
    - `model_defect` if a replay failed;
    - `pending` otherwise. `known_limitation` is not assigned until I40's BMC can show that no public path exists.
    - Bins are reproducibility; v1 `triage` (intent) is untouched.
  - `tools/casestudy.py` plus a sidecar `spec/ledger/maps_to.json` (frozen M0 IR cannot gain `maps_to`). It writes `results/casestudy_coverage.json` and `docs/CASESTUDY.md`. Criteria: "full" means a law mapped to the id, an outcome that matches the §11.3 rule, and the obstruction observed in replay; "partial" means anything less.
  - Strict G6.
  - Tests: `test_filter.py`, `test_casestudy.py`.
- **Preregister.**
  - Predictions:
    - On-chain byte 0 is `0x02` for the v2 witness; the commit path writes ssvh = 0.
    - The `L_tag_BVH` consumer recomputation differs from the stored BVH.
    - The two `L_fact_Z` derivation outputs differ.
    - Provenance: `L_dom_hdr` Solidity side `internal_harness`; `L_nat_eta2` `emulated_storage`; `L_own_txspayload` and both consumer sides `library_api`; the rest `public_schedule`.
    - Bins: `finding` for `L_undo_BVH`, `L_undo_cancel`, `L_sort_remaining`, `L_sym_omega` and both M0 commit-path witnesses; `pending` for the rest.
  - Regressions: none counted. Coverage counts are derived data, not predictions.
- **Exit.** Every new replay passes or carries a model-only label. Strict G6 PASS. Tests green.
- **Risks and fallback.** If `node/` dependencies cannot be fetched through the proxy, the consumer sides stay `model-only pending replay`, their bins stay `pending`, and the M1 replay letter stays partly unmet. Reported.

#### I5. First audit round on M0/M1 (about 1 to 2 days)

- **Milestone.** M2 entry. Closes D-g.
- **Goal.** Run the never-executed adversarial audit before building on M0/M1.
- **Realizes.** §9.5 (A2, A3, A4 style), L19.
- **Deliverables.**
  - `prompts/P6b_audit_M1.md`, adapting P6 to M1. Attacks: model vs `Rollup.sol` and Go, gate evasion through BINDINGS or ledger, vacuity, determinism, and new mutations beyond MUT1–4.
  - `audit/M0_round1.md` and `audit/M1_round1.md`, written by a fresh session from a different model family if Q9 allows.
  - `audit/rounds/M1/round1.json`, and `spec/schemas/audit_round.schema.json` (a minimal version, extended in I45).
  - `audit/findings.jsonl`: one entry per finding, each with a severity and an assigned fix iteration. Fixes happen in separate sessions, each with a test, as P6 requires.
  - `python -m holon audit status`.
- **Preregister.**
  - Predictions: the vacuity attack finds no unsatisfiable premise among the 24 laws (given I3); the determinism attack finds no nondeterminism.
- **Exit.** Both round files exist and validate. `holon audit status` reports zero open high-severity findings before I6 starts.
- **Risks and fallback.** With a same-family auditor, rounds are labelled as such and the findings still count. Convergence accounting starts in I45.

### M2: foundations, extraction, replay

**M2 exit criteria (§15.2):**
- (a) zero unexplained replay disagreements over a historical window;
- (b) mutation adequacy at or above a preregistered threshold.

#### I6. Remove Morph-specific code from the generators (about 3 days)

- **Milestone.** M2. Prerequisite for extraction and for M4.
- **Goal.** `holon/` holds only generic machinery, and the meaning of every frozen M0/M1 statement stays exactly as it is.
- **Realizes.** §8.3, §9.7, App. H. Closes V16.
- **Deliverables.**
  - `spec/M1/lib/morph_rollup.lib.json` holds the DSL defs that replace `win_at`, `win_last`, `nth_ch`, `set_ch`, `bump_f`, `any_open`, `clear_chs`, `zero_csr`, `set_last_csr`, `tags_exact`, `hdr_of`, `agg` and `es_*`. I30 later deletes `tags_exact` from M2+ models.
  - `spec/lib/go_slices.lib.json` holds the Go append and growth oracle. The size-class table is emitted **exactly** as today, because it triggers the bend2/BendTT mismatch (`docs/M1_REPORT.md` §2.6, `replay/M1/kernel_mismatch/`).
  - `machine.py` keeps only generic primitives. `mcanary` derives live fields from `Machine.reads`. `holon/js/policy_gen.mjs` generates candidates. `policy_lib.mjs` becomes the untrusted `spec/M1/policy_hints.mjs`. The `mreplay` op table is generated. `mproofs.deadline` handles linear Nat conjunctions.
  - `tests_m2/fixtures/toy_queue.facts.json` and `tests_m2/test_target_agnostic.py` (grep for Morph identifiers, plus the toy machine end to end).
- **Preregister.**
  - Predictions:
    - `gen/M0/**` and `gen/M1/**` (`.bend` files and `DEFS.json`) are byte-identical before and after. `BINDINGS.json` is unchanged.
    - Records are byte-identical modulo `seconds`, witnesses included, with `policy_hints.mjs` preserving the search order.
    - The grep allowlist is empty.
    - Toy machine: one planted true law PROVED, one planted false law REFUTED.
  - Regressions: 24 statuses and hashes; canary counts at least 16 and 21, all rejected; 0 disagreements on the 300-trace corpus.
- **Exit.** All suites and gates green. Byte-identity test green. Grep test green.
- **Risks and fallback.** A def that cannot be emitted byte-identically stays in `holon/` as a named allowlist exception and is listed as debt. It is never re-emitted with different text. A record difference is a Surprise: the old witness must still check as a counter-law, and any new witness must replay.

#### I7. IR 0.3 (about 3 days)

- **Milestone.** M2. Prerequisite for every generated law.
- **Goal.** A kernel-neutral IR that has:
  - types, including function types for hashes and oracles;
  - references to model definitions by hash;
  - CF and hypothesis premises;
  - a scope separate from status;
  - counter-laws for ∧-laws;
  - correct semantics for ∃-laws and for hypothesis splits.
- **Realizes.** §8.9, §8.5, §8.6, §9.4, Thm 6.17, Cor 6.16.
- **Deliverables.**
  - `spec/schemas/law_ir_0_3.schema.json`. Types: `Nat`, `Bool`, `Bytes(n)`, `Fn<A,B>`, record refs, `State`, `Trace`, `Act`, `Reach`. Premise forms `{cf}` and `{hyp}`. `statement.scope ∈ {unbounded, bounded{H}, at_state{ref}}`. Structured `maps_to`. `rule` includes INTENT.
  - **The 0.3 statement hash** is sha256 over `{ir_version, law_id, rule, rule_catalog_version, statement, refs}`.
    - `refs` maps each referenced definition to the content hash of the construct that defines it: a facts or lib def, or, from I11 on, its diagram element (one-to-one by I11's mapping test).
    - Generator-synthesized helpers (`runs_ok`, `cost`, `elapsed`, `perm_X`) map to `{template_id, template_version}`.
    - No whole-bundle hashes. An extraction change outside a law's refs leaves its hash unchanged.
    - Generator source sha256 is provenance (`DERIVATION.json`, `BINDINGS.json`), enforced by G1.
  - `holon/gen/mlaws.py`:
    - `for h: <Fn>` with pairwise CF premises over the finite S (frozen probe `p12`);
    - **∧ counter-laws**: a concrete witness plus the failing conjunct's index; REFUTED is legitimate because the law is ∀;
    - **∃-laws are never REFUTED.** AGENTS rule 6 requires a concrete witness, and Thm 6.17 covers only ∀-laws. The rule that emits an ∃-law also emits its negation subform ∀¬P (for example the DISCH blocked invariant, §8.4) as its own frozen law. The ∃-law stays UNKNOWN with `negation: <law id>`. A bounded exhaustive negative search is recorded as UNKNOWN `{bounded_negative: H, space}`.
    - **Hypothesis splits are law pairs.** A hypothesis-dependent obligation is emitted once per named hypothesis variant (`L@H`, `L@H′`), each with a standard status. `results/<M>/splits.json` derives "split on H" when the two differ.
  - G3 rejects any premise stating global injectivity; a canary carries one.
  - G11V for the new premise kinds:
    - CF(h, S) is inhabited by h := `agg` with CF(agg, S) discharged by evaluation;
    - `hyp` premises are inhabited by the concrete oracle instance named in the oracle record (I12).
  - Probes `bend/notes/p_ir03_fn_verdict` and `p_ir03_import_depth`, verdicts recorded in `bend/notes/README.md`.
  - `tests_m2/test_ir03.py`.
- **Preregister.**
  - Predictions:
    - The Fn+cf probe checks under both bend and `--verdict`.
    - A false ∧ fixture is REFUTED; a true one stays UNKNOWN.
    - A false ∃ fixture gives UNKNOWN `{bounded_negative}`, and its generated ∀¬ law is PROVED.
    - The global-injectivity canary is rejected.
    - A CF fixture's inhabitant checks.
  - Regressions: all 24 existing hashes recompute equal.
- **Exit.** `test_ir03` green. Probe verdicts recorded.
- **Risks and fallback.** If ∀¬ generation is out of reach for a rule, its ∃-laws stay UNKNOWN with the reason recorded.

#### I8. Core library and `Reach` (about 2 to 3 days)

- **Milestone.** M2. Waits on Q14a; the default is in §0.3.
- **Goal.**
  - Shared lemmas are checked once and imported, never trusted unchecked.
  - Invariants over reachable states become provable.
- **Realizes.** §8.3 (R), §6 core library, §10.3, L2.
- **Deliverables.**
  - **Probe first:** `bend/notes/p_core_import`. It answers two questions. (a) Does a `PROOF.bend` that imports a LAWS module containing an unproved law fail its check? (b) Does importing a `PROOF.bend` put that file's proofs into the checked closure?
  - The design does not depend on the answer:
    - generated proofs import `core/PROOF.bend` (which imports `core/LAWS.bend`), never `core/LAWS.bend` alone;
    - G3 bans bare LAWS imports textually;
    - a G4 canary leaves one core law unproved and must be rejected.
  - `holon/gen/core.py` emits `<gen_dir>/core/{LAWS.bend, PROOF.bend}`, imported as `../core/PROOF.bend`. Then `holon run --gen-dir <tmp>/gen` (frozen `tests/test_30_m0_results.py`) stays self-contained. M0 and M1 keep their pasted `CORE`, byte-identical; only M2+ import the core.
  - G3, G5 and G7 cover the core.
  - `machine.py` emits `Reach : HSt -> Type` (`r0`, `r_step`), with the fallback encoding `Σ p. s == run(p, s0)`.
  - `mproofs.reach_invariant`. `holon/js/houdini.mjs` (untrusted) proposes strengthenings, which live only in proof files.
  - G11V: `Reach` premises are inhabited by `r0` or `r_step` chains.
  - `tests_m2/test_reach.py` on the toy machine.
- **Preregister.**
  - Predictions:
    - probe (a): the importer fails;
    - toy machine: 2 true invariants PROVED, 2 false ones REFUTED;
    - `Reach` checks under `--verdict`;
    - G5 time on the toy rises by no more than 20%.
  - Regressions: `gen/M0` and `gen/M1` byte-identical.
- **Exit.** Tests green. The core canary is rejected.
- **Risks and fallback.** If probe (a) shows unproved imported laws are trusted silently, that is a Bend hazard: record it as a Surprise, and file a Question for the frozen primer. The PROOF-import rule already covers it.

#### I9. Lean second kernel for M0 (about 3 days)

- **Milestone.** M2. Closes D-d.
- **Goal.** Re-prove the M0 laws in Lean from the IR, through emitters independent of the Bend ones. Record independence class I2 only when both kernels agree.
- **Realizes.** §8.8, §8.9, §12.2, App. G G7. Closes V1 for M0.
- **Deliverables.**
  - `holon/gen/lean_model.py` (`Hdr` as a structure of `BitVec 8` fields), `holon/gen/lean_laws.py` (statement hash in a doc comment; must not import `holon/gen/laws.py`) and `holon/gen/lean_proofs.py`.
  - Proofs use `rfl`, `simp` (axioms: `propext` only) and per-cell lemmas, with `set_option maxRecDepth` emitted per file. `decide` is used only on closed concrete goals, such as counter-witnesses. **No `bv_decide`**: the local probe shows it adds `<thm>._native.bv_decide.ax_*`.
  - `lean/` lake project (`leanprover/lean4:v4.34.0`, no Mathlib), built into a temp directory so a copied `.lake` is never reused.
  - `holon/lean.py`: runner plus Lean G3. Lean G3 audits `#print axioms` and scans for the forbidden list in §2.5.
  - `gen/M0/lean/*.lean`. Records gain `kernels[]` and `independence_class`.
  - `tests_m2/test_lean.py`, including the emitter cross-check (canonical binders and premises are equal).
- **Preregister.**
  - Predictions:
    - the 5 PROVED M0 laws are re-proved in Lean;
    - the 3 counter-laws check;
    - cross-kernel agreement is 8/8;
    - each file checks in 120 s or less;
    - a flipped-equality Lean canary is rejected;
    - the M0 gate with Lean stays under 900 s.
- **Exit.** G7 lists I2 for all 8 M0 laws.
- **Risks and fallback.** If a 257-byte goal exceeds the budget even with per-cell lemmas, the Lean result is UNKNOWN and the record says I1. Common mode: both kernels consume the same facts (deferred item 2).

#### I10. Statement lifecycle, A3, prover separation (about 2 to 3 days)

- **Milestone.** M2. Must land before re-extraction changes any statement.
- **Goal.** Every statement change goes through an auditable channel. Cross-milestone weakening is caught. The rule that provers cannot change laws is enforced mechanically.
- **Realizes.** §9.4, §9.5 A3, L14, L22.
- **Deliverables.**
  - `laws/STATEMENT_DIFF.jsonl`, append-only. Entry kinds:
    - **reextraction**: allowed unsigned only if the changed refs come from extractor output that G1 reproduces from the pinned code with the pinned extractor, **and** `holon derive` reproduces the new statement from the same (rule, subform, basis element). Hand-written facts can never use this kind.
    - **binding_change**: an emitted def changed under a fixed 0.1/0.2 statement. Needs a generated, kernel-checked equivalence law between the old and new def, or a signature.
    - **strengthening**: needs a kernel-checked S′ ⇒ S.
    - **weakening**: needs a gpg signature from `keys/` (Q3) and an auditor review.
    - **cross_milestone**: a later milestone re-derives an analogue of an earlier law under a new id. The pair needs a checked S_new ⇒ S_old, or a signed weakening entry. Pairs come from `DERIVATION.json` back-test links, not from ids.
  - `holon/statement_diff.py`, `holon/gen/implication.py`, `holon/audit/regress.py` (`holon audit regress --from A --to B`, read-only `git show`; an audit tool, not a gate check).
  - **Prover separation, mechanically.** For M2+, laws live in `gen/<M>/laws/` and proofs in `gen/<M>/proofs/`.
    - G1 regenerates laws from 𝔇 plus the rules, so any edit to a law file fails G1.
    - G3 rejects a `law` declaration in `proofs/`.
    - Bend already refuses proof files that redefine model names (probe p15).
  - Tests: `test_statement_diff.py`, `test_regress.py`, `test_cross_milestone.py`.
- **Preregister.**
  - Predictions:
    - an unsigned weakening is rejected;
    - a strengthening with a checked proof is accepted;
    - a reextraction entry backed by a hand-edited facts file is rejected;
    - a cross-milestone fixture without an implication proof is rejected.
  - Regressions, all already known from history: A3 over `8a1dbe7..HEAD` reports 0 hash changes; 15 law files added at `9a96037` together with their results; `L_own_txspayload` added at `3e9cb2a` with its result and prediction entry; `spec/M1/predictions.json` introduced at `bfdb5f2`. A3 flags all 16 M1 laws as "result in the same commit; prediction later or together", and cannot single out the 2 labelled post hoc.
- **Exit.** Tests green. Gate green.
- **Risks and fallback.** Without a key the gate rejects every weakening. That claim is self-certified until Q1 freezes the registries, `BINDINGS.json`, `statement_diff.py` and `keys/`; A3 in every PR plus human review are the backstop.

#### I11. Diagram 𝔇 and principal classes (about 3 days)

- **Milestone.** M2.
- **Goal.** One deterministic diagram, built from all fact documents, that every rule, evidence check and sort reads from. No silent drops.
- **Realizes.** §4 Defs 4.1–4.4 and 4.7, §8.3 (principal class), App. H `diagram/`. Closes V6 apart from linking (I19), and V22 for M2+.
- **Deliverables.**
  - `holon/diagram/{model.py, build.py, interfaces.py, access.py, fragments.py, principals.py}`:
    - `Carrier(id, cls ∈ {rep, state, env, digest, buffer}, base_type, sort_ref, interface, reach)`;
    - `Edge(id, kind ∈ {CODEC, HASH, STORE, LOAD, CONS, TRANS, MIG, SYM}, src, tgt, component, version, partial, access, principal_class)`;
    - `Diagram`.
  - **Adapters, one mapping per facts section.**
    - Facts 0.1:
      - `types` → base types;
      - `functions` → CODEC edges, decoder domains, and product metadata for projections;
      - `assumptions` → ledger links.
    - Facts 0.2:
      - `params` → environment and parameter carriers;
      - `constants_doc` → lexical sources (E6);
      - `types` → base types;
      - `state` → state carriers plus a STORE/LOAD pair per field;
      - `ghost_state` → ghost carriers;
      - `shadow` → residue carriers;
      - `initial` → S0;
      - `principals` → Π;
      - `reasons` → revert result variants;
      - `defs` → content-hashed definitions attached to edges;
      - `actions` → TRANS, with index-sensitive read/write sets from `access.py`;
      - `migrations` → MIG;
      - `observers` → observation LOAD edges into Obs;
      - `disch` → DISCH metadata (class, guard-conjunct annotations, cost/delay terms);
      - `consumers` → CONS;
      - `coverage` → coverage-debt entries (feeding G8);
      - `abstractions` → abstraction records (feeding the ledger);
      - `target` and `extraction` → provenance.
    - **Debt cap:** zero unmapped constructs across the three existing fact documents (the test fails on any). Later facts versions may record debt, counted in metrics.
  - **Principal classes:** {caller type, permission predicate as a guard expression}. A generated `perm_X(a, who)` replaces the string-prefix `perm` in M2+ models. M1 models keep `perm`, bound by `BINDINGS.json`.
  - `spec/schemas/diagram.schema.json`. `python -m holon diagram --milestone M2` writes `gen/M2/diagram/*.json`, covered by G1.
  - `tests_m2/test_diagram.py`.
- **Preregister.**
  - Predictions:
    - M0 diagram: 4 CODEC edges (3 encoders, 1 decoder), 0 projection edges; interface carrier `Bytes` with domains `ok_sol` and `ok_go`.
    - Rollup diagram:
      - 10 TRANS edges, with `wait` as an environment edge;
      - 2 MIG, with `legacy` flagged as a pseudo-migration;
      - 1 CONS;
      - a STORE/LOAD pair per state field;
      - 0 HASH edges, recorded as coverage debt;
      - principal classes {owner, active submitter, challenger, anyone, environment}, each with a predicate.
    - Batchdata diagram: 2 TRANS.
    - Index terms include `(win, idx−lfi)`, `(chs, bc)` and the shadow slot at `lci+1`.
- **Exit.** Byte-identical regeneration. Schema valid. Zero unmapped constructs. G1 green.
- **Risks and fallback.** A construct that fits no edge kind is a Question about the diagram definition, not a forced mapping.

#### I12. Hashes and oracles as parameters (about 3 days)

- **Milestone.** M2. Moved ahead of every generated law, so no generated law has to be re-derived when hashes become parameters.
- **Goal.** M2+ models take hash functions and oracles as parameters, with CF and Hyp premises in the frozen statements. Every §11.1 oracle has a record.
- **Realizes.** §8.3 (HASH and oracle rows), §8.5, Thm 6.15, Cor 6.16. Closes V4 and V5 for M2+.
- **Deliverables.**
  - `spec/M2/lib/oracles.json` (sidecar). Each entry holds `{parameter, hypothesis predicate, concrete instance (for refutation and inhabitation), status: modelled | not_in_scope(reason)}`, and the file covers:
    - `agg` as the stand-in for keccak over blob hashes;
    - header presentation as CF(keccak, headers);
    - ISubmitter, the verifier and the messenger;
    - the full §11.1 oracle list: compression codec, circuits, KZG and the transaction codec, **L2 predeploys**, fetcher, **sealing loop**.
  - `machine.py` threads `h` and the oracle parameters through `step` and `run` in `gen/M2/model`. `agg` survives only as the instance used by the refuter and the inhabitants.
  - `holon/oracle_check.py` writes `results/M2/hypotheses.json`. Each hypothesis is tested against the real oracle where one is available (A4). The verifier's `proof == 1` rule is a stand-in and is labelled `untestable_here`.
  - For M2+ laws, `model_assumptions` is exactly the set of hypothesis premises, as §8.5 requires.
  - G11V: each hypothesis has a concrete instance satisfying it, proved by a checked law. The `splits.json` machinery from I7 applies here.
- **Preregister.**
  - Predictions:
    - the parametric model checks with term size per law at most 1.5× the M1 model's on the same fixture laws;
    - a fixture oracle with two hypothesis variants yields a law pair with different statuses, reported as a split;
    - the `agg` inhabitant of CF(h, S) checks.
  - Regressions: M1 laws and models untouched.
- **Exit.** Tests green. G3 rejects a global-injectivity premise.
- **Risks and fallback.** If threading the parameters breaks term-size limits, fall back to an opaque state field that holds an oracle table, with CF over it.

#### I13. Sorts I: grammar, constraints, union-find, unsat cores, frozen assignment (about 3 days)

- **Milestone.** M2. Moved before evidence, because E5 is "identical refined sorts".
- **Goal.** Infer refined sorts mechanically and freeze the assignment before any typed check.
- **Realizes.** §7.1–§7.4, §7.7 steps 1–4, Thm 6.18 freezing condition.
- **Deliverables.**
  - `holon/sorts/{grammar, constraints, flow, solve, core, unions}.py`. `solve.py` is a pure-Python union-find. `core.py` extracts minimal unsat cores by deletion (QuickXplain).
  - `spec/schemas/sorts.schema.json`.
  - `python -m holon sorts` writes `gen/M2/sorts/{constraints, assignment, conflicts, unions, unresolved}.json`.
  - `sorts_sha256` goes into `laws/M2/REGISTRY.json`.
  - Sites are keyed by source span.
  - `tests_m2/test_sorts_*.py`, including a planted Time+Time fixture.
- **Preregister.** Frozen before the solver first runs on Morph facts.
  - Predictions:
    - `t` is Time and `wait.dt` is Dur; W, F and D are Dur; `Ch.start` is Time.
    - `W + cstart − t` is SDur at **one** source site, Rollup.sol:363. Three entry points reach it through `_commitBatchWithBatchData`: `commitBatch` (:268), `commitState` (:285) and `commitBatchWithProof` (:411). The M1 facts duplicate the guard per action (`spec/M1/facts/morph_rollup.json`, lines 1110, 1502, 2017), and deduplication by span yields one site.
    - `qpend` and `Entry.tot` get distinct sorts, `Idx[queue]_fin` and `Idx[queue]_inc`, through writer provenance.
    - `win.bvh` and `s_bvh` form the union `Dig[VH] + Dig[Agg]`.
    - 0 SORT-affine conflicts on the M1 facts.
    - The planted fixture's minimal core has exactly 2 constraints.
- **Exit.** Byte-identical assignments across two runs. Tests green.
- **Risks and fallback.** Weakly seeded variables stay "Nat (unrefined)" and are counted in `unresolved.json`; nothing is guessed.

#### I14. Evidence calculus (E1–E6) and frozen evidence set (about 2 days)

- **Milestone.** M2.
- **Goal.** Compute evidence levels from 𝔇, E5 included. Freeze the evidence set (L3). Derive triage defaults without touching the frozen v1 `triage`.
- **Realizes.** Def 4.5, §5.1, §10.2 getter recovery, L3. Closes V7.
- **Deliverables.**
  - `holon/layout.py: recovers, evidence`.
  - `holon/diagram/evidence.py`: E1 layout inversion, E2 write-then-read, E3 compared outputs, E4 recompute, E5 equal refined sorts (from I13), E6 lexical.
  - `gen/M2/evidence.json` is the **frozen evidence set**; its sha goes into the registry.
  - Gate check **GEVID**: metadata evidence must be a subset of computed evidence. It is report-only for M0/M1 and enforcing for M2+.
  - v2 field `evidence_triage`: `intent_question` if the maximum level is E6, `finding` otherwise. Overrides need `evidence_override` plus a `why`, and the gate lists them.
  - `tests_m2/test_evidence.py`.
- **Preregister.**
  - Predictions:
    - (enc_sol, dec_go) and (enc_go_v1, dec_go) have E1 on all v0/v1 fields.
    - (commit*, revertBatch) have E2 on the BVH residue.
    - The previous-state-root guard gives E3.
    - `L_par_hdr_ssvh`'s `evidence_triage` is `finding`, against its v1 `triage` of `intent_question`, and is listed as a divergence.
    - GEVID's verdict on the E5 claims of `L_sort_remaining` and `L_tag_BVH` is preregistered per law against I13's frozen assignment.
- **Exit.** GEVID report generated. Tests green.
- **Risks and fallback.** Laws are never edited to agree with GEVID. A mismatch is a finding about the metadata.

#### I15. Sorts II: per-site SORT laws and the rules registry (about 3 days)

- **Milestone.** M2. These are the first generated M2 laws.
- **Goal.** One obligation per signed-to-unsigned site, whether or not a human modelled a require. Coherence obstructions surface at guard sites.
- **Realizes.** §7.2, §7.3, §5.6, Thm 6.18 localization, App. E SORT basis.
- **Deliverables.**
  - `holon/rules/__init__.py`: the registry, `rule_catalog_version: 1`, and `python -m holon derive` writing `laws/<M>/`, `REGISTRY.json` and `DERIVATION.json`.
  - `holon/sorts/check.py`.
  - `holon/sorts/sites.py` (rule SORT-site) emits one IR 0.3 law per source span: `∀p. at_site(p, s0, ℓ) → nonneg(d_ℓ)`, with an id derived from the span.
  - An instrumented M2 model with ghost `site_hit` events. `mproofs.coercion_guard`. `gen/M2/sorts/obstructions.json`.
  - `tests_m2/test_sort_sites.py`.
- **Preregister.**
  - Predictions:
    - every `-` site is classified by span, with per-site outcomes listed in the prereg;
    - the :363 site yields **one** law, REFUTED, with one witness per entry point (`commitBatch`, `commitState`, `commitBatchWithProof`), each replaying as Panic 0x11 at :363. This localizes the failure to a site, where `L_sort_remaining` was stated over a reason code;
    - the `idx−1` site (:636) is PROVED by `coercion_guard`;
    - under MUT2 the :363 law is still generated and REFUTED through the two unmutated entry points, and the derive diff lists `commitBatchWithProof` as no longer reaching the site;
    - coherence obstructions appear at the `enq_first` call sites.
- **Exit.** Derive output is byte-identical. New witnesses replay or are labelled. Gate green for M2.
- **Risks and fallback.** An unguarded site without a witness stays UNKNOWN, with its bound; I40 revisits it.

#### I16. Native C model, per-edge corpus, refinement records, metrics (about 3 days)

- **Milestone.** M2. The corpus half of M2 exit (a).
- **Goal.** Per-edge replay at volume, with every disagreement classified by a mechanical criterion.
- **Realizes.** §8.7 sources 1–3, Def 4.7 ρ(e), §8.6, §13.
- **Deliverables.**
  - A probe in `bend/notes/c_probe/`.
  - `holon/gen/cdriver.py`, `holon/model_native.py`, `holon/corpus.py` (seeded grammar samples, sort-boundary values, witnesses).
  - Harnesses `replay/M2/go/holon_codec_test.go` and `replay/M2/solidity/HolonCodec.t.sol`. Their dependencies stay outside the repo.
  - `holon/refinement.py` writes `results/M2/refinement/<edge>.json`, comparing each model edge **with its own implementation**: `enc_sol` with the Solidity store, `enc_go_v1` with Go's `Bytes()`, `dec_go` with Go's decode.
  - **Mechanical disagreement classes** in `spec/M2/disagreements.json`:
    - `extraction_defect` is valid only with a linked fix commit and a green re-run record for that edge;
    - `real_defect` is valid only with a link to a REFUTED law whose witness replays with `obstruction_observed`;
    - `oracle_mismatch` is valid only with a link to a failing hypothesis record;
    - anything else is `unexplained`, and the gate FAILS. The gate checks the links, not the labels.
  - Records gain `refinement_refs`; `pending:I16` is removed.
  - `holon/metrics.py` writes deterministic `results/<M>/metrics.json`. Timings, including from-scratch gate time, go to `metrics_timing.json`, which G1 excludes.
  - Tests: `test_native.py`, `test_refinement.py`, `test_metrics.py`.
- **Preregister.**
  - Predictions:
    - native and `.mjs` agree on 100% of the refuter's candidates;
    - per codec edge: 2,000 grammar samples, all boundary values, all witnesses;
    - **0 disagreements on every faithful edge**, v2 inputs included (`enc_go_v1` writes byte 0 = 1 exactly as Go does), and decoder domains included;
    - O1 and O2 appear as cross-edge PAR differences linked to `L_dom_hdr` and `L_par_hdr_v2`, not in the refinement counts;
    - 0 unexplained.
  - Regressions: 0 disagreements on the M1 corpus.
- **Exit.** Tests green. `metrics.json` generated. Gate green.
- **Risks and fallback.** If C compilation fails, keep `.mjs`, record a Surprise, and still produce per-edge records.

#### I17. Solidity frontend I: compile, AST/Yul walk, layouts (about 3 days)

- **Milestone.** M2 scope (codec extraction).
- **Goal.** Derive the header layout from the compiler's Yul, not from a transcription.
- **Realizes.** §10.1, §10.2 (`calldatacopy`), §8.3 (facts 0.3). Part of V10 and V17.
- **Deliverables.**
  - `holon/frontends/solidity/{compile, ast, layout_extract}.py`.
  - `tools/setup_env.sh --extract`, which installs pinned slither-analyzer and z3-solver into `~/.holon/tools`.
  - `spec/M2/facts/morph_header.extracted.json` (holon-facts/0.3, covered by G1).
  - `calldatacopy` cells; `Maybe<Bytes>` encoders.
  - `tests_m2/test_extract_solidity_layout.py`.
- **Preregister.**
  - Predictions: the extracted `enc_sol` layout equals the frozen one cell for cell for versions 0, 1 and 2; the unsupported-Yul debt list is empty for the store sequences.
- **Exit.** Byte-identical extraction across two runs. Tests green.
- **Risks and fallback.** A layout difference is either a finding about the frozen facts or an extractor bug. Raise a Question; never edit `facts/`.

#### I18. Go frontend: codecs, partiality, slice headers, pipelines, loop bounds (about 3 days)

- **Milestone.** M2 scope. It also extracts what M3's OWN and consumer rules need, so M3 never transcribes it by hand.
- **Goal.** Extract from SSA the Go codecs, their panic and partiality conditions, slice backing identities, consumer pipelines and loop bounds.
- **Realizes.** §10.1 Go, all four bullets.
- **Deliverables.**
  - `holon/frontends/go/ssadump/{main.go, go.mod, go.sum}`, pinning `golang.org/x/tools`.
  - `holon/frontends/go/extract.py`. It extracts `enc_go_v0`, `enc_go_v1` and `dec_go` with their partiality; backing-identity facts `(backing, offset, len, cap)` for returned slices; call-chain skeletons from producers to consumers; and loop bounds as cost or fuel annotations.
  - Output in `spec/M2/facts/*.go.extracted.json`.
  - `tests_m2/test_extract_go.py`.
- **Preregister.**
  - Predictions:
    - the extracted layouts equal the frozen ones;
    - decoder partiality equals `ok_go` on every length constant ±1;
    - there is no v2 encoder (O2, recorded as an absence);
    - the `TxsPayloadV2` result shares backing with the spare capacity of `blockContexts`, which is O36's precondition.
- **Exit.** Tests green.
- **Risks and fallback.** If the pin cannot be downloaded, vendor the module hash-pinned, and scan the vendored tree for `.env` and `bunfig.toml` (frozen `tests/test_12_hygiene.py` scans the whole repo).

#### I19. Solidity frontend II: storage, transitions, cost terms, principals, linking, G8 (about 3 days)

- **Milestone.** M2 scope (straight-line state updates).
- **Goal.** Extract state carriers, guards, effects, cost terms and principal predicates. Link Solidity to Go. Account for coverage.
- **Realizes.** §10.1 Solidity, linking, §7.7 step 5, §9.3 G8, L1 coverage.
- **Deliverables.**
  - `holon/frontends/solidity/{storage, transitions}.py`:
    - storage families with widths;
    - inlined modifiers become ordered guards with reasons, and **modifiers also become principal-class predicates**;
    - effects;
    - **loop bounds become cost terms** `c0 + Σ c_ℓ·iters_ℓ`;
    - `keccak256`, `blobhash` and verifier call sites become HASH or COMMIT edges;
    - external calls and loops with storage writes go to coverage debt.
  - `holon/frontends/link.py`.
  - `holon/coverage.py` and gate check **G8** (report exists, matches a fresh run, `unaccounted == ∅`). Records gain `coverage`; `pending:I19` is removed.
  - `spec/M2/facts/morph_rollup.extracted.json`.
  - Tests: `test_extract_transitions.py`, `test_coverage.py`.
- **Preregister.**
  - Predictions:
    - the extracted families include CB, CSR, BVH, BD, CH, LCI and LFI (slots 151–174);
    - the guard sequences for the 8 modelled actions match the M1 guards modulo the abstraction map, with every mismatch listed and the `committedBatches` checks appearing as abstraction differences;
    - 249, 257 and Z are equal across languages;
    - principal predicates for `onlyOwner`, the active-submitter check and the challenger check are extracted;
    - unaccounted = 0.
- **Exit.** G8 PASS on M2. Tests green.
- **Risks and fallback.** Without SlithIR, use the AST walker. Unsupported statements are listed with source spans.

#### I20. Extracted rollup model: refinement, width, optional hevm (about 3 days)

- **Milestone.** M2. The corpus half of M2 exit (a).
- **Goal.** Compile the extracted state machine, show it refines the real contract, and generate width obligations.
- **Realizes.** §8.7, §7.6, §10.1 translators, L1 (optional hevm equivalence).
- **Deliverables.**
  - `machine.py` compiles facts 0.3 (raw families, plus a window view where declared).
  - `holon/replay_fragments.py`.
  - Width-site laws (rule SORT-width).
  - An M1-laws differential with `--no-registry` on the extracted facts.
  - Explorer boundary values from the extracted sorts.
  - Re-derivation of I15's site laws on the extracted facts, through reextraction entries.
  - **Optional:** `hevm equivalence` between the bytecode of `BatchHeaderCodecV0/V1.store*` and Yul generated from the model layout, for the top codec edges. If hevm cannot be installed, recorded as "not run".
  - `tests_m2/test_extracted_refinement.py`.
- **Preregister.**
  - Predictions:
    - 0 unexplained disagreements on the 300-trace and boundary corpus;
    - the width obligation at the `unchecked` accumulator (:324) is UNKNOWN under enumeration;
    - the reextraction entries for I15's laws validate unsigned.
- **Exit.**
  - Refinement records show 0 unexplained disagreements for every extracted edge.
  - The differential table is complete: each of the 15 rollup laws is re-run, and every status difference links to a delta id present in `gen/M2/abstraction_diff.json`.
- **Risks and fallback.** If the generated window view disagrees with the hand abstraction, the raw-family model is authoritative and both are reported.

#### I21. A2/A4 audit round on extraction (about 1 to 2 days)

- **Milestone.** M2.
- **Goal.** Check, before A1 relies on them, that the extracted partiality matches the code's and that premises and hypotheses hold up.
- **Realizes.** §9.5 A2 and A4.
- **Deliverables.** A fresh auditor session runs two attacks:
  - A2: hostile inputs at every interface carrier through public entry points;
  - A4: premise satisfiability, and hypotheses tested against the real oracles.

  Output goes to `audit/rounds/M2/round1.json`, with findings in `audit/findings.jsonl`.
- **Preregister.**
  - Predictions: A2 finds no partiality mismatch on the v0/v1 decoders; A4 finds every hypothesis in `results/M2/hypotheses.json` either tested or labelled untestable.
- **Exit.** The round validates. Zero open high-severity findings before I22.
- **Risks and fallback.** A same-family round is labelled, and its findings still block.

#### I22. A1 mutation adequacy on real code (about 3 days)

- **Milestone.** M2. **Closes M2 exit (b).** Waits for Q6.
- **Goal.** Plant misimplementations in the real Solidity and Go, re-extract, and measure the kill rate against a threshold fixed in advance.
- **Realizes.** §9.5 A1, L1 sensitivity, §15.2 M2. Closes V14.
- **Deliverables.**
  - `holon/mutate/operators.py`, a seeded catalog:
    - Solidity: mstore offset ±1, dropped `delete`, wrong `shl` width, swapped cursors, `>=` ↔ `>`;
    - Go: `PutUint64` offset ±1, copy bounds, dropped length check.
  - `holon/mutate/run.py`: a scratch copy of `/root/work/morph`, re-extraction with I17–I19 **and I18**, `holon run --no-registry`, replay.
  - `spec/M2/equivalent_mutants.json`. The human adjudicates on the mutant diffs **before any run**, without seeing outcomes.
  - `results/M2/mutation_adequacy.json` and `tests_m2/test_mutation_adequacy.py`.
- **Kill criterion.** A mutant is killed iff the obstruction predicted for its operator appears, localized to the mutated edge: a law moves to REFUTED, with a witness that replays on the mutant code, or a PROVED law loses its proof. A replay disagreement alone is recorded as "extraction defect detected", not as a kill.
- **Preregister.** In `spec/M2/preregistration.json`, before the catalog first runs:
  - the threshold from Q6;
  - the catalog, the seed and the in-scope list. These fix the denominator. Both rates are reported: over all mutants, and over non-equivalent mutants;
  - per-operator predicted kills:
    - header offset and `shl` mutants → PAR laws;
    - dropped `delete` in `revertBatch` → UNDO laws;
    - swapped cursors → the corpus plus the UNDO and SYM laws;
    - Go offset and copy mutants → round-trip laws;
    - dropped length check → the domain law.
- **Exit.** The rate meets the threshold, recomputed by test.
- **Risks and fallback.** Below threshold means M2 exit (b) is not met. Survivors are filed as extraction gaps or rule gaps. The threshold never moves.

#### I23. Historical inputs and M2 exit evaluation (about 2 days)

- **Milestone.** M2. **Closes M2 exit (a) only if historical data is supplied.**
- **Goal.** A complete, offline-deterministic path from historical transactions to model replay, and an honest exit report either way.
- **Realizes.** §8.7 source 4, §15.2 M2.
- **Deliverables.**
  - `tools/fetch_historical.py`, for the human to run where RPC is allowed.
  - A BigQuery SQL alternative.
  - `holon/historical.py`.
  - The 6 morph fixtures, labelled `synthetic_smoke`.
  - `docs/M2_EXIT.md`, generated from the metrics.
- **Preregister.** In `spec/M2/preregistration.json`: the window bounds, the expected explained classes (each with its I16 mechanical criterion), and a target of 0 unexplained.
- **Exit.**
  - With a snapshot: `metrics.refinement.unexplained == 0` over the window.
  - Without one: `M2 exit (a): UNKNOWN, no historical data reachable (403 policy)`. Substitute-corpus results are labelled as a substitute, and M2 is not declared closed.
- **Risks and fallback.** Blobs older than about 18 days are gone. A calldata-only window needs the human's acceptance (Q5).

---

### M3: full Morph bundle, eight rules, audit loop, blind rerun

**M3 exit criterion:** a published comparison with §11.8 and Appendix A.
- Tests live in `tests_m3/`.
- Every back-test pair needs an implication proof or a signed cross-milestone entry (I10).
- M3 facts are extractor outputs (§2.3).

#### I24. Rules engine and PAR, all sub-forms (about 3 days)

- **Goal.** `holon/rules/par.py` generates every PAR sub-form wherever the diagram has the structure:
  - round trip;
  - cross-component codec agreement;
  - **recomputation** (E4 pairs);
  - **branch agreement** (fast and slow paths of one CODEC);
  - **consumer agreement** (CONS edges against commitments);
  - **cycle** (fundamental cycles over TRANS, CODEC and HASH, via a deterministic BFS spanning tree);
  - **initialization coherence** (E3 equations in S0; instances arrive in I28);
  - domain coherence at each interface;
  - **totality** (each CODEC or CONS edge total on R^ext, or partial with an explicit option; the O4 class);
  - **PAR-weak** (E6-only pairs, emitted as laws with `evidence_triage = intent_question`; the O10 class).
- **Realizes.** §5.1, §10.3 steps 1–3, Thm 6.4 use, App. E, §11.3 sub-forms.
- **Deliverables.** `par.py`, `laws/M3/` with REGISTRY and DERIVATION, `tests_m3/fixtures/par_<subform>.facts.json` (one per sub-form) and `tests_m3/test_derive_par.py`.
- **Preregister.**
  - Predictions:
    - the basis count equals \|E\|−\|V\|+κ, computed from the I11 diagram in the prereg;
    - each fixture's derived law and outcome is listed;
    - the new Morph laws beyond M0 are listed.
  - Regressions: the matched M0 outcomes are identical.
- **Exit.**
  - The back-test table is complete: every M0 law has an α-equivalent derived law with a checked implication, or an open rule-gap record.
  - Every sub-form generator produces its fixture law.
  - M3 exit cannot be claimed while a back-test rule gap is open.
- **Risks and fallback.** A missed M0 law is a rule gap. It is never added by hand.

#### I25. PAR-lossy and injective pushing (about 2 to 3 days)

- **Goal.**
  - Enumerate evidenced lossy pairs from the frozen evidence set.
  - Push through injective maps (Lemma 6.12).
  - Report evidenced-pair coverage.
  - Every uncovered replay disagreement opens an evidence review.
- **Realizes.** §10.3 step 6, Prop 6.11, Lemma 6.12, L3.
- **Deliverables.**
  - `holon/rules/par_lossy.py`.
  - Lemma 6.12 `inj_push` as a core law, under CF premises for hash maps.
  - An `evidenced_pair_coverage` metric.
  - `spec/M3/evidence_review.jsonl`: one entry per uncovered refinement disagreement, adjudicated by A4 in I45.
- **Preregister.**
  - Predictions:
    - `inj_push` is PROVED;
    - a lossy fixture with an injective post-map gives a pushed law PROVED;
    - a non-injective fixture yields no basis law and coverage below 100%;
    - D7's 32-bit tree-index truncation is identified as a pushing candidate, with its instance in I36.
- **Exit.** The coverage metric is in `metrics.json`, and there is one review entry for each uncovered disagreement.
- **Risks and fallback.** Completeness is relative to the evidence set (Prop 6.11), and the metric says so.

#### I26. FACT rule, attribution (O25), F(m,c) (about 3 days)

- **Goal.**
  - FACT obligations per commitment × consumer.
  - The quantitative form in bits.
  - The attribution case §5.5 lists.
- **Realizes.** §5.5, Thm 6.8 (iii), Def 6.13 F(m,c), §11.4 N3.
- **Deliverables.** `holon/rules/fact.py`, `mproofs.product` and `holon/measures_fact.py`.
- **Preregister.**
  - Predictions:
    - **O25/N3**: the FACT-attribution law (whose bond is at risk on recommit, against who chose the content under the BVH pin) is REFUTED. Witness: S1 commits, the owner reverts, S2 recommits the pinned content. It replays in Foundry.
    - F(Z, derivation) = 1 bit.
  - Regressions: the parametric `L_fact_Z` analogue (premises CF and Hyp-Z0-kzg) is REFUTED, and its implication to the old law (via CF(agg, S) by computation) checks.
- **Exit.** Tests green. Witnesses replay.
- **Risks and fallback.** Product programs that exceed the term budget stay UNKNOWN, with the size recorded.

#### I27. UNDO rule and static deadness (about 3 days)

- **Goal.** Detect undo pairs, compute residues, classify them dead or live statically, and generate a law per residue.
- **Realizes.** §5.2, §10.6, Thm 6.9 bridge.
- **Deliverables.** `holon/rules/undo.py`, `holon/analysis/deadness.py`, and index-relative noninterference using the `set_d` and `nth_d` core lemmas.
- **Preregister.**
  - Predictions:
    - the detected pairs include (commit*, revertBatch);
    - the residues at LCI+1 are {CSR, BD, BVH, tag};
    - statically, CSR and BD are dead and BVH is live;
    - `L_undo_cancel` is derived only if a detection criterion fires; otherwise it is a back-test miss.
  - Regressions: the α-equivalents of `L_undo_CSR`, `L_undo_BD` and `L_undo_BVH` keep their outcomes.
- **Exit.** Static and kernel classifications agree, or the gate warns.
- **Risks and fallback.** A disagreement is a Surprise, and it blocks window/shadow generation.

#### I28. Deployment-history extraction, versioned machines, PAR-init (about 3 days)

- **Goal.**
  - Extract migrations instead of transcribing them.
  - Per-version machines with MIG edges.
  - PAR-init instances.
  - The D4 invariant.
  - Coverage of F12.5.
- **Realizes.** §10.1 deployment history, Def 4.3 S_k/A_k, §5.1 PAR-init. Closes V12.
- **Deliverables.**
  - `holon/frontends/solidity/history.py`. It reads reinitializer functions (`initialize2`/`3`/`4`, Rollup.sol:188/199/209) and `importGenesisBatch` (:226), and diffs solc `storageLayout` across the morph git tags `v0.4.6`..`v0.6.3`. Output: MIG edges and in-flight types.
  - The on-chain upgrade timeline is recorded as an assumption pending Q18.
  - `spec/M3/facts/morph_rollup.extracted.json` extends I20's extracted model. It is not a hand-written file.
  - `machine.py` emits `step_k` and `run_k`.
  - `holon/rules/par_init.py`.
  - G11V: in-flight sets are inhabited by concrete legacy states from the extracted migrations.
- **Preregister.**
  - Predictions:
    - O9 is REFUTED (a genesis header with a nonzero total is accepted);
    - D4 is PROVED by `reach_invariant` under the initialization-coherence premise, with scope stated;
    - the version-transition obligation covering F12.5 is REFUTED, or a rule-gap record is filed (never hand-written).
- **Exit.** Tests green. The O9 witness replays.
- **Risks and fallback.** The legacy staking contract is absent at `3e44e79`. The pre-cutover registry is a labelled stand-in oracle (Q12).

#### I29. NAT rule (about 2 to 3 days)

- **Goal.** Native equivalence (a), naturality (b) and composition coherence (c), over entry points × in-flight types and over reachable migration orders.
- **Realizes.** §5.3, Thm 6.7 use, §8.4.
- **Deliverables.** `holon/rules/nat.py` and `mproofs.{naturality_step, nat_entry}`.
- **Preregister.**
  - Predictions:
    - O14, O16 and O18 are REFUTED (η₄ before η₃ leaves D = 0);
    - O17 is REFUTED and classified benign;
    - naturality squares for unchanged entry points are PROVED.
  - Regressions: the O15 analogue is REFUTED.
- **Exit.** Every REFUTED witness replays.
- **Risks and fallback.** Laws needing missing induction stay UNKNOWN, with the failing per-action lemma named.

#### I30. Sorts III: nominal types, hole-free coercions, generated ghost tags (about 3 days)

- **Goal.** One Bend wrapper type per sort, typed affine operations, coercions without holes, generated ghost tags with a taint check, and per-read-site exactness laws.
- **Realizes.** §7.8, Thm 6.18, Prop 6.19, §5.6. Closes V3.
- **Deliverables.**
  - **Coercions without holes:**
    - `realize : SDur → Maybe Dur` returns `None` on a negative value, and the model reverts with Panic 0x11 on `None`, which is faithful to checked arithmetic. The obligation is the per-site law `∀s ∈ Reach_ℓ. is_some(realize(d_ℓ(s)))`.
    - `as_member : Tagged → Tag → Maybe σ`, with a per-read-site exactness law.
    - No `?` anywhere.
  - The sort section in the emitter, `mproofs.tag_exact`, a taint `FactsError`, `holon/rules/sort.py` and a term-size report.
  - Deletes the `tags_exact` lib def from M2+ models. The M1 model keeps its own copy, bound by `BINDINGS.json`.
- **Preregister.**
  - Predictions:
    - the exactness law at the recommit read in `commitState` (Rollup.sol:285, the path of the O26 witness) is REFUTED;
    - the one in `commitBatchWithProof` (:407) is also predicted REFUTED;
    - the delay-guard `reinterpret` law is REFUTED;
    - taint violations: 0;
    - every law stays under about 1,000 terms.
  - Regressions: the outcome of the `L_tag_BVH` analogue.
- **Exit.** Term-size report within budget. Tests green.
- **Risks and fallback.** On a term-size blowup, keep the I15 per-site form for the affected sites, labelled "untyped sort obligation".

#### I31. DISCH I: closure, blocking, external dependence (about 2 to 3 days)

- **Goal.** Enumerate guard conjuncts, compute Write*_X as a fixpoint over the extracted principal classes, and generate blocking and external-dependence laws.
- **Realizes.** §5.7, Thm 6.10, §11.5. Closes V13 (closure half).
- **Deliverables.** `holon/rules/disch.py`, `holon/analysis/closure.py`, and `x_closure` built on `perm_X`.
- **Preregister.**
  - Predictions:
    - Write*_sub excludes enq[P];
    - O31: the ∃-strategy laws for Y = active submitter (`proveState`) and Y = owner (`revertBatch`) are PROVED;
    - O32: the blocking invariant and `chain_revert` are PROVED.
  - Regressions: the `L_disch_stale` analogue is PROVED.
- **Exit.** Tests green. A canary that adds one non-X writer is rejected.
- **Risks and fallback.** An action whose enablement cannot be certified is excluded from X, and the exclusion is recorded.

#### I32. DISCH II: ∀-schedule profiles and classification (about 3 days)

- **Goal.**
  - Profile-point laws in the §8.4 form, ∃σ. ∀ schedule ≤ H. holds(σ), where the schedule quantifies over interleavings of other principals' actions. H is part of the generated statement and is fixed before results.
  - Pareto search.
  - Dominance laws.
  - Classification, including the persistent profile.
- **Realizes.** Def 6.20, Prop 6.21, §8.4, §10.7. Closes V13 and V23.
- **Deliverables.**
  - `holon/analysis/abstraction.py`, `holon/js/profile.mjs` and `holon/rules/disch_profile.py`.
  - A soundness law for the abstraction.
  - Proofs combine a strategy program with an enumeration of schedules up to H, or an invariant.
  - False points are shown by bounded dominance laws (∀ form).
  - Records carry `disch_class`.
- **Preregister.**
  - Predictions:
    - the pay and wait points in ∀-schedule form are PROVED for the H given in the prereg;
    - the bounded dominance law is PROVED;
    - the persistent profile is {(c_msg per trigger, 0), (0, Δ_fin per trigger)}, class mixed.
  - Regressions: the frontier {(c_msg, 0), (0, Δ_fin)}; (1000, 0) dominated, as already recorded in `docs/M1_REPORT.md` §2.1.
- **Exit.** Profile laws regenerate byte-identically.
- **Risks and fallback.** Exactness holds relative to the abstraction and H, and the records say so.
- **As built (`docs/iterations/I32.md`).** The predictions ran on the test milestone T32, M1's machine: the delay guard
  reads the L1 message queue, external on M3 until I36, and Q19 forbids hand-written facts there. The wait point is
  PROVED in the §8.4 form; the pay point is REFUTED (a permissionless commitBatchWithProof front-runs the submitter);
  the robust frontier is {(0, Δ_fin), (3 c_msg, 0)} at H = 2. The delay guard's M3 profile follows I36.

#### I33. Intent contracts and G10 (about 2 days)

- **Goal.** `@intended(rule, scope, L_weak)` contracts as frozen artifacts. L_weak is proved. Suppression applies only within scope. Contracts are re-proved on every change. Includes the volatile-view contract type that OWN needs.
- **Realizes.** §5.9, §5.8 exception, §9.3 G10.
- **Deliverables.**
  - `laws/CONTRACTS/<id>.json` and its registry, `holon/contracts.py`, G10, and a ghost counter for O12.
  - `intended_bounded` as a v2 `filter_bin` value. The frozen v1 `triage` enum lacks it, so v1 `triage` is untouched (Q4).
  - For M0/M1, G10 is listed under `not_applicable` with a reason (Q15).
- **Preregister.**
  - Predictions:
    - the O12 L_weak is PROVED (f_j ≤ commit_j + F + W·#challenges);
    - the `L_undo_cancel` analogue from I27 gets `filter_bin = intended_bounded`;
    - a facts change invalidates the contract until it is re-proved.
- **Exit.** G10 PASS on M3. M2+ milestones report G1–G11.
- **Risks and fallback.** A contract whose L_weak is UNKNOWN suppresses nothing.

#### I34. SYM rule: families, splits, both promotion routes, races, sentinels (about 3 days)

- **Goal.**
  - τ, ι, π and μ families admitted by sorts, with per-action equivariance laws.
  - Splits reported, and promoted only by route (i) (E1–E4 evidence or an intent contract) or route (ii) (an auditor adjudicates both "minority deviates" and "majority deviates").
  - Reorder pairs filtered by principal class and sink reachability.
  - **Disabling races classified separately.**
  - Sentinels.
- **Realizes.** §5.4, §10.8, Thm 6.6 use.
- **Deliverables.**
  - `holon/rules/sym.py`, `holon/sym_split.py`, `mproofs.equivariance` and `results/M3/sym/*.json`.
  - `audit/sym_adjudications/<split>.json` requests, answered in I45.
  - Race class `race_disabling`.
- **Preregister.**
  - Predictions:
    - O20's π split law is REFUTED;
    - O21 is REFUTED from a migrated legacy-queue state;
    - the D6 sentinels are PROVED;
    - no split is promoted without route (i) or (ii).
  - Regressions: the O19 analogue is REFUTED.
- **Exit.** Tests green.
- **Risks and fallback.** Equivariance needing missing arithmetic lemmas stays UNKNOWN, with the lemma named.

#### I35. OWN rule from extracted backing identities (about 2 days)

- **Goal.** Buffer carriers from I18's SSA backing identities, enumeration of views × writers, value-receiver copies, and the volatile-view exception through I33 contracts.
- **Realizes.** §5.8, §10.1 (slice headers).
- **Deliverables.**
  - `holon/rules/own.py`, `mproofs.heap_disjoint`.
  - The header-cache facts come from SSA extraction. The hand-written `morph_header_cache.json` of revision 1 is dropped.
- **Preregister.**
  - Predictions: O37 lost-write is REFUTED, with a Go replay.
  - Regressions: the O36 analogue is REFUTED.
- **Exit.** Go replays pass.
- **Risks and fallback.** A view whose alias set cannot be computed intraprocedurally is listed as coverage debt.

#### I36. Bundle I, extracted: messenger, queue, Merkle, accounting, cutover (about 3 days)

- **Goal.** Bring the messenger and queue fee rule, `Verify.sol`, `withdrawalRoots`, Amt-sorted ledgers and payable inputs into 𝔇 through the Solidity frontend, not by hand.
- **Realizes.** §11.1 scope, §7.5.
- **Deliverables.**
  - Extractor extensions, with loops handled as cost terms or debt.
  - `spec/M3/facts/morph_messenger.extracted.json`, `holon/sorts/conservation.py`, and a harness deploying the real messenger, queue and whitelist.
  - Split on 2026-10-23 (row I69): the extraction of the messenger, queue, whitelist and Submitter, their models, the linked machine and the harness deploying the real bundle are I69's (= I36a), under `gen/M3/bundle/`, `results/M3/bundle/` and `replay/M3/bundle/`; I36 (= I36b) adopts the head members' documents into M3's derivation, at `spec/M3/facts/morph_<member>.extracted.json`, when its laws need them; O13 and O20's economic half go to I70 (= I36c).
- **Preregister.**
  - Predictions:
    - O29 REFUTED;
    - O34 blocking PROVED, and the owner strategy PROVED;
    - D7 PROVED through injective pushing under CF (I25);
    - D9 PROVED;
    - O30 REFUTED;
    - D8 PROVED, with annotated exceptions;
    - O13 REFUTED (stand-in);
    - **O20 economic half**: a slash on a pre-cutover batch transfers zero, so the conservation or π law is REFUTED.
- **Exit.** Witnesses replay.
- **Risks and fallback.** Results that depend on the legacy staking contract carry the stand-in label (Q12).

#### I37. Bundle II, extracted: router, public input, HypC, calibrated cost (about 3 days)

- **Goal.** Model the verifier router and the public-input commitment, add circuit hypotheses as law pairs, and calibrate costs against forge gas.
- **Realizes.** §8.5 HypC, App. D cost, §5.7 self-controlled enabledness.
- **Deliverables.** Router facts (extracted), `PI = K(...)` with an uninterpreted `K`, cost expressions from I19's loop bounds, `En_G`, and `tools/calibrate_gas.py`.
- **Preregister.**
  - Predictions:
    - O3 REFUTED;
    - O23 REFUTED, with F(PI, parent lbn) = 64 bits;
    - calibrated costs within 5% of forge gas at backlog k ∈ {1, 2, 4, 8, 16, 32, 64};
    - O35: some submitter strategy with k ≤ 64 pushes `challengeState` out of `En_G`.
- **Exit.** Tests green.
- **Risks and fallback.** Above 5% error, the cost model is labelled "uncalibrated" and O35 stays UNKNOWN.

#### I38. Go codecs at loop granularity, compression oracle (about 3 days)

- **Goal.** Loop and array ops in facts 0.3, extracted, plus an uninterpreted zstd under **HypZ** in the §8.5 sense (∀x, k ≤ K. Dec(Enc x ++ 0^k) = x) and HypZ_len. Both are distinct from Hyp-Z0-kzg.
- **Realizes.** §10.1 Go pipelines, §8.5, App. D compression row.
- **Deliverables.** Extractor extensions, `spec/M3/facts/morph_blob_go.extracted.json`, Go replays.
- **Preregister.**
  - Predictions:
    - O4 REFUTED: index panic at element 3968, stated at the real blob size of 4096 elements;
    - O5 REFUTED twice (PAR-branch);
    - O6 REFUTED (PAR-recompute);
    - O28 REFUTED with 65,536 L1 messages through parametric counts;
    - D3 PROVED.
  - Regressions: D2 (checked since I3).
- **Exit.** Go replays pass.
- **Risks and fallback.** If the kernel cannot evaluate the real-size law within budget, the law is UNKNOWN with the bound recorded. The 3968 constant is never re-parametrized to a smaller N.

#### I39. Go derivation and product machine (about 3 days)

- **Goal.** `ParseBatch` as an extracted consumer, and a product machine that joins the Solidity commit with Go derivation.
- **Realizes.** §5.1 consumer and cycle, §5.5, F11.
- **Deliverables.** `spec/M3/facts/morph_derivation.extracted.json` (from I18 skeletons), the product construction, and a Go replay through `BatchInfo.ParseBatch`.
- **Preregister.**
  - Predictions:
    - O7 REFUTED (PAR-cycle);
    - **O8 as a law pair**: `L_O8@HypC_binds_trailing` PROVED and `L_O8@HypC_ignores_trailing` REFUTED, with `splits.json` reporting a split on HypC;
    - O24 REFUTED;
    - the F11 L1-count law REFUTED, with its missing O-id raised as a Question.
- **Exit.** Tests green.
- **Risks and fallback.** If the `node/` dependencies fail to download, these laws stay UNKNOWN and are reported.

#### I40. Refutation engines, App. D encodings, BMC, filter recomputation (about 3 days)

- **Goal.** Solver, fuzzer and BMC engines that commit to the Appendix D encodings, plus concretization, emitted per-witness tests, and recomputation of every filter bin.
- **Realizes.** §10.5, App. D, §10.2 (layouts as solver queries), §10.9, §9.6.
- **Deliverables.**
  - `holon/smt/{encode.py, run.py}` (pinned z3, `random_seed = 0`). Encodings:
    - keccak and sha256 as K(n, x) with ground injectivity over the query's own terms;
    - VH uninterpreted with ground injectivity, Z := VH(0), top byte 0x01;
    - the blob-hash vector as a dense prefix with top byte 0x01;
    - Enc and Dec under HypZ up to K;
    - time as non-decreasing;
    - checked arithmetic as a revert predicate, unchecked as bitvector wraparound;
    - cost as c0 + Σ c_ℓ·iters_ℓ against G.
  - Layout facts emitted as solver queries.
  - `holon/fuzz.py`.
  - `holon/bmc.py`: BMC over TRANS edges with environment moves and principal constraints.
  - `holon/gen/{foundry.py, gotest.py}`, replacing the hand op tables.
  - `holon/filter.py` final: bins recomputed from concretization plus replay. `known_limitation` only when BMC shows no public path within a recorded bound.
- **Preregister.**
  - Predictions:
    - SMT re-finds every existing REFUTED witness class;
    - per-law predictions for the UNKNOWNs left by I15 and I20;
    - per-record bin predictions after BMC are listed;
    - every solver candidate either passes its counter-law on the compiled model or is discarded.
- **Exit.** Emitted tests regenerate byte-identically. Every record's bin has been recomputed.
- **Risks and fallback.** Timeouts become UNKNOWN, with budget and reason.

#### I41. Untrusted prover intake (about 2 days)

- **Goal.** A path for agent-written proofs (§9.1, §10.4) that cannot touch statements. Waits for Q14c: AGENTS rule 4 says proofs come from generators.
- **Realizes.** §9.1 Provers → PROOF/, §9.2(3), §10.4.
- **Deliverables.**
  - `proofs/inbox/<law_id>/PROOF.bend`, accepted only for laws whose generators returned UNKNOWN, and only if:
    - G1 shows every law file unchanged;
    - the proof checks in every applicable kernel;
    - G3 is clean;
    - it stays within budget.
  - Records carry `prover: generator | agent:<session>`.
  - `tests_m3/test_intake.py`.
- **Preregister.**
  - Predictions: a fixture proof that edits its law file is rejected by G1; a valid fixture agent proof is accepted and labelled.
- **Exit.** Tests green.
- **Risks and fallback.** If Q14c says no, this iteration is skipped and recorded under Not done.

#### I42. Theory core I (about 3 days, research risk)

- **Goal.** Generic Graph, Walk and holonomy. Thm 6.4 ((iii) ⇒ (i) ⇒ (ii)), Cor 6.5, Lemma 6.2 and Thm 6.3. Instantiate `basis_sufficient_header` by application. Waits for Q14b, since these are hand-proved meta-theorems.
- **Realizes.** §6, §10.3, App. H `core/`.
- **Deliverables.** A `gen/core` law family, `holon/gen/basis.py`, `mproofs.congruence`.
- **Preregister.**
  - Predictions: the core laws are PROVED under bend and `--verdict` within budget; the header instantiation is PROVED; a canary that drops one cycle law is rejected.
- **Exit.** Tests green.
- **Risks and fallback.** On failure, records label basis sufficiency "paper proof only".

#### I43. Theory core II; Lean for the promoted set (about 3 days)

- **Goal.** The core forms of Thm 6.6 and 6.7 used by I29 and I34 (Lemma 6.12 already landed in I25). Lean emitters for the set Q8 promotes.
- **Realizes.** §6, §8.8.
- **Deliverables.** Core laws, and Lean noninterference and induction proofs (`rfl`, `simp`, induction; no `bv_decide`). Records gain I2.
- **Preregister.**
  - Predictions: the core laws are PROVED; the promoted set reaches cross-kernel agreement on every law.
- **Exit.** Tests green.
- **Risks and fallback.** A law that fails in Lean stays I1, labelled.

#### I44. Measures (all of Def 6.13), ranking (about 2 days)

- **Goal.** Compute every Def 6.13 measure and rank findings lexicographically.
- **Realizes.** Def 6.13, Thm 6.8, §10.10, §11.3 Impact column.
- **Deliverables.** `holon/measures.py`, `holon/rank.py`, `results/M3/ranking.json`, `spec/schemas/ranking.schema.json`.
- **Preregister.**
  - Predictions:
    - holonomy defect size of the `L_par_hdr_v2` analogue = 1 byte position (byte 0);
    - naturality defect mass of the η₂ obstruction = LCI − LFI on its witness state (the window indices whose CSR η₂ leaves zero);
    - F(Z, derivation) = 1 bit and F(PI, parent lbn) = 64 bits;
    - the `L_undo_BVH` liveness distance is 1, certified minimal under the stated bound;
    - the discharge profile comes from I32;
    - computed sink classes match the §11.3 Impact column, or each difference is explained.
- **Exit.** Ranking regenerates byte-identically. Every measure has a value or a bound.
- **Risks and fallback.** Uncertifiable measures are reported with their bounds.

#### I45. Audit loop, coordinator, rule gaps, rule admission, SYM route (ii) (about 3 days)

- **Goal.**
  - A1–A4 rounds by fresh auditors from another family.
  - Convergence after k clean rounds.
  - Rule-gap records, and the L7 admission rule for new rules.
  - SYM route (ii) adjudications.
  - A coordinator that renders `prompts/I<n>_*.md` and `docs/STATUS.md`.
- **Realizes.** §9.1 coordinator, §9.2(6), §9.5, §5.4 (ii), L7, L19.
- **Deliverables.**
  - `audit/` prompts and `rounds/M3/*.json`.
  - `holon/audit/{rounds, hostile, vacuity, oracles, converge}.py`.
  - `holon/coordinator.py`.
  - `audit/rule_gaps.jsonl`. A new rule is admitted only with at least two instances, a basis argument and human approval.
  - Answers to the I34 adjudication requests, and A4 adjudication of the I25 evidence reviews.
- **Preregister.**
  - Predictions: k = 3; the A2 round re-finds the O4 class; the A4 round flags no degenerate inhabitant.
- **Exit.** `results/M3/audit_status.json` reports `converged = true` (3 consecutive rounds with no high-priority finding). Listing open findings does not satisfy this exit, and M3 exit requires convergence.
- **Risks and fallback.** Same-family rounds (Q9) are labelled and do not count toward convergence.

#### I46. Blind rerun from code, and generated comparison (about 3 days)

- **Milestone.** **Closes the M3 exit.**
- **Goal.** A fresh session regenerates everything from code, with no access to the case study, and a comparison table is generated against §11.8 and F1–F14.
- **Realizes.** §11.7, §11.8, L8, §15.2 M3.
- **Protocol.**
  - **The sealed bundle contains:** the pinned target code; HOLON tooling (extractors, rules, generators, gate) at a fixed commit; and the whitepaper with §2, §11, Appendix A, Appendix B and every "Morph instances" list removed.
  - **It excludes:** `facts/`, `spec/`, `laws/`, `gen/`, `results/`, `replay/`, `docs/`, `prompts/`, the `maps_to` sidecars, and `spec/M1/policy_hints.mjs`.
  - The blind session runs extract → derive → run → replay.
- **Deliverables.** `tools/blind_pack.py`, `audit/blind/<round>/`, `holon/report.py` writing `docs/M3_COMPARISON.md` (covered by G1), `spec/M3/appendixA_map.json`.
- **Preregister.**
  - Thresholds: `blind_agreement ≥ 0.90` on the statuses of α-equivalent statements, with the matched-statement fraction reported.
  - Predictions: each mechanized law's blind outcome equals its mechanized outcome; every F-id gets a cell, and "not mechanized" is allowed.
- **Exit.** The comparison is generated deterministically and `blind_agreement` meets the threshold.
- **Risks and fallback.** The tooling was developed on Morph, so contamination remains, and the comparison states this. The M4 held-out target is the real control. Disagreements are findings about the pipeline, never reconciled by hand.

---

### M4: held-out target and the §13 protocol

**M4 exit criterion:** the §13 protocol run against the baselines. Tests live in `tests_m4/`.

#### I47. Target-agnostic factory, parallel checking, performance loop, drift trigger (about 3 days)

- **Goal.**
  - Move target specifics into `targets/<name>/`.
  - Parallel per-law work with deterministic merge.
  - The §9.2(7) performance loop with veto.
  - **The L22 drift trigger.**
- **Deliverables.**
  - `targets/morph/target.json`.
  - `ProcessPoolExecutor` in the pipelines and the gate.
  - `tools/perf_loop.py`.
  - `python -m holon drift --target morph`: `git ls-remote` against the pinned version; on change, re-extract, compute the stale closure, and record the `stale_closure_latency` metric.
  - A toy second target.
- **Preregister.**
  - Predictions: the toy target runs with zero edits to `holon/`; the M1 gate is at least 2× faster with 4 workers; outputs are byte-identical to the sequential run; a simulated new tag triggers re-extraction and marks exactly the predicted stale set.
- **Exit.** Tests green.
- **Risks and fallback.** No GPU; the CPU substitute is stated.

#### I48. Evaluation corpus and unsolved controls (about 2 to 3 days)

- **Goal.**
  - `spec/eval/corpus.json`: public defects with pre-fix and fix commits obtained through `git clone`, minimal rule labels from two labellers, and isomorphic renaming.
  - `spec/eval/controls.json`: planted true and false obligations with known ground truth, sized beyond the budgets, for UNKNOWN calibration (L15).
- **Preregister.**
  - Thresholds: corpus size N (proposed 20 defects across at least 3 systems; Q20); the inter-rater agreement target (reported, not asserted); the size of the control set.
- **Exit.** The manifests validate with at least N doubly labelled entries, and the renaming tool round-trips.
- **Risks and fallback.** Same-family labellers are labelled as such.

#### I49 / I50. Held-out target (about 3 + 3 days)

- **Goal.**
  - I49: extraction, facts and diagram for the target the human sealed (Q7).
  - I50: rules, run, replay, metrics.
- **Preregister.** Frozen after extraction and before any rule runs: per-rule obligation counts and expected rule classes.
- **Exit.** All gates green on the target. Replay results recorded. Obligation counts against \|E\| and \|V\| are reported across the four diagrams (toy, Morph M2, Morph M3, held-out), with no linearity claim from one target.
- **Risks and fallback.** An unsealed target is labelled, with a contamination caveat.

#### I51. HOLON on corpus pre-fix commits (about 3 days)

- **Goal.** Run extraction, rules, replay and filtering on every corpus pre-fix commit, then compute per-rule recall and precision (true defects, intended asymmetries, model defects).
- **Preregister.** Predictions: expected detections per corpus entry, written before any run.
- **Exit.** `results/eval/holon/corpus.json` has a row for every entry, with "not run" only for extraction failures that carry a reason.
- **Risks and fallback.** Extraction gaps on foreign codebases are counted as misses, not excluded.

#### I52. Baselines on Morph, corpus and held-out target (about 3 days)

- **Goal.** Pinned slither, echidna, medusa, hevm and halmos (installed to `~/.holon/tools`), plus Go fuzzing, 2-cycle round-trip testing, frequency-based spec mining and agent-only review. All at equal budget, reported in a common findings schema, run on Morph, the corpus pre-fix commits and the held-out target.
- **Preregister.** Predictions: per-baseline expected detections, written before any baseline runs. For example, 2-cycle testing finds the O1/O2 class; single-component analyzers find no relational obstruction.
- **Exit.** `results/eval/<system>/<baseline>.json` exists for all three systems.
- **Risks and fallback.** A baseline that cannot be installed is recorded as missing, never substituted silently.

#### I53. Ablations, UNKNOWN calibration, §13 metrics (about 2 days)

- **Milestone.** **Closes the M4 exit.**
- **Goal.**
  - All nine §13 ablations: no sorts-as-types, no writer provenance, no evidence calculus, 2-cycles instead of fundamental cycles, **no native-equivalence NAT**, no enablement in DISCH, no replay, single kernel, and no frozen statements (weakening rate measured by A3 in a sandbox).
  - UNKNOWN calibration on the I48 controls.
  - Every §13 metric, with deltas against the baselines.
- **Exit.** `results/eval/ablations.json` and `docs/M4_EVAL.md` are generated, and every ablation has run, since every component exists by then. An ablation that has not run means M4 exit is not met.

---

### M5: intent lane, games, environment

**M5 exit criterion:** the L6, L9 and L10 metrics are reported. Tests live in `tests_m5/`.

#### I54. L6, L9 and L10 definitions, preregistered (about 1 day)

- **Goal.** The whitepaper gives "—" for L6 and L9. The human approves definitions (Q11), and they are preregistered in `spec/M5/preregistration.json` **before** the work they measure.
- **Exit.** The definitions are committed, with a computation stub and tests on fixtures.

#### I55. Intent lane (about 3 days)

- **Goal.**
  - `holon/intent/atomize.py` turns NatSpec and docs into records with exact source spans.
  - Reviewed clauses compile to `laws/INTENT/`.
  - A refuted intent law is an intent obstruction.
  - Intent feeds SYM route (i).
- **Preregister.** The clause count and the expected intent obstructions, O10 doc-drift items included.
- **Exit.** L10 is computed by the I54 definition.
- **Risks and fallback.** Unreviewed clauses cannot produce findings.

#### I56. Bounded games (about 3 days)

- **Goal.** Payoff facts, strategies as checked programs quantified over all schedules up to H, and DISCH-econ laws.
- **Preregister.** O25/N3: a rational recommitter refuses (the economic reading of the I26 attribution law). The economic reading of O35.
- **Exit.** L6 is computed by the I54 definition.
- **Risks and fallback.** Rationality assumptions are premises in the frozen statements.

#### I57. Environment modules (about 3 days)

- **Goal.** L1 reorg depth, the blob retention window and fetcher modules, with time-indexed FACT and UNDO laws.
- **Preregister.** Which existing laws change outcome under retention and reorg.
- **Exit.** L9 is computed by the I54 definition.
- **Risks and fallback.** Module parameters are premises, not facts about mainnet.

#### I58. M5 report (about 1 day)

- **Milestone.** **Closes the M5 exit.**
- **Exit.** `metrics.json` reports L6, L9 and L10 as measured, and `docs/M5_REPORT.md` is generated.

---

## 5. Deferred / research questions

1. **Basis sufficiency at scale.** BendTT cost grows superlinearly above about 1,000 terms per law. Can Thm 6.4 be instantiated by application for diagrams with hundreds of edges? This is the fallback label in I42.
2. **Independence class I2 still shares the facts and the extractor.** Should independence classes record shared upstream inputs?
3. **Transfer between abstractions.** Do laws proved on a window/shadow view transfer to raw storage families? That needs a bisimulation law (I20, I27).
4. **DISCH exactness beyond bounded H and the abstraction.**
5. **Sorts-as-types term size** for the full bundle (I30).
6. **Calldata-only historical windows** for refinement of blob edges.
7. **GPU refutation (R5).** Not possible here; whether 4-core native enumeration suffices at M3 scale is open.
8. **Non-straight-line extraction.** Loops with storage writes, callbacks and goroutines stay coverage debt, or need human-approved hand-written waivers (Q19).
9. **Equivalent mutants.** Adjudication is manual and blind to outcomes (I22). An automated detector would reduce subjectivity.
10. **Frequency-free SYM promotion.** The split adjudication rate (L11) is unknown until I34 and I45.
11. **Lexical sort seeds.** Measured through `unresolved`, not assumed.
12. **Intent-lane review cost.**
13. **Games.** Whether ordinal payoffs say anything robust about O25 and O35.
14. **Cross-language linking equations** that the code does not imply can only be surfaced as assumptions.
15. **Blind rerun on the development target.** The tooling was tuned on Morph. How much does I46 measure discovery, rather than pipeline determinism?
16. **Agent proofs vs AGENTS rule 4** (I41, Q14c). Whether untrusted provers add value beyond per-class generators.
17. **Lean on large byte layouts.** `rfl` on 257-element lists needs a raised `maxRecDepth`. Whether per-cell lemmas scale to 131,072-byte blobs is open.

---

## 6. Questions for the human

1. **Freezing.** *Answered: yes, by the human (steps in docs/HUMAN_ANSWERS.md).*  *Needed before:* nothing blocks on it, but every protection stays self-certified until it is answered.
   - Please add to `FROZEN.sha256`: `laws/M1/` (including `REGISTRY.json` and `BINDINGS.json`), `spec/M1/predictions.json`, `spec/M1/mutations.json`, `tests_m1/` and `whitepaper.md`.
   - Please consider extending `FROZEN_ROOTS` in `tools/freeze.py` to cover `laws/M*`, `spec/M*/predictions.json`, `spec/M*/preregistration.json`, `spec/schemas/`, `tests_m*`, `holon/audit/prereg.py`, `holon/statement_diff.py`, `keys/` and later `laws/CONTRACTS`.
2. **M1 adjudication.**
   - (a) `L_tag_BVH` wording: the agent appended "either direction" after the search found v1→v2, and §11.8 says v2→v1. Please adjudicate. Also: should M1 be re-baselined on §11.8's 10 rows rather than the agent's 14-entry expansion?
   - (b) Does `go test` satisfy M1's "replays as a Foundry test" for the Go-only `L_own_txspayload`?
3. **Signing.** A gpg key under a frozen `keys/`. Without one, weakening is rejected. Re-extraction and strengthening do not need it.
4. **Schemas.** *Answered 2026-10-13 (delegated to the lead): yes, at I33's adoption step after I41; the human runs the freeze; see docs/HUMAN_ANSWERS.md.*  Should `result_record_v2` and `law_ir_0_3` be adopted into the frozen `schemas/`? That includes `filter_bin` values such as `intended_bounded`, `kernels[]`, `scope{kind,H}`, `refinement_refs`, `coverage` and the INTENT rule. *Needed before:* I33's adoption step.
5. **M2 historical window.** *Answered 2026-10-12: an unconditional yes for every source and the full window; see docs/HUMAN_ANSWERS.md.*  Choose one: a snapshot from `tools/fetch_historical.py`, BigQuery credentials, or allow-listing one RPC host and one blob archive. Also: which block window, and is calldata-only acceptable?
6. **Mutation-adequacy threshold.** *Answered: 0.80.*  Confirm or replace the proposed 0.80 of non-equivalent mutants in scope, sign off the operator catalog, and adjudicate equivalent mutants from the diffs before any run. *Needed before:* I22's prereg commit.
7. **Held-out target.** *Answered: ScrollChain, sealed in spec/heldout/target.json.*  Choose and seal it (for example Scroll's ScrollChain at a pinned commit, or a bridge). Is a public, clonable repo acceptable? *Needed before:* I49.
8. **G7 promotion.** *Answered 2026-10-13 (delegated to the lead): every PROVED law; see docs/HUMAN_ANSWERS.md.*  All PROVED laws, or a promoted subset? *Needed before:* I43.
9. **Auditor family.** *Answered: the default stands (same-family, labelled).*  Is another model family available for audits and the blind rerun? If not, may same-family rounds count toward convergence? *Needed before:* I5.
10. **Observation boundary for Thm 6.9.** *Answered 2026-10-14 (delegated to the lead): public view getters count as observations; the transaction-outcome-only boundary may be reported alongside; see docs/HUMAN_ANSWERS.md.*  Do public view getters count as observations? `L_undo_CSR`'s status depends on the answer; both boundaries can be run and reported.
11. **L6 and L9 definitions.** *Answered 2026-10-13 (delegated to the lead): target-agnostic, ground-truth-measured, preregistered in I54; see docs/HUMAN_ANSWERS.md.*  *Needed before:* I54.
12. **Legacy registry.** *Answered 2026-10-13 (delegated to the lead): fetch the real code; a labelled stand-in only as a last resort; see docs/HUMAN_ANSWERS.md.*  Is a labelled stand-in acceptable for O13 and O14, or should historical bytecode be fetched?
13. **Whitepaper inconsistencies.** Should I record these as errata, and treat `whitepaper.md` as frozen preregistration?
    - O18 cites "A15", which is not defined.
    - F12.5 and F11's "L1 counts discarded" have no O-id.
    - §11.7 claims "all of F1–F14" reproduced.
    - §8.6 lists "split" as a status, which conflicts with AGENTS rule 6; this plan uses law pairs.
    - §8.8 recommends `bv_decide`, which adds an axiom (verified in Lean 4.34.0) and so conflicts with §8.5.
    - `whitepaper.md` was committed at `9ffdf77`, after M1. Can you confirm that §11.8 predates M1, for example from the zip's timestamp?
    - Also, outside the whitepaper: `docs/M1_REPORT.md:108` calls the D2 check "HypZ" and cites Rollup.sol:24 (the constant is at :25).
14. **AGENTS rule 4.** *Answered: (b) and (c) yes.*  Are these acceptable as "proofs come from generators"?
    - (a) A core lemma library emitted by `holon/gen/core.py` from a reviewed catalog. *Needed before:* I8.
    - (b) Hand-proved meta-theorems (Thm 6.4, 6.6, 6.7). *Needed before:* I42.
    - (c) Agent-written proofs through an intake, as §10.4 envisions. *Needed before:* I41.
15. **Gate semantics.** Is it acceptable to add new check keys (G6, G9, G11V, GEVID, G8, G10), and to list checks that do not apply to M0/M1 under a top-level `not_applicable` key rather than reporting a vacuous pass?
16. **Installs and upstream.** *Answered: installs yes.* 
    - May `tools/setup_env.sh` install pinned z3-solver, slither-analyzer, hevm, echidna, medusa and halmos into `~/.holon/tools`?
    - Will you file the bend2/BendTT mismatch reproducer (`replay/M1/kernel_mismatch/`) upstream?
    - Do you want CI and branch protection?
17. **Budget.** The plan implies about 23 sessions for M2, 23 for M3, 7 for M4 and 5 for M5.
18. **Deployment history.** *Answered 2026-10-13 (delegated to the lead): both, code-derived as the model and the on-chain timeline as an independent check; see docs/HUMAN_ANSWERS.md.*  The on-chain upgrade timeline needs RPC. Is code-derived history (reinitializers plus storage-layout diffs across git tags) acceptable for M3's migrations? *Needed before:* I28.
19. **M3 hand-written facts.** *Answered 2026-10-13 (delegated to the lead): extracted facts for every M3 law; a per-item waiver only where no extractor reaches, never where an extracted document exists; see docs/HUMAN_ANSWERS.md.*  For components the extractors cannot reach, may a hand-written fact be used under a per-item waiver, flagged in coverage? Without waivers, those components stay coverage debt.
20. **Corpus size.** *Answered: N = 20.*  Confirm N = 20 defects across at least 3 systems, or set another N. *Needed before:* I48.

---

## 7. Critique responses

Every point was checked against the tree, the whitepaper, `/root/work/morph` at `3e44e79`, or a local probe. All are accepted except the partial rejections and corrections below.

**Partially rejected or corrected (one line each)**
- *"Catalog and generator versions never enter the hash" (missing #4):* partly rejected. `rule_catalog_version` now enters the 0.3 hash (I7), but generator source does not, because hashing it would unfreeze every statement on refactors that emit identical statements; generator identity is bound by G1 reproduction and `BINDINGS.json` instead (I2).
- *"I3 assigns witness_provenance before BMC" (missing #16, misordered #3):* partly rejected. Provenance describes how an existing replay ran and needs no BMC; only `filter_bin` depends on concretization, and it is now provisional until I40 recomputes it.
- *"Rollup.sol:269"* (inaccurate #7): accepted with a correction. The `commitBatch` call is at :268.
- *"Line 913 is the keccak aggregate write"* (inaccurate #8): accepted with a correction. The aggregate keccak is at :910 and :913 is the `_blobCount > 0` require; neither is a recommit read.
- *"L_own_txspayload replays only through go test" (inaccurate #1):* accepted as a gap in the letter, but not treated as a defect, since Foundry cannot run Go code. Left to the human (Q2b).

**Accepted, and where each point landed**

*Missing.*
- Lossy fragment → I25.
- PAR recompute, branch, totality, weak, consumer and cycle generators → I24.
- §8.6 refinement and coverage fields → I1, I16, I19.
- Refs by hash → I2, I7.
- Prover intake and enforcement → I10, I41, Q14c.
- Non-vacuity beyond I2 → I3, I7, I8, I12, I28.
- §13 corpus runs, controls and the NAT ablation → I48, I51, I52, I53.
- §10.1 extraction items → I18, I19, I28, I35–I39, §2.3.
- hevm, L7, L22 and checker upgrade → I20, I45, I47, I3.
- SYM route (ii), races and the volatile-view exception → I34, I45, I33, I35.
- DISCH ∀-schedule → I32.
- Principal classes → I11, I19, I31.
- L2 predeploys and the sealing loop → I12.
- O25, O20 economic half and F12.5 → I26, I36, I28.
- Unlisted M0/M1 debts → D-f, D-g and D-e(3) in §1.1; I4, I5, I1.
- Bins after BMC → I40.
- All Def 6.13 measures → I44.
- Appendix D encodings and layout solver queries → I40.

*Misordered.*
- I4 before the binding → bindings now come first (I2 before I6).
- A1 needs the Go extractor → I22 depends on I18.
- Filter before BMC → provisional bins in I4, recomputed in I40.
- Q3 blocking M2/M3 → the re-extraction channel plus per-def refs (I7, I10).
- Core and meta-theorems before Q14 → §0.3 gating.
- Q6 after the run → I22 waits for Q6.
- Vacuous E5 prediction → sorts (I13) before evidence (I14).
- L6/L9 defined after use → I54 first.
- M3 regressing to transcription → I28 and I35–I39 extend the extractors.
- Blind-rerun contamination → I46 protocol.
- Parametric hashes too late → I12, before I15.
- I34's dependencies → I33 depends on I27, plus Q4.
- tags_exact contradiction → I6 moves it, I30 deletes it.
- Baselines only on Morph → I52 after I50, on all three systems.
- First audit too late → I5 and I21.
- G11V never revisited → extended in I7, I8, I12 and I28.

*Unverifiable.*
- Prereg holes → §0.1 (outcome paths, immutability, tests-first, no skip, self-certification stated).
- Restated outcomes → separate `regressions` arrays everywhere.
- Labelling loophole → mechanical classes (I16).
- A1 kill and denominator → I22.
- G9 and ledger completeness → I1.
- I4 tautology → byte-identity (I6).
- "Tests green" exits → tests-first rule (§0.1), plus mechanical exits in I24, I45, I46, I48 and I53.
- Quarantine and companion statement → I3.
- "Weakening impossible" → I10, invariant 11.
- I9 cap and section mapping → I11.
- Metrics timing → I16.
- Unclear exits → I20, I32, I37, I49/I50.
- G1–G11 on M0/M1 → invariant 10, I33, Q15.
- ∃ fixture semantics → I7.

*Inaccurate.*
- M0/M1 by the letter → §1.1.
- L_tag_BVH and L_fact_Z replay → §1.1, D-f, I4.
- Commit history and 10 rows → D-a, I10.
- render_term and ir.premises → I1.
- Replay stamps → I1.
- DISCH s* → I3.
- One :363 site → I13, I15.
- Recommit lines → I30.
- HypZ naming and :25 → D-e, V20, I1, I3, I38.
- D2 "partial" → §1.2.
- MACH-E → removed from I38.
- I13 v2 refinement → I16.
- SORT row → §1.2.
- Appendix A count → §1.2, I4.
- REGISTRY unfrozen → I10, invariant 11.

*AGENTS risks.*
- ∃ counter-laws → I7, invariant 12.
- SPLIT status → law pairs (I7, I12, I39).
- bv_decide axiom → I9, invariant 5 (verified locally).
- Core LAWS import and gen-dir → I8.
- NONVAC single file → I3 (`nonvac/` subdirectory).
- Holes in realize and as_member → I30.
- Weakening through new ids → `cross_milestone` kind (I10), invariant 7.
- O4 at reduced N → I38.
- Lib moves outside the hash, and the mismatch table → I2, I6.
- M3 hand-written facts → §2.3, Q19.
- Frozen-test conflicts → invariant 10, I1, I14, I33.
- Agent-writable tamper protection → invariant 11, Q1.
- prompts/ files → §0.2.
- Rule 4 vs §10.4 and meta-theorems → Q14a–c, I41, I42.
- Hygiene in vendored trees → invariant 8, I18.
- Prereg test skipping → §0.1 item 4.