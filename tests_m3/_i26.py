"""I26 instrument, fixed at the I26 prereg: rules F1-F9 of tests_m3/test_fact.py written out a second time, independently
of holon/, the back-test move (FB2) and the raw-call replay on the REAL Rollup.

  analyse(path, sidecar)     the FACT analysis of a transitions document (F1-F9): commitments, kernel basis, attribution
                             consumers, pins, writers of the pinned families, attribution basis, law ids, fact ids,
                             premises (without the hash-binder premises, which test_fact adds from I30's laws) and the
                             measure F(m, c) of every kernel basis element (F9: fibers over the representative domain)
  fact_basis_doc(root)       the content of spec/M3/lib/fact_basis.json (its doc field aside), from the committed inputs
  move_kernel_witness(w, mv) the M1 inputs (p, c1, c2) a kernel witness moves to under the frozen map (FB2)
  agg_m1(xs)                 the M1 model's version-2 blob hash (gen/M1/model/morph_rollup.bend d_blob_hash at version
                             2: 1000 + b_enc(xs)), for the CF(agg, S) bridge (FB3)
  realized(traces, slots)    each trace on the REAL Rollup at the pinned commit, deployed as the I20 binding deploys it,
                             through byte copies of the I20 step harness taken at this prereg (tests_m3/fixtures/fact/
                             harness/): per trace {"harness": the test contract's address (the Rollup's owner), "steps":
                             [{"status": "ok" | "revert", "ret", "logs": [{"topics", "data"}], "calls": [{"to", "data",
                             "ok", "ret"}], "slots": {slot: int}}]}; slots read with vm.load after each step
  o25_chain(...), z_pair(..) the hand-built traces of the instrument check (test_fact.TestInstrument): the O25 chain (S1
                             commits, the owner reverts, S2 recommits the pinned content, a challenge, a timed-out proof)
                             and the no-blob / zero-blob pair

The toolchain is pinned (config/holon.json replay: forge, solc, the dependency tree; I15's check): a missing or
different tool is a failure, never a skip. Nothing here imports holon/.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from tests_m2 import _i15 as I15
from tests_m2._i16 import morph_checkout
from tests_m2._keccak import keccak256
from tests_m3._m3 import ROOT, load_json

HASHES = ("keccak256", "sha256")
OPS = {"?", "==", "!=", "!", "||", "&&", "<", "<=", ">", ">=", "+", "-", "*"}
SCAN = ("guards", "checks", "panics", "calls", "writes", "events", "mstores", "loops")
NOT_STATE = ("view", "pure")
W256 = 1 << 256
HARNESS_DIR = ROOT / "tests_m3" / "fixtures" / "fact" / "harness"
# byte copies of replay/M2/solidity/HolonStepBase.sol, replay/M1/solidity/HolonTraceReplay.t.sol and
# replay/M2/solidity/HolonExtractedStep.t.sol at the I26 prereg (the same bytes I27's and I31's fixtures copied)
HARNESS = {"HolonStepBase.sol": "d6b490fad4b5da0ae4438c32be6dab6a3e301eff1a06b7b111b470a6874f6334",
           "HolonTraceReplay.t.sol": "3e651a254861603f30c9614ee85ccaa85b6b012d3c2bf88e2aa8813b26959853",
           "HolonExtractedStep.t.sol": "8a4e31d7cc0cfd7b86db08c71e7ad27c618ec75808b67afa1fc8eecfbfa8a5da"}
EPOCH = 1_700_000_000           # the binding's clock origin (replay/M1/solidity/HolonTraceReplay.t.sol EPOCH)
STANDIN_SUBMITTERS = ("0x0000000000000000000000000000000000001002", "0x0000000000000000000000000000000000001003")
CHALLENGER = "0x0000000000000000000000000000000000001004"


# ------------------------------------------------------------------ JSON and terms
def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ck(obj) -> str:
    return canonical(obj).decode("utf-8")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def is_op(t, op=None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def conjuncts(e) -> list:
    if is_op(e, "&&"):
        out = []
        for x in e[1:]:
            out += conjuncts(x)
        return out
    return [e]


def holds_head(t, head: str) -> bool:
    if isinstance(t, list):
        if t and t[0] == head:
            return True
        return any(holds_head(x, head) for x in t)
    if isinstance(t, dict):
        return any(holds_head(v, head) for v in t.values())
    return False


def word_hex(n: int) -> str:
    return "0x" + (n % W256).to_bytes(32, "big").hex()


def admissible(n: int) -> bool:
    """A blob versioned hash an EIP-4844 transaction may carry: nonzero, version byte 0x01 (premise blobs_wf)."""
    return is_int(n) and 0 < n < W256 and (n >> 248) == 0x01


# ------------------------------------------------------------------ the document
class Doc:
    def __init__(self, path: Path, rel: str | None = None):
        self.path = Path(path)
        self.rel = rel or str(self.path)
        self.d = load_json(self.path)
        self.contract = self.d["contract"]
        self.model = self.path.name[:-len(".json")] if self.path.name.endswith(".json") else self.path.name
        self.fams = {f["name"]: f for f in self.d["storage"] + self.d.get("inherited_storage", [])}
        self.actions = self.d["actions"]
        self.by = {a["name"]: a for a in self.actions}
        self.constants = {k: int(v, 16) if isinstance(v, str) else int(v) for k, v in (self.d.get("constants") or {}).items()}


def wkey(w: dict):
    """(key term or None, whole): a write's key (["map", k] first path element) and whether it writes a whole register."""
    path = w["path"]
    if not path:
        return None, True
    if is_op(path[0], "map"):
        return path[0][1], len(path) == 1
    return None, False


