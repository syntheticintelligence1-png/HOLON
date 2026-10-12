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
