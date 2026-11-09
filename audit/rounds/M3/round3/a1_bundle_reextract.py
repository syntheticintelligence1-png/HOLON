"""A1, the bundle members by hand (the driver cannot re-extract them, F-M3-09): what `holon bundle extract` extracts
for a member (holon.bundle.extract.build: its generated sidecar, holon.frontends.solidity.extract_document over the
member's source), from the pinned checkout and from a scratch clone carrying one mutant; the two documents' content
compared with the extraction inputs' hashes and the sidecar reference left out. Reads the repository and the checkout,
writes only under the scratch directory given.
usage: bundle_reextract.py ROOT CHECKOUT SCRATCH SPEC"""
import copy, json, os, subprocess, sys, tempfile
from pathlib import Path
root, checkout, scratch, spec_p = map(Path, sys.argv[1:5])
sys.path.insert(0, str(root))
from holon.bundle import context, render, sha256_bytes
from holon.bundle.extract import generated_sidecar, source_for
from holon.frontends.solidity import extract_document

def content(doc):
    d = copy.deepcopy(doc)
    d.get("extraction", {}).pop("inputs", None)
    d.get("extraction", {}).pop("sidecar", None)
    return d

def diff_paths(a, b, path=""):
    if type(a) != type(b):
        return [path or "/"]
    if isinstance(a, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}/{k}")
            else:
                out += diff_paths(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list):
        if len(a) != len(b):
            return [f"{path}[len {len(a)} -> {len(b)}]"]
        out = []
        for i, (x, y) in enumerate(zip(a, b)):
            out += diff_paths(x, y, f"{path}/{i}")
        return out
    return [] if a == b else [path]

def extract(name, src_repo):
    ctx = context(root, "M3")
    repo = ctx.side["target"]["repo"]
    ctx.cfg = json.loads(json.dumps(ctx.cfg))
    ctx.cfg.setdefault("extract", {}).setdefault("sources", {})[repo] = str(src_repo)
    m = ctx.member(name)
    sc = generated_sidecar(ctx, m)
    srel = f"{ctx.out('sidecars')}/{m['name']}.json"
    sdata = render(sc)
    sp = ctx.path(srel)
    tmpd = None
    if sp.is_file() and sp.read_bytes() == sdata:
        eff = sp
    else:
        tmpd = tempfile.TemporaryDirectory(dir=scratch)
        eff = Path(tmpd.name) / sp.name
        eff.write_bytes(sdata)
    try:
        doc = extract_document(sc, eff, ctx.root, source_for(ctx, m["commit"]))
    finally:
        if tmpd:
            tmpd.cleanup()
    doc["extraction"]["sidecar"] = {"path": srel, "sha256": sha256_bytes(sdata)}
    return doc, sc["output"]

spec = json.load(open(spec_p))
clone = scratch / "morph_clone"
if not clone.is_dir():
    subprocess.run(["git", "clone", "-q", "--shared", "--no-checkout", str(checkout), str(clone)], check=True)
    head = subprocess.run(["git", "-C", str(checkout), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "-C", str(clone), "checkout", "-q", "--detach", head], check=True)
member_of = {"contracts/contracts/l1/rollup/L1MessageQueueWithGasPriceOracle.sol": "queue",
             "contracts/contracts/l1/L1CrossDomainMessenger.sol": "messenger"}
base = {}
report = {"baseline": {}, "mutants": {}}
for name in sorted(set(member_of.values())):
    doc, out = extract(name, checkout)
    committed = json.loads((root / out).read_text())
    base[name] = doc
    report["baseline"][name] = {"document": out, "reproduces_committed_bytes": render(doc) == (root / out).read_bytes(),
                                "same_content_as_committed": content(doc) == content(committed)}
for mu in spec["mutations"]:
    name = member_of[mu["file"]]
    f = clone / mu["file"]
    orig = f.read_text()
    lines = orig.splitlines(keepends=True)
    e = mu["edit"]
    ln = lines[e["line"] - 1]
    assert ln.count(e["old"]) == 1
    lines[e["line"] - 1] = ln.replace(e["old"], e["new"])
    f.write_text("".join(lines))
    subprocess.run(["git", "-C", str(clone), "update-index", "--assume-unchanged", "--", mu["file"]], check=True)
    try:
        doc, _ = extract(name, clone)
        paths = diff_paths(content(base[name]), content(doc))
        report["mutants"][mu["id"]] = {"member": name, "content_changed": bool(paths), "paths": paths[:25],
                                       "n_paths": len(paths)}
    except Exception as ex:  # reported, never skipped
        report["mutants"][mu["id"]] = {"member": name, "error": f"{type(ex).__name__}: {str(ex)[:500]}"}
    finally:
        f.write_text(orig)
        subprocess.run(["git", "-C", str(clone), "update-index", "--no-assume-unchanged", "--", mu["file"]], check=True)
print(json.dumps(report, indent=1, sort_keys=True))
