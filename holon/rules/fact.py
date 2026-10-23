"""Rule FACT over the extracted documents: commitments, consumers, pins, the attribution basis and their laws (BUILD_PLAN
I26; whitepaper §5.5, Thm 6.8, Def 6.13, §8.4 FACT row, §8.5, App. D, App. E FACT row, App. F; the contract is the
docstring of tests_m3/test_fact.py, rules F1-F8, H1, "The analysis" and "Laws"). The measure F9 is
holon.measures_fact.

  python -m holon fact --milestone M [--root DIR] [--fact-sidecar PATH] [--facts PATH ..] [--out DIR] [--classify]
                       [--backtest]

writes <out, default gen/<M>/fact>/<model>.json for every document of the FACT sidecar (default spec/<M>/lib/fact.json),
or of --facts (planted documents). --classify writes results/<M>/fact/classification.json (Thm 6.8: bits against the
records' statuses); --backtest results/M3/fact/backtest.json and gen/M3/fact/backtest/ (holon.fact.backtest). Exit 0
written; 2 refused, nothing written (a sidecar or document missing or malformed); 1 an unreadable input.

  F1 commitments    a mapping family F with a commitment write (F2) in a non-view action and an authenticating guard
                    reach in some action: a top-level conjunct ["==", R, H] or ["==", H, R], R = ["map", ["storage", F],
                    k], H a hash term
  F2 sites          every final, whole, keyed, unconditional write of F in a non-view action whose value is a hash term
  F3 delivered data a site's action holding a blob-hash term in any record: the consumer "blobhash"
  F4 kernel laws    L_fact_kernel_<contract>_<action>_<F>_<consumer>
  F5 attribution    an argument ["member", ["map", ["storage", A], k], m] of a call of an action b that authenticates a
     consumers      commitment F at the syntactically same key k before the call
  F6 pins           a final, whole, unconditional write of P (not F) by a site's action at the site's key whose value is
                    the copy C = ["map", ["storage", P], key] ("copy") or a ? term with C among its branches ("branch")
  F7 attribution    one per (pin of P by w, attribution consumer of the same commitment) where w records A.m at the
     basis          pin's key: L_fact_attr_<contract>_<w>_<P>_<A>_<m>
  F8 premises       blobs_wf; cf:<h> and nz:<h> per hash binder; hyp:<id> on a kernel law for each premise hypothesis
                    whose constant's value is an integer literal of its action's records

Nothing here names a target: every action, family, member, contract and term comes from the document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from .. import measures_fact as MF

RULE = "FACT"
SUBFORMS = ("kernel", "attribution")
FACT_VERSION = "holon-fact/0.1"
TEMPLATE_VERSION = 1
NOT_STATE = ("view", "pure")
HASHES = ("keccak256", "sha256")
SCAN = ("guards", "checks", "panics", "calls", "writes", "events", "mstores", "loops")
ROOT = Path(__file__).resolve().parents[2]
LAW_PREFIX = "L_" + RULE.lower() + "_"
CONSUMER_BLOBS = "blobhash"


class FactError(ValueError):
    """A basis that cannot be derived (exit 3 of derive)."""


class Refused(ValueError):
    """A sidecar or document missing or malformed: exit 2, nothing written."""


def dumps(obj) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def is_op(t, op: str | None = None) -> bool:
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


def is_hash(t) -> bool:
    return is_op(t) and t[0] in HASHES


def holds(t, head: str) -> bool:
    if isinstance(t, list):
        if t and t[0] == head:
            return True
        return any(holds(x, head) for x in t)
    if isinstance(t, dict):
        return any(holds(v, head) for v in t.values())
    return False


def ints(t, out: set) -> None:
    if is_int(t):
        out.add(t)
    elif isinstance(t, list):
        for x in t:
            ints(x, out)
    elif isinstance(t, dict):
        for x in t.values():
            ints(x, out)


def records(a: dict) -> list:
    return [r for sec in SCAN for r in (a.get(sec) or [])]


# ------------------------------------------------------------------------------------------------ terms
def wkey(w: dict):
    """(key or None, whole): path [] a scalar (whole), [["map", k]] a whole register, longer a member."""
    path = w.get("path") or []
    if not path:
        return None, True
    if is_op(path[0], "map"):
        return path[0][1], len(path) == 1
    return None, False


def final(a: dict, i: int) -> bool:
    """No later write of the same action writes the same family whole at the syntactically same key."""
    ws = a.get("writes") or []
    w = ws[i]
    k, _ = wkey(w)
    for j, w2 in enumerate(ws):
        if j == i or w2.get("family") != w.get("family") or w2.get("seq", 0) <= w.get("seq", 0):
            continue
        k2, whole2 = wkey(w2)
        if whole2 and canon(k2) == canon(k):
            return False
    return True


def unconditional(w: dict) -> bool:
    return w.get("cond") == 1


def map_read(F: str, k) -> list:
    return ["map", ["storage", F], k]


def reaches(a: dict) -> list:
    return [(gi, ri, r) for gi, g in enumerate(a.get("guards") or []) for ri, r in enumerate(g.get("reaches") or [])]


def auth_key(expr, F: str):
    """The keys k of every top-level conjunct ["==", R, H] / ["==", H, R] with R = F's register at k and H a hash."""
    out = []
    for c in conjuncts(expr):
        if is_op(c, "==") and len(c) == 3:
            for r, h in ((c[1], c[2]), (c[2], c[1])):
                if is_op(r, "map") and len(r) == 3 and r[1] == ["storage", F] and is_hash(h):
                    out.append(r[2])
    return out


