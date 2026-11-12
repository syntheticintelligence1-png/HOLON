# HOLON status

Rendered by `python -m holon coordinator status` (holon/coordinator.py, I87) from every `spec/M*/predictions.json`, `prompts/`, `docs/iterations/` and `results/M*/audit_status.json`. Do not edit it: edit those and re-render. `--check` fails on any difference, so whoever merges a new key, prompt, report or audit status re-renders it.

## Milestones

| Milestone | Keys | Predictions | Regressions | Reports |
|---|---|---|---|---|
| M2 | 27 | 242 | 126 | 27 |
| M3 | 52 | 326 | 288 | 52 |
| M4 | 6 | 29 | 35 | 6 |
| M5 | 8 | 41 | 22 | 6 |
| M6 | 0 | 0 | 0 | 0 |

## Audit loop (whitepaper §9.5; results/<M>/audit_status.json)

| Milestone | Converged | Streak | k | Counted rounds | Rounds | Open high findings | Why |
|---|---|---|---|---|---|---|---|
| M3 | yes | 4 | 3 | 7 | 9 | none | converged: 4 consecutive counted clean rounds (k = 3) and no open high-priority finding |

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
| I29 | M3 | I29: rule NAT over I28's versioned machine (catalog holon-rules/1.8): naturality squares across the deployed path's MIG… | `prompts/I29_nat.md` | 3 | 3 | 1 | `docs/iterations/I29.md` |
| I30 | M3 | Sorts III: nominal types, hole-free coercions, generated ghost tags | `prompts/I30_typed_sorts.md` | 8 | 6 | 1 | `docs/iterations/I30.md` |
| I31 | M3 | DISCH I: guard conjuncts, the enableable write closure over the extracted principal classes, blocking and external depe… | `prompts/I31_disch.md` | 12 | 3 | 1 | `docs/iterations/I31.md` |
| I32 | M3 | DISCH II: discharge profiles in the §8.4 form, Pareto search, bounded dominance and classification (test milestone T32:… | `prompts/I32_disch_profile.md` | 5 | 2 | 1 | `docs/iterations/I32.md` |
| I33 | M3 | O12's intent contract on M3, the typed extracted Rollup: C_o12_m3 bounds the residue of one cancellation (challengeStat… | `prompts/I33_o12_m3.md` | 8 | 4 | 1 | `docs/iterations/I33.md` |
| I34 | M3 | Rule SYM on M3, the typed extracted Rollup: families admitted by sorts (τ over the Time words, π over the set roles; ι … | `prompts/I34_sym.md` | 6 | 2 | 1 | `docs/iterations/I34.md` |
| I35 | M3 | Rule OWN from extracted backing identities: OWN-alias pairs and OWN-lost-write laws over the Go document's slice facts,… | `prompts/I35_own.md` | 7 | 3 | 1 | `docs/iterations/I35.md` |
| I40 | M3 | Refutation engines, Appendix D encodings, BMC over the extracted TRANS edges, concretization, emitted tests and the fin… | `prompts/I40_refute.md` | 11 | 5 | 1 | `docs/iterations/I40.md` |
| I41 | M3 | Untrusted prover intake | `prompts/I41_prover_intake.md` | 9 | 3 | 1 | `docs/iterations/I41.md` |
| I42 | M3 | Theory core I: generic graphs, walks and holonomy with Lemma 6.2, Thm 6.3, Thm 6.4 and Cor 6.5 kernel-checked in Lean i… | `prompts/I42_theory_core.md` | 4 | 9 | 1 | `docs/iterations/I42.md` |
| I43 | M3 | Theory core II and Lean for the promoted set: Thm 6.6 (symmetries: identity, composition, inverses, the submonoid of pa… | `prompts/I43_theory_core2_lean.md` | 3 | 12 | 2 | `docs/iterations/I43.md` |
| I44 | M3 | I44 (= I44b): Def 6.13's measures that I81 (= I44a) left pending, and the ranking over them: NAT's naturality defect ma… | `prompts/I44_measures_pending.md` | 7 | 5 | 1 | `docs/iterations/I44.md` |
| I46 | M3 | I46: the blind rerun from code, its comparison with the lead, and the M3 exit decision (I82 = I46a built the pack, the … | `prompts/I46_blind_rerun.md` | 6 | 6 | 1 | `docs/iterations/I46.md` |
| I47 | M4 | Target-agnostic factory, parallel checking, performance loop, drift trigger: targets/<name>/target.json for the develop… | `prompts/I47_target_factory.md` | 5 | 6 | 1 | `docs/iterations/I47.md` |
| I48 | M4 | Evaluation corpus and unsolved controls: 20 public defects across six fixed systems (two rollups, four beyond), collect… | `prompts/I48_eval_corpus.md` | 4 | 6 | 1 | `docs/iterations/I48.md` |
| I49 | M4 | Held-out target I: extraction, facts and the diagram of the sealed target (blind prereg) | `prompts/I49_heldout_extraction.md` | 6 | 6 | 1 | `docs/iterations/I49.md` |
| I50 | M4 | Held-out target II: the pinned catalog's rules, the run, replay and metrics on the sealed target | `prompts/I50_heldout_rules.md` | 5 | 5 | 1 | `docs/iterations/I50.md` |
| I51 | M4 | HOLON on the corpus pre-fix commits: every one of the 20 I48 entries cloned at its pre-fix commit and run through HOLON… | `prompts/I51_corpus_holon.md` | 4 | 6 | 1 | `docs/iterations/I51.md` |
| I54 | M5 | I54: L6, L9 and L10 defined and preregistered (Q11): bounded games scored against constructed and documented truth, env… | `prompts/I54_m5_definitions.md` | 3 | 3 | 1 | `docs/iterations/I54.md` |
| I55 | M5 | I55: the intent lane: doc comments atomized with exact spans, reviewed clauses compiled to laws/INTENT/ over the factor… | `prompts/I55_intent_lane.md` | 11 | 3 | 1 | `docs/iterations/I55.md` |
| I56 | M5 | I56: bounded games over F(M3) (M5, L6): payoff facts as a generated value-flow document with V9 coverage, strategies as… | `prompts/I56_games.md` | 5 | 3 | 1 | `docs/iterations/I56.md` |
| I57 | M5 | I57: environment modules (L1 reorg depth, the DA retention window, the blob-archive fetcher) validated against observat… | `prompts/I57_environment_modules.md` | 7 | 2 | 1 | `docs/iterations/I57.md` |
| I58 | M5 | I58: the M5 report: L6, L9 and L10 reported as measured in results/M5/metrics.json, each computed by I54's stub (holon.… | `prompts/I58_m5_report.md` | 7 | 3 | 1 | `docs/iterations/I58.md` |
| I59 | M2 | I23a track: historical on-chain acquisition and the first per-edge replay on real inputs (human answer Q5) | `prompts/I59_historical.md` | 9 | 2 | 1 | `docs/iterations/I59.md` |
| I60 | M2 | A1 mutation adequacy on real code, replacement catalog | `prompts/I60_mutation_replacement.md` | 20 | 10 | 1 | `docs/iterations/I60.md` |
| I61 | M2 | A1 mutation adequacy on real code, second replacement catalog | `prompts/I61_mutation_second_replacement.md` | 24 | 11 | 1 | `docs/iterations/I61.md` |
| I62 | M2 | A1 mutation adequacy on real code, the rerun of I61's catalog with I61's defects fixed | `prompts/I62_mutation_rerun.md` | 9 | 13 | 1 | `docs/iterations/I62.md` |
| I63 | M3 | = I28a: deployment history from the code (versions, reinitializers, storage-layout diffs and MIG edges over every tag o… | `prompts/I63_history.md` | 5 | 3 | 1 | `docs/iterations/I63.md` |
| I64 | M3 | = I33a: intent contracts (format, registry, derivation of L_weak, the run's marking), G10, intended_bounded in the v2 r… | `prompts/I64_contracts.md` | 4 | 3 | 1 | `docs/iterations/I64.md` |
| I65 | M3 | = I33b: the O12 intent contract on M2's window view of the extracted Rollup: a ghost counter (IR 0.3 term), the proof c… | `prompts/I65_o12_view.md` | 4 | 4 | 1 | `docs/iterations/I65.md` |
| I66 | M3 | holon differential's window view in M2's evidence set (Q62): its diagram by I11's adapters and its E2, E3, E4 and E6 at… | `prompts/I66_view_evidence.md` | 1 | 5 | 1 | `docs/iterations/I66.md` |
| I67 | M3 | I67 (= I38a): Go codecs at loop granularity (holon-go-frontend/0.2 loop bodies), Go-op components over interface carrie… | `prompts/I67_go_loop.md` | 5 | 5 | 1 | `docs/iterations/I67.md` |
| I68 | M3 | Structural storage keys in the M3 model (the Q21 fix): mapping storage keyed as (base slot, key path) instead of a look… | `prompts/I68_structural_keys.md` | 7 | 8 | 1 | `docs/iterations/I68.md` |
| I69 | M3 | = I36a: Bundle I's extraction and acquisition, no laws: the message queue, the messenger, the whitelist and the Submitt… | `prompts/I69_bundle_extraction.md` | 7 | 5 | 1 | `docs/iterations/I69.md` |
| I70 | M3 | = I36c: the cutover x slash laws, O13 and O20's economic half, over the real legacy staking code (Q12): the legacy regi… | `prompts/I70_cutover_slash.md` | 6 | 4 | 1 | `docs/iterations/I70.md` |
| I71 | M3 | UNDO's third sub-form cancel (I33's catalog key): the cancel restore U3' and criterion U4' over the extracted transitio… | `prompts/I71_undo_cancel.md` | 6 | 6 | 1 | `docs/iterations/I71.md` |
| I72 | M3 | E2 over the adopted holon-facts/0.3 transitions documents (I33's evidence key): written-via-p, read-via-q atoms from th… | `prompts/I72_e2_transitions.md` | 1 | 5 | 1 | `docs/iterations/I72.md` |
| I80 | M3 | = I37a: Bundle II's extraction and acquisition, no laws: the verifier router (MultipleVersionRollupVerifier) extracted … | `prompts/I80_bundle2_extraction.md` | 6 | 4 | 1 | `docs/iterations/I80.md` |
| I81 | M3 | I81 (= I44a): Def 6.13's measures (holon/measures.py, one interface over PAR's holonomy defect size, NAT's naturality d… | `prompts/I81_measures_ranking.md` | 7 | 7 | 1 | `docs/iterations/I81.md` |
| I82 | M3 | I82 (= I46a): the blind pack, the comparison generator and the agreement metric (I46 keeps its number for the blind rer… | `prompts/I82_blind_tooling.md` | 9 | 4 | 1 | `docs/iterations/I82.md` |
| I83 | M3 | I83 (= I28b): I28's model debt paid. | `prompts/I83_versions_debt.md` | 6 | 3 | 1 | `docs/iterations/I83.md` |
| I84 | M3 | = I37b: Bundle II's laws over I80's extraction: rule catalog holon-rules/1.10 adds PAR link_domain (O3: a proof call th… | `prompts/I84_bundle2_laws.md` | 8 | 4 | 1 | `docs/iterations/I84.md` |
| I85 | M3 | = I39a: the Go derivation extracted (ParseBatch as an extracted consumer: I18's skeleton document of node/derivation pl… | `prompts/I85_derivation_extraction.md` | 6 | 4 | 1 | `docs/iterations/I85.md` |
| I86 | M3 | = I36b: Bundle I's laws over the current deployment, over I69's extraction: rule catalog holon-rules/1.11 adds SORT pay… | `prompts/I86_bundle_laws.md` | 11 | 4 | 1 | `docs/iterations/I86.md` |
| I87 | M3 | I87 (= I45a): the audit-loop machinery (round records with the auditor's family, Q9's labels and the convergence rule, … | `prompts/I87_audit_loop.md` | 4 | 13 | 1 | `docs/iterations/I87.md` |
| I88 | M3 | = I39b: I39's laws over I85's product machine (O7 PAR-cycle, the O8 law pair under HypC with a hypothesis split, O24, t… | `prompts/I88_derivation_laws.md` | 6 | 4 | 1 | `docs/iterations/I88.md` |
| I89 | M3 | = I39c: the Go consumer compiled to Bend from I85's extracted SSA by a generator (holon/derivation/bendgen.py: Go's int… | `prompts/I89_derivation_bend.md` | 10 | 4 | 1 | `docs/iterations/I89.md` |
| I90 | M3 | I90 (= I38b): O28 at 65,536 L1 messages, through the count channels of a Go component: a Go count component over the ca… | `prompts/I90_go_counts.md` | 4 | 5 | 1 | `docs/iterations/I90.md` |
| I91 | M3 | I91 (= I38c): the compression oracle, HypZ and HypZ_len (§8.5; distinct from Hyp-Z0-kzg), tested on the real codec at t… | `prompts/I91_compression_oracle.md` | 6 | 4 | 1 | `docs/iterations/I91.md` |
| I92 | M3 | = I34b: rule SYM over Bundle I (O21 and the messenger's sentinels). | `prompts/I92_sym_bundle.md` | 6 | 4 | 1 | `docs/iterations/I92.md` |
| I93 | M3 | = I38d: O5, O6 and D3 as laws over a Go part of rule PAR (holon-rules/1.15) with the frontend 0.3 config: D3 as two PRO… | `prompts/I93_go_laws.md` | 5 | 4 | 1 | `docs/iterations/I93.md` |
| I94 | M3 | = I36d: O13 and O20's economic half decided by the checker (I70's two slash laws, statements unchanged), and model3's c… | `prompts/I94_slash_decide.md` | 5 | 4 | 1 | `docs/iterations/I94.md` |
| I95 | M3 | I95 (= I46b): moving I46's E2 with the lead's rulings: the binding derived from code inside the pack, DISCH's budget in… | `prompts/I95_blind_rerun_b.md` | 7 | 7 | 1 | `docs/iterations/I95.md` |
| I97 | M3 | I97: the F-M3-13 fix, BendTT (G7) on M3 in CI and the six BendTT rejections classified by the lead's ruling | `prompts/I97_bendtt_g7_m3.md` | 5 | 8 | 1 | `docs/iterations/I97.md` |
| I98 | M3 | I98: G6 on M3, the two REFUTED records G6 refuses diagnosed and fixed, one rule for the final filter and G6, and G6 in … | `prompts/I98_g6_m3.md` | 6 | 7 | 1 | `docs/iterations/I98.md` |
| I99 | M3 | I99: G9 checks every result record's premises against its law's assume clauses (audit M3/5 F-M3-19, high, gate_evasion) | `prompts/I99_g9_premises.md` | 5 | 9 | 1 | `docs/iterations/I99.md` |
| I100 | M3 | I100: rule PAR_record_round_trip: the record law over an encoder into a byte record and its getter family, the constant… | `prompts/I100_par_record_round_trip.md` | 9 | 14 | 1 | `docs/iterations/I100.md` |
| I101 | M3 | I101: the post-exit fixes of three M3 audit findings: the counted-round evidence rule reads each record's content and C… | `prompts/I101_post_exit_audit_fixes.md` | 4 | 8 | 1 | `docs/iterations/I101.md` |
| I102 | M3 | I102: holon audit regress compares each commit with its own parents, so it neither reports statement changes no commit … | `prompts/I102_regress_parents.md` | 3 | 8 | 1 | `docs/iterations/I102.md` |
| I50b | M4 | Held-out target, a contaminated rerun (I50b): two generic producer changes (a sorts rule for the frontend's update term… | `prompts/I50b_heldout_rerun.md` | 5 | 6 | 1 | `docs/iterations/I50b.md` |
| I54b | M5 | I54b: the corpus-truth key: I54's frozen truth protocol run on I48's 20 entries by two fresh labellers per entry, every… | `prompts/I54b_m5_truth_key.md` | 5 | 3 | 1 | `docs/iterations/I54b.md` |
| I55b | M5 | I55b: the intent lane on the corpus: L10's corpus_recall over the corpus-truth key I54b's scored entries (c17), the tru… | `prompts/I55b_intent_corpus.md` | 3 | 2 | 1 | none |
| I56b | M5 | I56b: L6's corpus accuracy scored against the corpus-truth key I54b (the lead's condition 5), with the truth pinned bef… | `prompts/I56b_corpus.md` | 0 | 3 | 1 | none |
| I96a | M3 | I96a (= I46c, first half): DISCH's R0 derived from the binding by a target-agnostic step that also writes the sidecar's… | `prompts/I96a_r0_from_binding.md` | 5 | 7 | 1 | `docs/iterations/I96a.md` |
| I96b | M3 | I96b (= I46c, second half): the refinement hints derived inside the pack (holon refinement; the fragments binding deriv… | `prompts/I96b_hints_from_code.md` | 5 | 10 | 1 | `docs/iterations/I96b.md` |

## Reports without a predictions key

`docs/iterations/F30.md`, `docs/iterations/F31.md`, `docs/iterations/F32.md`, `docs/iterations/F33.md`, `docs/iterations/F34.md`, `docs/iterations/F35.md`, `docs/iterations/F36.md`, `docs/iterations/F38.md`, `docs/iterations/F40.md`, `docs/iterations/checkpoint_I11.md`, `docs/iterations/checkpoint_I16.md`
