"""A4 representative for a FACT kernel law whose inhabitant is D2 (one run used for both state binders): run the law's
own inhabitant generator (holon.fact.proofs.inhabitant_proof, holon.undo.search.settle_witness) with two runs that
differ, x2 being x1 one second later, from the committed inhabitant's prefix, and check the file with both kernels
(holon.sorts.run3.check_file: bend2, then BendTT --verdict). Run from the root of a scratch tree of the target commit.
Usage: python3 rep_fact.py <law id> <out json>"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from holon.fact import run as FR, proofs as FP
from holon.sorts import run3, proofs3 as P3, search3 as S3
from holon.undo import search as US
from holon.rules import fact as RF

lid, out = sys.argv[1], Path(sys.argv[2])
root = Path.cwd()
ctx = FR.Ctx("M3", root, None, None, None, None, log=lambda *a: None)
dec = FR.Decider(ctx)
e = ctx.rc.derivation[lid]
law = json.loads((ctx.rc.laws_dir / f"{lid}.json").read_text())
tc = ctx.fact(e["facts"])
el = tc.element(lid)
rec = json.loads((root / "results" / "M3" / f"{lid}.json").read_text())
w = rec["non_vacuity"]["witness"]
prefix = [run3.step_of_json(s) for s in w["prefix"]]
xs = run3.step_of_json(w["x"])
env2 = json.loads(json.dumps(xs.env))
env2["block.timestamp"] = int(env2["block.timestamp"]) + 1
xs2 = S3.Step(xs.action, json.loads(json.dumps(xs.args)), env2)
x = RF.ghost_x(lid)
sh = ctx.rc.registry["statements"][lid]
kh, shs, val, states = US.settle_witness(tc.factory, prefix, f"fhit_{x}",
                                         lambda m, g: [m.act(xs), {"$ref": g}, m.act(xs2)])
res = {"law": lid, "fhit_value_at_representative": val, "x1_timestamp": xs.env["block.timestamp"],
       "x2_timestamp": env2["block.timestamp"], "prefix_steps": [s.action for s in prefix], "x": xs.action}
if val is True:
    m = tc.factory(empty=True, native=False)
    acts = [m.act(st) for st in prefix]
    d = dec.paths(lid)["nonvac"].parent / "nonvac_rep"
    d.mkdir(parents=True, exist_ok=True)
    mi, si = dec.imports(d, tc)
    lp = d / "LAWS.bend"
    lp.write_text(FP.inhabitant_law(law, sh, mi, si, tc.hashes), encoding="utf-8")
    p = d / "PROOF.bend"
    args = (law, mi, si, P3.rel_import(d, lp), tc.hashes, {"s1": (acts, states), "s2": (acts, states)},
            {"x1": m.act(xs), "x2": m.act(xs2)}, {"keccak256": kh, "sha256": shs}, FP.Lit(tc.recs, set()))
    tried = []
    for shape in (FP.Shape(tc.module_text, el["subform"], el["basis"]["action"]), None):
        t = FP.inhabitant_proof(*args, shape=shape) if shape else FP.inhabitant_proof(*args)
        p.write_text(t, encoding="utf-8")
        t0 = time.time()
        checker, verdict = run3.check_file(p)
        tried.append({"by_parts": shape is not None, "marker": checker.get("marker"), "verdict": verdict,
                      "seconds": round(time.time() - t0, 1)})
        if checker.get("marker") == "ALL PROOFS CHECK" and verdict == "checked":
            break
    res["checks"] = tried
    res["laws_file"] = str(lp.relative_to(root))
    res["witness"] = {"runs": [{"prefix": dec.steps_json(tc, prefix), "x": dec.steps_json(tc, [xs])[0]},
                               {"prefix": dec.steps_json(tc, prefix), "x": dec.steps_json(tc, [xs2])[0]}],
                      "hashes": dec.hashes_json(tc, {"keccak256": kh, "sha256": shs})}
ctx.close()
out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
print(json.dumps({k: v for k, v in res.items() if k != "witness"}, indent=1))
