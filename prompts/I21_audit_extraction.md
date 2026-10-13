# I21: A2/A4 audit round on extraction (audit round M2/2)

Rendered from `docs/BUILD_PLAN.md` §4 I21 (whitepaper §9.5 auditors A2 and A4, §9.6 finding filter, Def 4.1 and §8.3 R^ext, §12.3 L21, L5, L19). Read `AGENTS.md`, `docs/M0_SPEC.md` and `docs/BEND_PRIMER.md` first. The exact outputs, formats, CLIs and rules are in the docstring of `tests_m2/test_audit_extraction.py`. The instrument is `spec/M2/lib/audit_round2.json`. It is frozen: the test pins its sha256, and its `doc` field shows how every value was computed from committed artifacts.

The prereg sits on the project branch at `90153fd`. That is after the I19 follow-up (A19), which regenerated the rollup and Go documents and `gen/M2/coverage.json`, and after I59, whose committed `results/M2/historical/replay.json` fixes the real inputs of the `go_consumer` surface.

## Goal

I22 relies on the extraction. Before it does, attack the extraction:
- **Auditor A2, hostile input.** Feed hostile inputs to every interface carrier through public entry points. Check that the partiality the extractors recorded (I17, I18, I19 with A19, and I20's model) matches the real code's.
  - This includes the header carrier's Go consumer, the node's derivation.
  - That consumer is fed I59's 62 172 real mainnet commits.
- **Auditor A4, vacuity and over-strength.**
  - Check that every premise is satisfiable and every inhabitant representative.
  - Test every hypothesis in `results/M2/hypotheses.json` against the real oracle, or label it untestable.

## When it runs

After I20 merges. The round audits one commit of the project branch, its `target_commit`. That commit holds I20's outputs, and every repository input is read from its tree. Nothing here runs before then.

The `go_consumer` surface also reads I59's snapshot (`~/.holon/historical`, outside the repository). Each object is checked against its sha256 in `results/M2/historical/index.json`. A missing snapshot fails the run, and `--check` fails too: it never skips.

## Roles

1. **A fresh auditor session.** It is the same model family (Q9 default, `docs/HUMAN_ANSWERS.md`).
   - It writes the two instruments: `holon/audit/hostile.py` (`python -m holon audit hostile`) and `holon/audit/vacuity.py` (`python -m holon audit vacuity`), plus their harness sources under `audit/rounds/M2/round2/harness/`.
   - It runs them, investigates every mismatch and files the findings.
   - It fixes nothing. It edits no facts, laws, extracted documents, generators or tests.
2. **Fix sessions.** Every high finding is fixed before I22 starts, each fix with a test (P6). Medium and low findings get a `fix_iteration`.

## Deliverables (summary; the contract has the details)

- `audit/rounds/M2/round2.json`. It is valid against the unchanged `spec/schemas/audit_round.schema.json` and labelled `same`, with `counts_toward_convergence: false`. It has the attacks A1–A11 from the sidecar:
  - A1–A6 are model_vs_code, one per surface: `sol_loader`, `sol_encoder`, `go_header`, `go_encoders`, `rollup_act`, `batchdata_act`;
  - A7 is vacuity;
  - A8 is bindings_ledger, for the hypotheses;
  - A9 is mutation_adequacy: the instruments' own planted mutants and canaries;
  - A10 is determinism;
  - A11 is model_vs_code for the `go_consumer` surface. It was added at the rebase onto `90153fd`, so the ids of A1–A10 are unchanged.
- `audit/rounds/M2/round2/a2.json` and `a4.json`, from the two CLIs. Both are canonical and byte-identical across runs. `--check` rebuilds each from the target commit's tree.
- `audit/M2_round2.md`, the prose round.
- New lines in `audit/M2_findings.jsonl` (`"round": "M2/round2"`). The line of F-M2-36 is updated with its resolution: it is assigned to I21, and A1–A4 reproduce or refute it.
- `docs/iterations/I21.md`, with a prediction table that gives pass or miss for each id.

**Two deviations from the plan text, both forced by committed facts.**
- **The round is `round2.json`, not `round1.json`.** `audit/rounds/M2/round1.json` already holds audit round M2/1, the I6–I13 audit.
- **Findings go to `audit/M2_findings.jsonl`, not `audit/findings.jsonl`.**
  - The preregistered I5 tests in `tests_m2/test_audit.py` require every id in `audit/findings.jsonl` to match `^F-M[01]-\d{2}$`, and allow no medium or high finding in the vacuity or determinism categories there.
  - Round M2/1 started the separate M2 file. That file is shared and append-only, and other lanes also append to it. So it is not an outcome path of I21, and the round's lines are identified by their `round` field.

**Target findings are not HOLON findings.** Some real code behaves as the extracted documents say but is an obstruction between the languages. When it is shown through public entry points on reachable inputs, it is a *finding* in the sense of whitepaper §9.6, and it goes into `a2.json` `target_findings`.
- It is not a line of `audit/M2_findings.jsonl`, and it does not block I22.
- It is reported in the prose round and in `docs/iterations/I21.md`, so that the human can decide on an upstream report.
- If the auditor judges that HOLON's model should have stated it and does not, that gap is a separate HOLON finding.

## Predictions (key I21)

They were made by reading three things, without running any hostile input:
- the code at the pinned commit `3e44e79`;
- the extracted documents (after A19), the diagram, `results/M2/` and I59's committed replay;
- the whitepaper.

| id | claim |
|---|---|
| P1 | **Solidity loader.** The 2561 hostile headers go through each of the 9 non-dominated `_loadBatchHeader` call sites (:230, :259, :277, :402, :414, :433, :600, :627, :716) by their public functions. The real contract accepts or rejects exactly as the extracted `load_sol` path, with its revert reason, and as the frozen `ok_sol`. That is 0 mismatches, with exactly the 4 extracted reasons. |
| P2 | **Go decoders.** On the same 2561 inputs, the 16 exported `BatchHeaderBytes` methods of `common/batch` and the 15 of `node/types` match their extracted paths: the error, and the decoded value on a nil error. `validate` and the getters match the frozen `ok_go` and `dec_go`. That is 0 mismatches and 0 panics. |
| P3 | **CODEC labels.** Of the 4 CODEC edges of `gen/M2/diagram/morph_header.json`, exactly `CODEC.enc_sol` has a `partial` label that the code contradicts (F-M2-36 reproduced). |
| P4 | **Solidity encoder.** The 1024 encoder inputs go through the three commit entry points. They match the extracted `enc_sol` exactly (:293, :294, :295). The frozen `enc_sol` mismatches only at versions 0..2 with a zero state root: 9 inputs per entry point, 27 in all. Versions 3..255 meet its UNDEF sentinel. |
| P5 | **Rollup Act carrier.** Every model/code disagreement over the hostile calldata corpus, against I20's model, is explained by a stated assumption of the extracted document or by a coverage-debt entry. That is 0 unexplained. An implicit-class disagreement names one of the exemptions of the A-implicit that A19 narrowed: dynamic calldata decoding, a narrow array element, or out of gas. |
| P6 | **BatchData.** The open site `common/batch/batch_data.go:75:36:slice` (`DataHash`) is a reachable panic from `NewBatchData`, through exported calls only. |
| P7 | **Go sites.** No hostile or real input panics at a site the Go documents mark safe. This covers the `go_header`, `go_encoders`, `batchdata_act` and `go_consumer` surfaces. |
| P8 | **Satisfiability.** Every PROVED premised law (an `assume` premise or a `Reach` binder) in `results/M2/` and `results/M2/extracted_m1/` has an inhabitant that replays on the compiled model, with its premises holding. |
| P9 | **Representativeness.** The degenerate rule (initial state, or a SORT-site subtrahend of 0) marks 5 of the 6 PROVED SORT-site laws' recorded inhabitants degenerate:<ul><li>the two `def_bvh_at` laws and `def_w`, which sit at the initial state;</li><li>`rollup_441` and `rollup_485_495`, where lfi = 0.</li></ul>`rollup_644_660` is not degenerate. |
| P10 | **Hypothesis coverage.** Every key of `results/M2/hypotheses.json` (at least the 12) is tested against a real-oracle implementation outside `holon/` and `tests/`, or labelled untestable with the missing piece named. |
| P11 | **Passing hypotheses.** CF-agg (at least 273 samples), CF-hdr (at least 768 headers, Solidity = Go), Hyp-Z0-kzg (the KZG library of the pinned Go module graph) and Hyp-messenger (the real messenger and queue) are tested and pass. |
| P12 | **Submitter.** Hyp-ISubmitter fails against the real `Submitter.sol`. `withdraw`, `removeSubmitter`, `setMinimumStake` and `updateChallengeDeposit` move `isActive` or `challengeDeposit()` in ways the M1 stand-in rules out. It is filed as a finding. |
| P13 | **Derivation consumer, real inputs.** I59's 62 172 commits go through `(*Derivation).UnPackData`, then `(*BatchInfo).ParseBatch`.<ul><li>UnPackData returns a nil error for all of them, by selector: `0xd63b3549` (7574, `legacyRollupABI`, derivation.go:639), `0x4a8d544f` (12 656, :617), `0x428868b5` (40 247) and `0x41f756da` (1695). Each parent header hashes to I59's recorded parent keccak.</li><li>ParseBatch rejects at `batch_info.go:92:55` (BatchIndex) exactly the 2954 commits of batches 2..7575 whose parent is a 281-byte version-0 header. Of these, 2953 are under `0xd63b3549` and 1 (batch 7575) is under `0x4a8d544f`.</li><li>No commit is rejected at :96:69.</li><li>The pinned Solidity loader accepts all 2954 parents.</li></ul>Recorded as one target finding, in bin `finding`, realizing L_dom_hdr: a node that derives from L1 stops at batch 2. |
| P14 | **Derivation consumer vs its extraction.** The header corpus is placed inside calldata under each of the 4 selectors (4 × 2561 inputs), together with the real commits.<ul><li>UnPackData returns each header unchanged with a nil error. It panics at none of its 5 open sites.</li><li>ParseBatch's header step rejects exactly what the extracted BatchIndex and TotalL1MessagePopped paths and `ok_go` reject, never at the TotalL1MessagePopped step.</li></ul>That is 0 mismatches. |
| P15 | **Representatives exist.** For each of P9's 5 degenerate laws, a breadth-first search over runs of at most 6 actions finds an inhabitant with a non-empty run and a nonzero subtrahend. It replays with its premises holding. So none of them is a vacuity finding. |

**Basis for the less obvious claims.**
- **P5 rests on I20 and A19.**
  - I20 targets every guard reach with its boundary corpus (I20 contract, clauses 7–9).
  - Since A19, the extracted document records panics, calls with their `callok`, callvalue, calldatasize and ABI range checks.
  - Its A-implicit exempts only dynamic calldata decoding and the range of narrow array elements. It also says that out of gas is not a check.
- **P6.** `Append(nil, nil, nil)` leaves `blockContexts` with capacity 0 and `blockNum` 1. `DataHash` then slices `[0:58]`.
- **P9.** In the I15 records, the inhabitants of `def_bvh_at` ×2 and `def_w` have an empty run. Those of `rollup_441` and `rollup_485_495` follow one `commitBatch` from the post-genesis state, so lfi = 0. `rollup_644_660`'s subtrahend is the constant 1. I20 re-derives these laws. The inhabitant search is breadth-first and returns the shallowest inhabitant, so the pattern is predicted to survive.
- **P12.** Each of these happens in the real `Submitter.sol`:
  - `isActive` requires `registered && !withdrawing && stakeOf >= minimumStake`;
  - `withdraw()` clears `registered` while the stake stays until `claimWithdrawal`;
  - the owner can change `minimumStake` and `challengeDeposit`.
- **P13.** I59 (Surprise 7) found that the pinned Go `validate` rejects the 281-byte version-0 headers of batches 1..7574, while the chain and the pinned Solidity accept them. The lead then traced the Go consumer:
  - `UnPackData`'s legacy branch ("before remove skipMap", derivation.go:639) passes the parent header on unchanged;
  - `ParseBatch` calls `BatchIndex()` first (batch_info.go:92), and BatchIndex runs `validate`.

  The selectors and counts come from `replay.json`: each legacy parent's `abi_origin` commit's `IRollup.BatchDataInput` (sidecar `doc`, item 10). They were checked against the derivation's own ABIs (`node/types/batch.go`).
- **P15.** Reading the model's guards, non-degenerate runs exist at length 4 or less:
  - `def_bvh_at`: one commitBatch;
  - `def_w`: commitBatch, wait, finalizeBatch;
  - `rollup_441`: two commitBatch, wait, finalizeBatch;
  - `rollup_485_495`: commitBatch, wait, finalizeBatch, commitBatch.

**Regressions and construction checks.**
- **R1.** Gates M0, M1 and M2 pass. The round itself changes no law, statement hash or status.
- **R2.** The round file, the attacks A1–A11, the findings ledger and the target commit are as the contract says.
- **R3.** The sidecar is the preregistered one, and the corpora run are the preregistered ones (including the 4 × 2561 hostile and 62 172 real consumer inputs). Every interface carrier is attacked, and every extracted path is exercised: 6, 5 and 223. Records are well-formed, and degenerate flags follow the rule.
- **R4.** Every planted mutant (at least one on each of the 7 surfaces) and every A4 canary is detected.
- **R5.** `--check` reproduces both outputs from the target commit.
- **R6 (exit).** F-M2-36 is resolved, there are zero open high findings before I22, and `holon audit status --findings audit/M2_findings.jsonl` shows nothing blocking.

## Rules

- **AGENTS.md is binding.** Expectations come from the extracted documents and the compiled models, never from `tests/reference/`. Harnesses run in scratch copies of the pinned checkout.
- **A same-family round** is labelled `same` and does not count toward convergence. Its findings still block (Q9).
- **No tuning.** Never shrink a corpus after a run, and never reclassify a mismatch to fit a prediction. A missed prediction is a Surprise, reported with its evidence.
- **For the human.** Report the P13 target finding, with its reproduction, under Questions for the human. Whether to report it upstream to Morph is the human's decision; HOLON cannot fix the target.