def mapping_families(doc: dict) -> list:
    return sorted(f["name"] for f in doc.get("storage") or [] if f.get("kind") == "mapping")


def state_actions(doc: dict) -> list:
    return [a for a in doc.get("actions") or [] if a.get("mutability") not in NOT_STATE]


# ------------------------------------------------------------------------------------------------ F1-F3
def sites_of(doc: dict, F: str) -> list:
    out = []
    for a in state_actions(doc):
        for i, w in enumerate(a.get("writes") or []):
            if w.get("family") != F:
                continue
            k, whole = wkey(w)
            if whole and k is not None and unconditional(w) and final(a, i) and is_hash(w.get("value")):
                out.append({"action": a["name"], "at": f"writes[{i}]", "key": k})
    return sorted(out, key=lambda s: (s["action"], s["at"]))


def authenticated_by(doc: dict, F: str) -> list:
    out = set()
    for a in doc.get("actions") or []:
        for gi, _ri, r in reaches(a):
            if auth_key(r.get("expr"), F):
                out.add((a["name"], f"guards[{gi}]"))
    return [{"action": x, "at": g} for x, g in sorted(out, key=lambda p: (p[0], _idx(p[1])))]


def _idx(at: str) -> int:
    m = re.search(r"\[(\d+)\]", at)
    return int(m.group(1)) if m else -1


def commitments(doc: dict) -> list:
    out = []
    for F in mapping_families(doc):
        sites = sites_of(doc, F)
        auth = authenticated_by(doc, F)
        if sites and auth:
            out.append({"family": F, "sites": sites, "authenticated_by": auth})
    return out


def action_of(doc: dict, name: str) -> dict:
    for a in doc.get("actions") or []:
        if a.get("name") == name:
            return a
    raise FactError(f"no action {name}")


def kernel_basis(doc: dict, comms: list) -> list:
    out = []
    for c in comms:
        for s in c["sites"]:
            a = action_of(doc, s["action"])
            if any(holds(r, "blobhash") for r in records(a)):
                out.append({"action": s["action"], "at": s["at"], "commitment": c["family"],
                            "consumer": CONSUMER_BLOBS})
    return sorted(out, key=lambda k: (k["action"], k["commitment"]))


# ------------------------------------------------------------------------------------------------ F5-F7
def attribution_consumers(doc: dict, comms: list) -> list:
    out = []
    for c in comms:
        F = c["family"]
        for b in doc.get("actions") or []:
            keys = [(canon(k), r.get("seq", 0)) for _gi, _ri, r in reaches(b) for k in auth_key(r.get("expr"), F)]
            if not keys:
                continue
            for ci, call in enumerate(b.get("calls") or []):
                for arg in call.get("args") or []:
                    if not (is_op(arg, "member") and len(arg) == 3 and is_op(arg[1], "map") and len(arg[1]) == 3
                            and is_op(arg[1][1], "storage") and isinstance(arg[2], str)):
                        continue
                    k = canon(arg[1][2])
                    if any(kk == k and seq < call.get("seq", 0) for kk, seq in keys):
                        rec = {"family": arg[1][1][1], "member": arg[2], "commitment": F, "action": b["name"],
                               "at": f"calls[{ci}]", "fn": call.get("fn")}
                        if rec not in out:
                            out.append(rec)
    return sorted(out, key=lambda r: (r["family"], r["member"], r["action"], _idx(r["at"])))


