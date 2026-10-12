# M3 spec: full Morph bundle, all eight rules, audit loop, blind rerun

Whitepaper §15.2, M3. Exit criterion: **a published comparison with §11.8 and Appendix A**.
Morph is pinned at `3e44e795586af3e11285b603ab642c67823add51`. Lead-authored; written before any M3 mechanization.

## Entry state (recorded, not re-opened)

- **M2 replay:** passes. 45,240/45,240 checks agree, with 0 unexplained over 1,131 mainnet commits.
- **M2 mutation adequacy:** fails in all three rounds. A1 19/45 = 0.42, A2 14/30 = 0.47, A3 16/30 = 0.53, against 0.80. A3's laws added no unique detection, and the misses sit in abstracted facts. M2 is therefore recorded as *adequacy-failed*, and M3 starts anyway with that debt stated.
- **Already mechanized:**
  - M0: 8 laws.
  - M1: 17 laws, plus `L_par_hdr_v2_composed`.
  - M3_sorts (U3): 7 SORT laws covering O20, O21, O27 and O28.
  - U2 proposals: 27 draft laws (`spec/M3/proposals/`, unfrozen).

## Decisions (made by the lead; Omar delegated these calls)

1. **No hand-written facts in M3.** This is the BUILD_PLAN Q19 default. Every M3 fact comes from an extractor. A component that can't be extracted is listed as coverage debt, and any law that needs it is predicted and reported UNKNOWN. M1 hand facts stay only as the M1 reference.
2. **Preregistration per law.** A U2 proposal becomes an M3 law only through a lead-reviewed commit that adds the law to `laws/M3/<RULE>/` and its prediction to `predictions/M3.json`, before any run on it.
   - A prediction that fails is a Surprise, published with an explanation.
   - Statements never move after results are seen.
3. **Blind rerun protocol (fixed now, before any M3 result exists).**
   - Fresh child sessions get a bundle that strips Appendix A, §11.3–§11.7, `spec/M3/proposals/`, `audit/` and all result/law/prediction trees.
   - They get the remaining whitepaper text, the factory code, the extractors, and the pinned Morph checkout.
   - They write laws per rule from the diagram and the extracted facts alone.
   - Their outputs are frozen by hash before the comparison script runs.
   - The script classifies each Appendix A finding F1–F14 and each §11.8 row as re-found, missed or contradicted.
4. **Status vocabulary.** Exactly PROVED, REFUTED or UNKNOWN. A REFUTED law counts as a finding only if its witness replays through public entry points on the pinned code (G6). Model-only or storage-injected witnesses are labelled as such.

## Work units

### Wave 1: extraction for the full bundle (prerequisite for most laws)

| Unit | Scope | Done when |
|---|---|---|
| E1 Rollup fidelity | Turn the 41 hand-written/coverage-debt items of `spec/M2/extracted/morph_rollup.json` into extracted facts: the `revertBatch` loop as a per-index effect, the `finalizeBatch` deletes, queue writes, and the delay profile | Debt count drops, with each remaining item justified; the M1 and A2/A3 law statuses on the new extraction are explained against the old ones |
| E2 Bundle contracts | L1MessageQueue, L1CrossDomainMessenger (`replayMessage`, fees), Submitter/Staking (`slash`, `stakeOf`), the verifier router (`getVerifier`, `updateVerifier`), linked via `links.json` | The facts that the U2 NAT, SYM, DISCH and SORT-payer laws need are extracted or listed as debt |
| E3 Go derivation | `ParseBatch`, `DecodeTxsFromBytes`, the two `RetrieveBlobBytes` twins, the estimators, `DataHash`/`DataHashV2` | The facts that the U2 PAR, FACT and OWN laws need are extracted or listed as debt |

### Wave 2: mechanize per rule (each one starts from a lead-reviewed preregistration commit)

| Rule | Laws (U2 ids) | Notes |
|---|---|---|
| PAR | dom_router, tot_retrieve, par_est_contexts, par_est_fastpath, par_datahash_legacy, par_lbn_cycle, par_l1count, cons_trailing, init_cursor | `cons_trailing` is split on HypC (circuit source absent) |
| NAT | nat_cutover_slash, nat_cutover_defend, nat_enq, nat_bvh_unpinned, nat_eta34 | Over `spec/M2/extracted/migrations.json` |
| FACT | fact_pih_lbn, fact_v0_ctx | Product programs, §8.5 premises |
| SYM | sym_pi_zero, sym_tau_enq | |
| SORT | sort_bearer_recommit, sort_width_l1, sort_payer_replay, sort_conservation_commit, sort_version_monotone | Plus the 7 U3 laws already merged |
| DISCH | disch_replay_budget, disch_challenge_gas | `challenge_gas` needs the HypGas affine model |
| OWN | own_hdr_cache | |
| intent | intent_docs | Intent lane only; never a theorem |

