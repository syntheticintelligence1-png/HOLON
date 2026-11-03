"""Rule SYM over the members of a bundle (I92 = I34b; the contract is the docstring of tests_m3/test_sym_bundle.py, rules
K1-K12): the producers of SYM's member sub-forms, registered under holon-rules/1.14 (holon.rules.CATALOGS) and run by
derive's symb part (holon.rules._symb_part), never by its typed part.

Basis (holon.symb.basis over the milestone's SYM-bundle sidecar spec/<M>/lib/sym_bundle.json, its members' documents
and their nominal sorts, holon.symb.sorts recomputed from the documents):

  member_tau        a member action touching a Time word: law id <prefix>tau_<contract>_<action>; binders s: Reach,
                    x: Act, d: Nat. A view whose return term is Time-sorted has its return word translated (K5).
  member_sentinel   a write of a sentinel register whose value is not the literal constant:
                    <prefix>sentinel_<contract>_<path, "." as "_">_<action>_<first line of the site's span>; binders
                    s: Reach, x: Act. A site whose value reads a call answer is stated over the members' link (K3).
  sentinel_inv      a view whose return is a conditional on a conjunction holding R != c next to another conjunct G:
                    <prefix>sentinel_inv_<contract>_<path, "." as "_">_<view>; binder s: Reach, the member's versioned
                    reach (the sidecar's legacy version, its upgrade eta, the head), every reach step's block_timestamp
                    at least 1.

<prefix> is holon.rules.sym's LAW_PREFIX. Statement (holon-ir/0.3, facts: the member's document): the claim
{"symb": <symb id>, "on": [binders]} == true, the symb id "<member>:<subform>:<basis words joined by ':'>". The
member's generated section (holon.symb.sections) gives the term its meaning. Its ref "symb:<ID>" is the sha256 of the
canonical {template, template_version, subform, basis}, recomputed from the sidecar, the documents and the sorts
(symb_ref).

Nothing here names a target: every member, contract, action, register and constant comes from the sidecar and the
documents.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .sym import LAW_PREFIX, RULE

ROOT = Path(__file__).resolve().parents[2]
SUBFORMS = ("member_tau", "member_sentinel", "sentinel_inv")
SIDECAR = "spec/{}/lib/sym_bundle.json"
TEMPLATE_VERSION = 1
BINDERS = {"member_tau": [("s", "Reach"), ("x", "Act"), ("d", "Nat")],
           "member_sentinel": [("s", "Reach"), ("x", "Act")],
           "sentinel_inv": [("s", "Reach")]}
WORD = {"member_tau": "tau", "member_sentinel": "sentinel", "sentinel_inv": "sentinel_inv"}


class SymbRuleError(ValueError):
    pass


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def has_sidecar(root, milestone: str) -> bool:
    return (Path(root) / SIDECAR.format(milestone)).is_file()


def _line(src) -> str:
    m = re.search(r":(\d+)(?:-\d+)?$", src or "")
    return m.group(1) if m else "x"


def _reads_answer(t) -> bool:
    """The term reads a call's answer (a link value, K3)."""
    if isinstance(t, list):
        if t and t[0] in ("call", "ret", "answer", "callret"):
            return True
        return any(_reads_answer(x) for x in t)
    if isinstance(t, dict):
        return any(_reads_answer(x) for x in t.values())
    return False


