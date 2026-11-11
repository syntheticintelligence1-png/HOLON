"""A4 representative for a D1-degenerate DISCH law: the law's own inhabitant generator (holon.disch.run: Run.emit ->
trace_proof, checked by check_file in bend2 and BendTT), at a witness whose state is NOT the initial state: a reachable
prefix of one successful commitBatch (the step of the committed FACT inhabitant's prefix, its external-call answers as
recorded) followed by the law's own recorded last step. Writes only under the scratch directory given."""
import json, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]   # the repository root (the run used the auditor's checkout of the target)
sys.path.insert(0, str(ROOT))
scratch = Path(sys.argv[1]); lids = sys.argv[2:]
os.environ['HOLON_BUILD_DIR'] = str(scratch / 'build')
from holon.disch.run import Run
from holon.sorts import run3 as R3
from holon.audit.vacuity import degenerate_rules
fact = json.loads((ROOT / 'results/M3/L_fact_kernel_Rollup_commitState_committedBatches_blobhash.json').read_text())
commit_step = fact['non_vacuity']['witness']['prefix'][0]
assert commit_step['action'] == 'commitBatch'
r = Run('M3', ROOT, None, None, scratch / 'gen', scratch / 'out', log=lambda *a, **k: print(*a, file=sys.stderr))
out = {}
try:
    for lid in lids:
        rec = json.loads((ROOT / f'results/M3/{lid}.json').read_text())
        law_ir = json.loads((ROOT / f'laws/M3/{lid}.json').read_text())
        w0 = rec['non_vacuity']['witness']
        e = r.ctx.derivation[lid]
        d = r.doc_of(e)
        law = r.law_of(d, lid)
        steps = [R3.step_of_json(commit_step)] + [R3.step_of_json(s) for s in w0['steps']]
        t = int(w0['t'])
        # the prefix must succeed on the model
        m = d.factory()
        g = m.s0()
        codes = []
        for s in steps[:-1]:
            code, g, _c = m.run_step(g, R3.S3.Step(s.action, s.args, json.loads(json.dumps(s.env))), save=True)
            codes.append(code)
        nd = scratch / 'gen' / lid / 'rep'
        from holon.disch.run import nonvac_law_text, rel_import
        nd.mkdir(parents=True, exist_ok=True)
        lpn = nd / 'LAWS.bend'
        sh = r.ctx.registry['statements'][lid]
        lpn.write_text(nonvac_law_text(lid, sh, rel_import(nd, d.ip), rel_import(nd, d.simp), [n for n, _h in d.tb]))
        p, checker, verdict, tables, val = r.emit(d, law, steps, t, 'nonvac', nd, lpn, 'A4 representative (round 7)')
        wj = r.witness_json(d, steps, t, tables)
        rules, readable = degenerate_rules(law_ir, wj)
        out[lid] = {'prefix_codes': codes, 'premise_value': val, 'bend2': checker.get('marker'), 'bendtt': verdict,
                    'degenerate_rules': sorted(rules), 'readable': readable, 'steps': [s['action'] for s in wj['steps']],
                    'witness': wj}
        print(lid, json.dumps({k: v for k, v in out[lid].items() if k != 'witness'}), flush=True)
finally:
    r.close()
(scratch / 'disch_rep.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
