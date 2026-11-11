"""A1 follow-up for m01/m02: are the queue and messenger mutants visible to HOLON's own bundle extraction path?
holon bundle extract (holon/bundle/extract.py build) calls holon.frontends.solidity.extract_document(sidecar, path, root,
source) with the generated member sidecar, never holon extract solidity (whose load_sidecar refuses a sidecar whose output
does not end .extracted.json). Here: that same call, with the committed generated sidecar, on (1) the unmutated scratch
clone (it must reproduce the committed document's content) and (2) the clone with the mutant planted (git told to treat the
file as unchanged, as holon audit mutation does). Prints whether the content (extraction inputs' hashes aside) changes."""
import json, subprocess, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); src = Path(sys.argv[2]); spec = json.loads(Path(sys.argv[3]).read_text())
sys.path.insert(0, str(ROOT))
from holon.frontends.solidity import extract_document
from holon.audit.mutation import content, diff_paths, changed_names
docs = {"contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol": "queue",
        "contracts/contracts/l1/L1CrossDomainMessenger.sol": "messenger"}
out = {}
def extract(member):
    sp = ROOT / f"gen/M3/bundle/sidecars/{member}.json"
    sc = json.loads(sp.read_text())
    return extract_document(sc, sp, ROOT, str(src))
for m in spec["mutations"]:
    if m["file"] not in docs:
        continue
    member = docs[m["file"]]
    committed = json.loads((ROOT / f"gen/M3/bundle/documents/{member}.json").read_text())
    base = extract(member)
    p = src / m["file"]
    text = p.read_text()
    lines = text.splitlines(keepends=True)
    ln = lines[m["edit"]["line"] - 1]
    assert ln.count(m["edit"]["old"]) == 1
    lines[m["edit"]["line"] - 1] = ln.replace(m["edit"]["old"], m["edit"]["new"])
    p.write_text("".join(lines))
    subprocess.run(["git", "-C", str(src), "update-index", "--assume-unchanged", "--", m["file"]], check=True)
    try:
        mut = extract(member)
    finally:
        p.write_text(text)
        subprocess.run(["git", "-C", str(src), "update-index", "--no-assume-unchanged", "--", m["file"]], check=True)
    b, c, x = content(base), content(committed), content(mut)
    # the sidecar path/sha in extraction.sidecar is written by holon bundle extract after extract_document
    for d in (b, c, x):
        (d.get("extraction") or {}).pop("sidecar", None)
    out[m["id"]] = {"member": member, "baseline_reproduces_committed_content": b == c,
                    "baseline_diff_paths": diff_paths(c, b) if b != c else [],
                    "mutant_content_changes": x != b, "paths": diff_paths(b, x), "names": sorted(changed_names(b, x))}
print(json.dumps(out, indent=1))
