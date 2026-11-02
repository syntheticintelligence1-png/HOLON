"""Rule SYM: equivariance laws per (family, action), ω reorder laws and sentinel laws (BUILD_PLAN I34; whitepaper §5.4,
§8.3, §8.4; the contract is rules J1-J8 of the docstring of tests_m3/test_sym.py).

Basis (holon.sym's analysis of a typed milestone's facts and sort assignment):

  tau        an action whose guards, writes, returns or checks read block.timestamp or a storage family holding a Time
             word: law id <prefix>tau_<contract>_<action>; binders s: Reach, x: Act, d: Nat.
  pi         an action and a set role it is gated by (the role's predicate), writes (the role's register) or reads (a
             member or scalar read of the role's register): <prefix>pi_<contract>_<action>_<role>; binders s: Reach,
             x: Act, a: Word, b: Word.
  omega      an eligible pair (a, b), a < b: <prefix>omega_<contract>_<a>_<b>; binders s: Reach, x: Act, y: Act.
  sentinel   a Time sentinel register and one of its non-literal write sites:
             <prefix>sentinel_<contract>_<register, "." as "_">_<action>_<first line of the site's span>; binders s: Reach,
             x: Act.

<prefix> is LAW_PREFIX, "L_sym_": a law id is the prefix, the sub-form and the basis words joined by "_" (law_id()).

Statement (holon-ir/0.3, facts: the typed document): the claim {"sym": <sym id>, "on": [binders]} == true, the sym id
"<model>:<subform>:<basis words joined by ':'>". The generated section (holon.gen.symsec) gives the term its meaning:
the generator applied to the state and the act (τ_d, π_{a,b}), the law's premises (the act's action; fits64 for tau;
two distinct members of the role for pi; both orders executing for omega; the act's success and block.timestamp >= 1
for a sentinel site that reads it) as the antecedent of an implication, and a hit predicate (the premises alone) for
G11V's inhabitant, as UNDO's undo term does. Its ref "sym:<ID>" is the sha256 of the canonical {template,
template_version, subform, basis}, recomputed from the law's facts and the milestone's sort assignment.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .. import sym as S

ROOT = Path(__file__).resolve().parents[2]
RULE = "SYM"
SUBFORMS = ("tau", "pi", "omega", "sentinel")
LAW_PREFIX = "L_sym_"
TEMPLATE_VERSION = 1


class SymRuleError(ValueError):
    pass


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def model_of(doc_rel: str) -> str:
    name = Path(doc_rel).name
    return name[:-len(".json")] if name.endswith(".json") else Path(doc_rel).stem


def _contract(facts: dict) -> str:
    c = facts.get("contract")
    return c.get("name") if isinstance(c, dict) else str(c)


def _touches_time(facts: dict, a: dict, assignment: dict) -> bool:
    tw = S.time_words(assignment, facts)
    if "env:block.timestamp" in tw and ["env", "block.timestamp"] in list(S._walk([a.get(k) for k in
                                                                                   ("guards", "writes", "returns",
                                                                                    "checks")])):
        return True
    fams = {w[len("storage:"):].split(".", 1)[0] for w in tw if w.startswith("storage:")}
    return bool((S._reads(a) | S._writes(a)) & fams)


def _role_touched(facts: dict, a: dict, role: str) -> bool:
    """The action is gated by the role's predicate, writes the role's register, or reads it."""
    p = a.get("principal")
    if isinstance(p, dict) and p.get("modifier") and S._families_in(p.get("predicate")):
        mod = p["modifier"][4:] if p["modifier"].startswith("only") else p["modifier"]
        if mod[:1].lower() + mod[1:] == role:
            return True
    for w in a.get("writes") or []:
        v = w.get("value")
        if w.get("family") == role and not (isinstance(v, list) and v[:1] == ["struct"]):
            return True
        if isinstance(v, list) and v[:1] == ["struct"] and any(name == role for name, _ in v[2]):
            return True
    for x in S._walk([a.get(k) for k in ("guards", "writes", "returns", "checks", "calls")]):
        if isinstance(x, list) and ((len(x) == 3 and x[0] == "member" and x[2] == role)
                                    or (len(x) == 2 and x[0] == "storage" and x[1] == role)):
            return True
    return False


def _line(src) -> str:
    m = re.search(r":(\d+)(?:-\d+)?$", src or "")
    return m.group(1) if m else "x"


def law_id(sub: str, *words) -> str:
    """The law id of a basis element: LAW_PREFIX, the sub-form and the words, joined by "_"."""
    return LAW_PREFIX + "_".join([sub, *[str(w) for w in words]])


def elements(facts: dict, assignment: dict, doc_rel: str) -> list:
    """The basis elements, sorted by law id: {law_id, subform, sym_id, basis}."""
    model, contract = model_of(doc_rel), _contract(facts)
    fam = {f["family"]: f for f in S.families(facts, assignment)}
    out = []

    def add(lid, sub, words, basis):
        out.append({"law_id": lid, "subform": sub, "sym_id": ":".join([model, sub, *words]),
                    "basis": {"kind": f"sym_{sub}", "model": model, "contract": contract, **basis}})
    acts = facts.get("actions") or []
    if fam["tau"]["status"] == "admitted":
        for a in acts:
            if _touches_time(facts, a, assignment):
                add(law_id("tau", contract, a["name"]), "tau", [a["name"]],
                    {"action": a["name"], "time_words": fam["tau"]["time_words"]})
    if fam["pi"]["status"] == "admitted":
        for role in fam["pi"]["roles"]:
            for a in acts:
                if _role_touched(facts, a, role):
                    add(law_id("pi", contract, a["name"], role), "pi", [a["name"], role],
                        {"action": a["name"], "role": role})
    if fam["omega"]["status"] == "admitted":
        for x, y in fam["omega"]["pairs"]:
            add(law_id("omega", contract, x, y), "omega", [x, y], {"a": x, "b": y})
    for sn in S.sentinels(facts, assignment):
        for site in sn["sites"]:
            reg = sn["register"]
            add(law_id("sentinel", contract, reg.replace(".", "_"), site["action"], _line(site["src"])), "sentinel",
                [reg, site["action"], _line(site["src"])],
                {"register": reg, "constant": sn["constant"], "action": site["action"], "src": site["src"],
                 "compares": sn["compares"]})
    ids = [e["law_id"] for e in out]
    if len(ids) != len(set(ids)):
        dup = sorted({i for i in ids if ids.count(i) > 1})
        raise SymRuleError(f"two basis elements map to one law id: {dup}")
    return sorted(out, key=lambda e: e["law_id"])


def sym_spec(subform: str, basis: dict) -> dict:
    return {"template": f"holon.rules.sym/{subform}", "template_version": TEMPLATE_VERSION, "subform": subform,
            "basis": basis}


def sym_hash(subform: str, basis: dict) -> str:
    return sha256_text(canon(sym_spec(subform, basis)))


def sym_ref(sid: str, law: dict, root=None) -> str:
    """The ref "sym:<ID>" recomputed from the law's facts and the milestone's assignment (G2 needs no derive output); a
    basis that no longer gives the id hashes as absent."""
    root = Path(root or ROOT)
    try:
        rel, facts, assignment = S.typed_inputs(root, str(law.get("milestone")))
        if rel != law.get("facts"):
            raise SymRuleError(f"the law's facts {law.get('facts')} are not the milestone's typed document {rel}")
        for e in elements(facts, assignment, rel):
            if e["sym_id"] == sid:
                return sym_hash(e["subform"], e["basis"])
    except (OSError, ValueError, KeyError, TypeError) as e:
        return sha256_text(canon({"absent": sid, "error": type(e).__name__}))
    return sha256_text(canon({"absent": sid}))


BINDERS = {"tau": [("s", "Reach"), ("x", "Act"), ("d", "Nat")],
           "pi": [("s", "Reach"), ("x", "Act"), ("a", "Word"), ("b", "Word")],
           "omega": [("s", "Reach"), ("x", "Act"), ("y", "Act")],
           "sentinel": [("s", "Reach"), ("x", "Act")]}


def _notes(e: dict) -> str:
    b = e["basis"]
    if e["subform"] == "tau":
        return (f"time translation: for every d, from a reachable s, an act x of {b['action']} run on τ_d s and τ_d x "
                "gives τ_d of its run on s and x (storage, outcome, Time words of the logs), every translated Time word "
                "below 2^64 (whitepaper §5.4, §8.4)")
    if e["subform"] == "pi":
        return (f"principal permutation within the role {b['role']}: for two distinct members a, b of the role in a "
                f"reachable s, an act x of {b['action']} run on π s and π x gives π of its run on s and x")
    if e["subform"] == "omega":
        return (f"reordering: from a reachable s where both orders of an act x of {b['a']} and an act y of {b['b']} "
                "execute, the two orders agree on every sink-reaching key")
    return (f"sentinel {b['register']} vs {b['constant']}: from a reachable s, a successful act x of {b['action']} (with "
            f"block.timestamp >= 1 where the site reads it) writes a value other than {b['constant']} at {b['src']}")


def law_ir(e: dict, milestone: str, doc_rel: str, doc_sha: str, catalog_version: str) -> dict:
    binders = [{"q": "forall", "name": n, "type": t} for n, t in BINDERS[e["subform"]]]
    return {"ir_version": "holon-ir/0.3", "law_id": e["law_id"], "milestone": milestone, "rule": RULE,
            "subform": e["subform"], "rule_catalog_version": catalog_version, "facts": doc_rel,
            "facts_sha256": doc_sha, "notes": f"{_notes(e)}; sym {e['sym_id']}",
            "statement": {"binders": binders, "assume": [],
                          "claim": {"eq": [{"sym": e["sym_id"], "on": [{"var": n} for n, _ in BINDERS[e["subform"]]]},
                                           {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(e: dict, doc_rel: str) -> dict:
    return {"law_id": e["law_id"], "rule": RULE, "subform": e["subform"], "facts": doc_rel, "basis": e["basis"]}


class _Producer:
    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.sym.{subform}"

    def produce(self, ctx) -> list:
        root = Path(ctx.root)
        try:
            rel, facts, assignment = S.typed_inputs(root, ctx.milestone)
        except (OSError, S.SymError) as e:
            raise SymRuleError(f"{RULE}: {e}") from e
        inputs = getattr(ctx, "inputs", None)
        if inputs is not None:
            inputs.read(root / "gen" / ctx.milestone / "sorts" / "assignment.json")
        doc = next((d for d in getattr(ctx, "typed_documents", []) or [] if d.rel == rel), None)
        if doc is None:
            raise SymRuleError(f"{RULE}: the assignment's document {rel} is not a typed document of the derivation")
        out = []
        for e in elements(facts, assignment, rel):
            if e["subform"] == self.subform:
                out.append((law_ir(e, ctx.milestone, rel, doc.sha256, ctx.rule_catalog_version), entry_of(e, rel)))
        return out


PRODUCERS = {sub: _Producer(sub) for sub in SUBFORMS}
