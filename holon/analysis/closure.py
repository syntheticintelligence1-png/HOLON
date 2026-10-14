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
WORD = 1 << 256
SET_MAX = 16
ANYONE = "anyone"


class _Top:
    """The abstract value "any word"."""

    def __repr__(self):
        return "T"


class _NonZero:
    """The abstract value "a non-zero word" (E-self: the length of the executing contract's code)."""

    def __repr__(self):
        return "NZ"


TOP = _Top()
NZ = _NonZero()
TIME_TERM = ["env", "block.timestamp"]
INPUT_HEADS = ("param", "caller", "blobhash")
LOOP_HEADS = frozenset({"iter", "count", "carried", "exit", "returned", "sum"})
OTHER_COMPONENT_HEADS = frozenset({"call", "callok", "caught", "sload", "balance", "codehash", "revertdata"})


class Refused(ValueError):
    """Exit 2: an input missing, malformed or stale."""


class ClassError(ValueError):
    """Exit 3: a construct rule D2 refuses."""


def canon(o) -> str:
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def x8(o) -> str:
    return hashlib.sha256(canon(o).encode("utf-8")).hexdigest()[:8]


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True) + "\n"


def slug(span: str) -> str:
    """The stem of a span's file, lower-cased, runs of other characters than [a-z0-9] as "_", then "_" and the line
    ("a-b" as "a_b")."""
    path, line = span.rsplit(":", 1)
    stem = path.rsplit("/", 1)[-1].split(".")[0].lower()
    return re.sub(r"[^a-z0-9]+", "_", stem) + "_" + line.replace("-", "_")


def model_name(doc_rel: str) -> str:
    name = Path(doc_rel).name
    return name[:-len(".json")] if name.endswith(".json") else name


# ================================================================================================ D1 checks
def checks(action: dict) -> list[dict]:
    """Every check of an action in walk (seq) order, with holon.machine's id: a guard's reaches take the guard's
    span, every other record its own; k counts the checks of a span in walk order."""
    recs = []
    for g in action.get("guards") or []:
        for r in g["reaches"]:
            recs.append(("guards", r, g))
    for section in ("panics", "checks"):
        for r in action.get(section) or []:
            recs.append((section, r, r))
    for r in action.get("calls") or []:
        if "expr" in r and r["expr"] != 1:
            recs.append(("calls", r, r))
    recs.sort(key=lambda x: x[1]["seq"])
    per_span: dict = {}
    out = []
    for section, r, owner in recs:
        span = owner.get("src") or section
        k = per_span.get(span, 0)
        per_span[span] = k + 1
        out.append({"id": f"{action['name']}#{span}#{k}", "section": section, "span": span, "seq": r["seq"],
                    "expr": r.get("expr", owner.get("expr")),
                    "op": r.get("op") if section == "panics" else None,
                    "code": r.get("code") if section == "panics" else None,
                    "loop": r.get("loop")})
    return out


# ================================================================================================ what a term reads
class Reads:
    """The leaves a term reads: storage families, other components' terms, time, inputs, the executing contract's
    code, loop terms."""

    def __init__(self, t):
        self.families: set = set()
        self.external: set = set()
        self.time = False
        self.inputs: set = set()
        self.self_code = False
        self.loop: set = set()
        self._walk(t)

    def _walk(self, t) -> None:
        if not isinstance(t, list) or not t:
            return
        head = t[0]
        if not isinstance(head, str):
            for x in t:
                self._walk(x)
            return
        if head == "storage":
            self.families.add(t[1])
            return
        if head == "env":
            if t[1] == TIME_TERM[1]:
                self.time = True
            else:
                self.inputs.add("env:" + t[1])
            return
        if head == "caller":
            self.inputs.add("caller")
            return
        if head == "param":
            self.inputs.add("param:" + str(t[1]))
            return
        if head == "blobhash":
            self.inputs.add("blobhash")
        elif head == "code":
            if t[1:] == [["this"]]:
                self.self_code = True
                return
            self.external.add("code")
        elif head in ("call", "callok"):
            self.external.add(t[1])
        elif head in OTHER_COMPONENT_HEADS:
            self.external.add(head)
        elif head in LOOP_HEADS:
            self.loop.add(head)
        for x in t[1:]:
            self._walk(x)


