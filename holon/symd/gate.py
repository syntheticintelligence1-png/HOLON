"""G11V for rule SYM's laws (I34): the inhabitant of a premised PROVED SYM law, as holon.symd.run writes it.

holon.inhabit.g11v regenerates an inhabitant over the untyped Machine. A SYM law's inhabitant is stated over the typed
model and its sym section (holon.symd.proofs.inhabitant_law), so holon.gate.Gate.g11v routes the SYM laws here:
  - a law without premises records no_premises, and a REFUTED law's non_vacuity is its counter-witness, as for every law;
  - a premised PROVED law records status inhabited, for this statement, with a reachable witness;
  - its directory gen/<M>/<id>/nonvac holds exactly LAWS.bend and PROOF.bend;
  - LAWS.bend is the existential holon.symd.proofs.inhabitant_law regenerates from the law's IR and the registry's
    statement hash (comments ignored): a reachable state (a Reach proof from s0) and binders where the law's premises
    (its sy_hit) hold;
  - PROOF.bend imports that file, defines its law, uses no escape hatch, and both kernels accept it.
The kernels' acceptance of the existential is the non-vacuity: no stored witness or flag is trusted for it, and the
decider's search is how the proof was found, not why it holds. holon.gate imports this module by name, so it stays
outside every generator closure.
"""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from .. import bend
from ..inhabit import NV, _body, premised


def sym_laws(laws: list) -> list:
    """The SYM laws among laws (holon.bindings._sym: a holon-ir/0.3 law of holon.rules.sym)."""
    from ..bindings import _sym
    return [law for law in laws if _sym(law)]


def expected_laws_text(law: dict, m: str, root: Path, statement_hash: str) -> str:
    """The inhabitant LAWS.bend holon.symd.run writes for law, regenerated from its IR (its sy_hit index in the
    document's SYM elements, the typed model's hash tables, and the imports from gen/<m>/<id>/nonvac)."""
    from ..bindings import _sym_section, _typed_model
    from ..rules import sym as RS
    from ..sorts.evaluate3 import hashes_of
    from ..sorts.model3 import model_name as typed_name
    from ..sorts.proofs3 import rel_import
    SP = importlib.import_module("holon.symd.proofs")
    root = Path(root)
    d = root / "gen" / m / law["law_id"] / NV
    doc = json.loads((root / law["facts"]).read_text())
    sorts = json.loads((root / "gen" / m / "sorts" / "assignment.json").read_text())
    els = RS.elements(doc, sorts["models"][typed_name(law["facts"])]["assignment"], law["facts"])
    n = next((i for i, e in enumerate(els) if e["law_id"] == law["law_id"]), None)
    if n is None:
        raise ValueError("the document's SYM analysis no longer gives the law")
    tm = _typed_model(law, m, root, importable=True)
    return SP.inhabitant_law(law, n, statement_hash, rel_import(d, tm), rel_import(d, _sym_section(law, m, root)),
                             hashes_of(tm.read_text()))


def g11v(gate, laws: list) -> tuple[bool, str]:
    """G11V over the SYM laws among a Gate's laws (holon.gate.Gate: laws, records, root, m, cfg)."""
    dual = bend.verdict_enabled(gate.cfg)
    reg = json.loads((Path(gate.root) / "laws" / gate.m / "REGISTRY.json").read_text())["statements"]
    recs = gate.records()
    bad, n_inh, n_cw = [], 0, 0
    for law in laws:
        lid = law["law_id"]
        rec = recs.get(lid)
        if rec is None:
            bad.append(f"{lid}: no result record")
            continue
        nv = rec.get("non_vacuity")
        if not isinstance(nv, dict):
            bad.append(f"{lid}: no non_vacuity record")
            continue
        if nv.get("parent_statement_hash") != rec.get("statement_hash"):
            bad.append(f"{lid}: non_vacuity is for another statement")
        if not premised(law):
            if nv.get("status") != "no_premises":
                bad.append(f"{lid}: no premises, but non_vacuity says {nv.get('status')!r}")
            continue
        if rec.get("status") == "REFUTED":
            n_cw += 1
            if nv.get("status") != "counter_witness":
                bad.append(f"{lid}: REFUTED, but non_vacuity says {nv.get('status')!r}")
            continue
        if rec.get("status") != "PROVED":
            continue
        if nv.get("status") != "inhabited":
            bad.append(f"{lid}: premised PROVED law without an inhabitant ({nv.get('bound')})")
            continue
        if nv.get("reachable") is not True or nv.get("witness") is None:
            bad.append(f"{lid}: the inhabitant records no reachable witness")
            continue
        d = Path(gate.root) / "gen" / gate.m / lid / NV
        files = sorted(f.name for f in d.iterdir()) if d.is_dir() else []
        if files != ["LAWS.bend", "PROOF.bend"]:
            bad.append(f"{lid}: inhabitant directory holds {files}, expected exactly LAWS.bend and PROOF.bend")
            continue
        try:
            want = expected_laws_text(law, gate.m, gate.root, reg[lid])
        except Exception as e:  # noqa: BLE001  (a law that cannot be regenerated fails the check)
            bad.append(f"{lid}: inhabitant LAWS.bend cannot be regenerated from its IR: {type(e).__name__}: {e}")
            continue
        laws_text, proof_text = (d / "LAWS.bend").read_text(), (d / "PROOF.bend").read_text()
        if _body(laws_text) != _body(want):
            bad.append(f"{lid}: inhabitant LAWS.bend is not the one generated from the law's IR")
            continue
        name = f"nv_{lid.lower()}"
        if "import ./LAWS.bend as Laws" not in proof_text or f"def Laws.{name}(" not in proof_text:
            bad.append(f"{lid}: inhabitant PROOF.bend does not import ./LAWS.bend and define Laws.{name}")
            continue
        if bend.escape_hatches(laws_text + proof_text):
            bad.append(f"{lid}: inhabitant uses an escape hatch")
            continue
        r = bend.check(d / "PROOF.bend", gate.cfg)
        if not r.ok:
            bad.append(f"{lid}: inhabitant rejected by bend: {r.first_line}")
            continue
        if dual:
            v = bend.check_verdict(d / "PROOF.bend", gate.cfg)
            if not v.ok:
                bad.append(f"{lid}: inhabitant rejected by BendTT: {v.first_line}")
                continue
        n_inh += 1
    kernels = "dual-checked" if dual else "single-kernel: BendTT unavailable"
    return (not bad, f"{n_inh} premised PROVED SYM laws inhabited (LAWS.bend regenerated from the IR, PROOF.bend "
                     f"{kernels}), {n_cw} premised REFUTED SYM laws inhabited by their counter-witness"
                     if not bad else "; ".join(bad[:8]))
