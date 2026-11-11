"""A7 t1 without the full gate: in a git clone of the target (HEAD = the target), append a contradictory second version
pin to the PROVED L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned (its premises become unsatisfiable: a vacuous law),
re-hash it into laws/M3/REGISTRY.json and its result record consistently, then run G2's own two components on the
tampered tree: holon.mpipeline.check_registry_multi (G2's registry check) and holon.statement_diff.tie_problems (G2's
statement-change tie, with every committed laws/STATEMENT_DIFF.jsonl entry assumed accepted, a generous stand-in for scan()'s accepted entries).
The tree is restored afterwards."""
import json, sys
from pathlib import Path
T = Path(sys.argv[1]); out = Path(sys.argv[2])
sys.path.insert(0, str(T))
import holon.mpipeline as MP
from holon import ir
from holon import statement_diff as SD
LID = 'L_par_cc_BatchHeaderV1_Bytes_enc_sol_v1_pinned'
lp = T / 'laws/M3' / f'{LID}.json'; rp = T / 'laws/M3/REGISTRY.json'; recp = T / 'results/M3' / f'{LID}.json'
saved = {p: p.read_bytes() for p in (lp, rp, recp)}
res = {}
def g2_parts(tag):
    r = {}
    try:
        MP.check_registry_multi(ir.load_laws_any('M3', T), ir.load_registry('M3', T), 'M3', root=T)
        r['registry_check'] = 'passes'
    except Exception as e:  # noqa: BLE001
        r['registry_check'] = f'fails: {type(e).__name__}: {str(e)[:300]}'
    allent = [json.loads(l) for l in (T / 'laws/STATEMENT_DIFF.jsonl').read_text().splitlines() if l.strip()]
    # every committed entry assumed accepted (generous: G2 passes only scan()'s accepted ones)
    bad, note = SD.tie_problems('M3', T, {'entries': [{'entry': e, 'ok': True} for e in allent]})
    r['tie_problems'] = bad[:5]; r['tie_note'] = str(note)[:300]
    res[tag] = r
try:
    g2_parts('clean')
    law = json.loads(lp.read_text())
    pin = next(p for p in law['statement']['assume'] if p.get('eq') and p['eq'][0] == {'field': 'version', 'of': {'var': 'k'}})
    law['statement']['assume'].append({'eq': [pin['eq'][0], {'bytes': '0x02'}]})
    lp.write_text(json.dumps(law, indent=2, sort_keys=True) + '\n')
    orc = MP.O.Oracles.for_milestone('M3', T / law['facts'], T)
    h = MP.R.law_hash(law, MP.F.load(T / law['facts']), oracles=orc, root=T)
    reg = json.loads(rp.read_text()); res['old_hash'] = reg['statements'][LID]; reg['statements'][LID] = h; res['new_hash'] = h
    rp.write_text(json.dumps(reg, indent=1, sort_keys=True) + '\n')
    rec = json.loads(recp.read_text()); rec['statement_hash'] = h
    recp.write_text(json.dumps(rec, indent=1, sort_keys=True) + '\n')
    g2_parts('t1')
finally:
    for p, b in saved.items():
        p.write_bytes(b)
(out / 't1_direct.json').write_text(json.dumps(res, indent=1, sort_keys=True) + '\n')
print(json.dumps(res, indent=1))
