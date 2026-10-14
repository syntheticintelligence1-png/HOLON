# I26: FACT rule, attribution (O25) and F(m, c), decided on the extracted real code

Rendered from `docs/BUILD_PLAN.md` §4 I26. Milestone M3.

Whitepaper sources:
- §5.5 (FACT: kernel containment per commitment × consumer, under local collision-freedom premises; the quantitative form; the Morph instances);
- Thm 6.8 ((i) to (iii) and F(m, c) = 0 iff they hold) and Def 6.13 (F(m, c), the FACT measure);
- §8.4 (FACT row: a relational law, proved through a product program; refuted by an input pair with its CF instance), §8.5 (hypotheses are premises; split status), Cor 6.16, App. D;
- App. E (FACT row), App. F (`fact_z`), §11.3 (O22, O25), §11.4 N3, §11.8 (`L_fact_Z`).

Read `AGENTS.md`, `docs/M0_SPEC.md`, `docs/BEND_PRIMER.md` and `docs/BEND_NOTES.md` first. Then read:
- `docs/iterations/I20.md`, `I21.md` (HypZ and Hyp-ISubmitter fail: F-M2-41, target finding T2; F-M2-40) and `I24.md` (the back-test across documents);
- the contracts of I30, I27 and I31 (the docstrings of `tests_m3/test_sort_types.py`, `test_undo.py`, `test_disch.py`): I26 binds to those preregistered contracts, not to their outcomes;
- `laws/M1/L_fact_Z.json` and `results/M1/L_fact_Z.json`.

**The docstring of `tests_m3/test_fact.py` is the contract.** It fixes:
- the terms;
- rules F1–F9: commitments, commitment sites, delivered data, kernel laws, attribution consumers, pins, the attribution basis, premises and the measure;
- rule H1 (hypotheses in records);
- the analysis document and its CLI;
- the laws: catalog, IR, the `fact` term and ref, the semantics of `fact_<x>`, the chooser companion, `fhit_<x>`;
- the proof routes, the term budget, the refutation search, the replay report, the records and the classification;
- the back-test (FB1–FB4), the sensitivity checks (S1–S3), the gate and the gaps (G1–G7).

Instruments fixed at the prereg (do not edit them; a wrong instrument is a Question and an amendment line in `spec/M3/amendments.jsonl`):
- `spec/M3/lib/fact.json`: the FACT sidecar. It holds I30's model sidecar, the documents, the binding, the hypotheses with their roles and I21's verdicts, the search budget, the measure's domain, the term budget and the frozen back-test map and move;
- `spec/M3/lib/fact_basis.json`: every commitment, consumer, pin, law, premise, measure and predicted outcome on the rollup document, computed by `tests_m3/_i26.py::fact_basis_doc`, which writes the rules out a second time, independently of `holon/`;
- `tests_m3/_i26.py`: that instrument, the back-test move, `agg_m1`, the raw-call replay and the hand-built chains;
- `tests_m3/fixtures/fact/harness/*.txt`: byte copies of the I20 step harness taken at the prereg.

## Why this iteration matters

M1's only FACT law, `L_fact_Z`, is a statement over the hand abstraction. The whitepaper's FACT obligation has never been derived, its measure has never been computed, and its attribution instance (N3/O25) has never been stated.

O25, the chain this iteration must show on the real Rollup:
1. Submitter S1 commits batch k with its own blob.
2. The owner reverts k. The batch's blob hash stays pinned: `batchBlobVersionedHashes` is a residue (I27).
3. Every later commit at k must reuse that blob. `commitBatch` reverts ("commitBatch requires no stored blob hash"), so a second submitter S2 recommits with `commitState`, which copies the pinned hash.
4. The chain records S2 as the batch's submitter: `batchDataStore[k].submitter` is the caller.
5. If the batch is challenged and its proof times out, `_challengerWin` slashes S2 (`ISubmitter.slash(batchDataStore[k].submitter)`).

So S2 bears the bond for content S1 chose. A rational S2 refuses to recommit unprovable content, and slashing becomes a liveness deterrent.

The prereg ran this chain, built by hand, on the real Rollup as the I20 binding deploys it (`TestInstrument.test_the_chain_instrument_runs_on_the_real_contract`):
- every step succeeds;
- `committedBatches[1]` after the recommit equals the original commit's;
- the recorded submitter goes 0x…1002 → 0x…1002 (after the revert) → 0x…1003;
- the timed-out proof calls `slash(0x…1003)`.

The real side is therefore known. The predictions are about holon: its rules derive the law, its model and search find the witness, the kernel checks the counter-law, and the replay passes.

## What the extracted side gives (computed at the prereg; the contract has the rules)

