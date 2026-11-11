"""Builds audit/rounds/M3/round9/a2_spec.json (round 9's A2 inputs). Deterministic; standard library only.
Header bytes follow the deployment's genesis (replay/M1/solidity/HolonTraceReplay.t.sol deploy(): hdr(0, 0, dh=1, ZVH,
post=r0) with r0 = fsr.0 = 100 of spec/M1/facts/morph_rollup.json)."""
import json, sys
DOC = "spec/M2/facts/morph_rollup.extracted.json"
ZVH = "010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014"
W = lambda n: n.to_bytes(32, "big").hex()
def hdr(v, idx=0, l1p=0, tot=0, dh=1, blob=ZVH, prev=0, post=100, withdraw=0, ssvh=0, parent=0, lbn=0):
    h = bytes([v]).hex() + idx.to_bytes(8, "big").hex() + l1p.to_bytes(8, "big").hex() + tot.to_bytes(8, "big").hex()
    h += W(dh) + blob + W(prev) + W(post) + W(withdraw) + W(ssvh) + W(parent)
    if v >= 1:
        h += lbn.to_bytes(8, "big").hex()
    return "0x" + h
G = hdr(0)
SUB, OUT, CHAL = "0x" + "%040x" % 0x1002, "0x" + "%040x" % 0x1005, "0x" + "%040x" % 0x1004
OWNER = "0x7fa9385be102ac3eac297483dd6233d62b3e1496"   # forge's default test contract (who2addr(1) = address(this))
B1, B2 = "0x01" + "11" * 31, "0x01" + "22" * 31
def bdi(version=0, parent=G, lbn=1, n=0, prev=100, post=101, wr=0):
    return {"batchDataInput": {"version": version, "parentBatchHeader": parent, "lastBlockNumber": lbn, "numL1Messages": n,
                               "prevStateRoot": "0x" + W(prev), "postStateRoot": "0x" + W(post), "withdrawalRoot": "0x" + W(wr)}}
cases = []
def act(cid, action, args=None, caller=SUB, blobs=None, value=0, pre=None, calldata=None):
    call = {"caller": caller}
    if calldata is not None:
        call["calldata"] = calldata
    else:
        call["args"] = args or {}
    if blobs is not None:
        call["blobs"] = blobs
    if value:
        call["value"] = value
    c = {"id": cid, "entry": {"kind": "action", "document": DOC, "action": action}, "call": call}
    if pre:
        c["pre"] = pre
    cases.append(c)
# commitBatch: the parent header carrier (loader R^ext) and the batch input
act("cb01_v0_ok", "commitBatch", bdi(0), blobs=[B1])
act("cb02_v1_ok", "commitBatch", bdi(1), blobs=[B1])
act("cb03_v2_two_blobs", "commitBatch", bdi(2), blobs=[B1, B2])
act("cb04_v0_noblob", "commitBatch", bdi(0), blobs=[])
act("cb05_parent_trailing_byte", "commitBatch", bdi(0, parent=G + "00"), blobs=[B1])
act("cb06_parent_short", "commitBatch", bdi(0, parent=G[:-2]), blobs=[B1])
act("cb07_parent_empty", "commitBatch", bdi(0, parent="0x"), blobs=[B1])
act("cb08_parent_version3", "commitBatch", bdi(0, parent="0x03" + G[4:]), blobs=[B1])
act("cb09_parent_v1_249", "commitBatch", bdi(0, parent="0x01" + G[4:]), blobs=[B1])
act("cb10_parent_v2_257", "commitBatch", bdi(0, parent=hdr(2)), blobs=[B1])
act("cb11_parent_v0_257", "commitBatch", bdi(0, parent=G + "00" * 8), blobs=[B1])
act("cb12_input_version3", "commitBatch", bdi(3), blobs=[B1])
act("cb13_input_version255", "commitBatch", bdi(255), blobs=[B1])
act("cb14_v2_no_blob", "commitBatch", bdi(2), blobs=[])
act("cb15_v1_two_blobs", "commitBatch", bdi(1), blobs=[B1, B2])
act("cb16_prev_zero", "commitBatch", bdi(0, prev=0), blobs=[B1])
act("cb17_post_zero", "commitBatch", bdi(0, post=0), blobs=[B1])
act("cb18_prev_wrong", "commitBatch", bdi(0, prev=101), blobs=[B1])
act("cb19_l1msgs_empty_queue", "commitBatch", bdi(0, n=1), blobs=[B1])
act("cb20_lbn_max_v1", "commitBatch", bdi(1, lbn=2**64 - 1), blobs=[B1])
act("cb21_not_submitter", "commitBatch", bdi(0), caller=OUT, blobs=[B1])
act("cb22_parent_wrong_index", "commitBatch", bdi(0, parent=hdr(0, idx=1)), blobs=[B1])
act("cb23_twice", "commitBatch", bdi(0), blobs=[B1],
    pre={"calls": [{"action": "commitBatch", "args": bdi(0), "caller": SUB, "blobs": [B1]}]})
