"""spec_mining (I52_baselines.json): frequency-based beliefs over the scope, Go (B1-B3, gotool mine) and Solidity (B4-B5,
solmine.py on the unit project). One unit per language present, each within its share of the budget."""
from __future__ import annotations

import json
from pathlib import Path

from . import core, gofuzz, sol


def run_spec_mining(system, target, wall, cpu):
    src = core.checkout(system, target)
    langs = core.languages(system, target)
    u = core.Units(wall, len(langs))
    fs, cmds, exhausted, setup, notes = [], [], False, 0.0, []
    status = "run"
    if "go" in langs:
        dirs = [str(src / p) for p in gofuzz.go_packages(src, system, target)]
        out = core.WORK / system / target / "mine-go.json"
        argv = [str(gofuzz.ensure_gotool()), "mine", str(src), *dirs]
        log = core.WORK / system / target / "logs" / "mine-go.log"
        r = core.run_bounded(argv, src, u.share(), cpu, {}, log)
        u.done("go", r["wall_s"], r["cpu_s"], exit=r["exit"], timed_out=r["timed_out"])
        exhausted |= r["timed_out"]
        cmds.append("i52-gotool mine <checkout> " + " ".join(gofuzz.go_packages(src, system, target)))
        try:
            data = json.loads(r["output"]) or []
        except json.JSONDecodeError:
            data, status = [], "error"
            notes.append("go miner output unreadable: " + core.tail(r["output"], 400))
        for d in data:
            s = d["site"]
            fs.append(core.finding(f"belief-{d['belief']}", d["message"], [core.loc(s["file"], s["line"], None, s["func"])],
                                   None, {"subject": d["subject"], "support": d["support"],
                                          "confidence": round(d["confidence"], 4)}))
        out.write_text(json.dumps(data or [], indent=1))
    if "solidity" in langs:
        b = sol.build(system, target)
        setup += b.get("setup_s", 0)
        if not b["ok"]:
            notes.append("solidity: " + (b["reason"] or "build failed"))
            if "go" not in langs:
                status = "error"
        else:
            unit = Path(b["unit"])
            out = unit / "solmine.json"
            out.unlink(missing_ok=True)
            argv = [str(core.PY / "python"), str(Path(__file__).parent / "solmine.py"), str(unit), str(out)]
            r = core.run_bounded(argv, unit, u.share(), cpu, sol.env(), unit / "solmine.log")
            u.done("solidity", r["wall_s"], r["cpu_s"], exit=r["exit"], timed_out=r["timed_out"])
            exhausted |= r["timed_out"]
            cmds.append("baselines-py/python solmine.py <unit project> <out>")
            if out.is_file():
                for d in core.load(out):
                    rel = sol.rel_of(b, d["file"])
                    if rel:
                        fs.append(core.finding(f"belief-{d['belief']}", d["message"],
                                               [core.loc(rel, d["line"], None, d["function"])], None,
                                               {"subject": d["subject"], "support": d["support"],
                                                "confidence": d["confidence"]}))
            else:
                notes.append("solidity miner failed: " + core.tail(r["output"], 600))
                if "go" not in langs:
                    status = "error"
    return {"status": status, "reason": "; ".join(notes) or None, "findings": fs if status == "run" else [],
            "units": u.used, "commands": cmds, "seeds": {}, "budget_exhausted": exhausted, "setup_s": round(setup, 3)}


RUNNERS = {"spec_mining": run_spec_mining}
