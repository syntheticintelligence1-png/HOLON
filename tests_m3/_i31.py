"""I31 instrument (DISCH I: closure, blocking, external dependence), fixed at the I31 prereg (BUILD_PLAN §0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_disch.py, rules D0-D12. This module writes those rules out a second
time, independently of holon/, so that the tests can decide what holon must write. It reads a holon-facts/0.3
transitions document (the A19 format, holon/frontends/solidity/transitions.py's docstring) and a DISCH sidecar's
"r0" abstraction, nothing else; nothing here imports holon/.

  checks(action)            D1: every check of an action, with holon.machine's check id "<action>#<span>#<k>"
  classes(doc)              D2: the extracted principal classes, the permission check of every action
  value sets, ev, dead      D3, D4: the abstract values of register paths and the dead actions
  closure(doc, r0, X)       D5: the enableable write closure Write*_X, the least fixpoint from the deployment
  conjuncts(doc, r0)        D6, D7: every check's kind, the blocked condition B of every state conjunct
  analysis(doc, r0)         D8-D10: basis elements, per-basis closures, unsafe writers, named classes, and the laws
  disch_doc(root)           the frozen sidecar's "expected" section, recomputed from the committed inputs
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path

from tests_m3._m3 import ROOT

TOP = "T"           # the abstract value "any word"
NZ = "NZ"           # the abstract value "a non-zero word" (E-self: the length of the executing contract's code)
W256 = 1 << 256
SET_MAX = 16        # a finite set of more values is TOP
SIDECAR = Path("spec") / "M3" / "lib" / "disch.json"
INPUT_ENV = frozenset({"msg.value", "msg.data.length", "tx.origin", "tx.gasprice", "msg.sig", "msg.data", "block.number",
                       "block.coinbase", "block.prevrandao", "block.basefee", "block.blobbasefee", "block.chainid",
                       "block.gaslimit", "gasleft"})
LOOP_HEADS = frozenset({"iter", "count", "carried", "exit", "returned", "sum"})
EXTERNAL_HEADS = frozenset({"call", "callok", "caught", "sload", "balance", "codehash", "revertdata"})
SUBFORMS = ("blocking", "revert", "external", "external_none")


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def x8(o) -> str:
    return hashlib.sha256(canon(o).encode("utf-8")).hexdigest()[:8]


# ------------------------------------------------------------------ D1 checks
def checks(a: dict) -> list[dict]:
    """Every check of action a in walk (seq) order: guard reaches, panics, implicit checks and call checks (a call whose
    expr is not 1), each with holon.machine's id "<action>#<span>#<k>" (span: the guard's src for a reach, else the
    record's src; k counts the checks of that span in walk order, loop bodies included)."""
    raw = []
    for g in a.get("guards") or []:
        for r in g["reaches"]:
            raw.append(("guards", r, g))
    for sec in ("panics", "checks"):
        for r in a.get(sec) or []:
            raw.append((sec, r, r))
    for r in a.get("calls") or []:
        if "expr" in r and r["expr"] != 1:
            raw.append(("calls", r, r))
    raw.sort(key=lambda x: x[1]["seq"])
    counts: dict = {}
    out = []
    for sec, r, p in raw:
        span = p.get("src") or sec
        k = counts.get(span, 0)
        counts[span] = k + 1
        out.append({"id": f"{a['name']}#{span}#{k}", "section": sec, "span": span, "seq": r["seq"],
                    "expr": r.get("expr", p.get("expr")), "op": r.get("op") if sec == "panics" else None,
                    "code": r.get("code") if sec == "panics" else None, "loop": r.get("loop"),
                    "guard_kind": p.get("kind") if sec == "guards" else None})
    return out


