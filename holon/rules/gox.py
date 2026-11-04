"""The Go part of rule PAR (I93 = I38d; the contract is the docstring of tests_m3/test_go_laws.py, rules G3-G7): the
producers of PAR's Go sub-forms, registered under holon-rules/1.15 (holon.rules.CATALOGS) and run by derive's gox part
(holon.rules._gox_part), never by its typed part.

Basis (holon.gox.basis over the milestone's gox sidecar spec/<M>/lib/go_laws.json, the Go document it names, its
compression sidecar and the Solidity documents of its recompute roles):

  go_round_trip   D(E(inputs)) is the non-error result v (P1 over an unversioned Go codec pair; G4)
  go_branch       a size test that short-cuts a compressing path agrees with that path (PAR-branch; G5)
  go_recompute    every Go data hash is some on-chain one, through the preimage (cross-language; G6)

Statement (holon-ir/0.3, facts: the Go document): the claim {"gox": <gox id>, "on": [binders]} == true, the gox id
"<subform>:<words>". The law's generated model (holon.gox.model) gives the term its meaning. Its ref "gox:<ID>" is the
sha256 of the canonical {template, template_version, subform, basis}, recomputed from the sidecar and the documents
(gox_ref). A basis element with a reason has no law (gen/<M>/gox/basis.json lists it).

Nothing here names a target: every function, field and constant comes from the sidecars and the documents.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

RULE = "PAR"
SUBFORMS = ("go_round_trip", "go_branch", "go_recompute")
TEMPLATE_VERSION = 1


class GoxRuleError(ValueError):
    pass


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def has_sidecar(root, milestone: str) -> bool:
    from ..gox.basis import has_sidecar as hs
    return hs(root, milestone)


def elements(root, milestone: str, inputs=None) -> list:
    from ..gox import basis as B
    try:
        return B.elements(root, milestone, inputs)
    except (B.GoxError, KeyError, TypeError, IndexError) as e:
        raise GoxRuleError(f"{RULE}/go: {e}") from e


def gox_spec(subform: str, basis: dict) -> dict:
    return {"template": f"holon.rules.gox/{subform}", "template_version": TEMPLATE_VERSION, "subform": subform,
            "basis": basis}


def gox_hash(subform: str, basis: dict) -> str:
    return sha256_text(canon(gox_spec(subform, basis)))


def gox_ref(gid: str, law: dict, root=None) -> str:
    """The ref "gox:<ID>" recomputed from the sidecar and the documents; a basis that no longer gives the id hashes as
    absent."""
    from pathlib import Path as _P
    root = _P(root) if root else _P(__file__).resolve().parents[2]
    try:
        for e in elements(root, str(law.get("milestone"))):
            if e["gox_id"] == gid and not e.get("reason"):
                if e["facts"] != law.get("facts"):
                    break
                return gox_hash(e["subform"], e["basis"])
    except (OSError, ValueError, KeyError, TypeError) as ex:
        return sha256_text(canon({"absent": gid, "error": type(ex).__name__}))
    return sha256_text(canon({"absent": gid}))


def binders(e: dict) -> list:
    """The law's binders (names and IR types): the encoder's input values as byte strings (go_round_trip), the Go ints
    and the compressor's output length as Nat (go_branch), the Go state as lists of bytes and counts (go_recompute)."""
    from ..gox import model as G
    return G.binders(e)


def _notes(e: dict) -> str:
    b = e["basis"]
    if e["subform"] == "go_round_trip":
        return (f"Go codec round trip: {b['decoder']} recovers what {b['encoder']} (entry {b['entry']}, length "
                f"{b['length']}) wrote at its reads, for all of the encoder's inputs (P1 over an unversioned Go codec)")
    if e["subform"] == "go_branch":
        hz = (f"; premise HypZ_len at the argument ({b['hypz_len']['from']})" if b.get("hypz_len") else "")
        return (f"size short-cut of {b['function']}: where path {b['p']}'s test holds, path {b['q']}'s value at "
                f"position {b['position']} (a size test of {b['call']}'s output) equals path {b['p']}'s{hz}")
    s = b["solidity"]
    return (f"cross-language recompute ({b['role']}): every hash {b['function']} returns is some value "
            f"{s['action']} stores at {s['store']} ({s['document']}), through the preimage")


def law_ir(e: dict, milestone: str, catalog_version: str) -> dict:
    bs = binders(e)
    return {"ir_version": "holon-ir/0.3", "law_id": e["law_id"], "milestone": milestone, "rule": RULE,
            "subform": e["subform"], "rule_catalog_version": catalog_version, "facts": e["facts"],
            "facts_sha256": e["facts_sha256"], "notes": f"{_notes(e)}; gox {e['gox_id']}",
            "statement": {"binders": [{"q": "forall", "name": n, "type": t} for n, t in bs], "assume": [],
                          "claim": {"eq": [{"gox": e["gox_id"], "on": [{"var": n} for n, _ in bs]}, {"bool": True}]},
                          "scope": {"kind": "unbounded"}}}


def entry_of(e: dict) -> dict:
    return {"law_id": e["law_id"], "rule": RULE, "subform": e["subform"], "facts": e["facts"], "basis": e["basis"]}


def is_gox_law(law: dict) -> bool:
    if law.get("ir_version") != "holon-ir/0.3" or law.get("rule") != RULE or law.get("subform") not in SUBFORMS:
        return False
    c = (law.get("statement") or {}).get("claim") or {}
    return any(isinstance(x, dict) and "gox" in x for x in c.get("eq") or [])


def basis_doc(root, milestone: str) -> dict:
    """gen/<M>/gox/basis.json: every basis element, with its law id or the reason it has none (G3)."""
    els = elements(root, milestone)
    return {"gox_version": "holon-gox/0.1", "milestone": milestone,
            "elements": [{"law_id": None if e.get("reason") else e["law_id"], "candidate": e["law_id"],
                          "subform": e["subform"], "gox_id": e["gox_id"], "reason": e.get("reason"),
                          "function": e.get("function") or e["basis"].get("function") or e["basis"].get("encoder"),
                          "facts": e["facts"], "facts_sha256": e["facts_sha256"]} for e in els]}


class _Producer:
    part = "gox"   # run by derive's gox part (holon.rules._gox_part), never by its typed part

    def __init__(self, subform: str):
        self.subform = subform
        self.__name__ = f"holon.rules.gox.{subform}"

    def produce(self, ctx) -> list:
        root = Path(ctx.root)
        if not has_sidecar(root, ctx.milestone):
            return []
        els = elements(root, ctx.milestone, getattr(ctx, "inputs", None))
        return [(law_ir(e, ctx.milestone, ctx.rule_catalog_version), entry_of(e)) for e in els
                if e["subform"] == self.subform and not e.get("reason")]


PRODUCERS = {sub: _Producer(sub) for sub in SUBFORMS}
