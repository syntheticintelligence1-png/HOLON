"""Input corpora for M2 refinement edges (whitepaper §8.7, sources 1-3):

1. grammar samples  — seeded random values of the carrier types;
2. sort boundaries  — 0, 1, max, max-1, and every sentinel constant;
3. refutation witnesses — every REFUTED law witness in results/, decoded
   into the edge's input type.

Everything is seeded deterministically (per-edge seed derived from the edge
name, recorded in the record).
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS_M0 = ROOT / "results" / "M0"
RESULTS_M1 = ROOT / "results" / "M1"

# Field names/widths of the M0 Header carrier, in declaration order.
FIELDS = [("version", 1), ("batchIndex", 8), ("l1MessagePopped", 8),
          ("totalL1MessagePopped", 8), ("dataHash", 32), ("blobVersionedHash", 32),
          ("prevStateHash", 32), ("postStateHash", 32), ("withdrawRootHash", 32),
          ("sequencerSetVerifyHash", 32), ("parentBatchHash", 32), ("lastBlockNumber", 8)]
HDR_CELLS = sum(w for _, w in FIELDS)  # 257


def edge_seed(edge: str) -> int:
    return int.from_bytes(hashlib.sha256(edge.encode()).digest()[:8], "big") & 0x7FFFFFFF


def _hex_bytes(s: str) -> list[int]:
    s = s[2:] if s.startswith("0x") else s
    if len(s) % 2:
        s = "0" + s
    return [int(s[i:i + 2], 16) for i in range(0, len(s), 2)]


def _u64(x: int) -> list[int]:
    return [(x >> (8 * k)) & 0xFF for k in reversed(range(8))]


# ------------------------------------------------------------------ headers

def grammar_headers(n: int, rng: random.Random) -> list[dict]:
    out = []
    for i in range(n):
        ver = rng.choice([0, 1])
        h = [ver] + [0] * (HDR_CELLS - 1)
        off = 1
        for name, w in FIELDS[1:-1]:
            for k in range(w):
                h[off + k] = rng.randrange(256) if rng.random() < 0.7 else 0
            off += w
        lbn = rng.choice([0, 1, rng.randrange(1 << 32), rng.randrange(1 << 64)])
        h[249:257] = _u64(lbn) if ver >= 1 else _u64(0)
        out.append({"kind": "hdr", "src": "grammar", "cells": h})
    return out


def boundary_headers(rng: random.Random) -> list[dict]:
    out = []
    # one field at a time takes a boundary value; others stay zero
    for name, w in FIELDS:
        off = sum(x for _, x in FIELDS[:[n for n, _ in FIELDS].index(name)])
        for v in (0, 1, (1 << (8 * w)) - 1, (1 << (8 * w)) - 2):
            h = [0] * HDR_CELLS
            bs = list(v.to_bytes(w, "big"))
            h[off:off + w] = bs
            out.append({"kind": "hdr", "src": f"boundary:{name}={v}", "cells": h})
    # sentinel constants: versions on a zero header
    for ver in (0, 1, 2, 3, 255):
        h = [0] * HDR_CELLS
        h[0] = ver
        out.append({"kind": "hdr", "src": f"boundary:version={ver}", "cells": h})
    # a full header at max
    out.append({"kind": "hdr", "src": "boundary:all-max",
                "cells": [255] * HDR_CELLS})
    return out


# ------------------------------------------------------------------ byte vectors

def grammar_bytes(n: int, rng: random.Random) -> list[dict]:
    out = []
    for _ in range(n):
        L = rng.choice([249, 257, rng.randrange(240, 270)])
        b = [rng.randrange(256) for _ in range(L)]
        b[0] = rng.choice([0, 1, 2, 3])
        out.append({"kind": "bytes", "src": "grammar", "b": b})
    return out


def boundary_bytes(rng: random.Random) -> list[dict]:
    out = []
    for L in (0, 1, 2, 248, 249, 250, 256, 257, 258, 259, 511, 512):
        for ver in (0, 1, 2, 3, 254, 255):
            b = [0] * L
            if L:
                b[0] = ver
            out.append({"kind": "bytes", "src": f"boundary:len={L},ver={ver}", "b": b})
    return out


# ------------------------------------------------------------------ witnesses

def m0_witnesses() -> list[dict]:
    """Every REFUTED M0 law witness, decoded as headers and byte vectors."""
    out = []
    for p in sorted(RESULTS_M0.glob("L_*.json")):
        rec = json.loads(p.read_text())
        if rec.get("status") != "REFUTED":
            continue
        w = rec.get("witness", {})
        law = p.stem
        if "h" in w:
            h = [0] * HDR_CELLS
            off = 0
            for name, width in FIELDS:
                bs = _hex_bytes(w["h"].get(name, ""))
                bs = bs[-width:] if len(bs) >= width else [0] * (width - len(bs)) + bs
                h[off:off + width] = bs
                off += width
            out.append({"kind": "hdr", "src": f"witness:{law}", "cells": h})
        if "b" in w:
            out.append({"kind": "bytes", "src": f"witness:{law}", "b": _hex_bytes(w["b"])})
    return out


def hdr_corpus(edge: str, n: int = 24) -> list[dict]:
    rng = random.Random(edge_seed(edge))
    return ([x for x in grammar_headers(n, rng) + boundary_headers(rng) + m0_witnesses()
             if x["kind"] == "hdr"])


def bytes_corpus(edge: str, n: int = 24) -> list[dict]:
    rng = random.Random(edge_seed(edge))
    return ([x for x in grammar_bytes(n, rng) + boundary_bytes(rng) + m0_witnesses()
             if x["kind"] == "bytes"])


# ------------------------------------------------------------------ traces

def rollup_witnesses() -> list[dict]:
    """REFUTED M1 rollup witnesses linearised into concrete traces."""
    from holon import mreplay
    out = []
    laws_dir = ROOT / "laws" / "M1"
    for p in sorted(RESULTS_M1.glob("L_*.json")):
        rec = json.loads(p.read_text())
        if rec.get("status") != "REFUTED":
            continue
        law_file = laws_dir / p.name
        if not law_file.exists():
            continue
        law = json.loads(law_file.read_text())
        if law.get("facts") != "spec/M1/facts/morph_rollup.json":
            continue  # batchdata witnesses belong to the batchdata corpus
        try:
            traces = mreplay.linearise(law, rec["witness"], conjunct=rec.get("refuted_conjunct"))
        except Exception:
            continue
        for tr in traces:
            steps = tr["trace"] if isinstance(tr, dict) and "trace" in tr else tr
            label = tr.get("label", "") if isinstance(tr, dict) else ""
            if not all(isinstance(a, dict) and a.get("op") in mreplay.OPS for a in steps):
                continue  # non-rollup actions cannot replay on the Rollup harness
            out.append({"kind": "trace", "src": f"witness:{p.stem}:{label}", "steps": steps})
    return out


def boundary_traces() -> list[dict]:
    """Single/double-step traces that poke every sentinel constant."""
    out = []

    def tr(src, steps):
        out.append({"kind": "trace", "src": src, "steps": steps})

    for who in (0, 1, 2, 3, 4, 5, 255):
        tr(f"boundary:sendMessage who={who}", [{"op": "sendMessage", "who": who}])
    for st in (0, 1):
        tr(f"boundary:setPause {st}", [{"op": "setPause", "who": 4, "status": bool(st)}])
    for dt in (0, 1, 255, 256, 65535):
        tr(f"boundary:wait dt={dt}", [{"op": "wait", "dt": dt}])
    for ver in (0, 1, 2, 3):
        for nb in (0, 1, 2):
            blobs = [100 + i for i in range(nb)]
            tr(f"boundary:commitBatch ver={ver} nb={nb}",
               [{"op": "commitBatch", "who": 2, "ver": ver, "parent": 0, "n": 1,
                 "lbn": 1, "prev": 1, "post": 2, "blobs": blobs}])
    for idx in (0, 1, 255):
        tr(f"boundary:revertBatch idx={idx}",
           [{"op": "commitBatch", "who": 2, "ver": 1, "parent": 0, "n": 1,
             "lbn": 1, "prev": 1, "post": 2, "blobs": [7]},
            {"op": "revertBatch", "who": 4, "idx": idx, "count": 1}])
    tr("boundary:legacy_eta2", [{"op": "@legacy_eta2", "root": 5}])
    return out


def bd_witnesses() -> list[dict]:
    out = []
    for p in sorted(RESULTS_M1.glob("L_*.json")):
        rec = json.loads(p.read_text())
        if rec.get("status") != "REFUTED":
            continue
        w = rec.get("witness", {})
        for key, steps in sorted(w.items()):
            if isinstance(steps, list) and steps and "bctx" in steps[0]:
                out.append({"kind": "btrace", "src": f"witness:{p.stem}:{key}",
                            "steps": steps})
    return out


def bd_grammar(rng: random.Random, n: int = 20) -> list[dict]:
    out = []
    for _ in range(n):
        steps = []
        for _ in range(rng.randint(1, 8)):
            if rng.random() < 0.7:
                steps.append({"op": "append",
                              "bctx": [rng.randrange(60) for _ in range(rng.choice([0, 60, 60, 120]))],
                              "payload": [rng.randrange(256) for _ in range(rng.randrange(0, 64))]})
            else:
                steps.append({"op": "txsPayloadV2"})
        out.append({"kind": "btrace", "src": "grammar", "steps": steps})
    return out


def bd_boundaries() -> list[dict]:
    out = []

    def tr(src, steps):
        out.append({"kind": "btrace", "src": src, "steps": steps})

    tr("boundary:empty", [])
    tr("boundary:txs_empty_view", [{"op": "txsPayloadV2"}])
    for nc in (0, 1, 60, 120):
        tr(f"boundary:append nctx={nc}",
           [{"op": "append", "bctx": [0] * nc, "payload": []},
            {"op": "txsPayloadV2"}])
    for np in (0, 1, 255, 256, 65535):
        tr(f"boundary:append npay={np}",
           [{"op": "append", "bctx": [0] * 60, "payload": [170] * np},
            {"op": "txsPayloadV2"}])
    tr("boundary:append_no_view", [{"op": "append", "bctx": [1] * 60, "payload": [9] * 4}])
    return out


def rollup_corpus(cm, edge: str, n: int = 60) -> tuple[list[dict], int]:
    """(corpus, seed). `cm` is a CompiledMachine for the explorer policy."""
    from holon import mreplay
    seed = edge_seed(edge)
    traces = [{"kind": "trace", "src": "grammar", "steps": t}
              for t in mreplay.random_corpus(cm, n, seed)]
    return traces + boundary_traces() + rollup_witnesses(), seed


def batchdata_corpus(edge: str, n: int = 40) -> tuple[list[dict], int]:
    rng = random.Random(edge_seed(edge))
    seed = edge_seed(edge)
    return bd_grammar(rng, n) + bd_boundaries() + bd_witnesses(), seed
