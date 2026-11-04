"""The law files of the Go part of rule PAR, regenerated for holon.bindings (I93): the statement emission
(counter=False) and the counter-law (counter=True) holon.gox.lawrun writes, from the law's DERIVATION basis and the
registry's statement hash; None for a form the decider never writes (a round trip's counter-law, a recompute's
positive law). Imported by name, so neither this module nor the decider enters a generator closure."""
from __future__ import annotations

from pathlib import Path

from . import model as G
from .lawrun import gox_entries


def emit(law: dict, m: str, root: Path, counter: bool) -> str | None:
    from .. import ir
    lid = law["law_id"]
    e = gox_entries(m, root).get(lid)
    if e is None:
        return None
    b = e["basis"]
    sh = ir.load_registry(m, root)["statements"][lid]
    mod_rel = f"../../gox/{lid}.bend"
    try:
        if e["subform"] == "go_round_trip":
            return None if counter else G.round_trip_files(b, lid, sh, mod_rel)[1]
        if e["subform"] == "go_branch":
            return G.branch_files(b, lid, sh, mod_rel, counter, G.branch_witness(b) if counter else None)[1]
        return G.recompute_files(b, lid, sh, mod_rel, G.recompute_witness(b))[1] if counter else None
    except G.ModelDebt:
        return None
