"""DISCH I: guard conjuncts, principal classes and the enableable write closure of an extracted transitions document
(BUILD_PLAN I31; whitepaper §5.7, Thm 6.10, §11.5, §8.3 "principal class", §8.4 and App. E's DISCH row). The contract
is the docstring of tests_m3/test_disch.py, rules D1-D10.

  python -m holon disch --milestone M [--root DIR] [--sidecar PATH] [--out DIR] [--check]

reads the milestone's DISCH sidecar (spec/<M>/lib/disch.json, or --sidecar: "documents", "r0", "hypotheses",
"hypothesis_verdicts", "inputs") and each transitions document it names, and writes <out>/closure.json and
<out>/conjuncts.json (default out gen/<M>/disch). Exit 0 written; 1 with --check when a file differs from a fresh run
(nothing written); 2 refused, nothing written (the sidecar or a document missing or malformed, an "inputs" sha256 that
does not match); 3 a construct D2 refuses (named).

The analysis, per document:
  D1 checks(action)          every check (guard reaches, panics, implicit checks, calls whose expr is not 1) with
                             holon.machine's id "<action>#<span>#<k>"
  D2 classes(doc)            the principal classes over the actions with a write record, each action's permission check
  D3 values                  abstract values of register paths (finite sets of words, TOP, NZ) from the deployment
  D4 dead                    actions with a check definitely false under the values of every write
  D5 closure(X)              the least fixpoint Act_X from the deployment; Write*_X its paths and external effects
  D6 kinds                   permission, external, input, loop, panic, never, time, state
  D7 blocked conditions      B_c of every state conjunct; basis elements (B, X)
  D8 exclusions              actions that revert whenever B holds
  D9 signs, unsafe writers   blocked / self, named classes and their writers
  D10 laws                   blocking, revert, external, external_none

Nothing here names a target: every name, span and term comes from the document and the sidecar. The analysis is
static and ignores keys (a write at another key counts); external terms are unknown (A-env), except E-self (the code of
the executing contract is not empty) and the deployment's abstraction r0, which the sidecar states.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "holon-disch/0.1"
SUBFORMS = ("blocking", "revert", "external", "external_none")
LAW_PREFIX = {"blocking": "L_disch_blk_", "revert": "L_disch_rev_", "external": "L_disch_ext_",
              "external_none": "L_disch_noext_"}
ANYONE = "anyone"
MOD = 2 ** 256          # D3: + - * are taken modulo 2^256
WIDE = 16               # D3: an arithmetic result with more values than this is TOP
CLOCK = ["env", "block.timestamp"]


class Refused(ValueError):
    """Exit 2: an input missing, malformed or stale."""


class ClassError(ValueError):
    """Exit 3: a construct rule D2 refuses."""


def canon(o) -> str:
    """canonical(o) of the contract: sorted keys, no spaces, UTF-8 text."""
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def x8(o) -> str:
    return hashlib.sha256(canon(o).encode("utf-8")).hexdigest()[:8]


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True) + "\n"


def slug(span: str) -> str:
    """D2's slug(span): the file name's stem, lower-cased, every run of characters outside [a-z0-9] replaced by "_",
    then "_" and the line ("a-b" gives "a_b")."""
    file_part, _, line = span.rpartition(":")
    stem = file_part.split("/")[-1].split(".", 1)[0].lower()
    return "_".join([re.sub("[^a-z0-9]+", "_", stem), line.replace("-", "_")])


def model_name(doc_rel: str) -> str:
    name = Path(doc_rel).name
    return name[:-5] if name.endswith(".json") else name


def _head(t):
    return t[0] if isinstance(t, list) and t and isinstance(t[0], str) else None


def _subterms(t):
    """Every subterm of t, t first, depth first (a list whose first element is not a string is a plain list)."""
    yield t
    if isinstance(t, list):
        for x in (t[1:] if _head(t) is not None else t):
            yield from _subterms(x)


# ================================================================================================ D1 checks
def checks(action: dict) -> list[dict]:
    """D1: every check of an action, in walk (seq) order: each reach of each guard (its span the guard's src), each
    panic, each implicit check and each call whose expr is not 1 (its span its own src); id "<action>#<span>#<k>"
    with k the number of earlier checks (walk order) on that span."""
    found = []
    for g in action.get("guards") or []:
        for r in g.get("reaches") or []:
            found.append({"seq": r["seq"], "span": g.get("src"), "expr": r.get("expr"), "section": "guards"})
    for p in action.get("panics") or []:
        found.append({"seq": p["seq"], "span": p.get("src"), "expr": p.get("expr"), "section": "panics",
                      "code": p.get("code"), "op": p.get("op"), "loop": p.get("loop")})
    for c in action.get("checks") or []:
        found.append({"seq": c["seq"], "span": c.get("src"), "expr": c.get("expr"), "section": "checks",
                      "loop": c.get("loop")})
    for c in action.get("calls") or []:
        if "expr" in c and c["expr"] != 1:
            found.append({"seq": c["seq"], "span": c.get("src"), "expr": c["expr"], "section": "calls",
                          "loop": c.get("loop")})
    found.sort(key=lambda r: r["seq"])
    used: dict = {}
    for r in found:
        k = used.get(r["span"], 0)
        used[r["span"]] = k + 1
        r["id"] = "#".join([action["name"], str(r["span"]), str(k)])
    return found


# ================================================================================================ D3 register paths
def register_path(t) -> str | None:
    """The register path a storage read reads: "family", or "family.member" for a struct member; keys ignored."""
    h = _head(t)
    if h == "storage":
        return t[1]
    if h in ("map", "index"):
        return register_path(t[1])
    if h == "member":
        inner = register_path(t[1])
        return None if inner is None else inner + "." + t[2]
    return None


class Layout:
    """The document's storage declarations: struct families and their members, bool paths, scalar families."""

    def __init__(self, doc: dict):
        decls = list(doc.get("storage") or []) + list(doc.get("inherited_storage") or [])
        self.members = {d["name"]: [f["name"] for f in d["fields"]] for d in decls if d.get("fields")}
        self.paths = set()
        self.bools = set()
        self.scalars = set()
        for d in decls:
            if d["name"] == "__gap":
                continue
            if d.get("fields"):
                for f in d["fields"]:
                    self.paths.add(d["name"] + "." + f["name"])
                    if f.get("type") == "bool":
                        self.bools.add(d["name"] + "." + f["name"])
            else:
                self.paths.add(d["name"])
                if d.get("value") == "bool":
                    self.bools.add(d["name"])
                if d.get("kind") == "scalar":
                    self.scalars.add(d["name"])

    def written(self, w: dict) -> list[tuple[str, object]]:
        """D3: (path, contribution) of a write record: a literal integer contributes itself, a struct literal each
        member's literal (TOP for a member that is not one), a delete (0) of a struct path 0 to every member, any
        other value TOP."""
        fam, val = w["family"], w.get("value")
        member = None
        for step in w.get("path") or []:
            if step and step[0] == "member":
                member = step[1]
        lit = lambda v: v if type(v) is int else TOP   # noqa: E731
        if member is not None:
            return [(fam + "." + member, lit(val))]
        if fam not in self.members:
            return [(fam, lit(val))]
        if _head(val) == "struct":
            given = dict((m, v) for m, v in val[2])
            return [(fam + "." + m, lit(given[m]) if m in given else TOP) for m in self.members[fam]]
        return [(fam + "." + m, 0 if val == 0 else TOP) for m in self.members[fam]]


# ================================================================================================ D3 abstract values
class _Abs:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name


TOP = _Abs("T")     # any word
NZ = _Abs("NZ")     # some non-zero word (E-self: the executing contract's code is not empty)
UNKNOWN = frozenset({0, 1})


def _store(doc: dict, layout: Layout, r0: dict | None, actions) -> dict:
    """V: R0 (the sidecar's r0 "values", "T" for TOP; {0} for every other path) joined with the contributions of the
    write records of `actions`."""
    given = (r0 or {}).get("values") or {}
    unknown = sorted(p for p in given if p not in layout.paths)
    if unknown:
        raise Refused(f"r0 names paths the document does not declare: {unknown}")
    V = {p: set(TOP if x == "T" else x for x in given[p]) if p in given else {0} for p in layout.paths}
    acts = {a["name"]: a for a in doc["actions"]}
    for n in sorted(actions):
        for w in acts[n].get("writes") or []:
            for p, x in layout.written(w):
                V.setdefault(p, {0}).add(x)
    return V


def deployment_values(doc: dict, r0: dict | None) -> dict:
    return _store(doc, Layout(doc), r0, ())


def _truth(v) -> frozenset:
    """The truth values an abstract value can take."""
    if v is TOP:
        return UNKNOWN
    if v is NZ:
        return frozenset({1})
    return frozenset(int(x != 0) for x in v)


def _bool_set(ts: frozenset) -> frozenset:
    return frozenset(ts)


_REL = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
_OPS = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b}


