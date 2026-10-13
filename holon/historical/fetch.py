"""`python -m holon historical fetch`: acquire the Rollup's on-chain history into the snapshot, write the index.

    python -m holon historical fetch [--milestone M2] [--from N] [--to M] [--index PATH] [--snapshot DIR]
                                     [--workers N] [--blob-workers N] [--batch N] [--offline]

Phases, in this order (each resumable: an item already ok in the state, with its object in the snapshot, is
not fetched again):
  0. window   the hash of the window's last block (eth_getBlockByNumber); for the sidecar's to_block it must
              equal the frozen to_block_hash, else the chain is not the one the prereg froze and nothing runs.
  1. logs     eth_getLogs over the proxy and the sidecar's topics, pages of at most limits.get_logs_max_blocks
              blocks aligned at the window start. A page whose answer is refused as too large is split.
  2. tx       eth_getTransactionByHash for every transaction a log belongs to (JSON-RPC batches).
  3. blob     every blob of every commit transaction (a transaction with a CommitBatch log and blob versioned
              hashes): from the beacon API (/eth/v1/beacon/blob_sidecars/<slot>) when the block is inside the
              blob retention window, otherwise from the blob archive (api.blobscan.com
              /blobs/<versioned hash>/data). A blob is kept only when it is 131072 bytes and, when a commitment
              is served with it (beacon sidecars), that commitment hashes to the versioned hash
              (0x01 || sha256(commitment)[1:]). Archive blobs carry no commitment in the index: the replay
              computes each blob's KZG commitment from its bytes. A blob no source serves is "unavailable",
              never faked. Phases 3 and 4 run concurrently (different hosts).
  4. receipt  eth_getTransactionReceipt for the same transactions.
  5. index    results/M2/historical/index.json (or --index): canonical JSON (sorted keys, indent=1),
              a function of the window and the state only.

Sources (the sidecar's `sources`): execution = $ETH_RPC_URL when set, then the sidecar's public endpoint;
logs also fall back to the explorer (api.etherscan.io) when $ETHERSCAN_API_KEY is set. A source that refuses a
request below some block (an "archive" refusal, a null receipt) is not asked again for that method at or
below that block during the run. Every output names a source by host only.

Exit status: 0 when every log page, transaction and receipt is in the snapshot (blobs may be unavailable:
that is data, scored by I59-P6); 1 when the index was written with unavailable transactions or receipts;
2 when a log page could not be fetched (no index is written: an index without all logs would be wrong).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

from .. import ir
from . import net
from .store import Snapshot, StoreError, canon_bytes, resolve_snapshot

ROOT = Path(__file__).resolve().parents[2]
BLOB_BYTES = 131072
GENESIS_TIME = 1606824023            # mainnet beacon genesis (also read from the beacon when reachable)
RETENTION_SLOTS = 4096 * 32          # MIN_EPOCHS_FOR_BLOB_SIDECARS_REQUESTS
RETENTION_MARGIN = 256 * 32          # do not ask the beacon for blocks this close to its pruning edge
MIN_FREE_BYTES = 1_500_000_000       # below this, blobs are verified and hashed but not kept (recorded)
ARCHIVE_INTERVAL = 0.15              # the blob archive answers 503 to bursts: at most ~6.7 requests/s
HISTORY_WORDS = ("archive", "pruned", "history", "missing trie node", "not available", "personal token")


def sidecar(milestone: str = "M2", root: Path = ROOT) -> dict:
    return json.loads((Path(root) / "spec" / milestone / "lib" / "historical.json").read_text())


def default_index(milestone: str = "M2", root: Path = ROOT) -> Path:
    return Path(root) / "results" / milestone / "historical" / "index.json"


def log(msg: str) -> None:
    print(net.scrub(msg), flush=True)


class Fetcher:
    def __init__(self, side: dict, snap: Snapshot, workers: int = 8, batch: int = 10, blob_workers: int = 12):
        self.side, self.snap, self.workers, self.batch = side, snap, max(1, workers), max(1, batch)
        self.blob_workers = max(1, blob_workers)
        self.http = net.Http(floors={net.host(side["sources"]["blob_archive"]): ARCHIVE_INTERVAL})
        self.address = side["contracts"]["Rollup"]["address"].lower()
        self.topics = sorted(t.lower() for t in side["events"].values())
        self.commit_topic = side["events"]["CommitBatch(uint256,bytes32)"].lower()
        self.page_blocks = int(side["limits"]["get_logs_max_blocks"])
        urls = []
        for s in side["sources"]["execution"]:
            if s.startswith("env:"):
                v = os.environ.get(s[4:])
                if v:
                    urls.append(v)
            else:
                urls.append(s)
        if not urls:
            raise SystemExit("historical fetch: no execution source (set ETH_RPC_URL or fix the sidecar)")
        self.rpcs = [net.Rpc(self.http, u) for u in urls]
        self.beacon = side["sources"]["beacon"].rstrip("/")
        self.archive = side["sources"]["blob_archive"].rstrip("/")
        self.etherscan_key = os.environ.get("ETHERSCAN_API_KEY") or None
        self.horizon: dict[tuple[str, str], int] = {}
        self.failures: list[str] = []

    # ---------------------------------------------------------------- execution calls with source fallback
    def _skip(self, rpc: net.Rpc, method: str, block: int | None) -> bool:
        h = self.horizon.get((rpc.host, method))
        return h is not None and block is not None and block <= h

    def _refused(self, rpc: net.Rpc, method: str, block: int | None, err: Exception | None) -> None:
        """Remember an explicit history refusal ("archive", "pruned", ...): the source is not asked again for this
        method at or below that block. A null result or another error never sets it (it may be spurious; the
        item is retried by the next source, and by the next run)."""
        if block is None or err is None or not any(w in str(err).lower() for w in HISTORY_WORDS):
            return
        k = (rpc.host, method)
        self.horizon[k] = max(self.horizon.get(k, -1), block)

    def calls(self, method: str, todo: list[tuple[str, int, list]], start: int = 0) -> dict[str, tuple]:
        """{key: (result, host)} for every (key, block, params) some source answers with a non-null result;
        keys no source serves are left out. The first source tried rotates with `start`."""
        out: dict[str, tuple] = {}
        pending = list(todo)
        n = len(self.rpcs)
        for k in range(n):
            if not pending:
                break
            rpc = self.rpcs[(start + k) % n]
            ask = [t for t in pending if not self._skip(rpc, method, t[1])]
            if not ask:
                continue
            res = None
            for attempt in range(6):
                try:
                    res = rpc.batch([(method, p) for _, _, p in ask]) if len(ask) > 1 else [rpc.call(method, ask[0][2])]
                    break
                except net.SourceError as e:
                    if net.is_rate_limit(e):
                        self.http.pacer(rpc.host).limited()
                        time.sleep(min(15, 2 ** attempt))
                        continue
                    res = [e] * len(ask)
                    break
                except net.TransientError as e:
                    res = [e] * len(ask)
                    break
            if res is None:
                res = [net.TransientError(f"{rpc.host}: rate limited")] * len(ask)
            again = []
            for t, r in zip(ask, res):
                if isinstance(r, Exception) and net.is_rate_limit(r):
                    again.append(t)
                elif isinstance(r, Exception) or r is None:
                    if isinstance(r, net.SourceError):
                        self._refused(rpc, method, t[1], r)
                else:
                    out[t[0]] = (r, rpc.host)
            if again:  # rate-limited inside an accepted batch: one more pass on this source, singly
                time.sleep(2)
                for t in again:
                    try:
                        r = rpc.call(method, t[2])
                        if r is not None:
                            out[t[0]] = (r, rpc.host)
                    except (net.SourceError, net.TransientError):
                        pass
            pending = [t for t in pending if t[0] not in out]
        return out

    # ---------------------------------------------------------------- phase 0: the window
    def block_hash(self, n: int) -> str:
        cached = self.snap.get_meta(f"block_hash:{n}")
        if cached:
            return cached
        got = self.calls("eth_getBlockByNumber", [("b", n, [hex(n), False])])
        if "b" not in got:
            raise SystemExit(f"historical fetch: no source returned block {n}")
        h = got["b"][0]["hash"].lower()
        self.snap.set_meta(f"block_hash:{n}", h)
        self.snap.set_meta(f"block_ts:{n}", int(got["b"][0]["timestamp"], 16))
        return h

    # ---------------------------------------------------------------- phase 1: logs
    def _log_page(self, lo: int, hi: int) -> tuple[int, int, str | None, list[dict] | None, str]:
        params = [{"address": self.address, "topics": [self.topics], "fromBlock": hex(lo), "toBlock": hex(hi)}]
        errs = []
        for rpc in self.rpcs:
            if self._skip(rpc, "eth_getLogs", lo):
                continue
            for attempt in range(6):
                try:
                    res = rpc.call("eth_getLogs", params)
                    if not isinstance(res, list):
                        raise net.SourceError(f"{rpc.host}: eth_getLogs returned {type(res).__name__}")
                    return lo, hi, rpc.host, res, ""
                except net.SourceError as e:
                    if net.is_rate_limit(e):
                        self.http.pacer(rpc.host).limited()
                        time.sleep(min(30, 2 ** attempt))
                        continue
                    s = str(e).lower()
                    if any(w in s for w in ("too many", "limit exceeded", "range", "10000 results", "response size")) \
                            and hi > lo and "archive" not in s:
                        return lo, hi, None, None, "split"
                    self._refused(rpc, "eth_getLogs", hi, e)
                    errs.append(str(e)[:200])
                    break
                except net.TransientError as e:
                    errs.append(str(e)[:200])
                    break
        if self.etherscan_key:
            try:
                return lo, hi, "api.etherscan.io", self._etherscan_logs(lo, hi), ""
            except (net.SourceError, net.TransientError) as e:
                errs.append(str(e)[:200])
        return lo, hi, None, None, "; ".join(errs) or "no source"

    def _etherscan_logs(self, lo: int, hi: int) -> list[dict]:
        """The explorer's logs API: every log of the address in [lo, hi] (filtered to the topics by the caller),
        1000 per page. Logs come back in the JSON-RPC shape with hex quantities ("0x" meaning 0)."""
        out, page = [], 1
        while True:
            url = ("https://api.etherscan.io/v2/api?chainid=1&module=logs&action=getLogs"
                   f"&address={self.address}&fromBlock={lo}&toBlock={hi}&page={page}&offset=1000&apikey={self.etherscan_key}")
            doc = self.http.get_json(url)
            res = doc.get("result")
            if doc.get("status") != "1":
                if isinstance(res, list) and not res:
                    break
                if "no records" in str(doc.get("message", "")).lower():
                    break
                raise net.SourceError(net.scrub(f"api.etherscan.io: {doc.get('message')}: {str(res)[:200]}"))
            for lg in res:
                lg = dict(lg)
                for k in ("logIndex", "transactionIndex", "blockNumber"):
                    if lg.get(k) in ("0x", "", None):
                        lg[k] = "0x0"
                out.append(lg)
            if len(res) < 1000:
                break
            page += 1
            if page > 10:
                raise net.SourceError("api.etherscan.io: more than 10000 logs in one page range")
        return out

    def logs(self, lo: int, hi: int) -> bool:
        gaps = self.snap.covered(lo, hi)
        pages = []
        for a, b in gaps:
            # pages aligned at the window start, so that resumed and repeated runs ask the same ranges
            k = (a - lo) // self.page_blocks
            s = lo + k * self.page_blocks
            while s <= b:
                e = s + self.page_blocks - 1
                pages.append((max(a, s), min(b, e)))
                s = e + 1
        total, done, t0 = len(pages), 0, time.time()
        log(f"logs: {total} pages to fetch in [{lo}, {hi}] ({len(self.snap.pages())} done before)")
        failed = []
        with cf.ThreadPoolExecutor(self.workers) as ex:
            futs = {ex.submit(self._log_page, a, b) for a, b in pages}
            while futs:
                fin, futs = cf.wait(futs, return_when=cf.FIRST_COMPLETED)
                for f in fin:
                    a, b, src, res, err = f.result()
                    if err == "split":
                        m = (a + b) // 2
                        futs |= {ex.submit(self._log_page, a, m), ex.submit(self._log_page, m + 1, b)}
                        total += 1
                        continue
                    if res is None:
                        failed.append((a, b, err))
                        continue
                    rows = []
                    for lg in res:
                        if (lg.get("address") or "").lower() != self.address or not lg.get("topics") \
                                or lg["topics"][0].lower() not in self.topics or lg.get("removed"):
                            continue
                        blk = int(lg["blockNumber"], 16)
                        if not (a <= blk <= b):
                            continue
                        sha = self.snap.put(canon_bytes(lg, "log"))
                        rows.append({"tx": lg["transactionHash"].lower(), "log_index": int(lg["logIndex"], 16),
                                     "block": blk, "topic": lg["topics"][0].lower(), "sha256": sha})
                    self.snap.page_done(a, b, src, rows)
                    done += 1
                    if done % 100 == 0 or not futs:
                        rate = done / max(1e-9, time.time() - t0)
                        log(f"logs: {done}/{total} pages, {rate:.1f}/s, eta {int((total - done) / max(rate, 1e-9))}s")
        for a, b, err in failed:
            log(f"logs: page [{a}, {b}] failed: {err}")
        if failed:
            log(f"logs: {len(failed)} pages could not be fetched. Historical eth_getLogs needs an archive "
                "endpoint: set ETH_RPC_URL to one (a keyed provider, or a public gateway that serves history), "
                "or ETHERSCAN_API_KEY; then re-run (the fetch resumes)")
            return False
        return True

    # ---------------------------------------------------------------- phase 2 and 4: transactions, receipts
    def _rpc_items(self, kind: str, method: str, txs: list[tuple[int, str]]) -> None:
        todo = [(b, h) for b, h in txs if not self.snap.ok(kind, h)]
        log(f"{kind}: {len(todo)} of {len(txs)} to fetch")
        if not todo:
            return
        chunks = [todo[i:i + self.batch] for i in range(0, len(todo), self.batch)]
        done, t0, missing = 0, time.time(), 0
        with cf.ThreadPoolExecutor(self.workers) as ex:
            futs = {ex.submit(self.calls, method, [(h, b, [h]) for b, h in ch], i): ch for i, ch in enumerate(chunks)}
            for f in cf.as_completed(list(futs)):
                ch = futs.pop(f)   # drop the future: its result holds the fetched objects
                got = f.result()
                for b, h in ch:
                    if h in got:
                        obj, src = got[h]
                        if kind == "tx" and (obj.get("hash") or "").lower() != h:
                            self.snap.put_item(kind, h, b, h, None, src, "unavailable", {"why": "hash mismatch"})
                            missing += 1
                            continue
                        if kind == "receipt" and (obj.get("transactionHash") or "").lower() != h:
                            self.snap.put_item(kind, h, b, h, None, src, "unavailable", {"why": "hash mismatch"})
                            missing += 1
                            continue
                        sha = self.snap.put(canon_bytes(obj, kind))
                        self.snap.put_item(kind, h, b, h, sha, src, "ok")
                    else:
                        self.snap.put_item(kind, h, b, h, None, self.rpcs[0].host, "unavailable", {"why": "no source"})
                        missing += 1
                done += 1
                if done % 200 == 0 or done == len(chunks):
                    rate = done * self.batch / max(1e-9, time.time() - t0)
                    log(f"{kind}: {min(done * self.batch, len(todo))}/{len(todo)}, {rate:.1f}/s, missing {missing}, "
                        f"eta {int((len(todo) - done * self.batch) / max(rate, 1e-9))}s")

    # ---------------------------------------------------------------- phase 3: blobs
    def head(self) -> tuple[int | None, int | None, int]:
        """(head beacon slot, latest execution block, genesis time) or Nones when unreachable."""
        genesis = GENESIS_TIME
        try:
            g = self.http.get_json(self.beacon + "/eth/v1/beacon/genesis")
            genesis = int(g["data"]["genesis_time"])
            hd = self.http.get_json(self.beacon + "/eth/v1/beacon/headers/head")
            slot = int(hd["data"]["header"]["message"]["slot"])
        except (net.SourceError, net.TransientError, KeyError, ValueError, TypeError):
            slot = None
        try:
            latest = int(self.calls("eth_blockNumber", [("n", None, [])])["n"][0], 16)
        except (KeyError, ValueError, TypeError):
            latest = None
        return slot, latest, genesis

    def _beacon_blobs(self, block: int, genesis: int) -> dict[str, tuple[bytes, str]] | None:
        ts = self.snap.get_meta(f"block_ts:{block}")
        if ts is None:
            got = self.calls("eth_getBlockByNumber", [("b", block, [hex(block), False])])
            if "b" not in got:
                return None
            ts = int(got["b"][0]["timestamp"], 16)
        slot = (ts - genesis) // 12
        try:
            doc = self.http.get_json(f"{self.beacon}/eth/v1/beacon/blob_sidecars/{slot}")
        except (net.SourceError, net.TransientError):
            return None
        out = {}
        for sc in doc.get("data") or []:
            try:
                c = bytes.fromhex(sc["kzg_commitment"][2:])
                blob = bytes.fromhex(sc["blob"][2:])
            except (KeyError, ValueError, TypeError):
                continue
            out[versioned_hash(c)] = (blob, "0x" + c.hex())
        return out

    def _archive_data(self, vh: str) -> bytes | None:
        """The blob's bytes from the blob archive (one request: /blobs/<versioned hash>/data)."""
        try:
            status, body = self.http.request(f"{self.archive}/blobs/{vh}/data")
        except net.TransientError:
            return None
        if status != 200:
            return None
        try:
            d = json.loads(body)
            data = d if isinstance(d, str) else (d.get("data") if isinstance(d, dict) else None)
        except ValueError:
            data = body.decode("ascii", "replace").strip()
        if not (isinstance(data, str) and data.startswith("0x")):
            return None
        try:
            return bytes.fromhex(data[2:])
        except ValueError:
            return None

    def _archive_commitment(self, vh: str) -> str | None:
        """The commitment the blob archive records for the blob (/blobs/<versioned hash>)."""
        try:
            doc = self.http.get_json(f"{self.archive}/blobs/{vh}")
        except (net.SourceError, net.TransientError):
            return None
        c = doc.get("commitment") if isinstance(doc, dict) else None
        return c.lower() if isinstance(c, str) and c.startswith("0x") else None

    def _blob_task(self, block: int, tx: str, hashes: list[str], beacon_ok: bool, genesis: int) -> list[tuple]:
        """[(versioned hash, position, blob bytes | None, commitment | None, source host, keep)] for one transaction.

        A beacon blob comes with its sidecar's commitment, which must hash to the versioned hash. An archive blob is
        fetched with one request and kept with no commitment: the replay computes its KZG commitment from the bytes
        (kzg4844 in the pinned checkout's go-ethereum) and checks that against the versioned hash. Only when the
        disk is short (the blob is hashed but not kept) is the archive's recorded commitment fetched and checked
        here, since the bytes will not be there to check later."""
        res, beacon = [], None
        keep = shutil.disk_usage(self.snap.dir).free > MIN_FREE_BYTES
        for pos, vh in enumerate(hashes):
            blob, comm, src = None, None, None
            if beacon_ok:
                if beacon is None:
                    beacon = self._beacon_blobs(block, genesis) or {}
                if vh in beacon:
                    (blob, comm), src = beacon[vh], net.host(self.beacon)
            if blob is None:
                blob = self._archive_data(vh)
                src = net.host(self.archive) if blob is not None else None
                if blob is not None and not keep:
                    comm = self._archive_commitment(vh)
                    if comm is None:
                        blob = None
            if blob is not None and (len(blob) != BLOB_BYTES
                                     or (comm is not None and versioned_hash(bytes.fromhex(comm[2:])) != vh)):
                blob = None  # not a blob, or a served commitment that does not hash to the versioned hash
            if blob is None:
                res.append((vh, pos, None, None, net.host(self.archive), keep))
            else:
                res.append((vh, pos, blob, comm, src, keep))
        return res

    def blob_jobs(self, txs: list[tuple[int, str]], commit_txs: set[str]) -> list[tuple[int, str, list[str]]]:
        jobs = []
        for b, h in txs:
            if h not in commit_txs:
                continue
            it = self.snap.item("tx", h)
            if not it or it["status"] != "ok":
                continue
            hashes = [x.lower() for x in self.snap.read_json(it["sha256"]).get("blobVersionedHashes") or []]
            need = [vh for vh in hashes if not self._blob_done(h, vh)]
            if need:
                jobs.append((b, h, hashes))
        return jobs

    def _blob_done(self, tx: str, vh: str) -> bool:
        it = self.snap.item("blob", f"{tx}:{vh}")
        if not it or it["status"] != "ok":
            return False
        return (not it["extra"].get("kept", True)) or self.snap.has(it["sha256"])

    def store_blobs(self, tx: str, block: int, res: list[tuple]) -> int:
        bad = 0
        for vh, pos, blob, comm, src, keep in res:
            key = f"{tx}:{vh}"
            if blob is None:
                self.snap.put_item("blob", key, block, tx, None, src, "unavailable",
                                   {"versioned_hash": vh, "position": pos})
                bad += 1
                continue
            sha = self.snap.put(blob, gz=True) if keep else hashlib.sha256(blob).hexdigest()
            self.snap.put_item("blob", key, block, tx, sha, src, "ok",
                               {"versioned_hash": vh, "position": pos, "commitment": comm, "kept": keep})
        return bad

    # ---------------------------------------------------------------- phase 3 + 4 together
    def blobs_and_receipts(self, txs: list[tuple[int, str]], commit_txs: set[str]) -> None:
        jobs = self.blob_jobs(txs, commit_txs)
        slot, latest, genesis = self.head() if jobs else (None, None, GENESIS_TIME)
        edge = None if latest is None or slot is None else latest - (RETENTION_SLOTS - RETENTION_MARGIN)
        log(f"blob: {len(jobs)} transactions with blobs to fetch (beacon serves blocks above {edge})")
        rec = threading_thread(self._rpc_items, "receipt", "eth_getTransactionReceipt", txs)
        done, bad, t0 = 0, 0, time.time()
        with cf.ThreadPoolExecutor(self.blob_workers) as ex:
            futs = {ex.submit(self._blob_task, b, h, hs, edge is not None and b > edge, genesis): (b, h) for b, h, hs in jobs}
            for f in cf.as_completed(list(futs)):
                b, h = futs.pop(f)  # drop the future: its result holds the blob bytes
                bad += self.store_blobs(h, b, f.result())
                done += 1
                if done % 200 == 0 or done == len(jobs):
                    rate = done / max(1e-9, time.time() - t0)
                    log(f"blob: {done}/{len(jobs)} transactions, {rate:.2f}/s, unavailable {bad}, "
                        f"eta {int((len(jobs) - done) / max(rate, 1e-9))}s, free {shutil.disk_usage(self.snap.dir).free >> 20} MiB")
        rec.join()
        if rec.error:
            raise rec.error


