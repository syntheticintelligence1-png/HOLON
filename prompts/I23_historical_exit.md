# I23: historical inputs and the M2 exit evaluation

Rendered from `docs/BUILD_PLAN.md` §4 I23 (whitepaper §8.7 source 4, Def 4.7 ρ(e), §12.1 "Behaviour", §13 "refinement disagreement rate", §15.2 M2 exit (a)). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact outputs, formats, CLIs and rules are in the docstring of `tests_m2/test_historical_exit.py`.

The instrument is `spec/M2/lib/historical_exit.json`. It is frozen: the test pins its sha256. It holds:
- the two historical windows;
- the deployed implementation and the pinned build it is compared with;
- the in-scope transactions and their input facts;
- the codec corpus and the M0 laws' premise inhabitants among the real headers;
- the supplementary acquisition (only what I59 lacks);
- the expected explained classes, each with its I16 mechanical criterion, and the target of 0 unexplained;
- the synthetic smoke corpus.

Its `computation` field shows how every value was computed from I59's committed outputs (`index.json`, `replay.json`) and the I59 snapshot's own transaction and receipt objects. BUILD_PLAN names `spec/M2/preregistration.json`; a prereg commit may only add files under `spec/M2/lib/`, hence the path.

## Goal

The human called on-chain replay make or break (Q5). I59 fetched the whole history (124 213 logs, 124 211 transactions and receipts, 62 192 KZG-checked blobs) and replayed the header decoders on it. I23 finishes the job:
- it replays the real inputs through every edge the M0 and M2 laws use;
- it records the agreement volume and every classified disagreement in refinement records (Def 4.7);
- it evaluates M2 exit (a), "zero unexplained replay disagreements over a historical window", and writes the exit report.

The report is honest either way. A disagreement is classified by I16's mechanical links, or it stays unexplained and exit (a) is not met.

## The two windows

- **Codec window**, I59's whole window `[19426587, 26179508]`. Every one of the 62 172 real parent headers goes through the header carrier's edges on the frozen M0 header model:
  - `dec_go`, `ok_go` and `ok_sol` are I59's comparisons, not re-run;
  - `enc_sol`, `enc_go_v0` and `enc_go_v1` run on the 59 218 decodable headers against their own implementations, through I16's binding and harnesses.