def copy_in(v, C) -> bool:
    """C among the branches of a ? term, at any depth."""
    if is_op(v, "?") and len(v) == 4:
        return any(x == C or copy_in(x, C) for x in (v[2], v[3]))
    return False


def pins(doc: dict, comms: list) -> list:
    out = []
    for c in comms:
        F = c["family"]
        for s in c["sites"]:
            a = action_of(doc, s["action"])
            for i, w in enumerate(a.get("writes") or []):
                P = w.get("family")
                if P == F:
                    continue
                k, whole = wkey(w)
                if not (whole and k is not None and unconditional(w) and final(a, i) and canon(k) == canon(s["key"])):
                    continue
                C = map_read(P, k)
                v = w.get("value")
                how = "copy" if v == C else ("branch" if copy_in(v, C) else None)
                if how:
                    rec = {"action": a["name"], "at": f"writes[{i}]", "family": P, "how": how, "commitment": F}
                    if rec not in out:
                        out.append(rec)
    return sorted(out, key=lambda p: (p["family"], p["action"], _idx(p["at"])))


def writer_kind(w: dict) -> str:
    k, _ = wkey(w)
    C = map_read(w["family"], k)
    v = w.get("value")
    if v == C:
        return "copy"
    if copy_in(v, C):
        return "branch"
    if is_int(v) and v == 0:
        return "clear"
    return "fresh"


def writers(doc: dict, families: list) -> dict:
    out = {}
    for P in families:
        ws = []
        for a in doc.get("actions") or []:
            for i, w in enumerate(a.get("writes") or []):
                if w.get("family") != P:
                    continue
                k, whole = wkey(w)
                if whole:
                    ws.append({"action": a["name"], "at": f"writes[{i}]", "kind": writer_kind(w)})
        out[P] = sorted(ws, key=lambda x: (x["action"], _idx(x["at"])))
    return out


def recorded(a: dict, A: str, m: str, key):
    """The value term a records for A.m at key: a member of a final whole unconditional struct write of A there, or a
    member write; None when a does not record it."""
    for i, w in enumerate(a.get("writes") or []):
        if w.get("family") != A:
            continue
        path = w.get("path") or []
        if not path or not is_op(path[0], "map") or canon(path[0][1]) != canon(key):
            continue
        v = w.get("value")
        if len(path) == 1 and unconditional(w) and final(a, i) and is_op(v, "struct") and len(v) == 3:
            for f in v[2]:
                if isinstance(f, list) and len(f) == 2 and f[0] == m:
                    return True, f[1]
        if len(path) == 2 and is_op(path[1], "member") and path[1][1] == m:
            return True, v
    return False, None


def attribution_basis(doc: dict, comms: list, ps: list, cons: list) -> list:
    out = []
    keys = {(c["family"], s["action"]): s["key"] for c in comms for s in c["sites"]}
    for p in ps:
        a = action_of(doc, p["action"])
        key = keys[(p["commitment"], p["action"])]
        for c in cons:
            if c["commitment"] != p["commitment"]:
                continue
            ok, v = recorded(a, c["family"], c["member"], key)
            if not ok:
                continue
            out.append({"action": p["action"], "pin": p["at"], "content": p["family"], "commitment": p["commitment"],
                        "consumer": {"family": c["family"], "member": c["member"], "action": c["action"],
                                     "at": c["at"], "fn": c["fn"]},
                        "recorded": v})
    return sorted(out, key=lambda r: (r["action"], r["content"], r["consumer"]["family"], r["consumer"]["member"]))


# ------------------------------------------------------------------------------------------------ F4, F7, F8
def kernel_law_id(contract: str, b: dict) -> str:
    return f"{LAW_PREFIX}kernel_{contract}_{b['action']}_{b['commitment']}_{b['consumer']}"


def kernel_fact_id(model: str, b: dict) -> str:
    return f"{model}:kernel:{b['action']}:{b['commitment']}:{b['consumer']}"


def attr_law_id(contract: str, b: dict) -> str:
    c = b["consumer"]
    return f"{LAW_PREFIX}attr_{contract}_{b['action']}_{b['content']}_{c['family']}_{c['member']}"