def ev(t, V: dict):
    """D3's ev(t, V): a frozenset of words, TOP or NZ."""
    if type(t) is bool:
        return frozenset({int(t)})
    if type(t) is int:
        return frozenset({t % MOD})
    h = _head(t)
    if h is None:
        return TOP
    p = register_path(t)
    if p is not None:
        vals = V.get(p, {0})
        return TOP if any(x is TOP for x in vals) else frozenset(vals)
    if h == "len" and len(t) == 2 and t[1] == ["code", ["this"]]:
        return NZ
    if h == "!":
        return frozenset(1 - x for x in _truth(ev(t[1], V)))
    if h == "&&":
        ts = [_truth(ev(x, V)) for x in t[1:]]
        if any(x == {0} for x in ts):
            return frozenset({0})
        return frozenset({1}) if all(x == {1} for x in ts) else UNKNOWN
    if h == "||":
        ts = [_truth(ev(x, V)) for x in t[1:]]
        if any(x == {1} for x in ts):
            return frozenset({1})
        return frozenset({0}) if all(x == {0} for x in ts) else UNKNOWN
    if h == "?":
        c = _truth(ev(t[1], V))
        if c == {1}:
            return ev(t[2], V)
        if c == {0}:
            return ev(t[3], V)
        a, b = ev(t[2], V), ev(t[3], V)
        if isinstance(a, frozenset) and isinstance(b, frozenset):
            return a | b
        return TOP
    if h in _REL:
        a, b = ev(t[1], V), ev(t[2], V)
        if isinstance(a, frozenset) and isinstance(b, frozenset):
            return frozenset(int(_REL[h](x, y)) for x in a for y in b)
        if a is NZ and b == {0}:          # a non-zero word against 0
            return frozenset({int(_REL[h](1, 0))})
        if b is NZ and a == {0}:
            return frozenset({int(_REL[h](0, 1))})
        return UNKNOWN
    if h in _OPS:
        a, b = ev(t[1], V), ev(t[2], V)
        if not (isinstance(a, frozenset) and isinstance(b, frozenset)):
            return TOP
        out = frozenset(_OPS[h](x, y) % MOD for x in a for y in b)
        return out if len(out) <= WIDE else TOP
    if h == "fits":
        e = t[2]
        if _head(e) in _OPS:
            a, b = ev(e[1], V), ev(e[2], V)
            if isinstance(a, frozenset) and isinstance(b, frozenset):
                return frozenset(int(0 <= _OPS[e[0]](x, y) < 2 ** t[1]) for x in a for y in b)
        return UNKNOWN
    return TOP


