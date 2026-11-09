"""A4 representative for a SYM law whose inhabitant is D1 (its state is the initial state): the law's own inhabitant
search (holon.symd.search.SymSearch.inhabitant) with the empty prefix skipped, so the first inhabitant it finds is at
a reachable state that is not the initial one, then the law's own inhabitant generator and check
(holon.symd.run.Decider.inhabit: settle_witness, holon.symd.proofs.inhabitant_proof, bend2 and BendTT). Run from the
root of a scratch tree of the target commit. Usage: python3 rep_sym.py <law id> <out json>"""
import json, sys, shutil
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from holon.symd import run as SR, search as SY

lid, out = sys.argv[1], Path(sys.argv[2])
orig = SY.SymSearch.over_prefixes
SY.SymSearch.over_prefixes = lambda self, entry, at: orig(self, entry, lambda trace, g: None if not trace else at(trace, g))
ctx = SR.Ctx("M3", Path.cwd(), None, None, None, log=lambda *a: None)
dec = SR.Decider(ctx)
e = ctx.rc.derivation[lid]
law = json.loads((ctx.rc.laws_dir / f"{lid}.json").read_text())
sc = ctx.sec(e["facts"])
el = next(x for x in sc.elements if x["law_id"] == lid)
nd = dec.paths(lid)["nonvac"]
keep = nd.parent / "nonvac_committed"
if nd.is_dir() and not keep.exists():
    shutil.copytree(nd, keep)
nv = dec.inhabit(el, law, sc)
rep = nd.parent / "nonvac_rep"
shutil.rmtree(rep, ignore_errors=True)
if nd.is_dir():
    shutil.copytree(nd, rep)
w = nv.get("witness") or {}
res = {"law": lid, "status": nv.get("status"), "bound": nv.get("bound"), "reachable": nv.get("reachable"),
       "prefix_steps": [s.get("action") for s in w.get("prefix") or []], "x": (w.get("x") or {}).get("action"),
       "laws_file": str((rep / "LAWS.bend").relative_to(Path.cwd())) if rep.is_dir() else None, "witness": w}
ctx.close()
out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
print(json.dumps({k: v for k, v in res.items() if k != "witness"}, indent=1))
