"""Solidity beliefs B4 and B5 of I52's spec_mining (I52_baselines.json), run by the baselines venv's python on a unit
project: `python solmine.py UNIT OUT.json`. Standalone (imports slither only, never holon). Writes a JSON list of
deviants {belief, subject, support, confidence, file (absolute), line, function, message}, sorted.

B4 (access-control belief): for each state variable of a contract, its writers are the contract's public or external
non-constructor functions that write it (directly or through internal calls). A guard is a modifier name, or
"msg.sender check" (msg.sender read in a condition). A guard held by >= 75% of >= 3 writers, but not all, flags each
writer without it.
B5 (must-check low-level calls): over every low-level call of the scope, if >= 75% of >= 3 have their success result
read in a condition, each one whose result is not is flagged.
"""
import json
import sys

from slither import Slither
from slither.core.declarations import SolidityVariableComposed
from slither.slithir.operations import LowLevelCall

MIN_SUPPORT, MIN_CONF = 3, 0.75


def guards(f):
    g = {"modifier " + m.name for m in f.modifiers}
    if SolidityVariableComposed("msg.sender") in f.all_conditional_solidity_variables_read():
        g.add("msg.sender check")
    return g


def line(f):
    sm = f.source_mapping
    return sm.filename.absolute, (sm.lines[0] if sm.lines else 0)


def main(unit, out_path):
    sl = Slither(unit, ignore_compile=True)
    out = []
    lowlevel = []
    for c in sl.contracts:
        if c.is_interface:
            continue
        for v in c.state_variables:
            writers = [f for f in c.functions if f.visibility in ("public", "external") and not f.is_constructor
                       and f.contract_declarer == c and v in f.all_state_variables_written()]
            if len(writers) < MIN_SUPPORT:
                continue
            gs = {}
            for f in writers:
                for g in guards(f):
                    gs[g] = gs.get(g, 0) + 1
            for g, n in sorted(gs.items()):
                conf = n / len(writers)
                if conf >= MIN_CONF and n < len(writers):
                    for f in writers:
                        if g not in guards(f):
                            file, ln = line(f)
                            out.append({"belief": "B4", "subject": f"{c.name}.{v.name} guarded by {g}",
                                        "support": len(writers), "confidence": round(conf, 4), "file": file,
                                        "line": ln, "function": f"{c.name}.{f.name}",
                                        "message": f"{n} of the {len(writers)} public writers of {c.name}.{v.name} "
                                                   f"carry {g}; {f.name} writes it without"})
        for f in c.functions:
            if f.contract_declarer != c:
                continue
            for node in f.nodes:
                for ir in node.irs:
                    if isinstance(ir, LowLevelCall):
                        read = False
                        lv = ir.lvalue
                        if lv is not None:
                            for n2 in f.nodes:
                                if (n2.contains_require_or_assert() or n2.contains_if()) and any(
                                        getattr(x, "name", None) == getattr(lv, "name", "") for x in n2.variables_read):
                                    read = True
                        sm = node.source_mapping
                        lowlevel.append((read, sm.filename.absolute, sm.lines[0] if sm.lines else 0,
                                         f"{c.name}.{f.name}"))
    n = len(lowlevel)
    k = sum(1 for x in lowlevel if x[0])
    if n >= MIN_SUPPORT and k / n >= MIN_CONF and k < n:
        for read, file, ln, fn in lowlevel:
            if not read:
                out.append({"belief": "B5", "subject": "low-level call success", "support": n,
                            "confidence": round(k / n, 4), "file": file, "line": ln, "function": fn,
                            "message": f"{k} of the scope's {n} low-level calls check their success; this one does not"})
    out.sort(key=lambda d: (d["file"], d["line"], d["belief"], d["subject"]))
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