def definitely_false(t, V: dict) -> bool:
    """D3: the expr evaluates to {0}."""
    v = ev(t, V)
    return isinstance(v, frozenset) and v == {0}


# ================================================================================================ D6 what a check reads
OTHER_COMPONENT = ("call", "callok", "caught", "sload", "balance", "codehash", "revertdata")
INPUT_LEAVES = ("param", "caller", "blobhash")
LOOP_LEAVES = ("iter", "count", "carried", "exit", "returned", "sum")


def external_terms(t) -> list[str]:
    """The other components' terms t reads: a call's function (call, callok), the head of caught, sload, balance,
    codehash and revertdata, and "code" for the code of an address that is not this contract."""
    out = set()
    for s in _subterms(t):
        h = _head(s)
        if h in ("call", "callok"):
            out.add(s[1])
        elif h in OTHER_COMPONENT:
            out.add(h)
        elif h == "code" and s[1:] != [["this"]]:
            out.add("code")
    return sorted(out)


def _reads_input(t) -> bool:
    for s in _subterms(t):
        h = _head(s)
        if h in INPUT_LEAVES or (h == "env" and s[1] != CLOCK[1]):
            return True
    return False


def _reads_loop(t) -> bool:
    return any(_head(s) in LOOP_LEAVES for s in _subterms(t))


def component(term: str) -> str:
    """D6: a function's interface (the text before "."), else the head itself."""
    return term.split(".", 1)[0] if "." in term else term


# ================================================================================================ D7 blocked conditions
def neg(x):
    return x[1] if _head(x) == "!" else ["!", x]


def kappa_rho(e):
    """D7: ["||", ["!", K], R..] gives (K, R, or ["||", R..] for several); anything else (1, e)."""
    if _head(e) == "||" and len(e) > 2 and _head(e[1]) == "!":
        rs = e[2:]
        return e[1][1], rs[0] if len(rs) == 1 else ["||", *rs]
    return 1, e


def blocked_atoms(e) -> list:
    """D7: atoms(B_c)."""
    kappa, rho = kappa_rho(e)
    atoms = []

    def conj(x):
        if _head(x) == "&&":
            for y in x[1:]:
                conj(y)
        elif x != 1:
            atoms.append(x)
    conj(kappa)
    for d in (rho[1:] if _head(rho) == "||" else [rho]):
        atoms.append(neg(d))
    seen = []
    for s in _subterms(rho):
        if _head(s) == "+" and len(s) == 3 and s not in seen:
            seen.append(s)
    atoms += [["fits", 256, s] for s in seen]
    return atoms


def blocked_term(atoms: list):
    return atoms[0] if len(atoms) == 1 else ["&&", *atoms]


# ================================================================================================ D9 signs
def _combine(signs) -> str:
    moving = [s for s in signs if s != "0"]
    if not moving:
        return "0"
    return moving[0] if moving[0] != "?" and all(s == moving[0] for s in moving) else "?"