# ================================================================================================ D2 principal classes
def _permission_check(action: dict, cks: list[dict]) -> str | None:
    guards = sorted(action.get("guards") or [], key=lambda g: g["reaches"][0]["seq"])
    if action.get("principal"):
        want = canon(action["principal"]["predicate"])
        chosen = next((g for g in guards if canon(g["reaches"][0]["expr"]) == want), None)
        if chosen is None:
            raise ClassError(f"{action['name']}: its principal predicate is the expr of no guard")
    else:
        chosen = next((g for g in guards if "caller" in Reads(g["reaches"][0]["expr"]).inputs), None)
    if chosen is None:
        return None
    seq = chosen["reaches"][0]["seq"]
    return next(c["id"] for c in cks if c["seq"] == seq)


class Classes:
    """D2 over the actions with at least one write record: of[action] = class id, members[class], predicate[class],
    permission[action] = the permission check id or None."""

    def __init__(self, doc: dict):
        self.of: dict = {}
        self.members: dict = {}
        self.predicate: dict = {}
        self.permission: dict = {}
        by_name = {a["name"]: a for a in doc["actions"]}
        for name in sorted(by_name):
            a = by_name[name]
            if not a.get("writes"):
                continue
            cks = checks(a)
            pid = _permission_check(a, cks)
            if a.get("principal"):
                cid = a["principal"]["modifier"]
            elif pid is not None:
                cid = "caller_" + slug(pid.split("#")[1])
            else:
                cid = ANYONE
            pred = next(c["expr"] for c in cks if c["id"] == pid) if pid is not None else None
            if cid in self.predicate and canon(self.predicate[cid]) != canon(pred):
                raise ClassError(f"class {cid}: two predicates")
            self.predicate.setdefault(cid, pred)
            self.members.setdefault(cid, []).append(name)
            self.of[name] = cid
            self.permission[name] = pid
        seen: dict = {}
        for cid in self.members:
            k = canon(self.predicate[cid])
            if k in seen:
                raise ClassError(f"classes {seen[k]} and {cid} share one predicate")
            seen[k] = cid

    def callable(self, cid: str) -> list[str]:
        """Callable_X: the class's actions and anyone's."""
        return sorted(set(self.members[cid]) | set(self.members.get(ANYONE, [])))


# ================================================================================================ D3 abstract values
def _storage_decls(doc: dict) -> list[dict]:
    return list(doc.get("storage") or []) + list(doc.get("inherited_storage") or [])


def struct_members(doc: dict) -> dict:
    return {s["name"]: [f["name"] for f in s["fields"]] for s in doc.get("storage") or [] if s.get("fields")}


def bool_paths(doc: dict) -> set:
    out = set()
    for s in _storage_decls(doc):
        if s.get("fields"):
            out |= {f"{s['name']}.{f['name']}" for f in s["fields"] if f.get("type") == "bool"}
        elif s.get("value") == "bool":
            out.add(s["name"])
    return out


def all_paths(doc: dict) -> list[str]:
    members = struct_members(doc)
    out = set()
    for s in _storage_decls(doc):
        if s["name"] == "__gap":
            continue
        if s["name"] in members:
            out |= {f"{s['name']}.{m}" for m in members[s["name"]]}
        else:
            out.add(s["name"])
    return sorted(out)


def path_of(t) -> str | None:
    """The register path a read term reads ("family" or "family.member"; keys ignored), None for another term."""
    if not isinstance(t, list) or not t:
        return None
    if t[0] == "storage":
        return t[1]
    if t[0] in ("map", "index"):
        return path_of(t[1])
    if t[0] == "member":
        base = path_of(t[1])
        return None if base is None else f"{base}.{t[2]}"
    return None


