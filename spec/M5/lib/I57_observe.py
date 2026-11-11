"""The L9 observation tool (I57): the only producer of observation sets that the key I57 admits.

    python -I spec/M5/lib/I57_observe.py <set> [--root DIR] [--out DIR]

<set> is a key of spec/M5/lib/I57_observe_plan.json `sets` (the plan). The tool executes that plan and writes
<out>/<set>.json (spec/M5/lib/inputs.schema.json#/$defs/observation_set) and <out>/<set>.meta.json. The default <out>
is the plan's output.dir.

What it records about itself, from its own run (the lead's condition G3 on I54):
  producer       always "spec/M5/lib/I57_observe.py" (this file's repo path), never a value read from anywhere
  source_sha256  the sha256 of this file's bytes, read at run time
  reads          every source this run actually read: each file (with the fields read from it) and each endpoint
                 template (host, method and path with the varying part as {..}), added by the one function that
                 opens it (_Net.get, _Net.rpc, _read_file)
It reads the plan, the target instrument the plan names and the I59 index (only the plan's index.fields). It never
reads the module records file, so no module parameter can enter an observation (BLOB_BYTES, the size of a blob
in bytes, happens to equal the DA module's W in slots; it is the blob format's constant, never compared with an age). It is
stdlib only and imports nothing from the repository, so its sha256 pins everything it runs.

Deterministic where the world allows: sampling is a function of the plan, the index and the chain heads read at the
start; outputs are json.dumps(obj, indent=2, sort_keys=True) + newline, with no timestamps. The observations
themselves are what the network answered when the tool ran: the set is the record of that run.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PRODUCER = "spec/M5/lib/I57_observe.py"
ROOT = Path(__file__).resolve().parents[3]
PLAN = Path("spec") / "M5" / "lib" / "I57_observe_plan.json"
BLOB_BYTES = 131072


def _dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _log(msg: str) -> None:
    print(f"observe: {msg}", file=sys.stderr, flush=True)


def source_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _vh(commitment_hex: str) -> str:
    """The versioned hash of a KZG commitment: version byte 0x01, then sha256(commitment)[1:]."""
    return "0x01" + hashlib.sha256(bytes.fromhex(commitment_hex[2:])).hexdigest()[2:]


class _Net:
    def __init__(self, plan: dict, reads: set):
        h = plan["http"]
        self.ua, self.timeout = h["user_agent"], h["timeout_s"]
        self.attempts, self.backoff = h["attempts"], h["backoff_s"]
        self.batch = h["rpc_batch"]
        self.src = plan["sources"]
        self.reads = reads
        self.calls = 0

    def _once(self, url: str, body: bytes | None):
        hdrs = {"user-agent": self.ua, "accept": "application/json"}
        if body is not None:
            hdrs["content-type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=hdrs, method="POST" if body is not None else "GET")
        self.calls += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read() if e.fp else b""
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            return None, b""

    def get(self, source: str, path: str, template: str, final=(200, 403, 404)) -> tuple:
        """(status, body) of GET <source><path>; retried while the status is not in `final`. status None: no answer."""
        self.reads.add(f"GET {self.src[source]}{template}")
        status, body = None, b""
        for i in range(self.attempts):
            status, body = self._once(self.src[source] + path, None)
            if status in final:
                return status, body
            if i < len(self.backoff):
                time.sleep(self.backoff[i])
        return status, body

    def get_json(self, source: str, path: str, template: str):
        status, body = self.get(source, path, template, final=(200,))
        if status != 200:
            raise RuntimeError(f"GET {source}{path}: status {status}")
        return json.loads(body)

    def rpc_many(self, calls: list[tuple[str, list]]) -> list:
        """The results of JSON-RPC calls to the execution source, in order (batches of http.rpc_batch)."""
        out = []
        for m in sorted({m for m, _ in calls}):
            self.reads.add(f"RPC {self.src['execution']} {m}")
        for lo in range(0, len(calls), self.batch):
            chunk = calls[lo:lo + self.batch]
            payload = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(chunk)]
            for i in range(self.attempts):
                status, body = self._once(self.src["execution"], json.dumps(payload).encode())
                docs = None
                if status == 200:
                    try:
                        docs = json.loads(body)
                    except ValueError:
                        docs = None
                if isinstance(docs, list) and len(docs) == len(chunk) and all("result" in d for d in docs):
                    by = {d["id"]: d["result"] for d in docs}
                    out.extend(by[i] for i in range(len(chunk)))
                    break
                if i < len(self.backoff):
                    time.sleep(self.backoff[i])
            else:
                raise RuntimeError(f"RPC batch of {len(chunk)} ({chunk[0][0]}): no complete answer")
        return out

    def rpc(self, method: str, params: list):
        return self.rpc_many([(method, params)])[0]


def _read_file(root: Path, rel: str, reads: set, fields: list[str] | None = None):
    reads.add(f"FILE {rel}" + (f"#{','.join(fields)}" if fields else ""))
    return json.loads((root / rel).read_text(encoding="utf-8"))


class Observer:
    def __init__(self, root: Path):
        self.root = root
        self.reads: set[str] = set()
        self.plan = _read_file(root, PLAN.as_posix(), self.reads)
        self.net = _Net(self.plan, self.reads)
        tgt = self.plan["target"]
        inst = _read_file(root, tgt["instrument"], self.reads, ["contracts"])
        self.address = inst["contracts"][tgt["contract"]]["address"].lower()
        self.meta: dict = {}

    # ------------------------------------------------------------ shared readers
    def index_blobs(self) -> list[dict]:
        ix = self.plan["index"]
        doc = _read_file(self.root, ix["path"], self.reads, ix["fields"])
        keep = [f for f in ix["fields"] if f != "kind"]
        return [{k: it[k] for k in keep} for it in doc["items"] if it.get("kind") == "blob"]

    def head_block(self) -> int:
        return int(self.net.rpc("eth_blockNumber", []), 16)

    def head_slot(self) -> int:
        d = self.net.get_json("beacon", "/eth/v1/beacon/headers/head", "/eth/v1/beacon/headers/head")
        return int(d["data"]["header"]["message"]["slot"])

    def genesis_time(self) -> int:
        d = self.net.get_json("beacon", "/eth/v1/beacon/genesis", "/eth/v1/beacon/genesis")
        return int(d["data"]["genesis_time"])

    def tx_hashes(self, txs: list[str]) -> dict[str, list[str]]:
        """{tx: its blobVersionedHashes} from the execution source."""
        res = self.net.rpc_many([("eth_getTransactionByHash", [t]) for t in txs])
        return {t: [h.lower() for h in (r or {}).get("blobVersionedHashes") or []] for t, r in zip(txs, res)}

    def block_ts(self, blocks: list[int]) -> dict[int, int]:
        res = self.net.rpc_many([("eth_getBlockByNumber", [hex(b), False]) for b in blocks])
        return {b: int(r["timestamp"], 16) for b, r in zip(blocks, res)}

    # ------------------------------------------------------------ obs-da-beacon
    def da(self, cfg: dict) -> list[dict]:
        genesis = self.genesis_time()
        q0, b0 = self.head_slot(), self.head_block()
        self.meta["start"] = {"slot": q0, "block": b0}
        n, max_age = cfg["n"], cfg["max_age_slots"]
        b_ref = b0 - max_age
        s_ref = (self.block_ts([b_ref])[b_ref] - genesis) // 12
        rate = (b0 - b_ref) / max(1, q0 - s_ref)
        by_block: dict[int, set] = {}
        chosen = []
        for k in range(n):
            est = int(round(b0 - (k + 0.5) * max_age / n * rate))
            doc = self.net.get_json("archive", f"/transactions?to={self.address}&startBlock={est}&sort=asc&ps=5",
                                    "/transactions?to={address}&startBlock={block}&sort=asc&ps=5")
            for tx in doc.get("transactions") or []:
                b = int(tx["blockNumber"])
                if b not in by_block and b <= b0:
                    by_block[b] = {tx["hash"].lower()}
                    chosen.append(b)
                    break
        self.meta["sampling"] = {"b_ref": b_ref, "s_ref": s_ref, "rate": round(rate, 9)}
        txs = sorted({t for b in chosen for t in by_block[b]})
        vhs = self.tx_hashes(txs)
        ts = self.block_ts(sorted(chosen))
        items, unresolved, counts = [], [], {}
        newest = max(chosen)

        def query(b: int):
            t = (ts[b] - genesis) // 12
            q = self.head_slot()
            st, body = self.net.get("beacon", f"/eth/v1/beacon/blob_sidecars/{t}", "/eth/v1/beacon/blob_sidecars/{slot}")
            want = {h for tx in by_block[b] for h in vhs.get(tx, [])}
            if st == 200:
                try:
                    got = {_vh(sc["kzg_commitment"]) for sc in json.loads(body).get("data") or []}
                except (ValueError, KeyError, TypeError):
                    got = set()
                return {"t": t, "q": q, "observed": bool(got & want), "block": b, "status": 200}
            if st in (403, 404):
                return {"t": t, "q": q, "observed": False, "block": b, "status": st}
            return None

        pending = list(chosen)
        for rnd in range(2):
            retry = []
            for lo in range(0, len(pending), 20):
                part = pending[lo:lo + 20]
                got = [(b, query(b)) for b in part]
                live = query(newest)
                if live is None or live["status"] != 200 or not live["observed"]:
                    retry.extend(part)
                    continue
                for b, o in got:
                    if o is None:
                        retry.append(b)
                    else:
                        items.append(o)
                _log(f"obs-da-beacon round {rnd}: {len(items)} observed, {len(retry)} to retry")
            pending = retry
            if not pending:
                break
        unresolved = sorted(pending)
        for o in items:
            counts[str(o["status"])] = counts.get(str(o["status"]), 0) + 1
        self.meta.update({"unresolved": unresolved, "status_counts": counts, "sampled": len(chosen),
                          "end": {"slot": self.head_slot(), "block": self.head_block()}})
        return items

    # ------------------------------------------------------------ obs-l1-depth
    def l1(self, cfg: dict) -> list[dict]:
        depths = sorted(cfg["depths"])
        seen: dict[tuple[int, int], str] = {}
        heads = []
        start = time.monotonic()
        last = None
        self.meta["start"] = {"block": self.head_block()}
        while time.monotonic() - start < cfg["duration_s"]:
            try:
                blk = self.net.rpc("eth_getBlockByNumber", ["latest", False])
                h = int(blk["number"], 16)
                if h != last:
                    nums = [h - j for j in depths]
                    res = self.net.rpc_many([("eth_getBlockByNumber", [hex(x), False]) for x in nums])
                    for j, x, r in zip(depths, nums, res):
                        if r is not None:
                            seen[(h, j)] = r["hash"].lower()
                    heads.append(h)
                    last = h
            except RuntimeError as e:
                _log(f"obs-l1-depth poll: {e}")
            time.sleep(cfg["poll_s"])
        top = max(heads)
        waited = 0
        while waited <= 2400:
            fin = int(self.net.rpc("eth_getBlockByNumber", ["finalized", False])["number"], 16)
            if fin >= top:
                break
            time.sleep(30)
            waited += 30
        nums = sorted({h - j for (h, j) in seen})
        res = self.net.rpc_many([("eth_getBlockByNumber", [hex(x), False]) for x in nums])
        canon = {x: r["hash"].lower() for x, r in zip(nums, res) if r is not None}
        items = [{"t": h - j, "head": h, "observed": canon[h - j] == hsh, "depth": j}
                 for (h, j), hsh in sorted(seen.items()) if (h - j) in canon]
        self.meta.update({"heads": len(heads), "finalized_at_check": fin, "highest_head": top,
                          "unresolved": sorted(x for x in nums if x not in canon),
                          "end": {"block": self.head_block()}})
        return items

    # ------------------------------------------------------------ obs-fetch-archive
    def fetch(self, cfg: dict) -> list[dict]:
        blobs, seen = [], set()
        for it in sorted(self.index_blobs(), key=lambda x: (int(x["block"]), x["tx"], int(x["position"]))):
            if it["versioned_hash"] not in seen:
                seen.add(it["versioned_hash"])
                blobs.append(it)
        N, n = len(blobs), cfg["n_committed"]
        sample = [blobs[int((k + 0.5) * N / n)] for k in range(n)]
        vhs = self.tx_hashes(sorted({s["tx"].lower() for s in sample}))
        self.meta["start"] = {"block": self.head_block()}
        items = []
        for k, s in enumerate(sample):
            vh = s["versioned_hash"].lower()
            tx_vhs = vhs.get(s["tx"].lower(), [])
            st, body = self.net.get("archive", f"/blobs/{vh}/data", "/blobs/{versioned_hash}/data")
            data = _blob_bytes(body) if st == 200 else None
            items.append({"t": int(s["block"]), "committed": vh in tx_vhs, "versioned_hash": vh, "flipped": False,
                          "observed": data is not None and len(data) == BLOB_BYTES
                          and hashlib.sha256(data).hexdigest() == s["sha256"], "status": st})
            if k % cfg["flip_every"] == 0:
                fv = vh[:-1] + format(int(vh[-1], 16) ^ 1, "x")
                st2, body2 = self.net.get("archive", f"/blobs/{fv}/data", "/blobs/{versioned_hash}/data")
                d2 = _blob_bytes(body2) if st2 == 200 else None
                items.append({"t": int(s["block"]), "committed": fv in tx_vhs, "versioned_hash": fv, "flipped": True,
                              "observed": d2 is not None and len(d2) == BLOB_BYTES, "status": st2})
            if k % 40 == 0:
                _log(f"obs-fetch-archive: {k + 1}/{n}")
        counts = {}
        for o in items:
            counts[str(o["status"])] = counts.get(str(o["status"]), 0) + 1
        self.meta.update({"status_counts": counts, "index_blobs_distinct": N, "end": {"block": self.head_block()}})
        return items


def _blob_bytes(body: bytes):
    try:
        d = json.loads(body)
        s = d if isinstance(d, str) else (d.get("data") if isinstance(d, dict) else None)
    except ValueError:
        s = body.decode("ascii", "replace").strip()
    if not (isinstance(s, str) and s.startswith("0x")):
        return None
    try:
        return bytes.fromhex(s[2:])
    except ValueError:
        return None


RUNS = {"obs-da-beacon": "da", "obs-l1-depth": "l1", "obs-fetch-archive": "fetch"}


def run(name: str, root: Path = ROOT, out: Path | None = None) -> Path:
    ob = Observer(root)
    if name not in ob.plan["sets"] or name not in RUNS:
        raise SystemExit(f"observe: unknown set {name!r}")
    items = getattr(ob, RUNS[name])(ob.plan["sets"][name])
    out = out or (root / ob.plan["output"]["dir"])
    out.mkdir(parents=True, exist_ok=True)
    doc = {"set": name, "producer": PRODUCER, "source_sha256": source_sha256(), "reads": sorted(ob.reads),
           "items": items}
    (out / f"{name}.json").write_text(_dumps(doc), encoding="utf-8")
    meta = dict(ob.meta, items=len(items), http_calls=ob.net.calls)
    (out / f"{name}.meta.json").write_text(_dumps(meta), encoding="utf-8")
    _log(f"wrote {out / (name + '.json')}: {len(items)} items")
    return out / f"{name}.json"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="I57_observe.py", description=__doc__,
                                 formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("set")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    run(a.set, a.root.resolve(), a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
