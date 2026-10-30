"""The evidence calculus E1-E6 over the protocol diagram, and the frozen evidence set (whitepaper Def 4.5,
§5.1, §10.2 getter recovery, Prop 6.11 and L3; BUILD_PLAN I14).

  python -m holon evidence [--milestone M2] [--root DIR] [--out PATH]

writes the evidence set of the milestone's fact documents (holon.diagram.fact_documents) to PATH (default
<root>/gen/<M>/evidence.json). The contract (file format, the six levels, the law-anchoring rules L1-L4, GEVID
and the record fields) is the docstring of tests_m2/test_evidence.py; this module implements it.

Inputs, all read from the root only, each listed with its sha256 under "inputs": the fact documents, their
diagrams (gen/M2/diagram/<model>.json, I11), the frozen sorts assignment (gen/M2/sorts/assignment.json, I13),
the target libraries of each holon-facts/0.2 document (holon.gen.targetlib.lib_files) and the E6 vocabulary
spec/M2/lib/evidence_lexical.json, the only target vocabulary of the pass. Nothing here names a target's
functions, fields, carriers or actions: every name comes from those inputs.

Levels (Def 4.5; for parallel paths the highest level supported). Atom endpoints are CODEC, TRANS, MIG and CONS
edges and observer LOAD edges; the per-carrier STORE and LOAD edges aggregate their access sets and are never
endpoints.
  E1  layout inversion, per version (holon.layout.recovers / evidence): an encoder and a decoder whose carriers
      meet, at a version both carry, with at least one getter recovering its field ("inverse"); two encoders
      with an inverse atom at one decoder and version, and recovered fields in common ("common_decoder").
  E2  written via p, read via q, over the diagram's access sets. A "*" term on a sequence carrier is imprecise
      when holon.diagram.access produces it only at its kindless-builtin fallback (re-walked here with the
      walker's drop_kindless instrumentation; the diagram is never rewritten). A pair whose only overlapping
      terms involve an imprecise term is an unresolved entry, never evidence.
  E3  an "==" node of a guard's require whose two operands are path terms (they mention a state field, an
      action input or a let; literals and parameters are not).
  E4  a call of a facts definition or library builtin over action inputs only (no state field), stored by one
      edge's effects (lets substituted) and recomputed, as written, by another TRANS edge.
  E5  a comparison or +/- node whose operands carry the same refined sort under the frozen assignment.
  E6  shared name tokens of two distinct parallel edges, with the sidecar's tokenizer and stopwords.

Adopted transitions documents (I20). The extracted holon-facts/0.3 transitions documents a milestone adopts for
derivation (spec/<M>/lib/derive_extracted.json "documents", holon.sorts.reextract; the sidecar and every document it
lists are inputs) are never fact documents (holon.diagram.fact_documents skips *.extracted.json), but laws are derived
over them (rule SORT-width), so the set covers them: one model each, keyed by the file name without ".json", with
"diagram": null and anchors read from the document itself (transitions_anchors): every action is the edge
TRANS.<action> (actions, trans), and every storage family (a name two contracts declare is "<declared_in>.<name>")
is a carrier whose writers are the actions with a write to it and whose readers are the actions with a
["storage", family] term; the other anchors are empty. E1-E6 are defined over the diagrams of facts 0.1 and 0.2
(holon.diagram.build has no 0.3 adapter). Since I72 (rules Z1-Z4 of tests_m3/test_e2_transitions.py) such a model has
E2 atoms read from the document's own terms (holon.diagram.transitions, whose docstring states the rule: write records,
map and member selections over the families' states, threading positions that are no reads, overlap separated only by
member names and literal keys), when a target milestone's build covers it from the committed diagrams (milestone
M<k>, diagrams None): transitions_atoms gives them, ids, p, q and via as E2 over a diagram gives them, src null, and a
construct the rule does not map is an EvidenceError. E1 and E3-E6 stay uncomputed over these documents. A build for a
test milestone, given its own diagrams, for no milestone or with adopted off gives such a model no atom, so a law over
it then has no evidence (levels []), and its triage is the computed default.

Window views (I66, rule V5 of tests_m3/test_view_evidence.py). A build that reads the committed diagrams (diagrams
None) for a target milestone (M<k>) also models every window view of gen_milestone(M) (holon.diagram.window_views:
holon.differential's views, gen/<M>/extracted/*.json naming a window declaration spec/<M>/lib/window_*.json): one model
each, keyed by the view's stem, over its committed diagram gen/<gm>/diagram/<stem>.json, with I14's atoms for a
facts-0.2 document over the view and its libraries (holon.gen.targetlib anchors them to its abstraction's). A view is
never a fact document: E5 reads the frozen assignment's model of its stem when there is one and otherwise gives no
operand a sort (no E5 atom). Its inputs are the view, its diagram and its window declaration; the files read only to
find the views are not inputs. A build given its own diagrams, a build for a test milestone and a build for no
milestone model no view, and a view whose stem is another model's is an EvidenceError.

Pure Python, standard library and holon imports only; the document is a deterministic function of its inputs
(sorted keys, ids derived from content, no timestamps). Unresolved pairs are results, not errors; an input that is
missing, unreadable, stale or holds a construct the pass cannot map is an EvidenceError and nothing is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

from .. import facts as F
from .. import layout as LAYOUT
from ..gen.targetlib import Library, LibError, lib_files
from ..sorts import grammar as G
from ..sorts.flow import span
from . import access as A
from . import transitions as TR
from .build import ROOT, Machine
from .model import DiagramError

EVIDENCE_VERSION = "holon-evidence/0.1"
LEVELS = ("E1", "E2", "E3", "E4", "E5", "E6")
STRENGTH = {"E1": "strong", "E2": "strong", "E3": "strong", "E4": "strong", "E5": "medium", "E6": "weak"}
LEXICAL = Path("spec") / "M2" / "lib" / "evidence_lexical.json"
SCHEMA = Path("spec") / "schemas" / "evidence.schema.json"
OVERRIDES = Path("config") / "evidence_overrides.json"
ENDPOINT_KINDS = ("CODEC", "TRANS", "MIG", "CONS")
E5_OPS = ("+", "-", "==", "!=", "<", "<=", ">", ">=")
PATH_BINDERS = ("Trace", "State", "Act", "Reach")   # L3: the law ranges over the machine's own steps
OVERRIDE_TRIAGES = ("finding", "intent_question")
RECORD_FIELDS = ("evidence_levels", "evidence_triage", "evidence_override")
IR01, IR02, IR03 = "holon-ir/0.1", "holon-ir/0.2", "holon-ir/0.3"
FACTS01, FACTS02, FACTS03 = "holon-facts/0.1", "holon-facts/0.2", "holon-facts/0.3"
_NUMERIC = re.compile(r"^(\d+)(?:\.\.(\d+))?$")
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_MACH = re.compile(r"^Mach\([1-9][0-9]*\)$")


class EvidenceError(ValueError):
    """An input the pass cannot read or map (no silent drops): nothing is written."""


# ====================================================================== text and hashes
def canonical_sha256(obj) -> str:
    """sha256 of the canonical JSON text: sorted keys, separators (",", ":"), UTF-8, no ASCII escaping."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render(doc: dict) -> str:
    """The file text of an evidence document."""
    return json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def body_sha256(doc: dict) -> str:
    """evidence_sha256: the document without evidence_sha256 and inputs (computed like I13's sorts_sha256)."""
    return canonical_sha256({k: v for k, v in doc.items() if k not in ("evidence_sha256", "inputs")})


def gen_milestone(milestone: str | None) -> str:
    """The milestone whose gen/ tree holds the evidence set and its inputs: M2 for M0, M1, M2 (and for anything
    that is not M<k>), M<k> itself from M3 on."""
    m = re.fullmatch(r"M(\d+)", milestone or "")
    return milestone if m and int(m.group(1)) >= 3 else "M2"


def evidence_path(milestone: str | None) -> Path:
    return Path("gen") / gen_milestone(milestone) / "evidence.json"