def _word_or_top(v):
    return v if isinstance(v, int) and not isinstance(v, bool) else TOP


def write_contributions(doc: dict, w: dict, members: dict | None = None) -> list[tuple]:
    """D3: (path, abstract value) for each path one write record writes."""
    members = struct_members(doc) if members is None else members
    fam, value = w["family"], w.get("value")
    named = [p[1] for p in (w.get("path") or []) if p[0] == "member"]
    if named:
        return [(f"{fam}.{named[-1]}", _word_or_top(value))]
    if fam in members:
        if isinstance(value, list) and value and value[0] == "struct":
            lit = {m: x for m, x in value[2]}
            return [(f"{fam}.{m}", _word_or_top(lit.get(m, 0))) for m in members[fam]]
        return [(f"{fam}.{m}", 0 if value == 0 else TOP) for m in members[fam]]
    return [(fam, _word_or_top(value))]


def deployment_values(doc: dict, r0: dict | None) -> dict:
    """R0: the sidecar's r0 "values" ("T" is TOP); every other path {0}."""
    given = (r0 or {}).get("values") or {}
    paths = all_paths(doc)
    stray = sorted(set(given) - set(paths))
    if stray:
        raise Refused(f"r0 names paths the document does not declare: {stray}")
    return {p: {TOP if x == "T" else x for x in given.get(p, [0])} for p in paths}


class Values:
    """The abstract store: R0 plus the writes of a set of actions."""

    def __init__(self, doc: dict, r0: dict | None, actions):
        self.v = deployment_values(doc, r0)
        members = struct_members(doc)
        by_name = {a["name"]: a for a in doc["actions"]}
        for n in sorted(actions):
            for w in by_name[n].get("writes") or []:
                for p, x in write_contributions(doc, w, members):
                    self.v.setdefault(p, {0}).add(x)


def _truths(x) -> set:
    if x is TOP:
        return {0, 1}
    if x is NZ:
        return {1}
    return {int(v != 0) for v in x}


_CMP = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b,
        ">": lambda a, b: a > b, ">=": lambda a, b: a >= b}
_ARITH = {"+": lambda a, b: a + b, "-": lambda a, b: a - b, "*": lambda a, b: a * b}


def abstract(t, V: dict):
    """D3: the abstract value of a term over the store V (a finite set of words, TOP or NZ)."""
    if isinstance(t, bool):
        return {int(t)}
    if isinstance(t, int):
        return {t % WORD}
    if not isinstance(t, list) or not t:
        return TOP
    head = t[0]
    p = path_of(t)
    if p is not None:
        vals = V.get(p, {0})
        return TOP if TOP in vals else set(vals)
    if head == "len" and t[1:] == [["code", ["this"]]]:
        return NZ
    if head == "!":
        x = abstract(t[1], V)
        if x is TOP:
            return TOP
        if x is NZ:
            return {0}
        return {int(v == 0) for v in x}
    if head in ("&&", "||"):
        parts = [_truths(abstract(x, V)) for x in t[1:]]
        if head == "&&":
            if any(v == {0} for v in parts):
                return {0}
            return {1} if all(v == {1} for v in parts) else {0, 1}
        if any(v == {1} for v in parts):
            return {1}
        return {0} if all(v == {0} for v in parts) else {0, 1}
    if head == "?":
        c = _truths(abstract(t[1], V))
        a, b = abstract(t[2], V), abstract(t[3], V)
        if c == {1}:
            return a
        if c == {0}:
            return b
        if not isinstance(a, set) or not isinstance(b, set):
            return TOP
        u = a | b
        return u if len(u) <= SET_MAX else TOP
    if head in _CMP:
        a, b = abstract(t[1], V), abstract(t[2], V)
        if a is NZ and b == {0}:
            return {1} if head in ("!=", ">", ">=") else {0}
        if b is NZ and a == {0}:
            return {1} if head in ("!=", "<", "<=") else {0}
        if not isinstance(a, set) or not isinstance(b, set):
            return {0, 1}
        f = _CMP[head]
        return {int(f(x, y)) for x in a for y in b}
    if head in _ARITH:
        a, b = abstract(t[1], V), abstract(t[2], V)
        if not isinstance(a, set) or not isinstance(b, set):
            return TOP
        f = _ARITH[head]
        u = {f(x, y) % WORD for x in a for y in b}
        return u if len(u) <= SET_MAX else TOP
    if head == "fits":
        n, e = t[1], t[2]
        if isinstance(e, list) and e and e[0] in _ARITH:
            a, b = abstract(e[1], V), abstract(e[2], V)
            if not isinstance(a, set) or not isinstance(b, set):
                return {0, 1}
            f = _ARITH[e[0]]
            return {int(0 <= f(x, y) < (1 << n)) for x in a for y in b}
        return {0, 1}
    return TOP