class threading_thread:
    """Run fn(*args) in a thread; join() re-raises nothing, .error holds an exception it raised."""

    def __init__(self, fn, *args):
        import threading
        self.error = None

        def run():
            try:
                fn(*args)
            except BaseException as e:  # noqa: BLE001 - reported by the caller
                self.error = e
        self.t = threading.Thread(target=run, daemon=True)
        self.t.start()

    def join(self):
        self.t.join()


def versioned_hash(commitment: bytes) -> str:
    return "0x01" + hashlib.sha256(commitment).hexdigest()[2:]


# ---------------------------------------------------------------- the index
def build_index(side: dict, snap: Snapshot, lo: int, hi: int, to_hash: str, commit_topic: str) -> tuple[dict, dict]:
    logs = snap.logs(lo, hi)
    items, missing = [], {"tx": 0, "receipt": 0, "blob": 0}
    txs = sorted({(lg["block"], lg["tx"]) for lg in logs})
    commit_txs = {lg["tx"] for lg in logs if lg["topic"] == commit_topic}
    for lg in logs:
        items.append({"kind": "log", "block": lg["block"], "tx": lg["tx"], "log_index": lg["log_index"],
                      "topic": lg["topic"], "sha256": lg["sha256"], "source": lg["source"], "status": "ok"})
    txi, rci, bli = snap.items("tx"), snap.items("receipt"), snap.items("blob")
    blobs_by_tx: dict[str, list[dict]] = {}
    for it in bli.values():
        blobs_by_tx.setdefault(it["tx"], []).append(it)
    for b, h in txs:
        for kind, table in (("tx", txi), ("receipt", rci)):
            it = table.get(h)
            ok = bool(it and it["status"] == "ok")
            items.append({"kind": kind, "block": b, "tx": h, "sha256": it["sha256"] if ok else None,
                          "source": it["source"] if it else None, "status": "ok" if ok else "unavailable"})
            missing[kind] += 0 if ok else 1
        if h in commit_txs and txi.get(h, {}).get("status") == "ok":
            hashes = [x.lower() for x in snap.read_json(txi[h]["sha256"]).get("blobVersionedHashes") or []]
            have = {it["extra"].get("versioned_hash"): it for it in blobs_by_tx.get(h, [])}
            for pos, vh in enumerate(hashes):
                it = have.get(vh)
                ok = bool(it and it["status"] == "ok")
                e = it["extra"] if it else {}
                row = {"kind": "blob", "block": b, "tx": h, "versioned_hash": vh, "position": pos,
                       "sha256": it["sha256"] if ok else None, "commitment": e.get("commitment") if ok else None,
                       "source": it["source"] if it else None, "status": "ok" if ok else "unavailable"}
                if ok and e.get("kept") is False:
                    row["kept"] = False
                items.append(row)
                missing["blob"] += 0 if ok else 1
    items.sort(key=lambda i: (i["block"], i["tx"], i["kind"], i.get("log_index", -1), i.get("sha256") or "",
                              i.get("position", -1)))
    counts: dict[str, int] = {}
    for i in items:
        counts[i["kind"]] = counts.get(i["kind"], 0) + 1
    doc = {"window": {"from_block": lo, "to_block": hi, "to_block_hash": to_hash},
           "snapshot": str(snap.dir), "items": items, "counts": dict(sorted(counts.items()))}
    doc["index_sha256"] = hashlib.sha256(ir.canonical_json(doc)).hexdigest()
    return doc, missing