def final(a: dict, i: int) -> bool:
    w = a["writes"][i]
    k, _ = wkey(w)
    for w2 in a["writes"]:
        if w2 is w or w2["family"] != w["family"] or w2["seq"] <= w["seq"]:
            continue
        k2, whole2 = wkey(w2)
        if whole2 and ck(k2) == ck(k):
            return False
    return True


def reaches(a: dict) -> list:
    return [(gi, ri, r) for gi, g in enumerate(a["guards"]) for ri, r in enumerate(g["reaches"])]


def authenticating(a: dict, F: str) -> list:
    """(guard index, reach index, seq, key) of every guard reach of a with a top-level conjunct ["==", R, H] or
    ["==", H, R], R = ["map", ["storage", F], k], H a keccak256 or sha256 term (F1)."""
    out = []
    for gi, ri, r in reaches(a):
        for c in conjuncts(r["expr"]):
            if is_op(c, "==") and len(c) == 3:
                for R, H in ((c[1], c[2]), (c[2], c[1])):
                    if (is_op(R, "map") and len(R) == 3 and R[1] == ["storage", F] and is_op(H) and H[0] in HASHES):
                        out.append((gi, ri, r["seq"], R[2]))
                        break
    return out


def commitment_writes(doc: Doc, F: str) -> list:
    """(action, i) of every final, whole, keyed, unconditional (cond 1) write of F in a non-view action whose value's head
    is keccak256 or sha256 (F2)."""
    out = []
    for a in doc.actions:
        if a["mutability"] in NOT_STATE:
            continue
        for i, w in enumerate(a["writes"]):
            k, whole = wkey(w)
            if (w["family"] == F and w["cond"] == 1 and whole and k is not None and is_op(w["value"])
                    and w["value"][0] in HASHES and final(a, i)):
                out.append((a["name"], i))
    return out


def commitments(doc: Doc) -> list:
    """F1/F2."""
    out = []
    for F in sorted(doc.fams):
        if doc.fams[F].get("kind") != "mapping":
            continue
        sites = commitment_writes(doc, F)
        auth = [(a["name"], gi) for a in doc.actions for gi, _, _, _ in authenticating(a, F)]
        if sites and auth:
            out.append({"family": F,
                        "sites": sorted(({"action": n, "at": f"writes[{i}]", "key": wkey(doc.by[n]["writes"][i])[0]}
                                         for n, i in sites), key=lambda x: (x["action"], x["at"])),
                        "authenticated_by": sorted(({"action": n, "at": f"guards[{gi}]"}
                                                    for n, gi in sorted(set(auth))),
                                                   key=lambda x: (x["action"], x["at"]))})
    return out


def reads_blobs(a: dict) -> bool:
    """F3: some record of a holds a ["blobhash", i] term."""
    return any(holds_head(a.get(sec) or [], "blobhash") for sec in SCAN)


def kernel_basis(doc: Doc, comms: list) -> list:
    out = []
    for c in comms:
        for s in c["sites"]:
            if reads_blobs(doc.by[s["action"]]):
                out.append({"action": s["action"], "at": s["at"], "commitment": c["family"], "consumer": "blobhash"})
    return sorted(out, key=lambda x: (x["action"], x["commitment"]))


def attribution_consumers(doc: Doc, comms: list) -> list:
    """F5: an argument of an external call that is exactly ["member", ["map", ["storage", A], k], m], in an action with
    an authenticating guard reach of a commitment F at the syntactically same key k before the call (smaller seq)."""
    out = []
    for a in doc.actions:
        for ci, c in enumerate(a["calls"]):
            for arg in c.get("args") or []:
                if not (is_op(arg, "member") and len(arg) == 3 and is_op(arg[1], "map") and len(arg[1]) == 3
                        and is_op(arg[1][1], "storage") and len(arg[1][1]) == 2):
                    continue
                A, k, m = arg[1][1][1], arg[1][2], arg[2]
                for cm in comms:
                    if any(seq < c["seq"] and ck(key) == ck(k) for _, _, seq, key in authenticating(a, cm["family"])):
                        out.append({"family": A, "member": m, "commitment": cm["family"], "action": a["name"],
                                    "at": f"calls[{ci}]", "fn": c["fn"]})
    uniq = {ck(x): x for x in out}
    return sorted(uniq.values(), key=lambda x: (x["family"], x["member"], x["action"], x["at"]))


def copy_in(v, C) -> bool:
    if v == C:
        return True
    if is_op(v, "?") and len(v) == 4:
        return copy_in(v[2], C) or copy_in(v[3], C)
    return False


def pins(doc: Doc, comms: list) -> list:
    """F6: a final, whole, unconditional write of a family P (not the commitment) by a commitment site's action, at the
    syntactically same key as that site, whose value is the copy C = ["map", ["storage", P], key] ("copy") or a ? term
    with C among its branches, at any depth ("branch")."""
    out = []
    for c in comms:
        for s in c["sites"]:
            a = doc.by[s["action"]]
            for j, w in enumerate(a["writes"]):
                k, whole = wkey(w)
                if (w["family"] == c["family"] or w["cond"] != 1 or not whole or ck(k) != ck(s["key"])
                        or not final(a, j)):
                    continue
                C = ["map", ["storage", w["family"]], k]
                if copy_in(w["value"], C):
                    out.append({"action": a["name"], "at": f"writes[{j}]", "family": w["family"],
                                "how": "copy" if w["value"] == C else "branch", "commitment": c["family"]})
    return sorted(out, key=lambda x: (x["family"], x["action"], x["at"]))


