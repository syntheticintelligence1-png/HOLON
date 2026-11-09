import json, sys
M = [
 ("m01_go_getter_offset", "common/batch/batch_header.go", 90, "b[9:17]", "b[10:18]",
  ["L_par_rt_BatchHeaderV1_Bytes_BatchHeaderBytes_L1MessagePopped_v1"],
  "off-by-one offset in the Go getter L1MessagePopped: the getter round trips over that field go PROVED -> REFUTED"),
 ("m02_go_dropped_write", "common/batch/batch_header.go", 256,
  "binary.BigEndian.PutUint64(batchBytes[249:], b.LastBlockNumber)", "_ = b.LastBlockNumber",
  ["L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned"],
  "the V1 Go encoder drops its LastBlockNumber write: the pinned cross-component codec law goes PROVED -> REFUTED"),
 ("m03_go_swapped_cursor", "common/batch/batch_header.go", 223,
  "copy(batchBytes[89:], b.PrevStateRoot[:])", "copy(batchBytes[121:], b.PrevStateRoot[:])",
  ["L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_PrevStateRoot_v0"],
  "the V0 Go encoder writes PrevStateRoot at PostStateRoot's cursor: the V0 PrevStateRoot round trip goes PROVED -> REFUTED"),
 ("m04_go_buffer_reuse_alias", "common/batch/batch_data.go", 36,
  "append(cks.txsPayload, txsPayload...)", "append(cks.txsPayload[:0], txsPayload...)",
  ["L_own_alias_batch_BatchData_TxsPayload_Append"],
  "Append reuses the payload buffer from index 0, overwriting a live TxsPayload view: the OWN alias law goes PROVED -> REFUTED"),
 ("m05_go_drifted_length", "common/batch/batch_header.go", 23, "expectedLengthV2 = 257", "expectedLengthV2 = 249",
  ["L_par_rt_BatchCache_createBatchHeaderWithSequencerSetHash_BatchHeaderBytes_BatchIndex_v2"],
  "the V2 length constant drifts to the V0 length: Go rejects every 257-byte V2 header, the V2 round trips go PROVED -> REFUTED"),
 ("m06_sol_wrong_shift", "contracts/contracts/libraries/codec/BatchHeaderCodecV0.sol", 155,
  "shl(192, _l1MessagePopped)", "shl(184, _l1MessagePopped)",
  ["L_par_rt_enc_sol_BatchHeaderBytes_L1MessagePopped_v1"],
  "wrong shift in the Solidity encoder's storeL1MessagePopped: the enc_sol round trip over L1MessagePopped goes PROVED -> REFUTED"),
 ("m07_sol_dropped_blob_guard", "contracts/contracts/l1/rollup/Rollup.sol", 276,
  "require(blobhash(0) == bytes32(0), ", "require(true, ",
  ["L_fact_kernel_Rollup_commitState_committedBatches_blobhash"],
  "commitState no longer refuses a call carrying blobs: two calls committing the same stored blob hash deliver different blobhash lists, the FACT kernel law goes PROVED -> REFUTED"),
 ("m08_sol_missing_clear_committed", "contracts/contracts/l1/rollup/Rollup.sol", 447,
  "committedBatches[_batchIndex] = bytes32(0);", "",
  ["L_undo_pair_Rollup_commitBatch_revertBatch"],
  "revertBatch no longer clears committedBatches: a new UNDO residue register (a derivation change), or a moved UNDO law"),
 ("m09_sol_missing_clear_revertreq", "contracts/contracts/l1/rollup/Rollup.sol", 456,
  "revertReqIndex = 0;", "revertReqIndex = revertReqIndex;",
  ["L_disch_ext_rollup_132_d953872f_onlyOwner"],
  "revertBatch no longer resets revertReqIndex: the nonReqRevert guard becomes non-dischargeable by the owner, the DISCH laws of rollup_132 move"),
 ("m10_sol_off_by_one_origin", "contracts/contracts/l1/rollup/Rollup.sol", 367,
  "block.timestamp,", "block.timestamp - 1,",
  ["L_sym_sentinel_Rollup_batchDataStore_originTimestamp_commitBatch_366"],
  "originTimestamp is written one second early: at block.timestamp 1 commitBatch writes the sentinel 0, the SYM sentinel law goes PROVED -> REFUTED"),
 ("m11_sol_swapped_payer", "contracts/contracts/l1/L1CrossDomainMessenger.sol", 290,
  "estimateCrossDomainMessageFee(_msgSender(), _gasLimit)", "estimateCrossDomainMessageFee(_to, _gasLimit)",
  ["L_sort_payer_L1CrossDomainMessenger_sendMessage_5f7b1577_291"],
  "the fee is priced for the recipient, not the payer: the SORT payer law goes PROVED -> REFUTED"),
 ("m12_go_height_offset", "common/batch/encoding.go", 24,
  "blockContextBytes[:8]", "blockContextBytes[1:9]",
  ["L_par_gort_BuildBlockContext_HeightFromBlockContextBytes_0"],
  "off-by-one offset in HeightFromBlockContextBytes: the Go round trip with BuildBlockContext goes PROVED -> REFUTED"),
]
order = sys.argv[2].split(",") if len(sys.argv) > 2 else [m[0] for m in M]
by = {m[0]: m for m in M}
muts = []
for i in order:
    mid, f, ln, old, new, laws, exp = by[i]
    muts.append({"id": mid, "file": f, "edit": {"line": ln, "old": old, "new": new}, "laws": laws, "expect": exp})
cap = int(sys.argv[3]) if len(sys.argv) > 3 else 2
spec = {"spec_version": "holon-audit-a1-spec/0.1", "milestone": "M3",
        "budget": {"law_timeout_s": 900, "max_law_runs": cap},
        "note": "round 5's A1 mutants, chosen by the auditor; each names the decided law it expects to move first",
        "mutations": muts}
open(sys.argv[1], "w").write(json.dumps(spec, indent=1) + "\n")
