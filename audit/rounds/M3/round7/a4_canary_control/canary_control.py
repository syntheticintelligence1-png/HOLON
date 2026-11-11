"""A4 canary control: holon.audit.vacuity's unsatisfiable_premise canary appends a second pin `k.version == <bx+1>`
to a pinned linked-codec law and counts it detected when no inhabitant is generated. Control: the same law with a
second pin equal to its own (`k.version == <bx>`, satisfiable) and with no second pin; does the generator refuse those
too? If the satisfiable control is refused the same way, the canary's detection does not show sensitivity to
unsatisfiability."""
import json, sys, copy
from pathlib import Path
sys.path.insert(0, '.')
from holon.codecrun import inhabitant_witness
from holon.audit.vacuity import _field_term
lid = 'L_par_cc_BatchCache_createBatchHeaderWithSequencerSetHash_enc_sol_v2_pinned'
law = json.loads(Path(f'laws/M3/{lid}.json').read_text())
doc = json.loads(Path(law['facts']).read_text())
cand = None
for p in law['statement'].get('assume') or []:
    a, b = p.get('eq') or [None, None]
    if _field_term(a) and isinstance(b, dict) and isinstance(b.get('bytes'), str) and len(b['bytes']) == 4:
        cand = (a, b['bytes']); break
term, bx = cand
out = {}
for tag, val in (('no_second_pin', None), ('second_pin_same_value_satisfiable', bx),
                 ('second_pin_next_value_unsatisfiable', '0x%02x' % ((int(bx, 16) + 1) % 256))):
    l2 = copy.deepcopy(law)
    if val is not None:
        l2['statement']['assume'].append({'eq': [copy.deepcopy(term), {'bytes': val}]})
    try:
        w = inhabitant_witness(l2, 'linked', doc)
        out[tag] = {'generated': True, 'witness_fields': sorted(w)[:4]}
    except Exception as e:  # noqa: BLE001
        out[tag] = {'generated': False, 'error': f'{type(e).__name__}: {str(e)[:300]}'}
print(json.dumps({'law': lid, 'pin': [term, bx], 'results': out}, indent=1))