def attr_fact_id(model: str, b: dict) -> str:
    c = b["consumer"]
    return f"{model}:attribution:{b['action']}:{b['content']}:{c['family']}.{c['member']}"


def hash_binders(doc: dict) -> list:
    from .sort import hash_functions
    return list(hash_functions(doc))


def hyp_premises(doc: dict, action: dict, hypotheses: dict) -> list:
    lits = set()
    for r in records(action):
        ints(r, lits)
    out = []
    for hid, h in sorted((hypotheses or {}).items()):
        if h.get("role") != "premise" or not h.get("constant"):
            continue
        v = (doc.get("constants") or {}).get(h["constant"])
        n = MF._int(v)
        if n is not None and n in lits:
            out.append(f"hyp:{hid}")
    return out


def premises(doc: dict, subform: str, action: dict, sidecar: dict) -> list:
    hb = hash_binders(doc)
    out = ["blobs_wf"] + [f"cf:{h}" for h in hb] + [f"nz:{h}" for h in hb]
    if subform == "kernel":
        out += hyp_premises(doc, action, sidecar.get("hypotheses") or {})
    return sorted(out)


def model_of(doc_rel: str) -> str:
    name = Path(doc_rel).name
    return name[:-len(".json")] if name.endswith(".json") else Path(doc_rel).stem


def analyse(doc: dict, model: str, sidecar: dict) -> dict:
    """F1-F9 over one transitions document."""
    contract = doc.get("contract")
    comms = commitments(doc)
    kern = kernel_basis(doc, comms)
    cons = attribution_consumers(doc, comms)
    ps = pins(doc, comms)
    wr = writers(doc, sorted({p["family"] for p in ps}))
    attr = attribution_basis(doc, comms, ps, cons)
    ms = (sidecar or {}).get("measure") or {}
    laws = {}
    for b in kern:
        basis = {"kind": "fact_kernel", "model": model, "contract": contract, "action": b["action"], "at": b["at"],
                 "commitment": b["commitment"], "consumer": b["consumer"]}
        a = action_of(doc, b["action"])
        laws[kernel_law_id(contract, b)] = {
            "subform": "kernel", "fact_id": kernel_fact_id(model, b), "basis": basis,
            "premises": premises(doc, "kernel", a, sidecar),
            "measure": MF.measure(doc, a, b["at"], list(ms.get("fresh") or []), int(ms.get("max_length", 0)))}
    for b in attr:
        basis = {"kind": "fact_attribution", "model": model, "contract": contract, "action": b["action"],
                 "pin": b["pin"], "content": b["content"], "commitment": b["commitment"], "consumer": b["consumer"],
                 "recorded": b["recorded"]}
        a = action_of(doc, b["action"])
        laws[attr_law_id(contract, b)] = {"subform": "attribution", "fact_id": attr_fact_id(model, b), "basis": basis,
                                          "premises": premises(doc, "attribution", a, sidecar), "measure": None}
    ids = list(laws)
    fids = [x["fact_id"] for x in laws.values()]
    if len(set(fids)) != len(fids):
        raise FactError(f"two bases with one fact id: {sorted(fids)}")
    del ids
    return {"model": model, "contract": contract, "commitments": comms, "kernel": kern,
            "attribution_consumers": cons, "pins": ps, "writers": wr, "attribution": attr,
            "laws": dict(sorted(laws.items()))}


def elements(an: dict) -> list:
    return [{"law_id": lid, **x} for lid, x in sorted(an["laws"].items())]


def ghost_x(law_id: str) -> str:
    return law_id[len(LAW_PREFIX):]


def fact_spec(subform: str, basis: dict, prem: list) -> dict:
    return {"template": f"holon.rules.fact/{subform}", "template_version": TEMPLATE_VERSION, "subform": subform,
            "basis": basis, "premises": prem}


def fact_hash(subform: str, basis: dict, prem: list) -> str:
    return sha256_bytes(canon(fact_spec(subform, basis, prem)).encode("utf-8"))