def write_index(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, sort_keys=True, indent=1) + "\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon historical fetch")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--from", dest="lo", type=int)
    ap.add_argument("--to", dest="hi", type=int)
    ap.add_argument("--index")
    ap.add_argument("--snapshot")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--batch", type=int, default=10, help="JSON-RPC calls per batch request")
    ap.add_argument("--blob-workers", type=int, default=12)
    ap.add_argument("--offline", action="store_true",
                    help="no network: write the index from the snapshot state alone (every log page must be done; "
                         "items the state lacks are listed as unavailable)")
    a = ap.parse_args(argv)
    side = sidecar(a.milestone)
    w = side["window"]
    lo = w["from_block"] if a.lo is None else a.lo
    hi = w["to_block"] if a.hi is None else a.hi
    if not (w["from_block"] <= lo <= hi <= w["to_block"]):
        print(f"historical fetch: [{lo}, {hi}] is not inside the sidecar's window [{w['from_block']}, {w['to_block']}]",
              file=sys.stderr)
        return 2
    try:
        snap = Snapshot(resolve_snapshot(a.snapshot))
    except StoreError as e:
        print(f"historical fetch: {e}", file=sys.stderr)
        return 2
    if a.offline:
        to_hash = snap.get_meta(f"block_hash:{hi}")
        gaps = snap.covered(lo, hi)
        if not to_hash or gaps:
            print(f"historical fetch --offline: the state lacks {'the hash of block %d' % hi if not to_hash else ''}"
                  f"{' and ' if not to_hash and gaps else ''}{'%d log ranges' % len(gaps) if gaps else ''}",
                  file=sys.stderr)
            return 2
        if hi == w["to_block"] and to_hash != w["to_block_hash"].lower():
            print("historical fetch --offline: the state's to_block hash differs from the sidecar's", file=sys.stderr)
            return 2
        commit_topic = side["events"]["CommitBatch(uint256,bytes32)"].lower()
        doc, missing = build_index(side, snap, lo, hi, to_hash, commit_topic)
        out = Path(a.index) if a.index else default_index(a.milestone)
        write_index(doc, out)
        log(f"wrote {out} (offline): counts {doc['counts']}, unavailable {missing}")
        snap.close()
        return 1 if missing["tx"] or missing["receipt"] else 0
    f = Fetcher(side, snap, a.workers, a.batch, a.blob_workers)
    log(f"historical fetch: window [{lo}, {hi}], snapshot {snap.dir}, execution sources "
        f"{[r.host for r in f.rpcs]}, explorer {'yes' if f.etherscan_key else 'no'}")
    to_hash = f.block_hash(hi)
    if hi == w["to_block"] and to_hash != w["to_block_hash"].lower():
        print(f"historical fetch: block {hi} has hash {to_hash} on this chain, the sidecar froze "
              f"{w['to_block_hash']}: refusing to fetch", file=sys.stderr)
        return 2
    if not f.logs(lo, hi):
        return 2
    logs = snap.logs(lo, hi)
    txs = sorted({(lg["block"], lg["tx"]) for lg in logs})
    commit_txs = {lg["tx"] for lg in logs if lg["topic"] == f.commit_topic}
    log(f"logs: {len(logs)} in the window, {len(txs)} transactions, {len(commit_txs)} with a CommitBatch log")
    f._rpc_items("tx", "eth_getTransactionByHash", txs)
    f.blobs_and_receipts(txs, commit_txs)
    doc, missing = build_index(side, snap, lo, hi, to_hash, f.commit_topic)
    out = Path(a.index) if a.index else default_index(a.milestone)
    write_index(doc, out)
    log(f"wrote {out}: counts {doc['counts']}, unavailable {missing}, calls {dict(sorted(f.http.calls.items()))}")
    snap.close()
    return 1 if missing["tx"] or missing["receipt"] else 0
