import json, sys
G = ("0x00" + "00"*24 + "00"*31 + "01" + "010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014"
     + "00"*32 + "00"*31 + "64" + "00"*32 + "00"*32 + "00"*32)
assert len(bytes.fromhex(G[2:])) == 249
OWNER = "0x7fa9385be102ac3eac297483dd6233d62b3e1496"
SUB = "0x0000000000000000000000000000000000001002"
CHAL = "0x0000000000000000000000000000000000001004"
T = 1700000010
B1 = "0x01" + "11"*31
B2 = "0x01" + "22"*31
Z = "0x" + "00"*32
D = "spec/M2/facts/morph_rollup.extracted.json"
def bdi(version=0, parent=G, last=0, n1=0, prev=100, post=1, wd=0):
    w = lambda v: "0x%064x" % v
    return {"batchDataInput": {"version": version, "parentBatchHeader": parent, "lastBlockNumber": last,
                               "numL1Messages": n1, "prevStateRoot": w(prev), "postStateRoot": w(post),
                               "withdrawalRoot": w(wd)}}
def act(cid, action, args=None, caller=OWNER, calldata=None, blobs=None, value=0, pre=None, ts=T):
    call = {"caller": caller, "timestamp": ts}
    if calldata is not None:
        call["calldata"] = calldata
    else:
        call["args"] = args
    if blobs is not None:
        call["blobs"] = blobs
    if value:
        call["value"] = value
    c = {"id": cid, "entry": {"kind": "action", "document": D, "action": action}, "call": call}
    if pre:
        c["pre"] = {"calls": pre}
    return c
commit_ok = {"action": "commitBatch", "args": bdi(), "caller": SUB, "timestamp": T}
# header of batch 1 as the real commitBatch above writes it (v0, index 1): taken from the committed witness corpus
H1 = sys.argv[2]
CB = sys.argv[3]   # the canonical calldata of commit_ok (from the committed witness corpus)
RB = sys.argv[4]   # the canonical calldata of revertBatch(H1, 1) (from the committed witness corpus)
def flip_last(cd):  # the last byte is the bytes tail's zero padding: set it to 0x01 (solc's decoder ignores it)
    return cd[:-2] + "01"
def set_word(cd, at, v):  # replace the 32-byte word at byte offset at (after the 0x) by v
    h = cd[2:]
    return "0x" + h[:2*at] + "%064x" % v + h[2*at + 64:]
