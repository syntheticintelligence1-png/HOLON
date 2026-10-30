"""`holon derivation corpus` (rules C1-C3): the sidecar's corpus made concrete.

A case's payload is "raw" segments (C2: "0x.." bytes or ["stream", seed, n]) compressed by the sidecar's compressor
through the real library (goside's TestHolonCompress), or "compressed" bytes used as given, or none. The data is split
into one chunk per blob (4096 field elements of 31 data bytes each); `blob(chunk, j, sets)` packs a chunk canonically
and applies the case's overrides. gen/M3/derivation/corpus.json:
  {"corpus_version", "sidecar": {"path", "sha256"}, "cases": [{"id", "source", "batch", "data": [hex per blob], "set"}],
   "product": [{"id", "commits": [{"k", "data": [hex per blob], "blobs"}]}]}
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from . import OUT_GEN, DerivationError, Refused, dumps, ref

CORPUS_VERSION = "holon-derivation-corpus/0.1"
ELEMENTS = 4096
CHUNK = ELEMENTS * 31          # data bytes of one blob
BLOB = ELEMENTS * 32


def stream(seed: str, n: int) -> bytes:
    out = bytearray()
    k = 0
    while len(out) < n:
        out += hashlib.sha256(seed.encode() + k.to_bytes(8, "big")).digest()
        k += 1
    return bytes(out[:n])


def expand(segments: list) -> bytes:
    out = bytearray()
    for s in segments:
        if isinstance(s, str) and s.startswith("0x"):
            out += bytes.fromhex(s[2:])
        elif isinstance(s, list) and len(s) == 3 and s[0] == "stream" and isinstance(s[2], int):
            out += stream(str(s[1]), s[2])
        else:
            raise Refused(f"a payload segment {str(s)[:80]}")
    return bytes(out)


def chunks(data: bytes, n: int) -> list:
    """The data split over n blobs; a case with no blob delivers no payload."""
    if n == 0:
        return []
    if len(data) > n * CHUNK:
        raise DerivationError(f"{len(data)} data bytes do not fit {n} blob(s)")
    return ["0x" + data[j * CHUNK:(j + 1) * CHUNK].hex() for j in range(n)]


def blob(chunk_hex: str, j: int, sets: list) -> bytes:
    """Rule C2: field element k of the blob is a zero byte, then data bytes 31k .. 31k+30 of its chunk (zero padded);
    then the overrides [blob, byte, value] of blob j."""
    data = bytes.fromhex(chunk_hex[2:])
    out = bytearray(BLOB)
    for k in range(0, (len(data) + 30) // 31):
        piece = data[31 * k:31 * k + 31]
        out[32 * k + 1:32 * k + 1 + len(piece)] = piece
    for b, i, v in sets:
        if b == j:
            out[i] = v
    return bytes(out)


def blobs_hex(entry: dict) -> list:
    return ["0x" + blob(c, j, entry.get("set") or []).hex() for j, c in enumerate(entry["data"])]


def raw_payloads(side: dict) -> list:
    """Every raw payload of the corpus, in corpus order (planted, random, then product commits)."""
    out = []
    for c in side["corpus"]["planted"] + side["corpus"]["random"]:
        p = c.get("payload")
        if p and "raw" in p:
            out.append(expand(p["raw"]))
    for tr in side["corpus"]["product"]:
        for cm in tr["commits"]:
            out.append(expand(cm["payload"]["raw"]))
    return out


def compress_all(root: Path, side: dict, payloads: list) -> dict:
    """{sha256 of a raw payload: its compressed bytes}, by the real compressor in one Go run."""
    from .goside import Workspace
    uniq = sorted({hashlib.sha256(p).hexdigest(): p for p in payloads}.items())
    doc_rel = side["extract"]["output"]
    if not (root / doc_rel).is_file():
        raise Refused(f"{doc_rel} is missing (run holon derivation extract first)")
    from . import load
    section = load(root / doc_rel)["consumer"]
    with Workspace(root, side, section) as ws:
        out = ws.run("TestHolonCompress", "HOLON_DERIV_COMPRESS", {"payloads": ["0x" + p.hex() for _, p in uniq]})
    res = {}
    for (h, _), r in zip(uniq, out):
        if "bytes" not in r:
            raise DerivationError(f"the compressor refused a payload: {r}")
        res[h] = bytes.fromhex(r["bytes"][2:])
    return res


def build(side: dict, compressed: dict) -> dict:
    def data_of(payload, n):
        if payload is None:
            return chunks(b"", n)
        if "compressed" in payload:
            return chunks(bytes.fromhex(payload["compressed"][2:]), n)
        raw = expand(payload["raw"])
        return chunks(compressed[hashlib.sha256(raw).hexdigest()], n)
    cases = []
    for c in side["corpus"]["planted"] + side["corpus"]["random"]:
        cases.append({"id": c["id"], "source": c["source"], "batch": c["batch"],
                      "data": data_of(c.get("payload"), c["blobs"]), "set": c.get("set") or []})
    product = []
    for tr in side["corpus"]["product"]:
        product.append({"id": tr["id"], "commits": [
            {"k": k + 1, "blobs": cm["blobs"], "data": data_of(cm["payload"], cm["blobs"])}
            for k, cm in enumerate(tr["commits"])]})
    return {"cases": cases, "product": product}


def run(root: Path, side: dict, side_rel: str) -> dict:
    compressed = compress_all(root, side, raw_payloads(side))
    body = build(side, compressed)
    out = {"corpus_version": CORPUS_VERSION, "sidecar": ref(root, side_rel), **body}
    return {f"{OUT_GEN}/corpus.json": dumps(out)}
