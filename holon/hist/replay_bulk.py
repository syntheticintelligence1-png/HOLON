"""replay_bulk.py — build S6 reconstruction records for the FULL S5 corpus
(replay/M2/corpus/commits/<idx>.json), and pre-fetch calldata payloads into
the §4 cache.

Cost discipline (the naive per-commit window fetch is ~450k calls):
  * window entries' immutable store values are read ONCE for the union
    [min_lfi .. max_idx] at the last commit's pre-block — exact whenever no
    RevertBatch happened in the span; commits whose pre-state shows
    inChallenge/bc/rri or a Revert event in range get per-block re-reads.
  * window input fields (ver/n/prev/post/lbn) decode from the corpus's own
    calldata payloads; pre-corpus window commits are fetched once.
  * per-commit reads stay per-commit: scalars, committedBatches[parent],
    queue, submitter, challenge, residues, post-state extras.

Same record format as replay_fixture.py emits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

from .replay_rpc import Rpc, RpcError, call_data, enc_uint, decode_uints, ZERO32
from .replay_atoms import canon_b32, canon_addr
from .replay_fixture import (COMMIT_TOPIC0, SEL_R, decode_input, scalars,
                             batch_data_store, batch_challenge, opt_call,
                             _call, _u, _block_of_commit, _event_for,
                             fetch_blob, slot_of_ts, sha_file)


def lci_of(man: dict) -> tuple[int, int]:
    idxs = [c["batch_index"] for c in man["commits"]]
    return min(idxs), max(idxs)


def ensure_calldata(rpc: Rpc, cache_dir: Path, commits: list[dict],
                    batch_size: int = 100) -> int:
    """Fetch each commit's tx input into cache_dir/<sha256> (raw bytes).
    Also caches blobVersionedHashes-free record (manifest already has them).
    Returns number fetched."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    have = {c["calldata_sha256"] for c in commits
            if (cache_dir / c["calldata_sha256"]).exists()
            or (cache_dir / f"{c['calldata_sha256']}.json").exists()}
    missing = [c for c in commits
               if c["calldata_sha256"] not in have or "from" not in c]
    got = 0
    for k in range(0, len(missing), batch_size):
        chunk = missing[k:k + batch_size]
        txs = rpc.batch([("eth_getTransactionByHash", [c["tx"]])
                         for c in chunk])
        for c, tx in zip(chunk, txs):
            data = bytes.fromhex(tx["input"][2:])
            assert hashlib.sha256(data).hexdigest() == c["calldata_sha256"]
            if c["calldata_sha256"] not in have:
                (cache_dir / c["calldata_sha256"]).write_bytes(data)
                got += 1
            c["from"] = canon_addr(tx["from"])
    return got


def window_inputs(rpc: Rpc, corpus_inputs: dict, need_ids: list[int],
                  window_lo_blk: int, blk_hi: int,
                  corpus_span: tuple[int, int] | None = None) -> dict:
    """Decoded inputs for off-corpus window commits; corpus ones come from
    the manifest payloads. Scans getLogs only in the off-corpus block
    ranges (corpus_span marks the range already covered by the manifest)."""
    have = {}
    spans = [(window_lo_blk, blk_hi)]
    if corpus_span:
        lo, hi = corpus_span
        spans = []
        if window_lo_blk < lo:
            spans.append((window_lo_blk, lo))
        if hi < blk_hi:
            spans.append((hi, blk_hi))
    for a, b in spans:
        for e in rpc.get_logs(
                "0x759894ced0e6af42c26668076ffa84d02e3cef60",
                COMMIT_TOPIC0, a, b):
            have[int(e["topics"][1], 16)] = e
    ids = [i for i in need_ids if i in have and i not in corpus_inputs]
    out = dict(corpus_inputs)
    if ids:
        txs = rpc.batch([("eth_getTransactionByHash",
                          [have[i]["transactionHash"]]) for i in ids])
        for i, tx in zip(ids, txs):
            sel = tx["input"][2:10]
            out[i] = decode_input(SEL_R.get(sel, "commitBatch"),
                                  bytes.fromhex(tx["input"][2:]))
    return out


