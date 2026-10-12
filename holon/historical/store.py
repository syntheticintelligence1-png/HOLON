"""The content-addressed snapshot outside the repo, and the resumable fetch state.

Layout of a snapshot directory (default ~/.holon/historical, env HOLON_HISTORICAL_DIR, flag --snapshot):

    objects/<aa>/<sha256>        an item's raw bytes (logs, transactions, receipts: canonical JSON, below)
    objects/<aa>/<sha256>.gz     a blob's raw 131072 bytes, gzip-compressed on disk (blobs are mostly zero
                                 padding); the name is the sha256 of the raw, uncompressed bytes
    state.sqlite                 what has been fetched: log pages, items (sha256, source host, status)

An object is written once, under the sha256 of its raw bytes, and read back only through `read`, which checks
that sha256 again. The state records the host an item came from, so a resumed run reproduces the index of
the run that fetched it. Nothing in the snapshot is ever inside the repository (`resolve_snapshot` refuses).

Canonical item bytes. JSON-RPC objects differ between providers in fields that are not chain data (extra
keys, key order, `yParity`, ...). An item stores the canonical JSON (holon.ir.canonical_json) of a fixed set of
fields, lowercase hex, so the bytes and their sha256 are a function of the chain alone:
    log      address, blockHash, blockNumber, data, logIndex, topics, transactionHash, transactionIndex
    tx       blobVersionedHashes, blockHash, blockNumber, from, gas, hash, input, nonce, to,
             transactionIndex, type, value
    receipt  blockHash, blockNumber, contractAddress, from, gasUsed, logs (each as a log), status, to,
             transactionHash, transactionIndex, type
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path

from .. import ir

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = "~/.holon/historical"

LOG_FIELDS = ("address", "blockHash", "blockNumber", "data", "logIndex", "topics", "transactionHash", "transactionIndex")
TX_FIELDS = ("blobVersionedHashes", "blockHash", "blockNumber", "from", "gas", "hash", "input", "nonce", "to",
             "transactionIndex", "type", "value")
RECEIPT_FIELDS = ("blockHash", "blockNumber", "contractAddress", "from", "gasUsed", "logs", "status", "to",
                  "transactionHash", "transactionIndex", "type")


class StoreError(RuntimeError):
    pass


def resolve_snapshot(arg: str | None) -> Path:
    d = Path(os.path.expanduser(arg or os.environ.get("HOLON_HISTORICAL_DIR") or DEFAULT_DIR)).resolve()
    root = ROOT.resolve()
    if d == root or str(d).startswith(str(root) + os.sep):
        raise StoreError(f"the snapshot must be outside the repository: {d}")
    return d


def _hex(v):
    if isinstance(v, str):
        return v.lower()
    if isinstance(v, list):
        return [_hex(x) for x in v]
    return v


def _qty(v):
    """A JSON-RPC quantity in its canonical form: 0x without leading zeros (some providers pad)."""
    if v is None:
        return None
    return hex(int(v, 16)) if isinstance(v, str) else v


QTY = {"blockNumber", "logIndex", "transactionIndex", "gas", "nonce", "type", "value", "status", "gasUsed"}


def canon_obj(obj: dict, fields: tuple[str, ...]) -> dict:
    out = {}
    for k in fields:
        v = obj.get(k)
        if k == "logs":
            v = [canon_obj(x, LOG_FIELDS) for x in (v or [])]
        elif k in QTY:
            v = _qty(v)
        else:
            v = _hex(v)
        if k == "blobVersionedHashes" and v is None:
            v = []
        out[k] = v
    return out


def canon_bytes(obj: dict, kind: str) -> bytes:
    fields = {"log": LOG_FIELDS, "tx": TX_FIELDS, "receipt": RECEIPT_FIELDS}[kind]
    return ir.canonical_json(canon_obj(obj, fields))


class Snapshot:
    def __init__(self, directory: Path):
        self.dir = Path(directory)
        (self.dir / "objects").mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.dir / "state.sqlite"), timeout=120, check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS pages (lo INTEGER, hi INTEGER, source TEXT, n INTEGER, PRIMARY KEY (lo, hi));
            CREATE TABLE IF NOT EXISTS logs (tx TEXT, log_index INTEGER, block INTEGER, topic TEXT, sha256 TEXT,
                                             source TEXT, PRIMARY KEY (tx, log_index));
            CREATE INDEX IF NOT EXISTS logs_block ON logs (block);
            CREATE TABLE IF NOT EXISTS items (kind TEXT, key TEXT, block INTEGER, tx TEXT, sha256 TEXT, source TEXT,
                                              status TEXT, extra TEXT, PRIMARY KEY (kind, key));
            CREATE INDEX IF NOT EXISTS items_tx ON items (tx);
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
        """)
        self.db.commit()

    # ---------------------------------------------------------------- objects
    def path(self, sha: str, gz: bool = False) -> Path:
        return self.dir / "objects" / sha[:2] / (sha + (".gz" if gz else ""))

    def has(self, sha: str) -> bool:
        return self.path(sha).exists() or self.path(sha, True).exists()

    def put(self, data: bytes, gz: bool = False) -> str:
        sha = hashlib.sha256(data).hexdigest()
        p = self.path(sha, gz)
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_name(p.name + f".tmp{os.getpid()}.{threading.get_ident()}")
            tmp.write_bytes(gzip.compress(data, 6, mtime=0) if gz else data)
            os.replace(tmp, p)
        return sha

    def read(self, sha: str) -> bytes:
        p = self.path(sha)
        if p.exists():
            data = p.read_bytes()
        elif self.path(sha, True).exists():
            data = gzip.decompress(self.path(sha, True).read_bytes())
        else:
            raise StoreError(f"object {sha} is not in the snapshot {self.dir}")
        if hashlib.sha256(data).hexdigest() != sha:
            raise StoreError(f"object {sha} in {self.dir} does not hash to its name")
        return data

    def read_json(self, sha: str):
        return json.loads(self.read(sha))

    # ---------------------------------------------------------------- state
    def page_done(self, lo: int, hi: int, source: str, logs: list[dict]) -> None:
        """Record one eth_getLogs page and its logs atomically (a page is done only with all its logs)."""
        with self.lock:
            with self.db:
                for lg in logs:
                    self.db.execute("INSERT OR REPLACE INTO logs VALUES (?,?,?,?,?,?)",
                                    (lg["tx"], lg["log_index"], lg["block"], lg["topic"], lg["sha256"], source))
                self.db.execute("INSERT OR REPLACE INTO pages VALUES (?,?,?,?)", (lo, hi, source, len(logs)))

    def pages(self) -> list[tuple[int, int]]:
        with self.lock:
            return [tuple(r) for r in self.db.execute("SELECT lo, hi FROM pages ORDER BY lo, hi")]

    def covered(self, lo: int, hi: int) -> list[tuple[int, int]]:
        """The sub-ranges of [lo, hi] that no done page covers."""
        gaps, cur = [], lo
        for a, b in self.pages():
            if b < cur or a > hi:
                continue
            if a > cur:
                gaps.append((cur, min(hi, a - 1)))
            cur = max(cur, b + 1)
            if cur > hi:
                break
        if cur <= hi:
            gaps.append((cur, hi))
        return gaps

    def logs(self, lo: int, hi: int) -> list[dict]:
        with self.lock:
            rows = self.db.execute("SELECT tx, log_index, block, topic, sha256, source FROM logs WHERE block BETWEEN ? AND ? "
                                   "ORDER BY block, tx, log_index", (lo, hi))
            return [dict(zip(("tx", "log_index", "block", "topic", "sha256", "source"), r)) for r in rows]

    def put_item(self, kind: str, key: str, block: int, tx: str, sha: str | None, source: str, status: str,
                 extra: dict | None = None) -> None:
        with self.lock:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?)",
                                (kind, key, block, tx, sha, source, status, json.dumps(extra or {}, sort_keys=True)))

    def item(self, kind: str, key: str) -> dict | None:
        with self.lock:
            r = self.db.execute("SELECT kind, key, block, tx, sha256, source, status, extra FROM items WHERE kind=? AND key=?",
                                (kind, key)).fetchone()
            if r is None:
                return None
            d = dict(zip(("kind", "key", "block", "tx", "sha256", "source", "status", "extra"), r))
            d["extra"] = json.loads(d["extra"] or "{}")
            return d

    def items(self, kind: str) -> dict[str, dict]:
        with self.lock:
            out = {}
            for r in self.db.execute("SELECT kind, key, block, tx, sha256, source, status, extra FROM items WHERE kind=?", (kind,)):
                d = dict(zip(("kind", "key", "block", "tx", "sha256", "source", "status", "extra"), r))
                d["extra"] = json.loads(d["extra"] or "{}")
                out[d["key"]] = d
            return out

    def get_meta(self, k: str):
        with self.lock:
            r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
            return json.loads(r[0]) if r else None

    def set_meta(self, k: str, v) -> None:
        with self.lock:
            with self.db:
                self.db.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (k, json.dumps(v, sort_keys=True)))

    def ok(self, kind: str, key: str) -> bool:
        """An item is done when the state says ok and its object is in the snapshot (resumability)."""
        it = self.item(kind, key)
        return bool(it and it["status"] == "ok" and it["sha256"] and self.has(it["sha256"]))

    def close(self) -> None:
        self.db.close()
