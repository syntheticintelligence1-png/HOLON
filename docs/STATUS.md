# HOLON status

Rendered by `python -m holon coordinator status` (holon/coordinator.py, I87) from every `spec/M*/predictions.json`, `prompts/`, `docs/iterations/` and `results/M*/audit_status.json`. Do not edit it: edit those and re-render. `--check` fails on any difference, so whoever merges a new key, prompt, report or audit status re-renders it.

## Milestones

| Milestone | Keys | Predictions | Regressions | Reports |
|---|---|---|---|---|
| M2 | 27 | 242 | 126 | 27 |
| M3 | 24 | 154 | 129 | 24 |
| M4 | 1 | 4 | 6 | 1 |

## Audit loop (whitepaper §9.5; results/<M>/audit_status.json)

| Milestone | Converged | Streak | k | Counted rounds | Rounds | Open high findings | Why |
|---|---|---|---|---|---|---|---|
| M3 | no | 0 | 3 | 0 | 1 | none | not converged: the streak is 0 counted clean round(s), k is 3; no round counts: none is a qualifying round from another model family (Q9: same-family and dry-run rounds are labelled and never counted) |

## Iterations

| Key | Milestone | Title | Prompt | Predictions | Regressions | Tests | Report |
|---|---|---|---|---|---|---|---|
| I1 | M2 | Prereg tool, honest ledger, v2 records, G1 over records, G6/G9 | `prompts/I1_ledger.md` | 5 | 3 | 6 | `docs/iterations/I1.md` |
| I2 | M2 | Semantic bindings and dependency index | `prompts/I2_bindings.md` | 5 | 1 | 1 | `docs/iterations/I2.md` |
| I3 | M2 | Non-vacuity (G11V), D2 zero-blob check, checker pin and upgrade procedure | `prompts/I3_nonvacuity_pins.md` | 4 | 3 | 3 | `docs/iterations/I3.md` |
| I4 | M2 | Replay completion, provisional finding filter, case-study coverage | `prompts/I4_replay_filter_casestudy.md` | 7 | 2 | 3 | `docs/iterations/I4.md` |
| I5 | M2 | First audit round on M0/M1 | `prompts/I5_audit.md` | 2 | 1 | 1 | `docs/iterations/I5.md` |
| I6 | M2 | Target-agnostic generators, byte-identical | `prompts/I6_target_agnostic.md` | 4 | 1 | 1 | `docs/iterations/I6.md` |
| I7 | M2 | IR 0.3 | `prompts/I7_ir03.md` | 5 | 1 | 1 | `docs/iterations/I7.md` |
| I8 | M2 | Core library and Reach | `prompts/I8_core_reach.md` | 6 | 2 | 1 | `docs/iterations/I8.md` |
| I9 | M2 | Lean second kernel for M0 | `prompts/I9_lean_kernel.md` | 4 | 1 | 1 | `docs/iterations/I9.md` |
| I10 | M2 | Statement lifecycle, A3, prover separation | `prompts/I10_lifecycle.md` | 4 | 6 | 3 | `docs/iterations/I10.md` |
| I11 | M2 | Diagram 𝔇 and principal classes | `prompts/I11_diagram.md` | 4 | 1 | 1 | `docs/iterations/I11.md` |
| I12 | M2 | Hashes and oracles as parameters | `prompts/I12_oracles.md` | 3 | 4 | 1 | `docs/iterations/I12.md` |
| I13 | M2 | Sorts I: grammar, constraints, union-find, unsat cores, frozen assignment | `prompts/I13_sorts.md` | 6 | 4 | 4 | `docs/iterations/I13.md` |
| I14 | M2 | Evidence calculus (E1-E6) and frozen evidence set | `prompts/I14_evidence.md` | 18 | 5 | 4 | `docs/iterations/I14.md` |
| I15 | M2 | Sorts II: per-site SORT laws and the rules registry (the first generated M2 laws) | `prompts/I15_sort_sites.md` | 6 | 13 | 2 | `docs/iterations/I15.md` |
| I16 | M2 | Native C model, per-edge corpus, refinement records, metrics | `prompts/I16_native_refinement.md` | 10 | 4 | 3 | `docs/iterations/I16.md` |
| I17 | M2 | Solidity frontend I: compile, AST/Yul walk, layouts (holon-facts/0.3) | `prompts/I17_solidity_layout.md` | 16 | 5 | 4 | `docs/iterations/I17.md` |
| I18 | M2 | Go frontend: codecs, partiality, slice headers, pipelines, loop bounds | `prompts/I18_go_frontend.md` | 14 | 9 | 3 | `docs/iterations/I18.md` |
| I19 | M2 | Solidity frontend II: storage, transitions, cost terms, principals, linking, G8 | `prompts/I19_solidity_transitions.md` | 8 | 5 | 2 | `docs/iterations/I19.md` |
| I20 | M2 | Extracted rollup model: refinement, width, optional hevm | `prompts/I20_extracted_model.md` | 7 | 2 | 1 | `docs/iterations/I20.md` |
| I21 | M2 | A2/A4 audit round on extraction (audit round M2/2) | `prompts/I21_audit_extraction.md` | 15 | 6 | 1 | `docs/iterations/I21.md` |
| I22 | M2 | A1 mutation adequacy on real code | `prompts/I22_mutation_adequacy.md` | 14 | 6 | 1 | `docs/iterations/I22.md` |
| I23 | M2 | Historical inputs and M2 exit evaluation | `prompts/I23_historical_exit.md` | 13 | 5 | 1 | `docs/iterations/I23.md` |
| I24 | M3 | Rules engine and PAR, all sub-forms, over the extracted documents (the first M3 laws) | `prompts/I24_par.md` | 7 | 9 | 2 | `docs/iterations/I24.md` |
| I25 | M3 | PAR-lossy and injective pushing over the frozen evidence set: the Def 4.4 fragment, the evidenced lossy elements, Lemma… | `prompts/I25_par_lossy.md` | 10 | 7 | 1 | `docs/iterations/I25.md` |
| I26 | M3 | FACT rule, attribution (O25) and F(m, c), decided on the extracted real code | `prompts/I26_fact.md` | 9 | 4 | 1 | `docs/iterations/I26.md` |
| I27 | M3 | UNDO rule and static deadness, decided on the extracted real code | `prompts/I27_undo.md` | 11 | 5 | 1 | `docs/iterations/I27.md` |
| I28 | M3 | I28 (the laws half; I63 = I28a holds the history half): versioned machines over the extracted deployment history (one e… | `prompts/I28_versions.md` | 6 | 2 | 1 | `docs/iterations/I28.md` |
| I30 | M3 | Sorts III: nominal types, hole-free coercions, generated ghost tags | `prompts/I30_typed_sorts.md` | 8 | 6 | 1 | `docs/iterations/I30.md` |
| I31 | M3 | DISCH I: guard conjuncts, the enableable write closure over the extracted principal classes, blocking and external depe… | `prompts/I31_disch.md` | 12 | 3 | 1 | `docs/iterations/I31.md` |
| I32 | M3 | DISCH II: discharge profiles in the §8.4 form, Pareto search, bounded dominance and classification (test milestone T32:… | `prompts/I32_disch_profile.md` | 5 | 2 | 1 | `docs/iterations/I32.md` |
| I40 | M3 | Refutation engines, Appendix D encodings, BMC over the extracted TRANS edges, concretization, emitted tests and the fin… | `prompts/I40_refute.md` | 11 | 5 | 1 | `docs/iterations/I40.md` |
| I41 | M3 | Untrusted prover intake | `prompts/I41_prover_intake.md` | 9 | 3 | 1 | `docs/iterations/I41.md` |
| I42 | M3 | Theory core I: generic graphs, walks and holonomy with Lemma 6.2, Thm 6.3, Thm 6.4 and Cor 6.5 kernel-checked in Lean i… | `prompts/I42_theory_core.md` | 4 | 9 | 1 | `docs/iterations/I42.md` |
| I43 | M3 | Theory core II and Lean for the promoted set: Thm 6.6 (symmetries: identity, composition, inverses, the submonoid of pa… | `prompts/I43_theory_core2_lean.md` | 3 | 12 | 2 | `docs/iterations/I43.md` |
| I48 | M4 | Evaluation corpus and unsolved controls: 20 public defects across six fixed systems (two rollups, four beyond), collect… | `prompts/I48_eval_corpus.md` | 4 | 6 | 1 | `docs/iterations/I48.md` |
| I59 | M2 | I23a track: historical on-chain acquisition and the first per-edge replay on real inputs (human answer Q5) | `prompts/I59_historical.md` | 9 | 2 | 1 | `docs/iterations/I59.md` |
| I60 | M2 | A1 mutation adequacy on real code, replacement catalog | `prompts/I60_mutation_replacement.md` | 20 | 10 | 1 | `docs/iterations/I60.md` |
| I61 | M2 | A1 mutation adequacy on real code, second replacement catalog | `prompts/I61_mutation_second_replacement.md` | 24 | 11 | 1 | `docs/iterations/I61.md` |
| I62 | M2 | A1 mutation adequacy on real code, the rerun of I61's catalog with I61's defects fixed | `prompts/I62_mutation_rerun.md` | 9 | 13 | 1 | `docs/iterations/I62.md` |
| I63 | M3 | = I28a: deployment history from the code (versions, reinitializers, storage-layout diffs and MIG edges over every tag o… | `prompts/I63_history.md` | 5 | 3 | 1 | `docs/iterations/I63.md` |
| I64 | M3 | = I33a: intent contracts (format, registry, derivation of L_weak, the run's marking), G10, intended_bounded in the v2 r… | `prompts/I64_contracts.md` | 4 | 3 | 1 | `docs/iterations/I64.md` |
| I65 | M3 | = I33b: the O12 intent contract on M2's window view of the extracted Rollup: a ghost counter (IR 0.3 term), the proof c… | `prompts/I65_o12_view.md` | 4 | 4 | 1 | `docs/iterations/I65.md` |
| I66 | M3 | holon differential's window view in M2's evidence set (Q62): its diagram by I11's adapters and its E2, E3, E4 and E6 at… | `prompts/I66_view_evidence.md` | 1 | 5 | 1 | `docs/iterations/I66.md` |
| I67 | M3 | I67 (= I38a): Go codecs at loop granularity (holon-go-frontend/0.2 loop bodies), Go-op components over interface carrie… | `prompts/I67_go_loop.md` | 5 | 5 | 1 | `docs/iterations/I67.md` |
| I69 | M3 | = I36a: Bundle I's extraction and acquisition, no laws: the message queue, the messenger, the whitelist and the Submitt… | `prompts/I69_bundle_extraction.md` | 7 | 5 | 1 | `docs/iterations/I69.md` |
| I72 | M3 | E2 over the adopted holon-facts/0.3 transitions documents (I33's evidence key): written-via-p, read-via-q atoms from th… | `prompts/I72_e2_transitions.md` | 1 | 5 | 1 | `docs/iterations/I72.md` |
| I80 | M3 | = I37a: Bundle II's extraction and acquisition, no laws: the verifier router (MultipleVersionRollupVerifier) extracted … | `prompts/I80_bundle2_extraction.md` | 6 | 4 | 1 | `docs/iterations/I80.md` |
| I81 | M3 | I81 (= I44a): Def 6.13's measures (holon/measures.py, one interface over PAR's holonomy defect size, NAT's naturality d… | `prompts/I81_measures_ranking.md` | 7 | 7 | 1 | `docs/iterations/I81.md` |
| I82 | M3 | I82 (= I46a): the blind pack, the comparison generator and the agreement metric (I46 keeps its number for the blind rer… | `prompts/I82_blind_tooling.md` | 9 | 4 | 1 | `docs/iterations/I82.md` |
| I85 | M3 | = I39a: the Go derivation extracted (ParseBatch as an extracted consumer: I18's skeleton document of node/derivation pl… | `prompts/I85_derivation_extraction.md` | 6 | 4 | 1 | `docs/iterations/I85.md` |
| I87 | M3 | I87 (= I45a): the audit-loop machinery (round records with the auditor's family, Q9's labels and the convergence rule, … | `prompts/I87_audit_loop.md` | 4 | 13 | 1 | `docs/iterations/I87.md` |

## Reports without a predictions key

`docs/iterations/F30.md`, `docs/iterations/F31.md`, `docs/iterations/F32.md`, `docs/iterations/F33.md`, `docs/iterations/F34.md`, `docs/iterations/F35.md`, `docs/iterations/F36.md`, `docs/iterations/F38.md`, `docs/iterations/F40.md`, `docs/iterations/checkpoint_I11.md`, `docs/iterations/checkpoint_I16.md`
