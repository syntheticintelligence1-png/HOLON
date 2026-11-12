"""The AI proposal channel (I104; rule R4 of tests_m6/test_i104_roles.py).

A proposal file (holon-roles-proposed/0.1) is written by an agent outside the gate and committed as data:

  {"roles_proposed_version": "holon-roles-proposed/0.1", "proposer": "agent", "doc": "...",
   "link":      {<id>: {"solidity": {document, edge|constant}, "go": {document, function|global}}},
   "go_ops":    {<id>: {"document", "carrier"}},
   "recompute": {<id>: {"go": {"document", "functions": [...]}, "solidity": {"document", "action", "store"}}}}

Its provenance is model-free: proposer must be "agent", and a key "model" anywhere refuses the file. It is read with its
sha256 and merged with the static roles deterministically (sorted ids): a proposed role whose id is a static role's id,
or whose facts already play a static role of the same sidecar, is dropped (static wins) and listed. Every merged role
carries roles_source "ai_proposal" and the evidence rule "proposal" with the facts it names. Nothing is checked against
the documents here beyond their presence: the readers and the checker decide what a wrong role gives.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .infer import RolesError, ident

VERSION = "holon-roles-proposed/0.1"


def _has_model_key(x) -> bool:
    if isinstance(x, dict):
        return any(k == "model" or _has_model_key(v) for k, v in x.items())
    if isinstance(x, list):
        return any(_has_model_key(v) for v in x)
    return False


def read(path: Path) -> tuple[dict, dict]:
    raw = Path(path).read_bytes()
    try:
        p = json.loads(raw)
    except ValueError as e:
        raise RolesError(f"{path}: not JSON ({e})") from e
    if not isinstance(p, dict) or p.get("roles_proposed_version") != VERSION:
        raise RolesError(f"{path}: roles_proposed_version is not {VERSION}")
    if p.get("proposer") != "agent":
        raise RolesError(f"{path}: proposer must be \"agent\" (model-free provenance), not {p.get('proposer')!r}")
    if _has_model_key(p):
        raise RolesError(f"{path}: a proposal names no model (a key \"model\" is present)")
    for k in ("link", "go_ops", "recompute"):
        if not isinstance(p.get(k, {}), dict):
            raise RolesError(f"{path}: {k} is not an object")
    return p, {"sha256": hashlib.sha256(raw).hexdigest(), "proposer": "agent"}


def _facts_of(r: dict) -> set:
    if r["sidecar"] == "link":
        return {json.dumps(r["solidity"], sort_keys=True), json.dumps(r["go"], sort_keys=True)}
    if r["sidecar"] == "go_ops":
        return {r["carrier"]}
    if r["sidecar"] == "go_laws" and "go" in r:
        return {f"{r['go']['document']}#{fn}" for fn in r["go"]["functions"]} | \
            {json.dumps(r["solidity"], sort_keys=True)}
    return set()


def _strip(src: dict) -> dict:
    return {k: v for k, v in src.items() if k != "fact"}


def roles_of(p: dict) -> list:
    out = []
    for rid, r in sorted((p.get("link") or {}).items()):
        s, g = r.get("solidity") or {}, r.get("go") or {}
        out.append({"sidecar": "link", "id": ident(rid), "roles_source": "ai_proposal",
                    "evidence": {"rule": "proposal", "facts": sorted({s.get("document", ""), g.get("document", "")})},
                    "solidity": s, "go": g})
    for rid, r in sorted((p.get("go_ops") or {}).items()):
        out.append({"sidecar": "go_ops", "id": ident(rid), "roles_source": "ai_proposal",
                    "evidence": {"rule": "proposal", "facts": [r.get("document", "")]},
                    "document": r.get("document"), "carrier": r.get("carrier"), "reach": r.get("reach") or
                    "proposed: the proposal's word, unchecked"})
    for rid, r in sorted((p.get("recompute") or {}).items()):
        g, s = r.get("go") or {}, r.get("solidity") or {}
        out.append({"sidecar": "go_laws", "id": ident(rid), "roles_source": "ai_proposal",
                    "evidence": {"rule": "proposal", "facts": sorted({g.get("document", ""), s.get("document", "")})},
                    "go": {"document": g.get("document"), "functions": list(g.get("functions") or [])},
                    "solidity": s})
    return out


def merge(static: list, proposed: list) -> tuple[list, list]:
    """(merged roles, dropped proposals): static wins on an id or a fact it already assigns."""
    ids = {(r["sidecar"], r["id"]) for r in static}
    facts: dict = {}
    for r in static:
        facts.setdefault(r["sidecar"], set()).update(_facts_of({**r, **({"solidity": _strip(r["solidity"]),
                                                                          "go": _strip(r["go"])}
                                                                         if r["sidecar"] == "link" else {})}))
    out, dropped = list(static), []
    for r in proposed:
        k = (r["sidecar"], r["id"])
        f = _facts_of({**r, **({"solidity": _strip(r["solidity"]), "go": _strip(r["go"])}
                               if r["sidecar"] == "link" else {})})
        if k in ids:
            dropped.append({"sidecar": r["sidecar"], "id": r["id"], "reason": "a static role has this id"})
            continue
        if f & facts.get(r["sidecar"], set()):
            dropped.append({"sidecar": r["sidecar"], "id": r["id"], "reason": "a fact it names plays a static role"})
            continue
        ids.add(k)
        facts.setdefault(r["sidecar"], set()).update(f)
        out.append(r)
    return out, dropped