- **Trans window**, `[26031670, 26179508]`: the live period of the implementation the proxy's last Upgraded event installed (block 26 031 669, `0x213ce22b…`). Its 3414 transactions are stepped in chain order through I20's extracted rollup model: 1695 `commitBatch` and 1719 `finalizeBatch`, one per block, all from one sender.
  - The real side is the chain itself: the receipt's status and logs, and the proxy's storage at the parent block and at the step's block.
  - The model's state is threaded through the whole window from the chain's storage at block 26 031 669 (the instrument's `storage_rule`). A slot is never re-read from the chain at a step's parent block, because that would silently heal a write the model missed. After the last step, every slot the replay touched is compared with the chain at the window's end.
  - External calls are answered by `eth_call` at the parent block. Each answer is also fetched at the step's block, as a stability check (`call_stability`), never as an answer.
  - Transactions before the window ran other code. They are never stepped through the extracted model, and their headers are in the codec window.

## Scope against whitepaper §8.7 source 4

- **"Every past commit's calldata, and its blobs where archived."** Every commit's parent header goes through the codec window. Every commit and finalize of the deployed implementation's live period goes through the trans window. The 60 477 commits before the last upgrade ran other code: their headers are replayed, their transitions are not.
- **"Compared with the stored commitments."** The CommitBatch and FinalizeBatch logs (P4, P5) and the stored batch hashes and roots (P6). I59's parent linkage and KZG checks are kept as regressions.
- **"And the node's derivations."** This is I21-P13's: auditor A2 runs the node's `UnPackData` and `ParseBatch` on I59's 62 172 commits. I23 does not duplicate it. `exit_a.coverage` lists `CONS.blobs_of` as not replayed, with that reason.

## When it runs

After I20 is merged. I23 uses, unchanged:
- I20's model and step semantics, with clause 7's observables;
- the frozen M0 model;
- I16's harnesses and binding;
- I59's `holon.historical`.

It does not wait for I21 or I22. Exit (b) is read from I22's `mutation_adequacy` metric when it exists, and is `pending` otherwise. I23 never computes it.

## Deliverables (summary; the contract has the details)

- **`python -m holon historical fetch-state`.** The supplementary acquisition, into the I59 snapshot, indexed in `results/M2/historical/supplement.json`. It fetches:
  - block headers;
  - the proxy's storage at `b - 1` and `b` for every slot a step reads or writes, and at the window's start and end for every slot the replay touches;
  - `eth_call` answers at `b - 1`, and the same calls at `b` (stability check);
  - the implementation's code and the proxy's implementation slot at `to_block`;
  - the proxy's logs of other topics over the trans window, with their transactions.

  It never refetches anything I59 indexed. `--offline` re-indexes from the snapshot.
- **`python -m holon historical codec`** writes `results/M2/historical/codec.json` and the six codec records under `results/M2/refinement/historical/`.
- **`python -m holon historical trans`** writes `results/M2/historical/trans.json` and one record per stepped action (`commitBatch`, `finalizeBatch`).
- **`python -m holon historical laws`** writes `results/M2/historical/laws.json`. For each `laws/M0` law and each `results/M2/L_*.json` record it gives:
  - the historical evidence of its edges;
  - premise inhabitants (M0);
  - realizations of REFUTED laws;
  - site reach (M2).
- **`python -m holon historical smoke`** writes `results/M2/historical/synthetic_smoke.json`: the six morph fixtures, labelled `synthetic_smoke`, never counted.
- **`holon metrics`** gains `refinement.historical`. GREF (`holon.refinement.check_disagreements`) reads the historical records; today it globs `results/M2/refinement/*.json` only, so a test plants an unlisted id in a scratch copy and GREF must report it.
- **Refinement records** carry ρ(e)'s reference to the implementation code (Def 4.7), and every new disagreement entry carries `"milestone": "M2"`, so the metric counts it.
- **`python -m holon historical exit [--check]`** writes `results/M2/m2_exit.json` and `docs/M2_EXIT.md`, generated from the metrics. `exit_a.coverage` lists the diagram edges the window replayed, and maps every other CODEC, CONS or TRANS edge of `gen/M2/diagram/` to why it was not replayed (for example, the hand abstraction's TRANS edges, the actions no in-scope transaction calls, and `CONS.blobs_of`).
- **`tools/fetch_historical.py`** (for the human, where RPC is allowed) and **`tools/historical_bigquery.sql`** (the BigQuery alternative; not run without credentials).
- **`docs/iterations/I23.md`**, with a prediction table.

## Predictions (key I23)

| id | claim |
|---|---|
| P1 | The runtime code at `0x213ce22b…` equals the pinned solc build of `Rollup.sol` at `3e44e795` under one of the checkout's two declared compiler configurations, immutables masked. |
| P2 | The trans window holds no Rollup log outside I59's five topics. All 3414 transactions are stepped, none unsupported, with exactly 3467 external calls: `isActive` 1695, `getFirstUnfinalizedMessageEnqueueTime` 1695, `getCrossDomainMessage` 40 (each commit at exactly the queue indices its calldata and parent imply), `popCrossDomainMessage` 37. |
| P3 | The model's status is ok on all 3414, as on chain. This includes the 179 finalizes of batches 60 299..60 477, whose storage the legacy implementation wrote. |
| P4 | All 1695 `CommitBatch(k, h)` logs are reproduced, topics and data equal to the snapshot's receipts. Each h is the model's own batch hash, including the dataHash over 40 real L1 message hashes and the version-2 blob hash. |
| P5 | All 1719 `FinalizeBatch` logs are reproduced, topics and data equal to the snapshot's receipts. |
| P6 | 0 storage differences. The model's state is threaded from block 26 031 669; it is compared before and after every step, and on every touched slot at the window's end. |
| P7 | Exactly 37 finalizes call `popCrossDomainMessage`. Every step's pop calls equal the queue's `DequeueTransaction` logs in its receipt (indices 27 647..27 690, 44 messages). |
| P8 | The real encoders agree with `enc_sol` (59 218), `enc_go_v0` (17 277) and `enc_go_v1` (41 941) on real headers: 0 disagreements. |
| P9 | Go re-encoding reproduces all 17 277 legacy 249-byte v0 headers and all 34 101 v1 headers byte for byte. On all 7840 v2 headers it differs in exactly cell 0: L_par_hdr_v2 realized on mainnet bytes. |
| P10 | L_par_hdr_ssvh is realized by all 34 101 v1 headers, and L_par_hdr_v2 by all 1694 inhabitants of its premise. |
| P11 | No M2 site or width obstruction is realized:<br>• the REFUTED :363 site is reached by no commit;<br>• the REFUTED :636 site is reached by all 1719 finalizes, with no Panic;<br>• the two width sites (I20-P2/P3) are reached by all 1695 commits, in width. |
| P12 | No historical disagreement of any class in either window, and no `D-historical` entry in `spec/M2/disagreements.json`. |
| P13 | M2 exit (a) is met over both windows, with 0 unexplained. |

**Regressions.**
- Gates M0, M1 and M2 pass.
- I23 changes no law, statement, facts document, extracted document, model or status.
- I59's outputs are byte-identical: `dec_go`, `ok_go` and `ok_sol` are I59's 62 172 comparisons with 0 disagreements, and L_dom_hdr is realized by I59's 2954 281-byte headers.
- The blob fallback runs on 0 blobs.

**Construction checks.**
- The instrument's values follow from I59's committed outputs. That includes the premise inhabitants:

  | laws | inhabitants |
  |---|---|
  | L_par_hdr_v0, L_rt_go_v0 | 1 (only the genesis header) |
  | L_par_hdr_v1, L_rt_go_v1 | 0 |
  | L_par_hdr_v2, L_rt_go_v2 | 1694 |
  | L_par_hdr_ssvh | 34 101 |
  | L_dom_hdr | 62 172 |

- The instrument's in-scope input facts are recomputed from the snapshot's own transaction and receipt objects.
- The supplement fetches only what I59 lacks, and covers what the replay needs: a header per block, call answers with their stability checks, initial and final storage, and the implementation's code.
- The records are well formed, with ρ(e)'s implementation reference. GREF passes, and is shown to read the historical records.
- `laws.json` edges match what the M0 statements call and what the M2 cones name.
- The smoke fixtures are labelled and never counted.
- The tools exist.
- The exit document lists the replayed and the not-replayed edges, and is reproduced by `--check`.
- Every output is byte-identical across runs.

**Report these plainly in `docs/iterations/I23.md` and `docs/M2_EXIT.md`, whatever the predictions do.** The PROVED v1 codec certificates (L_par_hdr_v1, L_rt_go_v1) hold over a domain that no mainnet header occupies: every real v1 header has a nonzero sequencerSetVerifyHash. The v0 ones cover only the genesis header. A certificate is "relative to 𝔅(𝔇) with this refinement evidence" (§12.1), and this is that evidence.

## Disclosure

While drafting this prereg, the drafter read:
- I59's committed outputs and report;
- the I59 snapshot's transaction and receipt objects in the trans window: selectors, sender, blob counts, versions, `numL1Messages`, the parent headers' `totalL1MessagePopped`, and the receipts' logs (batch indices, the queue's `DequeueTransaction` data);
- the last Upgraded log;
- the pinned checkout's sources, compiler configurations and fixture file.

The drafter also probed `gateway.tenderly.co/public/mainnet` once each:
- `eth_getCode` of the proxy at block 26 032 693;
- `eth_getStorageAt` of the proxy's implementation slot at block 26 032 692, which held `0x213ce22b…`;
- `debug_traceTransaction`, which was refused (rate limit). It does not exist on `ethereum-rpc.publicnode.com`.

No model, harness or compiler was run. No implementation code, block header, step storage or call answer was read. No prediction's outcome was computed.

The adversarial reviewer of this prereg read the following, and made no network request:
- the same snapshot objects, to recompute every in-scope value of the instrument (all equal);
- `index.json` and `replay.json`, to recompute the codec corpus and the premise inhabitants (all equal);
- the I20 branch's two width records, for their format only: `width_site.span` lies in `BatchHeaderCodecV0.sol` (:144 `batchIndex`, :166 `totalL1MessagePopped`), and they have no `site`;
- `holon/refinement.py` and `holon/metrics.py` at `f8fa447`;
- the pinned checkout's `Rollup.sol` and `batch_header.go`.

The reviewer changed the storage observable, made the event, status and queue checks independent of the outputs' flags, made the GREF check non-vacuous, and added the coverage report. The instrument's `storage_rule` and the call-stability kind were added by the reviewer; no value in the instrument changed.

## Rules

- **AGENTS.md is binding.** Never edit any of these:
  - `facts/`, `laws/`, `spec/M1/facts/`, `spec/M2/facts/`;
  - I59's or I20's outputs;
  - the pinned checkout.
- **The real sides are fixed.** They are the chain and the real code, through I16's binding and the instrument's sources. `tests/reference` is never imported from `holon/`.
- **No value is assumed.** No storage slot is read as zero and no call answer is guessed. A missing value makes the step unsupported, which is a status disagreement, never a skip.
- **Classes come from links.** A disagreement is classified by `holon.refinement` links only, never by a label or by prose.
- **Cross-edge differences are realizations.** A cross-edge difference realizes a REFUTED law. It is listed in `laws.json` and is never a refinement disagreement.
- **No tool changes.** I20's model, I16's harnesses and I59's modules run unchanged. A defect found in one is a Surprise. Its fix is an `extraction_defect` with a fix commit and a green rerun.
- **No moving goalposts.** The windows never move and the target stays 0 unexplained. A miss is a Surprise reported with its evidence, and exit (a) is then reported not met.
- **No skips.** A missing snapshot, network, toolchain or I20 output is a failure with a clear message.
- **No secrets in any output.** Never commit or print `~/.holon/secrets`. The secret test checks the outputs against those values and names only the file, never the value.
- **The tests read the I59 snapshot themselves.** They check the model's events, the receipts' status and the queue calls against the snapshot's receipts, independently of the outputs' own `agree` flags. A missing snapshot fails them; it never skips them.