# ------------------------------------------------------------------ term features
def feats(t, acc=None) -> dict:
    """The leaves a term reads: reg (storage families), ext (external terms), time, inp (inputs), self, loop."""
    if acc is None:
        acc = {k: set() for k in ("reg", "ext", "time", "inp", "self", "loop")}
    if isinstance(t, list) and t and not isinstance(t[0], str):
        for x in t:
            feats(x, acc)
        return acc
    if isinstance(t, list) and t:
        h = t[0]
        if h == "storage":
            acc["reg"].add(t[1])
            return acc
        if h == "env":
            if t[1] == "block.timestamp":
                acc["time"].add(t[1])
            else:
                acc["inp"].add("env:" + t[1])
            return acc
        if h == "caller":
            acc["inp"].add("caller")
            return acc
        if h == "param":
            acc["inp"].add("param:" + t[1])
            return acc
        if h == "blobhash":
            acc["inp"].add("blobhash")
        elif h == "code":
            if t[1:] == [["this"]]:
                acc["self"].add("code:this")
                return acc
            acc["ext"].add("code")
        elif h in ("call", "callok"):
            acc["ext"].add(t[1])
        elif h in EXTERNAL_HEADS:
            acc["ext"].add(h)
        elif h in LOOP_HEADS:
            acc["loop"].add(h)
        for x in t[1:]:
            feats(x, acc)
    return acc


def mentions_caller(t) -> bool:
    return "caller" in feats(t)["inp"]