def _opp(s: str) -> str:
    return "-" if s == "+" else "+" if s == "-" else s


def _reads(t, target: str) -> bool:
    for s in _subterms(t):
        if target == "time" and s == CLOCK:
            return True
        if target != "time" and _head(s) in ("storage", "map", "index", "member") and register_path(s) == target:
            return True
    return False


def sign(t, target: str) -> str:
    """D9's sign(t, p) (p a register path, or "time"): +, -, 0 or ?."""
    if not _reads(t, target):
        return "0"
    if target == "time" and t == CLOCK:
        return "+"
    if target != "time" and register_path(t) == target:
        node = t   # a read of p: + unless a key on its path reads p
        while _head(node) in ("map", "index", "member"):
            if _head(node) != "member" and _reads(node[2], target):
                return "?"
            node = node[1]
        return "+"
    h = _head(t)
    if h == "!":
        return _opp(sign(t[1], target))
    if h in ("&&", "||", "+"):
        return _combine([sign(x, target) for x in t[1:]])
    if h in ("<", "<="):
        return _combine([_opp(sign(t[1], target)), sign(t[2], target)])
    if h in (">", ">="):
        return _combine([sign(t[1], target), _opp(sign(t[2], target))])
    if h == "-":
        return _combine([sign(t[1], target), _opp(sign(t[2], target))])
    if h == "fits" and _head(t[2]) == "-":       # as a >= b
        return _combine([sign(t[2][1], target), _opp(sign(t[2][2], target))])
    if h == "fits" and _head(t[2]) == "+":       # as a + b < 2^n
        return _opp(_combine([sign(t[2][1], target), sign(t[2][2], target)]))
    return "?"


def read_paths(t) -> set:
    return {register_path(s) for s in _subterms(t) if register_path(s) is not None}