def fact_ref(fid: str, law: dict, root=None) -> str:
    """The ref "fact:<ID>" recomputed from the law's document and the FACT sidecar of its milestone."""
    root = Path(root or ROOT)
    rel = str(law.get("facts"))
    try:
        d = json.loads((root / rel).read_text(encoding="utf-8"))
        sc = load_sidecar(str(law.get("milestone")), root)
        an = analyse(d, model_of(rel), sc.doc)
    except (OSError, ValueError, KeyError, TypeError, Refused) as e:
        return sha256_bytes(canon({"absent": fid, "error": type(e).__name__}).encode("utf-8"))
    for x in an["laws"].values():
        if x["fact_id"] == fid:
            return fact_hash(x["subform"], x["basis"], x["premises"])
    return sha256_bytes(canon({"absent": fid}).encode("utf-8"))


def law_ir(lid: str, x: dict, milestone: str, doc_rel: str, doc_sha: str, catalog_version: str, hashes: list) -> dict:
    b = x["basis"]
    if x["subform"] == "kernel":
        head = [("s1", "Reach"), ("x1", "Act"), ("s2", "Reach"), ("x2", "Act")]
        notes = (f"if calls x1 and x2 of {b['action']} both succeed and commit equal {b['commitment']} values at their "
                 f"write keys, they deliver equal {b['consumer']} lists (Thm 6.8 (iii): ker(m) within ker(c), the product "
                 "program of §8.4), under the premises")
    else:
        head = [("p", "Trace"), ("y", "Act")]
        c = b["consumer"]
        notes = (f"after a trace p, a call y of {b['action']} taking the pin of {b['content']} records as "
                 f"{c['family']}.{c['member']} (the argument of {c['action']} {c['at']} {c['fn']}) the chooser of the "
                 "pinned content, or the content has no chooser (attribution: whose bond is at risk against who chose "
                 "the content), under the premises")
    binders = [{"q": "forall", "name": n, "type": t} for n, t in head]
    binders += [{"q": "forall", "name": h, "type": "Fn<Bytes,Word>"} for h in hashes]
    return {"ir_version": "holon-ir/0.3", "law_id": lid, "milestone": milestone, "rule": RULE,
            "subform": x["subform"], "rule_catalog_version": catalog_version, "facts": doc_rel,
            "facts_sha256": doc_sha, "notes": f"{notes}; fact {x['fact_id']}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"fact": x["fact_id"], "on": [{"var": y["name"]} for y in binders]},
                                           {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(lid: str, x: dict, doc_rel: str) -> dict:
    m = x["measure"]
    return {"law_id": lid, "rule": RULE, "subform": x["subform"], "facts": doc_rel, "basis": x["basis"],
            "premises": x["premises"], "measure": None if m is None else {"bits": m["bits"], "max_fiber": m["max_fiber"]}}


# ------------------------------------------------------------------------------------------------ the sidecar
class Sidecar:
    def __init__(self, path: Path, rel: str, doc: dict, root: Path):
        self.path, self.rel, self.doc, self.root = path, rel, doc, root

    @property
    def sort_types(self) -> str:
        return self.doc["sort_types"]

    @property
    def documents(self) -> list:
        return [str(x) for x in self.doc.get("documents") or []]

    @property
    def search(self) -> dict:
        return dict(self.doc.get("search") or {})

    @property
    def backtest(self) -> dict | None:
        return self.doc.get("backtest")


def _rel(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return f"<outside>/{Path(p).name}"


def resolve(path: str, root: Path) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return root / p if (root / p).exists() else Path.cwd() / p


def default_sidecar(milestone: str, root: Path) -> Path:
    return Path(root) / "spec" / milestone / "lib" / "fact.json"


def load_sidecar(milestone: str, root: Path, path: str | None = None) -> Sidecar:
    root = Path(root).resolve()
    p = resolve(path, root) if path else default_sidecar(milestone, root)
    if not p.is_file():
        raise Refused(f"the FACT sidecar {_rel(p, root)} does not exist")
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        raise Refused(f"{_rel(p, root)}: not JSON: {e}") from None
    if not isinstance(doc, dict) or doc.get("fact_version") != FACT_VERSION:
        raise Refused(f"{_rel(p, root)}: fact_version {doc.get('fact_version') if isinstance(doc, dict) else None!r} "
                      f"(want {FACT_VERSION})")
    for k in ("sort_types", "documents", "hypotheses", "search", "measure", "term_size"):
        if k not in doc:
            raise Refused(f"{_rel(p, root)}: no {k!r}")
    return Sidecar(p, _rel(p, root), doc, root)


def has_sidecar(milestone: str, root: Path, path: str | None = None) -> bool:
    return bool(path) or default_sidecar(milestone, root).is_file()


# ------------------------------------------------------------------------------------------------ producers
def _ctx_elements(ctx) -> list:
    root = Path(ctx.root)
    spath = getattr(ctx, "fact_sidecar", None)
    if not has_sidecar(ctx.milestone, root, spath):
        return []
    if getattr(ctx, "_fact_elements", None) is not None:
        return ctx._fact_elements
    try:
        sc = load_sidecar(ctx.milestone, root, spath)
    except Refused as e:
        raise FactError(str(e)) from e
    tsc = getattr(ctx, "sidecar", None)
    if tsc is not None and Path(sc.root / sc.sort_types).resolve() != Path(tsc.path).resolve():
        raise FactError(f"the FACT sidecar {sc.rel} reads {sc.sort_types}, not the typed-sorts sidecar {tsc.rel}")
    # DERIVATION lists the FACT sidecar; the obstructions document (the typed part's own inputs) does not
    inputs = getattr(ctx, "disch_inputs", None) or getattr(ctx, "inputs", None)
    if inputs is not None:
        inputs.read(sc.path)
    out = []
    for d in getattr(ctx, "typed_documents", []) or []:
        if sc.documents and d.rel not in sc.documents:
            continue
        an = analyse(d.facts, model_of(d.rel), sc.doc)
        out.append((d, an, hash_binders(d.facts)))
    ctx._fact_elements = out
    return out


class _Producer:
    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.fact.{subform}"

    def produce(self, ctx) -> list:
        out = []
        for d, an, hashes in _ctx_elements(ctx):
            for lid, x in an["laws"].items():
                if x["subform"] != self.subform:
                    continue
                law = law_ir(lid, x, ctx.milestone, d.rel, d.sha256, ctx.rule_catalog_version, hashes)
                out.append((law, entry_of(lid, x, d.rel)))
        return out


KERNEL = _Producer("kernel")
ATTRIBUTION = _Producer("attribution")
PRODUCERS = {"kernel": KERNEL, "attribution": ATTRIBUTION}


# ------------------------------------------------------------------------------------------------ the analysis document
def _transitions(d) -> bool:
    return isinstance(d, dict) and d.get("facts_version") == "holon-facts/0.3" and \
        (d.get("extraction") or {}).get("kind") == "transitions"


def analysis_document(milestone: str, root: Path, doc_rel: str, sidecar: dict, inputs: list) -> dict:
    p = root / doc_rel
    raw = p.read_bytes()
    d = json.loads(raw.decode("utf-8"))
    if not _transitions(d):
        raise Refused(f"{doc_rel}: not a holon-facts/0.3 transitions document")
    an = analyse(d, model_of(doc_rel), sidecar)
    ins = {x["path"]: x["sha256"] for x in inputs}
    ins[doc_rel] = sha256_bytes(raw)
    return {"document": "fact", "fact_version": FACT_VERSION, "milestone": milestone, "model": an["model"],
            "contract": an["contract"], "facts": doc_rel, "facts_sha256": sha256_bytes(raw),
            "inputs": [{"path": k, "sha256": v} for k, v in sorted(ins.items())],
            **{k: an[k] for k in ("commitments", "kernel", "attribution_consumers", "pins", "writers", "attribution",
                                  "laws")}}


# ------------------------------------------------------------------------------------------------ classification
def classification(milestone: str, root: Path, results: Path | None = None) -> dict:
    """Thm 6.8: a kernel law agrees iff (bits == 0) == (status == PROVED), with a status PROVED or REFUTED (UNKNOWN never
    agrees); attribution laws carry bits null and agree null."""
    root = Path(root)
    results = Path(results) if results else root / "results" / milestone
    dv = json.loads((root / "laws" / milestone / "DERIVATION.json").read_text(encoding="utf-8"))
    laws, dis = {}, []
    for e in dv.get("laws") or []:
        if e.get("rule") != RULE:
            continue
        lid = e["law_id"]
        rp = results / f"{lid}.json"
        st = json.loads(rp.read_text(encoding="utf-8")).get("status") if rp.is_file() else None
        if e.get("subform") == "kernel":
            bits = (e.get("measure") or {}).get("bits")
            agree = st in ("PROVED", "REFUTED") and bits is not None and (bits == 0) == (st == "PROVED")
            if not agree:
                dis.append(lid)
        else:
            bits, agree = None, None
        laws[lid] = {"subform": e.get("subform"), "bits": bits, "kernel": st, "agree": agree}
    return {"document": "fact_classification", "milestone": milestone, "laws": dict(sorted(laws.items())),
            "disagreements": sorted(dis)}


# ------------------------------------------------------------------------------------------------ the CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon fact")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--fact-sidecar", help="the FACT sidecar (default spec/<M>/lib/fact.json)")
    ap.add_argument("--facts", action="append", help="a planted transitions document to analyse instead")
    ap.add_argument("--out", help="output directory (default <root>/gen/<M>/fact)")
    ap.add_argument("--classify", action="store_true", help="write results/<M>/fact/classification.json")
    ap.add_argument("--backtest", action="store_true", help="write results/M3/fact/backtest.json and gen/M3/fact/backtest/")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        sc = load_sidecar(a.milestone, root, a.fact_sidecar)
        base = [{"path": sc.rel, "sha256": sha256_bytes(sc.path.read_bytes())}]
        written = {}
        if a.facts:
            for f in a.facts:
                p = resolve(f, root)
                if not p.is_file():
                    raise Refused(f"--facts {f}: no such document")
                rel = _rel(p, root)
                if rel.startswith("<outside>"):
                    rel = p.resolve().as_posix()
                    doc_rel_name = p.name
                    written[model_of(doc_rel_name)] = _outside_document(a.milestone, p, sc.doc, base)
                    continue
                written[model_of(rel)] = analysis_document(a.milestone, root, rel, sc.doc, base)
        else:
            for rel in sc.documents:
                if not (root / rel).is_file():
                    raise Refused(f"{rel}: the document the sidecar names does not exist")
                written[model_of(rel)] = analysis_document(a.milestone, root, rel, sc.doc, base)
    except Refused as e:
        print(f"holon fact: refused: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f"holon fact: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    out = Path(a.out).resolve() if a.out else root / "gen" / a.milestone / "fact"
    out.mkdir(parents=True, exist_ok=True)
    for model, doc in sorted(written.items()):
        (out / f"{model}.json").write_text(dumps(doc), encoding="utf-8")
        print(f"holon fact: {model}: {len(doc['commitments'])} commitments, {len(doc['kernel'])} kernel, "
              f"{len(doc['pins'])} pins, {len(doc['laws'])} laws -> {_rel(out / f'{model}.json', root)}")
    try:
        if a.classify:
            c = classification(a.milestone, root)
            p = root / "results" / a.milestone / "fact" / "classification.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(dumps(c), encoding="utf-8")
            print(f"holon fact: classification: {len(c['laws'])} laws, {len(c['disagreements'])} disagreements")
        if a.backtest:
            # imported by name: holon.rules.fact sits in the M1/M2 generator closure (through holon.gen.refs), the
            # back-test is no generator of theirs (holon.records.generator_files)
            import importlib
            b = importlib.import_module("holon.fact.backtest").write(a.milestone, root, sc)
            print(f"holon fact: back-test: {len(b['rows'])} rows, gaps {b['gaps']}, complete {b['complete']}")
    except Refused as e:
        print(f"holon fact: refused: {e}", file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError) as e:
        print(f"holon fact: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    return 0


def _outside_document(milestone: str, p: Path, sidecar: dict, inputs: list) -> dict:
    """A planted document outside the root (a test's variant): its path is named by its file name only."""
    raw = p.read_bytes()
    d = json.loads(raw.decode("utf-8"))
    if not _transitions(d):
        raise Refused(f"{p.name}: not a holon-facts/0.3 transitions document")
    rel = f"<outside>/{p.name}"
    an = analyse(d, model_of(p.name), sidecar)
    ins = {x["path"]: x["sha256"] for x in inputs}
    ins[rel] = sha256_bytes(raw)
    return {"document": "fact", "fact_version": FACT_VERSION, "milestone": milestone, "model": an["model"],
            "contract": an["contract"], "facts": rel, "facts_sha256": sha256_bytes(raw),
            "inputs": [{"path": k, "sha256": v} for k, v in sorted(ins.items())],
            **{k: an[k] for k in ("commitments", "kernel", "attribution_consumers", "pins", "writers", "attribution",
                                  "laws")}}