### Wave 3: audit loop, blind rerun, comparison

- **A-round 2:** an independent auditor session covering M2 and M3, as round 1 did. Its findings are remediated in PRs.
- **Blind rerun:** under decision 3, at least two independent fresh sessions.
- **The comparison:** `docs/M3_COMPARISON.md`, the exit artifact. It has a row for every §11.8 law and every F1–F14 finding, giving the factory status, the blind-rerun status, replay evidence, and the deviation explanation.

### Optional: adequacy round A4

After E1 lands, run a fourth held-out round over lines not used by A1–A3, on the new extraction. It is reported separately. It cannot change the A1–A3 scores or the M2 *adequacy-failed* record.

## Gates

`python -m holon gate --milestone M3` extends the M1 gate with:
- the coverage-debt accounting from decision 1;
- G6 replay evidence for every REFUTED law;
- G11 inhabitance for every PROVED law with premises.

The M0, M1 and M3_sorts gates and `tools/freeze.py check` must keep passing on every merge.

## Blind bundle: `tools/blind_bundle.py`

`python3 tools/blind_bundle.py OUT` copies the tracked tree at HEAD without `.git`.

It removes everything that states findings, laws, predictions or results:
- `audit/`, `results/`, `laws/`, `predictions/`, `replay/`, `facts/`, `gen/`, `prompts/`;
- `spec/M0..M3`, every `tests*/`, `config/triage.json`, `FROZEN.sha256` and `README.md`;
- every doc except the Bend primer and notes;
- whitepaper §11.3–§11.8 and Appendix A.

It writes `BLIND_MANIFEST.json`, holding the source commit, a sha256 per file and `known_leaks`. The output is deterministic.

The blind agents rerun the extractors themselves. Residual leaks that can't be removed without removing the factory are listed in `known_leaks`; at f386798 + this tool there are 6:
- law ids in `holon/assemble/header.py`, `holon/mreplay.py`, `holon/mutate/runner.py`, `holon/replay.py` and `holon/sorts/factsgen.py`;
- O/law ids in whitepaper §1–§10.

The comparison reports, for every re-found item, whether it is named in a leaked file. Re-finding an item that is named in a leaked file counts as weak evidence only.

## Amendments

- `spec/M3/predictions.json` sha256: `146a5b370cabbc9f4b842fed3a1ee680104d2ada3766c91a835b2d36abe31f0f`
  (R9b preregistration of 9 `L_init_*` router laws, before any run; previous sha `e10eb81d8358d331c193f9d2b29360f795feb723f88f8258e1d9b22ae4564a23`)