# ================================================================================================ the analysis
class Analysis:
    """Rules D1-D10 over one transitions document and the deployment's abstraction r0."""

    def __init__(self, doc: dict, r0: dict | None, model: str):
        self.doc, self.r0, self.model = doc, r0, model
        self.layout = Layout(doc)
        self.acts = {a["name"]: a for a in doc["actions"]}
        self.cks = {n: checks(a) for n, a in self.acts.items()}
        self._classes()
        self.V_all = _store(doc, self.layout, r0, list(self.cls_of))
        self.dead = {}
        for n in sorted(self.cls_of):                                    # D4
            hit = next((c for c in self.cks[n] if definitely_false(c["expr"], self.V_all)), None)
            if hit is not None:
                self.dead[n] = hit["id"]

    # ---------------------------------------------------------------------------------------- D2
    def _permission(self, a: dict) -> str | None:
        guards = sorted((g for g in a.get("guards") or [] if g.get("reaches")), key=lambda g: g["reaches"][0]["seq"])
        pr = a.get("principal")
        if pr:
            pick = [g for g in guards if canon(g["reaches"][0]["expr"]) == canon(pr["predicate"])]
            if not pick:
                raise ClassError(f"{a['name']}: no guard's first reach is its principal predicate")
        else:
            pick = [g for g in guards if any(_head(s) == "caller" for s in _subterms(g["reaches"][0]["expr"]))]
        if not pick:
            return None
        first = pick[0]["reaches"][0]["seq"]
        return next(c["id"] for c in self.cks[a["name"]] if c["seq"] == first)

    def _classes(self) -> None:
        self.cls_of, self.perm, self.pred, self.members = {}, {}, {}, {}
        for n in sorted(self.acts):
            a = self.acts[n]
            if not a.get("writes"):
                continue        # views and receive belong to no class
            pid = self._permission(a)
            expr = None if pid is None else next(c["expr"] for c in self.cks[n] if c["id"] == pid)
            if a.get("principal"):
                cid = a["principal"]["modifier"]
            elif pid is not None:
                cid = "caller_" + slug(pid.split("#")[1])
            else:
                cid = ANYONE
            if cid in self.pred and canon(self.pred[cid]) != canon(expr):
                raise ClassError(f"class {cid} has two predicates")
            self.pred[cid] = expr
            self.members.setdefault(cid, []).append(n)
            self.cls_of[n] = cid
            self.perm[n] = pid
        by_pred: dict = {}
        for cid in sorted(self.members):
            k = canon(self.pred[cid])
            if k in by_pred:
                raise ClassError(f"one predicate for two classes: {by_pred[k]} and {cid}")
            by_pred[k] = cid

    def callable(self, cid: str) -> list[str]:
        return sorted(set(self.members.get(cid, [])) | set(self.members.get(ANYONE, [])))

    # ---------------------------------------------------------------------------------------- D5
    def closure(self, cid: str) -> dict:
        live = [n for n in self.callable(cid) if n not in self.dead]

        def stopped(n, V):
            return any(c["id"] != self.perm[n] and definitely_false(c["expr"], V) for c in self.cks[n])
        act, rounds = frozenset(), 0
        while True:
            rounds += 1
            V = _store(self.doc, self.layout, self.r0, act)
            nxt = frozenset(n for n in live if not stopped(n, V))
            if nxt == act:
                break
            act = nxt
        V = _store(self.doc, self.layout, self.r0, act)
        excluded = {}
        for n in live:
            if n in act:
                continue
            excluded[n] = next(c["id"] for c in self.cks[n] if definitely_false(c["expr"], V))
        wc = set()
        for n in act:
            for w in self.acts[n].get("writes") or []:
                wc.update(p for p, _x in self.layout.written(w))
            for c in self.acts[n].get("calls") or []:
                if c.get("mutability") not in ("view", "pure"):
                    wc.add("call:" + c["fn"])
        return {"actions": sorted(act), "excluded": {k: excluded[k] for k in sorted(excluded)},
                "write_closure": sorted(wc), "rounds": rounds}

    # ---------------------------------------------------------------------------------------- D6
    def kind(self, n: str, c: dict) -> str:
        e = c["expr"]
        if c["id"] == self.perm[n]:
            return "permission"
        if external_terms(e):
            return "external"
        if _reads_input(e):
            return "input"
        if _reads_loop(e) or c.get("loop") is not None:
            return "loop"
        if c["section"] == "panics":
            if not (c.get("code") == 17 and c.get("op") == "-"):
                return "panic"
        elif c["section"] != "guards":
            return "input"
        B = blocked_term(blocked_atoms(e))
        if definitely_false(B, self.V_all):
            return "never"
        if sign(B, "time") in ("-", "?"):
            return "time"
        return "state"

    # ---------------------------------------------------------------------------------------- D9
    def unsafe_paths(self, n: str, B, reads: set) -> list[str]:
        a = self.acts[n]
        bad = []
        for w in a.get("writes") or []:
            for p, v in self.layout.written(w):
                if p not in reads or p in bad:
                    continue
                s = sign(B, p)
                if s == "0" or (s == "-" and v == 0) or (s == "+" and v == 1 and p in self.layout.bools):
                    continue
                bad.append(p)
        if not bad:
            return []
        post = a.get("post") or {}
        if all(p in self.layout.scalars and type(post.get(p)) is int for p in bad):
            V = {p: ({0, 1} if p in self.layout.bools else {TOP}) for p in reads}
            V.update({p: {post[p]} for p in bad})
            if ev(B, V) == {1}:
                return []     # the post-state keeps B whenever the action succeeds
        return sorted(bad)

    # ---------------------------------------------------------------------------------------- D6-D10
    def run(self) -> dict:
        rows = []          # (check row, check)
        for n in sorted(self.cls_of):
            if n in self.dead:
                continue
            for c in self.cks[n]:
                k = self.kind(n, c)
                row = {"id": c["id"], "action": n, "class": self.cls_of[n], "kind": k, "span": c["span"]}
                if k == "external":
                    row["external"] = external_terms(c["expr"])
                rows.append((row, c))
        kinds: dict = {}
        for row, _c in rows:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        comps: dict = {}
        for row, _c in rows:
            for term in row.get("external") or []:
                e = comps.setdefault(component(term), {"checks": set(), "actions": set(), "classes": set(),
                                                        "functions": set()})
                e["checks"].add(row["id"])
                e["actions"].add(row["action"])
                e["classes"].add(row["class"])
                e["functions"].add(term)
        external = {k: {f: sorted(v[f]) for f in v} for k, v in sorted(comps.items())}
        # D7: group the state checks by their blocked condition
        by_B: dict = {}
        for row, c in rows:
            if row["kind"] == "state":
                atoms = blocked_atoms(c["expr"])
                by_B.setdefault(canon(blocked_term(atoms)), (blocked_term(atoms), atoms, []))[2].append((row, c))
        groups = sorted(by_B.values(), key=lambda g: min((slug(r["span"]), r["id"]) for r, _c in g[2]))
        basis, laws = [], []
        for B, atoms, members in groups:
            rrow, rc = min(members, key=lambda m: (m[0]["span"], m[0]["id"]))     # B's representative c
            tag = slug(rrow["span"]) + "_" + x8(B)
            atom_set = {canon(x) for x in atoms}
            excl = {}                                                               # D8
            for n in sorted(self.cls_of):
                if n in self.dead:
                    continue
                for c in self.cks[n]:
                    if canon(c["expr"]) == canon(rc["expr"]) or canon(neg(c["expr"])) in atom_set:
                        excl[n] = c["id"]
                        break
            reads = read_paths(B)
            classes = sorted({r["class"] for r, _c in members})
            per = {}
            for X in classes:                                                       # D9
                xcl = [n for n in self.callable(X) if n not in self.dead and n not in excl]
                uns = {n: u for n in xcl for u in [self.unsafe_paths(n, B, reads)] if u}
                named = {}
                if not uns:
                    mine = set(self.callable(X))
                    for Y in sorted(self.members):
                        if Y == X:
                            continue
                        ws = [n for n in self.callable(Y) if n not in mine and n not in self.dead and n not in excl
                              and self.unsafe_paths(n, B, reads)]
                        if ws:
                            named[Y] = sorted(ws)
                per[X] = {"closure": xcl, "unsafe": uns, "status": "self" if uns else "blocked", "named": named,
                          "checks": sorted(r["id"] for r, _c in members if r["class"] == X)}
            basis.append({"tag": tag, "blocked": B, "check": rrow["id"], "check_expr": rc["expr"],
                          "checks": sorted(r["id"] for r, _c in members), "excluded": excl, "classes": per,
                          "time": sign(B, "time")})
            for X in classes:                                                       # D10
                laws.append({"law_id": LAW_PREFIX["blocking"] + tag + "_" + X, "subform": "blocking", "tag": tag,
                             "class": X, "closure": per[X]["closure"], "status": per[X]["status"]})
            laws.append({"law_id": LAW_PREFIX["revert"] + tag, "subform": "revert", "tag": tag, "class": None,
                         "excluded": sorted(excl)})
            namers: dict = {}
            for X in classes:
                for Y, ws in per[X]["named"].items():
                    namers.setdefault(Y, ([], set()))
                    namers[Y][0].append(X)
                    namers[Y][1].update(ws)
            for Y in sorted(namers):
                ycl = [n for n in self.callable(Y) if n not in self.dead and n not in excl]
                for sf in ("external", "external_none"):
                    laws.append({"law_id": LAW_PREFIX[sf] + tag + "_" + Y, "subform": sf, "tag": tag, "class": Y,
                                 "blocked_for": sorted(namers[Y][0]), "writers": sorted(namers[Y][1]),
                                 "closure": ycl})
        laws.sort(key=lambda lw: lw["law_id"])
        return {"model": self.model,
                "classes": {cid: {"predicate": self.pred[cid], "actions": sorted(self.members[cid]),
                                  "external": external_terms(self.pred[cid]) if self.pred[cid] is not None else []}
                            for cid in sorted(self.members)},
                "permission": {n: self.perm[n] for n in sorted(self.perm)}, "dead": self.dead,
                "closure": {cid: self.closure(cid) for cid in sorted(self.members)},
                "kinds": {k: kinds[k] for k in sorted(kinds)}, "checks": [r for r, _c in rows], "external": external,
                "basis": basis, "laws": laws}