def snapshot_reads(rpc: Rpc, rollup: str, ids: list[int], blk: int) -> dict:
    """One read of (bvh, csr, batchDataStore) per index at `blk`."""
    out = {}
    CH = 120
    for k in range(0, len(ids), CH):
        chunk = ids[k:k + CH]
        calls = []
        for i in chunk:
            for sig in ("batchBlobVersionedHashes(uint256)",
                        "committedStateRoots(uint256)",
                        "batchDataStore(uint256)"):
                calls.append(("eth_call", [{"to": rollup, "data": call_data(
                    sig, enc_uint(i))}, hex(blk)]))
        vals = rpc.batch(calls)
        for j, i in enumerate(chunk):
            bvh, csr, bd = vals[3 * j:3 * j + 3]
            bdw = decode_uints(bd, 4)
            out[i] = {"bvh": canon_b32(bvh), "csr": canon_b32(csr),
                      "bdo": bdw[0], "bdf": bdw[1], "bdn": bdw[2],
                      "bds": canon_addr(hex(bdw[3]))}
    return out


SCALAR_FIELDS = [("lfi", "lastFinalizedBatchIndex()", 0, True),
                 ("lci", "lastCommittedBatchIndex()", None, True),
                 ("inch", "inChallenge()", 0, False),
                 ("bc", "batchChallenged()", 0, False),
                 ("rri", "revertReqIndex()", 0, False),
                 ("paused", "paused()", 0, False),
                 ("F", "finalizationPeriodSeconds()", None, False),
                 ("W", "proofWindow()", 0, False),
                 ("D", "rollupDelayPeriod()", 0, False)]


def scalars_bulk(rpc: Rpc, rollup: str, blks: list[int]) -> list[dict]:
    """scalars() for many commits in one shot: all getter calls across all
    blocks flattened into batch RPCs of 120."""
    per = len(SCALAR_FIELDS) + 2  # + submitterContract + messageQueue
    calls = []
    for blk in blks:
        for _name, sig, _d, _req in SCALAR_FIELDS:
            calls.append(("eth_call", [{"to": rollup,
                                        "data": call_data(sig, b"")},
                                       hex(blk)]))
        for sig in ("submitterContract()", "messageQueue()"):
            calls.append(("eth_call", [{"to": rollup,
                                        "data": call_data(sig, b"")},
                                       hex(blk)]))
    vals = []
    for k in range(0, len(calls), 120):
        vals += rpc.batch(calls[k:k + 120])
    out = []
    for j, blk in enumerate(blks):
        row = vals[j * per:(j + 1) * per]
        sc, missing = {}, []
        for k, (name, sig, default, required) in enumerate(SCALAR_FIELDS):
            v = row[k]
            if v is None:
                if required:
                    raise RpcError(f"required getter {sig} unavailable "
                                   f"@ {blk}")
                missing.append(sig)
                v = hex(default) if isinstance(default, int) else default
            sc[name] = int(v, 16)
        sc["missing_getters"] = missing
        sc["inch"] = bool(sc["inch"])
        sc["paused"] = bool(sc["paused"])
        sub = row[-2]
        sc["submitterContract"] = canon_addr(sub[-40:]) if sub else None
        mq = row[-1]
        sc["messageQueue"] = canon_addr(mq[-40:]) if mq else None
        out.append(sc)
    return out


def _retry_null_rpc(rpc, method, params, tries: int = 8):
    for _ in range(tries):
        v = rpc.call(method, params)
        if v is not None:
            return v
        rpc._rotate()
        time.sleep(0.5)
    raise RpcError(f"RPC null for {method} after retries")