def writer_kind(w: dict) -> str:
    k, _ = wkey(w)
    C = ["map", ["storage", w["family"]], k]
    if w["value"] == C:
        return "copy"
    if copy_in(w["value"], C):
        return "branch"
    if w["value"] == 0:
        return "clear"
    return "fresh"


def writers(doc: Doc, families: list) -> dict:
    """Every whole write of each pinned family, classified (A4's ghost step)."""
    out = {}
    for P in families:
        rows = []
        for a in doc.actions:
            for i, w in enumerate(a["writes"]):
                if w["family"] == P and wkey(w)[1]:
                    rows.append({"action": a["name"], "at": f"writes[{i}]", "kind": writer_kind(w)})
        out[P] = sorted(rows, key=lambda x: (x["action"], x["at"]))
    return out


def recorded_member(a: dict, A: str, m: str, key):
    """The value w records for A[key].m: the member of a final whole struct write of A at key, or a member write."""
    for i, w in enumerate(a["writes"]):
        k, whole = wkey(w)
        if w["family"] != A or ck(k) != ck(key) or not final(a, i) or w["cond"] != 1:
            continue
        if whole and is_op(w["value"], "struct"):
            for mm, v in w["value"][2]:
                if mm == m:
                    return v
        if len(w["path"]) == 2 and w["path"][1] == ["member", m]:
            return w["value"]
    return None


def attribution_basis(doc: Doc, comms: list, ps: list, cons: list) -> list:
    """F7."""
    out = []
    site_key = {(s["action"], c["family"]): s["key"] for c in comms for s in c["sites"]}
    for p in ps:
        for cn in cons:
            if cn["commitment"] != p["commitment"]:
                continue
            key = site_key[(p["action"], p["commitment"])]
            v = recorded_member(doc.by[p["action"]], cn["family"], cn["member"], key)
            if v is None:
                continue
            out.append({"action": p["action"], "pin": p["at"], "content": p["family"], "commitment": p["commitment"],
                        "consumer": {"family": cn["family"], "member": cn["member"], "action": cn["action"],
                                     "at": cn["at"], "fn": cn["fn"]},
                        "recorded": v})
    return sorted(out, key=lambda x: (x["action"], x["content"], x["consumer"]["family"], x["consumer"]["member"]))


def kernel_law_id(doc: Doc, b: dict) -> str:
    return f"L_fact_kernel_{doc.contract}_{b['action']}_{b['commitment']}_{b['consumer']}"


def kernel_fact_id(doc: Doc, b: dict) -> str:
    return f"{doc.model}:kernel:{b['action']}:{b['commitment']}:{b['consumer']}"


def attr_law_id(doc: Doc, b: dict) -> str:
    return (f"L_fact_attr_{doc.contract}_{b['action']}_{b['content']}_{b['consumer']['family']}_"
            f"{b['consumer']['member']}")


def attr_fact_id(doc: Doc, b: dict) -> str:
    return (f"{doc.model}:attribution:{b['action']}:{b['content']}:{b['consumer']['family']}."
            f"{b['consumer']['member']}")


def hyp_premises(doc: Doc, action: str, sidecar: dict) -> list:
    """F8: a kernel law's hyp premises: each sidecar hypothesis of role "premise" whose constant's value (the document's
    constants) occurs as an integer literal in the action's records."""
    out = []
    a = doc.by[action]
    lits = set()

    def walk(t):
        if is_int(t):
            lits.add(t)
        elif isinstance(t, list):
            for x in t:
                walk(x)
        elif isinstance(t, dict):
            for v in t.values():
                walk(v)
    for sec in SCAN:
        walk(a.get(sec) or [])
    for hid, h in sorted((sidecar.get("hypotheses") or {}).items()):
        if h.get("role") != "premise":
            continue
        val = doc.constants.get(h.get("constant"))
        if val is not None and val in lits:
            out.append(f"hyp:{hid}")
    return out


def fact_ref(subform: str, basis: dict, premises: list) -> str:
    return hashlib.sha256(canonical({"template": f"holon.rules.fact/{subform}", "template_version": 1,
                                     "subform": subform, "basis": basis, "premises": premises})).hexdigest()


# ------------------------------------------------------------------ F9: the measure F(m, c) of a kernel basis element
def _blob_loops(a: dict) -> set:
    return {lp["src"] for lp in a["loops"] if holds_head(lp.get("break"), "blobhash")}


def _is_bterm(t, loops: set) -> bool:
    return (is_op(t, "blobhash") or (is_op(t, "count") and len(t) == 2 and t[1] in loops))


def _reads_b(t, loops: set) -> bool:
    if _is_bterm(t, loops):
        return True
    if isinstance(t, list):
        return any(_reads_b(x, loops) for x in t)
    return False


def _atoms(t, loops: set, out: dict) -> None:
    """Maximal subterms that are neither literals, B-terms, operator applications nor memory/hash structure."""
    if is_int(t) or isinstance(t, (str, bool)) or t is None:
        return
    if _is_bterm(t, loops):
        return
    if is_op(t) and (t[0] in OPS or t[0] in HASHES or t[0] in ("slice", "mem", "mloop", "mstore", "mstore8", "iter")):
        for x in t[1:]:
            _atoms(x, loops, out)
        return
    out[ck(t)] = t


