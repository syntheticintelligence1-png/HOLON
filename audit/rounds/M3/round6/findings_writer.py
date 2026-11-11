import json
RND = "M3/round6 (claude-subagent/M3-round6/2026-11-09, a fresh coordinator-launched agent session (model not recorded), same family, HUMAN_ANSWERS Q9b)"
C = "ed893be8abb2fa2c57804cf32e0cd45de7184fbb"
MUT = (f"python -m holon audit mutation --milestone M3 --round 6 --spec audit/rounds/M3/round6/a1_spec.json --target {C} "
       f"--work <scratch> (pinned checkout /root/work/morph at 3e44e795, clean; 12 mutants, max_law_runs 0, about 12 minutes)")
def F(**k):
    base = {"id": None, "round": RND, "iteration_audited": None, "severity": None, "category": None, "aspect": None,
            "title": None, "reproduction": None, "plan_or_paper_ref": None, "suggested_fix": None,
            "confirmed_by_reproduction": True, "status": "open", "fix_iteration": None, "test": None}
    base.update(k)
    return base
out = [
F(id="F-M3-22", severity="medium", category="mutation_adequacy",
  aspect="PAR round-trip obligations vanish under a decoder offset bug",
  title=("A decoder offset bug deletes the PAR round-trip laws that should refute it: two realistic Go decoder mutants "
         "(BatchHeaderBytes.BatchIndex reading b[2:10], HeightFromBlockContextBytes reading [1:9]) leave M3 with no law "
         "over the mutated decoder, so the codec drift PAR exists to catch produces no obstruction; the A1 driver counts "
         "the deletion as a detection"),
  reproduction=(f"At {C}: {MUT} writes audit/rounds/M3/round6/a1.json. Mutant go_getter_batchindex "
         "(common/batch/batch_header.go:83, b[1:9] -> b[2:10]): derivation.dropped = the six BatchIndex round trips "
         "(L_par_rt_enc_sol_BatchHeaderBytes_BatchIndex_v0/_v1/_v2, L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_BatchIndex_v0, "
         "L_par_rt_BatchHeaderV1_Bytes_BatchHeaderBytes_BatchIndex_v1, L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BatchIndex_v2), "
         "added = []. At C exactly 12 laws name BatchHeaderBytes_BatchIndex (`grep -l BatchHeaderBytes_BatchIndex laws/M3/L*.json`): "
         "those six and the six cross-component codec laws. The kept-tree follow-up (`python -m holon audit mutation ... --spec "
         "audit/rounds/M3/round6/a1_followup_spec.json --keep-trees --out audit/rounds/M3/round6/a1_followup.json`; diff in "
         "audit/rounds/M3/round6/a1_followup/go_getter_batchindex.laws_diff.json) shows the six codec laws drop the decoder from "
         "their decoder list, and the v0 pair drops the premise h.BatchIndex == k.batchIndex, so no law of the mutant names the decoder "
         "(L_fact_pi_Rollup_commitBatchWithProof_BatchIndex only re-reads 'bytes 2..10', and is REFUTED at C already). Mutant "
         "go_blockctx_height (common/batch/encoding.go:24, blockContextBytes[:8] -> [1:9]): dropped = "
         "L_par_gort_BuildBlockContext_HeightFromBlockContextBytes_0/_1, added = [], statement_changed = []; at C these two are the "
         "only laws naming HeightFromBlockContextBytes. Both verdicts read detected ('derivation change: N law(s) dropped'); the "
         "auditor judges both missed: the obligation that would refute the wrong read is gone, and nothing is refuted. Contrast "
         "sol_store_total (an encoder-side offset, BatchHeaderCodecV0.sol:166 add(batchPtr, 17) -> 16): its re-derived "
         "L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned, run with `python -m holon run --milestone M3 --laws "
         "L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0_pinned` in the kept mutant tree, is REFUTED (bend2 and bendtt checked; witness "
         "differs at byte 24), because the codec law compares whole encodings; a decoder-side offset changes no encoding."),
  plan_or_paper_ref="whitepaper §5.1 (PAR round trip, cross-component codec agreement), Appendix E (codec drift), §9.5 A1",
  suggested_fix=("Derive the round-trip and common-decoder obligations from the diagram's parallel paths (an encoder's field and the "
         "decoder that the evidence names for it), not from the E1 layout atoms that exist only where the extracted read range already "
         "equals the field's write range, so a disagreeing pair yields a law that is REFUTED instead of no law. In holon audit "
         "mutation, report a law dropped by the re-derivation as a lost obligation for the auditor to judge, not as a detection.")),
F(id="F-M3-23", severity="medium", category="mutation_adequacy",
  aspect="A1 driver: bundle documents out of reach; 'missed' with a false reason",
  title=("holon audit mutation cannot re-extract the bundle documents gen/M3/bundle/documents/messenger.json and queue.json "
         "(their baseline extraction fails on the sidecar format), yet lists them as reachable and reports every mutant of their "
         "sources 'missed' with the false reason that the frontends extract the same content"),
  reproduction=(f"At {C}: {MUT}. In audit/rounds/M3/round6/a1.json, baseline.documents for both bundle documents reads error "
         "'holon extract solidity (exit 2): holon extract solidity: refused: sidecar <work>/target/gen/M3/bundle/sidecars/messenger.json: "
         "malformed: output is not a repo-relative path ending .extracted.json' (queue.json likewise), reproduces false, while "
         "scope.reachable lists both. Mutants messenger_fee_guard (contracts/contracts/l1/L1CrossDomainMessenger.sol:291, "
         "msg.value >= _fee + _value -> msg.value >= _fee) and queue_enqueue_index "
         "(contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol:377, messageEnqueueTime[_queueIndex] -> "
         "messageEnqueueTime[_queueIndex + 1]) have documents status 'error' (the same refusal) and verdict 'missed', why 'the "
         "frontends extract the same content from the mutant (only the input files' hashes differ): no law can see it': nothing was "
         "extracted on either side. Cause: holon/audit/mutation.py Round.mutant sets status 'error' when the mutant's and the "
         "baseline's extraction both fail, and only 'no_baseline' leads to 'incomplete', so it falls through to the 'not changed' "
         "branch. The 15 decided laws over these two documents (packet auditors.A1.targets: 10 and 5) are out of A1's reach without "
         "the record saying so. Medium rather than low: the brief tells auditors to file every missed mutant as a finding, so the "
         "driver manufactures false gaps and hides real ones."),
  plan_or_paper_ref="whitepaper §9.5 A1, §9.7 (extractors: A1 mutation adequacy)",
  suggested_fix=("Re-extract a bundle document with the command its sidecar belongs to (or list it under scope.out_of_reach with the "
         "reason), and when the baseline extraction of a document fails, give the mutant 'incomplete' with both errors, never 'missed'.")),
F(id="F-M3-24", severity="medium", category="mutation_adequacy",
  aspect="O12 laws blind to a missing proofWindow extension",
  title=("An off-by-one in challengeState's extension loop (i <= lastCommittedBatchIndex -> i < lastCommittedBatchIndex), which "
         "leaves the last committed batch's finalizeTimestamp unextended while another batch is challenged, moves neither decided "
         "law over that loop: L_contract_C_o12_m3 stays PROVED (it bounds the extension from above only) and "
         "L_undo_cancel_Rollup_challengeState_setPause stays REFUTED"),
  reproduction=(f"At {C}: `python -m holon audit mutation --milestone M3 --round 6 --spec "
         "audit/rounds/M3/round6/a1_run_challenge_loop_spec.json --target ed893be8abb2fa2c57804cf32e0cd45de7184fbb --work <scratch> "
         "--out audit/rounds/M3/round6/a1_run_challenge_loop.json` (about 5.5 minutes): mutant rollup_challenge_loop "
         "(contracts/contracts/l1/rollup/Rollup.sol:489) re-extracts spec/M2/facts/morph_rollup.extracted.json with changes only in "
         "/actions/5/loops/0/bound (challengeState), no statement changes, 141 laws touched; runs: L_contract_C_o12_m3 committed PROVED, "
         "baseline PROVED, mutant PROVED; L_undo_cancel_Rollup_challengeState_setPause committed REFUTED, baseline REFUTED, mutant "
         "REFUTED; verdict incomplete (the other 139 touched laws were not run within the cap of 4 runs). These are the only decided "
         "laws that name challengeState (`grep -l challengeState laws/M3/L*.json` against the packet's statuses). The mutant is a "
         "real defect: while one batch is in challenge no other can be challenged (require(!inChallenge)), and the loop's +proofWindow "
         "keeps the other unfinalized batches' challenge windows open; with the mutant the newest batch's window is consumed by the "
         "other challenge. The driver's verdict is incomplete; the auditor judges it a miss of the laws that state O12."),
  plan_or_paper_ref="whitepaper §5.9 (intent contract O12), §5.2 (UNDO challenge/cancel), §5.4 (SYM index translation), §9.5 A1",
  suggested_fix=("State O12 from both sides (every unfinalized batch other than the challenged one gains exactly proofWindow per "
         "challenge started while it is unfinalized), or derive a SYM index-translation split over challengeState's loop, so a "
         "skipped index is refuted.")),
F(id="F-M3-25", severity="medium", category="model_vs_code",
  aspect="calldata carrier: the ABI decoder's bounds are not modelled",
  title=("The compiled rollup model accepts calldata that solc's ABI decoder rejects: for finalizeBatch(bytes) with an out-of-range "
         "offset or a length past the end of calldata, the model evaluates the action with no arguments and predicts the 'Empty "
         "batch header' revert at Rollup.sol:825, while the real code reverts in the decoder with empty revert data"),
  reproduction=(f"At {C}: `python -m holon audit hostile-input --milestone M3 --round 6 --spec audit/rounds/M3/round6/a2_spec.json "
         f"--target {C} --work <scratch>` (51 cases, about 1.6 minutes) prints '49 agree, 2 disagree, 0 unsupported'. In "
         "audit/rounds/M3/round6/a2.json, case fin_raw_offset_huge (calldata 0x13361101 followed by 32 bytes 0xff) and case "
         "fin_raw_len_past_end (0x13361101, offset 0x20, length 249, then 10 data bytes) have real revert_key ['raw', '0x'] and "
         "model revert_key ['error', 'Empty batch header'], guard finalizeBatch#contracts/contracts/l1/rollup/Rollup.sol:825#0; "
         "fin_raw_no_args (the selector alone) agrees (['raw', '0x'] on both sides). Cause: holon/replay_fragments.py model_call "
         "gives args {} to calldata that decodes neither strictly nor loosely ('calldata shorter than its arguments gives none'), "
         "but these calldatas are not shorter than the argument head, and the model has no clause for the decoder's offset and "
         "length bounds of a dynamic argument. Both sides revert, so no recorded status moves; the model's partiality at the "
         "calldata carrier is not the code's."),
  plan_or_paper_ref="whitepaper §5.1 (domain coherence at every interface carrier, R^ext), §9.5 A2, §8.7",
  suggested_fix=("Model solc's decoder checks for each dynamic argument (offset + 32 <= calldatasize and offset + 32 + length <= "
         "calldatasize, else revert with empty data) as the action's first guard, or have model_call report undecodable calldata "
         "as the decoder's revert instead of evaluating the model on no arguments.")),
F(id="F-M3-26", severity="medium", category="vacuity",
  aspect="FACT kernel law with a constant consumer; a D2-only inhabitant generator",
  title=("L_fact_kernel_Rollup_commitState_committedBatches_blobhash is PROVED whatever its commitment premise says: commitState "
         "reverts unless blobhash(0) == 0, so every successful call delivers the same empty blob-hash list, and its inhabitant is "
         "D2-degenerate because the FACT kernel inhabitant generator can only write one step for both runs"),
  reproduction=(f"At {C}: `python -m holon audit vacuity --milestone M3 --round 6 --target {C}` (about 7.5 minutes) writes "
         "audit/rounds/M3/round6/a4.json, whose entry for the law reads class 'degenerate', rules ['D2'] ('its two runs are "
         "identical'), representative not_searched. gen/M3/proofs/L_fact_kernel_Rollup_commitState_committedBatches_blobhash/PROOF.bend "
         "line 7: '# route guard: commitState's blob guard (M.k_commitState_41) makes a successful step's blob-hash list empty, so two "
         "successful runs have equal consumers'; the real guard is contracts/contracts/l1/rollup/Rollup.sol:276 "
         "require(blobhash(0) == bytes32(0), ...). So the law's consumer is constant on commitState's success set, and ker(m) within "
         "ker(c) holds whatever m is: the PROVED status certifies nothing about the commitment. The inhabitant generator cannot write "
         "a representative: holon/fact/search.py FactSearch.inhabit_kernel tests fhit(s, x1, s, x1) only, and holon/fact/run.py "
         "inhabit passes {'x1': m.act(xs), 'x2': m.act(xs)} with one prefix for both runs. A non-degenerate inhabitant exists in "
         "the code (two successful commitState calls from one reachable state by the two active submitters commit the same header, "
         "since the caller is no header field); the auditor did not check one, because the law's own generator cannot express it."),
  plan_or_paper_ref="whitepaper §5.5 (FACT), §12.3 (L21: vacuity; representative inhabitants), §9.5 A4",
  suggested_fix=("Scope a FACT kernel law's consumers to what the action consumes (commitState consumes the stored "
         "batchBlobVersionedHashes, not the transaction's blobs) and flag a law whose consumer is constant on the action's success "
         "set instead of reporting it PROVED; let the kernel inhabitant generator take two distinct runs.")),
F(id="F-M3-27", severity="medium", category="gate_evasion",
  aspect="CV1 counts a round on its own run flags",
  title=("holon audit round and holon audit converge count a round on its own run flags: three round files whose attacks A1-A7 "
         "cite no evidence, ran no command and have no packet, driver record or directory pass RD1-RD5 (ROUNDS OK) and are each "
         "counted clean, which brings M3's streak to k = 3"),
  reproduction=(f"In a scratch copy of {C} (git archive), never this repository: `python audit/rounds/M3/round6/a7/cv1_probe.py "
         "<scratch>` writes rounds 6-8 (family same, ruling HUMAN_ANSWERS Q9b, counts_toward_convergence true, every attack run true "
         "with evidence [] and tried 'nothing (scratch probe of CV1: no command was run)'); `python -m holon audit round "
         "--milestone M3 --root <scratch>` prints 'M3: 8 round(s), ROUNDS OK'; `python -m holon audit converge --milestone M3 "
         "--root <scratch> --out <file>` reports rounds 6, 7 and 8 'counted: a same-family round admitted by HUMAN_ANSWERS Q9b', "
         "clean, streak 3, and 'not converged: open high-priority finding(s): F-M3-19' only (output in "
         "audit/rounds/M3/round6/a7/cv1_probe.audit_status.json). holon/audit/rounds.py qualifies checks family, dry_run, the "
         "attacks' run flags, and session freshness; RD5 checks a1.json and a2.json only when they exist. Medium, not high: no "
         "recorded round lacks evidence and no recorded verdict moves; exploiting it takes a fabricated round."),
  plan_or_paper_ref="whitepaper §9.5 (convergence), L19; spec/M3/lib/audit_loop.json convergence; CODEX_AUDITOR.md §0 CV1",
  suggested_fix=("For a round with counts_toward_convergence true, require the driver records of A1, A2 and A4 (a1.json, a2.json, "
         "a4.json) and the packet in its directory, naming its round and target (RD5 for presence, not only consistency), with "
         "packet.json and a4.json rebuilding byte for byte (holon audit hostile/vacuity --check).")),
]
with open('/home/user/audit-m3-r6/audit/M3_findings.jsonl', 'a', encoding='utf-8') as f:
    for x in out:
        f.write(json.dumps(x, ensure_ascii=False) + "\n")
print("appended", [x["id"] for x in out])