def per_commit_record(rpc: Rpc, rollup: str, c: dict, sc: dict,
                      inputs: dict, snap: dict, tot: dict,
                      revert_in_window: bool) -> dict:
    """Record for one corpus commit; `snap` is the union window snapshot."""
    idx = c["batch_index"]
    blk = c["block"]
    blk1 = blk - 1
    entries, missing = [], []
    for i in range(sc["lfi"], sc["lci"] + 1):
        ci = inputs.get(i)
        # batchDataStore/committedStateRoots/batchBlobVersionedHashes[i] are
        # DELETED by finalizeBatch(i+1): they are only alive at the commit's
        # own pre-block, so the union snapshot is only a fast path when no
        # finalization moved between it and blk1 (never true in bulk).
        st = snap.get(i) if snap else None
        if st is not None and revert_in_window:
            st = None
        if st is None:
            vals = rpc.batch([
                ("eth_call", [{"to": rollup, "data": call_data(
                    "batchBlobVersionedHashes(uint256)", enc_uint(i))},
                    hex(blk1)]),
                ("eth_call", [{"to": rollup, "data": call_data(
                    "committedStateRoots(uint256)", enc_uint(i))},
                    hex(blk1)]),
                ("eth_call", [{"to": rollup, "data": call_data(
                    "batchDataStore(uint256)", enc_uint(i))}, hex(blk1)]),
            ])
            bvh, csr, bd = vals
            bdw = decode_uints(bd, 4)
            st = {"bvh": canon_b32(bvh), "csr": canon_b32(csr),
                  "bdo": bdw[0], "bdf": bdw[1], "bdn": bdw[2],
                  "bds": canon_addr(hex(bdw[3]))}
        if ci is None:
            missing.append(i)
            continue
        entries.append({
            "index": i, "ver": ci["version"], "tot": tot.get(i, 0),
            "n": ci["numL1Messages"], "prev": ci["prevStateRoot"],
            "post": ci["postStateRoot"], "lbn": ci["lastBlockNumber"],
            "csr": st["csr"], "bvh": st["bvh"],
            "bdo": st["bdo"], "bdf": st["bdf"], "bdn": st["bdn"],
            "bds": st["bds"], "lbn_store": st["bdn"]})
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
        enq = [0] * qpend + enq
    if sc["submitterContract"]:
        is_active = _u(rpc, sc["submitterContract"], "isActive(address)",
                       blk1, bytes.fromhex(c["from"][2:].rjust(64, "0")))
    else:
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
        res_bd.append({"o": bd["originTimestamp"], "f": bd["finalizeTimestamp"],
                       "n": bd["blockNumber"], "s": bd["submitter"]})
    # post extras not in the S5 manifest entry; free endpoints occasionally
    # answer result:null instead of an error — retry across the pool
    binfo = _retry_null_rpc(rpc, "eth_getBlockByNumber", [hex(blk), False])
    post = {
        "committedBatches": c["post"]["committedBatches"],
        "committedStateRoots": c["post"]["committedStateRoots"],
        "batchBlobVersionedHash": canon_b32(_call(
            rpc, rollup, "batchBlobVersionedHashes(uint256)", blk,
            enc_uint(idx))),
        "batchDataStore": batch_data_store(rpc, rollup, idx, blk),
        "lastCommittedBatchIndex": c["post"]["lastCommittedBatchIndex"],
    }
    recpt = _retry_null_rpc(rpc, "eth_getTransactionReceipt", [c["tx"]])
    return {
        "batch_index": idx, "tx": c["tx"], "from": c["from"],
        "method": c.get("method", "commitBatch"),
        "selector": c.get("selector"), "block": blk,
        "receipt_status": int(recpt["status"], 16),
        "pre": {
            "block": blk1, "t": int(binfo["timestamp"], 16),
            "scalars": sc,
            "committedBatches": {str(idx - 1): canon_b32(cb_parent)},
            "active_submitters": [canon_addr(c["from"])] if is_active else [],
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
        "post": post,
    }


def build_records(rpc: Rpc, rollup: str, manifest_path: Path, corpus_dir: Path,
                  cache_dir: Path, limit: int | None = None,
                  progress_every: int = 50) -> dict:
    man = json.loads(manifest_path.read_text())
    commits = sorted(man["commits"], key=lambda c: c["batch_index"])
    if limit:
        commits = commits[:limit]
    got = ensure_calldata(rpc, cache_dir, commits)
    print(f"[bulk] calldata cached: {got} fetched "
          f"({len(commits) - got} already present)", flush=True)
    # corpus decodes of every manifest commit's input
    corpus_inputs = {}
    tx_from = {}
    for c in commits:
        data = (cache_dir / c["calldata_sha256"]).read_bytes()
        corpus_inputs[c["batch_index"]] = decode_input(
            c.get("method") or "commitBatch", data)
        tx_from[c["batch_index"]] = c.get("from")
    # scalars for every commit first — defines the union window
    scalars_by_idx = {}
    min_lfi = None
    scs = scalars_bulk(rpc, rollup, [c["block"] - 1 for c in commits])
    print(f"[bulk] scalars for {len(commits)} commits (rpc={rpc.n_calls})",
          flush=True)
    for c, sc in zip(commits, scs):
        scalars_by_idx[c["batch_index"]] = sc
        if min_lfi is None or sc["lfi"] < min_lfi:
            min_lfi = sc["lfi"]
    lo_i, hi_i = commits[0]["batch_index"], commits[-1]["batch_index"]
    need = list(range(min_lfi, hi_i + 2))
    # window inputs outside the corpus (below first idx, plus the tip's
    # successor whose parent header is needed for the last succ.* check)
    pre_ids = [i for i in need if i < lo_i or i > hi_i]
    inputs = dict(corpus_inputs)
    if pre_ids:
        print(f"[bulk] fetching {len(pre_ids)} off-corpus window inputs",
              flush=True)
        inputs = window_inputs(rpc, inputs, pre_ids,
                               man["window"]["from_block"] - 40000,
                               man["window"]["to_block"] + 2500,
                               corpus_span=(man["window"]["from_block"],
                                            man["window"]["to_block"]))
    # tot(i) = totalL1MessagePopped of commit(i+1)'s parent header
    tot = {i: int.from_bytes(inputs[i + 1]["parentBatchHeader"][17:25], "big")
           for i in need if i + 1 in inputs}
    # one snapshot read over the union window at the last commit's pre-block
    # union snapshot disabled: finalizeBatch deletes csr/bvh/bds[i-1] on
    # every finalization, so store values are only meaningful at each
    # commit's own pre-block. Keep the (much cheaper) correctness path:
    snap = {}
    snap_blk = commits[-1]["block"] - 1
    # revert-era commits: scalars flags alone decide (RevertBatch events are
    # oracle-side; inch/rri/bc are the state the transition itself reads)
    rev_flags = {}
    any_rev = True  # per-block reads always (see snap note above)
    out_dir = corpus_dir / "commits"
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    t0 = time.time()

    def build_one(wrpc, c):
        idx = c["batch_index"]
        sc = scalars_by_idx[idx]
        rev = any_rev or bool(sc["inch"] or sc["rri"])
        rec = per_commit_record(wrpc, rollup, c, sc, inputs, snap, tot, rev)
        rec["successor_parent_header"] = (
            "0x" + inputs[idx + 1]["parentBatchHeader"].hex()
            if idx + 1 in inputs else None)
        (out_dir / f"{idx}.json").write_text(
            json.dumps(rec, indent=2) + "\n")

    # parallelize across endpoints: each worker gets its own Rpc pinned to
    # a different URL subset (the record loops are pure I/O)
    import threading
    urls = rpc.urls
    todo = [c for c in commits
            if not (out_dir / f"{c['batch_index']}.json").exists()]
    NW = min(4, len(urls), max(1, len(todo)))
    shards = [todo[w::NW] for w in range(NW)]
    counters = [0]
    lock = threading.Lock()

    def worker(w):
        wrpc = Rpc([urls[w]] + urls[:w] + urls[w + 1:])
        for c in shards[w]:
            try:
                build_one(wrpc, c)
            except Exception as e:
                print(f"[bulk] record {c['batch_index']} failed: {e}",
                      flush=True)
                raise
            with lock:
                counters[0] += 1
                k = counters[0]
            if k % progress_every == 0:
                dt = time.time() - t0
                print(f"[bulk] {k}/{len(todo)} records "
                      f"({dt:.0f}s)", flush=True)

    ts = [threading.Thread(target=worker, args=(w,)) for w in range(NW)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    n = sum(1 for c in commits
            if (out_dir / f"{c['batch_index']}.json").exists())
    print(f"[bulk] records: {n} -> {out_dir} "
          f"(revert_in_window={any_rev})", flush=True)
    return {"n": n, "any_revert": any_rev, "min_lfi": min_lfi}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon.hist.replay_bulk")
    ap.add_argument("--rpc", default=",".join(
        ["https://eth.drpc.org",
         "https://eth-mainnet.public.blastapi.io",
         "https://eth-pokt.nodies.app",
         "https://ethereum-rpc.publicnode.com"]))
    ap.add_argument("--rollup",
                    default="0x759894ced0e6af42c26668076ffa84d02e3cef60")
    ap.add_argument("--manifest", type=Path,
                    default=Path("replay/M2/corpus/manifest.json"))
    ap.add_argument("--corpus", type=Path,
                    default=Path("replay/M2/corpus"))
    ap.add_argument("--cache-dir", type=Path, default=Path(
        __import__("os").environ.get("HOLON_CACHE",
                                     "~/.holon/cache/m2")).expanduser())
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(argv)
    rpc = Rpc([u for u in a.rpc.split(",") if u])
    r = build_records(rpc, a.rollup, a.manifest, a.corpus, a.cache_dir,
                      a.limit)
    print(f"built {r['n']} records (min_lfi={r['min_lfi']}, "
          f"any_revert={r['any_revert']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