def definitely_false(t, V: dict) -> bool:
    return _truths(abstract(t, V)) == {0}


# ================================================================================================ D4, D5
def effects(action: dict, doc: dict) -> set:
    """The paths an action's write records write and "call:<fn>" for each call that is not view or pure."""
    members = struct_members(doc)
    out = set()
    for w in action.get("writes") or []:
        out |= {p for p, _x in write_contributions(doc, w, members)}
    for c in action.get("calls") or []:
        if c.get("mutability") not in ("view", "pure"):
            out.add("call:" + c["fn"])
    return out


# ================================================================================================ D7 blocked conditions
def neg(x):
    if isinstance(x, list) and x and x[0] == "!":
        return x[1]
    return ["!", x]


def kappa_rho(e):
    """(kappa, rho): ["||", ["!", K], R..] gives (K, R, or ["||", R..] for several); anything else (1, e)."""
    if isinstance(e, list) and len(e) >= 3 and e[0] == "||" and isinstance(e[1], list) and e[1][:1] == ["!"]:
        rest = e[2:]
        return e[1][1], (rest[0] if len(rest) == 1 else ["||"] + rest)
    return 1, e


def _conjuncts(x) -> list:
    if isinstance(x, list) and x and x[0] == "&&":
        return [y for z in x[1:] for y in _conjuncts(z)]
    return [] if x == 1 else [x]


def _sums(t, acc: list) -> list:
    """The distinct ["+", a, b] subterms of t in depth-first first-occurrence order."""
    if isinstance(t, list) and t:
        if t[0] == "+" and len(t) == 3 and canon(t) not in {canon(x) for x in acc}:
            acc.append(t)
        for x in t[1:]:
            _sums(x, acc)
    return acc


def blocked_atoms(e) -> list:
    """D7: the conjuncts of kappa, then neg(d) for every disjunct d of rho, then ["fits", 256, s] for every sum s in rho
    (B reads its sums exactly)."""
    k, r = kappa_rho(e)
    out = _conjuncts(k)
    disj = r[1:] if isinstance(r, list) and r and r[0] == "||" else [r]
    out += [neg(d) for d in disj]
    out += [["fits", 256, s] for s in _sums(r, [])]
    return out


def blocked_term(atoms: list):
    return atoms[0] if len(atoms) == 1 else ["&&"] + atoms


# ================================================================================================ D9 signs
def _reads_target(t, target: str) -> bool:
    if target == "time":
        if canon(t) == canon(TIME_TERM):
            return True
    elif path_of(t) == target:
        return True
    return isinstance(t, list) and any(_reads_target(x, target) for x in t[1:])


def _join(*signs) -> str:
    live = [s for s in signs if s != "0"]
    if not live:
        return "0"
    if "?" in live:
        return "?"
    return live[0] if all(s == live[0] for s in live) else "?"


def _flip(s: str) -> str:
    return {"+": "-", "-": "+"}.get(s, s)


