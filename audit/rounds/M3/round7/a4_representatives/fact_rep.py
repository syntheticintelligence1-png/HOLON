"""A4 representative for L_fact_kernel_Rollup_commitState_committedBatches_blobhash (D2: both runs identical): two
DIFFERENT reachable runs, run 1 = the committed inhabitant's prefix (commitBatch of batch 1 at T0, revertBatch), then
its commitState; run 2 = the same steps 5 s later (commitBatch, revertBatch and commitState at T0 + 5), so the states
differ (batchDataStore[1]'s times) while the committed header, hence committedBatches, is the same. The law's own
generator (holon.fact.proofs.inhabitant_law / inhabitant_proof, by parts first as holon.fact.run.Decider.inhabit
does) and both kernels (run3.check_file) check it. Writes only under the scratch directory."""
import json, sys, os, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]   # the repository root (the run used the auditor's checkout of the target)
sys.path.insert(0, str(ROOT))
scratch = Path(sys.argv[1])
os.environ['HOLON_BUILD_DIR'] = str(scratch / 'build')
from holon.fact import run as FR
from holon.fact import proofs as FP
from holon.rules import fact as RF
from holon.sorts import run3, proofs3 as P3
from holon.undo import search as US
from holon.audit.vacuity import degenerate_rules
lid = 'L_fact_kernel_Rollup_commitState_committedBatches_blobhash'
rec = json.loads((ROOT / f'results/M3/{lid}.json').read_text())
law = json.loads((ROOT / f'laws/M3/{lid}.json').read_text())
w0 = rec['non_vacuity']['witness']
def later(st, dt):
    s = copy.deepcopy(st)
    s['env']['block.timestamp'] = int(s['env']['block.timestamp']) + dt
    return s
p1 = [run3.step_of_json(copy.deepcopy(s)) for s in w0['prefix']]
p2 = [run3.step_of_json(later(s, 5)) for s in w0['prefix']]
x1 = run3.step_of_json(copy.deepcopy(w0['x']))
x2 = run3.step_of_json(later(w0['x'], 5))
ctx = FR.Ctx('M3', ROOT, None, None, scratch / 'gen', scratch / 'out', log=lambda *a, **k: print(*a, file=sys.stderr))
dec = FR.Decider(ctx)
try:
    doc_rel = ctx.rc.derivation[lid]['facts']
    tc = ctx.fact(doc_rel)
    el = tc.element(lid)
    x = RF.ghost_x(lid)
    holder = {}
    def args_of(m, g):
        g2 = m.s0()
        for st in p2:
            code, g2, _c = m.run_step(g2, US.fresh_step(st), save=True)
            if code != 0:
                raise RuntimeError(f'run 2 prefix step {st.action} fails (code {code})')
        holder['g2'] = g2
        return [m.act(x1), {"$ref": g2}, m.act(x2)]
    kh, shs, val, states1 = US.settle_witness(tc.factory, p1, f'fhit_{x}', args_of)
    # the decoded states of run 2 with the settled tables
    m = tc.factory(empty=True, native=False)
    m.kh, m.sh = dict(kh), dict(shs)
    g = m.s0()
    states2 = []
    for st in p2:
        _code, g, _c = m.run_step(g, US.fresh_step(st), save=True)
        states2.append(m.ev.req({"show": g})["out"])
    m2 = tc.factory(empty=True, native=False)
    acts1 = [m2.act(st) for st in p1]
    acts2 = [m2.act(st) for st in p2]
    d = scratch / 'gen' / lid / 'rep'
    d.mkdir(parents=True, exist_ok=True)
    mi, si = dec.imports(d, tc)
    sh = ctx.rc.registry['statements'][lid]
    lp = d / 'LAWS.bend'
    lp.write_text(FP.inhabitant_law(law, sh, mi, si, tc.hashes), encoding='utf-8')
    args = (law, mi, si, P3.rel_import(d, lp), tc.hashes, {"s1": (acts1, states1), "s2": (acts2, states2)},
            {"x1": m2.act(x1), "x2": m2.act(x2)}, {"keccak256": kh, "sha256": shs}, FP.Lit(tc.recs, set()))
    cands = [FP.inhabitant_proof(*args, shape=FP.Shape(tc.module_text, el["subform"], el["basis"]["action"])),
             FP.inhabitant_proof(*args)]
    limit = dec.budget - dec.measure.terms(dec.measure.law_blocks((ROOT / 'gen/M3/laws' / lid / 'LAWS.bend').read_text()))
    tried = []
    ok = None
    for i, t in enumerate(cands):
        n = dec.measure.terms(t)
        p = d / f'PROOF.{i}.bend'
        p.write_text(t, encoding='utf-8')
        pp = d / 'PROOF.bend'
        pp.write_text(t, encoding='utf-8')
        checker, verdict = run3.check_file(pp)
        tried.append({'candidate': ['by_parts', 'closed'][i], 'terms': n, 'limit': limit, 'bend2': checker['marker'], 'bendtt': verdict})
        if checker['marker'] == 'ALL PROOFS CHECK' and verdict == 'checked':
            ok = i
            break
    wj = {"runs": [{"prefix": dec.steps_json(tc, p1), "x": dec.steps_json(tc, [x1])[0]},
                   {"prefix": dec.steps_json(tc, p2), "x": dec.steps_json(tc, [x2])[0]}],
          "hashes": dec.hashes_json(tc, {"keccak256": kh, "sha256": shs})}
    rules, readable = degenerate_rules(law, wj)
    res = {'fhit': val, 'tried': tried, 'accepted_candidate': ok, 'degenerate_rules': sorted(rules), 'readable': readable,
           'witness': wj}
    print(lid, json.dumps({k: v for k, v in res.items() if k != 'witness'}), flush=True)
    (scratch / 'fact_rep.json').write_text(json.dumps({lid: res}, indent=1, sort_keys=True) + '\n')
finally:
    ctx.close()
