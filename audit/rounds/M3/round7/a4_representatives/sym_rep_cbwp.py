"""A4 representative for L_sym_sentinel_Rollup_batchDataStore_originTimestamp_commitBatchWithProof_366 (D1): prefix =
one successful commitBatch of batch 1 at T0 (the commitBatch law's own inhabitant step); x = commitBatchWithProof of
batch 2 on batch 1 at T0 + 21 (past the 20 s rollup delay of batch 1's origin time), its _batchHeader the header the
commit writes, its verifier call answered as the committed inhabitant's (ok, empty return) with batch 2's public input.
The law's own generator (holon.symd) and both kernels check it. Writes only under the scratch directory."""
import json, sys, os, copy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[5]   # the repository root (the run used the auditor's checkout of the target)
sys.path.insert(0, str(ROOT))
scratch = Path(sys.argv[1])
os.environ['HOLON_BUILD_DIR'] = str(scratch / 'build')
from holon.keccak import keccak256
from holon.symd import run as SR
from holon.symd import proofs as SP
from holon.sorts import run3
from holon.undo import proofs as UP
from holon.audit.vacuity import degenerate_rules
US = SR.US
lid = 'L_sym_sentinel_Rollup_batchDataStore_originTimestamp_commitBatchWithProof_366'
rec = json.loads((ROOT / f'results/M3/{lid}.json').read_text())
law = json.loads((ROOT / f'laws/M3/{lid}.json').read_text())
x0 = rec['non_vacuity']['witness']['x']
c1 = json.loads((ROOT / 'results/M3/L_sym_sentinel_Rollup_batchDataStore_originTimestamp_commitBatch_366.json').read_text())['non_vacuity']['witness']['x']
fw = json.loads((ROOT / 'results/M3/L_fact_kernel_Rollup_commitState_committedBatches_blobhash.json').read_text())['non_vacuity']['witness']
B1 = fw['prefix'][1]['args']['_batchHeader']
b1 = bytes.fromhex(B1[2:])
h1 = keccak256(b1)
data_hash = bytes.fromhex('6bd2dd6bd408cbee33429358bf24fdc64612fbf8b1b4db604518f40ffd34b607')
zvh = bytes.fromhex('010657f37554c781402a22917dee2f75def7ab966d7b770905398eba3c444014')
w32 = lambda n: n.to_bytes(32, 'big')
b2 = bytes([0]) + (2).to_bytes(8, 'big') + bytes(8) + bytes(8) + data_hash + zvh + w32(1) + w32(2) + w32(0) + w32(0) + h1
assert len(b2) == 249
pi = keccak256((0xcf55).to_bytes(8, 'big') + w32(1) + w32(2) + w32(0) + w32(0) + data_hash + zvh)
vdata = '0x2c09a848' + w32(0).hex() + w32(2).hex() + w32(0x80).hex() + pi.hex() + w32(10).hex() + bytes(32).hex()
x2 = copy.deepcopy(x0)
x2['args']['_batchHeader'] = '0x' + b2.hex()
bdi = x2['args']['batchDataInput']
bdi['parentBatchHeader'] = B1
bdi['prevStateRoot'], bdi['postStateRoot'] = 1, 2
x2['env']['block.timestamp'] = int(c1['env']['block.timestamp']) + 21
x2['env']['calls'] = [x0['env']['calls'][0], {"to": x0['env']['calls'][1]['to'], "data": vdata, "ok": True, "ret": "0x"}]
w = {"prefix": [run3.step_of_json(copy.deepcopy(c1))], "x": run3.step_of_json(x2)}
ctx = SR.Ctx('M3', ROOT, None, scratch / 'gen', scratch / 'out', log=lambda *a, **k: print(*a, file=sys.stderr))
dec = SR.Decider(ctx)
try:
    doc_rel = ctx.rc.derivation[lid]['facts']
    sc = ctx.sec(doc_rel)
    el = next(e for e in sc.elements if e['law_id'] == lid)
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
    (nd / 'LAWS.bend').write_text(SP.inhabitant_law(law, n, sh, mi, si, sc.hashes), encoding='utf-8')
    p = nd / 'PROOF.bend'
    p.write_text(SP.inhabitant_proof(law, n, mi, si, './LAWS.bend', sc.hashes, [m.act(x) for x in w['prefix']], states,
                                     dec.values(el, w, m), {'keccak256': kh, 'sha256': shh}, UP.Lit(sc.recs, sc.mine)),
                 encoding='utf-8')
    checker, verdict = run3.check_file(p)
    wj = dec.witness_json(el, sc, w, {'keccak256': kh, 'sha256': shh})
    rules, readable = degenerate_rules(law, wj)
    res = {'codes': codes, 'sy_hit': val, 'bend2': checker.get('marker'), 'bendtt': verdict,
           'degenerate_rules': sorted(rules), 'readable': readable, 'prefix': [s['action'] for s in wj['prefix']],
           'x': wj['x']['action'], 'witness': wj}
    print(lid, json.dumps({k: v for k, v in res.items() if k != 'witness'}), flush=True)
    (scratch / 'sym_rep_cbwp.json').write_text(json.dumps({lid: res}, indent=1, sort_keys=True) + '\n')
finally:
    ctx.close()