- AUDIT_R2 follow-up preregistration (lead, before any run): 5 laws from `spec/M3/laws_src/r2_nat_rel_laws.py` (L_natr_defend REFUTED, L_natr_slash_at_stake REFUTED, L_natr_slash_at_stake_native PROVED) and `r2_msg_rel_laws.py` (L_msgr_payer_bears_fee REFUTED, L_msgr_sender_can_replay REFUTED). predictions.json regenerated (36 -> 41 entries); the sha above supersedes abc8896d…; existing 36 entries unchanged.
  (generated by `spec/M3/laws_src/gen_predictions.py` from each law's `predicted`; audit R2 F5)
- R3 coverage laws (`spec/M3/laws_src/r3_cov_laws.py`, 28 laws `L_cov_*` across M3_nat 21, M3_msg 2, M3_router 5), all predicted PROVED from the pinned Solidity source, preregistered in this commit before any run, after the G8 fidelity fixes `07d4905`/`8369b08`. They target the G8 holes; a miss is published, not repaired in the law. `L_cov_rt_vap_unregistered_fails` is expected to expose the MVRV not-found sentinel (the model routes to `b_nf(0)`, the contract reverts).
- R3 encoding erratum (before any M3_nat R3 law ran): 9 `L_cov_*` NAT laws encoded the `List<Nat>` input `blobs` as `{"nat": [...]}` because the r3 generator reused the scalar-only `e2_laws.act`. `holon/gen/mlaws.py` rejected them at emit, so none of the 21 NAT laws ran. The generator now encodes lists as `{"nats": [...]}`. Claims, setups and predictions are unchanged (predictions sha unchanged); only those 9 statement hashes change.
- R4: MVRV `getVerifier` not-found is now an extracted revert at the call sites, not a sentinel. The structural recogniser in `translate.s_loop` (`for (i = L; i > 0; --i) { X = A[i-1]; if (X.f <= K) { F = true; break; } }` over an `abs_map_list` record family, `L == A.length`, `F` a declared bool local) binds `X := lv_le(A, K)` and `F := lv_le_has(A, K)` (new `lv_le_has` builtin); the existing RevertStatement → call_guards → def_call path then emits `require !(lv[v].s > idx && !lv_le_has(lvv[v], idx))` with reason `ErrorVerifierNotFound`, prov ast. Near-miss loops fall through to `untranslated_loop`. `defs.get_verifier.body` stays spec-forced with `b_nf` for the `verifier_of` observer only; `L_rt_before_start` stays REFUTED on that artefact. The guard needed def params counted as bound names during def-body translation, so `defs_from` entries may declare `bind_params`; it is set only on `get_verifier`, and every other facts file regenerates byte-identical. The same unbound-drop silently kills other defs' param-referencing guards (a real fidelity defect; taken as a separate unit). No prediction changed (sha unchanged); the M3_router facts rebind `61f60923… → c2044f60…` is recorded in `laws/M3_router/ERRATA.json` with all 15 statuses unchanged. The `L_cov_rt_vap_unregistered_fails` miss was misattributed in R3: it stays REFUTED, but the cause is the external `verifyBatch` oracle — solc 0.8.24's `extcodesize` check reverts the real call to address(0) with empty data (native evidence: `replay/M3/mvrv_notfound_report.json`), not the not-found sentinel.
- R5: def params are bound names during every `defs_from` body translation, not only `get_verifier`. Lets/guards referencing a def param had been silently dropped by `_unbound_names` everywhere; the `bind_params` flag is removed and `mvrv.json` regenerates byte-identical. The only M3 change: `blob_hash` (`_computeBlobVersionedHash`) now emits its two requires at the `commitBatch`/`commitBatchWithProof` call sites ("V2 requires at least 1 blob", "legacy batches support exactly 1 blob"; Rollup.sol:913,915), both verified against source with `stored==0` folded in. `spec/M2/` stays at committed bytes; the regeneration drift is recorded in `docs/M2_EXTRACTION_DRIFT.md`. No prediction changed (sha unchanged); the M3_nat rebind `5ee99bad… → 60986073…` is in `laws/M3_nat/ERRATA.json` with all 38 statuses unchanged (35 PROVED, `L_natr_defend`/`L_natr_slash_at_stake` REFUTED findings, `L_natr_slash_at_stake_native` UNKNOWN).
- R6: trace search for machines without a hand policy. `holon/js/policy_lib.mjs` gains `derivedPolicy(s, facts)`, which builds candidates from `facts.actions[*].inputs` alone: a Nat dictionary {0,1,2} + Nat literals <= 2^16 in guards/effects/defs + scalar Nats in the decoded state (and +1) + list lengths, sorted unique capped at 12; Bool {false,true}; `List<Nat>` [] and [d] for the 3 smallest d; other types skip the action and log one "untyped input" note. Per action a deterministic diagonal enumeration of the input product, capped at 48 candidates, actions in facts order. `policyOf` now selects explicitly: named `facts.policy` wins; the Rollup heuristics apply only when the facts contain a `commitBatch` action, with derived candidates appended for ops the heuristics don't emit (composed machines like morph_rollup); everything else gets the derived policy alone. Before R6 the Submitter, messenger and MVRV machines fell into the Rollup heuristics, which throw on registers they don't have, so quantified trace laws over them were UNKNOWN by construction (a B1 report). The search policy is untrusted, so soundness is unaffected: it only steers candidate enumeration; claims are still evaluated on the compiled model and proofs still go through the checker. No facts sha, law or prediction changed; `holon run` for M3_msg, M3_router and M3_nat flipped no status and produced no new GPRED miss.
- R7: three emitter/facts gaps from B1's report. `Emitter.view` no longer special-cases `log` — it erases like any other state field (checked: `mproofs.noninterference` treats erased fields uniformly, `explore.mjs` `proj` deletes named fields and `stateKey` already drops `log` independently). Counter-laws of a conjunction are now supported: `emit(counter=True, conj=k)` refutes conjunct k (`exs` binders/premises + `{a_k != b_k}`); the pipeline picks k as the lowest index the compiled model evaluates false under the witness and records `refuted_conjunct` in the result record (UNKNOWN if none falsifies; `mreplay.linearise` replays only conjunct k or reports the law not linearisable). The messenger environment's initial `t` is 1, not 0 — `block.timestamp > 0` on any real chain and `messageSendTimestamp == 0` is the contract's not-enqueued sentinel; M3_msg rebound `ca5a8c6d… -> 15d94ae2…` via ERRATA with all 16 statuses unchanged (the `L_msgr_*` findings and their witnesses are unchanged). B1 acceptance (scratch, not in `laws/`): `L_b1_disch_msg_replay_budget` now PROVED at t=1 (the t=0 artefact is gone), `L_b1_fact_blob_conflation`/`L_b1_undo_revert_residue` REFUTED with witnesses (neither linearisable: blobs_of without `new_hdr` premise; a `proj[log]` view-equality claim has no replay kind), `L_b1_sym_msg_commit_commute`/`L_b1_sym_revert_split` stay UNKNOWN (bounded search).
- R8: a lifter from `holon-extracted/go-machine/0.1` to `holon-facts/0.2`. `holon/frontends/go/lift.py` (`python -m holon.frontends.go lift <go-machine.json> -o <facts.json> [--coverage <cov.json>]`) converts the extracted OWN machine into machine facts, generating `spec/M3/extracted/go_batchdata_machine.json` + `spec/M3/coverage/go_batchdata_machine.json`. Identifiers Bend already accepts are kept verbatim; others are sanitised into [a-z_][a-z0-9_]* (`'` -> `_p`), with the table recorded under `extraction.renames`; collisions are a hard error. An action input named like a state field is renamed `in_<name>`; the ambiguous `txsPayload` in `go_append_*(h, txsPayload, txsPayload, cls)` is resolved positionally to source semantics (slice argument = field, payload argument = input). Anything the lifter can't express is a `coverage.debt` item of kind `unlifted_<what>` (9 items: dropped fields, other_ops, machine coverage_debt). `policy` stays unset (the go-machine carries no batchdata hint) so `derivedPolicy` applies. Verification: the lifted model compiles through the normal machine generator; the lifted and hand-written machines agree on obs logs for all 820 traces to depth 3 over the batchdata candidates (mapped positionally), 0 disagreements. `L_own_txspayload` on the lifted facts comes out UNKNOWN (bounded) vs committed REFUTED: the witness needs a 60-element list input, which `derivedPolicy`'s `[]`/`[d]` candidates cannot reach -- a search-policy coverage gap, not a model disagreement. (R9 added List<Nat> length candidates `Array(l).fill(m)` for literals l in [2,256] -- the lifted facts contain no such literal, so L is empty and the law stays UNKNOWN; no tuning past that.)
- R9: a generic code-presence guard on high-level external calls. In `call_contract`, `require(<addr> != 0)` ("call to address without code", prov ast) is emitted before oracle/inline/debt handling when the callee is contract-typed (MemberAccess on `I(expr).m()` or `x.m()` where `x` is contract-typed) AND its address is a modelled value -- a state register, action input, or let/computed value (`_addr_bound`: fact_inputs, fam scalar, let_names/pending/emitted lets, hoist_bound). Unmodelled, oracle_addr, queue-map and spec-constant addresses get no guard and no inputs; each such site records an `assumed` coverage item ("deployment-fixed address <name> assumed nonzero with code"). Action interfaces are unchanged vs HEAD. Guards emitted: mvrv 2 (`!= rollup 0` MVRV.sol:149, `!= v_verifier 0` MVRV.sol:138); submitter/l1messenger/morph_rollup facts are byte-identical. In replay comparison the reason displays as `raw:0x` (empty revert data) via `REASON_DATA` in mreplay. Effect: `L_cov_rt_vap_unregistered_fails` flips REFUTED -> PROVED matching its prediction (native: `vap_unregistered rev 0x`); 9 other M3_router laws flip PROVED -> REFUTED -- closed laws whose traces omit `initialize`, so `rollup==0` and the contract reverts calling `IRollup(0)` (setup-order artefacts, triaged none/closed; native control `ctrlC_uninit_updateVerifier rev 0x`); `L_rt_before_start` flips REFUTED -> PROVED (the sentinel-observer trace now reverts earlier). All recorded in ERRATA; no law or prediction changed.

### R9b: router laws restated on an initialised router (preregistered before any run)

R9 made 9 closed router laws REFUTED, because their traces start from `s0` without `initialize`, so `rollup == 0`. Those laws, their predictions and results stay as they are, triaged as setup-order artefacts.
- `spec/M3/laws_src/r9_init_laws.py` (lead-authored) generates `L_init_<id>` for each of them: the same statement with `initialize(who=1, r=5)` prepended to every trace rooted at `s0`.
- Each keeps its original's prediction, because the deployed MVRV is initialised.
- A miss is a published surprise, never a fix to the law.