def analysis(doc: dict, r0: dict | None, model: str) -> dict:
    return Analysis(doc, r0, model).run()


def attach_hypotheses(an: dict, hypotheses: dict | None, verdicts: dict | None) -> dict:
    """The contract's with_hypotheses: for each external component, the sidecar's hypothesis name with I21's verdict,
    result and finding for it; null for a component no hypothesis stands for."""
    table = (verdicts or {}).get("hypotheses") or {}
    for comp in an["external"]:
        name = (hypotheses or {}).get(comp)
        rec = table.get(name) or {} if name is not None else None
        an["external"][comp]["hypothesis"] = None if name is None else {
            "name": name, "verdict": rec.get("verdict"), "result": rec.get("result"), "finding": rec.get("finding")}
    return an


# ================================================================================================ derivation views
def entries(an: dict) -> dict:
    """D12: each DISCH DERIVATION entry without "facts" and "statement_hash", by law id."""
    tags = {b["tag"]: b for b in an["basis"]}
    out = {}
    for lw in an["laws"]:
        b, sf = tags[lw["tag"]], lw["subform"]
        e = {"law_id": lw["law_id"], "rule": "DISCH", "subform": sf,
             "basis": {"kind": "guard_conjunct", "model": an["model"], "tag": b["tag"], "check": b["check"],
                       "checks": b["checks"], "blocked": b["blocked"], "class": lw["class"]}}
        if sf == "revert":
            e["closure"], e["excluded"], e["entry_points"] = [], lw["excluded"], lw["excluded"]
        else:
            e["closure"], e["excluded"], e["entry_points"] = lw["closure"], [], lw["closure"]
            if sf == "blocking":
                e["status"] = lw["status"]
            else:
                e["blocked_for"], e["writers"] = lw["blocked_for"], lw["writers"]
        out[lw["law_id"]] = e
    return out


def disch_id(model: str, law: dict) -> str:
    """D11: "<model>:<subform>:<tag>:<class>" (class "all" for revert)."""
    return ":".join([model, law["subform"], law["tag"], law["class"] or "all"])


