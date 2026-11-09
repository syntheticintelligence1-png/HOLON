"""A5: the structural-key hypothesis A-keccak-structural (spec/M3/ledger.json) against the real Keccak-256 (Foundry's
cast, independent of HOLON): recompute every structural key's real slot of gen/M3/sorts/keys.json as the hypothesis
states it (b + o, then keccak256(pad32(k) ++ pad32(slot)) + offset per step, mod 2**256), compare with the file's
"real" column, and look for a collision among the structural slots and with the raw and literal slots.
Usage: python3 -I keys_check.py <cast> <keys.json>"""
import json, subprocess, sys
cast, path = sys.argv[1], sys.argv[2]
K = json.load(open(path))
M = 1 << 256
def keccak(b: bytes) -> int:
    return int(subprocess.run([cast, "keccak", "0x" + b.hex()], capture_output=True, text=True, check=True).stdout.strip(), 16)
bad, slots = [], {}
for e in K["structural"]:
    s = (int(e["b"], 16) + int(e["o"], 16)) % M
    for st in e["p"]:
        s = (keccak(int(st["k"], 16).to_bytes(32, "big") + s.to_bytes(32, "big")) + int(st["o"], 16)) % M
    if s != int(e["real"], 16):
        bad.append({"key": e, "recomputed": hex(s)})
    slots.setdefault(s, []).append(e)
raw = {int(x, 16) for x in K["raw"]}
lit = {int(x, 16) for x in K["literal"]}
coll = [hex(s) for s, es in slots.items() if len(es) > 1]
hit_raw = [hex(s) for s in slots if s in raw or s in lit]
print(json.dumps({"structural": len(K["structural"]), "distinct_real_slots": len(slots), "raw": len(raw),
                  "literal": len(lit), "recompute_mismatches": bad, "structural_collisions": coll,
                  "structural_equal_to_raw_or_literal": hit_raw, "file_collisions": K["collisions"]}, indent=1))
