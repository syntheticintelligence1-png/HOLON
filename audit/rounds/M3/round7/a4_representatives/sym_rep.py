"""A4 representative for the D1-degenerate SYM sentinel laws (commitBatch / commitBatchWithProof at Rollup.sol:366):
the law's own inhabitant generator (holon.symd.run.Decider.inhabit's body: US.settle_witness, SP.inhabitant_law,
SP.inhabitant_proof, run3.check_file in bend2 and BendTT) at a witness whose state is NOT the initial state: the
prefix is one successful commitBatch of batch 1 (the committed inhabitant's own step), and x is a commitBatch of batch 2
whose parent header is batch 1's header (the FACT inhabitant's revertBatch argument, i.e. what batch 1 committed).
Writes only under the scratch directory given."""
import json, sys, os, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]   # the repository root (the run used the auditor's checkout of the target)
sys.path.insert(0, str(ROOT))
scratch = Path(sys.argv[1]); lids = sys.argv[2:]
os.environ['HOLON_BUILD_DIR'] = str(scratch / 'build')
from holon.symd import run as SR
from holon.symd import proofs as SP
from holon.sorts import run3
from holon.undo import proofs as UP
from holon.audit.vacuity import degenerate_rules
import holon.symd.run as SRM
US = SRM.US
fact = json.loads((ROOT / 'results/M3/L_fact_kernel_Rollup_commitState_committedBatches_blobhash.json').read_text())
fw = fact['non_vacuity']['witness']
assert fw['prefix'][1]['action'] == 'revertBatch'
batch1_header = fw['prefix'][1]['args']['_batchHeader']
ctx = SR.Ctx('M3', ROOT, None, scratch / 'gen', scratch / 'out', log=lambda *a, **k: print(*a, file=sys.stderr))
dec = SR.Decider(ctx)
out = {}
try:
    for lid in lids:
        rec = json.loads((ROOT / f'results/M3/{lid}.json').read_text())
        law = json.loads((ROOT / f'laws/M3/{lid}.json').read_text())
        w0 = rec['non_vacuity']['witness']
        doc_rel = ctx.rc.derivation[lid]['facts']
        sc = ctx.sec(doc_rel)
        el = next(e for e in sc.elements if e['law_id'] == lid)
        x1 = copy.deepcopy(w0['x'])
        if x1['action'] != 'commitBatch':
            # commitBatchWithProof's inhabitant: keep its own x, and put the commitBatch of batch 1 before it
            pre = [run3.step_of_json(copy.deepcopy(json.loads((ROOT / 'results/M3/L_sym_sentinel_Rollup_batchDataStore_originTimestamp_commitBatch_366.json').read_text())['non_vacuity']['witness']['x']))]
            x2 = copy.deepcopy(x1)
            x2['args']['batchDataInput']['parentBatchHeader'] = batch1_header
            x2['args']['batchDataInput']['prevStateRoot'] = 1
            x2['args']['batchDataInput']['postStateRoot'] = 2
            x2['env']['block.timestamp'] = int(x1['env']['block.timestamp']) + 1
        else:
            pre = [run3.step_of_json(x1)]
            x2 = copy.deepcopy(x1)
            x2['args']['batchDataInput']['parentBatchHeader'] = batch1_header
            x2['args']['batchDataInput']['prevStateRoot'] = 1
            x2['args']['batchDataInput']['postStateRoot'] = 2
            x2['env']['block.timestamp'] = int(x1['env']['block.timestamp']) + 1
        w = {"prefix": pre, "x": run3.step_of_json(x2)}
        # the prefix and the step must succeed on the model
        m0 = sc.factory()
        g = m0.s0()
        codes = []
        for st in w['prefix'] + [w['x']]:
            code, g, _c = m0.run_step(g, run3.S3.Step(st.action, st.args, json.loads(json.dumps(st.env))), save=True)
            codes.append(code)
        n = sc.fn[lid]
        sh = ctx.rc.registry['statements'][lid]
        kh, shh, val, states = US.settle_witness(sc.factory, w['prefix'], f'sy_hit_{n}', dec.args_of(el, w))
        m = sc.factory(empty=True, native=False)
        nd = scratch / 'gen' / lid / 'rep'
        nd.mkdir(parents=True, exist_ok=True)
        mi, si = dec.imports(nd, sc)
        lp = nd / 'LAWS.bend'
        lp.write_text(SP.inhabitant_law(law, n, sh, mi, si, sc.hashes), encoding='utf-8')
        p = nd / 'PROOF.bend'
        text = SP.inhabitant_proof(law, n, mi, si, './LAWS.bend', sc.hashes, [m.act(x) for x in w['prefix']],
                                   states, dec.values(el, w, m), {'keccak256': kh, 'sha256': shh},
                                   UP.Lit(sc.recs, sc.mine))
        p.write_text(text, encoding='utf-8')
        checker, verdict = run3.check_file(p)
        wj = dec.witness_json(el, sc, w, {'keccak256': kh, 'sha256': shh})
        rules, readable = degenerate_rules(law, wj)
        out[lid] = {'codes': codes, 'sy_hit': val, 'bend2': checker.get('marker'), 'bendtt': verdict,
                    'degenerate_rules': sorted(rules), 'readable': readable,
                    'prefix': [s['action'] for s in wj['prefix']], 'x': wj['x']['action'], 'witness': wj}
        print(lid, json.dumps({k: v for k, v in out[lid].items() if k != 'witness'}), flush=True)
finally:
    ctx.close()
(scratch / 'sym_rep.json').write_text(json.dumps(out, indent=1, sort_keys=True) + '\n')