def elements(root, milestone: str, inputs=None) -> list:
    """The basis elements, sorted by law id: {law_id, subform, symb_id, member, facts, facts_sha256, basis}."""
    from ..symb import context
    from ..symb import basis as B
    from ..symb.sorts import Solver, members_sorts
    root = Path(root)
    ctx = context(root, milestone)
    if inputs is not None:
        inputs.read(root / ctx.side_rel)
    sorts = members_sorts(ctx)
    laws = B.member_laws(ctx, sorts)
    lg = ctx.side.get("legacy") or {}
    out = []
    for member in sorted(laws):
        v = laws[member]
        rel = ctx.side["members"][member]["document"]
        data = (root / rel).read_bytes()
        if inputs is not None:
            inputs.read(root / rel)
        doc = json.loads(data)
        so = sorts["members"][member]
        solver = Solver({member: doc}, {})
        solver.time[member] = set(so["time"])
        solver.idx[member] = set(so["idx"])
        acts = {a["name"]: a for a in doc["actions"]}
        common = {"member": member, "contract": v["contract"], "sorts": so}

        def add(sub, words, basis):
            lid = LAW_PREFIX + "_".join([WORD[sub], v["contract"], *[str(w) for w in words]])
            out.append({"law_id": lid, "subform": sub, "symb_id": ":".join([member, sub, *[str(w) for w in words]]),
                        "member": member, "facts": rel, "facts_sha256": sha256_bytes(data),
                        "basis": {"kind": f"sym_{sub}", **common, **basis}})
        for act in v["tau"]:
            a = acts[act]
            view = a.get("mutability") in ("view", "pure") and a.get("returns") is not None
            add("member_tau", [act], {"action": act,
                                      "time_return": bool(view and solver.sort(member, a.get("returns")) == "time")})
        for path, act, src, val, const in v["sentinels"]:
            basis = {"register": path, "constant": const, "action": act, "src": src, "value": val}
            if _reads_answer(val):
                basis["link"] = {"calls": list((ctx.side.get("link") or {}).get("calls_of", {}).get(member)
                                               or (ctx.side.get("link") or {}).get(f"{member}_calls") or []),
                                 "callees": _callees(ctx, member, root, inputs)}
            add("member_sentinel", [path.replace(".", "_"), act, _line(src)], basis)
        for path, view, const in v["readers"]:
            basis = {"register": path, "constant": const, "view": view}
            if lg.get("member") == member:
                basis["versioned"] = _versioned(ctx, root, inputs)
            add("sentinel_inv", [path.replace(".", "_"), view], basis)
    ids = [e["law_id"] for e in out]
    if len(ids) != len(set(ids)):
        raise SymbRuleError(f"two basis elements map to one law id: {sorted({i for i in ids if ids.count(i) > 1})}")
    return sorted(out, key=lambda e: e["law_id"])


def _callees(ctx, member: str, root: Path, inputs) -> dict:
    """{callee member: its document's sha256}: the sidecar's other members (the link's callees, K3)."""
    out = {}
    for m, spec in sorted(ctx.side["members"].items()):
        if m == member:
            continue
        p = root / spec["document"]
        if inputs is not None:
            inputs.read(p)
        out[m] = sha256_bytes(p.read_bytes())
    return out


def _versioned(ctx, root: Path, inputs) -> dict:
    """The versioned member's inputs (K3): the legacy version, its document and the upgrade's eta."""
    lg = ctx.side["legacy"]
    doc = root / ctx.out("legacy", f"{lg['member']}.json")
    eta = root / ctx.out(f"eta_{lg.get('eta', 'enq')}.json")
    for p in (doc, eta):
        if not p.is_file():
            raise SymbRuleError(f"{p.relative_to(root)} is missing (holon symb legacy writes it)")
        if inputs is not None:
            inputs.read(p)
    return {"tag": lg["tag"], "commit": lg["commit"], "document": doc.relative_to(root).as_posix(),
            "document_sha256": sha256_bytes(doc.read_bytes()), "eta": eta.relative_to(root).as_posix(),
            "eta_sha256": sha256_bytes(eta.read_bytes())}


def symb_spec(subform: str, basis: dict) -> dict:
    return {"template": f"holon.rules.symb/{subform}", "template_version": TEMPLATE_VERSION, "subform": subform,
            "basis": basis}


def symb_hash(subform: str, basis: dict) -> str:
    return sha256_text(canon(symb_spec(subform, basis)))


