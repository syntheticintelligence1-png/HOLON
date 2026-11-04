"""`python -m holon historical fetch-state`: the supplementary acquisition of I23, only what I59 lacks.

    python -m holon historical fetch-state [--milestone M2] [--snapshot DIR] [--out PATH] [--offline] [--workers N]

The contract is the docstring of tests_m2/test_historical_exit.py; the kinds, sources and rules are the instrument's
supplement (spec/<M>/lib/historical_exit.json). Every item goes into the I59 snapshot (content-addressed as I59's:
objects/<aa>/<sha256>, the name the sha256 of the bytes), recorded in the snapshot's supplement.sqlite (I59's
state.sqlite is never written), and indexed in results/<M>/historical/supplement.json.

Kinds (key; block; the object's bytes):
  header        "<block>"; b; the canonical JSON of HEADER_FIELDS of eth_getBlockByNumber(b), lowercase hex. Its hash
                must be the block hash the in-scope transaction records.
  storage       "<address>:<slot>"; the block read at; canonical {address, block, slot, value} of eth_getStorageAt.
  call          "<to>:<sha256 of the calldata>:<from>"; b - 1; canonical {block, data, from, to, value, ok, ret,
                error} of eth_call (an execution revert is an answer: ok false, ret its revert data or null).
  call_after    the same call at b: a stability check, never an answer.
  code          "<address>"; to_block; the runtime code's raw bytes (eth_getCode), so the sha256 is the code's.
  log_other     "<tx>:<log index>"; the log's block; I59's canonical log bytes (holon.historical.store), topic0 outside
                I59's five. A page's log of the five topics must be byte-identical to I59's indexed log (else the
                fetch fails, exit 2) and is not stored again.
  tx_other, receipt_other  "<tx>"; the block; I59's canonical transaction and receipt bytes, for a transaction a
                log_other item belongs to that I59 did not index.

What is fetched (in this order; each step resumable, an item already ok in the state is never fetched again):
  1. log_other: eth_getLogs of the proxy, every topic, over the trans window, in pages of I59's limit aligned at the
     window start (a page refused as too large is split); their transactions and receipts (tx_other, receipt_other).
  2. header: every block holding an in-scope transaction (I59's index items in the window, plus tx_other).
  3. code: eth_getCode of the last upgrade's implementation at to_block, and the proxy's EIP-1967 implementation slot
     at to_block (a storage item).
  4. discovery: which slots and calls the replay needs. Every in-scope transaction is stepped through the extracted
     model (holon.historical.stepper, the model unchanged) on the chain's storage at b - 1, fetched as the step reads
     it, its external calls answered by eth_call at b - 1, in passes until no step needs more. This only decides what
     to fetch: the replay (holon historical trans) never reads a b - 1 value as model state.
  5. storage at b - 1 and b of every slot a step reads or writes; at from_block - 1 (initial) and to_block (final) of
     every slot any step touches; call_after at b of every call item.
  6. completion: the replay itself, the model's state threaded from the initial values as holon historical trans
     threads it; any slot or call it needs that is still absent is fetched, until it needs nothing more.
Then the plan (the items of this run) is stored in the state and the index is written from it.

Sources: the instrument's supplement.sources.execution in order ("env:NAME" is that variable's URL when set). A source
that refuses a method with a history refusal ("archive", "personal token", "historical state", ...) is not asked for
that method again in the run. Requests are paced per host and retried (holon.historical.net). Outputs name a source by
host only; no secret is printed or written.

--offline writes the index from the snapshot state (the stored plan and items) without the network.

Exit status: 0 when every item of the plan is ok; 1 when some item is unavailable (listed; never faked); 2 when the
acquisition cannot proceed (no snapshot, no source, a log page no source serves, a five-topic log that differs from
I59's).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
from pathlib import Path

from .. import ir
from . import net
from . import stepper as S
from .context import ContextError, Window
from .store import canon_bytes

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("header", "storage", "call", "call_after", "code", "log_other", "tx_other", "receipt_other")
HEADER_FIELDS = ("baseFeePerGas", "blobGasUsed", "excessBlobGas", "gasLimit", "gasUsed", "hash", "miner", "mixHash",
                 "number", "parentHash", "stateRoot", "timestamp")
QTY = {"baseFeePerGas", "blobGasUsed", "excessBlobGas", "gasLimit", "gasUsed", "number", "timestamp"}
STATE_FILE = "supplement.sqlite"
HISTORY_WORDS = ("archive", "pruned", "personal token", "historical state", "missing trie node", "not available",
                 "state is not available", "header not found")
BATCH = 10
# the public archive gateway refuses a request over its cost budget (6 eth_calls, or 25 eth_getStorageAt, measured)
BATCH_BY_METHOD = {"eth_call": 4, "eth_getLogs": 1, "eth_getStorageAt": 16}
MAX_DISCOVERY_PASSES = 200
SLICE = 4000          # items fetched (and stored) per slice


def log(msg: str) -> None:
    print(net.scrub(msg), flush=True)


def default_out(milestone: str = "M2", root: Path = ROOT) -> Path:
    return Path(root) / "results" / milestone / "historical" / "supplement.json"


def _qty(v):
    return hex(int(v, 16)) if isinstance(v, str) and v.startswith("0x") else v


def canon_header(b: dict) -> bytes:
    out = {}
    for k in HEADER_FIELDS:
        v = b.get(k)
        out[k] = _qty(v) if k in QTY else (v.lower() if isinstance(v, str) else v)
    return ir.canonical_json(out)


def word(v) -> int:
    if not (isinstance(v, str) and v.startswith("0x")):
        raise ValueError(f"not a hex word: {str(v)[:80]}")
    return int(v[2:] or "0", 16)


# ---------------------------------------------------------------- the supplement's state (beside I59's, never in it)
class State:
    def __init__(self, directory: Path):
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(Path(directory) / STATE_FILE), timeout=120, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS items (kind TEXT, block INTEGER, key TEXT, sha256 TEXT, source TEXT, status TEXT,
                                              topic TEXT, PRIMARY KEY (kind, block, key));
            CREATE TABLE IF NOT EXISTS pages (lo INTEGER, hi INTEGER, source TEXT, n INTEGER, PRIMARY KEY (lo, hi));
            CREATE TABLE IF NOT EXISTS plan (kind TEXT, block INTEGER, key TEXT, PRIMARY KEY (kind, block, key));
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
        """)
        self.db.commit()

    def put(self, rows: list[tuple]) -> None:
        with self.lock:
            with self.db:
                self.db.executemany("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?)", rows)

    def items(self, kind: str | None = None) -> dict:
        with self.lock:
            q = "SELECT kind, block, key, sha256, source, status, topic FROM items" + (" WHERE kind=?" if kind else "")
            rows = self.db.execute(q, (kind,) if kind else ()).fetchall()
        return {(r[0], r[1], r[2]): dict(zip(("kind", "block", "key", "sha256", "source", "status", "topic"), r))
                for r in rows}

    def page(self, lo: int, hi: int, source: str, n: int) -> None:
        with self.lock:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO pages VALUES (?,?,?,?)", (lo, hi, source, n))

    def pages(self) -> list[tuple[int, int]]:
        with self.lock:
            return [tuple(r) for r in self.db.execute("SELECT lo, hi FROM pages ORDER BY lo, hi")]

    def set_plan(self, keys: list[tuple]) -> None:
        with self.lock:
            with self.db:
                self.db.execute("DELETE FROM plan")
                self.db.executemany("INSERT INTO plan VALUES (?,?,?)", sorted(set(keys)))

    def plan(self) -> list[tuple]:
        with self.lock:
            return [tuple(r) for r in self.db.execute("SELECT kind, block, key FROM plan")]

    def set_meta(self, k: str, v) -> None:
        with self.lock:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, json.dumps(v, sort_keys=True)))

    def get_meta(self, k: str):
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r[0]) if r else None


