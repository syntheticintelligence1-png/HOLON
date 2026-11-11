"""A5 (A-keccak-structural): recompute every structural key's real slot in gen/M3/sorts/keys.json with Foundry's cast
(cast keccak of pad32(k) ++ pad32(slot), then + offset, mod 2^256), the model assumption's own definition, independently
of holon's code; and check that no real slot equals another key's real slot, a literal slot or a raw slot."""
import json, subprocess, sys
cast = sys.argv[1]
k = json.load(open('gen/M3/sorts/keys.json'))
M = 1 << 256
def kec(hexdata):
    return int(subprocess.run([cast, 'keccak', hexdata], capture_output=True, text=True).stdout.strip(), 16)
bad, reals = [], {}
for e in k['structural']:
    slot = (int(e['b'], 16) + int(e['o'], 16)) % M
    for st in e['p']:
        slot = (kec('0x' + '%064x' % (int(st['k'], 16) % M) + '%064x' % slot) + int(st['o'], 16)) % M
    if slot != int(e['real'], 16):
        bad.append({'key': e, 'cast': '0x%064x' % slot})
    reals.setdefault(slot, []).append(e)
lit = {int(x, 16) for x in k['literal']} | {int(x, 16) for x in k['raw']}
coll = [v for s, v in reals.items() if len(v) > 1]
lit_hits = [s for s in reals if s in lit]
print(json.dumps({'structural': len(k['structural']), 'wrong_real_slots': bad[:10], 'n_wrong': len(bad),
                  'collisions_among_structural': len(coll), 'structural_equal_to_literal_or_raw': len(lit_hits),
                  'recorded_collisions': k['collisions']}, indent=1))
