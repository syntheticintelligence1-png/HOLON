# M3 law proposals (U2) — index

Status: **proposals only**. Nothing here is frozen, generated, modelled or proved. Every file under
`laws/` is an IR-style draft (`"status": "proposal"`, `facts: null`) whose `facts_needed` lists the
carriers / edges / registers / actions the current fact sets (`facts/morph_header.json`,
`spec/M1/facts/*.json`) lack, each with a Morph source citation (`file:line`, verified against
`morph-l2/morph @ 3e44e795586af3e11285b603ab642c67823add51` by substring match on the cited lines).
Hash and oracle hypotheses are listed as `premises` (whitepaper §8.5); no axioms.
`predictions.json` carries one preregistered prediction per law; §11.8 has no row for any of these
laws, so all are `origin: derived`.

Statement grammar: `holon-ir/0.1` (M0 style: `forall/assume/claim` over `call`) for codec/Go
component laws; `holon-ir/0.2` (M1 style: `binders/assume/claim` with `run/obs/mig/fn`) for
state-machine laws; `holon-ir/0.2-intent` for the single intent-lane record. `fn`/`call` symbols
not in the current facts are the ones `facts_needed` introduces.

## O1–O37

| ID | Rule | M3 law(s) | Status / reason |
|---|---|---|---|
| O1 | PAR-domain | — | mechanized M0: `L_dom_hdr`, `L_par_hdr_v0` (REFUTED, replayed) |
| O2 | PAR-domain | — | mechanized M0: `L_par_hdr_v2`, `L_rt_go_v2` (no v2 encoder; byte 0 patched, `common/batch/batch_cache.go:1729-1730`) |
| O3 | PAR-domain | `L_dom_router` | proposal |
| O4 | PAR-totality | `L_tot_retrieve` | proposal |
| O5 | PAR-branch | `L_par_est_contexts`, `L_par_est_fastpath` | proposal (two estimators, two laws; fast path splits on HypZstd) |
| O6 | PAR-recompute | `L_par_datahash_legacy` | proposal |
| O7 | PAR-cycle | `L_par_lbn_cycle` | proposal |
| O8 | PAR-consumer | `L_cons_trailing` | proposal; SPLIT on oracle HypC (circuit source not in checkout) |
| O9 | PAR-init | `L_init_cursor` | proposal; needs a pre-genesis initial state (M1 debt: `importGenesisBatch`) |
| O10 | PAR-weak | `L_intent_docs` | intent lane (E6): five intent questions I1–I5 for human adjudication; not a theorem |
| O11 | UNDO | — | mechanized M1: `L_undo_BVH` |
| O12 | UNDO | — | mechanized M1: `L_undo_cancel` (intent-contract candidate stays with the lead) |
| O13 | NAT | `L_nat_cutover_slash` | proposal |
| O14 | NAT | `L_nat_cutover_defend` | proposal |
| O15 | NAT | — | mechanized M1: `L_nat_eta2` |
| O16 | NAT | `L_nat_enq` | proposal |
| O17 | NAT (benign) | `L_nat_bvh_unpinned` | proposal; predicted REFUTED (benign), recorded for completeness |
| O18 | NAT-composition | `L_nat_eta34` | proposal |
| O19 | SYM-ω | — | mechanized M1: `L_sym_omega` |
| O20 | SYM-π | `L_sym_pi_zero` | proposal (witness chains O19) |
| O21 | SYM-τ | `L_sym_tau_enq` | proposal |
| O22 | FACT | — | mechanized M1: `L_fact_Z` |
| O23 | FACT | `L_fact_pih_lbn` | proposal |
| O24 | FACT | `L_fact_v0_ctx` | proposal |
| O25 | FACT/SORT | `L_sort_bearer_recommit` | proposal (minimal rule SORT payer/bearer; needs a ghost `chooser` register) |
| O26 | SORT×UNDO | — | mechanized M1: `L_tag_BVH` |
| O27 | SORT-sign | — | mechanized M1: `L_sort_remaining` |
| O28 | SORT-width | `L_sort_width_l1` | proposal |
| O29 | SORT-payer | `L_sort_payer_replay` | proposal |
| O30 | SORT-conservation | `L_sort_conservation_commit` | proposal |
| O31 | DISCH-external | — | mechanized M1: `L_disch_stale`, `L_disch_stale_commit` |
| O32 | DISCH-non-dischargeable | — | mechanized M1: `L_undo_BVH` (pin), `L_disch_*` profile |
| O33 | DISCH-mixed | — | mechanized M1: `L_disch_delay_{nofree,pay,wait,prove}` |
| O34 | DISCH-external | `L_disch_replay_budget` | proposal; predicted PROVED = blocking invariant holds (the finding) |
| O35 | DISCH-self-controlled | `L_disch_challenge_gas` | proposal; needs an affine gas cost model (HypGas) and ceiling G |
| O36 | OWN-alias | — | mechanized M1: `L_own_txspayload` |
| O37 | OWN-lost-write | `L_own_hdr_cache` | proposal |