# ------------------------------------------------------------------ D2 principal classes
def slug(span: str) -> str:
    """'<dir>/Rollup.sol:363' -> 'rollup_363'; a line range 'a-b' -> 'a_b'."""
    f, line = span.rsplit(":", 1)
    stem = f.rsplit("/", 1)[-1].split(".")[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", stem) + "_" + line.replace("-", "_")


def writes_something(a: dict) -> bool:
    return bool(a.get("writes"))


def permission_check(a: dict) -> str | None:
    """D2: the check id of the action's permission guard: the first reach of the guard whose first reach's expr is
    I19's principal predicate (when the action has a principal), else the first guard (walk order of first reaches)
    whose first reach's expr mentions ["caller"]; None when there is none."""
    gs = sorted(a.get("guards") or [], key=lambda g: g["reaches"][0]["seq"])
    target = None
    if a.get("principal"):
        pred = canon(a["principal"]["predicate"])
        target = next((g for g in gs if canon(g["reaches"][0]["expr"]) == pred), None)
        if target is None:
            raise ValueError(f"{a['name']}: the principal predicate is no guard of the action")
    else:
        target = next((g for g in gs if mentions_caller(g["reaches"][0]["expr"])), None)
    if target is None:
        return None
    seq = target["reaches"][0]["seq"]
    return next(c["id"] for c in checks(a) if c["seq"] == seq)


def classes(doc: dict) -> dict:
    """D2: {"of": {action: class id}, "classes": {cid: {"predicate", "actions"}}, "permission": {action: check id |
    None}} over the actions with at least one write record."""
    acts = {a["name"]: a for a in doc["actions"]}
    of, cls, perm = {}, {}, {}
    for n in sorted(acts):
        a = acts[n]
        if not writes_something(a):
            continue
        pid = permission_check(a)
        if a.get("principal"):
            cid = a["principal"]["modifier"]
        elif pid:
            cid = "caller_" + slug(pid.split("#")[1])
        else:
            cid = "anyone"
        pred = None
        if pid:
            pred = next(c["expr"] for c in checks(a) if c["id"] == pid)
        if cid in cls and canon(cls[cid]["predicate"]) != canon(pred):
            raise ValueError(f"class {cid}: two predicates")
        cls.setdefault(cid, {"predicate": pred, "actions": []})["actions"].append(n)
        of[n] = cid
        perm[n] = pid
    keys = {}
    for cid, c in cls.items():
        k = canon(c["predicate"])
        if k in keys:
            raise ValueError(f"classes {keys[k]} and {cid} share a predicate")
        keys[k] = cid
    return {"of": of, "classes": cls, "permission": perm}


def callable_by(cl: dict, X: str) -> list[str]:
    return sorted(set(cl["classes"][X]["actions"]) | set(cl["classes"].get("anyone", {"actions": []})["actions"]))


# ------------------------------------------------------------------ D3 register paths, value sets, evaluation
def struct_members(doc: dict) -> dict:
    out = {}
    for s in doc.get("storage") or []:
        if s.get("fields"):
            out[s["name"]] = [f["name"] for f in s["fields"]]
    return out


def bool_paths(doc: dict) -> set:
    out = set()
    for s in list(doc.get("storage") or []) + list(doc.get("inherited_storage") or []):
        if s.get("fields"):
            out |= {f"{s['name']}.{f['name']}" for f in s["fields"] if f.get("type") == "bool"}
        elif s.get("value") == "bool":
            out.add(s["name"])
    return out


def scalar_families(doc: dict) -> set:
    out = set()
    for s in list(doc.get("storage") or []) + list(doc.get("inherited_storage") or []):
        if s.get("kind") == "scalar":
            out.add(s["name"])
    return out


def rpath(t):
    """The register path of a read term: 'family' (a scalar, a mapping's or array's values) or 'family.member' (a member
    of a struct family); keys are ignored. None when t is not a storage read."""
    if not isinstance(t, list) or not t:
        return None
    if t[0] == "storage":
        return t[1]
    if t[0] in ("map", "index"):
        return rpath(t[1])
    if t[0] == "member":
        b = rpath(t[1])
        return f"{b}.{t[2]}" if b is not None else None
    return None


def const(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else TOP


def write_values(doc: dict, w: dict) -> list[tuple[str, object]]:
    """D3: the (path, abstract value) pairs one write record contributes."""
    sm = struct_members(doc)
    fam, path, v = w["family"], w.get("path") or [], w.get("value")
    members = [p[1] for p in path if p[0] == "member"]
    if members:
        return [(f"{fam}.{members[-1]}", const(v))]
    if fam in sm:
        if isinstance(v, list) and v and v[0] == "struct":
            vals = {m: x for m, x in v[2]}
            return [(f"{fam}.{m}", const(vals.get(m, 0))) for m in sm[fam]]
        return [(f"{fam}.{m}", 0 if v == 0 else TOP) for m in sm[fam]]
    return [(fam, const(v))]


def all_paths(doc: dict) -> list[str]:
    sm = struct_members(doc)
    ps = set()
    for s in list(doc.get("storage") or []) + list(doc.get("inherited_storage") or []):
        if s["name"] == "__gap":
            continue
        if s["name"] in sm:
            ps |= {f"{s['name']}.{m}" for m in sm[s["name"]]}
        else:
            ps.add(s["name"])
    return sorted(ps)


def r0_sets(doc: dict, r0: dict) -> dict:
    """The deployment's abstract values: every path {0} unless the sidecar's r0 "values" names it."""
    vals = (r0 or {}).get("values") or {}
    out = {}
    for p in all_paths(doc):
        out[p] = set(TOP if x == TOP else x for x in vals.get(p, [0]))
    unknown = sorted(set(vals) - set(out))
    if unknown:
        raise ValueError(f"r0 names paths the document does not declare: {unknown}")
    return out


def value_sets(doc: dict, r0: dict, actions) -> dict:
    """V: the deployment's values plus every value the writes of `actions` contribute."""
    acts = {a["name"]: a for a in doc["actions"]}
    V = r0_sets(doc, r0)
    for n in sorted(actions):
        for w in acts[n].get("writes") or []:
            for p, v in write_values(doc, w):
                V.setdefault(p, {0}).add(v)
    return V


def _truth(x):
    if x == TOP:
        return {0, 1}
    if x == NZ:
        return {1}
    return {int(v != 0) for v in x}


def ev(t, V):
    """D3: the abstract value of a term: a finite set of words, TOP or NZ."""
    if isinstance(t, bool):
        return {int(t)}
    if isinstance(t, int):
        return {t % W256}
    if not isinstance(t, list) or not t:
        return TOP
    h = t[0]
    p = rpath(t)
    if p is not None:
        vs = V.get(p, {0})
        return TOP if TOP in vs else set(vs)
    if h == "len" and t[1:] == [["code", ["this"]]]:
        return NZ
    if h == "!":
        x = ev(t[1], V)
        return TOP if x == TOP else ({0} if x == NZ else {int(v == 0) for v in x})
    if h in ("&&", "||"):
        vals = [_truth(ev(x, V)) for x in t[1:]]
        if h == "&&":
            if any(v == {0} for v in vals):
                return {0}
            return {1} if all(v == {1} for v in vals) else {0, 1}
        if any(v == {1} for v in vals):
            return {1}
        return {0} if all(v == {0} for v in vals) else {0, 1}
    if h == "?":
        c = _truth(ev(t[1], V))
        a, b = ev(t[2], V), ev(t[3], V)
        if c == {1}:
            return a
        if c == {0}:
            return b
        if not isinstance(a, set) or not isinstance(b, set):
            return TOP
        r = a | b
        return r if len(r) <= SET_MAX else TOP
    if h in ("==", "!=", "<", "<=", ">", ">="):
        a, b = ev(t[1], V), ev(t[2], V)
        if a == NZ and b == {0}:
            return {1} if h in ("!=", ">", ">=") else {0}
        if b == NZ and a == {0}:
            return {1} if h in ("!=", "<", "<=") else {0}
        if not isinstance(a, set) or not isinstance(b, set):
            return {0, 1}
        f = {"==": lambda x, y: x == y, "!=": lambda x, y: x != y, "<": lambda x, y: x < y,
             "<=": lambda x, y: x <= y, ">": lambda x, y: x > y, ">=": lambda x, y: x >= y}[h]
        return {int(f(x, y)) for x in a for y in b}
    if h in ("+", "-", "*"):
        a, b = ev(t[1], V), ev(t[2], V)
        if not isinstance(a, set) or not isinstance(b, set):
            return TOP
        f = {"+": lambda x, y: x + y, "-": lambda x, y: x - y, "*": lambda x, y: x * y}[h]
        r = {f(x, y) % W256 for x in a for y in b}
        return r if len(r) <= SET_MAX else TOP
    if h == "fits":
        n, e = t[1], t[2]
        if isinstance(e, list) and e and e[0] in ("+", "-", "*"):
            a, b = ev(e[1], V), ev(e[2], V)
            if not isinstance(a, set) or not isinstance(b, set):
                return {0, 1}
            f = {"+": lambda x, y: x + y, "-": lambda x, y: x - y, "*": lambda x, y: x * y}[e[0]]
            return {int(0 <= f(x, y) < (1 << n)) for x in a for y in b}
        return {0, 1}
    return TOP


def definitely_false(e, V) -> bool:
    return _truth(ev(e, V)) == {0}


# ------------------------------------------------------------------ D4 dead actions, D5 the closure
def dead_actions(doc: dict, r0: dict, cl: dict) -> dict:
    """D4: action -> the first check (walk order) that is definitely false under the values of every write of every
    action, from the deployment."""
    acts = {a["name"]: a for a in doc["actions"]}
    V = value_sets(doc, r0, cl["of"])
    out = {}
    for n in sorted(cl["of"]):
        for c in checks(acts[n]):
            if definitely_false(c["expr"], V):
                out[n] = c["id"]
                break
    return out


def effects(doc: dict, n: str) -> set:
    """The register paths an action writes and its external effects 'call:<fn>' (calls that are not view or pure)."""
    a = next(x for x in doc["actions"] if x["name"] == n)
    out = set()
    for w in a.get("writes") or []:
        out |= {p for p, _ in write_values(doc, w)}
    for c in a.get("calls") or []:
        if c.get("mutability") not in ("view", "pure"):
            out.add("call:" + c["fn"])
    return out


def closure(doc: dict, r0: dict, cl: dict, X: str, dead: dict) -> dict:
    """D5: the least fixpoint. Act_0 = {}; V_i = the deployment's values plus the writes of Act_i; Act_{i+1} = the
    actions callable by X, not dead, none of whose checks but its own permission check is definitely false under
    V_i. Stops when Act is stable. Write*_X = the effects of Act."""
    acts = {a["name"]: a for a in doc["actions"]}
    cand = [n for n in callable_by(cl, X) if n not in dead]
    act: set = set()
    rounds = 0
    while True:
        V = value_sets(doc, r0, act)
        new = {n for n in cand if not any(c["id"] != cl["permission"][n] and definitely_false(c["expr"], V)
                                          for c in checks(acts[n]))}
        rounds += 1
        if new == act:
            break
        act = new
    V = value_sets(doc, r0, act)
    excluded = {}
    for n in cand:
        if n not in act:
            excluded[n] = next(c["id"] for c in checks(acts[n])
                               if c["id"] != cl["permission"][n] and definitely_false(c["expr"], V))
    wc = set()
    for n in act:
        wc |= effects(doc, n)
    return {"actions": sorted(act), "excluded": dict(sorted(excluded.items())), "write_closure": sorted(wc),
            "rounds": rounds}


# ------------------------------------------------------------------ D6 kinds, D7 blocked conditions, signs
def neg(x):
    if isinstance(x, list) and x and x[0] == "!":
        return x[1]
    return ["!", x]


def split(e):
    """(kappa, rho): ["||", ["!", K], R..] -> (K, R or ["||", R..]); anything else -> (1, e)."""
    if isinstance(e, list) and e and e[0] == "||" and len(e) >= 3 and isinstance(e[1], list) and e[1][:1] == ["!"]:
        rest = e[2:]
        return e[1][1], (rest[0] if len(rest) == 1 else ["||"] + rest)
    return 1, e


def flat_and(x) -> list:
    if isinstance(x, list) and x and x[0] == "&&":
        return [y for z in x[1:] for y in flat_and(z)]
    return [] if x == 1 else [x]


def plus_terms(t, acc=None) -> list:
    """Distinct ["+", a, b] subterms of t, in depth-first first-occurrence order."""
    if acc is None:
        acc = []
    if isinstance(t, list) and t:
        if t[0] == "+" and len(t) == 3 and canon(t) not in {canon(x) for x in acc}:
            acc.append(t)
        for x in t[1:]:
            plus_terms(x, acc)
    return acc


def blocked_atoms(e) -> list:
    """D7: the atoms of B_c = kappa and not rho, with the no-overflow condition of every checked sum inside rho:
    flat_and(kappa) ++ [neg(d) for d in rho's disjuncts] ++ [["fits", 256, s] for every ["+", a, b] subterm s of rho]."""
    k, r = split(e)
    atoms = flat_and(k)
    ds = r[1:] if isinstance(r, list) and r and r[0] == "||" else [r]
    atoms += [neg(d) for d in ds]
    atoms += [["fits", 256, s] for s in plus_terms(r)]
    return atoms


def blocked_term(atoms: list):
    return atoms[0] if len(atoms) == 1 else ["&&"] + atoms


TIME = ["env", "block.timestamp"]


def _contains(t, target) -> bool:
    if target == "time":
        if canon(t) == canon(TIME):
            return True
    elif rpath(t) == target:
        return True
    return isinstance(t, list) and any(_contains(x, target) for x in t[1:])


def _comb(*ss):
    ss = [s for s in ss if s != "0"]
    if not ss:
        return "0"
    if "?" in ss:
        return "?"
    return ss[0] if all(s == ss[0] for s in ss) else "?"


def _flip(s):
    return {"+": "-", "-": "+"}.get(s, s)


def sign(t, target) -> str:
    """D9: the monotonicity of the truth of t in a register path (or 'time'): '+' (increasing), '-' (decreasing), '0'
    (not read), '?' (unknown). Arithmetic is read as exact (B_c carries the no-overflow atoms of its sums)."""
    if not _contains(t, target):
        return "0"
    if target == "time" and canon(t) == canon(TIME):
        return "+"
    if target != "time" and rpath(t) == target:
        k = t
        while isinstance(k, list) and k and k[0] in ("member", "map", "index"):
            if k[0] in ("map", "index") and _contains(k[2], target):
                return "?"
            k = k[1]
        return "+"
    if not isinstance(t, list) or not t:
        return "0"
    h = t[0]
    if h == "!":
        return _flip(sign(t[1], target))
    if h in ("&&", "||"):
        return _comb(*[sign(x, target) for x in t[1:]])
    if h in ("<", "<="):
        return _comb(_flip(sign(t[1], target)), sign(t[2], target))
    if h in (">", ">="):
        return _comb(sign(t[1], target), _flip(sign(t[2], target)))
    if h == "+":
        return _comb(sign(t[1], target), sign(t[2], target))
    if h == "-":
        return _comb(sign(t[1], target), _flip(sign(t[2], target)))
    if h == "fits":
        e = t[2]
        if isinstance(e, list) and e and e[0] == "-":
            return _comb(sign(e[1], target), _flip(sign(e[2], target)))
        if isinstance(e, list) and e and e[0] == "+":
            return _flip(_comb(sign(e[1], target), sign(e[2], target)))
        return "?"
    return "?"


def kind_of(c: dict, perm_id: str | None, V_all: dict) -> str:
    """D6: permission | external | input | loop | panic | never | time | state."""
    if c["id"] == perm_id:
        return "permission"
    f = feats(c["expr"])
    if f["ext"]:
        return "external"
    if f["inp"]:
        return "input"
    if f["loop"] or c.get("loop") is not None:
        return "loop"
    if c["section"] == "panics" and not (c["code"] == 17 and c["op"] == "-"):
        return "panic"
    if c["section"] not in ("guards", "panics"):
        return "input"
    B = blocked_term(blocked_atoms(c["expr"]))
    if definitely_false(B, V_all):
        return "never"
    if sign(B, "time") not in ("+", "0"):
        return "time"
    return "state"


def reads(t, acc=None) -> set:
    if acc is None:
        acc = set()
    p = rpath(t)
    if p is not None:
        acc.add(p)
    if isinstance(t, list):
        for x in t[1:]:
            reads(x, acc)
    return acc


# ------------------------------------------------------------------ D8-D10 the analysis
def analysis(doc: dict, r0: dict, model: str) -> dict:
    """Everything holon disch and holon derive must compute for one transitions document (rules D1-D10)."""
    acts = {a["name"]: a for a in doc["actions"]}
    cl = classes(doc)
    dead = dead_actions(doc, r0, cl)
    V_all = value_sets(doc, r0, cl["of"])
    bools = bool_paths(doc)
    clos = {X: closure(doc, r0, cl, X, dead) for X in sorted(cl["classes"])}
    # D6: kinds
    rows = []
    for n in sorted(cl["of"]):
        if n in dead:
            continue
        for c in checks(acts[n]):
            k = kind_of(c, cl["permission"][n], V_all)
            row = {"id": c["id"], "action": n, "class": cl["of"][n], "kind": k, "span": c["span"]}
            if k == "external":
                row["external"] = sorted(feats(c["expr"])["ext"])
            rows.append((row, c))
    # D7: basis elements (B, X)
    by_b: OrderedDict = OrderedDict()
    for row, c in rows:
        if row["kind"] != "state":
            continue
        atoms = blocked_atoms(c["expr"])
        B = blocked_term(atoms)
        by_b.setdefault(canon(B), {"B": B, "atoms": atoms, "checks": []})["checks"].append((row, c))
    bdocs = []
    lawlist = []
    for bk in sorted(by_b, key=lambda k: min((slug(r["span"]), r["id"]) for r, _ in by_b[k]["checks"])):
        g = by_b[bk]
        B, atoms = g["B"], g["atoms"]
        rep_row, rep = min(g["checks"], key=lambda rc: (rc[0]["span"], rc[0]["id"]))
        tag = f"{slug(rep_row['span'])}_{x8(B)}"
        atom_keys = {canon(x) for x in atoms}
        # D8: excluded under B (any class): a check equal to the representative's expr, or whose negation is an atom
        excl = {}
        for n in sorted(cl["of"]):
            if n in dead:
                continue
            for c in checks(acts[n]):
                if canon(c["expr"]) == canon(rep["expr"]) or canon(neg(c["expr"])) in atom_keys:
                    excl[n] = c["id"]
                    break
        rd = reads(B)

        def unsafe(n):
            """D9: the paths of B's reads an action may move against B (empty: frame or safe)."""
            out = set()
            a = acts[n]
            post_const = {}
            for p, v in (a.get("post") or {}).items():
                if isinstance(v, int) and not isinstance(v, bool):
                    post_const[p] = v
            cand = set()
            for w in a.get("writes") or []:
                for p, v in write_values(doc, w):
                    if p not in rd:
                        continue
                    s = sign(B, p)
                    if s == "0" or (s == "-" and v == 0) or (s == "+" and v == 1 and p in bools):
                        continue
                    cand.add(p)
            if cand and all(p in post_const for p in cand):
                Vp = {p: {0, 1} if p in bools else {TOP} for p in rd}
                for p in cand:
                    Vp[p] = {post_const[p]}
                if _truth(ev(B, Vp)) == {1}:
                    return set()
            return cand

        classes_with = sorted({cl["of"][r["id"].split("#")[0]] for r, _ in g["checks"]})
        per_x = {}
        for X in classes_with:
            cl_x = [n for n in callable_by(cl, X) if n not in dead and n not in excl]
            uns = {n: sorted(unsafe(n)) for n in cl_x}
            uns = {n: p for n, p in uns.items() if p}
            status = "self" if uns else "blocked"
            named = {}
            if status == "blocked":
                for Y in sorted(cl["classes"]):
                    if Y == X:
                        continue
                    ys = [n for n in callable_by(cl, Y) if n not in callable_by(cl, X) and n not in dead and n not in excl]
                    yu = sorted(n for n in ys if unsafe(n))
                    if yu:
                        named[Y] = yu
            per_x[X] = {"closure": cl_x, "unsafe": uns, "status": status, "named": named,
                        "checks": sorted(r["id"] for r, _ in g["checks"] if r["class"] == X)}
        bdocs.append({"tag": tag, "blocked": B, "check": rep_row["id"], "check_expr": rep["expr"],
                      "checks": sorted(r["id"] for r, _ in g["checks"]), "excluded": excl, "classes": per_x,
                      "time": sign(B, "time")})
        for X in classes_with:
            lawlist.append({"law_id": f"L_disch_blk_{tag}_{X}", "subform": "blocking", "tag": tag, "class": X,
                            "closure": per_x[X]["closure"], "status": per_x[X]["status"]})
        lawlist.append({"law_id": f"L_disch_rev_{tag}", "subform": "revert", "tag": tag, "class": None,
                        "excluded": sorted(excl)})
        ys = sorted({Y for X in classes_with for Y in per_x[X]["named"]})
        for Y in ys:
            blocked_for = sorted(X for X in classes_with if Y in per_x[X]["named"])
            writers = sorted({n for X in blocked_for for n in per_x[X]["named"][Y]})
            ycl = [n for n in callable_by(cl, Y) if n not in dead and n not in excl]
            for sf, prefix in (("external", "L_disch_ext_"), ("external_none", "L_disch_noext_")):
                lawlist.append({"law_id": f"{prefix}{tag}_{Y}", "subform": sf, "tag": tag, "class": Y,
                                "blocked_for": blocked_for, "writers": writers, "closure": ycl})
    lawlist.sort(key=lambda x: x["law_id"])
    ext: dict = {}
    for row, c in rows:
        for fn in row.get("external", []):
            comp = fn.split(".")[0] if "." in fn else fn
            e = ext.setdefault(comp, {"checks": [], "actions": set(), "classes": set(), "functions": set()})
            e["checks"].append(row["id"])
            e["actions"].add(row["action"])
            e["classes"].add(row["class"])
            e["functions"].add(fn)
    ext = {k: {"checks": sorted(set(v["checks"])), "actions": sorted(v["actions"]), "classes": sorted(v["classes"]),
               "functions": sorted(v["functions"])} for k, v in sorted(ext.items())}
    kinds: dict = {}
    for row, _ in rows:
        kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
    return {"model": model,
            "classes": {cid: {"predicate": c["predicate"], "actions": sorted(c["actions"]),
                              "external": sorted(feats(c["predicate"])["ext"]) if c["predicate"] is not None else []}
                        for cid, c in sorted(cl["classes"].items())},
            "permission": dict(sorted(cl["permission"].items())), "dead": dead, "closure": clos,
            "kinds": dict(sorted(kinds.items())), "checks": [r for r, _ in rows], "external": ext,
            "basis": bdocs, "laws": lawlist}


def with_hypotheses(an: dict, hypotheses: dict, verdicts: dict | None) -> dict:
    """Each external component's hypothesis (the sidecar's "hypotheses": component -> M2 hypothesis name or null) and
    I21's record of it (a4.json "hypotheses"[name]: its "verdict" (tested, untestable), "result" (pass, fail, null)
    and "finding"), copied as {"name", "verdict", "result", "finding"}; null for a component no hypothesis covers."""
    for comp, e in an["external"].items():
        name = (hypotheses or {}).get(comp)
        if name is None:
            e["hypothesis"] = None
            continue
        rec = ((verdicts or {}).get("hypotheses") or {}).get(name) or {}
        e["hypothesis"] = {"name": name, "verdict": rec.get("verdict"), "result": rec.get("result"),
                           "finding": rec.get("finding")}
    return an


def entries(an: dict) -> dict:
    """D12: the statement-independent part of every DISCH entry of DERIVATION.json, by law id."""
    basis = {b["tag"]: b for b in an["basis"]}
    out = {}
    for law in an["laws"]:
        b = basis[law["tag"]]
        sf = law["subform"]
        ent = {"law_id": law["law_id"], "rule": "DISCH", "subform": sf,
               "basis": {"kind": "guard_conjunct", "model": an["model"], "tag": b["tag"], "check": b["check"],
                         "checks": b["checks"], "blocked": b["blocked"], "class": law["class"]}}
        if sf == "blocking":
            ent.update(status=law["status"], closure=law["closure"], excluded=[], entry_points=law["closure"])
        elif sf == "revert":
            ent.update(closure=[], excluded=law["excluded"], entry_points=law["excluded"])
        else:
            ent.update(closure=law["closure"], excluded=[], entry_points=law["closure"],
                       blocked_for=law["blocked_for"], writers=law["writers"])
        out[law["law_id"]] = ent
    return out


def disch_id(an: dict, law: dict) -> str:
    """D11: the disch term's id "<model>:<subform>:<tag>:<class>" (class "all" for revert)."""
    return f"{an['model']}:{law['subform']}:{law['tag']}:{law['class'] or 'all'}"


def ref_doc(an: dict, law: dict) -> dict:
    """D11: the document whose sha256 is the ref "disch:<ID>"."""
    b = next(x for x in an["basis"] if x["tag"] == law["tag"])
    ent = entries(an)[law["law_id"]]
    return {"template": f"holon.rules.disch/{law['subform']}", "template_version": 1, "subform": law["subform"],
            "model": an["model"], "blocked": b["blocked"], "check": b["check"], "check_expr": b["check_expr"],
            "class": law["class"], "closure": ent["closure"], "excluded": ent["excluded"]}


# ------------------------------------------------------------------ the sidecar
def load_sidecar(root: Path = ROOT, rel=SIDECAR) -> dict:
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def model_name(doc_rel: str) -> str:
    return Path(doc_rel).name[: -len(".json")] if doc_rel.endswith(".json") else Path(doc_rel).name


def expected(root: Path = ROOT, rel=SIDECAR, docs: dict | None = None) -> dict:
    """The analysis of every document of a DISCH sidecar (rules D1-D10, with each external component's hypothesis),
    from the committed inputs; `docs` may replace a document's content by path (a mutation test)."""
    side = load_sidecar(root, rel)
    verdicts = None
    if side.get("hypothesis_verdicts"):
        verdicts = json.loads((Path(root) / side["hypothesis_verdicts"]).read_text(encoding="utf-8"))
    out = {}
    for d in side["documents"]:
        doc = (docs or {}).get(d) or json.loads((Path(root) / d).read_text(encoding="utf-8"))
        an = analysis(doc, side.get("r0"), model_name(d))
        out[model_name(d)] = with_hypotheses(an, side.get("hypotheses") or {}, verdicts)
    return out


def summary(an: dict) -> dict:
    """The compact form the frozen sidecar records ("expected"): classes, dead actions, closures, kind counts, the
    external components, the basis and the laws."""
    return {
        "classes": {k: {"actions": v["actions"], "external": v["external"]} for k, v in an["classes"].items()},
        "permission": an["permission"],
        "dead": an["dead"],
        "closure": an["closure"],
        "kinds": an["kinds"],
        "external": an["external"],
        "basis": [{"tag": b["tag"], "check": b["check"], "checks": b["checks"], "blocked": b["blocked"],
                   "excluded": b["excluded"], "time": b["time"],
                   "classes": {X: {"status": v["status"], "closure": v["closure"], "unsafe": v["unsafe"],
                                   "named": v["named"]} for X, v in b["classes"].items()}}
                  for b in an["basis"]],
        "laws": an["laws"],
    }