def ref_doc(an: dict, law: dict) -> dict:
    """D11: the document whose sha256 is the ref "disch:<ID>"."""
    b = next(x for x in an["basis"] if x["tag"] == law["tag"])
    e = entries(an)[law["law_id"]]
    return {"template": "holon.rules.disch/" + law["subform"], "template_version": 1, "subform": law["subform"],
            "model": an["model"], "blocked": b["blocked"], "check": b["check"], "check_expr": b["check_expr"],
            "class": law["class"], "closure": e["closure"], "excluded": e["excluded"]}


# ================================================================================================ the sidecar
def default_sidecar(milestone: str) -> str:
    return f"spec/{milestone}/lib/disch.json"


def _rel(p: Path, root: Path) -> str:
    try:
        return Path(p).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        raise Refused(f"{p} is not inside the root {root}") from None


class Sidecar:
    """A DISCH sidecar (holon-disch/0.1) and the documents it names, read and checked (Refused on a problem)."""

    def __init__(self, milestone: str, root: Path, sidecar: str | None = None):
        root = Path(root).resolve()
        self.root = root
        if sidecar:
            p = Path(sidecar)
            p = p if p.is_absolute() else root / p
        else:
            if not str(milestone).startswith("M"):
                raise Refused(f"test milestone {milestone} needs --sidecar")
            p = root / default_sidecar(milestone)
        if not p.is_file():
            raise Refused(f"the DISCH sidecar {p} does not exist")
        self.path = p
        self.rel = _rel(p, root)
        raw = p.read_bytes()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        try:
            self.doc = json.loads(raw.decode("utf-8"))
        except ValueError as e:
            raise Refused(f"{self.rel}: not JSON ({e})") from None
        if not isinstance(self.doc, dict) or self.doc.get("disch_version") != VERSION:
            raise Refused(f"{self.rel}: disch_version is not {VERSION}")
        docs = self.doc.get("documents")
        if not isinstance(docs, list) or not docs or not all(isinstance(d, str) for d in docs):
            raise Refused(f"{self.rel}: no documents")
        for i in self.doc.get("inputs") or []:
            q = root / i["path"]
            if not q.is_file():
                raise Refused(f"{self.rel}: input {i['path']} is missing")
            if hashlib.sha256(q.read_bytes()).hexdigest() != i["sha256"]:
                raise Refused(f"{self.rel}: input {i['path']} does not have the sha256 the sidecar pins")
        self.documents = list(docs)
        self.r0 = self.doc.get("r0")
        self.hypotheses = self.doc.get("hypotheses") or {}
        self.verdicts_rel = self.doc.get("hypothesis_verdicts")
        self.search = dict(self.doc.get("search") or {})
        self.binding = self.doc.get("binding")
        self.model_sidecar = self.doc.get("model_sidecar")

    def read_json(self, rel: str) -> tuple[dict, str]:
        q = self.root / rel
        if not q.is_file():
            raise Refused(f"{rel} is missing")
        raw = q.read_bytes()
        try:
            return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()
        except ValueError as e:
            raise Refused(f"{rel}: not JSON ({e})") from None

    def analyses(self) -> tuple[dict, list[dict]]:
        """{model: analysis with hypotheses} of every document, and the inputs read (sorted)."""
        inputs = {}
        verdicts = None
        if self.verdicts_rel:
            verdicts, h = self.read_json(self.verdicts_rel)
            inputs[self.verdicts_rel] = h
        out = {}
        for d in self.documents:
            doc, h = self.read_json(d)
            inputs[d] = h
            if not isinstance(doc, dict) or not isinstance(doc.get("actions"), list):
                raise Refused(f"{d}: not a transitions document")
            m = model_name(d)
            if m in out:
                raise Refused(f"two documents name the model {m}")
            try:
                an = analysis(doc, self.r0, m)
            except (KeyError, TypeError, IndexError) as e:
                raise Refused(f"{d}: malformed ({type(e).__name__}: {e})") from None
            an["_doc"] = d
            an["_doc_sha256"] = h
            out[m] = attach_hypotheses(an, self.hypotheses, verdicts)
        return out, [{"path": k, "sha256": v} for k, v in sorted(inputs.items())]


def _r0_listing(doc: dict, r0: dict | None) -> dict:
    return {p: sorted(["T" if x is TOP else x for x in v], key=lambda x: (isinstance(x, str), x))
            for p, v in sorted(deployment_values(doc, r0).items())}


