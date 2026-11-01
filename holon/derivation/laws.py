"""The plan-stated product laws and their verdicts (BUILD_PLAN row I88 = I39b; the contract is the docstring of
tests_m3/test_derivation_laws.py, rules S1-S4, L1-L5 and D1-D3): `holon derivation laws`.

  python -m holon derivation laws [--check] [--laws-sidecar PATH] [--root DIR]

No rule of the catalog discovers a product obligation, so the law set's statements are frozen in a sidecar (default
spec/M3/lib/derivation_laws.json) and this module only generates them, as holon.contracts generates an intended
contract's L_weak: each law file is the sidecar's statement with refs inserted (L3) and the law's metadata (L2); the
registry lists each law's statement hash, holon.gen.refs.law_hash's, the hash `holon run` gives a 0.3 law (L4). The law
set lives in its own directory (the sidecar's law_set.laws), out of every top-level glob of laws/<M> (L5).

Every name of the target (functions, types, fields, actions) comes from the sidecar and the documents it names; this
module names none. It is imported by no generator closure.

The verdict interface (D1-D3), for the key that builds the consumer's Bend model:

  verdict_of(law_id, model=None, root=ROOT) -> {"status", "attempt", ...}
      one law of the set by its id: its committed law file and its committed evidence (the outputs of
      `holon derivation decide`), handed to verdict;
  verdict(law, evidence, model=None) -> {"status", "attempt", ...}
      what `holon derivation decide` calls for every law, with evidence(...) built from its own run.

  Without a model the status is UNKNOWN: AGENTS rules 5 and 6 leave a law undecided until Bend accepts its proof or a
  counter-law, and the consumer has no Bend model. A model is any object with
      decide(law: dict, evidence: dict) -> {"status": "PROVED" | "REFUTED" | "UNKNOWN", "attempt": dict, ...}
  where evidence is evidence(...)'s dict: the law's id, its witness candidate (the search space's entry, or None),
  the observation {lhs, rhs}, the replay report's entry, the number of candidates whose premises hold and the number
  of candidates. The model returns the status the checker gave its LAWS.bend / PROOF.bend pair; its attempt replaces
  the Bend attempt of the record (the evaluator's attempt stays), and for a PROVED or REFUTED status any other key it
  returns replaces that field of the record (`holon derivation decide --model MODULE` imports
  MODULE.consumer_model(root) and re-makes the records).
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path

from . import ROOT, DerivationError, Refused, load, sha256_file

LAWS_SIDECAR = "spec/M3/lib/derivation_laws.json"
LAWS_VERSION = "holon-derivation-laws/0.1"
REGISTRY_VERSION = "holon-derivation-laws-registry/0.1"
PRODUCT_TEMPLATE = "holon.derivation.laws/product"
HYP_TEMPLATE = "holon.derivation.laws/hypothesis"
TEMPLATE_VERSION = 1
NO_MODEL = ("no Bend model of the consumer: the consumer runs only on the evaluator-level interpreter of its SSA "
            "(holon.derivation.interp), so no counter-law or proof can be checked over it, and AGENTS rules 5 and 6 "
            "leave the law UNKNOWN until a Bend model of the consumer decides it")


def canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def law_text(obj) -> str:
    """A law file's text: holon.rules.dumps's form."""
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def side_of(root: Path, rel: str = LAWS_SIDECAR) -> dict:
    side = load(root / rel)
    if side.get("derivation_laws_version") != LAWS_VERSION:
        raise Refused(f"{rel}: derivation_laws_version must be {LAWS_VERSION}")
    for k in ("inputs", "law_set", "outputs", "vocabulary", "hypotheses", "laws", "search"):
        if k not in side:
            raise Refused(f"{rel}: no {k} section")
    for rel_in in list(side["inputs"].values()) + [side["law_set"]["facts"]]:
        if not (root / rel_in).is_file():
            raise Refused(f"{rel_in} is missing")
    ids = [e.get("id") for e in side["laws"]]
    if len(set(ids)) != len(ids):
        raise Refused(f"{rel}: duplicate law ids")
    fams = side["hypotheses"]
    for name in fams:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_]*", name):
            raise Refused(f"{rel}: hypothesis name {name!r} is not letters, digits and '_' (assumption_id)")
    for e in side["laws"]:
        for h in hyp_names(e["statement"]):
            if h not in fams:
                raise Refused(f"{e['id']}: hypothesis {h} is not in the sidecar")
    return side


def hyp_names(statement: dict) -> list:
    return [p["hyp"]["name"] for p in statement.get("assume", []) if isinstance(p.get("hyp"), dict)]


def assumption_id(name: str) -> str:
    """A hypothesis's id in a record's model_assumptions: its name in the id alphabet of
    spec/schemas/result_record_v2.schema.json (letters, digits and '-', as A-env or Hyp-Z0-kzg), each '_' written '-'
    (HypC_binds_trailing is HypC-binds-trailing). side_of admits names of letters, digits and '_' only, so the map is
    one to one and a record still names exactly its law's hypotheses."""
    return name.replace("_", "-")


