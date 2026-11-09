"""m05 offline: holon.gox.basis.round_trips on the committed go03 document, and on the same document with the one
change the m05 mutant makes to the extraction (HeightFromBlockContextBytes reads 8 bytes at offset 1, not 0)."""
import copy, json, sys
sys.path.insert(0, sys.argv[1])
from holon.gox import basis as B
doc = json.load(open(sys.argv[1] + "/spec/M3/facts/morph_go03.go.extracted.json"))
class Cx:  # the attributes round_trips reads
    pass
def run(d):
    cx = Cx(); cx.doc = d; cx.fns = d["go"]["functions"]
    return [(e["law_id"], e.get("reason")) for e in B.round_trips(cx)]
print("committed:", run(doc))
m = copy.deepcopy(doc)
for dec in m["go"]["codecs"]["decoders"]:
    if dec["function"].endswith("HeightFromBlockContextBytes"):
        dec["reads"][0]["offset"] = 1
print("m05 reads at 1:", run(m))
