"""The three law sets of one unit (instrument law_sets; the contract's pipeline steps 3-4): own decided inputs,
carrying, matching, families, and the law entries' common fields. The M0 decision path is holon.mutate.m0; the trace
laws (M1x and M2) are decided here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from . import common as C

SETS = ("M0", "M1x", "M2")
M0_FAMILIES = (("L_par_hdr_", "PAR-codec"), ("L_rt_go_", "PAR-round-trip"), ("L_dom_hdr", "PAR-domain"))
VIEW = "gen/M2/extracted/m1_view.json"
REPLAY_CANDIDATES_KEY = "replay_candidates"
SPAN_RE = re.compile(r"^(?P<unit>.+):(?P<lo>[0-9]+)(?:-(?P<hi>[0-9]+))?$")


def entry(set_: str, family: str, baseline: str) -> dict:
    """A law entry with every field of the record format at its empty value."""
    return {"set": set_, "matched_from": None, "family": family, "entry_points": None, "baseline": baseline,
            "mutant": "absent", "decided": None, "own_input": {"sha256": None, "changed": None}, "predicted": False,
            "basis_span": None, "site_in_mutated_function": False, "proof": None, "hits": None, "replay": None,
            "witness": None, "counter_law": None, "falsifier": None, "witness_fits_entry": None, "how": None,
            "error": None}


def m0_family(law_id: str) -> str:
    for pre, fam in M0_FAMILIES:
        if law_id.startswith(pre):
            return fam
    raise C.MutateError(f"{law_id}: no M0 family")


def statement_part(law: dict) -> dict:
    """The statement component of an own decided input: the law file without facts_sha256."""
    return {k: v for k, v in law.items() if k != "facts_sha256"}


def own_input_sha(law: dict, facts: dict, cone: dict) -> str:
    """law_sets.own_input: sha256 of the canonical JSON {statement, facts, cone}."""
    return C.sha256_text(C.compact({"statement": statement_part(law), "facts": facts, "cone": cone}))


def cones(deps_path: Path, defs_path: Path) -> dict:
    """{law: {definition: sha256 of its BendTT kernel form}} from a run's deps.json and its model's defs index."""
    deps = json.loads(Path(deps_path).read_text())
    defs = json.loads(Path(defs_path).read_text())["defs"]
    out: dict = {}
    for d, laws in deps.get("dependents", {}).items():
        for law in laws:
            out.setdefault(law, {})[d] = defs[d]["sha256"] if d in defs else None
    return {law: dict(sorted(v.items())) for law, v in sorted(out.items())}


def span_inside(span, where) -> bool:
    """Whether a basis span '<unit>:<lo>[-<hi>]' lies inside (unit, first, last)."""
    if where is None or not isinstance(span, str):
        return False
    mt = SPAN_RE.match(span)
    if mt is None or mt.group("unit") != where[0]:
        return False
    lo, hi = int(mt.group("lo")), int(mt.group("hi") or mt.group("lo"))
    return where[1] <= lo and hi <= where[2]


def derivation(root: Path) -> dict:
    """{law id: DERIVATION entry} of a tree's laws/M2."""
    p = Path(root) / "laws" / "M2" / "DERIVATION.json"
    return {e["law_id"]: e for e in json.loads(p.read_text())["laws"]}


def match_key(e: dict) -> tuple:
    return (e.get("rule"), e.get("subform"), (e.get("basis") or {}).get("span"))


def match(base_der: dict, mut_der: dict) -> tuple[dict, list, list]:
    """law_sets.matching: ({baseline law: mutant law id it is decided from}, [new mutant law ids], [baseline laws the
    mutant run lacks]). A mutant law id absent from the baseline is matched to the one baseline law with its (rule,
    subform, basis span) when exactly one exists and that baseline id is not itself derived on the mutant."""
    pairs = {law: law for law in base_der if law in mut_der}
    new = []
    by_key: dict = {}
    for law, e in base_der.items():
        by_key.setdefault(match_key(e), []).append(law)
    for law in sorted(mut_der):
        if law in base_der:
            continue
        cands = by_key.get(match_key(mut_der[law]), [])
        if len(cands) == 1 and cands[0] not in mut_der and cands[0] not in pairs:
            pairs[cands[0]] = law
        else:
            new.append(law)
    missing = sorted(law for law in base_der if law not in pairs)
    return dict(sorted(pairs.items())), new, missing


def m2_traces(rec: dict) -> list:
    """The witness traces of an M2 SORT-site record ({entry: {witness: {a, s: {run}}}}): [(label, trace)] in entry
    order, the I15 replay's trace (prefix run, then the action)."""
    out = []
    for ent, w in sorted((rec.get("witnesses") or {}).items()):
        wt = (w or {}).get("witness")
        if not isinstance(wt, dict) or "a" not in wt:
            continue
        run = ((wt.get("s") or {}).get("run")) or []
        out.append((ent, list(run) + [wt["a"]]))
    if not out and isinstance(rec.get("witness"), dict) and "a" in rec["witness"]:
        wt = rec["witness"]
        out.append(("witness", list(((wt.get("s") or {}).get("run")) or []) + [wt["a"]]))
    return out


def m1_traces(law: dict, rec: dict) -> list:
    """The concrete traces of an M1x record's witness (holon.mreplay.linearise): [(label, trace)]."""
    w = rec.get("witness")
    if not isinstance(w, dict):
        return []
    from ..mreplay import linearise
    try:
        sides = linearise(law, w)
    except (ValueError, KeyError, AssertionError, IndexError):
        return []
    return [(s["label"], s["trace"]) for s in sides if isinstance(s.get("trace"), list)]