## Appendix A (F1–F14)

| ID | M3 law(s) | Status / reason |
|---|---|---|
| F1 | `L_disch_challenge_gas` | proposal (O35) |
| F2 | — | mechanized M1: `L_undo_BVH`, `L_fact_Z` (O11, O22, O32) |
| F3 | `L_tot_retrieve` | proposal (O4) |
| F4 | — | mechanized M1: `L_sort_remaining`, `L_disch_stale` (O27, O31) |
| F5 | `L_sym_pi_zero` | O19 part mechanized M1 (`L_sym_omega`); O20 part proposed |
| F6 | — | mechanized M1: `L_tag_BVH` (O26) |
| F7 | `L_nat_enq`, `L_sym_tau_enq` | O33 profile mechanized M1 (`L_disch_delay_*`); O16/O21 proposed |
| F8 | `L_sort_payer_replay`, `L_disch_replay_budget` | proposal (O29, O34) |
| F9 | `L_par_est_contexts`, `L_par_est_fastpath` | estimator items proposed (O5); aliasing item mechanized M1 (`L_own_txspayload`, O36) |
| F10 | `L_nat_cutover_slash` | proposal (O13) |
| F11 | `L_cons_trailing` (a), `L_par_lbn_cycle` (b,c), `L_fact_pih_lbn` (d), `L_par_l1count` (e), `L_fact_v0_ctx` (f) | proposal; F11e ("L1 counts are discarded") has no O row and gets its own law |
| F12 | `L_own_hdr_cache` (.3), `L_init_cursor` (.4), `L_sort_version_monotone` (.5 downgrade), `L_par_datahash_legacy` (.6), `L_sort_width_l1` (.7), `L_intent_docs` (.8) | .1 and .2 mechanized M0 (`L_dom_hdr`, `L_par_hdr_v2`); .5 "downgrade" has no O row and gets its own law |
| F13 | `L_sort_conservation_commit` | proposal (O30) |
| F14 | `L_dom_router` | proposal (O3) |

## Out of scope / not proposed (explicit)

- **O12 intent contract (N2)**: the UNDO law is mechanized (REFUTED); turning the +W residue into a
  proved intent contract (§5.9) needs the lead's scoping decision, so no M3 law is drafted for it.
- **N1–N4** are covered through their O rows (O15 mechanized; O12 mechanized; O25, O14 proposed).
- **D1–D9** are discharged obligations, not findings; D4's base case is the only piece re-opened here
  (`L_init_cursor`), and D8's "annotated slash `receive`" is folded into `L_sort_conservation_commit`.
- **Circuit-side laws** (anything needing the prover source) are stated parametric in HypC/HypV and
  marked SPLIT; the oracle hypotheses must be tested outside this repo (A4).

## Shared facts debt (union of `facts_needed`)

- Pre-genesis initial state and `importGenesisBatch` as an action (`Rollup.sol:226-252`).
- Migrations `eta3`, `eta4`, `eta_enq`, `eta_bvh`, `legacy_queue`, `legacy_bvh` with in-flight types
  (`Rollup.sol:199-219`, `L1MessageQueueWithGasPriceOracle.sol:60,261-268`, `Rollup.sol:106-108`).
- Environment contracts as edges: `MultipleVersionRollupVerifier.getVerifier/updateVerifier`
  (`:98-123`, `:148-167`), `Submitter.slash/isActive` (`:146-159`, `:70-72`),
  `L1CrossDomainMessenger.replayMessage/updateMaxReplayTimes` (`:175-244`, `:263-269`).
- Registers: `BatchData.submitter` and a ghost `chooser`, `legacyCutoverBatchIndex`, `replayStates`,
  `maxReplayTimes`, ETH balance + `msg.value`, gas-cost model with ceiling `G`.
- Go component carriers: `Blob`, `BatchData` (uint16 accumulators), both `RetrieveBlobBytes`
  implementations, both estimators, legacy `DataHash`, `BatchHeaderV{0,1}.Bytes` caches,
  derivation `ParseBatch`/`handleL1Message`.
