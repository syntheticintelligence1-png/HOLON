"""A7 (gate evasion) in a scratch copy T of the target tree: each tamper is applied to T, the named gate checks run on
T (`python -m holon gate --milestone M3 --root T --checks ... --report ...`, T's own code), and T is restored.
  clean   no tamper
  t1      a weakened claim: one extra premise appended to a PROVED law's statement (the version pin of the V1
          cross-component codec law repeated with another value, which makes its premises unsatisfiable, i.e. the
          law vacuously true), with laws/M3/REGISTRY.json and the law's result record re-hashed consistently, so
          G2's registry check sees matching hashes
  t2      a vacuous LAWS.bend: the law declaration removed from a PROVED law's checked LAWS.bend
  t3      a REFUTED law's counter-law LAWS.bend replaced by the statement law (as if the claim were PROVED)
Prints each check's verdict and detail head."""
import json, os, shutil, subprocess, sys, re
from pathlib import Path
T = Path(sys.argv[1]); out = Path(sys.argv[2]); which = sys.argv[3:] or ['clean', 't1', 't2', 't3']
out.mkdir(parents=True, exist_ok=True)
CHECKS = os.environ.get('CLEAN_CHECKS', 'G2,G3,G11')
env = dict(os.environ); env['PYTHONPATH'] = str(T)
def gate(tag, checks=CHECKS):
    rp = out / f'gate_{tag}.json'
    p = subprocess.run([sys.executable, '-m', 'holon', 'gate', '--milestone', 'M3', '--root', str(T), '--checks', checks,
                        '--report', str(rp)], cwd=str(T), env=env, capture_output=True, text=True, timeout=3600)
    rep = json.loads(rp.read_text()) if rp.is_file() else {}
    res = {g: {'passed': c.get('passed'), 'detail': str(c.get('detail'))[:400]} for g, c in (rep.get('checks') or {}).items()
           if g in checks.split(',')}
    return {'exit': p.returncode, 'checks': res}
def backup(paths):
    return {p: p.read_bytes() for p in paths}
def restore(b):
    for p, data in b.items():
        p.write_bytes(data)
results = {}
LID = 'L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned'
REF = 'L_par_cc_BatchHeaderV0_Bytes_enc_sol_v0'          # REFUTED at C
if 'clean' in which:
    results['clean'] = gate('clean')
if 't1' in which:
    sys.path.insert(0, str(T))
    import holon.mpipeline as MP
    lp = T / 'laws/M3' / f'{LID}.json'; rp = T / 'laws/M3/REGISTRY.json'; recp = T / 'results/M3' / f'{LID}.json'
    b = backup([lp, rp, recp])
    try:
        law = json.loads(lp.read_text())
        pin = next(p for p in law['statement']['assume'] if p.get('eq') and p['eq'][0] == {'field': 'version', 'of': {'var': 'k'}})
        law['statement']['assume'].append({'eq': [pin['eq'][0], {'bytes': '0x02'}]})
        lp.write_text(json.dumps(law, indent=2, sort_keys=True) + '\n')
        orc = MP.O.Oracles.for_milestone('M3', T / law['facts'], T)
        h = MP.R.law_hash(law, MP.F.load(T / law['facts']), oracles=orc, root=T)
        reg = json.loads(rp.read_text()); old = reg['statements'][LID]; reg['statements'][LID] = h
        rp.write_text(json.dumps(reg, indent=1, sort_keys=True) + '\n')
        rec = json.loads(recp.read_text()); rec['statement_hash'] = h
        recp.write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
        results['t1'] = {'old_hash': old, 'new_hash': h, **gate('t1', os.environ.get('T1_CHECKS', 'G2,G11'))}
    finally:
        restore(b)
if 't2' in which:
    rec = json.loads((T / 'results/M3' / f'{LID}.json').read_text())
    lb = T / rec['artifacts']['laws']
    b = backup([lb])
    try:
        txt = lb.read_text()
        lb.write_text(re.sub(r'(?ms)^law [^\n]*:\n(?:  [^\n]*\n)+', '', txt))
        results['t2'] = gate('t2', 'G11')
    finally:
        restore(b)
if 't3' in which:
    rec = json.loads((T / 'results/M3' / f'{REF}.json').read_text())
    lb = T / rec['artifacts']['laws']
    b = backup([lb])
    try:
        stmt = (T / 'gen/M3/laws' / LID / 'LAWS.bend')
        txt = lb.read_text()
        lb.write_text(txt.replace('cl_' + REF.lower(), REF.lower()))
        results['t3'] = gate('t3', os.environ.get('T3_CHECKS', 'G2,G11'))
    finally:
        restore(b)
(out / 'tamper_results.json').write_text(json.dumps(results, indent=1, sort_keys=True) + '\n')
print(json.dumps(results, indent=1)[:6000])