act("cb24_v2_one_zero_blob_gap", "commitBatch", bdi(2), blobs=[B1, "0x" + "00" * 32, B2])
act("cb25_parent_header_v2_genesis_bytes", "commitBatch", bdi(2, parent="0x02" + G[4:] + "00" * 8), blobs=[B1])
# commitBatch with a hostile ABI encoding: the bytes offset of parentBatchHeader points past the calldata
SEL = next(a["selector"] for a in json.load(open(sys.argv[2] + "/" + DOC))["actions"] if a["name"] == "commitBatch")
SEL = SEL[2:] if SEL.startswith("0x") else SEL
head = W(0) + W(2**64 - 1) + W(1) + W(0) + W(100) + W(101) + W(0)   # version, bytes offset, lbn, n, prev, post, wr
act("cb26_raw_bytes_offset_oob", "commitBatch", calldata="0x" + SEL + W(0x20) + head, blobs=[B1])
act("cb27_raw_truncated", "commitBatch", calldata="0x" + SEL + W(0x20) + W(0)[:30], blobs=[B1])
act("cb28_raw_dirty_version", "commitBatch", calldata="0x" + SEL + W(0x20) + W(0x100) + W(7 * 32) + W(1) + W(0) + W(100)
    + W(101) + W(0) + W(249) + G[2:] + "00" * 7, blobs=[B1])
# commitState: the stored-blob path
act("cs01_no_stored_blob", "commitState", bdi(0), blobs=[])
act("cs02_with_blob", "commitState", bdi(0), blobs=[B1])
# finalizeBatch: the header carrier
act("fb01_genesis", "finalizeBatch", {"_batchHeader": G}, caller=OUT)
act("fb02_trailing", "finalizeBatch", {"_batchHeader": G + "00"}, caller=OUT)
act("fb03_one_byte", "finalizeBatch", {"_batchHeader": "0x00"}, caller=OUT)
act("fb04_empty", "finalizeBatch", {"_batchHeader": "0x"}, caller=OUT)
act("fb05_v1_of_genesis", "finalizeBatch", {"_batchHeader": hdr(1)}, caller=OUT)
act("fb06_committed_in_window", "finalizeBatch", {"_batchHeader": G}, caller=OUT,
    pre={"calls": [{"action": "commitBatch", "args": bdi(0), "caller": SUB, "blobs": [B1]}]})
# revertBatch (owner): count edge values, the loader
act("rb01_genesis", "revertBatch", {"_batchHeader": G, "_count": 1}, caller=OWNER)
act("rb02_count0", "revertBatch", {"_batchHeader": G, "_count": 0}, caller=OWNER)
act("rb03_count_max", "revertBatch", {"_batchHeader": G, "_count": 2**256 - 1}, caller=OWNER)
act("rb04_not_owner", "revertBatch", {"_batchHeader": G, "_count": 1}, caller=OUT)
act("rb05_short", "revertBatch", {"_batchHeader": "0x00", "_count": 1}, caller=OWNER)
# importGenesisBatch again, proveState / proveCommittedBatchState on the genesis
act("ig01_again", "importGenesisBatch", {"_batchHeader": G}, caller=OWNER)
act("ig02_v1", "importGenesisBatch", {"_batchHeader": hdr(1)}, caller=OWNER)
act("ps01_genesis", "proveState", {"_batchHeader": G, "_batchProof": "0x"}, caller=OUT)
act("ps02_empty", "proveState", {"_batchHeader": "0x", "_batchProof": "0x"}, caller=OUT)
act("pc01_genesis", "proveCommittedBatchState", {"_batchHeader": G, "_batchProof": "0x00"}, caller=OUT)
# challengeState on the genesis and on an unknown batch
act("ch01_genesis", "challengeState", {"batchIndex": 0, "_batchHash": "0x" + "00" * 32}, caller=CHAL, value=10**18)
act("ch02_future", "challengeState", {"batchIndex": 2**64 - 1, "_batchHash": "0x" + "00" * 32}, caller=CHAL, value=10**18)
# view helpers on index edges
for i, n in (("bx01", 0), ("bx02", 2**256 - 1)):
    act(i + "_batchInsideChallengeWindow", "batchInsideChallengeWindow", {"batchIndex": n}, caller=OUT)
    act(i + "_isBatchFinalized", "isBatchFinalized", {"_batchIndex": n}, caller=OUT)
# Go: the blob carrier of the Go-op document
GO = "gen/M3/goops/blob_ops.json"
for fn in ("batch_RetrieveBlobBytes", "blob_RetrieveBlobBytes"):
    for cid, s in (("zero", []), ("hi0", [[0, 1]]), ("hi_last", [[131040, 128]]), ("lo_last", [[131071, 255]]),
                   ("lo_all31", [[i, 255] for i in range(1, 32)]), ("hi_mid", [[32 * 2048, 255]]),
                   ("lo_and_hi", [[1, 7], [32 * 4095, 1]])):
        cases.append({"id": f"go_{fn}_{cid}", "entry": {"kind": "go", "document": GO, "function": fn}, "input": {"set": s}})
spec = {"spec_version": "holon-audit-a2-spec/0.1", "milestone": "M3", "cases": cases}
open(sys.argv[1], "w").write(json.dumps(spec, indent=1, sort_keys=True) + "\n")
print(len(cases), "cases")
