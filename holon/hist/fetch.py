"""`holon.hist.fetch` (M2 unit S5): build the historical commit corpus for the
Morph mainnet L1 Rollup proxy (whitepaper §8.7 input source 4, M2_SPEC §1 and §4).

    python -m holon.hist.fetch --snapshot-block N
    python -m holon.hist.fetch --latest            # snapshot = current head

What it does, for every `CommitBatch` event of the Rollup proxy inside the
14-day window ending at the snapshot block:

  1. enumerates the events via `eth_getLogs` (chunked, range auto-shrinks);
  2. fetches each transaction (calldata, `blobVersionedHashes`) and receipt;
  3. fetches each blob sidecar from the beacon API (falls back to blobscan);
  4. reads the post-state at the commit block: `committedBatches(i)`,
     `committedStateRoots(i)` and `lastCommittedBatchIndex` via `eth_call`;
  5. stores every raw artifact under `$HOLON_CACHE` (default
     `~/.holon/cache/m2`), content-addressed by sha256;
  6. writes `replay/M2/corpus/manifest.json` in the exact §4 format and up to
     5 full-commit fixtures under `replay/M2/corpus/fixtures/`.

Determinism: given the same snapshot block, the manifest is byte-identical —
all data is historical and final, output ordering is fixed, and no timestamps
are emitted. The proxy address comes from the morph checkout
(`node/types/networks.go`, `MainnetRollupContractAddress`) and is confirmed
on-chain before fetching (code present + EIP-1967 implementation slot).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Constants (target: morph-l2/morph @ 3e44e795586af3e11285b603ab642c67823add51)
# ---------------------------------------------------------------------------

# node/types/networks.go:11 — MainnetRollupContractAddress.
ROLLUP_PROXY = "0x759894Ced0e6af42c26668076Ffa84d02E3CeF60"
# Free archive-capable L1 endpoints (2026-10: ethereum-rpc.publicnode.com
# gates archive queries behind a personal token; nodies/blastapi/drpc still
# serve eth_call/eth_getStorageAt at old blocks). getLogs range caps differ
# per provider, so the scanner parses the provider's own range hint.
DEFAULT_L1_RPC = ("https://eth-pokt.nodies.app,"
                  "https://eth-mainnet.public.blastapi.io,"
                  "https://eth.drpc.org")
DEFAULT_BEACON = "https://ethereum-beacon-api.publicnode.com"
DEFAULT_BLOBSCAN = "https://api.blobscan.com"

BEACON_GENESIS_TS = 1606824023  # Ethereum beacon-chain genesis (slot 0).
SECONDS_PER_SLOT = 12
DEFAULT_WINDOW_DAYS = 14
MIN_COMMITS = 200
MAX_FIXTURES = 5

# EIP-1967 implementation slot (keccak256("eip1967.proxy.implementation") - 1).
EIP1967_IMPL_SLOT = (
    "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
)

USER_AGENT = "holon-hist-fetch/0.1 (github.com/syntheticintelligence1-png/HOLON)"

# ---------------------------------------------------------------------------
# Keccak-256 (Ethereum flavor: pad10*1 domain byte 0x01). Stdlib sha3_256 is
# NIST SHA-3 (0x06), so the checksum is implemented here.
# ---------------------------------------------------------------------------

_RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
_ROT = [
    [0, 36, 3, 41, 18],
    [1, 44, 10, 45, 2],
    [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56],
    [27, 20, 39, 8, 14],
]
_M64 = (1 << 64) - 1


def _rol(x: int, n: int) -> int:
    return ((x << n) | (x >> (64 - n))) & _M64 if n else x


def _keccak_f(s: list[int]) -> None:
    for rc in _RC:
        c = [s[x] ^ s[x + 5] ^ s[x + 10] ^ s[x + 15] ^ s[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                s[x + 5 * y] ^= d[x]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol(s[x + 5 * y], _ROT[x][y])
        for x in range(5):
            for y in range(5):
                s[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y])
        s[0] ^= rc


def keccak256(data: bytes) -> bytes:
    rate = 136
    s = [0] * 25
    d = bytearray(data)
    d.append(0x01)
    while len(d) % rate:
        d.append(0)
    d[-1] |= 0x80
    for off in range(0, len(d), rate):
        blk = d[off:off + rate]
        for i in range(rate // 8):
            s[i] ^= int.from_bytes(blk[8 * i:8 * i + 8], "little")
        _keccak_f(s)
    out = b""
    for i in range(rate // 8):
        out += s[i].to_bytes(8, "little")
        if len(out) >= 32:
            break
    return out[:32]


def _sig(sig: str) -> bytes:
    return keccak256(sig.encode())


_BATCHDATA_INPUT = "(uint8,bytes,uint64,uint16,bytes32,bytes32,bytes32)"

# Method selector -> manifest `method` name (IRollup.sol / Rollup.sol ABI).
SELECTOR_METHODS = {
    _sig(f"commitBatch({_BATCHDATA_INPUT})")[:4].hex(): "commitBatch",
    _sig(f"commitState({_BATCHDATA_INPUT})")[:4].hex(): "commitState",
    _sig(f"commitBatchWithProof({_BATCHDATA_INPUT},bytes,bytes)")[:4].hex(): "commitBatchWithProof",
    _sig(f"importGenesisBatch({_BATCHDATA_INPUT},bytes32)")[:4].hex(): "importGenesisBatch",
}

COMMIT_BATCH_TOPIC = "0x" + _sig("CommitBatch(uint256,bytes32)").hex()
_SEL_COMMITTED_BATCHES = _sig("committedBatches(uint256)")[:4].hex()
_SEL_COMMITTED_STATE_ROOTS = _sig("committedStateRoots(uint256)")[:4].hex()
_SEL_LAST_COMMITTED = _sig("lastCommittedBatchIndex()")[:4].hex()


# ---------------------------------------------------------------------------
# HTTP / JSON-RPC client with polite pacing and retries. Every network call in
# this module goes through it, so tests can substitute a scripted client.
# ---------------------------------------------------------------------------

class FetchError(Exception):
    pass


class Client:
    def __init__(self, qps: float = 4.0, max_attempts: int = 14, log=sys.stderr):
        self.min_interval = 1.0 / qps if qps > 0 else 0.0
        self.max_attempts = max_attempts
        self._last_at = 0.0
        self.log = log

    def _pace(self) -> None:
        now = time.monotonic()
        wait = self.min_interval - (now - self._last_at)
        if wait > 0:
            time.sleep(wait)
        self._last_at = time.monotonic()

    def http_get(self, url: str) -> bytes:
        """GET raw bytes (blob payloads, IPFS references)."""
        for attempt in range(self.max_attempts):
            self._pace()
            req = urllib.request.Request(url, headers={"user-agent": USER_AGENT})
            try:
                return urllib.request.urlopen(req, timeout=60).read()
            except urllib.error.HTTPError as e:
                if e.code in (403, 404, 410) and attempt >= self.max_attempts - 1:
                    raise FetchError(f"GET {url} -> HTTP {e.code}")
                self._backoff(attempt, e.headers.get("Retry-After"))
            except Exception as e:
                if attempt >= self.max_attempts - 1:
                    raise FetchError(f"GET {url} -> {e}")
                self._backoff(attempt, None)
        raise FetchError(f"GET {url} failed")

    def http_json(self, url: str, body: dict | None = None) -> dict:
        """POST JSON (or GET when body is None) and decode a JSON object."""
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(self.max_attempts):
            self._pace()
            req = urllib.request.Request(
                url,
                data=data,
                headers={"user-agent": USER_AGENT, "content-type": "application/json",
                         "accept": "application/json"},
            )
            try:
                raw = urllib.request.urlopen(req, timeout=60).read()
                out = json.loads(raw)
                if not isinstance(out, dict):
                    raise FetchError(f"{url} -> non-object response")
                return out
            except FetchError:
                raise
            except urllib.error.HTTPError as e:
                if attempt >= self.max_attempts - 1:
                    raise FetchError(f"{url} -> HTTP {e.code}")
                self._backoff(attempt, e.headers.get("Retry-After"))
            except Exception as e:
                if attempt >= self.max_attempts - 1:
                    raise FetchError(f"{url} -> {e}")
                self._backoff(attempt, None)
        raise FetchError(f"{url} failed")

    def rpc(self, rpc_urls, method: str, params: list) -> object:
        """JSON-RPC call; treats errors/null results as retryable (the endpoint
        is a pool of heterogeneous backends: some prune, some lag, some 403).
        `rpc_urls` is a URL or list of URLs: consecutive attempts rotate over
        the list, so one endpoint's rate limit fails over to another's."""
        urls = [rpc_urls] if isinstance(rpc_urls, str) else list(rpc_urls)
        last = "unknown error"
        for attempt in range(self.max_attempts):
            url = urls[attempt % len(urls)]
            self._pace()
            req = urllib.request.Request(
                url,
                data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                 "params": params}).encode(),
                headers={"user-agent": USER_AGENT, "content-type": "application/json"},
            )
            try:
                out = json.loads(urllib.request.urlopen(req, timeout=60).read())
                if not isinstance(out, dict):
                    last = f"non-object response: {str(out)[:80]}"
                elif out.get("error") is not None:
                    last = f"rpc error: {out['error']}"
                elif out.get("result") is None:
                    last = "null result"
                else:
                    return out["result"]
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                self._backoff(attempt, e.headers.get("Retry-After"))
                continue
            except Exception as e:
                last = str(e)
            self._backoff(attempt, None)
        raise FetchError(f"{method} failed after {self.max_attempts} attempts: {last}")

    def rpc_batch(self, rpc_urls, calls: list) -> list:
        """One HTTP request carrying several JSON-RPC calls (same retry /
        rotation rules as rpc()). `calls` is a list of (method, params);
        returns the results list in call order. Any item that errors or is
        null retries the whole batch — the per-commit batches are tiny."""
        urls = [rpc_urls] if isinstance(rpc_urls, str) else list(rpc_urls)
        payload = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p}
                   for i, (m, p) in enumerate(calls)]
        last = "unknown error"
        for attempt in range(self.max_attempts):
            url = urls[attempt % len(urls)]
            self._pace()
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode(),
                headers={"user-agent": USER_AGENT, "content-type": "application/json"},
            )
            try:
                out = json.loads(urllib.request.urlopen(req, timeout=60).read())
                if not isinstance(out, list) or len(out) != len(calls):
                    last = f"non-batch response: {str(out)[:80]}"
                else:
                    by_id = {item.get("id"): item for item in out}
                    ordered = [by_id.get(i, {}) for i in range(len(calls))]
                    bad_item = next((item for item in ordered
                                     if item.get("error") is not None or
                                     item.get("result") is None), None)
                    if bad_item is not None:
                        last = ("batch item error: "
                                f"{bad_item.get('error') or 'null/missing result'}")
                    else:
                        return [item["result"] for item in ordered]
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                self._backoff(attempt, e.headers.get("Retry-After"))
                continue
            except Exception as e:
                last = str(e)
            self._backoff(attempt, None)
        raise FetchError(f"batch failed after {self.max_attempts} attempts: {last}")

    def _backoff(self, attempt: int, retry_after: str | None) -> None:
        delay = min(0.5 * (1.6 ** attempt), 30.0)
        if retry_after:
            try:
                delay = max(delay, float(retry_after))
            except ValueError:
                pass
        print(f"  retry {attempt + 1} in {delay:.1f}s", file=self.log)
        time.sleep(delay)


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without network)
# ---------------------------------------------------------------------------

def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hex_to_bytes(value: str) -> bytes:
    v = value[2:] if value.startswith("0x") else value
    return bytes.fromhex(v)


def slot_for_timestamp(ts: int) -> int:
    return (ts - BEACON_GENESIS_TS) // SECONDS_PER_SLOT


def versioned_hash_for_commitment(kzg_commitment: bytes) -> str:
    """EIP-4844: versioned hash = 0x01 || sha256(kzg_commitment)[1:]."""
    h = hashlib.sha256(kzg_commitment).digest()
    return "0x" + (b"\x01" + h[1:]).hex()


def method_for_calldata(calldata: bytes) -> str:
    sel = calldata[:4].hex()
    return SELECTOR_METHODS.get(sel, f"unknown:0x{sel}")


def parse_commit_event(log: dict) -> dict:
    """One CommitBatch log -> (batch_index, tx, block, tx_index)."""
    return {
        "batch_index": int(log["topics"][1], 16),
        "tx": log["transactionHash"],
        "block": int(log["blockNumber"], 16),
        "tx_index": int(log["transactionIndex"], 16),
    }


def decode_uint256(ret_hex: str) -> int:
    return int(ret_hex, 16)


def encode_call_uint256(selector_hex: str, index: int) -> str:
    return "0x" + selector_hex + index.to_bytes(32, "big").hex()


# ---------------------------------------------------------------------------
# Content-addressed cache ($HOLON_CACHE, default ~/.holon/cache/m2)
# ---------------------------------------------------------------------------

class Cache:
    """Raw artifacts live under `objects/<sha256>`; small derived indexes under
    `index/` map tx/slot keys to those object hashes (recomputed, never
    authoritative)."""

    def __init__(self, root: Path):
        self.root = root
        self.objects = root / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        (root / "index").mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes) -> str:
        digest = sha256_hex(data)
        path = self.objects / digest
        if not path.exists():
            tmp = self.objects / (digest + ".tmp")
            tmp.write_bytes(data)
            tmp.replace(path)
        return digest

    def get(self, digest: str) -> bytes | None:
        path = self.objects / digest
        return path.read_bytes() if path.exists() else None

    def index_put(self, group: str, key: str, value: dict) -> None:
        d = self.root / "index" / group
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{key}.json").write_text(json.dumps(value, sort_keys=True))

    def index_get(self, group: str, key: str) -> dict | None:
        path = self.root / "index" / group / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text())
        return None


def default_cache_dir() -> Path:
    return Path(os.environ.get("HOLON_CACHE", "~/.holon/cache/m2")).expanduser()


# ---------------------------------------------------------------------------
# Fetch pipeline
# ---------------------------------------------------------------------------

def resolve_window(client: Client, rpc_url: str, snapshot_block: int,
                   window_days: int) -> dict:
    """from_block = first block whose timestamp >= to_block.ts - window_days."""
    to_blk = client.rpc(rpc_url, "eth_getBlockByNumber", [hex(snapshot_block), False])
    to_ts = int(to_blk["timestamp"], 16)
    target = to_ts - window_days * 86400
    # 14 days is ~100k blocks; bound the search so it never wanders into
    # history the public endpoint may prune.
    lo, hi = max(0, snapshot_block - 300000), snapshot_block
    while lo < hi:
        mid = (lo + hi) // 2
        m = client.rpc(rpc_url, "eth_getBlockByNumber", [hex(mid), False])
        if int(m["timestamp"], 16) < target:
            lo = mid + 1
        else:
            hi = mid
    return {"from_block": lo, "to_block": snapshot_block}


def verify_proxy(client: Client, rpc_url: str, proxy: str, block: int) -> str:
    """Confirm the address is the live Rollup proxy at `block`."""
    tag = hex(block)
    code = client.rpc(rpc_url, "eth_getCode", [proxy, tag])
    if len(code) <= 2:
        raise FetchError(f"no code at {proxy} (block {block})")
    impl = client.rpc(rpc_url, "eth_getStorageAt", [proxy, EIP1967_IMPL_SLOT, tag])
    impl_addr = int(impl, 16)
    if impl_addr == 0:
        raise FetchError(f"{proxy} has no EIP-1967 implementation at {block}")
    lci = client.rpc(rpc_url, "eth_call",
                     [{"to": proxy, "data": "0x" + _SEL_LAST_COMMITTED}, tag])
    return "0x" + impl_addr.to_bytes(20, "big").hex(), int(lci, 16)


def fetch_commit_events(client: Client, rpc_url: str, proxy: str,
                        window: dict, events: list[dict] | None = None,
                        start_at: int | None = None,
                        checkpoint=None) -> list[dict]:
    """eth_getLogs for the CommitBatch topic, chunked; the chunk halves itself
    whenever the endpoint rejects a range (403 / range errors / timeouts).
    Resumable: `start_at` skips already-scanned blocks, `checkpoint` is called
    with (events_so_far, next_block) after every accepted chunk."""
    if events is None:
        events = []
    start, end = window["from_block"], window["to_block"]
    span = 400
    b = max(start, start_at or start)
    while b <= end:
        e = min(b + span - 1, end)
        try:
            logs = client.rpc(rpc_url, "eth_getLogs", [{
                "address": proxy,
                "fromBlock": hex(b),
                "toBlock": hex(e),
                "topics": [COMMIT_BATCH_TOPIC],
            }])
            events.extend(parse_commit_event(l) for l in logs)
            print(f"  logs {b}-{e}: +{len(logs)} (total {len(events)})", file=client.log)
            b = e + 1
            if checkpoint:
                checkpoint(events, b)
        except FetchError as err:
            if span <= 8:
                raise
            # Providers report their own cap ("maximum allowed is 50 blocks",
            # "up to a 10 block range"); honor it directly instead of halving.
            m = re.search(r"(?:maximum allowed is|up to a)\D{0,20}(\d+)",
                          str(err))
            hint = int(m.group(1)) if m else None
            if hint and hint < span:
                span = max(1, hint)
            else:
                span = max(8, span // 2)
            print(f"  logs {b}-{e} rejected; shrinking chunk to {span}", file=client.log)
    events.sort(key=lambda ev: (ev["batch_index"], ev["block"], ev["tx_index"]))
    return events


def _block_timestamp(client: Client, rpc_url: str, block: int, ts_cache: dict) -> int:
    if block not in ts_cache:
        blk = client.rpc(rpc_url, "eth_getBlockByNumber", [hex(block), False])
        ts_cache[block] = int(blk["timestamp"], 16)
    return ts_cache[block]


def fetch_blobs_beacon(client: Client, beacon_url: str, slot: int,
                       wanted: list[str], cache: Cache) -> list[bytes] | None:
    """Blob bytes for `wanted` versioned hashes in beacon slot. None if any is
    missing (caller falls back to blobscan)."""
    index = cache.index_get("slots", str(slot))
    if index and all(v in index for v in wanted):
        return [cache.get(index[v]) for v in wanted]
    out = client.http_json(f"{beacon_url}/eth/v1/beacon/blob_sidecars/{slot}")
    sidecars = out.get("data")
    if not isinstance(sidecars, list):
        return None
    by_vh: dict[str, bytes] = {}
    for sc in sidecars:
        vh = versioned_hash_for_commitment(hex_to_bytes(sc["kzg_commitment"]))
        by_vh[vh] = hex_to_bytes(sc["blob"])
    if not all(v in by_vh for v in wanted):
        return None
    new_index: dict[str, str] = dict(index or {})
    for vh, data in by_vh.items():
        new_index[vh] = cache.put(data)
    cache.index_put("slots", str(slot), new_index)
    return [by_vh[v] for v in wanted]


def fetch_blobs_blobscan(client: Client, blobscan_url: str, tx_hash: str,
                         wanted: list[str], cache: Cache) -> list[bytes]:
    """Fallback: blobscan transaction -> dataStorageReferences -> raw bytes."""
    out = client.http_json(f"{blobscan_url}/transactions/{tx_hash}")
    blobs = out.get("blobs") or []
    by_vh: dict[str, bytes] = {}
    for blob in blobs:
        vh = blob.get("versionedHash")
        for ref in blob.get("dataStorageReferences") or []:
            url = ref.get("url")
            if not url:
                continue
            try:
                by_vh[vh] = client.http_get(url)
                break
            except FetchError:
                continue
    missing = [v for v in wanted if v not in by_vh]
    if missing:
        raise FetchError(f"blobscan has no data for {missing} (tx {tx_hash})")
    return [by_vh[v] for v in wanted]


def fetch_blobs(client: Client, beacon_url: str, blobscan_url: str,
                block_ts: int, tx_hash: str, wanted: list[str],
                cache: Cache) -> list[bytes]:
    slot = slot_for_timestamp(block_ts)
    try:
        blobs = fetch_blobs_beacon(client, beacon_url, slot, wanted, cache)
    except FetchError:
        blobs = None
    if blobs is not None:
        return blobs
    print(f"  beacon slot {slot} incomplete for {tx_hash}; trying blobscan",
          file=client.log)
    return fetch_blobs_blobscan(client, blobscan_url, tx_hash, wanted, cache)


def fetch_post_state(client: Client, rpc_url: str, proxy: str,
                     batch_index: int, block: int) -> dict:
    tag = hex(block)
    cb = client.rpc(rpc_url, "eth_call", [{
        "to": proxy,
        "data": encode_call_uint256(_SEL_COMMITTED_BATCHES, batch_index)}, tag])
    csr = client.rpc(rpc_url, "eth_call", [{
        "to": proxy,
        "data": encode_call_uint256(_SEL_COMMITTED_STATE_ROOTS, batch_index)}, tag])
    lci = client.rpc(rpc_url, "eth_call", [{
        "to": proxy, "data": "0x" + _SEL_LAST_COMMITTED}, tag])
    return {
        "committedBatches": "0x" + cb[2:].rjust(64, "0"),
        "committedStateRoots": "0x" + csr[2:].rjust(64, "0"),
        "lastCommittedBatchIndex": decode_uint256(lci),
    }


def fetch_commit(client: Client, rpc_url: str, beacon_url: str,
                 blobscan_url: str, proxy: str, event: dict,
                 ts_cache: dict, cache: Cache) -> dict:
    tag = hex(event["block"])
    # One HTTP request for the five L1 reads the entry needs; free endpoints
    # meter per request, so batching cuts the rate-limit surface ~5x. Falls
    # back to serial calls if the endpoint rejects JSON-RPC batches.
    calls = [
        ("eth_getTransactionByHash", [event["tx"]]),
        ("eth_getTransactionReceipt", [event["tx"]]),
        ("eth_call", [{"to": proxy,
                       "data": encode_call_uint256(_SEL_COMMITTED_BATCHES,
                                                   event["batch_index"])}, tag]),
        ("eth_call", [{"to": proxy,
                       "data": encode_call_uint256(_SEL_COMMITTED_STATE_ROOTS,
                                                   event["batch_index"])}, tag]),
        ("eth_call", [{"to": proxy, "data": "0x" + _SEL_LAST_COMMITTED}, tag]),
    ]
    try:
        tx, receipt, cb, csr, lci = client.rpc_batch(rpc_url, calls)
        post = {
            "committedBatches": "0x" + cb[2:].rjust(64, "0"),
            "committedStateRoots": "0x" + csr[2:].rjust(64, "0"),
            "lastCommittedBatchIndex": decode_uint256(lci),
        }
    except FetchError:
        tx = client.rpc(rpc_url, "eth_getTransactionByHash", [event["tx"]])
        receipt = client.rpc(rpc_url, "eth_getTransactionReceipt", [event["tx"]])
        post = fetch_post_state(client, rpc_url, proxy, event["batch_index"],
                                event["block"])

    calldata = hex_to_bytes(tx["input"])
    calldata_sha = cache.put(calldata)
    receipt_sha = cache.put(canonical_json(receipt))
    cache.index_put("tx", event["tx"], {
        "calldata": calldata_sha,
        "receipt": receipt_sha,
    })

    vhashes = list(tx.get("blobVersionedHashes") or [])
    blobs_sha: list[str] = []
    if vhashes:
        ts = _block_timestamp(client, rpc_url, event["block"], ts_cache)
        blobs = fetch_blobs(client, beacon_url, blobscan_url, ts,
                            event["tx"], vhashes, cache)
        blobs_sha = [cache.put(b) for b in blobs]

    return {
        "batch_index": event["batch_index"],
        "tx": event["tx"],
        "block": event["block"],
        "method": method_for_calldata(calldata),
        "calldata_sha256": calldata_sha,
        "blob_versioned_hashes": vhashes,
        "blobs_sha256": blobs_sha,
        "post": post,
    }


# ---------------------------------------------------------------------------
# Output: manifest (exact M2_SPEC §4 shape) + <=5 full fixtures
# ---------------------------------------------------------------------------

def build_manifest(window: dict, commits: list[dict], proxy: str) -> dict:
    return {
        "chain": "ethereum-mainnet",
        "rollup_proxy": proxy,
        "window": {"from_block": window["from_block"],
                   "to_block": window["to_block"]},
        "commits": commits,
    }


def manifest_bytes(manifest: dict) -> bytes:
    return (json.dumps(manifest, indent=2) + "\n").encode()


def write_fixture(path: Path, entry: dict, cache: Cache,
                  tx_index: dict | None, receipt: dict | None) -> None:
    fixture = {
        "commit": entry,
        "calldata": "0x" + (cache.get(entry["calldata_sha256"]) or b"").hex(),
        "blobs": ["0x" + (cache.get(h) or b"").hex()
                  for h in entry["blobs_sha256"]],
        "receipt": receipt,
        "index": tx_index,
    }
    name = f"batch{entry['batch_index']}-{entry['tx'][:12]}.json"
    (path / name).write_text(json.dumps(fixture, indent=2) + "\n")


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m holon.hist.fetch")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--snapshot-block", type=int,
                     help="window end block; re-run with the same value to "
                          "reproduce the manifest byte-for-byte")
    src.add_argument("--latest", action="store_true",
                     help="snapshot the current head (not reproducible later)")
    ap.add_argument("--rpc", default=DEFAULT_L1_RPC,
                    help="L1 JSON-RPC endpoint(s), comma-separated; attempts "
                         "rotate over the list when one rate-limits")
    ap.add_argument("--logs-rpc", default="https://eth-pokt.nodies.app",
                    help="endpoint(s) used only for the getLogs enumeration; "
                         "defaults to nodies (50-block free range cap)")
    ap.add_argument("--beacon", default=DEFAULT_BEACON)
    ap.add_argument("--blobscan", default=DEFAULT_BLOBSCAN)
    ap.add_argument("--proxy", default=ROLLUP_PROXY)
    ap.add_argument("--cache", type=Path, default=None)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "replay" / "M2" / "corpus")
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--min-commits", type=int, default=MIN_COMMITS)
    ap.add_argument("--fixtures", type=int, default=MAX_FIXTURES)
    ap.add_argument("--qps", type=float, default=4.0,
                    help="max requests per second across all endpoints")
    args = ap.parse_args(argv)
    rpc_urls = [u.strip() for u in args.rpc.split(",") if u.strip()]
    logs_urls = [u.strip() for u in args.logs_rpc.split(",") if u.strip()]

    client = Client(qps=args.qps)
    cache = Cache(args.cache or default_cache_dir())
    out_dir = args.out
    fixtures_dir = out_dir / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    snapshot = args.snapshot_block
    if args.latest:
        snapshot = int(client.rpc(rpc_urls, "eth_blockNumber", []), 16)
    print(f"snapshot block: {snapshot}", file=client.log)

    impl, lci = verify_proxy(client, rpc_urls, args.proxy, snapshot)
    print(f"proxy {args.proxy} ok: impl {impl}, lastCommittedBatchIndex {lci}",
          file=client.log)

    window = resolve_window(client, rpc_urls, snapshot, args.window_days)
    print(f"window: {window['from_block']}..{window['to_block']}", file=client.log)

    # Resumable run state (cache-side, outside the repo): a restart with the
    # same snapshot block continues where the last attempt stopped.
    state_path = cache.root / f"state-{window['from_block']}-{window['to_block']}.json"
    state = {"scan_next": window["from_block"], "events": [], "commits": {}}
    if state_path.exists():
        prev = json.loads(state_path.read_text())
        if prev.get("window") == window:
            state = prev
            print(f"resuming: {len(state['commits'])} commits, "
                  f"scan at {state['scan_next']}", file=client.log)

    def save_state() -> None:
        state["window"] = window
        tmp = state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state))
        tmp.replace(state_path)

    def on_chunk(events, next_block):
        state["events"] = events
        state["scan_next"] = next_block
        save_state()

    events = fetch_commit_events(client, logs_urls, args.proxy, window,
                                 events=state["events"],
                                 start_at=state["scan_next"],
                                 checkpoint=on_chunk)
    state["events"] = events
    save_state()
    print(f"commit events: {len(events)}", file=client.log)
    if len(events) < args.min_commits:
        raise FetchError(
            f"only {len(events)} CommitBatch events in window "
            f"(need >= {args.min_commits})")

    ts_cache: dict[int, int] = {}
    for i, ev in enumerate(events, 1):
        if ev["tx"] in state["commits"]:
            continue
        entry = fetch_commit(client, rpc_urls, args.beacon, args.blobscan,
                             args.proxy, ev, ts_cache, cache)
        state["commits"][ev["tx"]] = entry
        save_state()
        if i % 25 == 0 or i == len(events):
            print(f"  {i}/{len(events)} commits fetched", file=client.log)
    commits = [state["commits"][ev["tx"]] for ev in events]

    manifest = build_manifest(window, commits, args.proxy)
    data = manifest_bytes(manifest)
    manifest_path = out_dir / "manifest.json"
    if manifest_path.exists() and manifest_path.read_bytes() == data:
        print("manifest unchanged (byte-identical)", file=client.log)
    manifest_path.write_bytes(data)
    print(f"wrote {manifest_path} ({len(commits)} commits)", file=client.log)

    # Fixtures: the first N commits (lowest batch_index), fully self-contained.
    for old in fixtures_dir.glob("*.json"):
        old.unlink()
    for entry in commits[: max(0, min(args.fixtures, MAX_FIXTURES))]:
        idx = cache.index_get("tx", entry["tx"])
        receipt = None
        if idx and cache.get(idx["receipt"]):
            receipt = json.loads(cache.get(idx["receipt"]))
        write_fixture(fixtures_dir, entry, cache, idx, receipt)
    print(f"wrote {min(args.fixtures, MAX_FIXTURES)} fixtures", file=client.log)
    return 0


def main() -> int:
    try:
        return run()
    except FetchError as e:
        print(f"fetch failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