cases = [
 act("a01_revert_empty_header", "revertBatch", {"_batchHeader": "0x", "_count": 1}),
 act("a02_revert_version3_1byte", "revertBatch", {"_batchHeader": "0x03", "_count": 1}),
 act("a03_revert_v0_248_bytes", "revertBatch", {"_batchHeader": G[:2 + 2*248], "_count": 1}),
 act("a04_revert_genesis_finalized", "revertBatch", {"_batchHeader": G, "_count": 1}),
 act("a05_revert_v0_250_bytes", "revertBatch", {"_batchHeader": G + "00", "_count": 1}),
 act("a06_revert_v1_256_bytes", "revertBatch", {"_batchHeader": "0x01" + "00"*255, "_count": 1}),
 act("a07_revert_v1_258_bytes", "revertBatch", {"_batchHeader": "0x01" + "00"*257, "_count": 1}),
 act("a08_revert_v2_257_zero", "revertBatch", {"_batchHeader": "0x02" + "00"*256, "_count": 1}),
 act("a09_revert_count_zero", "revertBatch", {"_batchHeader": G, "_count": 0}),
 act("a10_revert_count_overflow", "revertBatch", {"_batchHeader": H1, "_count": 2**256 - 1}, pre=[commit_ok]),
 act("a11_revert_not_owner", "revertBatch", {"_batchHeader": G, "_count": 1}, caller=SUB),
 act("a12_revert_v255_249_bytes", "revertBatch", {"_batchHeader": "0xff" + G[4:], "_count": 1}),
 act("a13_commit_parent_250_bytes", "commitBatch", bdi(parent=G + "00"), caller=SUB),
 act("a14_commit_version3", "commitBatch", bdi(version=3), caller=SUB),
 act("a15_commit_v2_no_blob", "commitBatch", bdi(version=2), caller=SUB),
 act("a16_commit_v1_two_blobs", "commitBatch", bdi(version=1), caller=SUB, blobs=[B1, B2]),
 act("a17_commit_v2_zero_blob_between", "commitBatch", bdi(version=2), caller=SUB, blobs=[B1, Z, B2]),
 act("a18_commit_v0_zero_then_blob", "commitBatch", bdi(version=0), caller=SUB, blobs=[Z, B2]),
 act("a19_commit_prev_root_zero", "commitBatch", bdi(prev=0), caller=SUB),
 act("a20_commit_v1_max_last_block", "commitBatch", bdi(version=1, last=2**64 - 1), caller=SUB),
 act("a21_commit_v0_ok", "commitBatch", bdi(), caller=SUB),
 act("a22_commit_parent_v1_257", "commitBatch", bdi(parent="0x01" + "00"*256), caller=SUB),
 act("a23_commit_v2_one_blob", "commitBatch", bdi(version=2), caller=SUB, blobs=[B1]),
 act("a24_commit_v0_one_blob", "commitBatch", bdi(version=0), caller=SUB, blobs=[B1]),
 act("a25_commit_not_submitter", "commitBatch", bdi(), caller=CHAL),
 act("a26_commitstate_zero_blob0", "commitState", bdi(), caller=SUB, blobs=[Z, B2]),
 act("a27_commitstate_after_revert", "commitState", bdi(), caller=SUB,
     pre=[commit_ok, {"action": "revertBatch", "args": {"_batchHeader": H1, "_count": 1}, "caller": OWNER, "timestamp": T}]),
 act("a28_commit_selector_only", "commitBatch", calldata="0x41f756da", caller=SUB),
 act("a29_revert_offset_out_of_bounds", "revertBatch",
     calldata="0x10d44583" + "ff"*32 + "00"*31 + "01", caller=OWNER),
 act("a30_import_genesis_again", "importGenesisBatch", {"_batchHeader": G}),
 act("a31_finalize_v0_250_bytes", "finalizeBatch", {"_batchHeader": G + "00"}, caller=SUB),
 act("a32_finalize_in_window", "finalizeBatch", {"_batchHeader": H1}, caller=SUB, pre=[commit_ok]),
 act("a33_challenge_absent_batch_zero_hash", "challengeState", {"batchIndex": 2**64 - 1, "_batchHash": "0x" + "00"*32},
     caller=CHAL, value=1),
 act("a34_commit_v1_parent_v0_ok", "commitBatch", bdi(version=1, last=7), caller=SUB, blobs=[B1]),
 act("a35_commit_dirty_tail_padding", "commitBatch", calldata=flip_last(CB), caller=SUB),
 act("a36_revert_dirty_tail_padding", "revertBatch", calldata=flip_last(RB), caller=OWNER, pre=[commit_ok]),
 act("a37_revert_bytes_length_past_end", "revertBatch", calldata=set_word(RB, 4 + 64, 300), caller=OWNER,
     pre=[commit_ok]),
 act("a38_challenge_dirty_uint64", "challengeState",
     calldata="0xcd4edc69" + "%064x" % (2**64) + "00"*32, caller=CHAL, value=1),
 act("a39_commit_dirty_uint8_version", "commitBatch", calldata=set_word(CB, 4 + 32, 256), caller=SUB),
 act("a40_revert_canonical_calldata", "revertBatch", calldata=RB, caller=OWNER, pre=[commit_ok]),
]
GO = "gen/M3/goops/blob_ops.json"
def go(cid, fn, sets):
    return {"id": cid, "entry": {"kind": "go", "document": GO, "function": fn}, "input": {"set": sets}}
cases += [
 go("g01_batch_all_zero", "batch_RetrieveBlobBytes", []),
 go("g02_batch_high_byte_3967", "batch_RetrieveBlobBytes", [[3967 * 32, 1]]),
 go("g03_batch_high_byte_3968", "batch_RetrieveBlobBytes", [[3968 * 32, 1]]),
 go("g04_batch_high_byte_4095", "batch_RetrieveBlobBytes", [[4095 * 32, 255]]),
 go("g05_batch_high_byte_0", "batch_RetrieveBlobBytes", [[0, 1]]),
 go("g06_batch_low_bytes_only", "batch_RetrieveBlobBytes", [[1, 255], [31, 255], [131071, 255]]),
 go("g07_batch_first_bad_low", "batch_RetrieveBlobBytes", [[3968 * 32, 1], [5 * 32, 9]]),
 go("g08_batch_first_bad_3967_then_3968", "batch_RetrieveBlobBytes", [[3967 * 32, 1], [3968 * 32, 1]]),
 go("g09_blob_all_zero", "blob_RetrieveBlobBytes", []),
 go("g10_blob_high_byte_3968", "blob_RetrieveBlobBytes", [[3968 * 32, 1]]),
 go("g11_blob_high_byte_4095", "blob_RetrieveBlobBytes", [[4095 * 32, 255]]),
 go("g12_blob_low_bytes_only", "blob_RetrieveBlobBytes", [[1, 255], [131071, 255]]),
 go("g13_batch_high_byte_4000_and_low", "batch_RetrieveBlobBytes", [[4000 * 32 + 1, 7], [4000 * 32, 2]]),
]
spec = {"spec_version": "holon-audit-a2-spec/0.1", "milestone": "M3",
        "note": "round 5's A2 cases, chosen by the auditor: the batch header carrier through every Rollup entry point that loads one (empty, short, long, bad version, wrong length per version), blob lists that a real chain cannot carry (a zero hash before a non-zero one), counts that overflow, malformed ABI encodings, and the blob carrier around the 3968th field element, where batch.RetrieveBlobBytes's error path indexes past its output buffer",
        "cases": cases}
open(sys.argv[1], "w").write(json.dumps(spec, indent=1) + "\n")
print(len(cases), "cases")
