"""Round 8 (M3), auditor A2: builds a2_spec.json (holon-audit-a2-spec/0.1), the auditor's hostile inputs.

    python audit/rounds/M3/round8/a2_build_spec.py > audit/rounds/M3/round8/a2_spec.json

The inputs are the auditor's choice. Headers are built here byte by byte from the layout documented in morph's
BatchHeaderCodecV0/V1.sol; raw calldata is hand-encoded here (a hostile ABI encoding the compiled ABI would never
produce). Keccak-256 comes from holon/keccak.py only to name the genesis batch's hash in a parent header; a wrong
value would show as a real "incorrect ... hash" revert in the record, not as a silent pass.
The deployment is the binding's (replay/M2/fragments.json -> HolonTraceReplayTest.deploy): owner = the forge test
contract, active submitters 0x..1002 and 0x..1003, challenger 0x..1004, F=40, W=10, D=20, clock EPOCH+10, genesis
post state root 100.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from holon.keccak import keccak256  # noqa: E402

DOC = "spec/M2/facts/morph_rollup.extracted.json"
GO = "gen/M3/goops/blob_ops.json"
OWNER = "0x7fa9385be102ac3eac297483dd6233d62b3e1496"   # the forge test contract (who2addr(1) = address(this))
SUB = "0x0000000000000000000000000000000000001002"
CHAL = "0x0000000000000000000000000000000000001004"
EPOCH = 1_700_000_000
T0 = EPOCH + 10
ZVH = bytes.fromhex("010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014")
B1 = "0x01" + "11" * 31
B2 = "0x01" + "22" * 31


def w(n: int) -> bytes:
    return n.to_bytes(32, "big")


def header(v, idx, l1p, tot, dh, blob, prev, post, wr, ssvh, parent, lbn=None) -> bytes:
    h = bytes([v]) + idx.to_bytes(8, "big") + l1p.to_bytes(8, "big") + tot.to_bytes(8, "big")
    h += dh + blob + prev + post + wr + ssvh + parent
    if lbn is not None:
        h += lbn.to_bytes(8, "big")
    return h


G = header(0, 0, 0, 0, w(1), ZVH, w(0), w(100), w(0), w(0), w(0))
GH = keccak256(G)
DH0 = keccak256(bytes(10))                       # lastBlockNumber 0 (8 bytes) || numL1Messages 0 (2 bytes)
H1 = header(0, 1, 0, 0, DH0, ZVH, w(100), w(1), w(0), w(0), GH)
hx = lambda b: "0x" + b.hex()  # noqa: E731


def bdi(version=0, parent=G, lbn=0, nl1=0, prev=100, post=1, wr=0):
    return {"version": version, "parentBatchHeader": hx(parent), "lastBlockNumber": lbn, "numL1Messages": nl1,
            "prevStateRoot": hx(w(prev)), "postStateRoot": hx(w(post)), "withdrawalRoot": hx(w(wr))}


def commit_calldata(parent=G, version=0, lbn=0, nl1=0, prev=100, post=1, wr=0, struct_off=0x20, bytes_len=None,
                    pad_byte=None, drop_pad=False) -> str:
    """commitBatch((uint8,bytes,uint64,uint16,bytes32,bytes32,bytes32)) by hand."""
    n = len(parent) if bytes_len is None else bytes_len
    pad = (-len(parent)) % 32
    tail = w(n) + parent + (b"" if drop_pad else bytes(pad))
    if pad_byte is not None and pad:
        tail = tail[:-1] + bytes([pad_byte])
    head = w(version) + w(7 * 32) + w(lbn) + w(nl1) + w(prev) + w(post) + w(wr)
    return "0x41f756da" + (w(struct_off) + head + tail).hex()


def bytes_arg_calldata(sel: str, b: bytes, off=0x20, length=None, pad_byte=None) -> str:
    n = len(b) if length is None else length
    pad = (-len(b)) % 32
    tail = w(n) + b + bytes(pad)
    if pad_byte is not None and pad:
        tail = tail[:-1] + bytes([pad_byte])
    return sel + (w(off) + tail).hex()


def act(cid, action, call, pre=None):
    c = {"id": cid, "entry": {"kind": "action", "document": DOC, "action": action}, "call": call}
    if pre:
        c["pre"] = {"calls": pre}
    return c


COMMIT1 = {"action": "commitBatch", "args": {"batchDataInput": bdi()}, "caller": SUB}
cases = [
    # the header carrier through finalizeBatch (anyone): lengths and version bytes outside the modelled set
    act("f01_empty", "finalizeBatch", {"args": {"_batchHeader": "0x"}}),
    act("f02_v3_257", "finalizeBatch", {"args": {"_batchHeader": hx(b"\x03" + bytes(256))}}),
    act("f03_v1_249", "finalizeBatch", {"args": {"_batchHeader": hx(b"\x01" + bytes(248))}}),
    act("f04_v2_258", "finalizeBatch", {"args": {"_batchHeader": hx(b"\x02" + bytes(257))}}),
    act("f05_v0_248", "finalizeBatch", {"args": {"_batchHeader": hx(bytes(248))}}),
    act("f06_v255_257", "finalizeBatch", {"args": {"_batchHeader": hx(b"\xff" + bytes(256))}}),
    act("f07_genesis", "finalizeBatch", {"args": {"_batchHeader": hx(G)}}),
    act("f08_genesis_plus1", "finalizeBatch", {"args": {"_batchHeader": hx(G + b"\x00")}}),
    act("f09_h1_in_window", "finalizeBatch", {"args": {"_batchHeader": hx(H1)}}, [COMMIT1]),
    act("f10_h1_after_window", "finalizeBatch", {"args": {"_batchHeader": hx(H1)}, "timestamp": T0 + 41}, [COMMIT1]),
    act("f11_h1_plus1_after_window", "finalizeBatch", {"args": {"_batchHeader": hx(H1 + b"\x00")},
                                                       "timestamp": T0 + 41}, [COMMIT1]),
    # hostile ABI encodings of the header argument (raw calldata)
    act("f12_raw_dirty_padding", "finalizeBatch", {"calldata": bytes_arg_calldata("0x13361101", G, pad_byte=1)}),
    act("f13_raw_offset_past_end", "finalizeBatch", {"calldata": bytes_arg_calldata("0x13361101", G, off=0x1000)}),
    act("f14_raw_length_past_end", "finalizeBatch", {"calldata": bytes_arg_calldata("0x13361101", G, length=300)}),
    act("f15_raw_offset_0x40", "finalizeBatch",
        {"calldata": "0x13361101" + (w(0x40) + w(0) + w(len(G)) + G + bytes((-len(G)) % 32)).hex()}),
    # the header carrier through commitBatch (an active submitter)
    act("c01_ok_v0", "commitBatch", {"args": {"batchDataInput": bdi()}, "caller": SUB}),
    act("c02_parent_plus1", "commitBatch", {"args": {"batchDataInput": bdi(parent=G + b"\x00")}, "caller": SUB}),
    act("c03_parent_v1_249", "commitBatch", {"args": {"batchDataInput": bdi(parent=b"\x01" + G[1:])}, "caller": SUB}),
    act("c04_v2_noblob", "commitBatch", {"args": {"batchDataInput": bdi(version=2)}, "caller": SUB}),
    act("c05_v2_two_blobs", "commitBatch", {"args": {"batchDataInput": bdi(version=2)}, "caller": SUB,
                                            "blobs": [B1, B2]}),
    act("c06_v0_two_blobs", "commitBatch", {"args": {"batchDataInput": bdi()}, "caller": SUB, "blobs": [B1, B2]}),
    act("c07_v3", "commitBatch", {"args": {"batchDataInput": bdi(version=3)}, "caller": SUB}),
    act("c08_v1_one_blob", "commitBatch", {"args": {"batchDataInput": bdi(version=1, lbn=7)}, "caller": SUB,
                                           "blobs": [B1]}),
    act("c09_raw_dirty_padding", "commitBatch", {"calldata": commit_calldata(pad_byte=1), "caller": SUB}),
    act("c10_raw_no_padding", "commitBatch", {"calldata": commit_calldata(drop_pad=True), "caller": SUB}),
    act("c11_raw_struct_offset_past_end", "commitBatch", {"calldata": commit_calldata(struct_off=0x1000),
                                                          "caller": SUB}),
    act("c12_raw_bytes_length_huge", "commitBatch", {"calldata": commit_calldata(bytes_len=1 << 32), "caller": SUB}),
    act("c13_raw_dirty_version", "commitBatch", {"calldata": commit_calldata(version=0x100), "caller": SUB}),
    act("c14_zero_post_root", "commitBatch", {"args": {"batchDataInput": bdi(post=0)}, "caller": SUB}),
    act("c15_paused", "commitBatch", {"args": {"batchDataInput": bdi()}, "caller": SUB},
        [{"action": "setPause", "args": {"_status": True}, "caller": OWNER}]),
    # revert, challenge, prove after one commit
    act("r01_revert_h1", "revertBatch", {"args": {"_batchHeader": hx(H1), "_count": 1}, "caller": OWNER}, [COMMIT1]),
    act("r02_revert_h1_count_max", "revertBatch", {"args": {"_batchHeader": hx(H1), "_count": (1 << 256) - 1},
                                                   "caller": OWNER}, [COMMIT1]),
    act("r03_revert_h1_plus1", "revertBatch", {"args": {"_batchHeader": hx(H1 + b"\x00"), "_count": 1},
                                               "caller": OWNER}, [COMMIT1]),
    act("r04_revert_genesis", "revertBatch", {"args": {"_batchHeader": hx(G), "_count": 1}, "caller": OWNER}),
    act("x01_challenge_h1", "challengeState", {"args": {"batchIndex": 1, "_batchHash": hx(keccak256(H1))},
                                               "caller": CHAL, "value": 1}, [COMMIT1]),
    act("x02_challenge_raw_dirty_index", "challengeState",
        {"calldata": "0xcd4edc69" + (w((1 << 64) | 1) + keccak256(H1)).hex(), "caller": CHAL, "value": 1}, [COMMIT1]),
    act("p01_prove_after_challenge", "proveState", {"args": {"_batchHeader": hx(H1), "_batchProof": "0x01"},
                                                    "caller": SUB},
        [COMMIT1, {"action": "challengeState", "args": {"batchIndex": 1, "_batchHash": hx(keccak256(H1))},
                   "caller": CHAL, "value": 1}]),
    act("p02_view_genesis", "proveCommittedBatchState", {"args": {"_batchHeader": hx(G), "_batchProof": "0x01"}}),
    act("p03_view_genesis_plus1", "proveCommittedBatchState", {"args": {"_batchHeader": hx(G + b"\x00"),
                                                                        "_batchProof": "0x01"}}),
    act("p04_view_genesis_bad_proof", "proveCommittedBatchState", {"args": {"_batchHeader": hx(G),
                                                                            "_batchProof": "0x02"}}),
]


def go(cid, fn, pairs):
    return {"id": cid, "entry": {"kind": "go", "document": GO, "function": fn}, "input": {"set": pairs}}


for op, tag in (("batch_RetrieveBlobBytes", "gb"), ("blob_RetrieveBlobBytes", "gl")):
    cases += [
        go(f"{tag}01_zero", op, []),
        go(f"{tag}02_hi_0", op, [[0, 1]]),
        go(f"{tag}03_hi_3967", op, [[3967 * 32, 255]]),
        go(f"{tag}04_hi_3968", op, [[3968 * 32, 1]]),
        go(f"{tag}05_hi_4095", op, [[4095 * 32, 128]]),
        go(f"{tag}06_low_bytes", op, [[1, 255], [126977, 9], [131071, 1]]),
        go(f"{tag}07_hi_100_and_3968", op, [[100 * 32, 2], [3968 * 32, 3]]),
    ]

print(json.dumps({"spec_version": "holon-audit-a2-spec/0.1", "milestone": "M3", "cases": cases}, indent=1))
