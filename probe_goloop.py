import sys, json
from pathlib import Path
sys.path.insert(0, ".")
from holon.gen import goloop
doc = json.load(open("/tmp/claude-0/-home-user-HOLON/13f9caff-002b-57ac-9895-57449b3592cb/scratchpad/i67/m3out/morph_blob_go.go.extracted.json"))
fns = doc["go"]["functions"]
for fid in ("morph-l2/common/batch.RetrieveBlobBytes", "morph-l2/common/blob.RetrieveBlobBytes"):
    f = fns[fid]
    blob_param = f["params"][0]["name"]
    lb = f["loop_bodies"][0]
    try:
        shape = goloop._shape(lb, blob_param)
        print(fid.split(".")[0].split("/")[-1], fid.split(".")[-1], "shape:", {k: shape[k] for k in ("limit","cont","trip","thr","panics")})
    except goloop.LoopShapeError as e:
        print(fid, "SHAPE ERROR:", e)
        continue
    out = Path(f"/tmp/claude-0/-home-user-HOLON/13f9caff-002b-57ac-9895-57449b3592cb/scratchpad/i67/gen/{fid.split(".")[0].split("/")[-1]}")
    out.mkdir(parents=True, exist_ok=True)
    (out/"M.bend").write_text(goloop.model_text(lb, blob_param))
    (out/"LAWS.bend").write_text(goloop.counter_law_text())
    (out/"PROOF.bend").write_text(goloop.proof_text())
    print("  wrote", out)
