import json, sys
ZVH = "010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014"
def w(n): return "%064x" % n
# the deployment's genesis header (replay/M1/solidity/HolonTraceReplay.t.sol deploy: hdr(0, 0, dh=1, ZVH, post=r0), r0 = 100)
G = "00" + "00"*8 + "00"*8 + "00"*8 + w(1) + ZVH + w(0) + w(100) + w(0) + w(0) + w(0)
assert len(G) == 249*2
OWNER = "0x7fa9385be102ac3eac297483dd6233d62b3e1496"   # the harness test contract (initialize's caller)
SUB, CHAL, ANY = "0x0000000000000000000000000000000000001002", "0x0000000000000000000000000000000000001004", "0x00000000000000000000000000000000000000aa"
DOC = "spec/M2/facts/morph_rollup.extracted.json"
def act(cid, action, args, caller=ANY, value=0, pre=None, calldata=None):
    c = {"id": cid, "entry": {"kind": "action", "document": DOC, "action": action},
         "call": ({"calldata": calldata} if calldata else {"args": args}) | {"caller": caller, "value": value}}
    if pre: c["pre"] = pre
    return c
def bdi(version=0, parent=G, lbn=1, n=0, prev=100, post=101, wr=0):
    return {"version": version, "parentBatchHeader": "0x" + parent, "lastBlockNumber": lbn, "numL1Messages": n,
            "prevStateRoot": "0x" + w(prev), "postStateRoot": "0x" + w(post), "withdrawalRoot": "0x" + w(wr)}
v1 = "01" + G[2:] + "00"*8          # version byte 1, 257 bytes
v2 = "02" + G[2:] + "00"*8          # version byte 2, 257 bytes
cases = [
 act("fin_genesis", "finalizeBatch", {"_batchHeader": "0x" + G}),
 act("fin_genesis_trailing", "finalizeBatch", {"_batchHeader": "0x" + G + "00"}),
 act("fin_genesis_trailing32", "finalizeBatch", {"_batchHeader": "0x" + G + "ff"*32}),
 act("fin_empty", "finalizeBatch", {"_batchHeader": "0x"}),
 act("fin_short248", "finalizeBatch", {"_batchHeader": "0x" + G[:-2]}),
 act("fin_one_byte_v0", "finalizeBatch", {"_batchHeader": "0x00"}),
 act("fin_v1_len249", "finalizeBatch", {"_batchHeader": "0x01" + G[2:]}),
 act("fin_v1_len258", "finalizeBatch", {"_batchHeader": "0x" + v1 + "00"}),
 act("fin_v2_len257", "finalizeBatch", {"_batchHeader": "0x" + v2}),
 act("fin_v3", "finalizeBatch", {"_batchHeader": "0x03" + G[2:]}),
 act("fin_vff_one_byte", "finalizeBatch", {"_batchHeader": "0xff"}),
 act("revert_zero_count", "revertBatch", {"_batchHeader": "0x" + G, "_count": 0}, caller=OWNER),
 act("revert_max_count", "revertBatch", {"_batchHeader": "0x" + G, "_count": 2**256 - 1}, caller=OWNER),
 act("revert_trailing", "revertBatch", {"_batchHeader": "0x" + G + "00", "_count": 1}, caller=OWNER),
 act("challenge_genesis", "challengeState", {"batchIndex": 0, "_batchHash": "0x" + "00"*32}, caller=CHAL, value=1),
 act("prove_genesis", "proveState", {"_batchHeader": "0x" + G, "_batchProof": "0x01"}, caller=SUB),
 act("import_again", "importGenesisBatch", {"_batchHeader": "0x" + G}, caller=OWNER),
 act("commit_ok_v0", "commitBatch", {"batchDataInput": bdi()}, caller=SUB),
 act("commit_parent_trailing", "commitBatch", {"batchDataInput": bdi(parent=G + "00")}, caller=SUB),
 act("commit_parent_v1_249", "commitBatch", {"batchDataInput": bdi(parent="01" + G[2:])}, caller=SUB),
 act("commit_version3", "commitBatch", {"batchDataInput": bdi(version=3)}, caller=SUB),
 act("commit_v2_noblob", "commitBatch", {"batchDataInput": bdi(version=2)}, caller=SUB),
 act("commit_prev_zero", "commitBatch", {"batchDataInput": bdi(prev=0)}, caller=SUB),
 act("commit_prev_wrong", "commitBatch", {"batchDataInput": bdi(prev=99)}, caller=SUB),
 act("commit_l1msg_empty_queue", "commitBatch", {"batchDataInput": bdi(n=1)}, caller=SUB),
 act("commit_lbn_max", "commitBatch", {"batchDataInput": bdi(lbn=2**64 - 1, version=1)}, caller=SUB),
 act("commit_not_submitter", "commitBatch", {"batchDataInput": bdi()}, caller=ANY),
 act("commit_then_finalize_early", "finalizeBatch", {"_batchHeader": "0x" + G}, caller=ANY,
     pre={"calls": [{"action": "commitBatch", "args": {"batchDataInput": bdi()}, "caller": SUB}]}),
 act("commit_twice_same_parent", "commitBatch", {"batchDataInput": bdi(post=102)}, caller=SUB,
     pre={"calls": [{"action": "commitBatch", "args": {"batchDataInput": bdi()}, "caller": SUB}]}),
 act("revert_after_commit_max_count", "revertBatch", {"_batchHeader": "0x" + G, "_count": 2**256 - 1}, caller=OWNER,
     pre={"calls": [{"action": "commitBatch", "args": {"batchDataInput": bdi()}, "caller": SUB}]}),
 # hostile ABI encodings of finalizeBatch(bytes): selector 0x8f1d3776? computed by the driver from the ABI is not
 # available here, so the raw cases carry the selector of finalizeBatch(bytes) = keccak("finalizeBatch(bytes)")[:4]
]
sel = sys.argv[1]   # finalizeBatch(bytes) selector, computed by the caller
cases += [
 act("fin_raw_offset_huge", "finalizeBatch", None, calldata="0x" + sel + "ff"*32),
 act("fin_raw_len_past_end", "finalizeBatch", None, calldata="0x" + sel + w(32) + w(249) + "00"*10),
 act("fin_raw_no_args", "finalizeBatch", None, calldata="0x" + sel),
]
GO = "gen/M3/goops/blob_ops.json"
sets = {"zero": [], "hi_elem0": [[0, 1]], "hi_elem3967": [[126944, 1]], "hi_elem3968": [[126976, 1]],
        "hi_elem4095": [[131040, 1]], "lo_bytes_only": [[1, 255], [31, 255], [126977, 9], [131071, 255]],
        "first_wins_3967_3968": [[126944, 1], [126976, 1]], "first_wins_0_4095": [[0, 128], [131040, 1]],
        "hi_elem3968_ff": [[126976, 255]]}
for op in ("batch_RetrieveBlobBytes", "blob_RetrieveBlobBytes"):
    for k, s in sets.items():
        cases.append({"id": f"go_{op.split('_')[0]}_{k}", "entry": {"kind": "go", "document": GO, "function": op},
                      "input": {"set": s}})
spec = {"spec_version": "holon-audit-a2-spec/0.1", "milestone": "M3", "cases": cases}
print(json.dumps(spec, indent=1))
