"""The diagram of an extracted transitions document (holon-diagram-transitions/0.1; I49).

holon.diagram.build maps holon-facts/0.1 and 0.2 documents. This module is the 0.3 counterpart for the transitions
documents the Solidity frontend writes (holon.frontends.solidity.transitions): the mapping is fixed by
spec/M4/lib/heldout_protocol.json diagram_mapping (rules V1-V5, E1-E5), and the output validates against
spec/M4/lib/diagram_transitions.schema.json.

  F                the document's inherited_storage and storage entries; an entry's id is its name, or
                   <declared_in>.<name> when another entry has the same name
  V1  per f in F   a state carrier, its id
  V2               State (the product of F), Act (every action's inputs, the interface), Obs (outcomes)
  V3               env.<n> per distinct ["env", n] term under the actions
  V4               ext.<fn> per distinct fn of an entry of an action's calls
  V5               hash.<fn> / commit.<fn> per distinct (kind, fn) of an entry of an action's edges
  E1  per f in F   STORE.<f> (State -> f), LOAD.<f> (f -> State)
  E2               TRANS.<a> (State -> State) per nonpayable or payable action
  E3               OBS.<a> (LOAD, State -> Obs) per view or pure action
  E4               CALL.<a>.<seq> (State -> ext.<fn>) per calls entry
  E5               <KIND>.<a>.<i> (State -> hash.<fn> | commit.<fn>) per edges entry

A construct none of these rules maps is a DiagramError and nothing is written. Pure, deterministic (document order
for families, actions, calls and edges; sorted ids for the V3-V5 carriers). Nothing here names a target.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .model import DiagramError

VERSION = "holon-diagram-transitions/0.1"
FACTS = "holon-facts/0.3"
MOVERS = ("nonpayable", "payable")
VIEWS = ("view", "pure")
EDGE_KINDS = {"HASH": ("hash", "digest", "image"), "COMMIT": ("commit", "rep", "external")}


def model_name(path: Path | str) -> str:
    """A document's diagram name: its file name without .json, every '.' replaced by '_'."""
    n = Path(path).name
    if not n.endswith(".json"):
        raise DiagramError(f"{path}: a fact document is a .json file")
    return n[:-len(".json")].replace(".", "_")


def _env(x, out: set) -> None:
    if isinstance(x, list):
        if len(x) == 2 and x[0] == "env" and isinstance(x[1], str):
            out.add(x[1])
        for v in x:
            _env(v, out)
    elif isinstance(x, dict):
        for k in sorted(x):
            _env(x[k], out)


def _carrier(cid: str, cls: str, rule: str, reach: str, interface: bool = False, base_type=None, product=None) -> dict:
    c = {"id": cid, "cls": cls, "rule": rule, "interface": interface, "reach": reach, "base_type": base_type}
    if product is not None:
        c["product"] = product
    return c


def _edge(eid: str, kind: str, rule: str, src: str, tgt: str, action, source) -> dict:
    return {"id": eid, "kind": kind, "rule": rule, "src": src, "tgt": tgt, "action": action, "source": source}


def build(doc: dict, rel: str, sha256: str) -> dict:
    if doc.get("facts_version") != FACTS:
        raise DiagramError(f"{rel}: facts_version {doc.get('facts_version')!r} is not {FACTS}")
    if not isinstance(doc.get("actions"), list) or not isinstance(doc.get("storage"), list):
        raise DiagramError(f"{rel}: not a transitions document (no actions and storage lists)")
    entries = list(doc.get("inherited_storage", [])) + list(doc["storage"])
    count = {}
    for s in entries:
        count[s["name"]] = count.get(s["name"], 0) + 1
    fams = [s["name"] if count[s["name"]] == 1 else f"{s.get('declared_in') or doc.get('contract')}.{s['name']}"
            for s in entries]
    dup = sorted({f for f in fams if fams.count(f) > 1})
    if dup:
        raise DiagramError(f"{rel}: two storage entries share the id {dup}")
    acts = doc["actions"]
    names = [a["name"] for a in acts]
    dup = sorted({a for a in names if names.count(a) > 1})
    if dup:
        raise DiagramError(f"{rel}: two actions share a name: {dup}")
    env: set = set()
    _env(acts, env)
    ext, linked = set(), set()
    for a in acts:
        for c in a.get("calls", []):
            ext.add(c["fn"])
        for e in a.get("edges", []):
            if e.get("kind") not in EDGE_KINDS:
                raise DiagramError(f"{rel}: action {a['name']}: an edges entry of kind {e.get('kind')!r} (unmapped)")
            linked.add((e["kind"], e["fn"]))
        if a.get("mutability") not in MOVERS + VIEWS:
            raise DiagramError(f"{rel}: action {a['name']}: mutability {a.get('mutability')!r} (unmapped)")
    carriers = [_carrier(f, "state", "V1", "inductive", base_type=s.get("value") or s.get("kind"))
                for f, s in zip(fams, entries)]
    carriers += [_carrier("State", "state", "V2", "inductive", base_type="State", product=fams),
                 _carrier("Act", "rep", "V2", "external", interface=True, base_type="Act"),
                 _carrier("Obs", "rep", "V2", "image", base_type="Obs")]
    carriers += [_carrier(f"env.{n}", "env", "V3", "external") for n in sorted(env)]
    carriers += [_carrier(f"ext.{fn}", "rep", "V4", "external") for fn in sorted(ext)]
    for kind, fn in sorted(linked):
        pre, cls, reach = EDGE_KINDS[kind]
        carriers.append(_carrier(f"{pre}.{fn}", cls, "V5", reach))
    edges = []
    for f in fams:
        edges.append(_edge(f"STORE.{f}", "STORE", "E1", "State", f, None, None))
        edges.append(_edge(f"LOAD.{f}", "LOAD", "E1", f, "State", None, None))
    for a in acts:
        n = a["name"]
        if a["mutability"] in MOVERS:
            edges.append(_edge(f"TRANS.{n}", "TRANS", "E2", "State", "State", n, a.get("src")))
        else:
            edges.append(_edge(f"OBS.{n}", "LOAD", "E3", "State", "Obs", n, a.get("src")))
        for c in a.get("calls", []):
            edges.append(_edge(f"CALL.{n}.{c['seq']}", "CALL", "E4", "State", f"ext.{c['fn']}", n, c.get("src")))
        for i, e in enumerate(a.get("edges", [])):
            pre = EDGE_KINDS[e["kind"]][0]
            edges.append(_edge(f"{e['kind']}.{n}.{i}", e["kind"], "E5", "State", f"{pre}.{e['fn']}", n, e.get("src")))
    ids = [e["id"] for e in edges]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        raise DiagramError(f"{rel}: edge ids collide: {dup}")
    prov = {}
    for k in ("target", "extraction"):
        if isinstance(doc.get(k), dict):
            prov[k] = doc[k]
    return {"diagram_version": VERSION, "model": model_name(rel), "facts": rel, "facts_sha256": sha256,
            "facts_version": FACTS, "contract": doc.get("contract", ""), "carriers": carriers, "edges": edges,
            "provenance": prov}


def build_file(path: Path, root: Path) -> dict:
    b = Path(path).read_bytes()
    rel = Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    return build(json.loads(b.decode("utf-8")), rel, hashlib.sha256(b).hexdigest())


def dumps(d: dict) -> str:
    return json.dumps(d, indent=2, sort_keys=True) + "\n"