def files(milestone: str, sc: Sidecar) -> dict[str, str]:
    """{name: text} of closure.json and conjuncts.json."""
    ans, inputs = sc.analyses()
    side = {"path": sc.rel, "sha256": sc.sha256}
    clo, con = {}, {}
    for m, an in sorted(ans.items()):
        doc, _h = sc.read_json(an["_doc"])
        clo[m] = {"r0": _r0_listing(doc, sc.r0), "classes": an["classes"], "permission": an["permission"],
                  "dead": an["dead"], "closure": an["closure"]}
        con[m] = {"kinds": an["kinds"], "checks": an["checks"], "external": an["external"],
                  "basis": [{k: b[k] for k in ("tag", "blocked", "check", "check_expr", "checks", "excluded", "time")}
                            | {"classes": b["classes"]} for b in an["basis"]]}
    return {"closure.json": dumps({"document": "disch_closure", "milestone": milestone, "sidecar": side,
                                   "inputs": inputs, "models": clo}),
            "conjuncts.json": dumps({"document": "disch_conjuncts", "milestone": milestone, "sidecar": side,
                                     "inputs": inputs, "models": con})}


def load(milestone: str, root: Path, sidecar: str | None = None) -> tuple[Sidecar, dict]:
    """The sidecar and {model: analysis} (for derive, run and the refs)."""
    sc = Sidecar(milestone, root, sidecar)
    ans, _inputs = sc.analyses()
    return sc, ans


_CACHE: dict = {}


def analysis_for(law: dict, root: Path | str | None = None) -> tuple[dict | None, Sidecar | None]:
    """The analysis of a DISCH law's document under the sidecar its milestone derives with: spec/<M>/lib/disch.json
    when it names the law's document, else the sidecar gen/<M>/disch/closure.json records (a test milestone).
    (None, None) when neither exists."""
    root = Path(root or ROOT).resolve()
    m, facts = str(law.get("milestone")), law.get("facts")
    cands = []
    if (root / default_sidecar(m)).is_file():
        cands.append(default_sidecar(m))
    cp = root / "gen" / m / "disch" / "closure.json"
    if cp.is_file():
        try:
            cands.append(json.loads(cp.read_text(encoding="utf-8"))["sidecar"]["path"])
        except (ValueError, KeyError, TypeError):
            pass
    for rel in cands:
        try:
            raw = (root / rel).read_bytes()
            side = json.loads(raw.decode("utf-8"))
        except (OSError, ValueError):
            continue
        if facts not in (side.get("documents") or []):
            continue
        try:
            dbytes = (root / facts).read_bytes()
        except OSError:
            return None, None
        key = (str(root), rel, hashlib.sha256(raw).hexdigest(), hashlib.sha256(dbytes).hexdigest())
        if key not in _CACHE:
            try:
                sc = Sidecar(m, root, rel)
                an = analysis(json.loads(dbytes.decode("utf-8")), sc.r0, model_name(facts))
            except (Refused, ClassError, ValueError, KeyError, TypeError):
                return None, None
            _CACHE[key] = (an, sc)
        return _CACHE[key]
    return None, None


def disch_ref(did: str, law: dict, root: Path | str | None = None) -> str:
    """The ref "disch:<ID>": sha256 (hex) of the canonical ref document, recomputed from the document and the
    sidecar; the hash of {"absent": ID} when the law's analysis does not give the id."""
    an, _sc = analysis_for(law, root)
    doc = {"absent": did}
    if an is not None:
        for lw in an["laws"]:
            if disch_id(an["model"], lw) == did:
                doc = ref_doc(an, lw)
                break
    return hashlib.sha256(canon(doc).encode("utf-8")).hexdigest()


# ================================================================================================ the CLI
def write(milestone: str, root: Path, sidecar: str | None, out: str | None, check: bool, log=print) -> int:
    root = Path(root).resolve()
    try:
        sc = Sidecar(milestone, root, sidecar)
        texts = files(milestone, sc)
    except Refused as e:
        print(f"holon disch: refused: {e}", file=sys.stderr)
        return 2
    except ClassError as e:
        print(f"holon disch: {e}", file=sys.stderr)
        return 3
    od = Path(out) if out else root / "gen" / milestone / "disch"
    if not od.is_absolute():
        od = root / od
    if check:
        bad = [n for n, t in texts.items() if not (od / n).is_file() or (od / n).read_text(encoding="utf-8") != t]
        if bad:
            print(f"holon disch: {', '.join(bad)} differ from a fresh run", file=sys.stderr)
            return 1
        log(f"holon disch: {', '.join(sorted(texts))} are current")
        return 0
    od.mkdir(parents=True, exist_ok=True)
    for n, t in texts.items():
        (od / n).write_text(t, encoding="utf-8")
    log(f"holon disch: {', '.join(sorted(texts))} -> {od}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon disch")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--sidecar", help=f"the DISCH sidecar (default {default_sidecar('<M>')}; a test milestone names one)")
    ap.add_argument("--out", help="output directory (default <root>/gen/<M>/disch)")
    ap.add_argument("--check", action="store_true", help="exit 1 when a file differs from a fresh run (nothing written)")
    a = ap.parse_args(argv)
    return write(a.milestone, Path(a.root) if a.root else ROOT, a.sidecar, a.out, a.check)


if __name__ == "__main__":
    sys.exit(main())