def symb_ref(sid: str, law: dict, root=None) -> str:
    """The ref "symb:<ID>" recomputed from the sidecar, the documents and the sorts; a basis that no longer gives the
    id hashes as absent."""
    root = Path(root or ROOT)
    try:
        for e in elements(root, str(law.get("milestone"))):
            if e["symb_id"] == sid:
                if e["facts"] != law.get("facts"):
                    break
                return symb_hash(e["subform"], e["basis"])
    except (OSError, ValueError, KeyError, TypeError) as ex:
        return sha256_text(canon({"absent": sid, "error": type(ex).__name__}))
    return sha256_text(canon({"absent": sid}))


def _notes(e: dict) -> str:
    b = e["basis"]
    if e["subform"] == "member_tau":
        ret = ("; the view's Time-sorted return word is translated in the first run's observation (K5)"
               if b.get("time_return") else "")
        return (f"time translation over the member {b['member']}: for every d, from a reachable s, an act x of "
                f"{b['action']} run on τ_d s and τ_d x gives τ_d of its run on s and x (storage, outcome, Time words "
                f"of the logs; a key the store does not hold is not translated){ret}")
    if e["subform"] == "member_sentinel":
        where = ("over the members' link: the value reads a callee's answer, the callee's own state (K3)"
                 if b.get("link") else "with block.timestamp >= 1 (a nonzero word) where the site reads it")
        return (f"sentinel {b['register']} vs {b['constant']} on the member {b['member']}: from a reachable s, a "
                f"successful act x of {b['action']} ({where}) writes a value other than {b['constant']} at {b['src']}")
    vs = b.get("versioned") or {}
    return (f"sentinel invariant {b['register']} vs {b['constant']} read by the view {b['view']} of the member "
            f"{b['member']}: on every state of the versioned member (the legacy version {vs.get('tag')}, its upgrade "
            f"and the head; every reach step's block_timestamp >= 1, a premise: no block has timestamp 0), the view's "
            f"other conjunct implies {b['register']} != {b['constant']}")


def law_ir(e: dict, milestone: str, catalog_version: str) -> dict:
    binders = [{"q": "forall", "name": n, "type": t} for n, t in BINDERS[e["subform"]]]
    return {"ir_version": "holon-ir/0.3", "law_id": e["law_id"], "milestone": milestone, "rule": RULE,
            "subform": e["subform"], "rule_catalog_version": catalog_version, "facts": e["facts"],
            "facts_sha256": e["facts_sha256"], "notes": f"{_notes(e)}; symb {e['symb_id']}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"symb": e["symb_id"],
                                            "on": [{"var": n} for n, _ in BINDERS[e["subform"]]]},
                                           {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(e: dict) -> dict:
    """The DERIVATION entry; its member names the law's bundle member, as I86's bundle-law entries do (the evidence set
    covers the documents of the entries with a member: holon.diagram.evidence.bundle_documents)."""
    return {"law_id": e["law_id"], "rule": RULE, "subform": e["subform"], "facts": e["facts"], "member": e["member"],
            "basis": e["basis"]}


def is_symb_law(law: dict) -> bool:
    if law.get("ir_version") != "holon-ir/0.3" or law.get("rule") != RULE or law.get("subform") not in SUBFORMS:
        return False
    c = (law.get("statement") or {}).get("claim") or {}
    return any(isinstance(x, dict) and "symb" in x for x in c.get("eq") or [])


class _Producer:
    part = "symb"   # run by derive's symb part (holon.rules._symb_part), never by its typed part

    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.symb.{subform}"

    def produce(self, ctx) -> list:
        root = Path(ctx.root)
        if not has_sidecar(root, ctx.milestone):
            return []
        try:
            els = elements(root, ctx.milestone, getattr(ctx, "inputs", None))
        except (OSError, KeyError) as e:
            raise SymbRuleError(f"{RULE}/{self.subform}: {e}") from e
        return [(law_ir(e, ctx.milestone, ctx.rule_catalog_version), entry_of(e)) for e in els
                if e["subform"] == self.subform]


PRODUCERS = {sub: _Producer(sub) for sub in SUBFORMS}
