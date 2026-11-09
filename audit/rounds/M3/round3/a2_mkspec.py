"""Build the round-3 A2 spec (holon-audit-a2-spec/0.1): hostile inputs at the Rollup's header carrier (commit path
encoder, header loader) and at the Go blob decoders. Hashes come from foundry's `cast keccak`."""
import json, subprocess, sys
CAST = "/root/work/foundry/cast"
def keccak(h):
    return subprocess.run([CAST, "keccak", h], capture_output=True, text=True, check=True).stdout.strip().lower()
def w(n): return n.to_bytes(32, "big")
ZVH = bytes.fromhex("010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014")
def hdr(v, idx, l1p, tot, dh, blob, prev, post, wr, ssvh, parent, lbn=None):
    b = bytes([v]) + idx.to_bytes(8, "big") + l1p.to_bytes(8, "big") + tot.to_bytes(8, "big") + dh + blob + prev + post + wr + ssvh + parent
    if lbn is not None:
        b += lbn.to_bytes(8, "big")
    return b
hx = lambda b: "0x" + b.hex()
# genesis as the binding deploys it (replay/M1/solidity/HolonTraceReplay.t.sol deploy: hdr(0, 0, 1, ZVH, r0 = 100))
g = hdr(0, 0, 0, 0, w(1), ZVH, w(0), w(100), w(0), w(0), w(0))
assert len(g) == 249
gh = bytes.fromhex(keccak(hx(g))[2:])
SUB, OWNER, CHAL, OTHER = "0x0000000000000000000000000000000000001002", "0x7fa9385be102ac3eac297483dd6233d62b3e1496", "0x0000000000000000000000000000000000001004", "0x0000000000000000000000000000000000001005"
POST1, WR1 = w(0x65), w(0x77)
def bdi(version, parent, lbn=1, n=0, prev=w(100), post=POST1, wr=WR1):
    return {"version": version, "parentBatchHeader": hx(parent), "lastBlockNumber": lbn, "numL1Messages": n,
            "prevStateRoot": hx(prev), "postStateRoot": hx(post), "withdrawalRoot": hx(wr)}
# batch 1 committed by commitBatch(version 0, parent g, lastBlockNumber 1, no L1 messages, no blob):
# dataHash = keccak256(uint64(1) ++ uint16(0)), blob hash ZERO_VERSIONED_HASH, parent hash keccak256(g)
dh1 = bytes.fromhex(keccak("0x" + (1).to_bytes(8, "big").hex() + (0).to_bytes(2, "big").hex())[2:])
h1 = hdr(0, 1, 0, 0, dh1, ZVH, w(100), POST1, WR1, w(0), gh)
h1v1 = hdr(1, 1, 0, 0, dh1, ZVH, w(100), POST1, WR1, w(0), gh, 1)
commit1 = {"action": "commitBatch", "args": {"batchDataInput": bdi(0, g)}, "caller": SUB}
commit1v1 = {"action": "commitBatch", "args": {"batchDataInput": bdi(1, g)}, "caller": SUB}
D = "spec/M2/facts/morph_rollup.extracted.json"
A = lambda a: {"kind": "action", "document": D, "action": a}
cases = []
def act(cid, action, call, pre=None, note=None):
    c = {"id": cid, "entry": A(action), "call": call}
    if pre: c["pre"] = pre
    cases.append(c)
# --- the header loader (load_sol) at the commit path's parent header
act("c01", "commitBatch", {"args": {"batchDataInput": bdi(0, g + b"\x00")}, "caller": SUB})          # v0, 250 bytes
act("c02", "commitBatch", {"args": {"batchDataInput": bdi(0, g[:248])}, "caller": SUB})              # v0, 248 bytes
act("c03", "commitBatch", {"args": {"batchDataInput": bdi(0, b"")}, "caller": SUB})                  # empty
act("c04", "commitBatch", {"args": {"batchDataInput": bdi(0, bytes([3]) + g[1:])}, "caller": SUB})   # version 3
act("c05", "commitBatch", {"args": {"batchDataInput": bdi(0, bytes([1]) + g[1:])}, "caller": SUB})   # v1 tag, 249 bytes
act("c06", "commitBatch", {"args": {"batchDataInput": bdi(0, bytes([2]) + g[1:] + bytes(8))}, "caller": SUB})  # v2 tag, 257 bytes, not committed
# --- the commit-path encoder (enc_sol) and its guards
act("c07", "commitBatch", {"args": {"batchDataInput": bdi(0, g)}, "caller": SUB})                    # valid v0
act("c08", "commitBatch", {"args": {"batchDataInput": bdi(1, g)}, "caller": SUB})                    # valid v1
act("c09", "commitBatch", {"args": {"batchDataInput": bdi(2, g)}, "caller": SUB})                    # v2 without a blob
act("c10", "commitBatch", {"args": {"batchDataInput": bdi(2, g)}, "caller": SUB,
                           "blobs": ["0x01" + "11" * 31]})                                            # v2, one blob
