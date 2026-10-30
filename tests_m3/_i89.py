"""I89's instrument, fixed at the prereg: the rules of the docstring of tests_m3/test_derivation_bend.py written a second
time, independently of holon/ (this module never imports holon).

  python -m tests_m3._i89 --write      writes the sidecar spec/M3/lib/derivation_bend.json (no outcome in it)

  sidecar()                 the sidecar's content: the boundary (the blob layer, HypB; the decoder, HypT), the natives'
                            kinds, the cone observables of I88's product terms, the fuel, the outputs; the target's names
                            live here and in the inputs only
  cut(section, side)        rule B1: the blob-layer region of the consumer's entry ({"entry_block", "first", "blocks",
                            "boundary", "inputs", "exits"}), or a refusal (ValueError) when the SSA is not of that shape
  canonical_cases(side85)   rule H2: the ids of I85's cases whose blobs are the canonical construction (C2) of a raw
                            payload, with that payload's bytes
  case_ids(side85)          the 169 case ids in I85's order (planted, random, then product/<trace>/<k>)
  cone_view(info, side)     rule F2: a receiver dump projected on the cone's observed fields
  agree(model, real, side)  rule F2: the refinement's comparison of one case
"""
from __future__ import annotations

import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = "spec/M3/lib/derivation_bend.json"
I85_SIDECAR = "spec/M3/lib/derivation.json"
I88_SIDECAR = "spec/M3/lib/derivation_laws.json"
VERSION = "holon-derivation-bend/0.1"


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def file_sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def out_text(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# ====================================================================== the sidecar
def sidecar() -> dict:
    return {
        "derivation_bend_version": VERSION,
        "doc": ("I89 (= I39c) sidecar, fixed at the I89 prereg (contract: the docstring of "
                "tests_m3/test_derivation_bend.py; written by tests_m3/_i89.py --write). The boundary of the consumer's "
                "Bend model (the blob layer under HypB, the transaction decoder under HypT), the kinds of the "
                "environment's native callees, the cone observables of I88's product terms, the fuel and the outputs. It "
                "is the only place the target's names live for holon/derivation/bendgen.py and its siblings. It states no "
                "outcome."),
        "inputs": {
            "document": "spec/M3/facts/morph_derivation.extracted.json",
            "product_sidecar": I85_SIDECAR,
            "corpus": "gen/M3/derivation/corpus.json",
            "environment": "results/M3/derivation/environment.json",
            "replay": "replay/M3/derivation/report.json",
            "laws_sidecar": I88_SIDECAR,
        },
        "boundary": {
            "blob_layer": {
                "hypothesis": "HypB",
                "parameter": "pl",
                "retrieve": "morph-l2/common/batch.RetrieveBlobBytes",
                "decompress": "morph-l2/common/codec/zstd.DecompressBatchBytes",
                "blobs_field": ["Sidecar", "Blobs"],
                "answers": ["PlOk", "PlDErr", "PlRet", "PlPanic"],
            },
            "decoder": {
                "hypothesis": "HypT",
                "parameter": "dt",
                "function": "morph-l2/common/batch.DecodeTxsFromBytes",
                "answers": ["DtOk", "DtErr", "DtPanic"],
            },
        },
        "natives": {
            "fmt.Errorf": "errorf",
            "errors.New": "errors_new",
            "(encoding/binary.bigEndian).Uint16": "be_uint",
            "(encoding/binary.bigEndian).Uint64": "be_uint",
            "bytes.NewReader": "bytes_reader",
            "encoding/binary.Read": "binary_read",
            "(*math/big.Int).SetBytes": "big_setbytes",
            "(*math/big.Int).Cmp": "big_cmp",
            "math/big.NewInt": "big_newint",
            "(github.com/morph-l2/go-ethereum/core/types.Transactions).Len": "slice_len",
            "(*github.com/morph-l2/go-ethereum/core/types.Transaction).MarshalBinary": "encoding",
        },
        "native_globals": {"encoding/binary.BigEndian": "byte_order"},
        "io_errors": {"eof": "EOF", "unexpected_eof": "unexpected EOF"},
        "fuel": 1000000,
        "observables": {
            "derive_ok": {"status": True},
            "derived:lastBlockNumber": {"field": "lastBlockNumber"},
            "derived_sum:l1MsgNum": {"blocks": "blockContexts", "members": ["l1MsgNum"]},
            "derived_blocks": {"blocks": "blockContexts", "members": ["Number"]},
            "trailing": {"blocks": "blockContexts", "members": ["txsNum", "l1MsgNum"], "decoder": True},
            "txs_data": {"decoder": True},
            "derived_batch": {"receiver": True},
        },
        "laws": {
            "L_prod_cycle_lastBlockNumber": ["derive_ok", "txs_data", "derived:lastBlockNumber"],
            "L_prod_count_l1MsgNum": ["derive_ok", "txs_data", "derived_sum:l1MsgNum"],
            "L_prod_trailing_HypC_binds_trailing": ["derive_ok", "txs_data", "trailing"],
            "L_prod_trailing_HypC_ignores_trailing": ["derive_ok", "txs_data", "trailing", "derived_batch"],
            "L_prod_calldata_BlockContexts": ["derive_ok", "txs_data", "derived_blocks"],
        },
        "refinement": {"compare": ["status", "error", "panic"], "fields": ["lastBlockNumber"],
                       "blocks": {"field": "blockContexts", "members": ["Number", "txsNum", "l1MsgNum"]}},
        "go": {"test": "TestHolonBlobLayer", "env": "HOLON_DERIV_BLOBLAYER"},
        "outputs": {
            "model": "gen/M3/derivation/bend/consumer.bend",
            "model_info": "gen/M3/derivation/bend/model.json",
            "blob_layer": "replay/M3/derivation/bend/blob_layer.json",
            "hypb": "results/M3/derivation/bend/hypb.json",
            "refinement": "results/M3/derivation/bend/refinement.json",
            "laws": "gen/M3/derivation/bend/laws",
            "decisions": "results/M3/derivation/bend/decisions.json",
            "witnesses": "replay/M3/derivation/bend/witnesses.json",
        },
    }


def write() -> None:
    (ROOT / SIDECAR).write_text(out_text(sidecar()), encoding="utf-8")


# ====================================================================== the SSA
def operands(ins: dict) -> list:
    out = [o for o in (ins.get("operands") or []) if isinstance(o, dict)]
    if ins.get("op") == "Call":
        c = ins["call"]
        out += [o for o in (c.get("args") or []) if isinstance(o, dict)]
        if isinstance(c.get("value"), dict):
            out.append(c["value"])
    return out


def dominators(fn: dict) -> dict:
    """{block: the set of blocks dominating it}, by the iterative data-flow rule from block 0."""
    idx = [b["index"] for b in fn["blocks"]]
    preds = {b["index"]: list(b.get("preds") or []) for b in fn["blocks"]}
    dom = {b: set(idx) for b in idx}
    dom[idx[0]] = {idx[0]}
    changed = True
    while changed:
        changed = False
        for b in idx[1:]:
            ps = [dom[p] for p in preds[b]]
            new = (set.intersection(*ps) if ps else set()) | {b}
            if new != dom[b]:
                dom[b], changed = new, True
    return dom


def natural_loops(fn: dict) -> list:
    """The natural loop (a frozenset of blocks) of each back edge b -> h (h dominates b), merged per header."""
    dom = dominators(fn)
    preds = {b["index"]: list(b.get("preds") or []) for b in fn["blocks"]}
    by_head = defaultdict(set)
    for b in fn["blocks"]:
        for h in b.get("succs") or []:
            if h in dom[b["index"]]:
                body, todo = {h, b["index"]}, [b["index"]]
                while todo:
                    x = todo.pop()
                    if x == h:
                        continue
                    for p in preds[x]:
                        if p not in body:
                            body.add(p)
                            todo.append(p)
                by_head[h] |= body
    return [frozenset(by_head[h]) for h in sorted(by_head)]


def cut(section: dict, side: dict) -> dict:
    """Rule B1. D is the entry's one call of the blob layer's decompress function. The slice is the backward closure of
    D's operands through operands (phi edges included), where every block of a natural loop (a back edge b -> h, h
    dominating b) that holds a slice member is taken whole (all its values join the slice). The region's values are the
    greatest set S within the slice such that every use of a member of S is an instruction defining a member of S, D,
    or a value-free instruction of a whole region block. A
    block is in the region whole when every value it defines is in S and it is not D's block, or when it defines no
    value and all its predecessors are whole region blocks; the one partial block holds a suffix of region instructions
    (from its first member of S to its end); D is the first instruction of its block, whose predecessors are all whole
    region blocks. Inputs: the operands defined outside the region, each read only as the blobs field path (FieldAddr
    chain) and a load. Exits: each Return of the region (PlRet) and the edge to D (PlOk / PlDErr by D's answer)."""
    bl = side["boundary"]["blob_layer"]
    fn = section["functions"][section["entry"]]
    blocks = {b["index"]: b for b in fn["blocks"]}
    preds = {b["index"]: list(b.get("preds") or []) for b in fn["blocks"]}
    calls = [(b["index"], k) for b in fn["blocks"] for k, ins in enumerate(b["instrs"])
             if ins.get("op") == "Call" and ins["call"].get("mode") == "static"
             and ins["call"].get("callee") == bl["decompress"]]
    if len(calls) != 1:
        raise ValueError(f"{len(calls)} calls of the decompress function in the entry")
    bD, kD = calls[0]
    D = blocks[bD]["instrs"][kD]
    if kD != 0:
        raise ValueError("the decompress call is not the first instruction of its block")
    pos = {}
    for b in fn["blocks"]:
        for k, ins in enumerate(b["instrs"]):
            if ins.get("name"):
                pos[ins["name"]] = (b["index"], k)
    users = defaultdict(set)
    for b in fn["blocks"]:
        for k, ins in enumerate(b["instrs"]):
            for o in operands(ins):
                if "v" in o:
                    users[o["v"]].add((b["index"], k))
    loops = natural_loops(fn)
    sl, todo, taken = set(), [o["v"] for o in operands(D) if "v" in o], set()
    while todo:
        while todo:
            v = todo.pop()
            if v in sl or v not in pos:
                continue
            sl.add(v)
            b, k = pos[v]
            todo += [o["v"] for o in operands(blocks[b]["instrs"][k]) if "v" in o]
        for lp in loops:
            if lp in taken or not any(pos[v][0] in lp for v in sl):
                continue
            taken.add(lp)
            for b in sorted(lp):
                for ins in blocks[b]["instrs"]:
                    if ins.get("name"):
                        todo.append(ins["name"])
                    todo += [o["v"] for o in operands(ins) if "v" in o]
    S = set(sl)
    while True:
        defb = {pos[v][0] for v in S}
        whole = set()
        for b in sorted(defb):
            if b != bD and all(ins["name"] in S for ins in blocks[b]["instrs"] if ins.get("name")):
                whole.add(b)
        grew = True
        while grew:
            grew = False
            for b in sorted(blocks):
                if b in whole or b == bD or any(ins.get("name") for ins in blocks[b]["instrs"]):
                    continue
                if preds[b] and all(p in whole for p in preds[b]):
                    whole.add(b)
                    grew = True
        ok_pos = {pos[v] for v in S} | {(bD, kD)}
        for b in whole:
            ok_pos |= {(b, k) for k in range(len(blocks[b]["instrs"]))}
        drop = {v for v in S if any(u not in ok_pos for u in users[v])}
        if not drop:
            break
        S -= drop
    partial = sorted({pos[v][0] for v in S} - whole)
    if len(partial) != 1:
        raise ValueError(f"the region has {len(partial)} partial blocks")
    pb = partial[0]
    first = min(k for v in S for (b, k) in [pos[v]] if b == pb)
    for k, ins in enumerate(blocks[pb]["instrs"]):
        if k >= first and ins.get("name") and ins["name"] not in S:
            raise ValueError("the partial block's region instructions are not a suffix")
    if not all(p in whole for p in preds[bD]):
        raise ValueError("the decompress call's block has a predecessor outside the region")
    region = {(pb, k) for k in range(first, len(blocks[pb]["instrs"]))}
    for b in whole:
        region |= {(b, k) for k in range(len(blocks[b]["instrs"]))}
    for b in sorted(blocks):
        if b in whole:
            continue
        for s in blocks[b].get("succs") or []:
            if s in whole and not (b == pb and blocks[pb]["instrs"][-1].get("op") in ("Jump", "If")):
                raise ValueError(f"block {b} enters the region")
    ins_names = {blocks[b]["instrs"][k].get("name") for b, k in region} - {None}
    inputs = sorted({o["v"] for b, k in region for o in operands(blocks[b]["instrs"][k])
                     if "v" in o and o["v"] not in ins_names})
    path = list(bl["blobs_field"])
    for v in inputs:
        for (b, k) in sorted(users[v]):
            if (b, k) not in region:
                continue
            chain, cur, ok = [], (b, k), False
            while True:
                ins = blocks[cur[0]]["instrs"][cur[1]]
                if ins.get("op") == "FieldAddr" and len(chain) < len(path):
                    chain.append(ins.get("fieldname"))
                    nxt = sorted(users[ins["name"]])
                    if len(nxt) != 1 or nxt[0] not in region:
                        break
                    cur = nxt[0]
                    continue
                ok = (ins.get("op") == "UnOp" and ins.get("unop") == "*" and chain == path)
                break
            if not ok:
                raise ValueError(f"the region reads its input {v} other than as the blobs field")
    exits = []
    for b, k in sorted(region):
        ins = blocks[b]["instrs"][k]
        if ins.get("op") == "Return":
            exits.append({"block": b, "kind": "PlRet", "pos": ins.get("pos")})
        if ins.get("op") in ("If", "Jump"):
            for s in blocks[b].get("succs") or []:
                if s not in whole and s != bD:
                    raise ValueError(f"the region leaves to block {s}")
    exits.append({"block": bD, "kind": "D", "pos": D.get("pos")})
    return {"entry_block": pb, "first": first, "blocks": sorted(whole), "boundary": D["name"],
            "boundary_block": bD, "inputs": inputs, "exits": exits,
            "instructions": len(region)}


def closure_outside(section: dict, side: dict) -> list:
    """The functions of the consumer's closure the model compiles: those a call outside the region reaches from the
    entry (the region's callees are reached only through it)."""
    c = cut(section, side)
    fn = section["functions"]
    entry = section["entry"]
    region = set()
    blocks = {b["index"]: b for b in fn[entry]["blocks"]}
    for b in c["blocks"]:
        region |= {(b, k) for k in range(len(blocks[b]["instrs"]))}
    region |= {(c["entry_block"], k) for k in range(c["first"], len(blocks[c["entry_block"]]["instrs"]))}
    region.add((c["boundary_block"], 0))
    seen, todo = set(), [entry]
    while todo:
        f = todo.pop()
        if f in seen or f not in fn:
            continue
        seen.add(f)
        for b in fn[f]["blocks"]:
            for k, ins in enumerate(b["instrs"]):
                if f == entry and (b["index"], k) in region:
                    continue
                if ins.get("op") == "Call" and ins["call"].get("mode") == "static":
                    todo.append(ins["call"]["callee"])
    return sorted(seen)


# ====================================================================== the corpus
def case_ids(side85: dict) -> list:
    out = [c["id"] for c in side85["corpus"]["planted"] + side85["corpus"]["random"]]
    for tr in side85["corpus"]["product"]:
        for k, _cm in enumerate(tr["commits"], start=1):
            out.append(f"{tr['id']}/{k}")
    return out


def _expand(segments: list) -> bytes:
    out = bytearray()
    for s in segments:
        if isinstance(s, str) and s.startswith("0x"):
            out += bytes.fromhex(s[2:])
        elif isinstance(s, list) and len(s) == 3 and s[0] == "stream":
            k, buf = 0, bytearray()
            while len(buf) < s[2]:
                buf += hashlib.sha256(str(s[1]).encode() + k.to_bytes(8, "big")).digest()
                k += 1
            out += bytes(buf[:s[2]])
        else:
            raise ValueError(f"a payload segment {str(s)[:60]}")
    return bytes(out)


def canonical_cases(side85: dict) -> dict:
    """Rule H2: {case id: payload bytes} for the cases whose blobs are the canonical packing (C2) of the real
    compressor's output on a raw payload: a raw payload, at least one blob and no override."""
    out = {}
    for c in side85["corpus"]["planted"] + side85["corpus"]["random"]:
        p = c.get("payload")
        if p and "raw" in p and c.get("blobs", 0) >= 1 and not c.get("set"):
            out[c["id"]] = _expand(p["raw"])
    for tr in side85["corpus"]["product"]:
        for k, cm in enumerate(tr["commits"], start=1):
            p = cm.get("payload")
            if p and "raw" in p and cm.get("blobs", 0) >= 1 and not cm.get("set"):
                out[f"{tr['id']}/{k}"] = _expand(p["raw"])
    return out


# ====================================================================== the comparison
def cone_view(info, side: dict):
    """The receiver dump projected on the refinement's fields: {field: value} and the blocks' members, in order."""
    if info is None:
        return None
    r = side["refinement"]
    out = {f: info.get(f) for f in r["fields"]}
    bf = r["blocks"]["field"]
    bs = info.get(bf)
    out[bf] = None if bs is None else [{m: (b or {}).get(m) for m in r["blocks"]["members"]} for b in bs]
    return out


def agree(model: dict, real: dict, side: dict) -> bool:
    """Rule F2: the model's outcome agrees with the real one on status, error text, panic text and the cone view."""
    for k in side["refinement"]["compare"]:
        if model.get(k) != real.get(k):
            return False
    return cone_view(model.get("info"), side) == cone_view(real.get("info"), side)


if __name__ == "__main__":
    if sys.argv[1:] == ["--write"]:
        write()
        print(f"wrote {SIDECAR}")
    else:
        print(json.dumps({"cut": cut(load(ROOT / "spec/M3/facts/morph_derivation.extracted.json")["consumer"],
                                      sidecar())}, indent=1))