# ---------------------------------------------------------------------------------------------------- refs (L3)
def product_ref(root: Path, side: dict) -> str:
    """The definition context of every product term: the derivation document, the join, the deployment, the header
    component and the vocabulary that names the terms' targets."""
    ins = side["inputs"]
    doc = {"template": PRODUCT_TEMPLATE, "template_version": TEMPLATE_VERSION,
           "document": sha256_file(root / ins["document"]), "join": load(root / ins["product"])["join"],
           "deployment": sha256_file(root / ins["deployment"]),
           "header_component": sha256_file(root / side["vocabulary"]["header_component"]),
           "vocabulary": side["vocabulary"]}
    return "sha256:" + hashlib.sha256(canon(doc)).hexdigest()


def hyp_ref(side: dict, name: str) -> str:
    h = {k: v for k, v in side["hypotheses"][name].items() if k not in ("doc", "instance")}
    return "sha256:" + hashlib.sha256(canon({"template": HYP_TEMPLATE, "template_version": TEMPLATE_VERSION,
                                             "name": name, "hypothesis": h})).hexdigest()


def with_refs(t, pref: str, side: dict):
    if isinstance(t, list):
        return [with_refs(x, pref, side) for x in t]
    if not isinstance(t, dict):
        return t
    out = {k: with_refs(v, pref, side) for k, v in t.items()}
    if isinstance(t.get("product"), str):
        out["ref"] = pref
    if isinstance(t.get("hyp"), dict):
        out["hyp"] = dict(out["hyp"], ref=hyp_ref(side, t["hyp"]["name"]))
    return out


# ---------------------------------------------------------------------------------------------------- laws (L1-L2)
def law_of(entry: dict, root: Path, side: dict, pref: str | None = None) -> dict:
    ls = side["law_set"]
    return {"ir_version": ls["ir_version"], "law_id": entry["id"], "milestone": ls["milestone"],
            "rule": entry["rule"], "subform": entry["subform"], "rule_catalog_version": ls["rule_catalog_version"],
            "facts": ls["facts"], "facts_sha256": sha256_file(root / ls["facts"]),
            "statement": with_refs(entry["statement"], pref or product_ref(root, side), side),
            "maps_to": entry["maps_to"],
            "notes": (f"plan-stated product law ({LAWS_SIDECAR}, {entry['id']}): {entry['obligation']}; generated by "
                      "holon derivation laws")}


def laws_of(root: Path, side: dict) -> list:
    pref = product_ref(root, side)
    return [law_of(e, root, side, pref) for e in side["laws"]]


def statement_hash(law: dict, root: Path) -> str:
    """holon.gen.refs.law_hash over the law's facts as holon.facts loads them: the hash `holon run` gives a 0.3 law
    (holon.contracts.statement_hash's form)."""
    from .. import facts as F
    from ..gen import oracles as O
    from ..gen import refs as R
    orc = O.Oracles.for_milestone(law["milestone"], root / law["facts"], root)
    return R.law_hash(law, F.load(root / law["facts"]), oracles=orc, root=root)