def sign(t, target: str) -> str:
    """D9: the monotonicity of t's truth in a register path (or "time"): +, -, 0 (not read) or ?."""
    if not _reads_target(t, target):
        return "0"
    if target == "time" and canon(t) == canon(TIME_TERM):
        return "+"
    if target != "time" and path_of(t) == target:
        k = t
        while isinstance(k, list) and k and k[0] in ("member", "map", "index"):
            if k[0] in ("map", "index") and _reads_target(k[2], target):
                return "?"
            k = k[1]
        return "+"
    if not isinstance(t, list) or not t:
        return "0"
    head = t[0]
    if head == "!":
        return _flip(sign(t[1], target))
    if head in ("&&", "||"):
        return _join(*[sign(x, target) for x in t[1:]])
    if head in ("<", "<="):
        return _join(_flip(sign(t[1], target)), sign(t[2], target))
    if head in (">", ">="):
        return _join(sign(t[1], target), _flip(sign(t[2], target)))
    if head == "+":
        return _join(sign(t[1], target), sign(t[2], target))
    if head == "-":
        return _join(sign(t[1], target), _flip(sign(t[2], target)))
    if head == "fits":
        e = t[2]
        if isinstance(e, list) and e and e[0] == "-":
            return _join(sign(e[1], target), _flip(sign(e[2], target)))
        if isinstance(e, list) and e and e[0] == "+":
            return _flip(_join(sign(e[1], target), sign(e[2], target)))
        return "?"
    return "?"


def read_paths(t, acc: set | None = None) -> set:
    acc = set() if acc is None else acc
    p = path_of(t)
    if p is not None:
        acc.add(p)
    if isinstance(t, list):
        for x in t[1:]:
            read_paths(x, acc)
    return acc