act("c11", "commitBatch", {"args": {"batchDataInput": bdi(1, g)}, "caller": SUB,
                           "blobs": ["0x01" + "11" * 31, "0x01" + "22" * 31]})                        # v1, two blobs
act("c12", "commitBatch", {"args": {"batchDataInput": bdi(3, g)}, "caller": SUB})                    # version 3
act("c13", "commitBatch", {"args": {"batchDataInput": bdi(0, g, prev=w(0))}, "caller": SUB})         # zero prev root
act("c14", "commitBatch", {"args": {"batchDataInput": bdi(0, g, post=w(0))}, "caller": SUB})         # zero post root
act("c15", "commitBatch", {"args": {"batchDataInput": bdi(0, g, prev=w(101))}, "caller": SUB})       # wrong prev root
act("c16", "commitBatch", {"args": {"batchDataInput": bdi(0, g, n=1)}, "caller": SUB})               # 1 L1 message, queue empty
act("c17", "commitBatch", {"args": {"batchDataInput": bdi(0, g, lbn=2**64 - 1, n=0)}, "caller": SUB})  # max lastBlockNumber
act("c18", "commitBatch", {"args": {"batchDataInput": bdi(0, g)}, "caller": OTHER})                  # not a submitter
# --- loaders of later actions, from a state with batch 1 committed
act("c19", "finalizeBatch", {"args": {"_batchHeader": hx(h1)}, "caller": OTHER}, {"calls": [commit1]})      # inside the window
act("c20", "finalizeBatch", {"args": {"_batchHeader": hx(h1 + b"\x00")}, "caller": OTHER}, {"calls": [commit1]})  # 250 bytes
act("c21", "revertBatch", {"args": {"_batchHeader": hx(h1), "_count": 1}, "caller": OWNER}, {"calls": [commit1]})  # valid
act("c22", "revertBatch", {"args": {"_batchHeader": hx(h1), "_count": 2**256 - 1}, "caller": OWNER}, {"calls": [commit1]})  # index + count overflows
act("c23", "revertBatch", {"args": {"_batchHeader": hx(h1), "_count": 0}, "caller": OWNER}, {"calls": [commit1]})
act("c24", "revertBatch", {"args": {"_batchHeader": hx(g), "_count": 1}, "caller": OWNER})                  # the finalized genesis
act("c25", "revertBatch", {"args": {"_batchHeader": hx(h1 + b"\x00"), "_count": 1}, "caller": OWNER}, {"calls": [commit1]})
act("c26", "commitBatch", {"args": {"batchDataInput": bdi(0, h1, prev=POST1, post=w(0x66))}, "caller": SUB}, {"calls": [commit1]})  # batch 2 on batch 1
act("c27", "commitBatch", {"args": {"batchDataInput": bdi(1, h1v1, prev=POST1, post=w(0x66))}, "caller": SUB}, {"calls": [commit1v1]})  # batch 2 on a v1 batch 1
act("c28", "commitBatch", {"args": {"batchDataInput": bdi(1, h1v1 + b"\x00", prev=POST1, post=w(0x66))}, "caller": SUB}, {"calls": [commit1v1]})  # v1 parent, 258 bytes
act("c29", "commitState", {"args": {"batchDataInput": bdi(0, g)}, "caller": SUB},
    {"calls": [commit1, {"action": "revertBatch", "args": {"_batchHeader": hx(h1), "_count": 1}, "caller": OWNER}]})  # recommit on the stored blob hash
