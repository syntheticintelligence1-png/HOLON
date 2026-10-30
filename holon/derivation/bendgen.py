"""`holon derivation bend` (the contract is the docstring of tests_m3/test_derivation_bend.py, rules B1-B6): a generator
from the consumer section's Go SSA (go/ssa as ssadump prints it, I85's document) to a Bend model.

  python -m holon derivation bend [--check] [--bend-sidecar PATH] [--root DIR]

The model gen/M3/derivation/bend/consumer.bend holds:
  * a runtime library over one value type GV, with Go's semantics as I85's interpreter (holon.derivation.interp)
    implements them: integers of every width as two U32 limbs (64-bit two's complement, normalized to the width), booleans,
    nil, slices (cell, path, offset, length, capacity) over a heap of cells (a list), pointers (cell, path), arrays and
    structs as records, byte arrays as byte lists, interfaces (type id, value), tuples, error values (template id and
    arguments, or an oracle's text), and the native kinds the sidecar names (a byte reader, a big integer's magnitude, an
    oracle-decoded transaction, a byte order);
  * Out = ORet | OPan | OFuel, and Res = (Out, heap) per call;
  * one trampoline per compiled function: the blocks of its CFG are a per-function enum, each block (or segment of a
    block, split at every instruction that may panic or call) a non-recursive def returning the next transition, the
    run a structural recursion on a Nat fuel (the sidecar's fuel per call); every branch on a computed value goes
    through a helper def's parameter (Bend refuses a match on a computed value);
  * the blob-layer region of the entry (rule B1) replaced by one application of the parameter pl (PlOk, PlDErr, PlRet,
    PlPanic) to the blobs' elements, and the decoder's call by an application of the parameter dt (DtOk, DtErr,
    DtPanic): both are parameters of consumer_run, never answered by a def of the model;
  * consumer_run(pl, dt, cells, recv, batch): the entry on a heap of the globals' cells followed by `cells`.

gen/M3/derivation/bend/model.json records the cut, the compiled functions, the template table (id -> text with Go
verbs), the type ids of interface values, the globals' cells, the type layouts the evaluator builds values from, the
cones (rule B6), the model's sha256 and the unsupported constructs (none, or the model is not written). Anything the
generator cannot express faithfully raises Unsupported (exit 2). Nothing here names a target: every function, field,
constant and text comes from the document and the sidecar.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from . import Refused, dumps, load, ref
from .values import Types
from .values import Unsupported as VUnsupported

MODEL_VERSION = "holon-derivation-bend-model/0.1"
BEND_SIDECAR = "spec/M3/lib/derivation_bend.json"
VERSION = "holon-derivation-bend/0.1"


class Unsupported(Exception):
    """A construct the generator cannot express faithfully: the model is not written."""


def bend_sidecar(root: Path, rel: str = BEND_SIDECAR) -> dict:
    side = load(root / rel)
    if side.get("derivation_bend_version") != VERSION:
        raise Refused(f"{rel}: derivation_bend_version must be {VERSION}")
    for k in ("inputs", "boundary", "natives", "fuel", "outputs", "observables", "laws"):
        if k not in side:
            raise Refused(f"{rel}: no {k}")
    return side


# ====================================================================== the SSA helpers
def operands(ins: dict) -> list:
    out = [o for o in (ins.get("operands") or []) if isinstance(o, dict)]
    if ins.get("op") == "Call":
        c = ins["call"]
        out += [o for o in (c.get("args") or []) if isinstance(o, dict)]
        if isinstance(c.get("value"), dict):
            out.append(c["value"])
    return out


def dominators(blocks: list) -> dict:
    idx = [b["index"] for b in blocks]
    preds = {b["index"]: list(b.get("preds") or []) for b in blocks}
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


def loops_of(blocks: list) -> list:
    """The natural loops (frozensets of block indices) of the back edges b -> h (h dominating b), merged per header."""
    dom = dominators(blocks)
    preds = {b["index"]: list(b.get("preds") or []) for b in blocks}
    by_head = defaultdict(set)
    for b in blocks:
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


def blob_cut(section: dict, side: dict) -> dict:
    """Rule B1: the blob-layer region of the entry (see the contract). Raises Unsupported when the SSA is not of that
    shape. Returns {"entry_block", "first", "blocks", "boundary", "boundary_block", "inputs", "exits", "instructions"}
    plus "_region" (a set of (block, k)) and "_input_path" ([field indices]) for the generator."""
    bl = side["boundary"]["blob_layer"]
    fn = section["functions"][section["entry"]]
    blocks = {b["index"]: b for b in fn["blocks"]}
    preds = {b["index"]: list(b.get("preds") or []) for b in fn["blocks"]}
    found = [(b["index"], k) for b in fn["blocks"] for k, ins in enumerate(b["instrs"])
             if ins.get("op") == "Call" and ins["call"].get("mode") == "static"
             and ins["call"].get("callee") == bl["decompress"]]
    if len(found) != 1:
        raise Unsupported(f"the entry calls the blob layer's decompress function {len(found)} times")
    bD, kD = found[0]
    D = blocks[bD]["instrs"][kD]
    if kD != 0:
        raise Unsupported("the decompress call is not the first instruction of its block")
    pos, users = {}, defaultdict(set)
    for b in fn["blocks"]:
        for k, ins in enumerate(b["instrs"]):
            if ins.get("name"):
                pos[ins["name"]] = (b["index"], k)
            for o in operands(ins):
                if "v" in o:
                    users[o["v"]].add((b["index"], k))
    loops = loops_of(fn["blocks"])
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
        whole = {b for b in {pos[v][0] for v in S}
                 if b != bD and all(i["name"] in S for i in blocks[b]["instrs"] if i.get("name"))}
        grew = True
        while grew:
            grew = False
            for b in sorted(blocks):
                if b in whole or b == bD or any(i.get("name") for i in blocks[b]["instrs"]):
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
        raise Unsupported(f"the blob-layer region has {len(partial)} partial blocks")
    pb = partial[0]
    first = min(pos[v][1] for v in S if pos[v][0] == pb)
    for k, ins in enumerate(blocks[pb]["instrs"]):
        if k >= first and ins.get("name") and ins["name"] not in S:
            raise Unsupported("the region's part of its partial block is not a suffix")
    if not all(p in whole for p in preds[bD]):
        raise Unsupported("the decompress call's block has a predecessor outside the region")
    region = {(pb, k) for k in range(first, len(blocks[pb]["instrs"]))}
    for b in whole:
        region |= {(b, k) for k in range(len(blocks[b]["instrs"]))}
    for b in sorted(blocks):
        if b in whole:
            continue
        for s in blocks[b].get("succs") or []:
            if s in whole and not (b == pb and blocks[pb]["instrs"][-1].get("op") in ("Jump", "If")):
                raise Unsupported(f"block {b} enters the blob-layer region")
    names_in = {blocks[b]["instrs"][k].get("name") for b, k in region} - {None}
    inputs = sorted({o["v"] for b, k in region for o in operands(blocks[b]["instrs"][k])
                     if "v" in o and o["v"] not in names_in})
    want = list(bl["blobs_field"])
    path_idx = None
    for v in inputs:
        for (b, k) in sorted(users[v]):
            if (b, k) not in region:
                continue
            names, idxs, cur, ok = [], [], (b, k), False
            while True:
                ins = blocks[cur[0]]["instrs"][cur[1]]
                if ins.get("op") == "FieldAddr" and len(names) < len(want):
                    names.append(ins.get("fieldname"))
                    idxs.append(int(ins["field"]))
                    nxt = sorted(users[ins["name"]])
                    if len(nxt) != 1 or nxt[0] not in region:
                        break
                    cur = nxt[0]
                    continue
                ok = ins.get("op") == "UnOp" and ins.get("unop") == "*" and names == want
                break
            if not ok:
                raise Unsupported(f"the region reads its input {v} other than as the blobs field")
            if path_idx is not None and path_idx != (v, idxs):
                raise Unsupported("the region reads the blobs through two paths")
            path_idx = (v, idxs)
    if path_idx is None:
        raise Unsupported("the region reads no blobs field")
    exits = []
    for b, k in sorted(region):
        ins = blocks[b]["instrs"][k]
        if ins.get("op") == "Return":
            if len(ins.get("operands") or []) != 1:
                raise Unsupported("a region return of other than one value")
            exits.append({"block": b, "kind": "PlRet", "pos": ins.get("pos")})
        if ins.get("op") in ("If", "Jump"):
            for s in blocks[b].get("succs") or []:
                if s not in whole and s != bD:
                    raise Unsupported(f"the region leaves to block {s}")
        if ins.get("op") == "Panic":
            raise Unsupported("a panic instruction in the region")
    exits.append({"block": bD, "kind": "D", "pos": D.get("pos")})
    return {"entry_block": pb, "first": first, "blocks": sorted(whole), "boundary": D["name"], "boundary_block": bD,
            "inputs": inputs, "exits": exits, "instructions": len(region),
            "_region": region, "_input": path_idx[0], "_input_path": path_idx[1]}


def public_cut(c: dict) -> dict:
    return {k: v for k, v in c.items() if not k.startswith("_")}


# ====================================================================== the runtime library
RUNTIME_TEMPLATES = [
    ("nil", "runtime error: invalid memory address or nil pointer dereference"),
    ("idx_len", "runtime error: index out of range [%d] with length %d"),
    ("idx_neg", "runtime error: index out of range [%d]"),
    ("div0", "runtime error: integer divide by zero"),
    ("mk_len", "runtime error: makeslice: len out of range"),
    ("mk_cap", "runtime error: makeslice: cap out of range"),
    ("s_hi_neg", "runtime error: slice bounds out of range [:%d]"),
    ("s_hi_cap", "runtime error: slice bounds out of range [:%d] with capacity %d"),
    ("s_hi_len", "runtime error: slice bounds out of range [:%d] with length %d"),
    ("s_lo_neg", "runtime error: slice bounds out of range [%d:]"),
    ("s_lo_hi", "runtime error: slice bounds out of range [%d:%d]"),
    ("s3_mx_neg", "runtime error: slice bounds out of range [::%d]"),
    ("s3_mx_cap", "runtime error: slice bounds out of range [::%d] with capacity %d"),
    ("s3_mx_len", "runtime error: slice bounds out of range [::%d] with length %d"),
    ("s3_hi_neg", "runtime error: slice bounds out of range [:%d:]"),
    ("s3_hi_mx", "runtime error: slice bounds out of range [:%d:%d]"),
    ("s3_lo_neg", "runtime error: slice bounds out of range [%d::]"),
    ("s3_lo_hi", "runtime error: slice bounds out of range [%d:%d:]"),
]
RT_ID = {k: i for i, (k, _t) in enumerate(RUNTIME_TEMPLATES)}
GV_CTORS = [("VI", "h: U32, l: U32"), ("VB", "b: Bool"), ("VNil", ""),
            ("VS", "c: Nat, p: List<&2, Nat>, o: U32, n: U32, k: U32"), ("VP", "c: Nat, p: List<&2, Nat>"),
            ("VR", "fs: List<&2, GV>"), ("VY", "bs: List<&2, U32>"), ("VF", "t: U32, v: GV"), ("VT", "vs: List<&2, GV>"),
            ("VE", "t: U32, a: List<&2, GV>"), ("VEs", "s: List<&2, U32>"), ("VBig", "bs: List<&2, U32>"),
            ("VTx", "e: List<&2, U32>"), ("VRd", "bs: List<&2, U32>, i: U32"), ("VStr", "bs: List<&2, U32>"),
            ("VOrd", "")]

PRELUDE = '''import Base

# ---------------------------------------------------------------- values, outcomes, registers
type GV is Data:
{gv_ctors}

type Out is Data:
  ORet{{v: GV}}
  OPan{{e: GV}}
  OFuel{{}}

type Res is Data:
  Res{{o: Out, h: List<&2, GV>}}

type Eff is Data:
  EOk{{h: List<&2, GV>, v: GV}}
  EPan{{h: List<&2, GV>, e: GV}}
  ERet{{h: List<&2, GV>, v: GV}}
  EFuel{{h: List<&2, GV>}}

type RT is Data:
  RE{{}}
  RL{{v: GV}}
  RN{{a: RT, b: RT}}

# the blob layer's answer (HypB's parameter pl) and the decoder's (HypT's parameter dt); n: a nil slice
type PlAns is Data:
  PlOk{{n: Bool, bs: List<&2, U32>}}
  PlDErr{{e: GV}}
  PlRet{{e: GV}}
  PlPanic{{e: GV}}

type DtAns is Data:
  DtOk{{n: Bool, txs: List<&2, List<&2, U32>>}}
  DtErr{{e: GV}}
  DtPanic{{e: GV}}

def b2u(b: Bool) -> U32:
  match b:
    case True{{}}:
      1
    case False{{}}:
      0

def gbool(+x: GV) -> Bool:
  match x:
    case VB{{b}}:
      b
    case _:
      False{{}}

def ih(+x: GV) -> U32:
  match x:
    case VI{{h, l}}:
      h
    case _:
      0

def il(+x: GV) -> U32:
  match x:
    case VI{{h, l}}:
      l
    case _:
      0

def is_nil(+x: GV) -> Bool:
  match x:
    case VNil{{}}:
      True{{}}
    case _:
      False{{}}

def rget(ps: List<&2, Bool>, +t: RT) -> GV:
  match ps:
    case Nil{{}}:
      match t:
        case RL{{v}}:
          v
        case _:
          VNil{{}}
    case Con{{d, rest}}:
      match d:
        case True{{}}:
          match t:
            case RN{{a, b}}:
              rget(rest, b)
            case _:
              VNil{{}}
        case False{{}}:
          match t:
            case RN{{a, b}}:
              rget(rest, a)
            case _:
              VNil{{}}

def rset(ps: List<&2, Bool>, +t: RT, +v: GV) -> RT:
  match ps:
    case Nil{{}}:
      RL{{v}}
    case Con{{d, rest}}:
      match d:
        case True{{}}:
          match t:
            case RN{{a, b}}:
              RN{{a, rset(rest, b, v)}}
            case _:
              RN{{RE{{}}, rset(rest, RE{{}}, v)}}
        case False{{}}:
          match t:
            case RN{{a, b}}:
              RN{{rset(rest, a, v), b}}
            case _:
              RN{{rset(rest, RE{{}}, v), RE{{}}}}

# ---------------------------------------------------------------- lists and the heap
def lget(xs: List<&2, GV>, i: Nat) -> GV:
  match xs i:
    case Nil{{}} _:
      VNil{{}}
    case Con{{x, t}} 0n:
      x
    case Con{{x, t}} 1n+p:
      lget(t, p)

def lput(xs: List<&2, GV>, i: Nat, +v: GV) -> List<&2, GV>:
  match xs i:
    case Nil{{}} _:
      Nil{{}}
    case Con{{x, t}} 0n:
      Con{{v, t}}
    case Con{{x, t}} 1n+p:
      Con{{x, lput(t, p, v)}}

def bget(xs: List<&2, U32>, i: Nat) -> U32:
  match xs i:
    case Nil{{}} _:
      0
    case Con{{x, t}} 0n:
      x
    case Con{{x, t}} 1n+p:
      bget(t, p)

def bput(xs: List<&2, U32>, i: Nat, +v: U32) -> List<&2, U32>:
  match xs i:
    case Nil{{}} _:
      Nil{{}}
    case Con{{x, t}} 0n:
      Con{{v, t}}
    case Con{{x, t}} 1n+p:
      Con{{x, bput(t, p, v)}}

def glen(xs: List<&2, GV>) -> U32:
  U32.from_nat(List.length(&2, GV, xs))

def blen(xs: List<&2, U32>) -> U32:
  U32.from_nat(List.length(&2, U32, xs))

def hpush(xs: List<&2, GV>, +v: GV) -> List<&2, GV>:
  match xs:
    case Nil{{}}:
      [v]
    case Con{{x, t}}:
      Con{{x, hpush(t, v)}}

def hlen(+xs: List<&2, GV>) -> Nat:
  List.length(&2, GV, xs)

def y_zeros(n: Nat) -> List<&2, U32>:
  match n:
    case 0n:
      Nil{{}}
    case 1n+p:
      Con{{0, y_zeros(p)}}

def r_rep(n: Nat, +z: GV) -> List<&2, GV>:
  match n:
    case 0n:
      Nil{{}}
    case 1n+p:
      Con{{z, r_rep(p, z)}}

def vget(ps: List<&2, Nat>, +x: GV) -> GV:
  match ps:
    case Nil{{}}:
      x
    case Con{{+i, rest}}:
      match x:
        case VR{{+fs}}:
          vget(rest, lget(fs, i))
        case VY{{+bs}}:
          VI{{0, bget(bs, i)}}
        case _:
          VNil{{}}

def vset(ps: List<&2, Nat>, +x: GV, +v: GV) -> GV:
  match ps:
    case Nil{{}}:
      v
    case Con{{+i, rest}}:
      match x:
        case VR{{+fs}}:
          VR{{lput(fs, i, vset(rest, lget(fs, i), v))}}
        case VY{{+bs}}:
          VY{{bput(bs, i, U32.and(il(v), 255))}}
        case _:
          x

def hget(xs: List<&2, GV>, c: Nat) -> GV:
  lget(xs, c)

def hload(+h: List<&2, GV>, +p: GV) -> GV:
  match p:
    case VP{{c, ps}}:
      vget(ps, hget(h, c))
    case _:
      VNil{{}}

def hstore(+h: List<&2, GV>, +p: GV, +v: GV) -> List<&2, GV>:
  match p:
    case VP{{c, ps}}:
      lput(h, c, vset(ps, hget(h, c), v))
    case _:
      h

def pext(+ps: List<&2, Nat>, +k: Nat) -> List<&2, Nat>:
  List.append(&2, Nat, ps, [k])

def g_faddr(+p: GV, +k: Nat) -> GV:
  match p:
    case VP{{c, ps}}:
      VP{{c, pext(ps, k)}}
    case _:
      VNil{{}}

def nil_panic() -> GV:
  VE{{{t_nil}, Nil{{}}}}

def e_faddr(+h: List<&2, GV>, +p: GV, +k: Nat) -> Eff:
  match p:
    case VP{{c, ps}}:
      EOk{{h, VP{{c, pext(ps, k)}}}}
    case _:
      EPan{{h, nil_panic()}}

def e_load(+h: List<&2, GV>, +p: GV) -> Eff:
  match p:
    case VP{{c, ps}}:
      EOk{{h, vget(ps, hget(h, c))}}
    case _:
      EPan{{h, nil_panic()}}

def e_store(+h: List<&2, GV>, +p: GV, +v: GV) -> Eff:
  match p:
    case VP{{c, ps}}:
      EOk{{lput(h, c, vset(ps, hget(h, c), v)), VNil{{}}}}
    case _:
      EPan{{h, nil_panic()}}

def res_eff(r: Res) -> Eff:
  match r:
    case Res{{o, h}}:
      match o:
        case ORet{{v}}:
          EOk{{h, v}}
        case OPan{{e}}:
          EPan{{h, e}}
        case OFuel{{}}:
          EFuel{{h}}

# ---------------------------------------------------------------- integers (two U32 limbs, 64-bit two's complement)
def mulhi32(+a: U32, +b: U32) -> U32:
  +a0 = U32.and(a, 65535)
  +a1 = U32.shrn(a, 16n)
  +b0 = U32.and(b, 65535)
  +b1 = U32.shrn(b, 16n)
  +p00 = U32.mul(a0, b0)
  +p01 = U32.mul(a0, b1)
  +p10 = U32.mul(a1, b0)
  +p11 = U32.mul(a1, b1)
  +mid = U32.add(U32.add(U32.shrn(p00, 16n), U32.and(p01, 65535)), U32.and(p10, 65535))
  U32.add(U32.add(U32.add(p11, U32.shrn(p01, 16n)), U32.shrn(p10, 16n)), U32.shrn(mid, 16n))

def add64(+ah: U32, +al: U32, +bh: U32, +bl: U32) -> GV:
  +l = U32.add(al, bl)
  VI{{U32.add(U32.add(ah, bh), b2u(U32.is_lt(l, al))), l}}

def sub64(+ah: U32, +al: U32, +bh: U32, +bl: U32) -> GV:
  VI{{U32.sub(U32.sub(ah, bh), b2u(U32.is_lt(al, bl))), U32.sub(al, bl)}}

def mul64(+ah: U32, +al: U32, +bh: U32, +bl: U32) -> GV:
  VI{{U32.add(mulhi32(al, bl), U32.add(U32.mul(ah, bl), U32.mul(al, bh))), U32.mul(al, bl)}}

def i_add(+x: GV, +y: GV) -> GV:
  add64(ih(x), il(x), ih(y), il(y))

def i_sub(+x: GV, +y: GV) -> GV:
  sub64(ih(x), il(x), ih(y), il(y))

def i_mul(+x: GV, +y: GV) -> GV:
  mul64(ih(x), il(x), ih(y), il(y))

def u64lt(+ah: U32, +al: U32, +bh: U32, +bl: U32) -> Bool:
  Bool.or(U32.is_lt(ah, bh), Bool.and(U32.is_eq(ah, bh), U32.is_lt(al, bl)))

def i_eq(+x: GV, +y: GV) -> Bool:
  Bool.and(U32.is_eq(ih(x), ih(y)), U32.is_eq(il(x), il(y)))

def i_ult(+x: GV, +y: GV) -> Bool:
  u64lt(ih(x), il(x), ih(y), il(y))

def i_slt(+x: GV, +y: GV) -> Bool:
  u64lt(U32.xor(ih(x), 2147483648), il(x), U32.xor(ih(y), 2147483648), il(y))

def i_neg(+x: GV) -> Bool:
  U32.is_eq(U32.shrn(ih(x), 31n), 1)

def sx(+b: U32) -> U32:
  U32.mul(b, 4294967295)

def nk_u64(+x: GV) -> GV:
  VI{{ih(x), il(x)}}

def nk_i64(+x: GV) -> GV:
  VI{{ih(x), il(x)}}

def nk_u32(+x: GV) -> GV:
  VI{{0, il(x)}}

def nk_i32(+x: GV) -> GV:
  VI{{sx(U32.shrn(il(x), 31n)), il(x)}}

def nk_u16(+x: GV) -> GV:
  VI{{0, U32.and(il(x), 65535)}}

def nk_i16(+x: GV) -> GV:
  +lo = U32.and(il(x), 65535)
  +s = U32.shrn(lo, 15n)
  VI{{sx(s), U32.or(lo, U32.mul(s, 4294901760))}}

def nk_u8(+x: GV) -> GV:
  VI{{0, U32.and(il(x), 255)}}

def nk_i8(+x: GV) -> GV:
  +lo = U32.and(il(x), 255)
  +s = U32.shrn(lo, 7n)
  VI{{sx(s), U32.or(lo, U32.mul(s, 4294967040))}}

type QR is Data:
  QR{{xh: U32, xl: U32, qh: U32, ql: U32, rh: U32, rl: U32}}

def dv_set(ge: Bool, +xh: U32, +xl: U32, +qh: U32, +ql: U32, +rh: U32, +rl: U32, +yh: U32, +yl: U32) -> QR:
  match ge:
    case True{{}}:
      QR{{xh, xl, qh, U32.or(ql, 1), U32.sub(U32.sub(rh, yh), b2u(U32.is_lt(rl, yl))), U32.sub(rl, yl)}}
    case False{{}}:
      QR{{xh, xl, qh, ql, rh, rl}}

def dv_step(+s: QR, +yh: U32, +yl: U32) -> QR:
  match s:
    case QR{{xh, xl, qh, ql, rh, rl}}:
      +nxh = U32.or(U32.shln(xh, 1n), U32.shrn(xl, 31n))
      +nxl = U32.shln(xl, 1n)
      +nrh = U32.or(U32.shln(rh, 1n), U32.shrn(rl, 31n))
      +nrl = U32.or(U32.shln(rl, 1n), U32.shrn(xh, 31n))
      +nqh = U32.or(U32.shln(qh, 1n), U32.shrn(ql, 31n))
      +nql = U32.shln(ql, 1n)
      dv_set(Bool.not(u64lt(nrh, nrl, yh, yl)), nxh, nxl, nqh, nql, nrh, nrl, yh, yl)

def dv_loop(n: Nat, +s: QR, +yh: U32, +yl: U32) -> QR:
  match n:
    case 0n:
      s
    case 1n+p:
      dv_loop(p, dv_step(s, yh, yl), yh, yl)

def qr_q(s: QR) -> GV:
  match s:
    case QR{{xh, xl, qh, ql, rh, rl}}:
      VI{{qh, ql}}

def i_udiv(+x: GV, +y: GV) -> GV:
  qr_q(dv_loop(64n, QR{{ih(x), il(x), 0, 0, 0, 0}}, ih(y), il(y)))

def e_udiv_k(z: Bool, +h: List<&2, GV>, +x: GV, +y: GV) -> Eff:
  match z:
    case True{{}}:
      EPan{{h, VE{{{t_div0}, Nil{{}}}}}}
    case False{{}}:
      EOk{{h, i_udiv(x, y)}}

def e_udiv(+h: List<&2, GV>, +x: GV, +y: GV) -> Eff:
  e_udiv_k(i_eq(y, VI{{0, 0}}), h, x, y)

# ---------------------------------------------------------------- equality, interfaces, tuples
def g_eq(+x: GV, +y: GV) -> Bool:
  match x:
    case VI{{xh, xl}}:
      i_eq(x, y)
    case VB{{b}}:
      Bool.and(Bool.not(Bool.xor(b, gbool(y))), Bool.not(is_nil(y)))
    case VNil{{}}:
      is_nil(y)
    case _:
      Bool.not(is_nil(y))

def g_extract(+x: GV, +k: Nat) -> GV:
  match x:
    case VT{{vs}}:
      lget(vs, k)
    case _:
      VNil{{}}

# ---------------------------------------------------------------- slices
def bs_take(+xs: List<&2, U32>, +o: U32, +n: U32) -> List<&2, U32>:
  List.take(&2, U32, List.drop(&2, U32, xs, U32.to_nat(o)), U32.to_nat(n))

def gs_take(+xs: List<&2, GV>, +o: U32, +n: U32) -> List<&2, GV>:
  List.take(&2, GV, List.drop(&2, GV, xs, U32.to_nat(o)), U32.to_nat(n))

def byte_of(+x: GV) -> U32:
  U32.and(il(x), 255)

def gv_bytes(xs: List<&2, GV>) -> List<&2, U32>:
  match xs:
    case Nil{{}}:
      Nil{{}}
    case Con{{x, t}}:
      Con{{byte_of(x), gv_bytes(t)}}

def arr_bytes(+a: GV) -> List<&2, U32>:
  match a:
    case VY{{bs}}:
      bs
    case VR{{fs}}:
      gv_bytes(fs)
    case _:
      Nil{{}}

def y_elems(xs: List<&2, U32>) -> List<&2, GV>:
  match xs:
    case Nil{{}}:
      Nil{{}}
    case Con{{x, t}}:
      Con{{VI{{0, x}}, y_elems(t)}}

def arr_elems(+a: GV) -> List<&2, GV>:
  match a:
    case VR{{fs}}:
      fs
    case VY{{bs}}:
      y_elems(bs)
    case _:
      Nil{{}}

def arr_len(+a: GV) -> U32:
  match a:
    case VY{{bs}}:
      blen(bs)
    case VR{{fs}}:
      glen(fs)
    case _:
      0

# the bytes of a byte slice (nil: none), a string's bytes
def g_bytes(+h: List<&2, GV>, +s: GV) -> List<&2, U32>:
  match s:
    case VS{{c, p, o, n, k}}:
      bs_take(arr_bytes(vget(p, hget(h, c))), o, n)
    case VStr{{bs}}:
      bs
    case _:
      Nil{{}}

def g_elems(+h: List<&2, GV>, +s: GV) -> List<&2, GV>:
  match s:
    case VS{{c, p, o, n, k}}:
      gs_take(arr_elems(vget(p, hget(h, c))), o, n)
    case _:
      Nil{{}}

def g_len(+h: List<&2, GV>, +x: GV) -> GV:
  match x:
    case VS{{c, p, o, n, k}}:
      VI{{0, n}}
    case VStr{{bs}}:
      VI{{0, blen(bs)}}
    case VP{{c, p}}:
      VI{{0, arr_len(vget(p, hget(h, c)))}}
    case VR{{fs}}:
      VI{{0, glen(fs)}}
    case VY{{bs}}:
      VI{{0, blen(bs)}}
    case _:
      VI{{0, 0}}

def u32_gv(+n: U32) -> GV:
  VI{{0, n}}

def fits(+i: GV, +n: U32) -> Bool:
  Bool.and(U32.is_eq(ih(i), 0), U32.is_lt(il(i), n))

def le_u(+i: GV, +n: U32) -> Bool:
  Bool.and(U32.is_eq(ih(i), 0), U32.is_le(il(i), n))

def ix_k(neg: Bool, inr: Bool, +h: List<&2, GV>, +c: Nat, +p: List<&2, Nat>, +at: U32, +i: GV, +n: U32, +ti: U32, +tn: U32) -> Eff:
  match neg:
    case True{{}}:
      EPan{{h, VE{{{t_idx_neg}, [VF{{ti, i}}]}}}}
    case False{{}}:
      match inr:
        case True{{}}:
          EOk{{h, VP{{c, pext(p, U32.to_nat(U32.add(at, il(i))))}}}}
        case False{{}}:
          EPan{{h, VE{{{t_idx_len}, [VF{{ti, i}}, VF{{tn, VI{{0, n}}}}]}}}}

def iaddr_k(+x: GV, +neg: Bool, +h: List<&2, GV>, +i: GV, +ti: U32, +tn: U32) -> Eff:
  match x:
    case VS{{c, p, o, n, k}}:
      ix_k(neg, fits(i, n), h, c, p, o, i, n, ti, tn)
    case VP{{c, p}}:
      +n = arr_len(vget(p, hget(h, c)))
      ix_k(neg, fits(i, n), h, c, p, 0, i, n, ti, tn)
    case VNil{{}}:
      ix_k(neg, False{{}}, h, 0n, Nil{{}}, 0, i, 0, ti, tn)
    case _:
      EPan{{h, nil_panic()}}

# IndexAddr: x a slice or a pointer to an array; sg: the index's type is signed; ti, tn: type ids of the texts
def e_iaddr(+h: List<&2, GV>, +x: GV, +i: GV, sg: Bool, +ti: U32, +tn: U32) -> Eff:
  iaddr_k(x, Bool.and(sg, i_neg(i)), h, i, ti, tn)
'''

PRELUDE2 = '''
# ---------------------------------------------------------------- slicing (Go 1.24's checks and texts)
type SB is Data:
  SB{{c: Nat, p: List<&2, Nat>, o: U32, n: U32, k: U32, nil: Bool, cap_word: Bool}}

def sb_of(+h: List<&2, GV>, +x: GV) -> SB:
  match x:
    case VS{{c, p, o, n, k}}:
      SB{{c, p, o, n, k, False{{}}, True{{}}}}
    case VP{{c, p}}:
      +n = arr_len(vget(p, hget(h, c)))
      SB{{c, p, 0, n, n, False{{}}, False{{}}}}
    case VStr{{bs}}:
      SB{{0n, Nil{{}}, 0, blen(bs), blen(bs), False{{}}, False{{}}}}
    case _:
      SB{{0n, Nil{{}}, 0, 0, 0, True{{}}, True{{}}}}

def sl_mk(+x: GV, +b: SB, +i: U32, +j: U32, +k: U32) -> GV:
  match x:
    case VStr{{bs}}:
      VStr{{bs_take(bs, i, U32.sub(j, i))}}
    case VNil{{}}:
      VNil{{}}
    case _:
      match b:
        case SB{{c, p, o, n, kk, nl, cw}}:
          VS{{c, p, U32.add(o, i), U32.sub(j, i), U32.sub(k, i)}}

def capt(cw: Bool, +a: U32, +b: U32) -> U32:
  match cw:
    case True{{}}:
      a
    case False{{}}:
      b

# a two-index slice x[lo:hi]: hl/hh say whether lo/hi are given; sl/sh: signed types; tl/th/tn: type ids of the texts
def sl2_c4(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +j: U32, +tl: U32, +th: U32, +hi: GV) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s_lo_hi}, [VF{{tl, lo}}, VF{{th, hi}}]}}}}
    case False{{}}:
      match b:
        case SB{{bc, bp, bo, bn, bk, bnl, bcw}}:
          EOk{{h, sl_mk(x, b, il(lo), j, bk)}}

def sl2_c3(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +j: U32, +tl: U32, +th: U32, +hi: GV) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s_lo_neg}, [VF{{tl, lo}}]}}}}
    case False{{}}:
      sl2_c4(U32.is_lt(j, il(lo)), h, x, b, lo, j, tl, th, hi)

def sl2_c2(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +sl: Bool, +j: U32, +tl: U32, +th: U32, +tn: U32, +hi: GV) -> Eff:
  match c:
    case True{{}}:
      match b:
        case SB{{bc, bp, bo, bn, bk, bnl, bcw}}:
          EPan{{h, VE{{capt(bcw, {t_s_hi_cap}, {t_s_hi_len}), [VF{{th, hi}}, VF{{tn, VI{{0, bk}}}}]}}}}
    case False{{}}:
      sl2_c3(Bool.and(sl, i_neg(lo)), h, x, b, lo, j, tl, th, hi)

def sl2_c1(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +sl: Bool, +hi: GV, +tl: U32, +th: U32, +tn: U32) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s_hi_neg}, [VF{{th, hi}}]}}}}
    case False{{}}:
      match b:
        case SB{{bc, bp, bo, bn, bk, bnl, bcw}}:
          sl2_c2(Bool.not(le_u(hi, bk)), h, x, b, lo, sl, il(hi), tl, th, tn, hi)

def sl2_nohi(+h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +sl: Bool, +tl: U32, +tn: U32) -> Eff:
  match b:
    case SB{{bc, bp, bo, bn, bk, bnl, bcw}}:
      sl2_c3(Bool.and(sl, i_neg(lo)), h, x, b, lo, bn, tl, tn, VI{{0, bn}})

def sl2_go(hashi: Bool, +b: SB, +h: List<&2, GV>, +x: GV, +lo: GV, +hi: GV, +sl: Bool, +sh: Bool, +tl: U32, +th: U32, +tn: U32) -> Eff:
  match hashi:
    case True{{}}:
      sl2_c1(Bool.and(sh, i_neg(hi)), h, x, b, lo, sl, hi, tl, th, tn)
    case False{{}}:
      sl2_nohi(h, x, b, lo, sl, tl, tn)

def e_slice2(+h: List<&2, GV>, +x: GV, hashi: Bool, +lo: GV, +hi: GV, +sl: Bool, +sh: Bool, +tl: U32, +th: U32, +tn: U32) -> Eff:
  sl2_go(hashi, sb_of(h, x), h, x, lo, hi, sl, sh, tl, th, tn)

# a three-index slice x[lo:hi:mx] (hi and mx given)
def sl3_c6(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +hi: GV, +mx: GV, +tl: U32, +th: U32) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s3_lo_hi}, [VF{{tl, lo}}, VF{{th, hi}}]}}}}
    case False{{}}:
      EOk{{h, sl_mk(x, b, il(lo), il(hi), il(mx))}}

def sl3_c5(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +hi: GV, +mx: GV, +tl: U32, +th: U32) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s3_lo_neg}, [VF{{tl, lo}}]}}}}
    case False{{}}:
      sl3_c6(U32.is_lt(il(hi), il(lo)), h, x, b, lo, hi, mx, tl, th)

def sl3_c4(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +hi: GV, +mx: GV, +sl: Bool, +tl: U32, +th: U32, +tm: U32) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s3_hi_mx}, [VF{{th, hi}}, VF{{tm, mx}}]}}}}
    case False{{}}:
      sl3_c5(Bool.and(sl, i_neg(lo)), h, x, b, lo, hi, mx, tl, th)

def sl3_c3(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +hi: GV, +mx: GV, +sl: Bool, +tl: U32, +th: U32, +tm: U32) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s3_hi_neg}, [VF{{th, hi}}]}}}}
    case False{{}}:
      sl3_c4(U32.is_lt(il(mx), il(hi)), h, x, b, lo, hi, mx, sl, tl, th, tm)

def sl3_c2(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +hi: GV, +mx: GV, +sl: Bool, +sh: Bool, +tl: U32, +th: U32, +tm: U32, +tn: U32) -> Eff:
  match c:
    case True{{}}:
      match b:
        case SB{{bc, bp, bo, bn, bk, bnl, bcw}}:
          EPan{{h, VE{{capt(bcw, {t_s3_mx_cap}, {t_s3_mx_len}), [VF{{tm, mx}}, VF{{tn, VI{{0, bk}}}}]}}}}
    case False{{}}:
      sl3_c3(Bool.and(sh, i_neg(hi)), h, x, b, lo, hi, mx, sl, tl, th, tm)

def sl3_k(c: Bool, +h: List<&2, GV>, +x: GV, +b: SB, +lo: GV, +hi: GV, +mx: GV, +sl: Bool, +sh: Bool, +tl: U32, +th: U32, +tm: U32, +tn: U32, +bk: U32) -> Eff:
  match c:
    case True{{}}:
      EPan{{h, VE{{{t_s3_mx_neg}, [VF{{tm, mx}}]}}}}
    case False{{}}:
      sl3_c2(Bool.not(le_u(mx, bk)), h, x, b, lo, hi, mx, sl, sh, tl, th, tm, tn)

def sl3_go(+b: SB, +h: List<&2, GV>, +x: GV, +lo: GV, +hi: GV, +mx: GV, +sl: Bool, +sh: Bool, +sm: Bool, +tl: U32, +th: U32, +tm: U32, +tn: U32) -> Eff:
  match b:
    case SB{{bc, bp, bo, bn, bk, bnl, bcw}}:
      sl3_k(Bool.and(sm, i_neg(mx)), h, x, SB{{bc, bp, bo, bn, bk, bnl, bcw}}, lo, hi, mx, sl, sh, tl, th, tm, tn, bk)

def e_slice3(+h: List<&2, GV>, +x: GV, +lo: GV, +hi: GV, +mx: GV, +sl: Bool, +sh: Bool, +sm: Bool, +tl: U32, +th: U32, +tm: U32, +tn: U32) -> Eff:
  sl3_go(sb_of(h, x), h, x, lo, hi, mx, sl, sh, sm, tl, th, tm, tn)
'''

PRELUDE3 = '''
# ---------------------------------------------------------------- make, append
def mk_alloc(by: Bool, +h: List<&2, GV>, +n: GV, +c: GV, +z: GV) -> Eff:
  match by:
    case True{{}}:
      EOk{{hpush(h, VY{{y_zeros(U32.to_nat(il(c)))}}), VS{{hlen(h), Nil{{}}, 0, il(n), il(c)}}}}
    case False{{}}:
      EOk{{hpush(h, VR{{r_rep(U32.to_nat(il(c)), z)}}), VS{{hlen(h), Nil{{}}, 0, il(n), il(c)}}}}

# MakeSlice: bad_len (len < 0), bad_cap (cap < len), big (cap beyond the model's bound: fuel)
def e_makeslice(bad_len: Bool, bad_cap: Bool, big: Bool, by: Bool, +h: List<&2, GV>, +n: GV, +c: GV, +z: GV) -> Eff:
  match bad_len:
    case True{{}}:
      EPan{{h, VE{{{t_mk_len}, Nil{{}}}}}}
    case False{{}}:
      match bad_cap:
        case True{{}}:
          EPan{{h, VE{{{t_mk_cap}, Nil{{}}}}}}
        case False{{}}:
          match big:
            case True{{}}:
              EFuel{{h}}
            case False{{}}:
              mk_alloc(by, h, n, c, z)

def big_cap(+c: GV) -> Bool:
  Bool.not(u64lt(ih(c), il(c), 0, 268435457))

def w_items(xs: List<&2, GV>, +h: List<&2, GV>, +c: Nat, +p: List<&2, Nat>, +at: U32) -> List<&2, GV>:
  match xs:
    case Nil{{}}:
      h
    case Con{{x, t}}:
      w_items(t, hstore(h, VP{{c, pext(p, U32.to_nat(at))}}, x), c, p, U32.add(at, 1))

def app_new(by: Bool, +h: List<&2, GV>, +olds: List<&2, GV>, +items: List<&2, GV>) -> Eff:
  match by:
    case True{{}}:
      +all = List.append(&2, GV, olds, items)
      EOk{{hpush(h, VY{{gv_bytes(all)}}), VS{{hlen(h), Nil{{}}, 0, glen(all), glen(all)}}}}
    case False{{}}:
      +all = List.append(&2, GV, olds, items)
      EOk{{hpush(h, VR{{all}}), VS{{hlen(h), Nil{{}}, 0, glen(all), glen(all)}}}}

def app_fit(fit: Bool, by: Bool, +h: List<&2, GV>, +c: Nat, +p: List<&2, Nat>, +o: U32, +n: U32, +k: U32, +items: List<&2, GV>) -> Eff:
  match fit:
    case True{{}}:
      EOk{{w_items(items, h, c, p, U32.add(o, n)), VS{{c, p, o, U32.add(n, glen(items)), k}}}}
    case False{{}}:
      app_new(by, h, gs_take(arr_elems(vget(p, hget(h, c))), o, n), items)

def app_k(items: List<&2, GV>, +by: Bool, +h: List<&2, GV>, +s: GV) -> Eff:
  match items:
    case Nil{{}}:
      EOk{{h, s}}
    case Con{{+x, +t}}:
      match s:
        case VS{{c, p, o, n, k}}:
          app_fit(U32.is_le(U32.add(n, glen(Con{{x, t}})), k), by, h, c, p, o, n, k, Con{{x, t}})
        case _:
          app_new(by, h, Nil{{}}, Con{{x, t}})

def str_elems(xs: List<&2, U32>) -> List<&2, GV>:
  y_elems(xs)

def g_items(+h: List<&2, GV>, +t: GV) -> List<&2, GV>:
  match t:
    case VStr{{bs}}:
      str_elems(bs)
    case _:
      g_elems(h, t)

def e_append(by: Bool, +h: List<&2, GV>, +s: GV, +t: GV) -> Eff:
  app_k(g_items(h, t), by, h, s)


# ---------------------------------------------------------------- natives
def be_fold(xs: List<&2, U32>, +h: U32, +l: U32) -> GV:
  match xs:
    case Nil{{}}:
      VI{{h, l}}
    case Con{{x, t}}:
      be_fold(t, U32.or(U32.shln(h, 8n), U32.shrn(l, 24n)), U32.or(U32.shln(l, 8n), x))

def be_k(ok: Bool, +h: List<&2, GV>, +bs: List<&2, U32>, +w: U32, +tn: U32) -> Eff:
  match ok:
    case True{{}}:
      EOk{{h, be_fold(bs_take(bs, 0, w), 0, 0)}}
    case False{{}}:
      EPan{{h, VE{{{t_idx_len}, [VF{{tn, VI{{0, U32.sub(w, 1)}}}}, VF{{tn, VI{{0, blen(bs)}}}}]}}}}

# (encoding/binary's byte order).UintN(b): b[w-1] checked, then big-endian
def e_be_uint(+h: List<&2, GV>, +s: GV, +w: U32, +tn: U32) -> Eff:
  be_k(U32.is_le(w, blen(g_bytes(h, s))), h, g_bytes(h, s), w, tn)

def e_reader(+h: List<&2, GV>, +s: GV) -> Eff:
  EOk{{hpush(h, VRd{{g_bytes(h, s), 0}}), VP{{hlen(h), Nil{{}}}}}}

def un_f(+x: GV) -> GV:
  match x:
    case VF{{t, v}}:
      v
    case _:
      x

def rd_cell(+r: GV) -> Nat:
  match r:
    case VP{{c, p}}:
      c
    case _:
      0n

def w_bytes(xs: List<&2, U32>, +h: List<&2, GV>, +c: Nat, +p: List<&2, Nat>, +at: U32) -> List<&2, GV>:
  match xs:
    case Nil{{}}:
      h
    case Con{{x, t}}:
      w_bytes(t, hstore(h, VP{{c, pext(p, U32.to_nat(at))}}, VI{{0, x}}), c, p, U32.add(at, 1))

def br_store_s(s: GV, +h: List<&2, GV>, +chunk: List<&2, U32>) -> List<&2, GV>:
  match s:
    case VS{{c, p, o, n, k}}:
      w_bytes(chunk, h, c, p, o)
    case _:
      h

def br_store(by: Bool, +h: List<&2, GV>, +ptr: GV, +chunk: List<&2, U32>) -> List<&2, GV>:
  match by:
    case True{{}}:
      br_store_s(hload(h, ptr), h, chunk)
    case False{{}}:
      hstore(h, ptr, be_fold(chunk, 0, 0))

def br_n(by: Bool, +w: U32, +v: GV) -> U32:
  match by:
    case True{{}}:
      match v:
        case VS{{c, p, o, n, k}}:
          n
        case _:
          0
    case False{{}}:
      w

def br_k2(eof: Bool, short: Bool, by: Bool, +h: List<&2, GV>, +rc: Nat, +bs: List<&2, U32>, +i: U32, +ptr: GV, +n: U32) -> Eff:
  match eof:
    case True{{}}:
      EOk{{h, VE{{{t_eof}, Nil{{}}}}}}
    case False{{}}:
      match short:
        case True{{}}:
          EOk{{lput(h, rc, VRd{{bs, blen(bs)}}), VE{{{t_ueof}, Nil{{}}}}}}
        case False{{}}:
          EOk{{br_store(by, lput(h, rc, VRd{{bs, U32.add(i, n)}}), ptr, bs_take(bs, i, n)), VNil{{}}}}

def br_k(+rd: GV, +by: Bool, +h: List<&2, GV>, +rc: Nat, +ptr: GV, +w: U32) -> Eff:
  match rd:
    case VRd{{bs, i}}:
      +n = br_n(by, w, hload(h, ptr))
      +rest = U32.sub(blen(bs), i)
      br_k2(U32.is_eq(rest, 0), U32.is_lt(rest, n), by, h, rc, bs, i, ptr, n)
    case _:
      EPan{{h, nil_panic()}}

# encoding/binary.Read(r, order, data) of a fixed-size unsigned value (w bytes) or into a byte slice (by): io.ReadFull
def e_bread(by: Bool, +h: List<&2, GV>, +r: GV, +d: GV, +w: U32) -> Eff:
  br_k(hget(h, rd_cell(un_f(r))), by, h, rd_cell(un_f(r)), un_f(d), w)

def head0(+xs: List<&2, U32>) -> Bool:
  match xs:
    case Nil{{}}:
      False{{}}
    case Con{{x, r}}:
      U32.is_eq(x, 0)

def trim1(xs: List<&2, U32>, z: Bool) -> List<&2, U32>:
  match xs:
    case Nil{{}}:
      Nil{{}}
    case Con{{x, +r}}:
      match z:
        case True{{}}:
          trim1(r, head0(r))
        case False{{}}:
          Con{{x, r}}

def e_setbytes(+h: List<&2, GV>, +z: GV, +buf: GV) -> Eff:
  EOk{{hstore(h, z, VBig{{trim1(g_bytes(h, buf), head0(g_bytes(h, buf)))}}), z}}

def big_mag(+x: GV) -> List<&2, U32>:
  match x:
    case VBig{{bs}}:
      bs
    case _:
      Nil{{}}

def cmp1(+x: U32, +y: U32) -> U32:
  U32.add(b2u(U32.is_lt(x, y)), U32.mul(2, b2u(U32.is_lt(y, x))))

def pick(+acc: U32, +c: U32) -> U32:
  U32.add(acc, U32.mul(c, b2u(U32.is_eq(acc, 0))))

def lexc(xs: List<&2, U32>, ys: List<&2, U32>, +acc: U32) -> U32:
  match xs:
    case Nil{{}}:
      acc
    case Con{{x, t}}:
      match ys:
        case Nil{{}}:
          acc
        case Con{{y, u}}:
          lexc(t, u, pick(acc, cmp1(x, y)))

def cmp_gv(+c: U32) -> GV:
  VI{{sx(b2u(U32.is_eq(c, 1))), U32.or(sx(b2u(U32.is_eq(c, 1))), b2u(U32.is_eq(c, 2)))}}

def big_cmp_v(+a: List<&2, U32>, +b: List<&2, U32>) -> GV:
  cmp_gv(pick(cmp1(blen(a), blen(b)), lexc(a, b, 0)))

def cmp_go(nx: Bool, ny: Bool, +h: List<&2, GV>, +x: GV, +y: GV) -> Eff:
  match nx:
    case True{{}}:
      EPan{{h, nil_panic()}}
    case False{{}}:
      match ny:
        case True{{}}:
          EPan{{h, nil_panic()}}
        case False{{}}:
          EOk{{h, big_cmp_v(big_mag(hload(h, x)), big_mag(hload(h, y)))}}

# (*big.Int).Cmp(x, y): -1, 0 or 1; a nil operand panics
def e_bigcmp(+h: List<&2, GV>, +x: GV, +y: GV) -> Eff:
  cmp_go(is_nil(x), is_nil(y), h, x, y)

def e_newbig(+h: List<&2, GV>, +mag: List<&2, U32>) -> Eff:
  EOk{{hpush(h, VBig{{mag}}), VP{{hlen(h), Nil{{}}}}}}

def mb_k(+h: List<&2, GV>, +x: GV) -> Eff:
  match x:
    case VTx{{e}}:
      EOk{{hpush(h, VY{{e}}), VT{{[VS{{hlen(h), Nil{{}}, 0, blen(e), blen(e)}}, VNil{{}}]}}}}
    case _:
      EPan{{h, nil_panic()}}

# the encoding callee: a transaction the decoder answered, encoded as the decoder reported it, and a nil error
def e_marshal(+h: List<&2, GV>, +x: GV) -> Eff:
  mb_k(h, x)

def tx_vals(xs: List<&2, List<&2, U32>>) -> List<&2, GV>:
  match xs:
    case Nil{{}}:
      Nil{{}}
    case Con{{x, t}}:
      Con{{VTx{{x}}, tx_vals(t)}}

def dt_ok(n: Bool, +h: List<&2, GV>, +txs: List<&2, List<&2, U32>>) -> Eff:
  match n:
    case True{{}}:
      EOk{{h, VT{{[VNil{{}}, VNil{{}}]}}}}
    case False{{}}:
      EOk{{hpush(h, VR{{tx_vals(txs)}}), VT{{[VS{{hlen(h), Nil{{}}, 0, glen(tx_vals(txs)), glen(tx_vals(txs))}}, VNil{{}}]}}}}

def dt_k(a: DtAns, +h: List<&2, GV>) -> Eff:
  match a:
    case DtOk{{n, txs}}:
      dt_ok(n, h, txs)
    case DtErr{{e}}:
      EOk{{h, VT{{[VNil{{}}, e]}}}}
    case DtPanic{{e}}:
      EPan{{h, e}}

# the decoder's call: HypT's parameter dt applied to the argument's bytes
def e_dt(dt: List<&2, U32> -> DtAns, +h: List<&2, GV>, +s: GV) -> Eff:
  dt_k(dt(g_bytes(h, s)), h)

def pl_ok(n: Bool, +h: List<&2, GV>, +bs: List<&2, U32>) -> Eff:
  match n:
    case True{{}}:
      EOk{{h, VT{{[VNil{{}}, VNil{{}}]}}}}
    case False{{}}:
      EOk{{hpush(h, VY{{bs}}), VT{{[VS{{hlen(h), Nil{{}}, 0, blen(bs), blen(bs)}}, VNil{{}}]}}}}

def pl_k(a: PlAns, +h: List<&2, GV>) -> Eff:
  match a:
    case PlOk{{n, bs}}:
      pl_ok(n, h, bs)
    case PlDErr{{e}}:
      EOk{{h, VT{{[VNil{{}}, e]}}}}
    case PlRet{{e}}:
      ERet{{h, e}}
    case PlPanic{{e}}:
      EPan{{h, e}}

# the blob-layer region: HypB's parameter pl applied to the blobs' elements
def e_pl(pl: List<&2, GV> -> PlAns, +h: List<&2, GV>, +s: GV) -> Eff:
  pl_k(pl(g_elems(h, s)), h)

def pl_spent(xs: List<&2, GV>) -> PlAns:
  PlRet{{VNil{{}}}}

def dt_spent(xs: List<&2, U32>) -> DtAns:
  DtErr{{VNil{{}}}}
'''


# ====================================================================== the compiler
def bpath(i: int, depth: int) -> str:
    return "[" + ", ".join("True{}" if (i >> (depth - 1 - j)) & 1 else "False{}" for j in range(depth)) + "]"


def int_kind(info) -> str:
    bits, unsigned = info
    if bits not in (8, 16, 32, 64):
        raise Unsupported(f"an integer of {bits} bits")
    return ("u" if unsigned else "i") + str(bits)


def limbs(v: int) -> tuple:
    v &= (1 << 64) - 1
    return v >> 32, v & 0xFFFFFFFF


class FnInfo:
    def __init__(self, fid: str, idx: int, raw: dict):
        self.fid, self.idx, self.raw = fid, idx, raw
        self.p = f"f{idx}"
        self.params = raw.get("params") or []
        self.types = {}
        for b in raw["blocks"]:
            for ins in b["instrs"]:
                if ins.get("name"):
                    self.types[ins["name"]] = ins.get("type") or ""


class Compiler:
    def __init__(self, section: dict, side: dict, cut: dict):
        self.section, self.side, self.cut = section, side, cut
        try:
            self.ty = Types(section["types"])
        except VUnsupported as e:
            raise Unsupported(str(e))
        self.entry = section["entry"]
        self.raw = section["functions"]
        self.kinds = {e["function"]: e["kind"] for e in section["environment"]}
        self.decoder = side["boundary"]["decoder"]["function"]
        self.fuel = int(side["fuel"])
        self.templates: list = [{"text": t, "kind": "format"} for _k, t in RUNTIME_TEMPLATES]
        self.t_eof = self.template(side["io_errors"]["eof"], "literal")
        self.t_ueof = self.template(side["io_errors"]["unexpected_eof"], "literal")
        self.tids: dict = {}
        self.out: list = []
        self.globals: list = []
        self.gcell: dict = {}
        self.consumed = set()

    # ------------------------------------------------------------ tables
    def template(self, text: str, kind: str) -> int:
        for i, t in enumerate(self.templates):
            if t["text"] == text and t["kind"] == kind:
                return i
        self.templates.append({"text": text, "kind": kind})
        return len(self.templates) - 1

    def tid(self, t: str) -> int:
        if t not in self.tids:
            self.tids[t] = len(self.tids)
        return self.tids[t]

    def int_info(self, t: str):
        try:
            return self.ty.int_info(t)
        except VUnsupported as e:
            raise Unsupported(str(e))

    def kind(self, t: str) -> str:
        try:
            return self.ty.kind(t)
        except VUnsupported as e:
            raise Unsupported(str(e))

    # ------------------------------------------------------------ the call graph
    def region_pos(self) -> set:
        return set(self.cut["_region"]) | {(self.cut["boundary_block"], 0)}

    def callees(self, fid: str) -> list:
        out, skip = [], (self.region_pos() if fid == self.entry else set())
        for b in self.raw[fid]["blocks"]:
            for k, ins in enumerate(b["instrs"]):
                if (b["index"], k) in skip:
                    continue
                if ins.get("op") == "Call" and ins["call"].get("mode") == "static" and ins["call"]["callee"] in self.raw:
                    out.append(ins["call"]["callee"])
        return out

    def order(self) -> list:
        seen, order = set(), []

        def visit(f, stack):
            if f in stack:
                raise Unsupported(f"recursion through {f}")
            if f in seen:
                return
            for g in sorted(set(self.callees(f))):
                visit(g, stack | {f})
            seen.add(f)
            order.append(f)
        visit(self.entry, frozenset())
        return order

    # ------------------------------------------------------------ values
    def zero(self, t: str) -> str:
        if t == "math/big.Int":
            return "VBig{Nil{}}"
        e = self.ty.entry(t)
        k = e.get("kind")
        if k == "basic":
            if e.get("boolean"):
                return "VB{False{}}"
            if e.get("string"):
                return "VStr{Nil{}}"
            if e.get("integer"):
                return "VI{0, 0}"
            raise Unsupported(f"the zero of {t}")
        if k in ("pointer", "slice", "map", "chan", "signature", "interface"):
            return "VNil{}"
        if k == "struct":
            fs = [self.zero(f["type"]) for f in e.get("fields") or []]
            return "VR{[" + ", ".join(fs) + "]}" if fs else "VR{Nil{}}"
        if k == "array":
            n = int(e["len"])
            if self.ty.is_byte(e["elem"]):
                if n <= 64:
                    return "VY{[" + ", ".join(["0"] * n) + "]}" if n else "VY{Nil{}}"
                return f"VY{{y_zeros(U32.to_nat({n}))}}"
            z = self.zero(e["elem"])
            if n <= 16:
                return "VR{[" + ", ".join([z] * n) + "]}" if n else "VR{Nil{}}"
            return f"VR{{r_rep(U32.to_nat({n}), {z})}}"
        raise Unsupported(f"the zero of {t} ({k})")

    def const(self, c: dict) -> str:
        k = c.get("kind")
        if k == "int":
            t = c.get("type") or "int"
            info = self.int_info(t) or (64, False)
            h, l = limbs(int(c["value"]))
            v = int(c["value"]) & ((1 << info[0]) - 1)
            if not info[1] and v >> (info[0] - 1):
                v -= 1 << info[0]
            h, l = limbs(v)
            return f"VI{{{h}, {l}}}"
        if k == "bool":
            return "VB{True{}}" if c["value"] == "true" else "VB{False{}}"
        if k == "string":
            bs = c["value"].encode("utf-8", "surrogateescape")
            return "VStr{[" + ", ".join(str(b) for b in bs) + "]}" if bs else "VStr{Nil{}}"
        if k == "nil":
            return "VNil{}"
        if k == "zero":
            return self.zero(c["type"])
        raise Unsupported(f"a constant of kind {k}")

    def global_cell(self, g: str) -> int:
        if g in self.gcell:
            return self.gcell[g]
        e = next((x for x in self.section["globals"] if x["global"] == g), None)
        if e is None or e.get("kind") == "unaccounted":
            raise Unsupported(f"global {g}")
        if e["kind"] == "native":
            kind = (self.side.get("native_globals") or {}).get(g)
            if kind != "byte_order":
                raise Unsupported(f"native global {g}")
            val, desc = "VOrd{}", "byte_order"
        else:
            t = e.get("value")
            if not (isinstance(t, list) and len(t) == 3 and t[0] == "call" and t[1] == "errors.New"
                    and len(t[2]) == 1 and isinstance(t[2][0], list) and t[2][0][:1] == ["str"]):
                raise Unsupported(f"the initializer of {g}")
            val, desc = f"VE{{{self.template(t[2][0][1], 'literal')}, Nil{{}}}}", t[2][0][1]
        self.gcell[g] = len(self.globals)
        self.globals.append({"global": g, "cell": len(self.globals), "value": desc, "bend": val})
        return self.gcell[g]


class FnGen:
    """One compiled function: its virtual blocks, segments, registers and code."""

    def __init__(self, C: Compiler, fi: FnInfo, index_of: dict):
        self.C, self.fi, self.index_of = C, fi, index_of
        self.is_entry = fi.fid == C.entry
        self.p = fi.p
        raw = fi.raw
        self.blocks = {b["index"]: b for b in raw["blocks"]}
        self.vblocks: dict = {}       # index -> {"instrs", "succs", "preds", "src"}
        if self.is_entry:
            cut = C.cut
            pb, first, bD = cut["entry_block"], cut["first"], cut["boundary_block"]
            gone = set(cut["blocks"]) | {bD}
            for i, b in self.blocks.items():
                if i in gone:
                    continue
                ins = list(b["instrs"])
                succs = list(b.get("succs") or [])
                src = i
                if i == pb:
                    D = self.blocks[bD]["instrs"][0]
                    pl = {"op": "PL", "name": D["name"], "type": D.get("type"), "pos": D.get("pos")}
                    ins = ins[:first] + [pl] + list(self.blocks[bD]["instrs"][1:])
                    succs = list(self.blocks[bD].get("succs") or [])
                    src = bD
                self.vblocks[i] = {"instrs": ins, "succs": succs, "preds": list(b.get("preds") or []), "src": src}
            for i, vb in self.vblocks.items():
                for s in vb["succs"]:
                    if s not in self.vblocks:
                        raise Unsupported(f"block {i} jumps into the cut region")
        else:
            for i, b in self.blocks.items():
                self.vblocks[i] = {"instrs": list(b["instrs"]), "succs": list(b.get("succs") or []),
                                   "preds": list(b.get("preds") or []), "src": i}
        self.loops = loops_of([{"index": i, "succs": vb["succs"], "preds": [p for p in vb["preds"]
                                                                           if p in self.vblocks]}
                               for i, vb in sorted(self.vblocks.items())])
        names = [f"P{k}" for k in range(len(fi.params))]
        for i in sorted(self.vblocks):
            for ins in self.vblocks[i]["instrs"]:
                if ins.get("name"):
                    names.append(ins["name"])
        self.reg = {n: k for k, n in enumerate(names)}
        self.depth = max(1, (len(names) - 1).bit_length())
        self.nonnil = set()
        for i in self.vblocks:
            for ins in self.vblocks[i]["instrs"]:
                if ins.get("op") in ("Alloc", "FieldAddr", "IndexAddr") and ins.get("name"):
                    self.nonnil.add(ins["name"])
        self.T = f"F{fi.idx}T"
        self.K = f"F{fi.idx}K"
        self.defs: list = []

    # ------------------------------------------------------------ helpers
    def path(self, n: str) -> str:
        return bpath(self.reg[n], self.depth)

    def type_of(self, o: dict) -> str:
        if "v" in o:
            return self.fi.types.get(o["v"], "")
        if "param" in o:
            return self.fi.params[o["param"]]["type"]
        if "const" in o:
            return o["const"].get("type") or ""
        if "global" in o:
            return "*" + (next((g.get("type") for g in self.C.section["globals"] if g["global"] == o["global"]),
                               None) or "")
        raise Unsupported(f"the type of operand {o}")

    def is_boundary(self, ins: dict) -> bool:
        op = ins.get("op")
        if op in ("PL", "IndexAddr", "Slice", "MakeSlice"):
            return True
        if op == "FieldAddr":
            return not self.statically_nonnil(ins["operands"][0])
        if op == "UnOp" and ins.get("unop") == "*":
            return not self.statically_nonnil(ins["operands"][0])
        if op == "Store":
            return not self.statically_nonnil(ins["operands"][0])
        if op == "BinOp" and ins.get("binop") == "/":
            y = ins["operands"][1]
            return not ("const" in y and int(y["const"].get("value", "0")) != 0)
        if op == "Call":
            c = ins["call"]
            if c.get("mode") == "builtin":
                return c["callee"] == "append"
            callee = c.get("callee")
            if callee in self.C.raw or callee == self.C.decoder:
                return True
            k = self.C.kinds.get(callee)
            if k == "encoding":
                return True
            if k == "native":
                return self.C.side["natives"].get(callee) not in ("errorf", "errors_new", "slice_len")
            return False
        return False

    def statically_nonnil(self, o: dict) -> bool:
        return ("v" in o and o["v"] in self.nonnil) or "global" in o

    def segments(self, b: int) -> list:
        segs, cur = [], []
        for ins in self.vblocks[b]["instrs"]:
            if ins.get("op") == "Phi":
                continue
            cur.append(ins)
            if self.is_boundary(ins):
                segs.append(cur)
                cur = []
        segs.append(cur)
        return segs

    # ------------------------------------------------------------ code
    def fn_params(self, entry_tail: bool = True) -> str:
        if self.is_entry:
            return ", pl: List<&2, GV> -> PlAns, dt: List<&2, U32> -> DtAns"
        return ""

    def go(self, k: str, h: str, r: str, pl: str = "pl", dt: str = "dt") -> str:
        if self.is_entry:
            return f"{self.T}Go{{{k}, {h}, {r}, {pl}, {dt}}}"
        return f"{self.T}Go{{{k}, {h}, {r}}}"

    def end(self, res: str) -> str:
        return f"{self.T}End{{{res}}}"

    def build(self) -> list:
        C, fi = self.C, self.fi
        all_segs = {b: self.segments(b) for b in sorted(self.vblocks)}
        # where each value is defined (block, segment) and used
        defseg, uses = {}, defaultdict(set)
        for b, segs in all_segs.items():
            for s, seg in enumerate(segs):
                for ins in seg:
                    n = ins.get("name")
                    if n:
                        defseg[n] = (b, s + 1) if self.is_boundary(ins) else (b, s)
                    for o in operands(ins):
                        if "v" in o:
                            uses[o["v"]].add((b, s))
            for ins in self.vblocks[b]["instrs"]:
                if ins.get("op") == "Phi":
                    defseg[ins["name"]] = (b, -1)
        for b, vb in self.vblocks.items():
            for ins in vb["instrs"]:
                if ins.get("op") != "Phi":
                    continue
                for j, o in enumerate(ins["operands"]):
                    if not isinstance(o, dict) or "v" not in o:
                        continue
                    pred = self.blocks[vb["src"]]["preds"][j] if vb["src"] == b else vb["preds"][j]
                    pv = self.virtual_of(pred)
                    if pv is None:
                        continue
                    uses[o["v"]].add((pv, len(all_segs[pv]) - 1))
        self.store = {n for n, ds in defseg.items() if ds[1] >= 0 and any(u != ds for u in uses.get(n, ()))}
        self.all_segs = all_segs
        defs = []
        for b in sorted(self.vblocks, reverse=True):
            segs = all_segs[b]
            for s in range(len(segs) - 1, -1, -1):
                defs.append(self.segment(b, s, segs[s], segs[s - 1][-1] if s > 0 else None))
        return defs

    def virtual_of(self, pred: int):
        if pred in self.vblocks:
            return pred
        if self.is_entry and pred == self.C.cut["boundary_block"]:
            return self.C.cut["entry_block"]
        return None

    def seg_name(self, b: int, s: int) -> str:
        return f"{self.p}_b{b}" if s == 0 else f"{self.p}_b{b}_s{s}"

    def segment(self, b: int, s: int, seg: list, bound) -> str:
        """One segment's def (s = 0: the block's start; else the continuation of the boundary `bound`)."""
        self.locals = set()
        self.lines = []
        self.hv = "h0"
        self.pl, self.dt = "pl", "dt"
        ret = self.T
        if s == 0:
            head = f"def {self.seg_name(b, s)}(+h0: List<&2, GV>, +r: RT{self.fn_params()}) -> {ret}:"
            ind = "  "
        else:
            bn = bound.get("name")
            vpat = f"+v_{bn}" if bn else "vx_"
            head = f"def {self.seg_name(b, s)}(e: Eff, +r: RT{self.fn_params()}) -> {ret}:"
            if bn:
                self.locals.add(bn)
            ind = "      "
        body = self.seg_body(b, s, seg)
        out = [head]
        if s == 0:
            out += ["  " + ln for ln in body]
        else:
            out += ["  match e:", f"    case EOk{{+h0, {vpat}}}:"] + ["      " + ln for ln in body]
            out += ["    case EPan{h0, x0}:", f"      {self.end('Res{OPan{x0}, h0}')}",
                    "    case ERet{h0, x0}:", f"      {self.end('Res{ORet{x0}, h0}')}",
                    "    case EFuel{h0}:", f"      {self.end('Res{OFuel{}, h0}')}"]
        return "\n".join(out) + "\n"

    def val(self, o) -> str:
        if o is None:
            raise Unsupported("a missing operand")
        if "v" in o:
            n = o["v"]
            if n in self.locals:
                return f"v_{n}"
            if n not in self.reg:
                raise Unsupported(f"value {n} has no register")
            return f"rget({self.path(n)}, r)"
        if "param" in o:
            return f"rget({self.path('P' + str(o['param']))}, r)"
        if "const" in o:
            return self.C.const(o["const"])
        if "global" in o:
            return f"VP{{{self.C.global_cell(o['global'])}n, Nil{{}}}}"
        raise Unsupported(f"operand {o}")

    def let(self, name, expr: str) -> None:
        if name:
            self.lines.append(f"+v_{name} = {{{expr} : GV}}")
            self.locals.add(name)

    def heap(self, expr: str) -> None:
        k = int(self.hv[1:]) + 1
        nv = f"h{k}"
        self.lines.append(f"+{nv} = {{{expr} : List<&2, GV>}}")
        self.hv = nv

    def r_out(self, seg_names: list) -> str:
        r = "r"
        for n in seg_names:
            if n in self.store and n in self.locals:
                r = f"rset({self.path(n)}, {r}, v_{n})"
        return r

    def seg_body(self, b: int, s: int, seg: list) -> list:
        defined = [ins["name"] for ins in seg if ins.get("name")]
        if s > 0:
            pass
        for k, ins in enumerate(seg):
            last = k == len(seg) - 1
            if last and self.is_boundary(ins):
                eff = self.eff(ins, b)
                defined_here = [n for n in self.locals]
                nxt = self.seg_name(b, s + 1)
                r = self.r_out(sorted(self.locals, key=lambda n: self.reg[n]))
                extra = f", {self.pl}, {self.dt}" if self.is_entry else ""
                self.lines.append(f"{nxt}({eff}, {r}{extra})")
                return self.lines
            op = ins.get("op")
            if op in ("If", "Jump", "Return"):
                self.terminator(b, ins)
                return self.lines
            self.plain(ins)
        raise Unsupported(f"block {b} of {self.fi.fid} has no terminator")

    # ------------------------------------------------------------ instructions (no boundary)
    def plain(self, ins: dict) -> None:
        op, n = ins.get("op"), ins.get("name")
        ops = ins.get("operands") or []
        if op == "Alloc":
            t = self.C.ty.pointee(ins["type"])
            self.lines.append(f"+v_{n} = {{VP{{hlen({self.hv}), Nil{{}}}} : GV}}")
            self.locals.add(n)
            self.heap(f"hpush({self.hv}, {self.C.zero(t)})")
            return
        if op == "BinOp":
            self.let(n, self.binop(ins))
            return
        if op == "UnOp":
            u = ins.get("unop")
            x = self.val(ops[0])
            if u == "*":
                self.let(n, f"hload({self.hv}, {x})")
                return
            if u == "!":
                self.let(n, f"VB{{Bool.not(gbool({x}))}}")
                return
            if u == "-":
                info = self.C.int_info(ins.get("type") or "")
                if info is None:
                    raise Unsupported("unary minus of a non-integer")
                self.let(n, f"nk_{int_kind(info)}(i_sub(VI{{0, 0}}, {x}))")
                return
            raise Unsupported(f"unop {u}")
        if op == "FieldAddr":
            self.let(n, f"g_faddr({self.val(ops[0])}, {int(ins['field'])}n)")
            return
        if op == "Store":
            self.heap(f"hstore({self.hv}, {self.val(ops[0])}, {self.val(ops[1])})")
            return
        if op == "Call":
            self.let(n, self.call_plain(ins))
            return
        if op == "Convert":
            src, dst = self.type_of(ops[0]), ins.get("type") or ""
            si, di = self.C.int_info(src), self.C.int_info(dst)
            if si is None or di is None:
                raise Unsupported(f"Convert {src} -> {dst}")
            self.let(n, f"nk_{int_kind(di)}({self.val(ops[0])})")
            return
        if op in ("ChangeType", "ChangeInterface"):
            self.let(n, self.val(ops[0]))
            return
        if op == "MakeInterface":
            self.let(n, f"VF{{{self.C.tid(self.type_of(ops[0]))}, {self.val(ops[0])}}}")
            return
        if op == "Extract":
            self.let(n, f"g_extract({self.val(ops[0])}, {int(ins['index'])}n)")
            return
        raise Unsupported(f"op {op}")

    def binop(self, ins: dict) -> str:
        o = ins["binop"]
        a, b = ins["operands"]
        x, y = self.val(a), self.val(b)
        ta = self.type_of(a)
        if o in ("+", "-", "*"):
            info = self.C.int_info(ins.get("type") or "")
            if info is None:
                raise Unsupported(f"binop {o} on {ins.get('type')}")
            fn = {"+": "i_add", "-": "i_sub", "*": "i_mul"}[o]
            return f"nk_{int_kind(info)}({fn}({x}, {y}))"
        if o == "/":
            info = self.C.int_info(ins.get("type") or "")
            if info is None or not info[1] or info[0] != 64:
                raise Unsupported(f"division on {ins.get('type')}")
            return f"i_udiv({x}, {y})"
        if o in ("<", "<=", ">", ">="):
            info = self.C.int_info(ta)
            if info is None:
                raise Unsupported(f"ordering of {ta}")
            lt = "i_ult" if info[1] else "i_slt"
            return {"<": f"VB{{{lt}({x}, {y})}}", ">": f"VB{{{lt}({y}, {x})}}",
                    "<=": f"VB{{Bool.not({lt}({y}, {x}))}}", ">=": f"VB{{Bool.not({lt}({x}, {y}))}}"}[o]
        if o in ("==", "!="):
            k = self.C.kind(ta) if ta else ""
            if self.C.int_info(ta) is not None or (k == "basic" and self.C.ty.entry(ta).get("boolean")):
                e = f"g_eq({x}, {y})"
            elif k in ("pointer", "interface", "slice", "map", "chan", "signature"):
                if "const" in b and b["const"].get("kind") == "nil":
                    e = f"is_nil({x})"
                elif "const" in a and a["const"].get("kind") == "nil":
                    e = f"is_nil({y})"
                else:
                    raise Unsupported(f"comparison of two {k} values")
            else:
                raise Unsupported(f"comparison of {ta}")
            return f"VB{{{e}}}" if o == "==" else f"VB{{Bool.not({e})}}"
        raise Unsupported(f"binop {o}")

    def call_plain(self, ins: dict) -> str:
        c = ins["call"]
        args = c.get("args") or []
        if c.get("mode") == "builtin":
            if c["callee"] == "len":
                return f"g_len({self.hv}, {self.val(args[0])})"
            raise Unsupported(f"builtin {c['callee']}")
        callee = c.get("callee")
        k = self.C.kinds.get(callee)
        nk = self.C.side["natives"].get(callee) if k == "native" else None
        if k == "slice_len" or nk == "slice_len":
            return f"g_len({self.hv}, {self.val(args[0])})"
        if nk == "errorf":
            f, a = args
            if "const" not in f or f["const"].get("kind") != "string":
                raise Unsupported("fmt.Errorf with a format that is not a constant")
            fmt = f["const"]["value"]
            if "%w" in fmt or re.search(r"%[^vdxs%]", fmt):
                raise Unsupported(f"the format {fmt!r}")
            t = self.C.template(fmt, "format")
            return f"VE{{{t}, g_elems({self.hv}, {self.val(a)})}}"
        if nk == "errors_new":
            f = args[0]
            if "const" not in f or f["const"].get("kind") != "string":
                raise Unsupported("errors.New of a text that is not a constant")
            return f"VE{{{self.C.template(f['const']['value'], 'literal')}, Nil{{}}}}"
        raise Unsupported(f"a call of {callee} ({k})")

    # ------------------------------------------------------------ boundaries
    def in_loop(self, b: int) -> bool:
        return any(b in lp for lp in self.loops)

    def eff(self, ins: dict, b: int) -> str:
        op = ins.get("op")
        ops = ins.get("operands") or []
        h = self.hv
        tint = self.C.tid("int")
        if op == "PL":
            if not self.is_entry or self.in_loop(b) or "pl" in self.C.consumed:
                raise Unsupported("the blob layer applied twice or in a loop")
            self.C.consumed.add("pl")
            ptr = self.val({"v": self.C.cut["_input"]})
            if self.C.cut["_input"] not in self.nonnil:
                raise Unsupported("the blob layer's input is not a non-nil pointer")
            for k in self.C.cut["_input_path"]:
                ptr = f"g_faddr({ptr}, {k}n)"
            self.pl = "pl_spent"
            return f"e_pl(pl, {h}, hload({h}, {ptr}))"
        if op == "FieldAddr":
            return f"e_faddr({h}, {self.val(ops[0])}, {int(ins['field'])}n)"
        if op == "UnOp":
            return f"e_load({h}, {self.val(ops[0])})"
        if op == "Store":
            return f"e_store({h}, {self.val(ops[0])}, {self.val(ops[1])})"
        if op == "IndexAddr":
            ti = self.type_of(ops[1])
            info = self.C.int_info(ti)
            if info is None:
                raise Unsupported(f"an index of type {ti}")
            sg = "False{}" if info[1] else "True{}"
            return f"e_iaddr({h}, {self.val(ops[0])}, {self.val(ops[1])}, {sg}, {self.C.tid(ti)}, {tint})"
        if op == "Slice":
            x, lo, hi = ops[0], ops[1], ops[2]
            mx = ops[3] if len(ops) > 3 else None

            def bound(o):
                if o is None:
                    return "VI{0, 0}", "False{}", tint
                t = self.type_of(o)
                info = self.C.int_info(t)
                if info is None:
                    raise Unsupported(f"a slice bound of type {t}")
                return self.val(o), ("False{}" if info[1] else "True{}"), self.C.tid(t)
            vl, sl, tl = bound(lo)
            vh, sh, th = bound(hi)
            if mx is not None:
                if hi is None:
                    raise Unsupported("a three-index slice without its middle index")
                vm, sm, tm = bound(mx)
                return (f"e_slice3({h}, {self.val(x)}, {vl}, {vh}, {vm}, {sl}, {sh}, {sm}, {tl}, {th}, {tm}, "
                        f"{tint})")
            hashi = "False{}" if hi is None else "True{}"
            return f"e_slice2({h}, {self.val(x)}, {hashi}, {vl}, {vh}, {sl}, {sh}, {tl}, {th}, {tint})"
        if op == "MakeSlice":
            n, cap = ops
            el = self.C.ty.entry(ins["type"])["elem"]
            by = "True{}" if self.C.ty.is_byte(el) else "False{}"
            ln_t, cp_t = self.type_of(n), self.type_of(cap)
            li, ci = self.C.int_info(ln_t), self.C.int_info(cp_t)
            if li is None or ci is None:
                raise Unsupported("makeslice of non-integer sizes")
            vn, vc = self.val(n), self.val(cap)
            neg = f"i_neg({vn})" if not li[1] else "False{}"
            lt = "i_ult" if (li[1] and ci[1]) else "i_slt"
            return (f"e_makeslice({neg}, {lt}({vc}, {vn}), big_cap({vc}), {by}, {h}, {vn}, {vc}, "
                    f"{self.C.zero(el)})")
        if op == "BinOp":
            return f"e_udiv({h}, {self.val(ops[0])}, {self.val(ops[1])})"
        if op == "Call":
            return self.call_eff(ins, b)
        raise Unsupported(f"a boundary {op}")

    def call_eff(self, ins: dict, b: int) -> str:
        c = ins["call"]
        args = c.get("args") or []
        h = self.hv
        if c.get("mode") == "builtin":
            if c["callee"] == "append":
                el = self.C.ty.entry(ins["type"])["elem"]
                by = "True{}" if self.C.ty.is_byte(el) else "False{}"
                if len(args) != 2:
                    raise Unsupported("append of other than one spread argument")
                return f"e_append({by}, {h}, {self.val(args[0])}, {self.val(args[1])})"
            raise Unsupported(f"builtin {c['callee']}")
        if c.get("mode") != "static":
            raise Unsupported(f"a call of mode {c.get('mode')}")
        callee = c["callee"]
        if callee in self.C.raw:
            if callee not in self.index_of:
                raise Unsupported(f"a call of {callee} outside the compiled closure")
            j = self.index_of[callee]
            a = "".join(f", {self.val(x)}" for x in args)
            return f"res_eff(f{j}_call({h}{a}))"
        if callee == self.C.decoder:
            if not self.is_entry or self.in_loop(b) or "dt" in self.C.consumed:
                raise Unsupported("the decoder called outside the entry, twice or in a loop")
            self.C.consumed.add("dt")
            self.dt = "dt_spent"
            return f"e_dt(dt, {h}, {self.val(args[0])})"
        k = self.C.kinds.get(callee)
        if k == "encoding":
            return f"e_marshal({h}, {self.val(args[0])})"
        if k != "native":
            raise Unsupported(f"a call of {callee} ({k})")
        nk = self.C.side["natives"].get(callee)
        tint = self.C.tid("int")
        if nk == "be_uint":
            info = self.C.int_info(ins.get("type") or "")
            if info is None or not info[1]:
                raise Unsupported(f"{callee} with result {ins.get('type')}")
            self.require_big_endian(args[0])
            return f"e_be_uint({h}, {self.val(args[1])}, {info[0] // 8}, {tint})"
        if nk == "bytes_reader":
            return f"e_reader({h}, {self.val(args[0])})"
        if nk == "binary_read":
            r, order, data = args
            self.require_big_endian(order)
            pt = self.made_from(data)
            el = self.C.ty.pointee(pt)
            info = self.C.int_info(el) if self.C.kind(el) == "basic" else None
            if info is not None and info[1]:
                return f"e_bread(False{{}}, {h}, {self.val(r)}, {self.val(data)}, {info[0] // 8})"
            if self.C.kind(el) == "slice" and self.C.ty.is_byte(self.C.ty.entry(el)["elem"]):
                return f"e_bread(True{{}}, {h}, {self.val(r)}, {self.val(data)}, 0)"
            raise Unsupported(f"encoding/binary.Read into {pt}")
        if nk == "big_setbytes":
            return f"e_setbytes({h}, {self.val(args[0])}, {self.val(args[1])})"
        if nk == "big_cmp":
            return f"e_bigcmp({h}, {self.val(args[0])}, {self.val(args[1])})"
        if nk == "big_newint":
            a = args[0]
            if "const" not in a or a["const"].get("kind") != "int" or int(a["const"]["value"]) < 0:
                raise Unsupported("math/big.NewInt of other than a non-negative constant")
            v = int(a["const"]["value"])
            mag = [] if v == 0 else list(v.to_bytes((v.bit_length() + 7) // 8, "big"))
            return f"e_newbig({h}, [{', '.join(str(x) for x in mag)}])" if mag else f"e_newbig({h}, Nil{{}})"
        raise Unsupported(f"native {callee} ({nk})")

    def def_of(self, name: str):
        for vb in self.vblocks.values():
            for ins in vb["instrs"]:
                if ins.get("name") == name:
                    return ins
        return None

    def made_from(self, o: dict) -> str:
        """The static type of the value an interface operand was made from (its MakeInterface's operand)."""
        d = self.def_of(o["v"]) if "v" in o else None
        if d is None or d.get("op") != "MakeInterface":
            raise Unsupported("an interface argument not made in the same function")
        return self.type_of(d["operands"][0])

    def require_big_endian(self, o: dict) -> None:
        d = self.def_of(o["v"]) if "v" in o else None
        while d is not None and d.get("op") in ("MakeInterface", "ChangeType", "ChangeInterface"):
            x = d["operands"][0]
            d = self.def_of(x["v"]) if "v" in x else None
        if not (d and d.get("op") == "UnOp" and d.get("unop") == "*" and "global" in d["operands"][0]
                and (self.C.side.get("native_globals") or {}).get(d["operands"][0]["global"]) == "byte_order"):
            raise Unsupported("a byte order that is not the native byte-order global")

    # ------------------------------------------------------------ terminators
    def phi_r(self, src_block: int, dst: int, r: str) -> tuple:
        """(lets, register expression) after the edge from virtual block src_block to dst."""
        vb = self.vblocks[dst]
        orig = self.vblocks[src_block]["src"]
        lets, sets = [], []
        for ins in vb["instrs"]:
            if ins.get("op") != "Phi":
                continue
            preds = self.blocks[dst]["preds"]
            if orig not in preds:
                raise Unsupported(f"block {dst}'s phi has no edge from {orig}")
            o = ins["operands"][preds.index(orig)]
            nm = f"q_{ins['name']}_{src_block}"
            lets.append(f"+{nm} = {{{self.val(o)} : GV}}")
            sets.append((ins["name"], nm))
        for n, nm in sets:
            r = f"rset({self.path(n)}, {r}, {nm})"
        return lets, r

    def terminator(self, b: int, ins: dict) -> None:
        op = ins["op"]
        base = self.r_out(sorted(self.locals, key=lambda n: self.reg[n]))
        if op == "Return":
            vs = [self.val(o) for o in ins.get("operands") or []]
            v = "VNil{}" if not vs else (vs[0] if len(vs) == 1 else "VT{[" + ", ".join(vs) + "]}")
            self.lines.append(self.end(f"Res{{ORet{{{v}}}, {self.hv}}}"))
            return
        succs = self.vblocks[b]["succs"]
        if op == "Jump":
            lets, r = self.phi_r(b, succs[0], base)
            self.lines += lets
            self.lines.append(self.go(f"{self.K}{succs[0]}{{}}", self.hv, r, self.pl, self.dt))
            return
        c = self.val(ins["operands"][0])
        lt, rt = self.phi_r(b, succs[0], base)
        le, re_ = self.phi_r(b, succs[1], base)
        self.lines += lt + le
        br = f"{self.p}_br{b}"
        extra = f", {self.pl}, {self.dt}" if self.is_entry else ""
        self.lines.append(f"{br}(gbool({c}), {self.hv}, {rt}, {re_}{extra})")
        sig = self.fn_params()
        self.branch_defs.append(
            f"def {br}(c: Bool, +h: List<&2, GV>, +rt: RT, +re: RT{sig}) -> {self.T}:\n"
            f"  match c:\n    case True{{}}:\n      {self.go(f'{self.K}{succs[0]}{{}}', 'h', 'rt')}\n"
            f"    case False{{}}:\n      {self.go(f'{self.K}{succs[1]}{{}}', 'h', 're')}\n")

    # ------------------------------------------------------------ the function
    def code(self) -> str:
        self.branch_defs = []
        segs = self.build()
        ks = sorted(self.vblocks)
        tkind = "Type" if self.is_entry else "Data"
        sig = self.fn_params()
        ex = ", pl: List<&2, GV> -> PlAns, dt: List<&2, U32> -> DtAns" if self.is_entry else ""
        exu = ", pl, dt" if self.is_entry else ""
        lines = [f"# ---------------------------------------------------------------- {self.fi.fid}",
                 f"type {self.K} is Data:"] + [f"  {self.K}{k}{{}}" for k in ks] + [""]
        lines += [f"type {self.T} is {tkind}:",
                  f"  {self.T}Go{{k: {self.K}, h: List<&2, GV>, r: RT{ex.replace(', pl:', ', pl:').replace(' -> ', ' -> ')}}}",
                  f"  {self.T}End{{x: Res}}", ""]
        out = "\n".join(lines) + "\n" + "\n".join(self.branch_defs) + "\n" + "\n".join(segs)
        disp = [f"def {self.p}_step(k: {self.K}, +h: List<&2, GV>, +r: RT{sig}) -> {self.T}:", "  match k:"]
        for k in ks:
            disp += [f"    case {self.K}{k}{{}}:", f"      {self.p}_b{k}(h, r{exu})"]
        go_pat = f"{self.T}Go{{k, h, r{exu}}}"
        run = [f"def {self.p}_out(t: {self.T}) -> Res:", "  match t:",
               f"    case {go_pat}:", "      Res{OFuel{}, h}", f"    case {self.T}End{{x}}:", "      x", "",
               f"def {self.p}_run(fuel: Nat, t: {self.T}) -> Res:", "  match fuel:", "    case 0n:",
               f"      {self.p}_out(t)", "    case 1n+p:", "      match t:", f"        case {self.T}End{{x}}:",
               "          x", f"        case {go_pat}:", f"          {self.p}_run(p, {self.p}_step(k, h, r{exu}))"]
        nparams = len(self.fi.params)
        rinit = "RE{}"
        for i in range(nparams - 1, -1, -1):
            rinit = f"rset({self.path('P' + str(i))}, {rinit}, a{i})"
        ps = "".join(f", +a{i}: GV" for i in range(nparams))
        call = [f"def {self.p}_call({'pl: List<&2, GV> -> PlAns, dt: List<&2, U32> -> DtAns, ' if self.is_entry else ''}"
                f"+h: List<&2, GV>{ps}) -> Res:",
                f"  {self.p}_run(U32.to_nat({self.C.fuel}), {self.go(f'{self.K}{ks[0]}{{}}', 'h', rinit)})"]
        return out + "\n" + "\n".join(disp) + "\n\n" + "\n".join(run) + "\n\n" + "\n".join(call) + "\n"


def generate(section: dict, side: dict) -> tuple:
    """(model text, info) of the consumer's Bend model; raises Unsupported."""
    cut = blob_cut(section, side)
    C = Compiler(section, side, cut)
    order = C.order()
    index_of = {f: i for i, f in enumerate(order)}
    bodies = []
    for f in order:
        fg = FnGen(C, FnInfo(f, index_of[f], C.raw[f]), index_of)
        bodies.append(fg.code())
    if C.consumed != {"pl", "dt"}:
        raise Unsupported(f"the model applies {sorted(C.consumed)} of the parameters pl and dt")
    t = {f"t_{k}": RT_ID[k] for k, _x in RUNTIME_TEMPLATES}
    t.update({"t_eof": C.t_eof, "t_ueof": C.t_ueof})
    prelude = (PRELUDE + PRELUDE2 + PRELUDE3).format(
        gv_ctors="\n".join(f"  {n}{{{f}}}" for n, f in GV_CTORS), **t)
    ei = index_of[C.entry]
    gl = "[" + ", ".join(g["bend"] for g in C.globals) + "]" if C.globals else "Nil{}"
    recv_t = C.ty.pointee(C.raw[C.entry]["params"][0]["type"])
    tail = [
        "# ---------------------------------------------------------------- the entry",
        f"def globals_cells() -> List<&2, GV>:\n  {gl}\n",
        f"def nglobals() -> Nat:\n  {len(C.globals)}n\n",
        f"def zero_recv() -> GV:\n  {C.zero(recv_t)}\n",
        "# the consumer's entry on the heap globals_cells() ++ cells, its receiver recv (a pointer) and its batch",
        "def consumer_run(pl: List<&2, GV> -> PlAns, dt: List<&2, U32> -> DtAns, +cells: List<&2, GV>, +recv: GV, "
        "+batch: GV) -> Res:",
        f"  f{ei}_call(pl, dt, List.append(&2, GV, globals_cells(), cells), recv, batch)",
    ]
    header = ("# GENERATED by holon.derivation.bendgen from the consumer section of a Go document and a sidecar; "
              "do not edit.\n")
    text = header + prelude + "\n" + "\n".join(bodies) + "\n" + "\n".join(tail) + "\n"
    info = {"cut": public_cut(cut), "functions": sorted(order), "order": order, "templates": C.templates,
            "type_ids": {str(v): k for k, v in sorted(C.tids.items(), key=lambda kv: kv[1])},
            "globals": [{k: g[k] for k in ("global", "cell", "value")} for g in C.globals], "fuel": C.fuel}
    return text, info, C
