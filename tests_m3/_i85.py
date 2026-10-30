"""I85 instrument (= I39a: the Go derivation extracted and the product machine), fixed at the I85 prereg (BUILD_PLAN
§0.1, "instruments are inputs").

The contract is the docstring of tests_m3/test_derivation_extraction.py (rules D1-D6, J1-J3, K1-K6, G1-G5, C1-C5).
This module writes the rules the tests decide a second time, independently of holon/: it never imports holon. It
reads the sidecar (spec/M3/lib/derivation.json), config/holon.json (where the target checkout is), the target
repository's git objects (read-only, lazy fetching disabled: a missing object is an InstrumentError, never a fetch),
committed records of earlier keys (the adopted Rollup document, I80's deployment record) and, after the build, the
committed document and records. tests_m2/_keccak.py gives keccak256.

  Rng(seed)                        a SHA-256 counter stream (deterministic on every Python): u64, below, pick, take
  rlp_str, rlp_list, rlp_int       RLP (the Ethereum yellow paper's appendix B), canonical
  tx_legacy, tx_typed              transaction encodings: a legacy RLP list, or a type byte and an RLP list (EIP-2718)
  context(...)                     a 60-byte block context: number, timestamp, base fee (32 bytes), gas limit, txs, l1
  header(...)                      a batch header by I20's harness rule (HolonTraceReplay.t.sol enc: 249 bytes, 257
                                   from version 1)
  genesis(root)                    I20's genesis header for the deployment record's init, with the check that its
                                   keccak256 is the word the deployment committed at committedBatches[0]
  planted(), random_cases(n), product_traces(), corpus()
                                   the sidecar's corpus section (rule C1), regenerated
  expand(segments)                 rule C2's payload segments as bytes ("0x.." and ["stream", seed, n])
  closure(section), reads(section, param), join(section, batch_type), join_rows(section, side, rollup_doc)
                                   rules D2, D3, D5 and J1 over a committed document's consumer section
  returns(root)                    the return statements of the consumer's body in the target source (K5's universe)
  recount(steps)                   rules C4-C5 recounted from results/M3/derivation/steps.json

  python -m tests_m3._i85 --corpus   print the corpus section (only at the prereg, to write the sidecar)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ROOT / "spec" / "M3" / "lib" / "derivation.json"
PIN = "3e44e795586af3e11285b603ab642c67823add51"
BLOB = 131072                 # bytes of one EIP-4844 blob
ELEM = 4096                   # field elements per blob
CHAIN = 53077                 # the Rollup's layer-2 chain id at the head (Rollup.sol constructor argument in I20)


class InstrumentError(RuntimeError):
    """An input the rules refuse."""


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def keccak(b: bytes) -> bytes:
    sys.path.insert(0, str(ROOT))
    from tests_m2._keccak import keccak256
    return keccak256(b)


def hx(b: bytes) -> str:
    return "0x" + bytes(b).hex()


# ---------------------------------------------------------------------------------------------- the stream
class Rng:
    """SHA-256(seed . counter) as a stream of 64-bit draws (no dependence on Python's random module)."""

    def __init__(self, seed: str):
        self.seed = seed.encode()
        self.n = 0

    def u64(self) -> int:
        h = hashlib.sha256(self.seed + self.n.to_bytes(8, "big")).digest()
        self.n += 1
        return int.from_bytes(h[:8], "big")

    def below(self, k: int) -> int:
        return self.u64() % k

    def pick(self, xs):
        return xs[self.below(len(xs))]

    def take(self, n: int) -> bytes:
        out = bytearray()
        while len(out) < n:
            out += hashlib.sha256(self.seed + b"/bytes/" + self.n.to_bytes(8, "big")).digest()
            self.n += 1
        return bytes(out[:n])


def stream(seed: str, n: int) -> bytes:
    """Rule C2's ["stream", seed, n]: the first n bytes of SHA-256(seed . k) for k = 0, 1, 2, ... (k as 8 big-endian
    bytes)."""
    out = bytearray()
    k = 0
    while len(out) < n:
        out += hashlib.sha256(seed.encode() + k.to_bytes(8, "big")).digest()
        k += 1
    return bytes(out[:n])


def expand(segments: list) -> bytes:
    """Rule C2: a payload's segments concatenated."""
    out = bytearray()
    for s in segments:
        if isinstance(s, str) and s.startswith("0x"):
            out += bytes.fromhex(s[2:])
        elif isinstance(s, list) and len(s) == 3 and s[0] == "stream":
            out += stream(s[1], s[2])
        else:
            raise InstrumentError(f"bad payload segment {str(s)[:80]}")
    return bytes(out)


# ---------------------------------------------------------------------------------------------- RLP and transactions
def _be(n: int) -> bytes:
    return b"" if n == 0 else n.to_bytes((n.bit_length() + 7) // 8, "big")


def rlp_str(b: bytes) -> bytes:
    if len(b) == 1 and b[0] < 0x80:
        return bytes(b)
    if len(b) <= 55:
        return bytes([0x80 + len(b)]) + b
    n = _be(len(b))
    return bytes([0xb7 + len(n)]) + n + b


def rlp_head(n: int, base: int) -> bytes:
    """The RLP prefix of a string (base 0x80) or list (base 0xc0) of n payload bytes."""
    if n <= 55:
        return bytes([base + n])
    m = _be(n)
    return bytes([base + 55 + len(m)]) + m


def rlp_list(items: list) -> bytes:
    p = b"".join(items)
    return rlp_head(len(p), 0xc0) + p


def rlp_int(n: int) -> bytes:
    return rlp_str(_be(n))


def _sig_word(rng: Rng) -> bytes:
    w = bytearray(rng.take(32))
    w[0] = w[0] | 0x01           # 32 bytes in canonical form: no leading zero byte
    return bytes(w)


def _access_list(rng: Rng) -> bytes:
    k = rng.below(3)
    entries = []
    for _ in range(k):
        keys = [rlp_str(rng.take(32)) for _ in range(rng.below(3))]
        entries.append(rlp_list([rlp_str(rng.take(20)), rlp_list(keys)]))
    return rlp_list(entries)


def tx_legacy(rng: Rng, data: bytes) -> bytes:
    v = rng.pick([27, 28, CHAIN * 2 + 35, CHAIN * 2 + 36])
    return rlp_list([rlp_int(rng.below(1000)), rlp_int(1 + rng.below(10 ** 10)), rlp_int(21000 + rng.below(10 ** 6)),
                     rlp_str(rng.take(20)), rlp_int(rng.below(10 ** 18)), rlp_str(data), rlp_int(v),
                     rlp_str(_sig_word(rng)), rlp_str(_sig_word(rng))])


def tx_typed(rng: Rng, kind: int, data: bytes) -> bytes:
    """EIP-2930 (kind 1) or EIP-1559 (kind 2): the type byte, then the RLP list."""
    head = [rlp_int(CHAIN), rlp_int(rng.below(1000))]
    if kind == 1:
        fees = [rlp_int(1 + rng.below(10 ** 10))]
    else:
        fees = [rlp_int(rng.below(10 ** 9)), rlp_int(1 + rng.below(10 ** 10))]
    body = head + fees + [rlp_int(21000 + rng.below(10 ** 6)), rlp_str(rng.take(20)), rlp_int(rng.below(10 ** 18)),
                          rlp_str(data), _access_list(rng), rlp_int(rng.below(2)), rlp_str(_sig_word(rng)),
                          rlp_str(_sig_word(rng))]
    return bytes([kind]) + rlp_list(body)


def tx(rng: Rng) -> bytes:
    data = rng.take(rng.below(48))
    kind = rng.pick([0, 1, 2, 2])
    return tx_legacy(rng, data) if kind == 0 else tx_typed(rng, kind, data)


def big_legacy_segments(rng: Rng, seed: str, n: int) -> list:
    """A legacy transaction whose data field is n bytes of stream(seed, n), as payload segments (rule C2), so that
    the sidecar holds the seed, not the bytes."""
    pre = [rlp_int(rng.below(1000)), rlp_int(1 + rng.below(10 ** 10)), rlp_int(21000 + rng.below(10 ** 6)),
           rlp_str(rng.take(20)), rlp_int(rng.below(10 ** 18))]
    post = [rlp_int(27), rlp_str(_sig_word(rng)), rlp_str(_sig_word(rng))]
    data_head = rlp_head(n, 0x80)
    total = sum(len(x) for x in pre) + len(data_head) + n + sum(len(x) for x in post)
    return [hx(rlp_head(total, 0xc0) + b"".join(pre) + data_head), ["stream", seed, n], hx(b"".join(post))]


# ---------------------------------------------------------------------------------------------- contexts and headers
def context(number: int, timestamp: int, base_fee: int, gas_limit: int, txs: int, l1: int) -> bytes:
    """A block context as node/types DecodeBlockContext reads it: number (8), timestamp (8), base fee (32), gas limit
    (8), txsNum (2), l1MsgNum (2), all big-endian: 60 bytes."""
    return (number.to_bytes(8, "big") + timestamp.to_bytes(8, "big") + base_fee.to_bytes(32, "big")
            + gas_limit.to_bytes(8, "big") + txs.to_bytes(2, "big") + l1.to_bytes(2, "big"))


def word(n) -> bytes:
    return n.to_bytes(32, "big") if isinstance(n, int) else bytes(n)


def header(v: int, idx: int, l1p: int, tot: int, dh, blob, prev, post, withdraw, parent, lbn: int = 0) -> bytes:
    """I20's harness rule (replay/M1/solidity/HolonTraceReplay.t.sol enc): version (1), batch index (8), L1 messages
    popped (8), total popped (8), data hash, blob versioned hash, previous and post state roots, withdrawal root,
    sequencer set verify hash (always 0), parent batch hash (32 each), and from version 1 the last block number (8)."""
    h = (bytes([v]) + idx.to_bytes(8, "big") + l1p.to_bytes(8, "big") + tot.to_bytes(8, "big") + word(dh) + word(blob)
         + word(prev) + word(post) + word(withdraw) + bytes(32) + word(parent))
    if v >= 1:
        h += lbn.to_bytes(8, "big")
    return h


ZVH = 0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014   # the Rollup's ZERO_VERSIONED_HASH


def genesis(root: Path = ROOT) -> bytes:
    """I20's genesis header for the deployment record's init (F, W, D, t0, r0): hdr(0, 0, 1, ZVH, r0); InstrumentError
    unless its keccak256 is the word I80's deployment record holds at committedBatches[0] (the Rollup document's
    mapping slot)."""
    dep = load(root / "replay" / "M3" / "bundle2" / "deployment.json")
    r0 = dep["init"][4]
    g = header(0, 0, 0, 0, 1, ZVH, 0, r0, 0, 0)
    doc = load(root / "spec" / "M2" / "facts" / "morph_rollup.extracted.json")
    slot = next(s["slot"] for s in doc["storage"] if s["name"] == "committedBatches")
    key = "0x" + keccak((0).to_bytes(32, "big") + slot.to_bytes(32, "big")).hex()
    have = dep["members"]["rollup"]["storage"].get(key)
    if have is None or int(have, 16) != int.from_bytes(keccak(g), "big"):
        raise InstrumentError(f"the genesis header does not hash to the deployment's committedBatches[0] ({have})")
    return g


# ---------------------------------------------------------------------------------------------- the corpus (rule C1)
def _ctxs(rng: Rng, first: int, n: int, l2: list, l1: list, zero_fee: bool = False) -> list:
    out = []
    for k in range(n):
        fee = 0 if zero_fee or rng.below(4) == 0 else 1 + rng.below(10 ** 12)
        out.append(context(first + k, 1_700_000_000 + 2 * (first + k), fee, 30_000_000 + rng.below(10 ** 6),
                           l2[k] + l1[k], l1[k]))
    return out


def _payload(ctxs: list, txs: list, tail: bytes = b"") -> list:
    return [hx(b"".join(ctxs) + b"".join(txs) + tail)]


def _root(rng: Rng) -> str:
    return hx(_sig_word(rng))


def _parent(v: int, idx: int, tot: int, lbn: int, rng: Rng) -> str:
    return hx(header(v, idx, 0, tot, rng.take(32), rng.take(32), rng.take(32), rng.take(32), rng.take(32),
                     rng.take(32), lbn))


def _case(cid: str, source: str, version: int, parent: str, lbn: int, l1: int, payload, blobs: int, rng: Rng,
          contexts=None, sets=None, compressed=None) -> dict:
    return {"id": cid, "source": source,
            "batch": {"Version": version, "ParentBatchHeader": parent, "BlockContexts": contexts,
                      "LastBlockNumber": lbn, "NumL1Messages": l1, "PrevStateRoot": _root(rng),
                      "PostStateRoot": _root(rng), "WithdrawRoot": _root(rng)},
            "payload": ({"compressed": compressed} if compressed is not None
                        else ({"raw": payload} if payload is not None else None)),
            "blobs": blobs, "set": sets or []}


def planted() -> list:
    """Rule C1's planted cases: inputs chosen, by reading ParseBatch, to end at each of its returns and at the panic
    of its blob decoder; none states an outcome."""
    r = Rng("i85/planted")
    T = lambda k: [tx(r) for _ in range(k)]  # noqa: E731
    out = []

    def add(cid, version, parent, lbn, payload, blobs=1, **kw):
        out.append(_case("planted/" + cid, "planted", version, parent, lbn, kw.pop("l1", 0), payload, blobs, r, **kw))

    p1 = lambda lbn, idx=7: _parent(1, idx, 3, lbn, r)  # noqa: E731
    p0 = lambda idx=7: _parent(0, idx, 3, 0, r)  # noqa: E731
    ok2 = lambda first: _payload(_ctxs(r, first, 2, [1, 2], [0, 0]), T(3))  # noqa: E731
    add("no_blobs", 1, p1(100), 102, None, blobs=0)
    add("parent_empty", 1, "0x", 102, ok2(101))
    add("parent_bad_version", 1, hx(b"\x03" + bytes.fromhex(p1(100)[4:])), 102, ok2(101))
    add("parent_bad_length", 1, p1(100)[:-16], 102, ok2(101))
    add("blob_high_byte", 1, p1(100), 102, ok2(101), sets=[[0, 32 * 5, 1]])
    add("blob_high_byte_late", 1, p1(100), 102, ok2(101), sets=[[0, 32 * 3968, 1]])
    add("compressed_garbage", 1, p1(100), 102, None, compressed=hx(b"\xff" * 64))
    add("compressed_empty", 1, p1(100), 102, None, compressed="0x")
    add("transition_short", 1, p0(), 1002, _payload([], [], b"\x00" * 10))
    add("transition_lbn_below", 1, p0(), 499, _payload(_ctxs(r, 500, 2, [1, 0], [0, 0]), T(1)))
    add("lbn_below_parent", 2, _parent(2, 7, 3, 100, r), 99, ok2(101))
    add("calldata_prefix_short", 0, p0(), 0, _payload([], T(1)), contexts="0x01")
    add("calldata_short", 1, p1(10), 12, _payload([], T(1)), contexts=hx(b"\x00\x02" + bytes(60)))
    add("blob_contexts_short", 1, p1(100), 105, _payload(_ctxs(r, 101, 2, [0, 0], [0, 0]), []))
    add("zero_block_count_v0", 0, p0(), 0, ok2(1))
    add("zero_block_count_equal", 1, p1(100), 100, ok2(101))
    add("bad_tx_type", 1, p1(100), 101, _payload(_ctxs(r, 101, 1, [1], [0]), [b"\x05" + bytes(70)]))
    add("tx_size_overflow", 1, p1(100), 101, _payload(_ctxs(r, 101, 1, [1], [0]), [b"\xfb\xff\xff\xff\xff\x01\x02"]))
    add("txsnum_below_l1", 1, p1(100), 101, _payload([context(101, 1_700_000_202, 7, 30_000_000, 1, 2)], T(1)))
    add("dequeue_short", 1, p1(100), 101, _payload(_ctxs(r, 101, 1, [3], [0]), T(1)))
    add("ok_transition", 1, p0(), 1002, _payload(_ctxs(r, 1000, 3, [1, 0, 2], [0, 0, 0]), T(3)))
    add("ok_v1", 1, p1(2000), 2003, _payload(_ctxs(r, 2001, 3, [2, 1, 1], [0, 0, 0]), T(4)))
    add("ok_v2_two_blobs", 2, _parent(2, 7, 3, 3000, r), 3002,
        [_payload(_ctxs(r, 3001, 2, [1, 1], [0, 0]), T(1))[0]] + big_legacy_segments(r, "i85/planted/big", 140000),
        blobs=2)
    add("ok_calldata_v0", 0, p0(), 0, _payload([], T(2)),
        contexts=hx(b"\x00\x02" + b"".join(_ctxs(r, 5000, 2, [1, 1], [0, 0]))))
    add("ok_calldata_v1", 1, p1(5999), 6001, _payload([], T(3)),
        contexts=hx(b"\x00\x02" + b"".join(_ctxs(r, 6000, 2, [2, 1], [0, 0]))))
    add("ok_basefee_zero", 1, p1(700), 702, _payload(_ctxs(r, 701, 2, [1, 1], [0, 0], zero_fee=True), T(2)))
    add("ok_empty_blocks", 1, p1(800), 802, _payload(_ctxs(r, 801, 2, [0, 0], [0, 0]), []))
    add("ok_l1_messages", 1, p1(900), 902, _payload(_ctxs(r, 901, 2, [1, 0], [2, 1]), T(1)), l1=3)
    add("ok_padded_second_blob", 1, p1(950), 951, _payload(_ctxs(r, 951, 1, [2], [0]), T(2)), blobs=2)
    return out


MUTATIONS = ("none", "drop_tx", "truncate", "corrupt", "high_byte", "version0", "parent_len", "l1_over",
             "zero_blobs", "extra_blob", "calldata_short")


def random_cases(n: int = 120) -> list:
    """Rule C1's random cases: a well-formed batch (contexts numbered as ParseBatch counts them, every context's
    transactions in the stream, NumL1Messages the contexts' L1 count) and at most one mutation, drawn in that order
    from Rng("i85/random")."""
    r = Rng("i85/random")
    out = []
    for i in range(n):
        pv = r.pick([0, 1, 2])
        v = r.pick([1, 2])
        nb = 1 + r.below(4)
        l2 = [r.below(4) for _ in range(nb)]
        l1 = [r.pick([0, 0, 0, 1, 2]) for _ in range(nb)]
        if pv == 0:
            first = 1 + r.below(10 ** 6)
            parent = _parent(0, 1 + r.below(10 ** 4), r.below(10 ** 3), 0, r)
        else:
            plbn = r.below(10 ** 6)
            first = plbn + 1
            parent = _parent(pv, 1 + r.below(10 ** 4), r.below(10 ** 3), plbn, r)
        lbn = first + nb - 1
        ctxs = _ctxs(r, first, nb, l2, l1)
        txs = [tx(r) for _ in range(sum(l2))]
        mut = r.pick(MUTATIONS)
        blobs, sets, version, contexts = 1, [], v, None
        if mut == "drop_tx" and txs:
            txs = txs[:-1]
        raw = b"".join(ctxs) + b"".join(txs)
        if mut == "truncate":
            raw = raw[:max(1, len(raw) - 1 - r.below(40))]
        if mut == "corrupt":
            sets = [[0, 1 + r.below(64), r.below(256)]]
        if mut == "high_byte":
            sets = [[0, 32 * r.below(200), 1 + r.below(255)]]
        if mut == "version0":
            version = 0
        if mut == "parent_len":
            parent = parent + "00"
        if mut == "l1_over":
            k = r.below(nb)
            c = bytearray(ctxs[k])
            tot = int.from_bytes(c[56:58], "big")
            c[58:60] = (tot + 1).to_bytes(2, "big")
            ctxs[k] = bytes(c)
            raw = b"".join(ctxs) + b"".join(txs)
        if mut == "zero_blobs":
            blobs = 0
        if mut == "extra_blob":
            blobs = 2
        if mut == "calldata_short":
            contexts = hx(nb.to_bytes(2, "big") + b"".join(ctxs)[:-1 - r.below(59)])
        out.append(_case(f"random/{i:03d}", "random", version, parent, lbn, sum(l1), [hx(raw)], blobs, r,
                         contexts=contexts, sets=sets))
    return out


def product_traces() -> list:
    """Rule C1's product traces (rule K1): commit sequences from I20's deployment, each commit's payload well-formed
    for the blocks after its parent's (the first context numbered after the last block the previous commit declared),
    no L1 message (the product's queue is empty)."""
    r = Rng("i85/product")
    plans = [("01", [1, 1, 2]), ("02", [0, 1, 2]), ("03", [2, 2, 1]), ("04", [1, 1]), ("05", [1, 1, 1, 1]),
             ("06", [0, 0, 1]), ("07", [2]), ("08", [1])]
    out = []
    for tid, versions in plans:
        nxt = 1
        commits = []
        for k, v in enumerate(versions):
            nb = 1 + r.below(3)
            if tid == "04":
                l2 = [0] * nb if k == 1 else [1 + r.below(2) for _ in range(nb)]
            elif tid == "08":
                l2 = [6, 6] if nb >= 2 else [12]
                nb = len(l2)
            else:
                l2 = [r.below(3) for _ in range(nb)]
            ctxs = _ctxs(r, nxt, nb, l2, [0] * nb, zero_fee=(tid == "04" and k == 0))
            txs = [tx(r) for _ in range(sum(l2))]
            segs = [hx(b"".join(ctxs) + b"".join(txs))]
            blobs = 1
            if tid == "07":
                segs += big_legacy_segments(r, "i85/product/big", 150000)
                blobs = 2
                c = bytearray(ctxs[-1])
                c[56:58] = (int.from_bytes(c[56:58], "big") + 1).to_bytes(2, "big")
                ctxs[-1] = bytes(c)
                segs[0] = hx(b"".join(ctxs) + b"".join(txs))
            if tid == "02" and k == 2:
                blobs = 2
            commits.append({"who": 2 + (k % 2), "version": v, "lastBlockNumber": nxt + nb - 1,
                            "postStateRoot": _root(r), "withdrawalRoot": _root(r), "payload": {"raw": segs},
                            "blobs": blobs})
            nxt += nb
        out.append({"id": "product/" + tid, "commits": commits})
    return out


def corpus() -> dict:
    return {"planted": planted(), "random": random_cases(), "product": product_traces()}


# ---------------------------------------------------------------------------------------------- the document (D, J)
def _ops(fn: dict):
    for b in fn.get("blocks") or []:
        for ins in b.get("instrs") or []:
            yield ins


def closure(section: dict) -> tuple[list, list]:
    """Rules D2-D3 recounted: (the functions reachable from the entry by static calls and closures whose bodies the
    section holds, the static callees outside them), both sorted."""
    funcs = section["functions"]
    seen, todo, env = set(), [section["entry"]], set()
    while todo:
        f = todo.pop()
        if f in seen or f not in funcs:
            continue
        seen.add(f)
        for ins in _ops(funcs[f]):
            c = ins.get("call")
            if c and c.get("mode") == "static":
                (todo.append if c["callee"] in funcs else env.add)(c["callee"])
            if ins.get("op") == "MakeClosure" and ins.get("fn"):
                todo.append(ins["fn"])
    return sorted(seen), sorted(env)


def reads(section: dict, param: int) -> list:
    """Rule D5 recounted: the field paths of the entry's parameter `param` that the entry reads (Field chains on the
    parameter, or FieldAddr chains on a local the parameter is stored into), sorted."""
    fn = section["functions"][section["entry"]]
    ins = list(_ops(fn))
    roots = {i["name"] for i in ins if i.get("op") == "Alloc"
             and any(s.get("op") == "Store" and s["operands"][0] == {"v": i["name"]} and s["operands"][1] == {"param": param}
                     for s in ins)}
    path: dict = {}
    for i in ins:
        if i.get("op") not in ("Field", "FieldAddr"):
            continue
        o = i["operands"][0] or {}
        base = None
        if o == {"param": param} and i["op"] == "Field":
            base = ()
        elif "v" in o and o["v"] in roots and i["op"] == "FieldAddr":
            base = ()
        elif "v" in o and o["v"] in path:
            base = path[o["v"]]
        if base is not None:
            path[i["name"]] = base + (i["fieldname"],)
    return sorted({".".join(p) for p in path.values()})


def join(section: dict, batch_type: str) -> list:
    """Rule J1 recounted over the join function: [source field, batch field] for every store into a field of a local
    of the batch type, the source traced back through conversions, loads, slices and one-argument static calls to a
    field read."""
    fn = section["join"]["ssa"]
    ins = {i["name"]: i for i in _ops(fn) if i.get("name")}
    allocs = {n for n, i in ins.items() if i.get("op") == "Alloc" and i.get("type") == "*" + batch_type}
    fields = {n: i["fieldname"] for n, i in ins.items()
              if i.get("op") == "FieldAddr" and (i["operands"][0] or {}).get("v") in allocs}

    def src(o, depth=0):
        if depth > 12 or not isinstance(o, dict) or "v" not in o or o["v"] not in ins:
            return None
        i = ins[o["v"]]
        op = i.get("op")
        if op in ("Field", "FieldAddr"):
            return i["fieldname"]
        if op in ("Convert", "ChangeType", "Slice") or (op == "UnOp" and i.get("unop") == "*"):
            return src(i["operands"][0], depth + 1)
        if op == "Call" and i["call"].get("mode") == "static" and len(i["call"]["args"]) == 1:
            return src(i["call"]["args"][0], depth + 1)
        return None
    rows = set()
    for i in _ops(fn):
        if i.get("op") == "Store" and (i["operands"][0] or {}).get("v") in fields:
            rows.add((src(i["operands"][1]), fields[i["operands"][0]["v"]]))
    return sorted([list(r) for r in rows], key=lambda r: (r[1], str(r[0])))


def join_rows(section: dict, side: dict, rollup_doc: dict) -> list:
    """Rule J1's product rows: [Solidity member, Go field (the member's first letter capitalized, as the derivation's
    ABI decoder names struct fields), batch field or null], in the commit parameter's member order."""
    act = next(a for a in rollup_doc["actions"] if a["name"] == side["product"]["commit_action"])
    param = next(p for p in act["params"] if p["name"] == side["product"]["commit_param"])
    rows = {s: b for s, b in join(section, side["product"]["batch_type"])}
    return [[m["name"], m["name"][:1].upper() + m["name"][1:], rows.get(m["name"][:1].upper() + m["name"][1:])]
            for m in param["fields"]]


# ---------------------------------------------------------------------------------------------- the source (K5)
def git(*args: str, repo: Path | None = None) -> str:
    cfg = load(ROOT / "config" / "holon.json")
    src = Path(repo or cfg["extract"]["sources"]["morph-l2/morph"])
    p = subprocess.run(["git", "-C", str(src), "-c", "protocol.allow=never", "-c", "gc.auto=0", *args],
                       capture_output=True, text=True)
    if p.returncode != 0:
        raise InstrumentError(f"git {' '.join(args)}: {p.stderr.strip()[:300]}")
    return p.stdout


def returns(root: Path = ROOT, side: dict | None = None) -> list:
    """The return statements of the consumer's body at the pinned commit: [[path:line, text]] in line order (the
    body from its func line to the first line that is a lone closing brace)."""
    side = side or load(SIDECAR)
    file, func = side["extract"]["consumer_source"]
    lines = git("show", f"{side['target']['commit']}:{file}").split("\n")
    start = next(k for k, ln in enumerate(lines) if ln.startswith(func))
    end = next(k for k in range(start + 1, len(lines)) if lines[k] == "}")
    return [[f"{file}:{k + 1}", lines[k].strip()] for k in range(start, end) if lines[k].strip().startswith("return")]


# ---------------------------------------------------------------------------------------------- the records (C4-C5)
OBS = ("status", "error", "panic", "info")


def agree(model: dict, real: dict) -> bool:
    return model.get("status") != "unsupported" and all(model.get(k) == real.get(k) for k in OBS)


def recount(steps: dict) -> dict:
    """Rules C4-C5 from steps.json alone: cases by source, agreement, unsupported, the sites the agreeing cases end at
    (their model exits), the panics' texts and every status pair."""
    by_source: dict = {}
    sites: dict = {}
    panics: dict = {}
    out = {"cases": 0, "agree": 0, "disagree": [], "unsupported": [], "by_source": by_source, "sites": sites,
           "panics": panics}
    for s in steps["steps"]:
        out["cases"] += 1
        by_source[s["source"]] = by_source.get(s["source"], 0) + 1
        m, r = s["model"], s["real"]
        if m.get("status") == "unsupported":
            out["unsupported"].append(s["id"])
        if agree(m, r):
            out["agree"] += 1
            if m.get("site"):
                site = ":".join(m["site"].split(":")[:2])
                sites[site] = sites.get(site, 0) + 1
            if m.get("status") == "panic":
                panics[m["panic"]] = panics.get(m["panic"], 0) + 1
        else:
            out["disagree"].append(s["id"])
        if bool(s.get("agree")) != agree(m, r):
            raise InstrumentError(f"{s['id']}: the record's agree flag is not the comparison of its two sides")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i85")
    ap.add_argument("--corpus", action="store_true", help="print the corpus section")
    a = ap.parse_args(argv)
    if a.corpus:
        print(json.dumps(corpus(), indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