def _compared_literals(t, atom_keys: set, out: dict) -> None:
    if not isinstance(t, list):
        return
    if is_op(t) and t[0] in ("==", "!=", "<", "<=", ">", ">=") and len(t) == 3:
        for x, y in ((t[1], t[2]), (t[2], t[1])):
            if is_int(y) and ck(x) in atom_keys:
                out.setdefault(ck(x), set()).add(y)
    for x in t:
        _compared_literals(x, atom_keys, out)


def _region_cells(v) -> list | None:
    """The cells of a commitment value keccak256/sha256(["slice", ["mem", cell..], off, len]) or None."""
    if not (is_op(v) and v[0] in HASHES and len(v) == 2 and is_op(v[1], "slice") and is_op(v[1][1], "mem")):
        return None
    return list(v[1][1][1:])


class _Eval:
    def __init__(self, a: dict, loops: set, ctx: dict, B: list):
        self.a, self.loops, self.ctx, self.B = a, loops, ctx, B
        self.loop_by = {lp["src"]: lp for lp in a["loops"]}

    def blob(self, i: int) -> int:
        return self.B[i] if 0 <= i < len(self.B) else 0

    def count(self, span: str) -> int:
        lp = self.loop_by[span]
        for i in range(len(self.B) + 2):
            if self.ev(lp["break"], {span: i}):
                return i
        raise AssertionError(f"the blob loop {span} does not end within the domain")

    def ev(self, t, it=None):
        it = it or {}
        if is_int(t):
            return t
        if isinstance(t, bool):
            return int(t)
        key = ck(t)
        if key in self.ctx:
            return self.ctx[key]
        h = t[0]
        if h == "iter":
            return it[t[1]]
        if h == "blobhash":
            return self.blob(self.ev(t[1], it))
        if h == "count":
            return self.count(t[1])
        if h == "?":
            return self.ev(t[2], it) if self.ev(t[1], it) else self.ev(t[3], it)
        if h == "!":
            return int(not self.ev(t[1], it))
        if h == "&&":
            return int(all(self.ev(x, it) for x in t[1:]))
        if h == "||":
            return int(any(self.ev(x, it) for x in t[1:]))
        if h in ("==", "!=", "<", "<=", ">", ">="):
            x, y = self.ev(t[1], it), self.ev(t[2], it)
            return int({"==": x == y, "!=": x != y, "<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y}[h])
        if h in ("+", "-", "*"):
            x, y = self.ev(t[1], it), self.ev(t[2], it)
            return {"+": x + y, "-": x - y, "*": x * y}[h] % W256
        if h in HASHES:   # CF: an injective symbolic image of the hashed cells
            return (h, self.region(t[1], it))
        raise AssertionError(f"F9 cannot evaluate {ck(t)[:160]}")

    def region(self, t, it):
        if not (is_op(t, "slice") and is_op(t[1], "mem")):
            raise AssertionError(f"F9: a hash of {ck(t)[:120]}")
        cells = []
        for c in t[1][1:]:
            if is_op(c, "mloop"):
                span, n = c[1], self.count(c[1]) if is_op(c[3], "count") else self.ev(c[3], it)
                for i in range(n):
                    for wr in c[4]:
                        cells.append((wr[0], self.ev(wr[1], {**it, span: i}), self.ev(wr[2], {**it, span: i})))
            elif is_op(c) and c[0] in ("mstore", "mstore8"):
                cells.append((c[0], self.ev(c[1], it), self.ev(c[2], it)))
            else:
                raise AssertionError(f"F9: a memory cell {ck(c)[:120]}")
        return (tuple(cells), self.ev(t[2], it), self.ev(t[3], it))


def _evaluable(t, loops: set, atoms: dict) -> bool:
    """Whether F9's evaluator interprets t: literals, B-terms, operators, iter, hashes of memory regions whose cells it
    interprets, and atoms (collected into atoms) that hold no B-term."""
    if is_int(t) or isinstance(t, bool):
        return True
    if _is_bterm(t, loops) or is_op(t, "iter"):
        return True
    if is_op(t) and t[0] in OPS:
        return all(_evaluable(x, loops, atoms) for x in t[1:])
    if is_op(t) and t[0] in HASHES:
        if not (len(t) == 2 and is_op(t[1], "slice") and is_op(t[1][1], "mem")):
            return False
        for c in t[1][1][1:]:
            if is_op(c, "mloop"):
                if not all(_evaluable(x, loops, atoms) for wr in c[4] for x in wr[1:]):
                    return False
            elif is_op(c) and c[0] in ("mstore", "mstore8"):
                if not (_evaluable(c[1], loops, atoms) and _evaluable(c[2], loops, atoms)):
                    return False
            else:
                return False
        return _evaluable(t[1][2], loops, atoms) and _evaluable(t[1][3], loops, atoms)
    if isinstance(t, list) and not _reads_b(t, loops):
        atoms[ck(t)] = t
        return True
    return False


def measure(doc: Doc, b: dict, sidecar: dict) -> dict:
    """F9 for the kernel basis element b."""
    a = doc.by[b["action"]]
    loops = _blob_loops(a)
    w = a["writes"][int(b["at"][len("writes["):-1])]
    cells = _region_cells(w["value"])
    if cells is None:
        raise AssertionError(f"{b['action']} {b['at']}: the commitment is not a hash of a memory region")
    V = [c[2] for c in cells if is_op(c) and c[0] in ("mstore", "mstore8") and _reads_b(c[2], loops)]
    V += [c for c in cells if is_op(c, "mloop") and _reads_b(c, loops)]
    atoms: dict = {}
    for t in V:
        if not _evaluable(t, loops, atoms):
            raise AssertionError(f"{b['action']}: F9 cannot evaluate the commitment cell {ck(t)[:160]}")
    guards = [(f"guards[{gi}].reaches[{ri}]", r["expr"]) for gi, ri, r in reaches(a)]
    guards += [(f"checks[{i}]", c.get("expr")) for i, c in enumerate(a["checks"]) if c.get("expr") is not None]
    bguards, unevaluated = [], []
    for at, e in guards:
        if not _reads_b(e, loops):
            continue
        sub: dict = {}
        if _evaluable(e, loops, sub):
            bguards.append(e)
            atoms.update(sub)
        else:
            unevaluated.append(at)
    keys = set(atoms)
    ev_guards = list(bguards)
    for _, e in guards:
        if _reads_b(e, loops):
            continue
        sub = {}
        if _evaluable(e, loops, sub) and sub and set(sub) <= keys:
            ev_guards.append(e)
    lits: dict = {}
    for t in V + ev_guards:
        _compared_literals(t, keys, lits)
    cand = {k: sorted({0} | {x for c in lits.get(k, set()) for x in (c - 1, c, c + 1) if x >= 0}) for k in sorted(keys)}
    dom = sidecar["measure"]
    alphabet = sorted({v for v in doc.constants.values() if admissible(v)} | {int(x, 16) for x in dom["fresh"]})
    lists = [list(p) for n in range(dom["max_length"] + 1) for p in itertools.product(alphabet, repeat=n)]
    fibers: dict = {}
    for combo in itertools.product(*[cand[k] for k in sorted(keys)]):
        ctx = dict(zip(sorted(keys), combo))
        for B in lists:
            e = _Eval(a, loops, ctx, B)
            if not all(e.ev(g) for g in ev_guards):
                continue
            val = tuple(e.ev(t) for t in V)
            fibers.setdefault((tuple(sorted(ctx.items())), repr(val)), []).append(B)
    mx = max((len(v) for v in fibers.values()), default=0)
    witness = sorted(({"context": [[k, v] for k, v in ctx], "lists": sorted([[word_hex(x) for x in B] for B in bs])}
                      for (ctx, _), bs in fibers.items() if len(bs) == mx), key=ck)
    return {"bits": round(math.log2(mx), 6) if mx else None, "max_fiber": mx,
            "domain": {"alphabet": [word_hex(x) for x in alphabet], "max_length": dom["max_length"],
                       "atoms": {k: cand[k] for k in sorted(keys)}},
            "max_fibers": witness, "unevaluated": sorted(unevaluated)}


# ------------------------------------------------------------------ the analysis
def analyse(path: Path, sidecar: dict, rel: str | None = None) -> dict:
    doc = Doc(path, rel)
    comms = commitments(doc)
    kb = kernel_basis(doc, comms)
    cons = attribution_consumers(doc, comms)
    ps = pins(doc, comms)
    ab = attribution_basis(doc, comms, ps, cons)
    laws = {}
    for b in kb:
        lid = kernel_law_id(doc, b)
        basis = {"kind": "fact_kernel", "model": doc.model, "contract": doc.contract, "action": b["action"],
                 "at": b["at"], "commitment": b["commitment"], "consumer": b["consumer"]}
        laws[lid] = {"subform": "kernel", "fact_id": kernel_fact_id(doc, b), "basis": basis,
                     "premises_fixed": sorted(["blobs_wf"] + hyp_premises(doc, b["action"], sidecar)),
                     "measure": measure(doc, b, sidecar)}
    for b in ab:
        lid = attr_law_id(doc, b)
        basis = {"kind": "fact_attribution", "model": doc.model, "contract": doc.contract, "action": b["action"],
                 "pin": b["pin"], "content": b["content"], "commitment": b["commitment"], "consumer": b["consumer"],
                 "recorded": b["recorded"]}
        laws[lid] = {"subform": "attribution", "fact_id": attr_fact_id(doc, b), "basis": basis,
                     "premises_fixed": ["blobs_wf"], "measure": None}
    return {"model": doc.model, "contract": doc.contract, "commitments": comms, "kernel": kb,
            "attribution_consumers": cons, "pins": ps, "writers": writers(doc, sorted({p["family"] for p in ps})),
            "attribution": ab, "laws": laws}


# ------------------------------------------------------------------ the basis sidecar
DOC_REL = "spec/M2/facts/morph_rollup.extracted.json"
SIDECAR_REL = "spec/M3/lib/fact.json"
PREDICTED = {   # law id -> (subform, predicted status): the I26 predictions (P5-P7) and the plan's regression (R2)
    "L_fact_attr_Rollup_commitBatchWithProof_batchBlobVersionedHashes_batchDataStore_submitter": ("attribution",
                                                                                                "REFUTED"),
    "L_fact_attr_Rollup_commitState_batchBlobVersionedHashes_batchDataStore_submitter": ("attribution", "REFUTED"),
    "L_fact_kernel_Rollup_commitBatchWithProof_committedBatches_blobhash": ("kernel", "REFUTED"),
    "L_fact_kernel_Rollup_commitBatch_committedBatches_blobhash": ("kernel", "REFUTED"),
    "L_fact_kernel_Rollup_commitState_committedBatches_blobhash": ("kernel", "PROVED"),
}


def basis_inputs(root: Path) -> list:
    return [{"path": p, "sha256": sha256_file(root / p)} for p in sorted([DOC_REL, SIDECAR_REL])]


def fact_basis_doc(root: Path = ROOT) -> dict:
    side = load_json(root / SIDECAR_REL)
    an = analyse(root / DOC_REL, side, DOC_REL)
    for lid, x in an["laws"].items():
        x["predicted"] = PREDICTED.get(lid, (x["subform"], None))[1]
    tot = {"commitments": len(an["commitments"]), "sites": sum(len(c["sites"]) for c in an["commitments"]),
           "kernel": len(an["kernel"]), "attribution_consumers": len(an["attribution_consumers"]),
           "pins": len(an["pins"]), "attribution": len(an["attribution"]),
           "laws": {"kernel": len(an["kernel"]), "attribution": len(an["attribution"])},
           "predicted": {s: sum(1 for x in an["laws"].values() if x["predicted"] == s)
                         for s in ("PROVED", "REFUTED", "UNKNOWN")}}
    return {"fact_basis_version": "holon-fact-basis/0.1", "iteration": "I26", "inputs": basis_inputs(root),
            "documents": {DOC_REL: an}, "totals": tot}


def write_basis(root: Path = ROOT) -> None:
    p = root / "spec" / "M3" / "lib" / "fact_basis.json"
    old = load_json(p) if p.exists() else {}
    obj = dict(fact_basis_doc(root), doc=old.get("doc", ""))
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


# ------------------------------------------------------------------ FB2/FB3: the back-test move and agg
def blob_token(h: str, mv: dict):
    n = int(h, 16)
    tab = {int(k, 16): v for k, v in mv["blob_tokens"].items()}
    if n in tab:
        return tab[n]
    if (n >> 248) == 0x01 and (n & ((1 << 248) - 1)) not in tab.values():
        return n & ((1 << 248) - 1)
    return None


def move_kernel_witness(w: dict, mv: dict, owner: str | None = None) -> dict | None:
    """The M1 inputs (p, c1, c2) of a kernel witness under the frozen move (spec/M3/lib/fact.json backtest.move); None
    when the two runs do not share their prefix or a value has no M1 token."""
    runs = w["runs"]
    if ck(runs[0]["prefix"]) != ck(runs[1]["prefix"]):
        return None
    prin = {k.lower(): v for k, v in mv["principals"].items()}
    if owner is not None:
        prin[owner.lower()] = mv["owner_token"]
    clock = [mv["m1_clock0"]]

    def act(step: dict, out: list):
        env = step["env"]
        t = int(env["block.timestamp"]) - mv["clock_offset"]
        if t > clock[0]:
            out.append({"op": "wait", "dt": t - clock[0]})
            clock[0] = t
        who = prin.get(str(env["caller"]).lower())
        if who is None:
            raise KeyError(env["caller"])
        name = step["action"]
        if name in ("commitBatch", "commitState", "commitBatchWithProof"):
            x = step["args"][0] if isinstance(step["args"], list) else step["args"]["batchDataInput"]
            parent = int(str(x["parentBatchHeader"])[2:][2:18], 16)
            toks = [blob_token(h, mv) for h in env.get("blobhash") or []]
            if None in toks:
                raise KeyError("blob")
            a = {"op": name, "who": who, "ver": _num(x["version"]), "parent": parent, "n": _num(x["numL1Messages"]),
                 "lbn": _num(x["lastBlockNumber"]), "prev": _num(x["prevStateRoot"]), "post": _num(x["postStateRoot"]),
                 "blobs": toks}
            out.append(a)
            return
        raise KeyError(name)
    try:
        p: list = []
        for s in runs[0]["prefix"]:
            act(s, p)
        pre_clock = clock[0]
        c: list = []
        act(runs[0]["x"], c)
        clock[0] = pre_clock
        c2: list = []
        act(runs[1]["x"], c2)
    except KeyError:
        return None
    waits1 = [x for x in c if x["op"] == "wait"]
    waits2 = [x for x in c2 if x["op"] == "wait"]
    if ck(waits1) != ck(waits2):
        return None
    return {"p": p + waits1, "c1": c[-1], "c2": c2[-1]}


def b_pair(a: int, b: int) -> int:
    return (a + b) * (a + b + 1) // 2 + b


def b_enc(xs: list) -> int:
    return 0 if not xs else 1 + b_pair(xs[0], b_enc(xs[1:]))


def agg_m1(xs: list) -> int:
    return 1000 + b_enc(xs)


# ------------------------------------------------------------------ ABI, headers, steps
def _word(n: int) -> bytes:
    return (int(n) % W256).to_bytes(32, "big")


def _hexb(v) -> bytes:
    if isinstance(v, (bytes, bytearray)):
        return bytes(v)
    s = str(v)
    return bytes.fromhex(s[2:] if s.startswith("0x") else s)


def _num(v) -> int:
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, str):
        return int(v, 16) if v.lower().startswith("0x") else int(v)
    return int(v)


def _split_tuple(t: str) -> list:
    inner, out, depth, cur = t[1:-1], [], 0, ""
    for ch in inner:
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        depth += ch == "("
        depth -= ch == ")"
        cur += ch
    if cur:
        out.append(cur)
    return out


def _dynamic(t: str) -> bool:
    if t.startswith("("):
        return any(_dynamic(x) for x in _split_tuple(t))
    return t in ("bytes", "string") or t.endswith("[]")


def abi_encode(types: list, values: list) -> bytes:
    heads, tails = [], []
    off = 32 * len(types)
    for t, v in zip(types, values):
        if t.startswith("("):
            enc = abi_encode(_split_tuple(t), list(v))
            if not _dynamic(t):
                heads.append(enc)
                continue
        elif t == "bytes":
            b = _hexb(v)
            enc = _word(len(b)) + b + b"\0" * ((-len(b)) % 32)
        elif t == "bytes32[]":
            enc = _word(len(v)) + b"".join(_hexb(x).rjust(32, b"\0") for x in v)
        else:
            heads.append(_hexb(v).rjust(32, b"\0") if t == "bytes32" else _word(_num(v)))
            continue
        heads.append(_word(off))
        tails.append(enc)
        off += len(enc)
    return b"".join(heads) + b"".join(tails)


def selector(sig: str) -> bytes:
    return keccak256(sig.encode())[:4]


INPUT = "(uint8,bytes,uint64,uint16,bytes32,bytes32,bytes32)"


def header(v: int, idx: int, l1p: int, tot: int, dh: int, blob: int, prev: int, post: int, withdraw: int,
           parent: bytes | int, lbn: int) -> bytes:
    """A batch header as BatchHeaderCodecV0/V1 lay it out (249 bytes at version 0, 257 from version 1)."""
    par = parent if isinstance(parent, (bytes, bytearray)) else _word(parent)
    h = (bytes([v]) + idx.to_bytes(8, "big") + l1p.to_bytes(8, "big") + tot.to_bytes(8, "big") + _word(dh)
         + _word(blob) + _word(prev) + _word(post) + _word(withdraw) + _word(0) + bytes(par))
    if v >= 1:
        h += lbn.to_bytes(8, "big")
    return h


def genesis_header(r0: int) -> bytes:
    """The deployment's genesis header (HolonTraceReplayTest.deploy: hdr(0, 0, 1, ZVH, r0))."""
    return header(0, 0, 0, 0, 1, int(ZVH, 16), 0, r0, 0, 0, 0)


ZVH = "0x010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014"


def data_hash(lbn: int, n: int = 0) -> int:
    return int.from_bytes(keccak256(lbn.to_bytes(8, "big") + n.to_bytes(2, "big")), "big")


def step(action: str, sig: str, types: list, args: list, caller: str, ts: int, value: int = 0,
         blobs: list | None = None) -> dict:
    data = selector(sig) + abi_encode(types, args)
    return {"action": action, "args": args, "calldata": "0x" + data.hex(),
            "env": {"caller": caller, "msg.value": value, "block.timestamp": ts, "blobhash": list(blobs or []),
                    "calls": []}}


def commit_step(action: str, inp: list, caller: str, ts: int, blobs: list | None = None) -> dict:
    return step(action, f"{action}({INPUT})", [INPUT], [inp], caller, ts, 0, blobs)


def call_step(st: dict) -> str:
    """The I20 step harness's call step: abi.encode(uint8 2, bool false, bytes payload), payload abi.encode(address
    caller, uint256 value, uint256 timestamp, bytes32[] blobhashes, address to (0: the target), bytes data)."""
    env = st.get("env") or {}
    payload = abi_encode(["address", "uint256", "uint256", "bytes32[]", "address", "bytes"],
                         [env["caller"], _num(env.get("msg.value", 0)), _num(env.get("block.timestamp", 0)),
                          list(env.get("blobhash") or []), 0, st["calldata"]])
    return "0x" + abi_encode(["uint8", "bool", "bytes"], [2, False, payload]).hex()


def deployment_init() -> list[int]:
    """The I20 binding's deployment parameters [F, W, D, t0, r0], as holon fragments passes them."""
    binding = load_json(ROOT / "replay" / "M2" / "fragments.json")
    initial = load_json(ROOT / binding["init"]["facts"])["initial"]
    out = []
    for k in binding["init"]["keys"]:
        name, _, idx = k.partition(".")
        out.append(int(initial[name][int(idx)] if idx else initial[name]))
    return out


def map_slot(key: int, slot: int) -> int:
    return int.from_bytes(keccak256(_word(key) + _word(slot)), "big")


def family_slot(doc: Doc, family: str, key: int, member: str | None = None) -> int:
    f = doc.fams[family]
    s = map_slot(key, f["slot"])
    if member is not None:
        s += next(x for x in f["fields"] if x["name"] == member)["slot"]
    return s


# ------------------------------------------------------------------ the raw-call replay on the real Rollup
def realized(traces: list[list[dict]], slots: list[int] | None = None) -> list[dict]:
    if not traces:
        raise AssertionError("no trace to replay")
    slots = list(slots or [])
    cfg = I15._check_toolchain()
    for name, pin in HARNESS.items():
        if sha256_file(HARNESS_DIR / f"{name}.txt") != pin:
            raise AssertionError(f"tests_m3/fixtures/fact/harness/{name}.txt is not the harness copied at the prereg")
    morph = morph_checkout()
    proj = Path(tempfile.mkdtemp(prefix="holon-i26-sol-"))
    try:
        shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
        for d in ("mock", "test"):
            shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
        for f in ("foundry.toml", "remappings.txt"):
            shutil.copy(morph / "contracts" / f, proj / f)
        shutil.copytree(Path(cfg["sol_deps"]) / "node_modules", proj / "node_modules", symlinks=False,
                        ignore=shutil.ignore_patterns(".git"))
        (proj / "test").mkdir()
        for name in HARNESS:
            shutil.copy(HARNESS_DIR / f"{name}.txt", proj / "test" / name)
        fin, fout = proj / "holon_i26_steps.json", proj / "holon_i26_steps.out"
        fin.write_text(json.dumps({"lens": [len(tr) for tr in traces],
                                   "steps": [call_step(s) for tr in traces for s in tr],
                                   "slots": ["0x" + _word(s).hex() for s in slots], "init": deployment_init()}))
        env = {**os.environ, "HOLON_STEPS_IN": str(fin), "HOLON_STEPS_OUT": str(fout), "HOLON_LO": "0",
               "HOLON_HI": str(len(traces))}
        p = subprocess.run([cfg["forge"], "test", "--offline", "--use", cfg["solc"], "--match-contract",
                            "^HolonExtractedStepTest$", "--match-test", r"^test_steps\(\)$"], cwd=proj, env=env,
                           capture_output=True, text=True, timeout=3000)
        if p.returncode != 0 or not fout.exists():
            raise AssertionError(f"the I26 replay instrument failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2000:]}")
        obs: dict = {}
        harness: dict = {}
        for line in fout.read_text().splitlines():
            f = line.split(" ")
            if f[0] == "T" and len(f) == 4:
                harness[int(f[1])] = "0x" + f[3][2:].lower().rjust(40, "0")
            elif f[0] == "S" and len(f) == 14 and f[3] == "call" and f[2].isdigit():
                o = obs.setdefault((int(f[1]), int(f[2])), {"logs": [], "calls": [], "slots": {}})
                o["status"] = "ok" if f[5] == "1" else "revert"
                o["ret"] = f[-1].lower()
            elif f[0] == "L" and f[2].isdigit():
                o = obs.setdefault((int(f[1]), int(f[2])), {"logs": [], "calls": [], "slots": {}})
                o["logs"].append({"topics": [] if f[3] == "-" else f[3].lower().split(","), "data": f[4].lower()})
            elif f[0] == "C" and f[2].isdigit():
                o = obs.setdefault((int(f[1]), int(f[2])), {"logs": [], "calls": [], "slots": {}})
                o["calls"].append({"to": f[3].lower(), "data": f[4].lower(), "ok": f[5] == "1", "ret": f[6].lower()})
            elif f[0] == "D" and f[2].isdigit():
                o = obs.setdefault((int(f[1]), int(f[2])), {"logs": [], "calls": [], "slots": {}})
                vals = [] if f[3] == "-" else f[3].split(",")
                o["slots"] = {s: (0 if v == "0" else int(v, 16)) for s, v in zip(slots, vals)}
        out = []
        for tid, tr in enumerate(traces):
            row = []
            for i in range(len(tr)):
                o = obs.get((tid, i))
                if o is None or "status" not in o:
                    raise AssertionError(f"trace {tid} step {i}: no S line in the harness output")
                if o["status"] == "revert":
                    o = dict(o, logs=[], calls=[])
                row.append(o)
            out.append({"harness": harness.get(tid), "steps": row})
        return out
    finally:
        shutil.rmtree(proj, ignore_errors=True)


def owner_address() -> str:
    """The Rollup's owner in the binding's deployment: the test contract that deployed it (HolonExtractedStepTest), at
    Foundry's default test-contract address; the instrument check compares it with the harness's T line."""
    return "0x7fa9385be102ac3eac297483dd6233d62b3e1496"


# ------------------------------------------------------------------ the hand-built traces of the instrument check
def _batch1(r0: int, blob: int, post: int, lbn: int) -> tuple[list, bytes]:
    """(the BatchDataInput of batch 1 over the genesis header at version 1, the header it commits)."""
    g = genesis_header(r0)
    inp = [1, g, lbn, 0, _word(r0), _word(post), _word(0)]
    h = header(1, 1, 0, 0, data_hash(lbn, 0), blob, r0, post, 0, keccak256(g), lbn)
    return inp, h


def o25_chain() -> tuple[list, dict]:
    """S1 commits batch 1 (version 1, one blob B), the owner reverts it, S2 recommits it with commitState (no blob: the
    pinned B), the challenger challenges it, and S1 proves it after the proof window (the timeout branch slashes the
    recorded submitter). Returns (the trace, {"hash", "header", "s1", "s2"})."""
    F, W, D, t0, r0 = deployment_init()
    blob = (1 << 248) | 0x42
    inp, h = _batch1(r0, blob, 110, 1)
    s1, s2 = STANDIN_SUBMITTERS
    T = EPOCH + t0
    hb = keccak256(h)
    tr = [commit_step("commitBatch", inp, s1, T + 1, [word_hex(blob)]),
          step("revertBatch", "revertBatch(bytes,uint256)", ["bytes", "uint256"], [h, 1], owner_address(), T + 2),
          commit_step("commitState", inp, s2, T + 3, []),
          step("challengeState", "challengeState(uint64,bytes32)", ["uint64", "bytes32"], [1, hb], CHALLENGER, T + 4,
               1),
          step("proveState", "proveState(bytes,bytes)", ["bytes", "bytes"], [h, b"\x01"], s1, T + 4 + W)]
    return tr, {"hash": "0x" + hb.hex(), "header": "0x" + h.hex(), "s1": s1, "s2": s2}


def z_pair() -> tuple[list, list, dict]:
    """Two runs of one commitBatch of batch 1 at version 1 with the same calldata: no blob, and the one blob
    ZERO_VERSIONED_HASH (the zero blob's versioned hash, Hyp-Z0-kzg)."""
    F, W, D, t0, r0 = deployment_init()
    inp, h = _batch1(r0, int(ZVH, 16), 110, 1)
    T = EPOCH + t0
    s1 = STANDIN_SUBMITTERS[0]
    return ([commit_step("commitBatch", inp, s1, T + 1, [])], [commit_step("commitBatch", inp, s1, T + 1, [ZVH])],
            {"hash": "0x" + keccak256(h).hex(), "header": "0x" + h.hex()})