**Commitments (F1, F2).** One commitment, `committedBatches`.
- It has 4 commitment writes, each keccak256 of a header region: `commitBatch`, `commitBatchWithProof`, `commitState` and `importGenesisBatch`, `writes[0]`.
- 7 guard reaches authenticate against it, `committedBatches[k] == keccak256(header)`: in the three commits (the parent), `finalizeBatch`, `proveCommittedBatchState`, `proveState` and `revertBatch`.

**Delivered data (F3).** `commitBatch`, `commitBatchWithProof` and `commitState` read blob hashes; `importGenesisBatch` does not. That gives 3 kernel laws, each over the consumer "blobhash": the derivation input.

**Attribution consumer (F5).** `batchDataStore.submitter`. It is the argument of `proveState`'s `ISubmitter.slash` (`calls[1]`, Rollup.sol:806), after `guards[7]` (:603) authenticates the batch.

**Pins (F6).** Two pins of `batchBlobVersionedHashes`:
- `commitState` `writes[2]`: the copy itself, Rollup.sol:359;
- `commitBatchWithProof` `writes[2]`: the branch under a nonzero stored word.

Its fresh writers are `commitBatch` and `importGenesisBatch`. `finalizeBatch` clears it.

**Attribution laws (F7).** Two:
- the `commitState` pin, which records the caller;
- the `commitBatchWithProof` pin, which records 0.

**Premises (F8).** `hyp:Hyp-Z0-kzg` goes on the `commitBatch` and `commitBatchWithProof` kernel laws: their records hold ZERO_VERSIONED_HASH as a literal. Every FACT law has `blobs_wf`, plus `cf:<h>` and `nz:<h>` for each hash binder.

**Measure (F9).** F(Z, derivation) = 1 bit. At versions 0 and 1, the committed blob word ZERO_VERSIONED_HASH comes from two delivered lists, `[]` and `[ZERO_VERSIONED_HASH]`. Every other fiber holds one list: one blob at most below version 2 (Rollup.sol:915), and keccak256 of the list at version 2 (injective under CF). So max fiber = 2 and F = log2 2 = 1.
- `commitBatchWithProof`: 1 bit (its fresh branch).
- `commitState`: 0 bits (Rollup.sol:276 admits only `[]`).

## Goal and deliverables (summary; the contract has the details)