# ================================================================================================ the analysis
class Analysis:
    """Rules D1-D10 on one document with the deployment's abstraction r0."""

    def __init__(self, doc: dict, r0: dict | None, model: str):
        self.doc = doc
        self.r0 = r0
        self.model = model
        self.actions = {a["name"]: a for a in doc["actions"]}
        self.cl = Classes(doc)
        self._checks = {n: checks(a) for n, a in self.actions.items()}
        self.V_all = Values(doc, r0, self.cl.of).v
        self.bools = bool_paths(doc)
        self.dead = self._dead()

    # D4
    def _dead(self) -> dict:
        out = {}
        for n in sorted(self.cl.of):
            for c in self._checks[n]:
                if definitely_false(c["expr"], self.V_all):
                    out[n] = c["id"]
                    break
        return out

    # D5
    def closure(self, cid: str) -> dict:
        cands = [n for n in self.cl.callable(cid) if n not in self.dead]
        act: set = set()
        rounds = 0

        def blocked_by(n, V):
            return next((c["id"] for c in self._checks[n]
                         if c["id"] != self.cl.permission[n] and definitely_false(c["expr"], V)), None)
        while True:
            V = Values(self.doc, self.r0, act).v
            new = {n for n in cands if blocked_by(n, V) is None}
            rounds += 1
            if new == act:
                break
            act = new
        V = Values(self.doc, self.r0, act).v
        excluded = {n: blocked_by(n, V) for n in cands if n not in act}
        wc = set()
        for n in act:
            wc |= effects(self.actions[n], self.doc)
        return {"actions": sorted(act), "excluded": dict(sorted(excluded.items())), "write_closure": sorted(wc),
                "rounds": rounds}

    # D6
    def kind(self, c: dict, perm: str | None) -> str:
        if c["id"] == perm:
            return "permission"
        rd = Reads(c["expr"])
        if rd.external:
            return "external"
        if rd.inputs:
            return "input"
        if rd.loop or c.get("loop") is not None:
            return "loop"
        if c["section"] == "panics" and not (c["code"] == 17 and c["op"] == "-"):
            return "panic"
        if c["section"] not in ("guards", "panics"):
            return "input"
        B = blocked_term(blocked_atoms(c["expr"]))
        if definitely_false(B, self.V_all):
            return "never"
        if sign(B, "time") not in ("+", "0"):
            return "time"
        return "state"

    # D9
    def unsafe(self, n: str, B, rd: set) -> set:
        a = self.actions[n]
        post = {p: v for p, v in (a.get("post") or {}).items() if isinstance(v, int) and not isinstance(v, bool)}
        moved = set()
        members = struct_members(self.doc)
        for w in a.get("writes") or []:
            for p, v in write_contributions(self.doc, w, members):
                if p not in rd:
                    continue
                s = sign(B, p)
                if s == "0" or (s == "-" and v == 0) or (s == "+" and v == 1 and p in self.bools):
                    continue
                moved.add(p)
        if moved and all(p in post for p in moved):
            Vp = {p: ({0, 1} if p in self.bools else {TOP}) for p in rd}
            for p in moved:
                Vp[p] = {post[p]}
            if _truths(abstract(B, Vp)) == {1}:
                return set()
        return moved

    def run(self) -> dict:
        cl = self.cl
        closures = {cid: self.closure(cid) for cid in sorted(cl.members)}
        rows = []
        for n in sorted(cl.of):
            if n in self.dead:
                continue
            for c in self._checks[n]:
                k = self.kind(c, cl.permission[n])
                row = {"id": c["id"], "action": n, "class": cl.of[n], "kind": k, "span": c["span"]}
                if k == "external":
                    row["external"] = sorted(Reads(c["expr"]).external)
                rows.append((row, c))
        groups: dict = {}
        for row, c in rows:
            if row["kind"] != "state":
                continue
            atoms = blocked_atoms(c["expr"])
            B = blocked_term(atoms)
            groups.setdefault(canon(B), {"B": B, "atoms": atoms, "checks": []})["checks"].append((row, c))
        basis, laws = [], []
        order = sorted(groups, key=lambda k: min((slug(r["span"]), r["id"]) for r, _c in groups[k]["checks"]))
        for key in order:
            g = groups[key]
            B, atoms = g["B"], g["atoms"]
            rep_row, rep = min(g["checks"], key=lambda rc: (rc[0]["span"], rc[0]["id"]))
            tag = f"{slug(rep_row['span'])}_{x8(B)}"
            atom_keys = {canon(x) for x in atoms}
            excl = {}
            for n in sorted(cl.of):
                if n in self.dead:
                    continue
                for c in self._checks[n]:
                    if canon(c["expr"]) == canon(rep["expr"]) or canon(neg(c["expr"])) in atom_keys:
                        excl[n] = c["id"]
                        break
            rd = read_paths(B)
            in_classes = sorted({cl.of[r["action"]] for r, _c in g["checks"]})
            per_x = {}
            for X in in_classes:
                cx = [n for n in cl.callable(X) if n not in self.dead and n not in excl]
                uns = {}
                for n in cx:
                    u = self.unsafe(n, B, rd)
                    if u:
                        uns[n] = sorted(u)
                status = "self" if uns else "blocked"
                named = {}
                if status == "blocked":
                    own = set(cl.callable(X))
                    for Y in sorted(cl.members):
                        if Y == X:
                            continue
                        ys = [n for n in cl.callable(Y) if n not in own and n not in self.dead and n not in excl]
                        writers = sorted(n for n in ys if self.unsafe(n, B, rd))
                        if writers:
                            named[Y] = writers
                per_x[X] = {"closure": cx, "unsafe": uns, "status": status, "named": named,
                            "checks": sorted(r["id"] for r, _c in g["checks"] if r["class"] == X)}
            basis.append({"tag": tag, "blocked": B, "check": rep_row["id"], "check_expr": rep["expr"],
                          "checks": sorted(r["id"] for r, _c in g["checks"]), "excluded": excl, "classes": per_x,
                          "time": sign(B, "time")})
            for X in in_classes:
                laws.append({"law_id": f"{LAW_PREFIX['blocking']}{tag}_{X}", "subform": "blocking", "tag": tag,
                             "class": X, "closure": per_x[X]["closure"], "status": per_x[X]["status"]})
            laws.append({"law_id": f"{LAW_PREFIX['revert']}{tag}", "subform": "revert", "tag": tag, "class": None,
                         "excluded": sorted(excl)})
            for Y in sorted({Y for X in in_classes for Y in per_x[X]["named"]}):
                blocked_for = sorted(X for X in in_classes if Y in per_x[X]["named"])
                writers = sorted({n for X in blocked_for for n in per_x[X]["named"][Y]})
                ycl = [n for n in cl.callable(Y) if n not in self.dead and n not in excl]
                for sf in ("external", "external_none"):
                    laws.append({"law_id": f"{LAW_PREFIX[sf]}{tag}_{Y}", "subform": sf, "tag": tag, "class": Y,
                                 "blocked_for": blocked_for, "writers": writers, "closure": ycl})
        laws.sort(key=lambda x: x["law_id"])
        ext: dict = {}
        for row, _c in rows:
            for fn in row.get("external", []):
                comp = fn.split(".")[0] if "." in fn else fn
                e = ext.setdefault(comp, {"checks": set(), "actions": set(), "classes": set(), "functions": set()})
                e["checks"].add(row["id"])
                e["actions"].add(row["action"])
                e["classes"].add(row["class"])
                e["functions"].add(fn)
        ext = {k: {f: sorted(v[f]) for f in ("checks", "actions", "classes", "functions")}
               for k, v in sorted(ext.items())}
        kinds: dict = {}
        for row, _c in rows:
            kinds[row["kind"]] = kinds.get(row["kind"], 0) + 1
        return {"model": self.model,
                "classes": {cid: {"predicate": cl.predicate[cid], "actions": sorted(cl.members[cid]),
                                  "external": (sorted(Reads(cl.predicate[cid]).external)
                                               if cl.predicate[cid] is not None else [])}
                            for cid in sorted(cl.members)},
                "permission": dict(sorted(cl.permission.items())), "dead": self.dead, "closure": closures,
                "kinds": dict(sorted(kinds.items())), "checks": [r for r, _c in rows], "external": ext,
                "basis": basis, "laws": laws}