def registry(laws: list, root: Path, side: dict) -> dict:
    facts = side["law_set"]["facts"]
    return {"registry_version": REGISTRY_VERSION, "milestone": side["law_set"]["milestone"],
            "facts_files": {facts: sha256_file(root / facts)},
            "statements": {law["law_id"]: statement_hash(law, root) for law in laws}}


def outputs(root: Path, side: dict) -> dict:
    d = side["law_set"]["laws"]
    laws = laws_of(root, side)
    out = {f"{d}/{law['law_id']}.json": law_text(law) for law in laws}
    out[f"{d}/REGISTRY.json"] = law_text(registry(laws, root, side))
    return out


def stray(root: Path, side: dict, outs: dict) -> list:
    """Files of the law set's directory the generator does not write (a stale law)."""
    d = root / side["law_set"]["laws"]
    if not d.is_dir():
        return []
    return sorted(f"{side['law_set']['laws']}/{p.name}" for p in d.iterdir()
                  if f"{side['law_set']['laws']}/{p.name}" not in outs)


def committed_laws(root: Path, side: dict) -> list:
    """The law files as committed, in the sidecar's order (the decider reads these, never the sidecar's text)."""
    d = root / side["law_set"]["laws"]
    out = []
    for e in side["laws"]:
        p = d / f"{e['id']}.json"
        if not p.is_file():
            raise Refused(f"{p.relative_to(root).as_posix()} is missing (run holon derivation laws first)")
        out.append(load(p))
    return out


# ---------------------------------------------------------------------------------------------------- verdicts (D1-D3)
def evidence(law_id: str, entry: dict, candidates: list, replay: dict) -> dict:
    """A law's evaluator evidence, as verdict receives it: entry is the law's entry of the evaluations' "laws"
    ({"witness", "held", "lhs", "rhs"}), candidates the search space (the candidates file's list) and replay the replay
    report."""
    w = entry["witness"]
    wit = None
    if w is not None:
        wit = next((c for c in candidates if c["id"] == w), None)
        if wit is None:
            raise DerivationError(f"{law_id}: witness candidate {w} is not in the search space")
    return {"law": law_id, "witness": wit,
            "observation": None if w is None else {"lhs": entry["lhs"], "rhs": entry["rhs"]},
            "replay": replay.get("witnesses", {}).get(law_id), "held": entry["held"], "candidates": len(candidates)}


def verdict_of(law_id: str, model=None, root: Path = ROOT, rel: str = LAWS_SIDECAR) -> dict:
    """The decider's interface by law id: the verdict for one law of the set, from its committed law file and the
    committed outputs of `holon derivation decide` (the sidecar's outputs: candidates, evaluations, replay)."""
    root = Path(root)
    side = side_of(root, rel)
    law = next((x for x in committed_laws(root, side) if x["law_id"] == law_id), None)
    if law is None:
        raise Refused(f"{law_id} is not a law of the set {side['law_set']['laws']}")
    out = side["outputs"]
    entry = load(root / out["evaluations"]).get("laws", {}).get(law_id)
    if entry is None:
        raise Refused(f"{out['evaluations']} has no entry for {law_id} (run holon derivation decide first)")
    ev = evidence(law_id, entry, load(root / out["candidates"])["candidates"], load(root / out["replay"]))
    return verdict(law, ev, model)


def verdict(law: dict, evidence: dict, model=None) -> dict:
    """The status and the checker's attempt for one law (see the module's docstring)."""
    if model is None:
        return {"status": "UNKNOWN",
                "attempt": {"engine": "bend", "result": "not_run", "reason": NO_MODEL}}
    got = model.decide(copy.deepcopy(law), copy.deepcopy(evidence))
    if not isinstance(got, dict) or got.get("status") not in ("PROVED", "REFUTED", "UNKNOWN"):
        raise DerivationError(f"{law['law_id']}: the consumer model returned no verdict")
    if not isinstance(got.get("attempt"), dict):
        raise DerivationError(f"{law['law_id']}: the consumer model's verdict has no attempt")
    return got
