"""A4 representative for a DISCH law whose inhabitant is D1 (a reachable state of 0 steps): the law's own inhabitant
search (holon.disch.search.LawSearch.inhabit over its candidates) with the 0-step candidates skipped, then the law's
own inhabitant generator and check (holon.disch.run.Run.emit: settle, trace_proof, bend2 and BendTT). Run from the
root of a scratch tree of the target commit. Usage: python3 rep_disch.py <law id> <out json>"""
import json, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from holon.disch import run as DR, search as DS

lid, out = sys.argv[1], Path(sys.argv[2])
orig = DS.LawSearch.candidates
def cands(self, *a, **k):
    for trace, g, t in orig(self, *a, **k):
        if trace:
            yield trace, g, t
DS.LawSearch.candidates = cands
run = DR.Run("M3", Path.cwd(), None, None, None, None, log=lambda *a: None)
e = run.ctx.derivation[lid]
d = run.doc_of(e)
law = run.law_of(d, lid)
nd = run.paths(lid)["nonvac"]
keep = nd.parent / "nonvac_committed"
if nd.is_dir() and not keep.exists():
    shutil.copytree(nd, keep)
nv = run.inhabit(d, law)
rep = nd.parent / "nonvac_rep"
shutil.rmtree(rep, ignore_errors=True)
if nd.is_dir():
    shutil.copytree(nd, rep)
w = nv.get("witness") or {}
res = {"law": lid, "status": nv.get("status"), "bound": nv.get("bound"), "reachable": nv.get("reachable"),
       "steps": [s.get("action") for s in w.get("steps") or []], "t": w.get("t"),
       "laws_file": str((rep / "LAWS.bend").relative_to(Path.cwd())) if rep.is_dir() else None, "witness": w}
out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
print(json.dumps({k: v for k, v in res.items() if k != "witness"}, indent=1))
