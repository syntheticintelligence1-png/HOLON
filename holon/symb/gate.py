"""G11V over rule SYM's member laws (I92): every premised PROVED law has a checked inhabitant of its premises, stated
exactly as holon.symb.lawrun generates it from the law's IR and its member's section (gen/<M>/<id>/nonvac/); a premised
REFUTED law counts through its counter-witness. Imported by name from holon.gate (outside every generator closure)."""
from __future__ import annotations

import importlib
import json
from pathlib import Path

from .. import bend
from ..inhabit import NV, _body, premised


def expected_laws_text(law: dict, m: str, root: Path, statement_hash: str) -> str:
    from ..bindings import _symb_files
    SL = importlib.import_module("holon.symb.lawrun")
    root = Path(root)
    _mp, _sp, e = _symb_files(law, m, root)
    if e is None or e.get("hit") is None:
        raise ValueError("the member's section states no premises for the law")
    return SL.nv_text(e, law["law_id"], statement_hash, root / "gen" / m / law["law_id"] / NV, root, m)


def g11v(gate, laws: list) -> tuple[bool, str]:
    """G11V over the SYM member laws among a Gate's laws (holon.gate.Gate: laws, records, root, m, cfg)."""
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
    return (not bad, f"{n_inh} premised PROVED SYM member laws inhabited (LAWS.bend regenerated from the IR, "
                     f"PROOF.bend {kernels}), {n_cw} premised REFUTED SYM member laws inhabited by their "
                     "counter-witness" if not bad else "; ".join(bad[:8]))