def analysis(doc: dict, r0: dict | None, model: str) -> dict:
    return Analysis(doc, r0, model).run()


def attach_hypotheses(an: dict, hypotheses: dict | None, verdicts: dict | None) -> dict:
    """Each external component's M2 hypothesis (the sidecar's component -> name map) with I21's record of it
    (verdict, result, finding), or null."""
    recs = (verdicts or {}).get("hypotheses") or {}
    for comp, e in an["external"].items():
        name = (hypotheses or {}).get(comp)
        if name is None:
            e["hypothesis"] = None
            continue
        r = recs.get(name) or {}
        e["hypothesis"] = {"name": name, "verdict": r.get("verdict"), "result": r.get("result"),
                           "finding": r.get("finding")}
    return an


# ================================================================================================ derivation views
def entries(an: dict) -> dict:
    """D12: the statement-independent part of every DISCH DERIVATION entry, by law id."""
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


def disch_id(model: str, law: dict) -> str:
    """D11: "<model>:<subform>:<tag>:<class>" (class "all" for revert)."""
    return f"{model}:{law['subform']}:{law['tag']}:{law['class'] or 'all'}"


def ref_doc(an: dict, law: dict) -> dict:
    """D11: the document whose sha256 is the ref "disch:<ID>"."""
    b = next(x for x in an["basis"] if x["tag"] == law["tag"])
    ent = entries(an)[law["law_id"]]
    return {"template": f"holon.rules.disch/{law['subform']}", "template_version": 1, "subform": law["subform"],
            "model": an["model"], "blocked": b["blocked"], "check": b["check"], "check_expr": b["check_expr"],
            "class": law["class"], "closure": ent["closure"], "excluded": ent["excluded"]}


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