class _Inputs:
    """Every file the pass reads, with its sha256 (the document's "inputs")."""

    def __init__(self, root: Path):
        self.root = root
        self.files: dict[str, str] = {}

    def rel(self, p: Path) -> str:
        try:
            return Path(p).resolve().relative_to(self.root).as_posix()
        except ValueError:
            raise EvidenceError(f"{p} is not inside the root {self.root}") from None

    def read_bytes(self, p: Path) -> bytes:
        try:
            b = Path(p).read_bytes()
        except OSError as e:
            raise EvidenceError(f"{self.rel(p)}: unreadable ({type(e).__name__}: {e})") from e
        self.files[self.rel(p)] = hashlib.sha256(b).hexdigest()
        return b

    def read_json(self, p: Path):
        b = self.read_bytes(p)
        try:
            return json.loads(b.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise EvidenceError(f"{self.rel(p)}: not JSON ({e})") from e

    def listing(self) -> list[dict]:
        return [{"path": p, "sha256": s} for p, s in sorted(self.files.items())]


# ====================================================================== shared helpers
def versions(label) -> list[int]:
    """A diagram version label as integers: "a..b" a range, "a,b" a list, "a" one, null none."""
    if label is None:
        return []
    out: set[int] = set()
    try:
        for part in str(label).split(","):
            if ".." in part:
                lo, hi = part.split("..")
                out |= set(range(int(lo), int(hi) + 1))
            else:
                out.add(int(part))
    except ValueError:
        raise EvidenceError(f"version label {label!r} is not a/a..b/a,b") from None
    return sorted(out)


def subterms(e):
    """Every list node of a facts expression, pre-order (record literals and updates included)."""
    if isinstance(e, list) and e:
        yield e
        for x in e[1:]:
            if isinstance(x, dict):
                for v in x.values():
                    yield from subterms(v)
            else:
                yield from subterms(x)


def _atom(model: str, level: str, p: str, q: str, via: dict, src) -> dict:
    return {"id": f"{model}:{level}:{p}:{q}:{canonical_sha256(via)[:8]}", "model": model, "level": level,
            "p": p, "q": q, "via": via, "src": src}


def _interval(term: str):
    m = _NUMERIC.match(term)
    return (int(m.group(1)), int(m.group(2) or m.group(1))) if m else None


def overlap(a: str, b: str) -> bool:
    """Index terms overlap when either is "*", or both are numeric and intersect, or one is symbolic (index
    expressions are evaluated in the states of different steps, so their syntax cannot separate them)."""
    if a == A.WHOLE or b == A.WHOLE:
        return True
    ia, ib = _interval(a), _interval(b)
    if ia is not None and ib is not None:
        return ia[0] <= ib[1] and ib[0] <= ia[1]
    return True


class Lexicon:
    """The E6 vocabulary: spec/M2/lib/evidence_lexical.json verbatim (names, tokenizer, stopwords, rule)."""

    def __init__(self, doc: dict):
        try:
            tk = doc["tokenize"]
            self.ident = re.compile(tk["identifier"])
            self.min_length = int(tk["min_length"])
            case = tk["case"]
            self.stop = set(doc["stopwords"])
            self.kinds = set(doc["names"])
        except (KeyError, TypeError, ValueError, re.error) as e:
            raise EvidenceError(f"{LEXICAL.as_posix()}: malformed ({type(e).__name__}: {e})") from e
        if case != "lower":
            raise EvidenceError(f"{LEXICAL.as_posix()}: case {case!r} is not one the pass reads")
        unread = sorted(self.kinds - {"CODEC", "TRANS"})
        if unread:
            raise EvidenceError(f"{LEXICAL.as_posix()}: names for edge kinds {unread}, which the pass cannot read")

    def tokens(self, text: str) -> set[str]:
        out = set()
        for ident in self.ident.findall(text):
            for part in ident.split("_"):
                if not part:
                    continue
                for t in _CAMEL.split(part):
                    t = t.lower()
                    if len(t) >= self.min_length and t not in self.stop:
                        out.add(t)
        return out

    def edge_tokens(self, edge: dict) -> set[str]:
        """Tokens of an edge's names: a CODEC edge's source[].fn, a TRANS edge's component (the action name)."""
        if edge["kind"] not in self.kinds:
            return set()
        if edge["kind"] == "CODEC":
            names = [s["fn"] for s in edge.get("source") or [] if isinstance(s, dict) and isinstance(s.get("fn"), str)]
        else:
            names = [edge["component"]]
        return set().union(set(), *(self.tokens(n) for n in names))


# ====================================================================== anchors
def anchors(dg: dict, sites: list, model: str) -> dict:
    """What laws name, from the model's diagram (and, for "sites", the frozen assignment's sites)."""
    es = dg["edges"]
    by = {e["id"]: e for e in es}
    trans = sorted(e["id"] for e in es if e["kind"] == "TRANS")
    actions = {by[i]["component"]: i for i in trans}
    reasons: dict[str, set] = {}
    for i in trans:
        for g in by[i].get("guards") or []:
            if g.get("reason") is not None:
                reasons.setdefault(str(g["reason"]), set()).add(i)
    carriers = {}
    for e in es:
        if e["kind"] == "STORE":
            load = by.get(f"LOAD.{e['tgt']}") or {}
            carriers[e["tgt"]] = {"writers": sorted(e.get("writers") or []),
                                  "readers": sorted(load.get("readers") or [])}
    preds = dg.get("predicates") or {}
    site_edges = {}
    for s in sites:
        if s.get("model") == model:
            site_edges[s["id"]] = sorted({actions[o["action"]] for o in s.get("occurrences") or []
                                          if o.get("action") in actions})
    return {
        "codec": {e["model_fn"]: e["id"] for e in es if e["kind"] == "CODEC"},
        "domains": {p: sorted(e["id"] for e in es if e["kind"] == "CODEC" and e.get("domain") == p) for p in preds},
        "actions": actions,
        "reasons": {k: sorted(v) for k, v in reasons.items()},
        "permissionless": sorted(i for i in trans if by[i].get("permissionless")),
        "observers": {e["component"]: e["id"] for e in es if e["kind"] == "LOAD" and e.get("observer")},
        "migrations": {e["component"]: e["id"] for e in es if e["kind"] == "MIG"},
        "consumers": {e["model_fn"]: e["id"] for e in es if e["kind"] == "CONS"},
        "carriers": carriers,
        "trans": trans,
        "sites": site_edges,
    }


def endpoints(dg: dict) -> list[dict]:
    """CODEC, TRANS, MIG and CONS edges and observer LOAD edges, by id (never the STORE/LOAD aggregates)."""
    return sorted((e for e in dg["edges"]
                   if e["kind"] in ENDPOINT_KINDS or (e["kind"] == "LOAD" and e.get("observer"))),
                  key=lambda e: e["id"])


# ====================================================================== E1
def e1(model: str, facts: dict, dg: dict) -> list[dict]:
    es = sorted(dg["edges"], key=lambda e: e["id"])
    enc = [e for e in es if e["kind"] == "CODEC" and e.get("fn_kind") == "encoder"]
    dec = [e for e in es if e["kind"] == "CODEC" and e.get("fn_kind") == "decoder"]
    out, inverse = [], {}
    for e in enc:
        for d in dec:
            if e["tgt"] != d["src"]:
                continue
            for v in sorted(set(versions(e["version"])) & set(versions(d["version"]))):
                try:
                    r = LAYOUT.evidence(facts, e["model_fn"], d["model_fn"], v)
                except (KeyError, ValueError) as x:
                    raise EvidenceError(f"{model}: E1 on ({e['id']}, {d['id']}) at version {v}: "
                                        f"{type(x).__name__}: {x}") from x
                if r["fields"]:
                    via = {"kind": "inverse", "version": v, "fields": r["fields"], "not_recovered": r["not_recovered"]}
                    out.append(_atom(model, "E1", e["id"], d["id"], via, None))
                    inverse[(e["id"], d["id"], v)] = r["fields"]
    for i, e1_ in enumerate(enc):
        for e2_ in enc[i + 1:]:
            if (e1_["src"], e1_["tgt"]) != (e2_["src"], e2_["tgt"]):
                continue
            for d in dec:
                for v in sorted({k[2] for k in inverse if k[1] == d["id"]}):
                    a, b = inverse.get((e1_["id"], d["id"], v)), inverse.get((e2_["id"], d["id"], v))
                    if a is None or b is None:
                        continue
                    common = [f for f in a if f in b]
                    if common:
                        via = {"kind": "common_decoder", "version": v, "decoder": d["id"], "fields": common}
                        out.append(_atom(model, "E1", e1_["id"], e2_["id"], via, None))
    return out


# ====================================================================== E2
def _walk(m: Machine, kind: str, name: str, item: dict, drop: bool) -> tuple[set, set]:
    """(reads, writes) of one TRANS, MIG or observer edge, as holon.diagram.build walks it."""
    w = m.walker()
    w.drop_kindless = drop
    if kind == "TRANS":
        sc = m.scope(n for n, _ in item["inputs"])
        for g in item["guards"]:
            if "let" in g:
                w.read(g["expr"], sc)
                sc.local[g["let"]] = sc.resolve(g["expr"])
            elif "require" in g:
                w.read(g["require"], sc)
        for fld, e in item["effects"].items():
            w.write(fld, e, sc)
        return set(w.reads), set(w.writes) | A.step_writes()
    if kind == "MIG":
        sc = m.scope(n for n, _ in item.get("inputs", []))
        for fld, e in item["effects"].items():
            w.write(fld, e, sc)
        return set(w.reads), set(w.writes)
    w.read(item["body"], m.scope())
    return set(w.reads), set(w.writes)


def imprecision(model: str, facts: dict, dg: dict, m: Machine) -> dict[str, tuple[set, set]]:
    """{edge id: (imprecise reads, imprecise writes)} of the walked edges: the "*" terms on sequence carriers that
    the walk without the kindless-builtin fallback lacks. The full walk must reproduce the diagram's access sets
    (else the diagram is stale, or the walk diverged from holon.diagram.build)."""
    keyed = {c["id"] for c in dg["carriers"] if c.get("key_space") is not None}
    by = {e["id"]: e for e in dg["edges"]}
    items = [("TRANS", a["name"], a) for a in facts.get("actions", [])]
    items += [("MIG", n, g) for n, g in facts.get("migrations", {}).items()]
    items += [("LOAD", n, o) for n, o in facts.get("observers", {}).items()]
    out = {}
    for kind, name, item in items:
        eid = {"TRANS": f"TRANS.{name}", "MIG": f"MIG.{name}", "LOAD": f"LOAD.obs.{name}"}[kind]
        if eid not in by:
            raise EvidenceError(f"{model}: the diagram has no edge {eid} for the facts' {kind} {name}")
        try:
            r1, w1 = _walk(m, kind, name, item, False)
            r2, w2 = _walk(m, kind, name, item, True)
        except A.AccessError as e:
            raise EvidenceError(f"{model}: {eid}: {e}") from e
        acc = by[eid]["access"]
        if {tuple(t) for t in acc["reads"]} != r1 or {tuple(t) for t in acc["writes"]} != w1:
            raise EvidenceError(f"{model}: {eid}: the diagram's access sets differ from the facts' (regenerate "
                                "gen/<M>/diagram with `holon diagram`)")
        out[eid] = ({t for t in r1 - r2 if t[1] == A.WHOLE and t[0] in keyed},
                    {t for t in w1 - w2 if t[1] == A.WHOLE and t[0] in keyed})
    return out


def e2(model: str, dg: dict, imprecise: dict) -> tuple[list[dict], list[dict]]:
    atoms, unresolved = [], []
    eps = endpoints(dg)

    def terms(e, side):
        out: dict[str, set] = {}
        for c, k in e["access"][side]:
            out.setdefault(c, set()).add(k)
        return out
    for p in eps:
        pw = terms(p, "writes")
        ipw = {c: {k for cc, k in imprecise.get(p["id"], (set(), set()))[1] if cc == c} for c in pw}
        for q in eps:
            qr = terms(q, "reads")
            iqr = {c: {k for cc, k in imprecise.get(q["id"], (set(), set()))[0] if cc == c} for c in qr}
            for c in sorted(set(pw) & set(qr)):
                W, R = pw[c], qr[c]
                PW, PR = W - ipw[c], R - iqr[c]
                ws = sorted(w for w in PW if any(overlap(w, r) for r in PR))
                if ws:
                    rs = sorted(r for r in PR if any(overlap(w, r) for w in PW))
                    atoms.append(_atom(model, "E2", p["id"], q["id"], {"carrier": c, "writes": ws, "reads": rs}, None))
                    continue
                ow = {w for w in W if any(overlap(w, r) for r in R)}
                if not ow:
                    continue
                orr = {r for r in R if any(overlap(w, r) for w in W)}
                imp = (["read"] if orr <= iqr[c] else []) + (["write"] if ow <= ipw[c] else [])
                if not imp:
                    raise EvidenceError(f"{model}: ({p['id']}, {q['id']}, {c}) overlaps only through imprecise "
                                        "terms on both sides of distinct pairs: a case the contract does not map")
                unresolved.append({"id": f"{model}:unresolved:{p['id']}:{q['id']}:{c}", "model": model, "p": p["id"],
                                   "q": q["id"], "carrier": c, "imprecise": imp})
    return atoms, unresolved


# ====================================================================== facts 0.2 scopes
class Names:
    """How a facts-0.2 name resolves inside one action, migration or observer: a let, then an input, then a
    parameter, then a state field (holon.diagram.access.Scope's order)."""

    def __init__(self, facts: dict, owner: str | None = None, inputs=(), lets: dict | None = None):
        self.owner = owner
        self.inputs = set(inputs)
        self.lets = dict(lets or {})
        self.params = set(facts.get("params", {}))
        self.state = {row[0]: row[1] for row in facts["state"]}

    def kind(self, name: str) -> str | None:
        if name in self.lets:
            return "let"
        if name in self.inputs:
            return "input"
        if name in self.params:
            return "param"
        if name in self.state:
            return "state"
        return None

    def state_type(self, e) -> str | None:
        return self.state[e] if isinstance(e, str) and self.kind(e) == "state" else None


def _lets(action: dict) -> dict:
    return {g["let"]: g["expr"] for g in action["guards"] if "let" in g}


def _let_sub(action: dict) -> dict:
    """let name -> its expression with earlier lets substituted (over inputs, parameters and state)."""
    sub: dict = {}
    for g in action.get("guards", []):
        if "let" in g:
            sub[g["let"]] = A.subst(g["expr"], sub)
    return sub


# ====================================================================== E3
def e3(model: str, facts: dict) -> list[dict]:
    out = []

    def path(x, nm: Names) -> bool:
        return any(nm.kind(v) in ("let", "input", "state") for v in A.free_vars(x))
    for a in facts.get("actions", []):
        nm = Names(facts, a["name"], (n for n, _ in a["inputs"]), _lets(a))
        for i, g in enumerate(a["guards"]):
            if "require" not in g:
                continue
            for n in subterms(g["require"]):
                if n[0] == "==" and len(n) == 3 and path(n[1], nm) and path(n[2], nm):
                    via = {"where": f"guards[{i}].require", "reason": g.get("reason"), "operands": [n[1], n[2]]}
                    eid = f"TRANS.{a['name']}"
                    out.append(_atom(model, "E3", eid, eid, via, span(g.get("src"))))
    return out


# ====================================================================== E4
def e4(model: str, facts: dict, lib: Library, m: Machine) -> list[dict]:
    defs = set(facts.get("defs", {}))

    def qualifying(expr, nm: Names, sub: dict):
        """Functions f of every qualifying call in expr: f a facts def or library builtin (not a generic builtin,
        not a shadow projection), at least one argument, no argument mentioning a state field and one mentioning
        an input, once the edge's lets are substituted into the arguments (sub; nm then resolves no let)."""
        for n in subterms(expr):
            if n[0] != "call" or len(n) < 3:
                continue
            f, args = n[1], [A.subst(x, sub) for x in n[2:]]
            if f in A.GENERIC_ROLES or f in m.roles.es or (f not in defs and f not in lib.builtins):
                continue
            kinds = {nm.kind(v) for x in args for v in A.free_vars(x)}
            if "state" not in kinds and "input" in kinds:
                yield f

    stores: dict[str, dict[str, set]] = {}     # edge -> f -> positions
    recomputes: dict[str, dict[str, set]] = {}
    owners = [("TRANS", a["name"], a) for a in facts.get("actions", [])]
    owners += [("MIG", n, g) for n, g in facts.get("migrations", {}).items()]
    for kind, name, item in owners:
        eid = f"{kind}.{name}"
        sub = _let_sub(item) if kind == "TRANS" else {}
        nm = Names(facts, name, (n for n, _ in item.get("inputs", [])))   # names once the lets are substituted
        for fld, e in item["effects"].items():   # stored: the effect with the lets substituted
            for f in qualifying(A.subst(e, sub), nm, {}):
                stores.setdefault(eid, {}).setdefault(f, set()).add(f"effects.{fld}")
        if kind != "TRANS":
            continue
        for i, g in enumerate(item["guards"]):   # recomputed: the call as written, its arguments substituted
            pos, expr = (f"guards[{i}].require", g["require"]) if "require" in g else (f"guards[{i}].expr", g["expr"])
            for f in qualifying(expr, nm, sub):
                recomputes.setdefault(eid, {}).setdefault(f, set()).add(pos)
        for fld, e in item["effects"].items():
            for f in qualifying(e, nm, sub):
                recomputes.setdefault(eid, {}).setdefault(f, set()).add(f"effects.{fld}")
    out = []
    for p in sorted(stores):
        for q in sorted(recomputes):
            if p == q:
                continue
            for f in sorted(set(stores[p]) & set(recomputes[q])):
                via = {"fn": f, "stored": sorted(stores[p][f]), "recomputed": sorted(recomputes[q][f])}
                out.append(_atom(model, "E4", p, q, via, None))
    return out


# ====================================================================== E5
def refined(s: str) -> bool:
    """A refined sort: not Nat (unrefined), Bool, a Mach(w) or a union (writers delivering distinct sorts)."""
    return not (s == G.UNREFINED_TEXT or s == "Bool" or _MACH.match(s) or " + " in s)


class Sorts:
    """Operand sorts from the frozen assignment of one model (rule E5)."""

    def __init__(self, facts: dict, assignment: dict, lib: Library):
        self.a = assignment
        self.records = set(facts.get("types", {}))
        self.def_types = {n: d.get("type") for n, d in facts.get("defs", {}).items()}
        self.lib_types = {n: b.get("type") for n, b in lib.builtins.items()}

    def key(self, name: str, nm: Names) -> str | None:
        k = nm.kind(name)
        if k in ("let", "input") and nm.owner is not None:
            return f"{nm.owner}.{name}"
        if k in ("state", "param"):
            return name
        return None

    def record_type(self, x, nm: Names, depth: int = 0) -> str | None:
        if depth > 64:
            raise EvidenceError("let bindings nest too deep (a cycle?)")
        if isinstance(x, list) and x and x[0] == "call":
            f = x[1]
            if f == "nth" and len(x) == 4:
                st = nm.state_type(x[2])
                inner = st[5:-1] if st and st.startswith("List<") and st.endswith(">") else None
                return inner if inner in self.records else None
            t = self.def_types.get(f) if f in self.def_types else self.lib_types.get(f)
            return t if t in self.records else None
        if isinstance(x, str) and nm.kind(x) == "let":
            return self.record_type(nm.lets[x], nm, depth + 1)
        return None

    def sort(self, e, nm: Names) -> str | None:
        if isinstance(e, bool) or isinstance(e, int):
            return None
        if isinstance(e, str):
            k = self.key(e, nm)
            return self.a.get(k) if k else None
        if not isinstance(e, list) or not e:
            return None
        op = e[0]
        if op == "get" and len(e) == 3:
            t = self.record_type(e[1], nm)
            return self.a.get(f"{t}.{e[2]}") if t else None
        if op == "call" and len(e) == 4 and e[1] == "nth" and nm.state_type(e[2]) == "List<Nat>":
            return self.a.get(e[2])
        if op in ("+", "-") and len(e) == 3:
            a, b = self.sort(e[1], nm), self.sort(e[2], nm)
            return G.affine(op, a, b) if a is not None and b is not None else None
        if op == "?" and len(e) == 4:
            a, b = self.sort(e[2], nm), self.sort(e[3], nm)
            return a if a is not None and a == b else None
        return None


def e5(model: str, facts: dict, assignment: dict, lib: Library) -> list[dict]:
    S = Sorts(facts, assignment, lib)
    out = []

    def scan(eid: str, where: str, expr, nm: Names, src):
        for n in subterms(expr):
            if n[0] in E5_OPS and len(n) == 3:
                a, b = S.sort(n[1], nm), S.sort(n[2], nm)
                if a is not None and a == b and refined(a):
                    via = {"where": where, "op": n[0], "operands": [n[1], n[2]], "sort": a}
                    out.append(_atom(model, "E5", eid, eid, via, src))
    for a in facts.get("actions", []):
        eid = f"TRANS.{a['name']}"
        nm = Names(facts, a["name"], (n for n, _ in a["inputs"]), _lets(a))
        for i, g in enumerate(a["guards"]):
            if "require" in g:
                scan(eid, f"guards[{i}].require", g["require"], nm, span(g.get("src")))
            else:
                scan(eid, f"guards[{i}].expr", g["expr"], nm, span(g.get("src")))
        esrc = span(a.get("effects_src") or a.get("src"))
        for fld, e in a["effects"].items():
            scan(eid, f"effects.{fld}", e, nm, esrc)
    for name, g in facts.get("migrations", {}).items():
        nm = Names(facts, name, (n for n, _ in g.get("inputs", [])))
        for fld, e in g["effects"].items():
            scan(f"MIG.{name}", f"effects.{fld}", e, nm, span(g.get("src")))
    for name, o in facts.get("observers", {}).items():
        scan(f"LOAD.obs.{name}", "body", o["body"], Names(facts), None)
    return out


# ====================================================================== E6
def e6(model: str, dg: dict, lex: Lexicon) -> list[dict]:
    eps = [e for e in endpoints(dg) if e["kind"] in lex.kinds]
    toks = {e["id"]: lex.edge_tokens(e) for e in eps}
    out = []
    for i, p in enumerate(eps):
        for q in eps[i + 1:]:
            if (p["kind"], p["src"], p["tgt"]) != (q["kind"], q["src"], q["tgt"]):
                continue
            shared = sorted(toks[p["id"]] & toks[q["id"]])
            if shared:
                out.append(_atom(model, "E6", p["id"], q["id"], {"tokens": shared}, None))
    return out


# ====================================================================== build
def _model(rel: str, facts: dict, sha: str, dg: dict, amodel: dict, sites: list, lex: Lexicon, root: Path,
           inp: _Inputs) -> tuple[dict, list, list]:
    stem = Path(rel).stem
    fv = facts.get("facts_version")
    for k, want in (("model", stem), ("facts", rel), ("facts_sha256", sha), ("facts_version", fv)):
        if dg.get(k) != want:
            raise EvidenceError(f"{stem}: the diagram's {k} is {dg.get(k)!r}, not {want!r} (a stale diagram: "
                                "regenerate it with `holon diagram`)")
    an = anchors(dg, sites, stem)
    atoms, unresolved = [], []
    if fv == FACTS01:
        atoms += e1(stem, facts, dg)
        atoms += e2(stem, dg, {})[0]
    elif fv == FACTS02:
        path = root / rel
        ctx = SimpleNamespace(f=facts, path=path, root=root, inputs={})
        try:
            m = Machine(ctx)
        except A.AccessError as e:
            raise EvidenceError(f"{stem}: definitions: {e}") from e
        for p in lib_files(path, root):
            inp.read_bytes(p)
        lib = Library.for_facts(path, facts.get("params", {}), root=root)
        a2, u2 = e2(stem, dg, imprecision(stem, facts, dg, m))
        atoms += a2
        unresolved += u2
        atoms += e3(stem, facts)
        atoms += e4(stem, facts, lib, m)
        atoms += e5(stem, facts, amodel, lib)
    else:
        raise EvidenceError(f"{rel}: facts_version {fv!r} has no evidence rules")
    atoms += e6(stem, dg, lex)
    return an, atoms, unresolved


def _storage_terms(t, acc: set) -> None:
    if isinstance(t, list):
        if len(t) == 2 and t[0] == "storage" and isinstance(t[1], str):
            acc.add(t[1])
        for x in t:
            _storage_terms(x, acc)
    elif isinstance(t, dict):
        for x in t.values():
            _storage_terms(x, acc)


def _writes(t, acc: set) -> None:
    """The families of every write record ({"family", "path", "value", ..}) at any depth (loop bodies included)."""
    if isinstance(t, dict):
        if isinstance(t.get("family"), str) and "path" in t and "value" in t:
            acc.add(t["family"])
        for x in t.values():
            _writes(x, acc)
    elif isinstance(t, list):
        for x in t:
            _writes(x, acc)


def transitions_anchors(doc: dict) -> dict:
    """The anchors of an adopted transitions document (module docstring, "Adopted transitions documents")."""
    acts = [a for a in doc.get("actions") or [] if isinstance(a, dict) and isinstance(a.get("name"), str)]
    actions = {a["name"]: f"TRANS.{a['name']}" for a in sorted(acts, key=lambda a: a["name"])}
    entries = [s for s in (doc.get("storage") or []) + (doc.get("inherited_storage") or []) if isinstance(s, dict)]
    names = [s.get("name") for s in entries]
    fams = sorted({f"{s['declared_in']}.{s['name']}" if names.count(s.get("name")) > 1 and s.get("declared_in")
                   else s["name"] for s in entries if isinstance(s.get("name"), str)})
    writes, reads = {}, {}
    for a in acts:
        w, r = set(), set()
        _writes(a, w)
        _storage_terms(a, r)
        writes[a["name"]], reads[a["name"]] = w, r
    carriers = {f: {"writers": sorted(actions[n] for n in actions if f in writes[n]),
                    "readers": sorted(actions[n] for n in actions if f in reads[n])} for f in fams}
    return {"codec": {}, "domains": {}, "actions": actions, "reasons": {}, "permissionless": [], "observers": {},
            "migrations": {}, "consumers": {}, "carriers": carriers, "trans": sorted(actions.values()), "sites": {}}


def transitions_atoms(model: str, doc: dict) -> list[dict]:
    """The E2 atoms of an adopted transitions document's model (module docstring, "Adopted transitions documents";
    holon.diagram.transitions), sorted by id; EvidenceError on a construct the rule does not map."""
    try:
        pairs = TR.e2_pairs(doc)
    except TR.TransitionsError as e:
        raise EvidenceError(f"{model}: a construct the E2 rule over transitions documents does not map ({e})") from e
    atoms = [_atom(model, "E2", f"TRANS.{p}", f"TRANS.{q}", {"carrier": f, "writes": ws, "reads": rs}, None)
             for p, q, f, ws, rs in pairs]
    return sorted(atoms, key=lambda a: a["id"])


def adopted_documents(gm: str, root: Path, inp: "_Inputs") -> list[tuple[str, bytes, dict]]:
    """(path, bytes, document) of every transitions document spec/<gm>/lib/derive_extracted.json adopts (I20)."""
    side = root / "spec" / gm / "lib" / "derive_extracted.json"
    if not side.exists():
        return []
    sc = inp.read_json(side)
    out = []
    for rel in sorted(sc.get("documents") or [] if isinstance(sc, dict) else []):
        raw = inp.read_bytes(root / rel)
        try:
            d = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise EvidenceError(f"{rel}: not JSON ({e})") from e
        if isinstance(d, dict) and d.get("facts_version") == FACTS03 and (d.get("extraction") or {}).get("kind") \
                == "transitions":
            out.append((rel, raw, d))
    return out


def bundle_documents(gm: str, root: Path, inp: "_Inputs") -> list[tuple[str, bytes, dict]]:
    """(path, bytes, document) of every transitions document a law of the milestone's bundle laws is over (I86): the
    members of the bundle declaration beside the corpus spec/<gm>/lib/bundle_laws.json names, each document the
    facts of one of the milestone's bundle laws (laws/<gm>/DERIVATION.json entries with a member)."""
    side = root / "spec" / gm / "lib" / "bundle_laws.json"
    der = root / "laws" / gm / "DERIVATION.json"
    if not side.exists() or not der.exists():
        return []
    sc = inp.read_json(side)
    corpus = ((sc.get("witnesses") or {}).get("corpus") if isinstance(sc, dict) else None)
    if not isinstance(corpus, str):
        return []
    decl_p = root / Path(corpus).parent / "bundle.json"
    if not decl_p.is_file():
        return []
    decl = inp.read_json(decl_p)
    dv = json.loads(der.read_text(encoding="utf-8"))
    facts = {e.get("facts") for e in dv.get("laws") or [] if isinstance(e, dict) and e.get("member")}
    out = []
    for m in decl.get("members") or []:
        rel = ((m.get("document") or {}).get("path") if isinstance(m, dict) else None)
        if not isinstance(rel, str) or rel not in facts:
            continue
        raw = inp.read_bytes(root / rel)
        try:
            d = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise EvidenceError(f"{rel}: not JSON ({e})") from e
        if isinstance(d, dict) and d.get("facts_version") == FACTS03:
            out.append((rel, raw, d))
    return sorted(out, key=lambda x: x[0])


def versioned_documents(gm: str, root: Path, inp: "_Inputs") -> list[tuple[str, bytes, dict, dict]]:
    """(path, bytes, document, anchors) of the versioned document spec/<gm>/lib/versions.json writes (I28,
    holon.versions), anchors only: the transitions anchors of its versions' documents (each one the sidecar's
    documents entry names, read with its sha256 checked), merged (an action of every version is the one edge
    TRANS.<name>, a family carried by the writers and readers of any version)."""
    side = root / "spec" / gm / "lib" / "versions.json"
    if not side.exists():
        return []
    sc = inp.read_json(side)
    rel = ((sc.get("outputs") or {}).get("versions") if isinstance(sc, dict) else None)
    if not isinstance(rel, str) or not (root / rel).is_file():
        return []
    raw = inp.read_bytes(root / rel)
    try:
        d = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise EvidenceError(f"{rel}: not JSON ({e})") from e
    if not isinstance(d, dict) or not isinstance(d.get("documents"), dict):
        raise EvidenceError(f"{rel}: not a versioned document (no documents)")
    an = {"codec": {}, "domains": {}, "actions": {}, "reasons": {}, "permissionless": [], "observers": {},
          "migrations": {}, "consumers": {}, "carriers": {}, "trans": [], "sites": {}}
    for vid in sorted(d["documents"]):
        e = d["documents"][vid]
        vraw = inp.read_bytes(root / e["path"])
        if hashlib.sha256(vraw).hexdigest() != e.get("sha256"):
            raise EvidenceError(f"{rel}: version {vid}'s document {e['path']} is not the one it records")
        va = transitions_anchors(json.loads(vraw.decode("utf-8")))
        an["actions"].update(va["actions"])
        for f, c in va["carriers"].items():
            have = an["carriers"].setdefault(f, {"writers": [], "readers": []})
            for k in ("writers", "readers"):
                have[k] = sorted(set(have[k]) | set(c[k]))
    an["actions"] = dict(sorted(an["actions"].items()))
    an["carriers"] = dict(sorted(an["carriers"].items()))
    an["trans"] = sorted(set(an["actions"].values()))
    return [(rel, raw, d, an)]


def build(fact_paths, root: Path | str = ROOT, diagrams: dict | None = None, assignment: dict | None = None,
          milestone: str | None = None, components: list | None = None, adopted: bool = True) -> dict:
    """The evidence document of the given fact documents (paths inside root); see the module docstring. diagrams:
    {model stem: diagram JSON} (default: the committed gen/M2/diagram/<stem>.json); assignment: a document shaped
    like gen/M2/sorts/assignment.json, of which only models[<stem>]["assignment"], "sites" and "sorts_sha256" are
    read (default: the committed one; from M3 on, null when the milestone has none: no sorts assignment covers an M3
    document until I30). components: linked codec documents (I24, rule X7), each (path, diagram JSON or None for the
    committed gen/<M>/diagram/<role>.json): one model per component, with its E1, E2 and E6 atoms. adopted: whether the
    transitions documents the milestone adopts are covered (anchors only, I20; only when a milestone is given).
    Independent of the order of fact_paths."""
    root = Path(root).resolve()
    inp = _Inputs(root)
    gm = gen_milestone(milestone)
    lex = Lexicon(inp.read_json(root / LEXICAL))
    if assignment is None:
        ap = root / "gen" / gm / "sorts" / "assignment.json"
        if not fact_paths and gm != "M2" and not ap.exists():
            assignment = {"models": {}, "sites": [], "sorts_sha256": None}
        else:
            assignment = inp.read_json(ap)
    if not isinstance(assignment, dict) or not isinstance(assignment.get("models"), dict):
        raise EvidenceError("the sorts assignment has no models")
    sites = assignment.get("sites") or []
    rels = sorted({inp.rel(Path(p)) for p in fact_paths})
    stems = [Path(r).stem for r in rels]
    if len(set(stems)) != len(stems):
        raise EvidenceError(f"two fact documents share a model name: {sorted(s for s in stems if stems.count(s) > 1)}")
    models, atoms, unresolved = {}, [], []
    for rel in rels:
        stem = Path(rel).stem
        raw = inp.read_bytes(root / rel)
        sha = hashlib.sha256(raw).hexdigest()
        try:
            facts = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise EvidenceError(f"{rel}: not JSON ({e})") from e
        if diagrams is not None:
            if stem not in diagrams:
                raise EvidenceError(f"{stem}: no diagram was passed in")
            dg, drel = diagrams[stem], None
        else:
            drel = f"gen/{gm}/diagram/{stem}.json"
            dg = inp.read_json(root / drel)
        amodel = assignment["models"].get(stem)
        if not isinstance(amodel, dict) or not isinstance(amodel.get("assignment"), dict):
            raise EvidenceError(f"{stem}: the sorts assignment has no model {stem} (regenerate it with `holon sorts`)")
        try:
            an, a, u = _model(rel, facts, sha, dg, amodel["assignment"], sites, lex, root, inp)
        except (KeyError, TypeError, IndexError, AttributeError, DiagramError, LibError) as e:
            raise EvidenceError(f"{rel}: a construct the evidence pass cannot map ({type(e).__name__}: {e})") from e
        models[stem] = {"facts": rel, "facts_sha256": sha, "facts_version": facts.get("facts_version"),
                        "diagram": drel, "anchors": an}
        atoms += a
        unresolved += u
    # I66: a target milestone's window views over their committed diagrams (module docstring, "Window views"); a build
    # given its own diagrams, for a test milestone or for no milestone models none
    if diagrams is None and re.fullmatch(r"M\d+", milestone or ""):
        from . import window_views
        from ..gen.targetlib import window_declaration
        for vp in window_views(gm, root):
            rel, stem = inp.rel(vp), vp.stem
            if stem in models:
                raise EvidenceError(f"{rel}: a window view shares the model name {stem} with a fact document")
            raw = inp.read_bytes(root / rel)
            sha = hashlib.sha256(raw).hexdigest()
            try:
                facts = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as e:
                raise EvidenceError(f"{rel}: not JSON ({e})") from e
            drel = f"gen/{gm}/diagram/{stem}.json"
            dg = inp.read_json(root / drel)
            inp.read_bytes(root / window_declaration(root / rel, root)[0])
            amodel = assignment["models"].get(stem)
            if amodel is not None and (not isinstance(amodel, dict) or not isinstance(amodel.get("assignment"), dict)):
                raise EvidenceError(f"{stem}: the sorts assignment's model {stem} has no assignment")
            try:
                an, a, u = _model(rel, facts, sha, dg, amodel["assignment"] if amodel else {}, sites, lex, root, inp)
            except (KeyError, TypeError, IndexError, AttributeError, DiagramError, LibError) as e:
                raise EvidenceError(f"{rel}: a construct the evidence pass cannot map ({type(e).__name__}: {e})") from e
            models[stem] = {"facts": rel, "facts_sha256": sha, "facts_version": facts.get("facts_version"),
                            "diagram": drel, "anchors": an}
            atoms += a
            unresolved += u
    for cp, cdg in components or []:   # I24: linked codec documents (rule X7); I67: Go-op documents (rule Y4)
        from . import goops as GO
        from . import linked as L
        rel = inp.rel(Path(cp))
        raw = inp.read_bytes(root / rel)
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as e:
            raise EvidenceError(f"{rel}: not JSON ({e})") from e
        layer, version = (GO, GO.GOOPS_VERSION) if GO.is_goops(doc) else (L, L.LINKED_VERSION)
        if layer is L and not L.is_linked(doc):
            raise EvidenceError(f"{rel}: not a linked codec document")
        key = doc["component"]
        if key in models:
            raise EvidenceError(f"two documents share the model name {key}")
        sha = hashlib.sha256(raw).hexdigest()
        if cdg is None:
            drel = f"gen/{gm}/diagram/{key}.json"
            cdg = inp.read_json(root / drel)
        else:
            drel = None
        for k, want in (("model", key), ("facts", rel), ("facts_sha256", sha), ("facts_version", version)):
            if cdg.get(k) != want:
                raise EvidenceError(f"{key}: the diagram's {k} is {cdg.get(k)!r}, not {want!r} (a stale diagram: "
                                    "regenerate it with `holon diagram`)")
        try:
            atoms += layer.atoms(doc, cdg, lex)
        except (KeyError, TypeError, L.LinkedError) as e:
            raise EvidenceError(f"{rel}: a construct the evidence pass cannot map ({type(e).__name__}: {e})") from e
        models[key] = {"facts": rel, "facts_sha256": sha, "facts_version": version, "diagram": drel,
                       "anchors": layer.anchors(cdg)}
    # I20: the milestone's adopted transitions documents, no diagram, anchors only; a build for no milestone (a
    # fixture's own documents) adopts nothing, else gen_milestone's default M2 would add M2's adoption to it
    for rel, raw, d in (adopted_documents(gm, root, inp) if adopted and milestone is not None else []):
        key = Path(rel).name[:-len(".json")]
        if key in models:
            raise EvidenceError(f"two documents share the model name {key}")
        try:
            an = transitions_anchors(d)
        except (KeyError, TypeError) as e:
            raise EvidenceError(f"{rel}: a construct the evidence pass cannot map ({type(e).__name__}: {e})") from e
        models[key] = {"facts": rel, "facts_sha256": hashlib.sha256(raw).hexdigest(), "facts_version": FACTS03,
                       "diagram": None, "anchors": an}
        if diagrams is None and re.fullmatch(r"M\d+", milestone or ""):   # I72: E2 over the document (rule Z4)
            atoms += transitions_atoms(key, d)
    # I86: the documents of the milestone's bundle laws that are not models yet (bundle_documents), no diagram,
    # anchors only
    for rel, raw, d in (bundle_documents(gm, root, inp) if adopted and milestone is not None else []):
        key = Path(rel).name[:-len(".json")]
        if any(x.get("facts") == rel for x in models.values()):
            continue
        if key in models:
            raise EvidenceError(f"two documents share the model name {key}")
        try:
            an = transitions_anchors(d)
        except (KeyError, TypeError) as e:
            raise EvidenceError(f"{rel}: a construct the evidence pass cannot map ({type(e).__name__}: {e})") from e
        models[key] = {"facts": rel, "facts_sha256": hashlib.sha256(raw).hexdigest(), "facts_version": FACTS03,
                       "diagram": None, "anchors": an}
    # I28: the milestone's versioned document, no diagram, anchors only (versioned_documents)
    for rel, raw, d, an in (versioned_documents(gm, root, inp) if adopted and milestone is not None else []):
        key = Path(rel).name[:-len(".json")]
        if key in models:
            raise EvidenceError(f"two documents share the model name {key}")
        models[key] = {"facts": rel, "facts_sha256": hashlib.sha256(raw).hexdigest(),
                       "facts_version": d.get("versions_version"), "diagram": None, "anchors": an}
    doc = {"document": "evidence", "evidence_version": EVIDENCE_VERSION, "milestone": milestone,
           "inputs": inp.listing(), "levels": dict(STRENGTH), "sorts_sha256": assignment.get("sorts_sha256"),
           "models": models, "atoms": _unique(atoms), "unresolved": _unique(unresolved)}
    doc["evidence_sha256"] = body_sha256(doc)
    return doc


def build_milestone(milestone: str, root: Path | str = ROOT) -> dict:
    """The evidence set `holon evidence --milestone M` writes: up to M2 over the milestone's fact documents
    (holon.diagram.fact_documents); from M3 on (I24) over the linked codec documents gen/<M>/codec/*.json and their
    committed diagrams, never a hand-written document (Q19), plus the adopted transitions documents (anchors only)."""
    from . import fact_documents
    from . import goops as GO
    from .linked import committed_codecs, linked_milestone
    root = Path(root).resolve()
    if linked_milestone(milestone):
        comps = [(p, None) for p in committed_codecs(milestone, root)]
        comps += [(p, None) for p in GO.committed(milestone, root)]   # I67: the Go-op components (rule Y4)
        if not comps:
            raise EvidenceError(f"no linked codec documents under gen/{milestone}/codec (run `holon codecs "
                                f"--milestone {milestone}`)")
        return build([], root, milestone=milestone, components=comps)
    return build(fact_documents(milestone, root), root, milestone=milestone)


def _unique(items: list[dict]) -> list[dict]:
    by: dict[str, dict] = {}
    for x in items:
        if x["id"] in by and by[x["id"]] != x:
            raise EvidenceError(f"two different entries share the id {x['id']}")
        by[x["id"]] = x
    return [by[k] for k in sorted(by)]


# ====================================================================== laws (L1-L4)
def _named(st: dict, irv: str, an: dict) -> set[str]:
    out: set[str] = set()

    def walk(t):
        if isinstance(t, dict):
            # holon-ir/0.1, and the codec terms holon-ir/0.3 adds (I24: laws over a holon-facts/0.1 document or a
            # linked codec document): a call names its CODEC edge, a domain predicate the edges it is the domain of
            f = t.get("call") if irv in (IR01, IR03) else None
            if isinstance(f, str):
                if f in an["codec"]:
                    out.add(an["codec"][f])
                out.update(an["domains"].get(f, []))
            if irv in (IR02, IR03):
                a = t.get("act")
                if isinstance(a, str) and a in an["actions"]:
                    out.add(an["actions"][a])
                # I65 (tests_m3/test_o12.py rule O4): a ghost term names its action's edge, as an act term does
                gh = t.get("ghost") if irv == IR03 and "over" in t else None
                if isinstance(gh, str) and gh in an["actions"]:
                    out.add(an["actions"][gh])
                fn = t.get("fn")
                if isinstance(fn, str):
                    if fn.startswith("is_") and fn[3:] in an["actions"]:
                        out.add(an["actions"][fn[3:]])
                    if fn == "perm":
                        out.update(an["permissionless"])
                    args = t.get("args")
                    if (fn == "no_code" and isinstance(args, list) and len(args) == 2 and isinstance(args[1], dict)
                            and "nat" in args[1]):
                        out.update(an["reasons"].get(str(args[1]["nat"]), []))
                    if fn in an["consumers"]:
                        out.add(an["consumers"][fn])
                o = t.get("obsv")
                if isinstance(o, str) and o in an["observers"]:
                    out.add(an["observers"][o])
                mg = t.get("mig")
                if isinstance(mg, str) and mg in an["migrations"]:
                    out.add(an["migrations"][mg])
                pj = t.get("proj")
                if isinstance(pj, list):
                    for c in pj:
                        if isinstance(c, str) and c in an["carriers"]:
                            out.update(an["carriers"][c]["writers"])
                            out.update(an["carriers"][c]["readers"])
                s = t.get("site")
                if irv == IR03 and isinstance(s, str):
                    out.update(an["sites"].get(s, []))
            for v in t.values():
                walk(v)
        elif isinstance(t, list):
            for v in t:
                walk(v)
    walk(st.get("assume"))
    walk(st.get("claim"))
    return out


def _version(st: dict, tag_premise: bool = False) -> int | None:
    """L4: the one value the premises fix for the record field "version" (holon-ir/0.1, and the codec terms of
    holon-ir/0.3), else None. tag_premise (holon-ir/0.3, I24 rule X8c): a premise that a byte-string decoder of the
    statement reads the one byte v ({"eq": [{"call": T, "args": [{"var": b}]}, {"some": {"bytes": "0x<v>"}}]}) fixes
    the version v of a law over a linked carrier, read as the version premise."""
    vals = set()
    for p in st.get("assume") or []:
        eq = p.get("eq") if isinstance(p, dict) else None
        if not isinstance(eq, list) or len(eq) != 2:
            continue
        for a, b in (eq, eq[::-1]):
            if (isinstance(a, dict) and set(a) == {"field", "of"} and a["field"] == "version"
                    and isinstance(a["of"], dict) and set(a["of"]) == {"var"}
                    and isinstance(b, dict) and set(b) == {"bytes"} and isinstance(b["bytes"], str)):
                try:
                    vals.add(int(b["bytes"], 16))
                except ValueError:
                    continue
            if (tag_premise and isinstance(a, dict) and set(a) == {"call", "args"} and isinstance(a["call"], str)
                    and isinstance(a["args"], list) and len(a["args"]) == 1 and isinstance(a["args"][0], dict)
                    and set(a["args"][0]) == {"var"} and isinstance(b, dict) and set(b) == {"some"}
                    and isinstance(b["some"], dict) and set(b["some"]) == {"bytes"}
                    and isinstance(b["some"]["bytes"], str) and len(b["some"]["bytes"]) == 4):
                try:
                    vals.add(int(b["some"]["bytes"], 16))
                except ValueError:
                    continue
    return next(iter(vals)) if len(vals) == 1 else None


def law_evidence(law: dict, doc: dict) -> dict:
    """Rules L1-L4: which edges the law names (and ranges over), and the atoms relating them."""
    models = doc.get("models") or {}
    model = next((m for m, mo in sorted(models.items()) if mo.get("facts") == law.get("facts")), None)
    sha = law.get("facts_sha256")
    covered = model is not None and (not sha or sha == models[model].get("facts_sha256"))
    out = {"model": model, "covered": covered, "named": [], "context": [], "version": None, "atoms": [],
           "levels": [], "max": None}
    if not covered:
        return out
    an = models[model]["anchors"]
    st = law.get("statement") or {}
    irv = law.get("ir_version")
    named = _named(st, irv, an)
    context = list(an["trans"]) if any(isinstance(b, dict) and b.get("type") in PATH_BINDERS
                                       for b in st.get("binders") or []) else []
    version = _version(st) if irv == IR01 else (_version(st, tag_premise=True) if irv == IR03 else None)
    N = named | set(context)
    rel = [a for a in doc.get("atoms") or [] if a["model"] == model and a["p"] in N and a["q"] in N
           and (a["p"] in named or a["q"] in named)
           and (version is None or "version" not in a["via"] or a["via"]["version"] == version)]
    levels = sorted({a["level"] for a in rel})
    out.update({"named": sorted(named), "context": context, "version": version,
                "atoms": sorted(a["id"] for a in rel), "levels": levels,
                "max": next((lv for lv in LEVELS if lv in levels), None)})
    return out


def evidence_triage(status, max_level) -> str:
    """BUILD_PLAN I14: only a REFUTED law is triaged; intent_question iff its strongest evidence is weak (E6),
    finding otherwise (also when nothing is computed)."""
    if status != "REFUTED":
        return "none"
    return "intent_question" if max_level == "E6" else "finding"


# ====================================================================== records
def load_set(root: Path | str, milestone: str | None) -> dict | None:
    """The committed evidence set of a milestone, or None when it is missing or unreadable."""
    try:
        doc = json.loads((Path(root) / evidence_path(milestone)).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def load_overrides(root: Path | str) -> tuple[dict | None, str | None]:
    """(config/evidence_overrides.json, None), ({}, None) when absent, or (None, why) when unreadable."""
    p = Path(root) / OVERRIDES
    if not p.exists():
        return {}, None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{OVERRIDES.as_posix()}: unreadable ({type(e).__name__}: {e})"
    if not isinstance(d, dict) or not all(isinstance(v, dict) for v in d.values()):
        return None, f"{OVERRIDES.as_posix()}: not an object of milestones to objects of laws"
    return d, None


def override_problem(entry) -> str | None:
    if not isinstance(entry, dict) or set(entry) != {"evidence_triage", "why"}:
        return "an override is exactly {\"evidence_triage\", \"why\"}"
    if entry["evidence_triage"] not in OVERRIDE_TRIAGES:
        return f"evidence_triage {entry['evidence_triage']!r} is not one of {list(OVERRIDE_TRIAGES)}"
    if not isinstance(entry["why"], str) or not entry["why"].strip():
        return "why is not a non-empty string"
    return None


def expected_fields(le: dict, status, override) -> dict:
    return {"evidence_levels": le["levels"] if le["covered"] else None,
            "evidence_triage": evidence_triage(status, le["max"] if le["covered"] else None),
            "evidence_override": override}


def record_fields(law: dict, status, root: Path | str = ROOT) -> dict:
    """The v2 record fields evidence_levels, evidence_triage, evidence_override of one law (holon.records): from
    the committed evidence set of its milestone and config/evidence_overrides.json. A law the set does not cover
    (planted mutations, toy targets), or a missing set, gives null levels and the computed triage; nothing fails
    here (GEVID reports what is wrong)."""
    doc = load_set(root, law.get("milestone"))
    le = law_evidence(law, doc) if doc is not None else {"covered": False, "levels": [], "max": None}
    ovs, _ = load_overrides(root)
    ov = ((ovs or {}).get(law.get("milestone")) or {}).get(law.get("law_id"))
    return expected_fields(le, status, ov)


# ====================================================================== GEVID
def _laws(root: Path, milestone: str, problems: list) -> dict[str, dict]:
    out = {}
    for p in sorted((root / "laws" / milestone).glob("L_*.json")):
        try:
            law = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            problems.append(f"laws/{milestone}/{p.name}: unreadable ({type(e).__name__})")
            continue
        out[law.get("law_id", p.stem)] = law
    return out


def gevid(milestone: str, root: Path | str = ROOT) -> dict:
    """Gate check GEVID (holon.gate runs it right after GREF): the committed evidence set regenerates byte for byte
    and its hashes agree; records carry the recomputed evidence fields; overrides are well formed; each law's
    metadata evidence is a subset of its computed levels. Report-only for M0 and M1 (mismatches are reported),
    enforcing from M2 on. Reads no git and runs no tool."""
    from .. import schema as S
    from . import fact_documents

    root = Path(root).resolve()
    mode = "report-only" if milestone in ("M0", "M1") else "enforcing"
    enforcing = mode == "enforcing"
    problems: list[str] = []
    rel = evidence_path(milestone).as_posix()
    gm = gen_milestone(milestone)
    doc, text = None, None
    try:
        text = (root / rel).read_text(encoding="utf-8")
        doc = json.loads(text)
        if not isinstance(doc, dict):
            raise ValueError("not an object")
    except FileNotFoundError:
        problems.append(f"{rel}: missing (run `holon evidence --milestone {gm}`)")
        doc = None
    except (OSError, ValueError) as e:
        problems.append(f"{rel}: unreadable ({type(e).__name__}: {e})")
        doc = None
    usable = doc
    if doc is not None:
        try:
            sch = json.loads((root / SCHEMA).read_text(encoding="utf-8"))
            errs = S.errors(doc, sch)
        except (OSError, ValueError) as e:
            problems.append(f"{SCHEMA.as_posix()}: unreadable ({type(e).__name__}: {e})")
            errs = []
        if errs:
            problems.append(f"{rel}: invalid against {SCHEMA.as_posix()}: {'; '.join(errs[:3])}")
            usable = None
        if doc.get("evidence_sha256") != body_sha256(doc):
            problems.append(f"{rel}: evidence_sha256 {doc.get('evidence_sha256')!r} is not the hash of its body")
        sp = Path("gen") / gm / "sorts" / "assignment.json"
        from .linked import linked_milestone
        if linked_milestone(milestone) and not (root / sp).exists():   # I24 (G4): no sorts assignment covers M3 yet
            if doc.get("sorts_sha256") is not None:
                problems.append(f"{rel}: sorts_sha256 {doc.get('sorts_sha256')!r}, but {sp.as_posix()} does not exist "
                                "(null expected)")
        else:
            try:
                want = json.loads((root / sp).read_text(encoding="utf-8")).get("sorts_sha256")
                if doc.get("sorts_sha256") != want:
                    problems.append(f"{rel}: sorts_sha256 {doc.get('sorts_sha256')!r} differs from "
                                    f"{sp.as_posix()}'s {want!r}")
            except (OSError, ValueError, AttributeError) as e:
                problems.append(f"{sp.as_posix()}: unreadable ({type(e).__name__}: {e}), so sorts_sha256 is unchecked")
        try:
            fresh = render(build_milestone(gm, root))
            if fresh != text:
                problems.append(f"{rel}: a fresh build from the committed inputs does not reproduce it byte for byte "
                                f"(rerun `holon evidence --milestone {gm}`, or an input drifted)")
        except (EvidenceError, DiagramError, OSError) as e:
            problems.append(f"{rel}: a fresh build from the committed inputs fails: {e}")
    edoc = usable if usable is not None else {"models": {}, "atoms": []}
    if enforcing:
        rp = Path("laws") / milestone / "REGISTRY.json"
        try:
            reg = json.loads((root / rp).read_text(encoding="utf-8"))
            if not isinstance(reg, dict) or "evidence_sha256" not in reg:
                problems.append(f"{rp.as_posix()}: lacks evidence_sha256")
            elif reg["evidence_sha256"] != (doc or {}).get("evidence_sha256"):
                problems.append(f"{rp.as_posix()}: evidence_sha256 {reg['evidence_sha256']!r} is not {rel}'s "
                                f"{(doc or {}).get('evidence_sha256')!r}")
        except (OSError, ValueError) as e:
            problems.append(f"{rp.as_posix()}: unreadable ({type(e).__name__}), so evidence_sha256 is unchecked")
    laws = _laws(root, milestone, problems)
    ovs, why = load_overrides(root)
    if why:
        problems.append(why)
    mine = (ovs or {}).get(milestone) or {}
    records = {}
    for lid in laws:
        p = root / "results" / milestone / f"{lid}.json"
        if p.exists():
            try:
                records[lid] = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError) as e:
                problems.append(f"results/{milestone}/{lid}.json: unreadable ({type(e).__name__})")
    overrides = []
    for lid in sorted(mine):
        entry = mine[lid]
        bad = override_problem(entry)
        if bad:
            problems.append(f"{OVERRIDES.as_posix()}: {milestone}.{lid}: malformed override ({bad})")
        if lid not in laws:
            problems.append(f"{OVERRIDES.as_posix()}: {milestone}.{lid}: names no law of {milestone}")
        elif (records.get(lid) or {}).get("status") != "REFUTED":
            problems.append(f"{OVERRIDES.as_posix()}: {milestone}.{lid}: an override on a law whose record is not "
                            "REFUTED")
        if not bad:
            overrides.append({"law": lid, "evidence_triage": entry["evidence_triage"], "why": entry["why"]})
    rows, mismatches, uncovered, divergences = {}, [], [], []
    for lid in sorted(laws):
        law = laws[lid]
        le = law_evidence(law, edoc)
        meta = sorted(set(law.get("evidence") or []))
        missing = sorted(set(meta) - set(le["levels"]))
        rec = records.get(lid)
        status = rec.get("status") if rec else None
        ov = mine.get(lid)
        et = evidence_triage(status, le["max"])
        eff = ov["evidence_triage"] if ov is not None and not override_problem(ov) else et
        v1 = rec.get("triage") if rec else None
        rows[lid] = {"metadata": meta, "computed": le["levels"], "missing": missing, "max": le["max"],
                     "covered": le["covered"], "evidence_triage": et, "override": ov, "effective": eff, "v1_triage": v1}
        if missing:
            mismatches.append({"law": lid, "missing": missing})
        if not le["covered"]:
            uncovered.append(lid)
            if enforcing:
                problems.append(f"{lid}: not covered by the evidence set {rel} (its facts or facts_sha256 match "
                                "no model)")
        if rec is not None:
            want = expected_fields(le, status, ov)
            for k in RECORD_FIELDS:
                if k not in rec or rec[k] != want[k]:
                    problems.append(f"{lid}: record field {k} is {rec.get(k, '<absent>')!r}, recomputed {want[k]!r}")
            if eff != v1:
                divergences.append({"law": lid, "v1_triage": v1, "evidence_triage": et, "effective": eff})
    passed = not problems and (not enforcing or not mismatches)
    head = (f"{mode}: {len(laws)} laws against {rel} (evidence_sha256 {(doc or {}).get('evidence_sha256')}); "
            f"{len(mismatches)} whose metadata evidence is not computed"
            + (f" ({', '.join(m['law'] for m in mismatches)})" if mismatches else "")
            + f"; {len(divergences)} divergences from the v1 triage; {len(overrides)} overrides; "
            + f"{len(uncovered)} uncovered")
    detail = head if not problems else head + "; problems: " + "; ".join(problems)
    return {"passed": passed, "detail": detail, "mode": mode, "milestone": milestone,
            "evidence_sha256": (doc or {}).get("evidence_sha256"), "laws": rows, "mismatches": mismatches,
            "uncovered": uncovered, "divergences": divergences, "overrides": overrides, "problems": problems}


# ====================================================================== CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon evidence")
    ap.add_argument("--milestone", default="M2")
    ap.add_argument("--root", help="repository root holding the inputs (default: this checkout)")
    ap.add_argument("--out", help="output file (default: <root>/gen/<milestone>/evidence.json)")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        doc = build_milestone(a.milestone, root)
        text = render(doc)
    except (EvidenceError, DiagramError) as e:
        print(f"holon evidence: {e}", file=sys.stderr)
        return 1
    out = Path(a.out) if a.out else root / evidence_path(a.milestone)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    by = {lv: sum(1 for x in doc["atoms"] if x["level"] == lv) for lv in LEVELS}
    print(f"holon evidence: {len(doc['atoms'])} atoms ({', '.join(f'{k} {v}' for k, v in by.items())}), "
          f"{len(doc['unresolved'])} unresolved -> {out}")
    return 0
