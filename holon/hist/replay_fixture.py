"""replay_fixture.py — build S6's 5-commit fixture from Morph mainnet.

Emits the §4 corpus format under replay/M2/corpus/fixtures/:
  manifest.json                 (commits sorted by batch_index)
  payload/<sha256>.json         (calldata + blob bodies, self-contained)
  commits/<batch_index>.json    (S6 reconstruction records: pre-state reads)

The same record format is what the full-corpus fetcher (S5) should emit per
commit; the replay engine consumes it offline. Oracle-side fetching only —
no model logic here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .replay_rpc import Rpc, call_data, enc_uint, decode_uints, ZERO32
from .replay_keccak import selector
from .replay_atoms import canon_b32, canon_addr

ROLLUP = "0x759894ced0e6af42c26668076ffa84d02e3cef60"
COMMIT_TOPIC0 = ("0x2c32d4ae151744d0bf0b9464a3e897a1d17ed2f1af71f7c9a75f12ce"
                 "0d28238f")
SEL = {"commitBatch": "41f756da", "commitState": "67caa37a",
       "commitBatchWithProof": "2a58a723"}
SEL_R = {v: k for k, v in SEL.items()}
# older implementations still emitting CommitBatch: the 2-arg overload
# commitBatch(BatchDataInput, BatchSignatureInput) (v1/v2 era) and the v0-era
# commitBatch; both decode through the same BatchDataInput layout.
SEL_R["428868b5"] = "commitBatch"
SEL_R["d63b3549"] = "commitBatch"
OLD_SELECTORS = {"428868b5", "d63b3549"}


def _call(rpc: Rpc, to: str, sig: str, blk: int, *args: bytes) -> str:
    return rpc.eth_call(to, call_data(sig, *args), blk)


def _u(rpc: Rpc, to: str, sig: str, blk: int, *args: bytes) -> int:
    return int(_call(rpc, to, sig, blk, *args), 16)


def opt_call(rpc: Rpc, to: str, sig: str, blk: int, default,
             *args: bytes) -> tuple:
    """eth_call that tolerates missing getters on older implementations."""
    try:
        return _call(rpc, to, sig, blk, *args), True
    except Exception:
        return default, False


def scalars(rpc: Rpc, rollup: str, blk: int) -> dict:
    # Getters that can be absent on older implementations are read with
    # opt_call; a missing getter means the feature did not exist at that era,
    # so the model-side default is the faithful reconstruction.
    fields = [("lfi", "lastFinalizedBatchIndex()", 0, True),
              ("lci", "lastCommittedBatchIndex()", None, True),
              ("inch", "inChallenge()", 0, False),
              ("bc", "batchChallenged()", 0, False),
              ("rri", "revertReqIndex()", 0, False),
              ("paused", "paused()", 0, False),
              ("F", "finalizationPeriodSeconds()", None, False),
              ("W", "proofWindow()", 0, False),
              ("D", "rollupDelayPeriod()", 0, False)]
    sc = {}
    missing = []
    for name, sig, default, required in fields:
        v, ok = opt_call(rpc, rollup, sig, blk, None)
        if v is None:
            if required:
                raise RpcError(f"required getter {sig} unavailable")
            missing.append(sig)
            v = default
        sc[name] = int(v, 16)
    sc["missing_getters"] = missing
    sc["inch"] = bool(sc["inch"])
    sc["paused"] = bool(sc["paused"])
    v, ok = opt_call(rpc, rollup, "submitterContract()", blk, None)
    sc["submitterContract"] = canon_addr(v[-40:]) if v else None
    v, ok = opt_call(rpc, rollup, "messageQueue()", blk, None)
    sc["messageQueue"] = canon_addr(v[-40:]) if v else None
    return sc


def batch_data_store(rpc: Rpc, rollup: str, i: int, blk: int) -> dict:
    r = decode_uints(_call(rpc, rollup, "batchDataStore(uint256)", blk,
                           enc_uint(i)), 4)
    return {"originTimestamp": r[0], "finalizeTimestamp": r[1],
            "blockNumber": r[2], "submitter": canon_addr(hex(r[3]))}


def batch_challenge(rpc: Rpc, rollup: str, i: int, blk: int) -> dict:
    r = decode_uints(_call(rpc, rollup, "challenges(uint256)", blk,
                           enc_uint(i)), 6)
    return {"index": r[0], "challenger": canon_addr(hex(r[1])),
            "challengeDeposit": r[2], "startTime": r[3],
            "challengeSuccess": bool(r[4]), "finished": bool(r[5])}


def decode_input(method: str, data: bytes) -> dict:
    """Oracle-side decode for fixture extraction (model does its own dec).
    Top level is a single tuple arg -> word 0 is the offset to the tuple head."""
    body = data[4:]
    base = int.from_bytes(body[:32], "big")
    t = body[base:]
    w = [int.from_bytes(t[32 * i:32 * i + 32], "big") for i in range(7)]
    (ver, off, lbn, n, prev, post, wr) = w
    plen = int.from_bytes(t[off:off + 32], "big")
    return {"version": ver,
            "parentBatchHeader": t[off + 32:off + 32 + plen],
            "lastBlockNumber": lbn, "numL1Messages": n,
            "prevStateRoot": "0x" + prev.to_bytes(32, "big").hex(),
            "postStateRoot": "0x" + post.to_bytes(32, "big").hex(),
            "withdrawalRoot": "0x" + wr.to_bytes(32, "big").hex()}


def hdr_field(h: bytes, off: int, w: int) -> bytes:
    return h[off:off + w]


def hdr_tot(h: bytes) -> int:
    return int.from_bytes(h[17:25], "big")


def sha_file(payload_dir: Path, kind: str, data: bytes) -> str:
    sha = hashlib.sha256(data).hexdigest()
    (payload_dir / f"{sha}.json").write_text(json.dumps(
        {"kind": kind, "sha256": sha, "data": "0x" + data.hex()}) + "\n")
    return sha


def _vh_of_commitment(kzg_commitment_hex: str) -> str:
    c = bytes.fromhex(kzg_commitment_hex[2:])
    return "0x01" + hashlib.sha256(c).hexdigest()[2:]


def fetch_blob(vh: str, beacon_url: str | None, blobscan_url: str | None,
               slot: int | None = None) -> bytes | None:
    """blob body for a versioned hash.

    Primary: beacon blob_sidecars at the tx's slot (match versioned hash via
    kzg commitment). Fallback: blobscan dataStorageReferences (gcs/ipfs)."""
    import urllib.request, json as J
    def get(url):
        req = urllib.request.Request(url, headers={"User-Agent": "h/1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return J.loads(r.read())
    if beacon_url and slot is not None:
        try:
            d = get(f"{beacon_url}/eth/v1/beacon/blob_sidecars/{slot}")
            for sc in d["data"]:
                if _vh_of_commitment(sc["kzg_commitment"]) == vh:
                    blob = sc["blob"]
                    return bytes.fromhex(blob[2:] if blob.startswith("0x")
                                         else blob)
        except Exception as e:
            print(f"beacon {vh[:12]}.. failed: {e}", file=sys.stderr)
    if blobscan_url:
        try:
            d = get(f"{blobscan_url}/blobs/{vh}")
            for ref in d.get("dataStorageReferences", []):
                url = ref.get("url", "")
                if not url.startswith("http"):
                    continue
                try:
                    import urllib.request as U
                    with U.urlopen(url, timeout=60) as r:
                        raw = r.read()
                    if raw[:2] == b"0x":
                        return bytes.fromhex(raw[2:].decode())
                    return raw
                except Exception:
                    continue
        except Exception as e:
            print(f"blobscan {vh[:12]}.. failed: {e}", file=sys.stderr)
    return None


BEACON_GENESIS = 1606824023  # ethereum mainnet


def slot_of_ts(ts: int) -> int:
    return (ts - BEACON_GENESIS) // 12


def _lci_at(rpc: Rpc, rollup: str, blk: int) -> int:
    return int(_call(rpc, rollup, "lastCommittedBatchIndex()", blk), 16)


def _block_of_commit(rpc: Rpc, rollup: str, idx: int, head: int,
                     deploy_blk: int = 21_100_000) -> int:
    """First block with lastCommittedBatchIndex >= idx — binary search."""
    lo, hi = deploy_blk, head
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if _lci_at(rpc, rollup, mid) < idx:
            lo = mid
        else:
            hi = mid
    return hi


def _event_for(rpc: Rpc, rollup: str, idx: int, hi: int,
               lo_min: int = 0) -> dict | None:
    """The CommitBatch event for batch `idx` (topic1 filter), expanding back."""
    t1 = "0x" + enc_uint(idx).hex()
    hi0 = hi
    while hi > lo_min:
        lo = max(lo_min, hi - 9000)
        evs = rpc.get_logs(rollup, COMMIT_TOPIC0, lo, hi, [t1])
        if evs:
            return evs[-1]
        hi = lo - 1
        if hi0 - hi > 400_000:
            break
    return None


def _inputs_of(rpc: Rpc, have: dict, ids: list[int]) -> dict:
    """batch tx-input decodes for commit events keyed by batch index."""
    ids = [i for i in ids if i in have]
    txs = rpc.batch([("eth_getTransactionByHash",
                      [have[i]["transactionHash"]]) for i in ids])
    out = {}
    for i, tx in zip(ids, txs):
        sel = tx["input"][2:10]
        out[i] = decode_input(SEL_R.get(sel, "?"),
                              bytes.fromhex(tx["input"][2:]))
    return out


def build(rpc: Rpc, rollup: str, out_dir: Path, count: int = 5,
          beacon_url: str | None = None, blobscan_url: str | None = None,
          indices: list[int] | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "payload").mkdir(exist_ok=True)
    (out_dir / "commits").mkdir(exist_ok=True)
    head = rpc.block_number()
    if indices:
        fixture_events = []
        for i in indices:
            # locate the commit's block via lci() binary search, then a small
            # topic1-filtered log scan around it
            b = _block_of_commit(rpc, rollup, i, head)
            ev = _event_for(rpc, rollup, i, b + 400, lo_min=max(0, b - 12000))
            if ev is None:
                raise SystemExit(f"no CommitBatch event found for index {i}")
            fixture_events.append(ev)
    else:
        logs = []
        lo = head
        while len(logs) < count + 1:
            lo -= 9500
            logs = rpc.get_logs(rollup, COMMIT_TOPIC0, lo, head)
        logs = sorted(logs, key=lambda e: int(e["topics"][1], 16))
        # stop one short of the tip: each fixture commit needs its successor.
        fixture_events = logs[-count - 1:-1]
    fixture_events.sort(key=lambda e: int(e["topics"][1], 16))
    idxs = [int(e["topics"][1], 16) for e in fixture_events]
    manifest_commits = []
    records = {}
    for ev in fixture_events:
        idx = int(ev["topics"][1], 16)
        blk = int(ev["blockNumber"], 16)
        print(f"[fixture] commit {idx} @ block {blk} "
              f"(rpc calls so far {rpc.n_calls})", flush=True)
        blk1 = blk - 1
        tx = rpc.get_tx(ev["transactionHash"])
        recpt = rpc.get_receipt(ev["transactionHash"])
        binfo = rpc.get_block(blk)
        calldata = bytes.fromhex(tx["input"][2:])
        sel_hex = calldata[:4].hex()
        method = SEL_R.get(sel_hex, "?")
        bvhs = tx.get("blobVersionedHashes") or []
        sc = scalars(rpc, rollup, blk1)
        # ---- window inputs: every commit event lfi..idx (idx = lci+1 here;
        # any commit can be a revert-era gap index, so filter by events found)
        lfi_ev = _event_for(rpc, rollup, sc["lfi"], blk)
        lo_blk = int(lfi_ev["blockNumber"], 16) - 1 if lfi_ev else blk - 30000
        wevs = rpc.get_logs(rollup, COMMIT_TOPIC0, lo_blk, blk)
        have = {int(e["topics"][1], 16): e for e in wevs}
        have[idx] = ev
        need = list(range(sc["lfi"], idx + 1))
        inputs = _inputs_of(rpc, have, need)
        tot = {i: hdr_tot(inputs[i + 1]["parentBatchHeader"])
               for i in need if i + 1 in inputs}
        # ---- store reads at THIS commit's pre-block ----
        ids = need
        entries_all = {}
        CH = 120
        for k in range(0, len(ids), CH):
            chunk = ids[k:k + CH]
            calls = []
            for i in chunk:
                calls += [
                    ("eth_call", [{"to": rollup, "data": call_data(
                        "batchBlobVersionedHashes(uint256)", enc_uint(i))},
                        hex(blk1)]),
                    ("eth_call", [{"to": rollup, "data": call_data(
                        "committedStateRoots(uint256)", enc_uint(i))},
                        hex(blk1)]),
                    ("eth_call", [{"to": rollup, "data": call_data(
                        "batchDataStore(uint256)", enc_uint(i))},
                        hex(blk1)]),
                ]
            vals = rpc.batch(calls)
            for j, i in enumerate(chunk):
                bvh, csr, bd = vals[3 * j:3 * j + 3]
                bdw = decode_uints(bd, 4)
                entries_all[i] = {"bvh": canon_b32(bvh), "csr": canon_b32(csr),
                                  "bdo": bdw[0], "bdf": bdw[1], "bdn": bdw[2],
                                  "bds": canon_addr(hex(bdw[3]))}
        # ---- parent commitment + submitter + queue + challenge reads ----
        cb_parent = _call(rpc, rollup, "committedBatches(uint256)", blk1,
                          enc_uint(idx - 1))
        if sc["messageQueue"]:
            qpend = _u(rpc, sc["messageQueue"], "pendingQueueIndex()", blk1)
            qlen = _u(rpc, sc["messageQueue"], "nextCrossDomainMessageIndex()",
                      blk1)
        else:
            qpend = qlen = 0
        enq = []
        if qpend < qlen:
            enq_calls = [("eth_call", [{"to": sc["messageQueue"], "data":
                                        call_data("messageEnqueueTime(uint256)",
                                                  enc_uint(i))}, hex(blk1)])
                         for i in range(qpend, qlen)]
            enq = [int(v, 16) for v in rpc.batch(enq_calls)]
            enq = [0] * qpend + enq  # dense indexing; prefix consumed
        if sc["submitterContract"]:
            is_active = _u(rpc, sc["submitterContract"], "isActive(address)",
                           blk1, bytes.fromhex(tx["from"][2:].rjust(64, "0")))
        else:
            # era without a submitter registry: the sender was authorized on
            # chain, so the faithful minimal set is {sender}
            is_active = 1
        try:
            chal = batch_challenge(rpc, rollup, sc["bc"], blk1) if sc["bc"] \
                else None
        except Exception:
            chal = None
        if chal is None:
            chal = {"index": sc["bc"], "challenger": "0x" + "00" * 20,
                    "challengeDeposit": 0, "startTime": 0,
                    "challengeSuccess": False, "finished": False}
        res_bvh, res_csr, res_bd = [], [], []
        for i in range(sc["lci"] + 1, sc["lci"] + 4):
            res_bvh.append(canon_b32(_call(
                rpc, rollup, "batchBlobVersionedHashes(uint256)", blk1,
                enc_uint(i))))
            res_csr.append(canon_b32(_call(
                rpc, rollup, "committedStateRoots(uint256)", blk1,
                enc_uint(i))))
            bd = batch_data_store(rpc, rollup, i, blk1)
            res_bd.append({"o": bd["originTimestamp"],
                           "f": bd["finalizeTimestamp"],
                           "n": bd["blockNumber"], "s": bd["submitter"]})
        entries, missing = [], []
        for i in range(sc["lfi"], sc["lci"] + 1):
            ci = inputs.get(i)
            st = entries_all.get(i)
            if ci is None or st is None:
                missing.append(i)
                continue
            entries.append({
                "index": i, "ver": ci["version"], "tot": tot.get(i, 0),
                "n": ci["numL1Messages"], "prev": ci["prevStateRoot"],
                "post": ci["postStateRoot"], "lbn": ci["lastBlockNumber"],
                "csr": st["csr"], "bvh": st["bvh"],
                "bdo": st["bdo"], "bdf": st["bdf"], "bdn": st["bdn"],
                "bds": st["bds"], "lbn_store": st["bdn"],
            })
        record = {
            "batch_index": idx, "tx": ev["transactionHash"],
            "from": tx["from"], "method": method, "selector": "0x" + sel_hex,
            "block": blk,
            "receipt_status": int(recpt["status"], 16),
            "pre": {
                "block": blk1, "t": int(binfo["timestamp"], 16),
                "scalars": sc,
                "committedBatches": {str(idx - 1): canon_b32(cb_parent)},
                "active_submitters": [canon_addr(tx["from"])]
                if is_active else [],
                "submitter_checked": bool(sc["submitterContract"]),
                "queue": {"qlen": qlen, "qpend": qpend, "enq": enq},
                "challenges": [chal],
                "window": {"entries": entries,
                           "expected_len": sc["lci"] - sc["lfi"] + 1,
                           "missing_inputs": missing},
                "residues": {"bvh": res_bvh, "csr": res_csr, "bd": res_bd,
                             "tag": [2 if canon_b32(v) != ZERO32 else 1
                                     for v in res_bvh]},
            },
            "post": {
                "committedBatches": canon_b32(_call(
                    rpc, rollup, "committedBatches(uint256)", blk,
                    enc_uint(idx))),
                "committedStateRoots": canon_b32(_call(
                    rpc, rollup, "committedStateRoots(uint256)", blk,
                    enc_uint(idx))),
                "batchBlobVersionedHash": canon_b32(_call(
                    rpc, rollup, "batchBlobVersionedHashes(uint256)", blk,
                    enc_uint(idx))),
                "batchDataStore": batch_data_store(rpc, rollup, idx, blk),
                "lastCommittedBatchIndex": _u(
                    rpc, rollup, "lastCommittedBatchIndex()", blk),
            },
        }
        # successor's presented parent header (for committedBatches linkage)
        succ_ev = _event_for(rpc, rollup, idx + 1, blk + 30000, lo_min=blk)
        if succ_ev is not None:
            stx = rpc.get_tx(succ_ev["transactionHash"])
            sel = stx["input"][2:10]
            record["successor_parent_header"] = "0x" + decode_input(
                SEL_R.get(sel, "?"),
                bytes.fromhex(stx["input"][2:]))["parentBatchHeader"].hex()
        else:
            record["successor_parent_header"] = None
        records[idx] = record
        # payloads
        cd_sha = sha_file(out_dir / "payload", "calldata", calldata)
        blob_shas = []
        slot = slot_of_ts(int(binfo["timestamp"], 16))
        for vh in bvhs:
            body = fetch_blob(canon_b32(vh), beacon_url, blobscan_url, slot)
            if body is not None:
                blob_shas.append(sha_file(out_dir / "payload", "blob", body))
            else:
                blob_shas.append(None)
        manifest_commits.append({
            "batch_index": idx, "tx": ev["transactionHash"], "block": blk,
            "method": method, "selector": "0x" + sel_hex,
            "calldata_sha256": cd_sha,
            "blob_versioned_hashes": [canon_b32(h) for h in bvhs],
            "blobs_sha256": blob_shas,
            "post": {
                "committedBatches": record["post"]["committedBatches"],
                "committedStateRoots": record["post"]["committedStateRoots"],
                "lastCommittedBatchIndex":
                record["post"]["lastCommittedBatchIndex"],
            },
        })
    for idx, rec in records.items():
        (out_dir / "commits" / f"{idx}.json").write_text(
            json.dumps(rec, indent=2) + "\n")
    manifest = {
        "chain": "ethereum-mainnet", "rollup_proxy": rollup,
        "window": {"from_block": int(fixture_events[0]["blockNumber"], 16),
                   "to_block": int(fixture_events[-1]["blockNumber"], 16)},
        "commits": manifest_commits,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon.hist.replay_fixture")
    ap.add_argument("--rpc", default=",".join(
        ["https://eth.drpc.org",
         "https://eth-mainnet.public.blastapi.io",
         "https://eth-pokt.nodies.app",
         "https://ethereum-rpc.publicnode.com"]),
        help="comma-separated L1 RPC URLs, rotated on failure")
    ap.add_argument("--rollup", default=ROLLUP)
    ap.add_argument("--out", type=Path,
                    default=Path("replay/M2/corpus/fixtures"))
    ap.add_argument("--count", type=int, default=5)
    ap.add_argument("--indices", default=None,
                    help="comma-separated explicit batch indexes (overrides "
                         "--count; use for version-diverse fixtures)")
    ap.add_argument("--blobscan", default="https://api.blobscan.com")
    ap.add_argument("--beacon",
                    default="https://ethereum-beacon-api.publicnode.com")
    a = ap.parse_args(argv)
    rpc = Rpc([u for u in a.rpc.split(",") if u])
    m = build(rpc, a.rollup, a.out, a.count, a.beacon, a.blobscan,
              [int(x) for x in a.indices.split(",")] if a.indices else None)
    print(f"fixture: {len(m['commits'])} commits "
          f"[{m['commits'][0]['batch_index']}..{m['commits'][-1]['batch_index']}] "
          f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