act("c30", "importGenesisBatch", {"args": {"_batchHeader": hx(g)}, "caller": OWNER})                       # genesis again
act("c31", "proveCommittedBatchState", {"args": {"_batchHeader": hx(h1), "_batchProof": "0x"}, "caller": OTHER}, {"calls": [commit1]})
# --- raw (hostile) ABI encodings
SEL_FIN = "0x" + keccak("0x" + b"finalizeBatch(bytes)".hex())[2:10]
act("c32", "finalizeBatch", {"calldata": SEL_FIN + (0x20).to_bytes(32, "big").hex() + (2**64).to_bytes(32, "big").hex(), "caller": OTHER})  # length past the data
act("c33", "finalizeBatch", {"calldata": SEL_FIN + (0x1000).to_bytes(32, "big").hex(), "caller": OTHER})  # offset past the data
act("c34", "finalizeBatch", {"calldata": SEL_FIN, "caller": OTHER})                                         # no argument
act("c35", "finalizeBatch", {"calldata": SEL_FIN + (0x20).to_bytes(32, "big").hex() + (249).to_bytes(32, "big").hex() + g.hex() + "ff" * 7, "caller": OTHER})  # dirty tail padding
# --- non-initial reachable states for A4's degenerate inhabitants (D1): commitBatchWithProof after a commit,
#     and the genesis guard (rollup:228) still blocking after a commit
h2 = hdr(0, 2, 0, 0, dh1, ZVH, POST1, w(0x66), WR1, w(0), bytes.fromhex(keccak(hx(h1))[2:]))
act("c36", "commitBatchWithProof", {"args": {"batchDataInput": bdi(0, h1, prev=POST1, post=w(0x66)), "_batchHeader": hx(h2),
                                             "_batchProof": "0x01"}, "caller": OTHER, "timestamp": 1700000100}, {"calls": [commit1]})
act("c37", "commitBatchWithProof", {"args": {"batchDataInput": bdi(0, h1, prev=POST1, post=w(0x66)), "_batchHeader": hx(h2),
                                             "_batchProof": "0x01"}, "caller": OTHER, "timestamp": 1700000015}, {"calls": [commit1]})
act("c38", "importGenesisBatch", {"args": {"_batchHeader": hx(g)}, "caller": OWNER}, {"calls": [commit1]})
# --- the A2 disagreements' follow-ups: the genesis header cleanly encoded, and calldata solc accepts (a bytes tail with
#     dirty padding) on a call that succeeds on the real code
act("c39", "finalizeBatch", {"args": {"_batchHeader": hx(g)}, "caller": OTHER})
SEL_REV = "0x" + keccak("0x" + b"revertBatch(bytes,uint256)".hex())[2:10]
act("c40", "revertBatch", {"calldata": SEL_REV + (0x40).to_bytes(32, "big").hex() + (1).to_bytes(32, "big").hex()
                           + (249).to_bytes(32, "big").hex() + h1.hex() + "ff" * 7, "caller": OWNER}, {"calls": [commit1]})
act("c41", "revertBatch", {"calldata": SEL_REV + (0x40).to_bytes(32, "big").hex() + (1).to_bytes(32, "big").hex()
                           + (249).to_bytes(32, "big").hex() + h1.hex() + "00" * 7, "caller": OWNER}, {"calls": [commit1]})
# --- A4's D2 inhabitant (L_fact_kernel_Rollup_commitState_committedBatches_blobhash): a second, different run whose
#     commitState commits the same batch value as c29's (both commit h1 on the stored blob hash; c29's prefix is
#     [commit1, revert]; this one's is [commit1, revert, commitState, revert])
rev1 = {"action": "revertBatch", "args": {"_batchHeader": hx(h1), "_count": 1}, "caller": OWNER}
cs1 = {"action": "commitState", "args": {"batchDataInput": bdi(0, g)}, "caller": SUB}
act("c42", "commitState", {"args": {"batchDataInput": bdi(0, g)}, "caller": SUB}, {"calls": [commit1, rev1, cs1, rev1]})
# --- the Go blob decoders (gen/M3/goops/blob_ops.json), both ops on the same blobs
GD = "gen/M3/goops/blob_ops.json"
blobs = {"zero": [], "b0": [[0, 1]], "hi3967": [[3967 * 32, 1]], "hi3968": [[3968 * 32, 1]], "hi4095": [[4095 * 32, 255]],
         "lo4095": [[4095 * 32 + 31, 255]], "b0_hi4000": [[0, 1], [4000 * 32, 1]], "lo5": [[5 * 32 + 1, 170]],
         "hi4000_lo3967": [[3967 * 32 + 5, 7], [4000 * 32, 9]]}
for op in ("batch_RetrieveBlobBytes", "blob_RetrieveBlobBytes"):
    for name, s in blobs.items():
        cases.append({"id": f"g_{op.split('_')[0]}_{name}", "entry": {"kind": "go", "document": GD, "function": op},
                      "input": {"set": s}})
spec = {"spec_version": "holon-audit-a2-spec/0.1", "milestone": "M3", "cases": cases}
json.dump(spec, open(sys.argv[1], "w"), indent=1, sort_keys=True)
open(sys.argv[1], "a").write("\n")
print(len(cases), "cases; genesis hash", "0x" + gh.hex(), "h1 dataHash", "0x" + dh1.hex())