- **`holon/rules/fact.py`** (F1–F8) and **`holon/measures_fact.py`** (F9), generic: no action, family, member, contract or law id. `python -m holon fact` writes `gen/<M>/fact/<model>.json`, with `--facts`, `--classify` and `--backtest`.
- **Rule FACT** in the rules registry, with subforms `kernel` and `attribution`, in catalog **holon-rules/1.5**. The catalog holds every earlier M3 producer as the same objects: I24's PAR (1.1), I30's SORT, I27's UNDO (1.3) and I31's DISCH (1.4). I25 adds no catalog version (its prereg `733b947`, rule L-G1), so 1.5 is the next free number.
- **The `fact` IR term** (additive, ref `fact:<id>`).
- **The FACT section** `gen/M3/fact/models/<model>.fact.bend`, over I30's typed model, imported and never copied. It holds blobs, the commitment read, the generated chooser companions, `run_fact`, `fact_<x>` and `fhit_<x>`.
- **`holon.gen.mproofs.product`**: the product program. Its routes are fixed: `guard` and `injective` for kernel laws, `provenance` for attribution laws. A product program over the term budget (I30's law_terms, 1000) stays UNKNOWN, with its size recorded.
- **Refutation:** search K1 for kernel laws and the attribution search with its consumer continuation, using the sidecar's budget and time candidates.
- **Replay:** `replay/M3/fact/report.json` through the I20 step harness. G6 binds every REFUTED FACT record to a passed entry.
- **Records**, with `fact.hypotheses` (rule H1), `unconditional`, `impact_conditional_on`, `route` and `term_size`. A law whose premise or witness rests on a hypothesis that did not pass (failed, or untestable like HypV-proof1) is never presented as unconditional. A PROVED law's `term_size` is I30's measure, recomputed by the tests from its law and proof files.
- **The Thm 6.8 classification** and **the back-test against M1** (witness transfer plus the CF(agg, S) bridge, by computation).
- **The sensitivity checks** S1–S3.
- **`docs/iterations/I26.md`**, with a prediction table.

## Predictions (key I26 in `spec/M3/predictions.json`)

| id | claim (short; the key has the full text) |
|---|---|
| P1 | One commitment, `committedBatches`: 4 sites, 7 authenticating reaches. Delivered data at the 3 commits. One attribution consumer: `batchDataStore.submitter` via `proveState`'s slash. Two pins. 5 FACT basis elements, as in `fact_basis.json`. |
| P2 | `holon derive` emits exactly the 5 FACT laws, with the contract's IR, binders, premises and refs. `hyp:Hyp-Z0-kzg` appears exactly on the `commitBatch` and `commitBatchWithProof` kernel laws. |
| P3 | **F(Z, derivation) = 1 bit** (`commitBatch`; max fiber `{[], [Z]}` at versions 0 and 1); `commitBatchWithProof` 1 bit; `commitState` 0 bits. |
| P4 | The `commitBatchWithProof` kernel law is REFUTED (fresh branch, `[]` vs `[Z]`). The `commitState` kernel law is PROVED (guard route, inhabited, within the term budget). |
| P5 | **O25/N3.** The `commitState` attribution law is REFUTED by the chain: [S1 `commitBatch` k, owner `revertBatch`]; S2 `commitState` k; then [`challengeState`, timed-out `proveState`], whose real slash passes S2. It replays. It is conditional on Hyp-ISubmitter (fails, F-M2-40). |
| P6 | The `commitBatchWithProof` attribution law is REFUTED: the stored-branch recommit records address(0) (O20 under the pin). t = []. |
| P7 | Every REFUTED FACT witness (4) replays on the real Rollup, in holon's report and in the independent replay. |
| P8 | Thm 6.8: kernel bits [1, 1, 0] agree with [REFUTED, REFUTED, PROVED]. In total: 1 PROVED, 4 REFUTED, 0 UNKNOWN. |
| P9 | H1 in every record. The `L_fact_Z` analogue lists Hyp-ISubmitter (witness, fail), Hyp-Z0-kzg (premise, pass) and HypZ (interpretation, fail): it is not unconditional, and its impact is conditional on HypZ. The `commitBatchWithProof` kernel law lists HypV-proof1 (witness, untestable): not unconditional. The `commitState` kernel law is unconditional, with impact conditional on HypZ. |

**Regressions.**
- R1: Gates M0–M2 pass. M1's `L_fact_Z` (REFUTED; its statement hash and witness) and I20's differential row are unchanged. No commit that writes an I26 outcome path touches an M0–M2 input or output or a frozen root (checked from git).
- R2 (the plan's regression): the parametric `L_fact_Z` analogue `L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash` (premises CF, NZ, blobs_wf and Hyp-Z0-kzg) is REFUTED by `[]` vs `[ZERO_VERSIONED_HASH]`. Its implication to `L_fact_Z` checks: the moved witness refutes `L_fact_Z` on the M1 model (Bend), and CF(agg, S) over `{[], [1]}` is checked by computation (1000 ≠ 1002). The row is accepted by "witness".
- R3: earlier M3 records keep their statuses, and their laws change only in `rule_catalog_version`.
- R4: construction checks, among them:
  - the instruments;
  - the catalog;
  - generic code;
  - determinism;
  - derive's byte-for-byte reproduction;
  - records;
  - independent Bend checks;
  - taint;
  - S1–S3;
  - the partial gate G1, G6, G11V on a copy;
  - the chain instrument on the real Rollup.

## Deviations from the plan, decided at the prereg (state them in the report)

1. **The attribution law compares the bonded party with the content's chooser.** It does not compare it with the commitment. A plain kernel law (committedBatches × submitter) would be refuted by two submitters each committing the same content: a benign witness. The plan's "whose bond is at risk on a recommit, against who chose the content under the BVH pin" is stated through a generated writer-provenance ghost (chooser), per pin site (§7.3, Prop 6.19). Its consumer continuation makes "at risk" concrete: the slash call's argument.
2. **The second pin site gives a second attribution law.** `commitBatchWithProof`'s stored branch records address(0), O20's implicit role. The rule derives it, and it is predicted (P6), not dropped.
3. **Consumers are the delivered data and the principal-keyed call**, as App. B's CONS edges are. On-chain registers bound by the header are not FACT consumers here (gap G3). O23 and O24 are not derivable on the adopted documents (G1, G2).
4. **The derivation consumer is the delivered blob list.** ParseBatch's output is not on the rollup document (G4). HypZ, its decoder's hypothesis, fails (F-M2-41, T2). Every record over that consumer carries `impact_conditional_on: ["HypZ"]`.
5. **Hyp-Z0-kzg is a closed premise**: the document constant equals the recorded KZG hash of the zero blob. It is what makes `[ZERO_VERSIONED_HASH]` "the zero blob". It passes (I3, I21).
6. **"Implication via CF(agg, S) by computation"** is FB2 (witness transfer on the M1 model) plus FB3 (CF of M1's agg stand-in on the moved blob lists, decided by evaluation), as I24's lead decision Q1 accepted witness transfer for REFUTED pairs.

## Rules

- **AGENTS.md is binding.**
  - Never edit `facts/`, `spec/M1/`, `spec/M2/facts/`, `spec/M2/lib/`, `laws/M0`–`M2`, `gen/M0`–`M2`, `results/M0`–`M2`, `replay/M1`, `replay/M2`, `gen/M3/sorts/` or a frozen file.
  - Do not edit another key's instruments: `tests_m3/_m3.py`, `_i24*.py`, `_i31*.py`, other keys' fixtures.
- **Q19.** No hand-written fact document is read by `holon fact`, `derive`, `run` or `replay` for FACT. The back-test alone reads `laws/M1/L_fact_Z.json`, `results/M1/L_fact_Z.json` and the M1 model.
- **No special-casing.** `holon/rules/fact.py` and `holon/measures_fact.py` name no target identifier. No file under `holon/` names an I26 law id or fact id.
- **The real contract decides replay.** A witness that does not replay is a model defect (§9.6), never a pass.
- **No tuning, no skips.**
  - The sidecars, the routes, the search budget and the term budget are fixed.
  - A missed prediction is a Surprise, with its evidence.
  - A Thm 6.8 disagreement is a Surprise.

## Outcome paths, narrowly

`laws/M3/L_fact_`, `results/M3/L_fact_`, `gen/M3/laws/L_fact_`, `gen/M3/proofs/L_fact_`, `gen/M3/L_fact_`, `gen/M3/fact/`, `results/M3/fact/` and `replay/M3/fact/`. Every commit that writes any of them must descend from this prereg commit.

Some files are written by several M3 keys. They are not I26's outcome paths, and the audit does not order them for I26:
- `laws/M3/REGISTRY.json` and `DERIVATION.json`, and the re-versioned earlier M3 laws;
- `results/M3/summary.json`, `deps.json`, `metrics.json`, `gate_report.json`;
- `spec/bindings/M3.json`, `gen/M3/coverage.json` and `gen/M3/core/`;
- `spec/schemas/law_ir_0_3.schema.json` and `result_record_v2.schema.json` (the additive `fact` term and record field).

Merge them by hand with I24, I25, I27, I30, I31 and I41.

## Coordination

- **Merge order: I25, then I26.** Union the M3 keys of `spec/M3/predictions.json`.
- **I30, I27 and I31 are built in parallel.** I26 binds to their preregistered contracts (prereg `499c70b`, `cb928cf`, `4827d1c`):
  - I30's typed model, Reach, witness format, search stages, hash binders and replay;
  - I27's continuation and NZ;
  - I31's time candidates.
- **Adding FACT bumps the M3 catalog.** Every earlier M3 law's `rule_catalog_version` (hashed) changes. Record this as the statement lifecycle requires; R3 checks that nothing else moves.

## Risks and fallbacks

- **commitBatchWithProof needs the rollup delay, a header that hashes to the new commitment, and a proof the stand-in verifier accepts.** If the search budget does not reach a successful step, P4 (refutation half) and P6 are UNKNOWN with their bounds. This is the same capability I27-P6 assumes. Never widen the budget after a result.
- **The guard-route product proof for `commitState`** must unfold the check chain up to Rollup.sol:276. If it exceeds the term budget, the law is UNKNOWN with its size, and P4 (proof half) and P8 miss. The proof is never weakened by a premise.
- **Kernel cost.** A counter-law that Bend accepts but BendTT cannot check within budget is recorded with its kernels as they are, and the miss is reported.

## Questions for the human (raised by the prereg)

1. **Conditional findings.** O25 (and the `L_fact_Z` analogue) rest on the binding's ISubmitter stand-in, whose hypothesis fails (F-M2-40). The records say so (`unconditional: false`). Is an extraction of the real Submitter (I36) required before O25 counts toward the M3 exit?
2. **Witness-only hypotheses.** H1 marks a law not unconditional when its witness uses a stand-in whose hypothesis fails, even if the law's statement does not mention it. That is the stricter reading. Should "unconditional" consider premises only?
3. **The catalog number.** holon-rules/1.5, the next free number: I25's prereg (`733b947`) adds no catalog. The key fixes 1.5; if another key takes 1.5 before I26 merges, that collision goes to the human (the key is never edited). Should catalog versions be assigned at merge time instead (I27's Question 3)?
4. **Untestable witness hypotheses.** H1 also marks a law not unconditional when its witness rests on a stand-in whose hypothesis is untestable (HypV-proof1: no prover exists here), as for the `commitBatchWithProof` kernel law. Is that the intended reading?

## Before committing

Run every suite: `tests`, `tests_m1`, `tests_m2` and `tests_m3`. Then run `holon gate` for M0, M1, M2 and M3, `python tools/freeze.py check`, and `python -m holon audit prereg` for M2 and M3.

Write `docs/iterations/I26.md`, with Done, Surprises, Questions for the human and Not done. Include:
- the commitment and consumer tables;
- the measures with their fibers;
- the outcome table, with witnesses, replays, hypotheses and kernel times;
- the back-test row;
- S1–S3;
- the gate lines.