# ---------------------------------------------------------------- JSON-RPC over the instrument's sources
class Rpc:
    """Batched JSON-RPC over the execution sources in order, each answer (or explicit refusal) per call."""

    def __init__(self, urls: list[str], workers: int = 4, floor: float = 0.06):
        self.urls = urls
        self.http = net.Http(retries=2)
        for u in urls:
            # a short pacer per host: the public archive gateway limits by request cost, not by a long window, so a
            # refused batch is retried after a short pause instead of slowing every later request (net.Pacer's
            # defaults grow the interval to 2 s)
            self.http.pacers[net.host(u)] = net.Pacer(floor, floor, 0.5, pause_on_limit=2.0)
        self.workers = max(1, workers)
        self.refused: set = set()       # (host, method)
        self.done = 0

    def _post(self, url: str, chunk: list[tuple]) -> dict:
        body = json.dumps([{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (_c, m, p) in enumerate(chunk)])
        status, data = self.http.request(url, body.encode(), {"content-type": "application/json"})
        try:
            doc = json.loads(data)
        except ValueError:
            raise net.SourceError(net.scrub(f"{net.host(url)}: HTTP {status}: {data[:200]!r}")) from None
        if isinstance(doc, dict):
            err = doc.get("error") or {"http": status}
            return {c[0]: {"error": err} for c in chunk}
        out = {}
        for r in doc:
            if isinstance(r, dict) and isinstance(r.get("id"), int) and 0 <= r["id"] < len(chunk):
                out[chunk[r["id"]][0]] = r
        return out

    @staticmethod
    def _kind(method: str, r: dict | None) -> str:
        """ok | answer (an execution revert of eth_call) | limit | refused | error | missing."""
        if r is None:
            return "missing"
        if "error" not in r or r["error"] is None:
            return "ok" if r.get("result") is not None else "missing"
        e = r["error"] if isinstance(r["error"], dict) else {"message": str(r["error"])}
        msg = json.dumps(e).lower()
        if "rate limit" in msg or "too many" in msg or "-32005" in msg or "429" in msg:
            return "limit"
        if method == "eth_call" and ("revert" in msg or e.get("code") == 3):
            return "answer"
        if any(w in msg for w in HISTORY_WORDS):
            return "refused"
        return "error"

    def run(self, calls: list[tuple]) -> dict:
        """{cid: (kind "ok" | "answer", result or error object, host)} for (cid, method, params) some source answers.
        Calls are batched per method (BATCH_BY_METHOD: a public gateway refuses a batch over its per-request budget
        as a rate limit); a batch refused as a whole is asked again in the next round, after a short pause."""
        out: dict = {}
        todo = list(calls)
        for url in self.urls:
            h = net.host(url)
            ask = [c for c in todo if (h, c[1]) not in self.refused]
            rounds = 0
            size = {}
            while ask and rounds < 12:
                chunks = []
                for m in sorted({c[1] for c in ask}):
                    xs = [c for c in ask if c[1] == m]
                    n = size.get(m, BATCH_BY_METHOD.get(m, BATCH))
                    chunks += [xs[i:i + n] for i in range(0, len(xs), n)]
                again = []
                with cf.ThreadPoolExecutor(self.workers) as ex:
                    futs = {ex.submit(self._post, url, ch): ch for ch in chunks}
                    for f in cf.as_completed(futs):
                        ch = futs[f]
                        try:
                            res = f.result()
                        except (net.SourceError, net.TransientError):
                            again += ch
                            continue
                        for c in ch:
                            r = res.get(c[0])
                            k = self._kind(c[1], r)
                            if k == "ok":
                                out[c[0]] = ("ok", r["result"], h)
                            elif k == "answer":
                                out[c[0]] = ("answer", r["error"], h)
                            elif k == "limit":
                                again.append(c)
                            elif k == "refused":
                                self.refused.add((h, c[1]))
                ask = [c for c in again if (h, c[1]) not in self.refused]
                rounds += 1
                if ask:
                    time.sleep(min(20.0, 1.0 * rounds))
            todo = [c for c in todo if c[0] not in out]
        return out


def sources(inst: dict) -> list[str]:
    urls = []
    for s in (inst.get("supplement") or {}).get("sources", {}).get("execution") or []:
        if s.startswith("env:"):
            v = os.environ.get(s[4:])
            if v:
                urls.append(v)
        else:
            urls.append(s)
    return urls


# ---------------------------------------------------------------- the acquisition
class Supplement:
    """The supplement's items in memory (values decoded from the snapshot objects) and their fetching."""

    def __init__(self, w: Window, state: State, rpc: Rpc | None):
        self.w, self.state, self.rpc = w, state, rpc
        self.proxy = w.proxy
        self.storage: dict = {}     # block -> {slot int: word int}
        self.answers: dict = {}     # (kind, block, call key) -> answer dict
        self.headers: dict = {}     # block -> header dict
        self.unavailable: dict = {}  # (kind, block, key) -> why
        for (kind, block, key), row in state.items().items():
            if row["status"] != "ok":
                continue
            if kind == "storage":
                o = w.obj(row["sha256"])
                if o["address"] == self.proxy:
                    self.storage.setdefault(block, {})[word(o["slot"])] = word(o["value"])
            elif kind in ("call", "call_after"):
                self.answers[(kind, block, key)] = w.obj(row["sha256"])
            elif kind == "header":
                self.headers[block] = w.obj(row["sha256"])

    def n_storage(self) -> int:
        return sum(len(v) for v in self.storage.values())

    # -------------------------------------------------- fetches (each skips what the state has ok)
    def _have(self, kind: str, block: int, key: str) -> bool:
        return (kind, block, key) in self.state_ok

    @property
    def state_ok(self) -> set:
        if not hasattr(self, "_ok"):
            self._ok = {k for k, r in self.state.items().items() if r["status"] == "ok"}
        return self._ok

    def _store(self, rows: list[tuple]) -> None:
        self.state.put(rows)
        for r in rows:
            if r[5] == "ok":
                self.state_ok.add((r[0], r[1], r[2]))

    def fetch_storage(self, pairs) -> None:
        """eth_getStorageAt(proxy, slot, block) for every (block, slot int) the state lacks (stored per slice)."""
        todo = sorted({(b, s) for b, s in pairs if not self._have("storage", b, S.slot_key(self.proxy, s))})
        for k in range(0, len(todo), SLICE):
            if len(todo) > SLICE:
                log(f"  storage: {k} of {len(todo)}")
            self._fetch_storage(todo[k:k + SLICE])

    def _fetch_storage(self, todo: list) -> None:
        if not todo:
            return
        calls = [(i, "eth_getStorageAt", [self.proxy, "0x%064x" % s, hex(b)]) for i, (b, s) in enumerate(todo)]
        got = self.rpc.run(calls)
        rows = []
        for i, (b, s) in enumerate(todo):
            key = S.slot_key(self.proxy, s)
            r = got.get(i)
            if r is None or r[0] != "ok":
                self.unavailable[("storage", b, key)] = "no source served it"
                rows.append(("storage", b, key, None, net.host(self.rpc.urls[0]), "unavailable", None))
                continue
            v = word(r[1])
            sha = self.w.snap.put(ir.canonical_json({"address": self.proxy, "block": b, "slot": "0x%064x" % s,
                                                     "value": "0x%064x" % v}))
            self.storage.setdefault(b, {})[s] = v
            rows.append(("storage", b, key, sha, r[2], "ok", None))
        self._store(rows)

    def fetch_calls(self, kind: str, todo_calls) -> None:
        """eth_call {from, to, data, value 0} at the item's block for every (block, to, data, from) the state lacks."""
        todo = sorted({c for c in todo_calls if not self._have(kind, c[0], S.call_key(c[1], c[2], c[3]))})
        for k in range(0, len(todo), SLICE):
            if len(todo) > SLICE:
                log(f"  {kind}: {k} of {len(todo)}")
            self._fetch_calls(kind, todo[k:k + SLICE])

    def _fetch_calls(self, kind: str, todo: list) -> None:
        if not todo:
            return
        calls = [(i, "eth_call", [{"from": frm, "to": to, "data": data, "value": "0x0"}, hex(b)])
                 for i, (b, to, data, frm) in enumerate(todo)]
        got = self.rpc.run(calls)
        rows = []
        for i, (b, to, data, frm) in enumerate(todo):
            key = S.call_key(to, data, frm)
            r = got.get(i)
            if r is None:
                self.unavailable[(kind, b, key)] = "no source served it"
                rows.append((kind, b, key, None, net.host(self.rpc.urls[0]), "unavailable", None))
                continue
            if r[0] == "ok":
                ans = {"ok": True, "ret": r[1].lower(), "error": None}
            else:
                e = r[1] if isinstance(r[1], dict) else {}
                d = e.get("data")
                ans = {"ok": False, "ret": d.lower() if isinstance(d, str) and d.startswith("0x") else None,
                       "error": str(e.get("message") or "")[:200]}
            obj = {"block": b, "data": data, "from": frm, "to": to, "value": "0x0", **ans}
            sha = self.w.snap.put(ir.canonical_json(obj))
            self.answers[(kind, b, key)] = obj
            rows.append((kind, b, key, sha, r[2], "ok", None))
        self._store(rows)

    def fetch_headers(self, blocks) -> None:
        todo = sorted({b for b in blocks if not self._have("header", b, str(b))})
        if not todo:
            return
        got = self.rpc.run([(b, "eth_getBlockByNumber", [hex(b), False]) for b in todo])
        rows = []
        for b in todo:
            r = got.get(b)
            if r is None or r[0] != "ok" or not isinstance(r[1], dict):
                self.unavailable[("header", b, str(b))] = "no source served it"
                rows.append(("header", b, str(b), None, net.host(self.rpc.urls[0]), "unavailable", None))
                continue
            data = canon_header(r[1])
            sha = self.w.snap.put(data)
            self.headers[b] = json.loads(data)
            rows.append(("header", b, str(b), sha, r[2], "ok", None))
        self._store(rows)

    def fetch_code(self, address: str, block: int) -> None:
        if self._have("code", block, address):
            return
        got = self.rpc.run([(0, "eth_getCode", [address, hex(block)])])
        r = got.get(0)
        if r is None or r[0] != "ok" or not isinstance(r[1], str) or len(r[1]) <= 2:
            self.unavailable[("code", block, address)] = "no source served it"
            self._store([("code", block, address, None, net.host(self.rpc.urls[0]), "unavailable", None)])
            return
        sha = self.w.snap.put(bytes.fromhex(r[1][2:]))
        self._store([("code", block, address, sha, r[2], "ok", None)])

    def fetch_logs(self) -> list[dict]:
        """Phase 1: every proxy log of the trans window outside I59's five topics (module docstring)."""
        lo, hi = self.w.trans["from_block"], self.w.trans["to_block"]
        size = int(self.w.side["limits"]["get_logs_max_blocks"])
        done = self.state.pages()
        pages = []
        s = lo
        while s <= hi:
            e = min(hi, s + size - 1)
            if not any(a <= s and e <= b for a, b in done):
                pages.append((s, e))
            s = e + 1
        indexed = self.w.index_logs()
        bad = []
        while pages:
            a, b = pages.pop(0)
            got = self.rpc.run([(0, "eth_getLogs", [{"address": self.proxy, "fromBlock": hex(a), "toBlock": hex(b)}])])
            r = got.get(0)
            if r is None or r[0] != "ok" or not isinstance(r[1], list):
                if b > a:
                    m = (a + b) // 2
                    pages[:0] = [(a, m), (m + 1, b)]
                    continue
                raise SystemExit(f"historical fetch-state: no source served the logs of block {a}")
            rows = []
            for lg in r[1]:
                if (lg.get("address") or "").lower() != self.proxy or lg.get("removed"):
                    continue
                blk = int(lg["blockNumber"], 16)
                if not (a <= blk <= b):
                    continue
                tx, li = lg["transactionHash"].lower(), int(lg["logIndex"], 16)
                data = canon_bytes(lg, "log")
                t0 = (lg.get("topics") or ["0x"])[0].lower()
                if t0 in self.w.five:
                    if indexed.get((tx, li)) != hashlib.sha256(data).hexdigest():
                        bad.append(f"{tx}:{li}")
                    continue
                rows.append(("log_other", blk, f"{tx}:{li}", self.w.snap.put(data), r[2], "ok", t0))
            self._store(rows)
            self.state.page(a, b, r[2], len(rows))
        if bad:
            raise SystemExit(f"historical fetch-state: {len(bad)} logs of I59's topics differ from I59's index or are "
                             f"not in it: {bad[:5]}")
        return [r for k, r in self.state.items("log_other").items() if r["status"] == "ok"]

    def fetch_other_txs(self, logs: list[dict]) -> None:
        known = {tx for _b, tx in self.w.index_txs()}
        want = sorted({(r["block"], r["key"].split(":")[0]) for r in logs} - {(b, t) for b, t in self.w.index_txs()})
        want = [(b, t) for b, t in want if t not in known]
        for kind, method in (("tx_other", "eth_getTransactionByHash"), ("receipt_other", "eth_getTransactionReceipt")):
            todo = [(b, t) for b, t in want if not self._have(kind, b, t)]
            got = self.rpc.run([(t, method, [t]) for _b, t in todo]) if todo else {}
            rows = []
            for b, t in todo:
                r = got.get(t)
                if r is None or r[0] != "ok" or not isinstance(r[1], dict):
                    self.unavailable[(kind, b, t)] = "no source served it"
                    rows.append((kind, b, t, None, net.host(self.rpc.urls[0]), "unavailable", None))
                    continue
                sha = self.w.snap.put(canon_bytes(r[1], "tx" if kind == "tx_other" else "receipt"))
                rows.append((kind, b, t, sha, r[2], "ok", None))
            self._store(rows)


# ---------------------------------------------------------------- the in-scope steps
def model_of(w: Window):
    """The adopted transitions document (spec/<M>/lib/derive_extracted.json) and its extracted model."""
    from .. import machine
    from ..sorts import reextract
    sc = reextract.sidecar(w.milestone, w.root) or {}
    docs = []
    for rel in sc.get("documents") or []:
        d = json.loads((w.root / rel).read_text())
        if machine.is_transitions(d):
            docs.append(rel)
    if len(docs) != 1:
        raise ContextError(f"spec/{w.milestone}/lib/derive_extracted.json adopts {len(docs)} transitions documents "
                           "(want 1): the trans replay has no extracted model")
    return docs[0], machine.load_extracted(docs[0], w.root)


def extras_of(state: State) -> list[dict]:
    """{block, tx, tx_sha, rc_sha} of the state's tx_other items with their receipt_other."""
    other = {(r["block"], r["key"]): r["sha256"] for r in state.items("tx_other").values() if r["status"] == "ok"}
    orc = {(r["block"], r["key"]): r["sha256"] for r in state.items("receipt_other").values() if r["status"] == "ok"}
    return [{"block": b, "tx": t, "tx_sha": sha, "rc_sha": orc[(b, t)]} for (b, t), sha in sorted(other.items())
            if (b, t) in orc]


def call_items(step: dict, calls: list[dict], answers: dict, kind: str, block: int, frm: str) -> list[dict]:
    """env "calls" of a step: every call answered by an item of `kind` at `block`."""
    out = []
    for c in calls:
        a = answers.get((kind, block, S.call_key(c["to"], c["data"], frm)))
        if a is not None:
            out.append({"fn": c["fn"], "to": c["to"], "data": c["data"], "args": None, "ok": a["ok"],
                        "ret": a["ret"] if a["ret"] is not None else "0x"})
    return out


class Discovery:
    """Steps 4 to 6 of the module docstring."""

    def __init__(self, sup: Supplement, model, plan: S.Plan, steps: list[dict]):
        self.sup, self.model, self.plan, self.steps = sup, model, plan, steps
        self.proxy = sup.proxy
        self.calls: dict = {}       # tx -> [{fn, to, data}] the step asks for (b - 1 answers)
        self.touch: dict = {}       # tx -> slots (int) the step reads or writes

    def _run(self, s: dict, values: dict) -> tuple[dict, S.Traced | None, set, set]:
        reads, missing = set(), set()
        state = S.SlotState(values, reads, missing)
        known = self.calls.get(s["tx"], [])
        env = S.tx_env(s["tx_obj"], self.proxy, self.sup.headers.get(s["block"]),
                       call_items(s, known, self.sup.answers, "call", s["block"] - 1, self.proxy))
        action = S.action_of(self.model, s["tx_obj"]["input"])
        if action is None:
            return {"status": "unsupported"}, None, reads, missing
        try:
            args = S.decode_args(self.model, action, s["tx_obj"]["input"])
        except Exception:  # noqa: BLE001 - calldata the ABI rejects: the step is unsupported, nothing to fetch
            return {"status": "unsupported"}, None, reads, missing
        res, e = S.traced_step(self.model, state, action, args, env, self.plan)
        return res, e, reads, missing

    def _new_calls(self, s: dict, e: S.Traced | None) -> bool:
        if e is None:
            return False
        have = {(c["fn"], c["to"], c["data"]) for c in self.calls.get(s["tx"], [])}
        new = [c for c in S.asked_calls(self.model, self.plan, e) if (c["fn"], c["to"], c["data"]) not in have]
        if new:
            self.calls.setdefault(s["tx"], []).extend(new)
        return bool(new)

    def on_chain_prestate(self) -> None:
        """Step 4: every step on the chain's storage at b - 1, in passes."""
        pending = list(self.steps)
        for n in range(MAX_DISCOVERY_PASSES):
            need_s, need_c, still = set(), set(), []
            for s in pending:
                b = s["block"] - 1
                res, e, reads, missing = self._run(s, self.sup.storage.get(b, {}))
                grew = self._new_calls(s, e)
                miss = {(b, x) for x in missing if x not in self.sup.storage.get(b, {})}
                unanswered = [c for c in self.calls.get(s["tx"], [])
                              if ("call", b, S.call_key(c["to"], c["data"], self.proxy)) not in self.sup.answers]
                if miss or grew or unanswered:
                    need_s |= miss
                    for c in self.calls.get(s["tx"], []):
                        if ("call", b, S.call_key(c["to"], c["data"], self.proxy)) not in self.sup.answers:
                            need_c.add((b, c["to"], c["data"], self.proxy))
                    still.append(s)
                else:
                    self.touch[s["tx"]] = set(reads) | (set(e.touched) if e is not None else set())
            log(f"discovery pass {n + 1}: {len(pending) - len(still)} steps complete, {len(still)} pending, "
                f"fetching {len(need_s)} slots and {len(need_c)} calls")
            if not still:
                return
            before = (self.sup.n_storage(), len(self.sup.answers))
            self.sup.fetch_storage(need_s)
            self.sup.fetch_calls("call", need_c)
            if (self.sup.n_storage(), len(self.sup.answers)) == before:
                for s in still:   # nothing more can be fetched: what they read so far is still needed
                    _res, e, reads, _m = self._run(s, self.sup.storage.get(s["block"] - 1, {}))
                    self.touch[s["tx"]] = set(reads) | (set(e.touched) if e is not None else set())
                log(f"discovery: {len(still)} steps need values no source serves")
                return
            pending = still

    def bulk(self) -> None:
        """Step 5: b - 1 and b of every touched slot per step, initial and final of every touched slot, call_after."""
        lo, hi = self.sup.w.trans["from_block"], self.sup.w.trans["to_block"]
        pairs, union = set(), set()
        for s in self.steps:
            for slot in self.touch.get(s["tx"], ()):
                pairs |= {(s["block"] - 1, slot), (s["block"], slot)}
                union.add(slot)
        pairs |= {(lo - 1, x) for x in union} | {(hi, x) for x in union}
        self.sup.fetch_storage(pairs)
        after = {(s["block"], c["to"], c["data"], self.proxy) for s in self.steps for c in self.calls.get(s["tx"], [])}
        self.sup.fetch_calls("call_after", after)

    def threaded(self) -> None:
        """Step 6: the replay's own needs, its state threaded from the initial values (holon historical trans)."""
        from .trans import Replay
        for n in range(MAX_DISCOVERY_PASSES):
            r = Replay(self.sup.w, self.model, self.plan, self.steps, self.sup.storage, self.sup.answers,
                       self.sup.headers, self.calls)
            r.run()
            need_s = {(b, x) for b, x in r.need_storage if x not in self.sup.storage.get(b, {})}
            need_c = {c for c in r.need_calls
                      if (c[4], c[0], S.call_key(c[1], c[2], c[3])) not in self.sup.answers}
            for tx, cs in r.asked.items():
                have = {(c["fn"], c["to"], c["data"]) for c in self.calls.get(tx, [])}
                self.calls.setdefault(tx, []).extend(c for c in cs if (c["fn"], c["to"], c["data"]) not in have)
            log(f"completion pass {n + 1}: {len(need_s)} slots and {len(need_c)} calls the threaded replay still needs")
            self.final_touch, self.step_touch, self.thr_asked = r.touched_all, r.step_touch, r.asked
            if not need_s and not need_c:
                return
            before = (self.sup.n_storage(), len(self.sup.answers))
            self.sup.fetch_storage(need_s)
            self.sup.fetch_calls("call", {c[:4] for c in need_c if c[4] == "call"})
            self.sup.fetch_calls("call_after", {c[:4] for c in need_c if c[4] == "call_after"})
            if (self.sup.n_storage(), len(self.sup.answers)) == before:
                log("completion: the replay needs values no source serves (listed as unavailable)")
                return


# ---------------------------------------------------------------- the index
def plan_keys(w: Window, sup: Supplement, disc: Discovery, steps: list[dict], impl: str) -> list[tuple]:
    """(kind, block, key) of every item this run's replay uses (module docstring)."""
    lo, hi = w.trans["from_block"], w.trans["to_block"]
    keys = set()
    keys |= {("header", s["block"], str(s["block"])) for s in steps}
    keys.add(("code", hi, impl))
    keys.add(("storage", hi, S.slot_key(w.proxy, int(w.inst["implementation"]["eip1967_implementation_slot"], 16))))
    for s in steps:
        for slot in disc.step_touch.get(s["tx"], set()):
            keys |= {("storage", s["block"] - 1, S.slot_key(w.proxy, slot)), ("storage", s["block"], S.slot_key(w.proxy, slot))}
        for c in disc.thr_asked.get(s["tx"], []):
            k = S.call_key(c["to"], c["data"], w.proxy)
            keys |= {("call", s["block"] - 1, k), ("call_after", s["block"], k)}
    union = set(disc.final_touch)
    keys |= {("storage", lo - 1, S.slot_key(w.proxy, x)) for x in union}
    keys |= {("storage", hi, S.slot_key(w.proxy, x)) for x in union}
    for kind in ("log_other", "tx_other", "receipt_other"):
        keys |= {(kind, b, k) for (_kd, b, k) in sup.state.items(kind)}
    return sorted(keys)


def build_index(w: Window, state: State, keys: list[tuple]) -> dict:
    rows = state.items()
    items = []
    for kind, block, key in keys:
        r = rows.get((kind, block, key))
        it = {"kind": kind, "block": block, "key": key, "sha256": r["sha256"] if r and r["status"] == "ok" else None,
              "source": r["source"] if r else None, "status": "ok" if r and r["status"] == "ok" else "unavailable"}
        if kind == "log_other":
            it["topic"] = r["topic"] if r else None
        items.append(it)
    items.sort(key=lambda x: (x["block"], x["kind"], x["key"]))
    counts: dict = {}
    for x in items:
        counts[x["kind"]] = counts.get(x["kind"], 0) + 1
    pages = [list(p) for p in state.pages()]
    doc = {"window": w.window("trans"), "snapshot": str(w.snap.dir), "items": items,
           "pages": {"log_other": pages}, "counts": dict(sorted(counts.items()))}
    doc["supplement_sha256"] = hashlib.sha256(ir.canonical_json(doc)).hexdigest()
    return doc


def write(doc: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(ir.canonical_json(doc) + b"\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon historical fetch-state")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--snapshot")
    ap.add_argument("--out")
    ap.add_argument("--offline", action="store_true", help="write the index from the snapshot state, no network")
    ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args(argv)
    try:
        w = Window(a.milestone, ROOT, a.snapshot)
    except (ContextError, S.StepperError) as e:
        print(f"historical fetch-state: {e}", file=sys.stderr)
        return 2
    state = State(w.snap.dir)
    out = Path(a.out) if a.out else default_out(a.milestone)
    if a.offline:
        keys = state.plan()
        if not keys:
            print("historical fetch-state --offline: the snapshot state holds no plan (run fetch-state online first)",
                  file=sys.stderr)
            return 2
        doc = build_index(w, state, keys)
        write(doc, out)
        bad = sum(1 for x in doc["items"] if x["status"] != "ok")
        log(f"wrote {out} (offline): counts {doc['counts']}, unavailable {bad}")
        return 1 if bad else 0
    urls = sources(w.inst)
    if not urls:
        print("historical fetch-state: no execution source (the instrument's supplement.sources)", file=sys.stderr)
        return 2
    rpc = Rpc(urls, a.workers)
    sup = Supplement(w, state, rpc)
    log(f"historical fetch-state: trans window [{w.trans['from_block']}, {w.trans['to_block']}], snapshot {w.snap.dir}, "
        f"sources {[net.host(u) for u in urls]}")
    logs = sup.fetch_logs()
    log(f"log_other: {len(logs)} logs outside I59's five topics")
    sup.fetch_other_txs(logs)
    from .trans import steps_of
    steps = steps_of(w, extras_of(state))
    log(f"steps: {len(steps)} in-scope transactions ({sum(1 for s in steps if s['extra'])} from log_other)")
    sup.fetch_headers({s["block"] for s in steps})
    for s in steps:
        h = sup.headers.get(s["block"])
        if h is not None and h["hash"] != s["tx_obj"]["blockHash"].lower():
            print(f"historical fetch-state: block {s['block']}: header hash {h['hash']} is not the transaction's "
                  f"block hash {s['tx_obj']['blockHash']}", file=sys.stderr)
            return 2
    impl = w.inst["implementation"]["last_upgrade"]["implementation"].lower()
    sup.fetch_code(impl, w.trans["to_block"])
    sup.fetch_storage({(w.trans["to_block"], int(w.inst["implementation"]["eip1967_implementation_slot"], 16))})
    doc_rel, model = model_of(w)
    plan = S.Plan(model, doc_rel)
    disc = Discovery(sup, model, plan, steps)
    disc.on_chain_prestate()
    disc.bulk()
    disc.threaded()
    keys = plan_keys(w, sup, disc, steps, impl)
    state.set_plan(keys)
    doc = build_index(w, state, keys)
    write(doc, out)
    bad = [x for x in doc["items"] if x["status"] != "ok"]
    log(f"wrote {out}: counts {doc['counts']}, unavailable {len(bad)}, calls {dict(sorted(rpc.http.calls.items()))}")
    for x in bad[:20]:
        log(f"  unavailable: {x['kind']} {x['block']} {x['key']}")
    return 1 if bad else 0
