"""I63 instrument (= I28a: deployment history and the on-chain cross-check), fixed at the I63 prereg (BUILD_PLAN §0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_history.py, rules H1-H8. This module writes those rules out a second
time, independently of holon/, so that the tests can decide what holon must write. It reads the history sidecar
(spec/M3/lib/history.json), config/holon.json (the pinned solc and the Solidity dependencies) and the target
repository's git objects; nothing here imports holon/.

  refs(side, repo)            H1: every tag whose tree holds the contract's source, by commit time, then the head
  build(side, cfg, tree, c)   H2: one compiler configuration's build of the contract at a materialized ref
  code_identity(build)        H2: the runtime code, immutable and link ranges zeroed, CBOR metadata stripped
  reinitializers(ast, side)   H3: the contract's initializer functions and their versions
  layout_entries(layout)      H4: the storage layout as entries with canonical type signatures
  layout_diff(a, b)           H5: what an upgrade from layout a to layout b does to every entry
  basis(root)                 H1-H6 over every ref: the versions and the migration edges (spec/M3/lib/history_basis.json)
  match(basis, code)          H7: the versions and configurations whose build a deployed runtime code equals

  python -m tests_m3._i63 --write   recompute spec/M3/lib/history_basis.json (only at the prereg)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ROOT / "spec" / "M3" / "lib" / "history.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "history_basis.json"


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git(repo: str, *args: str, binary: bool = False):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True)
    return p.stdout if binary else p.stdout.decode()


# ---------------------------------------------------------------------------------------------------- H1 refs
def refs(side: dict, repo: str) -> list:
    """Every tag of the repository whose commit's tree holds the contract's source, ordered by the commit's committer
    time, then by tag name; then the head commit (the sidecar's pinned commit) as ref "head"."""
    src = side["contract"]["source"]
    out = []
    for t in sorted(git(repo, "tag", "-l").split()):
        c = git(repo, "rev-parse", f"{t}^{{commit}}").strip()
        has = subprocess.run(["git", "-C", repo, "cat-file", "-e", f"{c}:{src}"], capture_output=True).returncode == 0
        if not has:
            continue
        out.append({"ref": t, "commit": c, "time": int(git(repo, "show", "-s", "--format=%ct", c).strip())})
    out.sort(key=lambda r: (r["time"], r["ref"]))
    head = side["head"]
    out.append({"ref": "head", "commit": head, "time": int(git(repo, "show", "-s", "--format=%ct", head).strip())})
    return out


def materialize(repo: str, commit: str, dest: Path, paths: list) -> None:
    """The commit's tree under the sidecar's build paths, written under dest (git archive: no checkout, no worktree)."""
    data = git(repo, "archive", "--format=tar", commit, "--", *paths, binary=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(dest, filter="data")


# ---------------------------------------------------------------------------------------------------- H2 builds
def build(side: dict, cfg: dict, tree: Path, conf: dict) -> dict:
    """One configuration's build: {"code": hex, "ranges": [[start, length]..], "layout": storageLayout, "ast": unit
    AST, "unit_text": the unit's source}. solc is config replay.solc (its sha256 must be replay.solc_sha256),
    --standard-json, base path the tree, include path <replay.sol_deps>/node_modules."""
    rep = cfg["replay"]
    solc = rep["solc"]
    if sha256_bytes(Path(solc).read_bytes()) != rep["solc_sha256"]:
        raise RuntimeError("the pinned solc does not hash to config replay.solc_sha256")
    unit, name = side["contract"]["source"], side["contract"]["name"]
    settings = {"evmVersion": conf["evm_version"], "optimizer": {"enabled": True, "runs": int(conf["optimizer_runs"])},
                "metadata": {"bytecodeHash": conf["bytecode_hash"]},
                "outputSelection": {unit: {name: ["evm.deployedBytecode.object",
                                                  "evm.deployedBytecode.immutableReferences",
                                                  "evm.deployedBytecode.linkReferences", "storageLayout"]},
                                    "*": {"": ["ast"]}}}
    text = (tree / unit).read_text(encoding="utf-8")
    inp = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}}, "settings": settings})
    cmd = [solc, "--standard-json", "--base-path", "."]
    deps = Path(rep["sol_deps"]) / "node_modules"
    if deps.is_dir():
        cmd += ["--include-path", str(deps)]
    p = subprocess.run(cmd, input=inp, capture_output=True, text=True, cwd=str(tree), timeout=7200)
    out = json.loads(p.stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise RuntimeError("; ".join((e.get("formattedMessage") or e["message"])[:300] for e in errs[:3]))
    c = out["contracts"][unit][name]
    d = c["evm"]["deployedBytecode"]
    ranges = sorted([r["start"], r["length"]] for refs_ in (d.get("immutableReferences") or {}).values()
                    for r in refs_)
    ranges += sorted([r["start"], r["length"]] for f in (d.get("linkReferences") or {}).values()
                     for refs_ in f.values() for r in refs_)
    decl = {}
    for src in out["sources"].values():
        for node in src["ast"].get("nodes", []):
            if node.get("nodeType") == "ContractDefinition":
                for v in node.get("nodes", []):
                    if v.get("nodeType") == "VariableDeclaration" and v.get("stateVariable"):
                        decl[v["id"]] = node["name"]
    return {"code": d["object"].lower(), "ranges": sorted(ranges), "layout": c["storageLayout"],
            "ast": out["sources"][unit]["ast"], "unit_text": text, "declared_in": decl}


def strip_metadata(code: bytes) -> bytes:
    """The runtime code without solc's trailing CBOR metadata: the last two bytes are the big-endian length n of the
    CBOR map before them; it is removed when 2 + n <= len(code) and the map's first byte is a CBOR map head
    (0xa0..0xb7)."""
    if len(code) < 2:
        return code
    n = int.from_bytes(code[-2:], "big")
    if 2 + n <= len(code) and n > 0 and 0xa0 <= code[-2 - n] <= 0xb7:
        return code[:-2 - n]
    return code


def code_identity(code: bytes, ranges: list) -> bytes:
    """H2: every immutable and link range zeroed, then the CBOR metadata stripped."""
    b = bytearray(code)
    for start, n in ranges:
        b[start:start + n] = bytes(min(n, max(0, len(b) - start)))
    return strip_metadata(bytes(b))


# ---------------------------------------------------------------------------------------------------- H3 initializers
def _line(text: str, offset: int) -> int:
    return text.encode("utf-8")[:offset].count(b"\n") + 1


def reinitializers(ast: dict, side: dict, text: str) -> list:
    """Every function of the contract (its own ContractDefinition, not an inherited one) that carries the modifier
    `initializer` (version 1) or `reinitializer(k)` with an integer literal k: [{"name", "version", "line"}], by
    version then name."""
    out = []
    for node in ast.get("nodes", []):
        if node.get("nodeType") != "ContractDefinition" or node.get("name") != side["contract"]["name"]:
            continue
        for f in node.get("nodes", []):
            if f.get("nodeType") != "FunctionDefinition":
                continue
            for m in f.get("modifiers", []):
                mn = (m.get("modifierName") or {}).get("name")
                if mn == "initializer":
                    k = 1
                elif mn == "reinitializer":
                    args = m.get("arguments") or []
                    if len(args) != 1 or args[0].get("nodeType") != "Literal" or args[0].get("kind") != "number":
                        continue
                    k = int(args[0]["value"], 0)
                else:
                    continue
                start = int(f["src"].split(":")[0])
                out.append({"name": f["name"], "version": k, "line": _line(text, start)})
    return sorted(out, key=lambda r: (r["version"], r["name"]))


# ---------------------------------------------------------------------------------------------------- H4 layouts
def _type_sig(types: dict, tid: str) -> dict:
    t = types[tid]
    sig = {"label": t["label"], "encoding": t["encoding"], "bytes": int(t["numberOfBytes"])}
    for k in ("key", "value", "base"):
        if k in t:
            sig[k] = _type_sig(types, t[k])
    if "members" in t:
        sig["members"] = [{"label": m["label"], "slot": int(m["slot"]), "offset": int(m["offset"]),
                           "type": _type_sig(types, m["type"])} for m in t["members"]]
    return sig


def layout_entries(layout: dict, declared_in: dict) -> list:
    """[{"contract": the declaring contract's name, "label", "slot", "offset", "bytes", "type": signature}] in
    (slot, offset) order. The declaring contract is the ContractDefinition whose state variable declaration has the
    entry's astId (solc's "contract" names the compiled contract for every entry, inherited ones included)."""
    types = layout.get("types") or {}
    out = []
    for e in layout.get("storage", []):
        sig = _type_sig(types, e["type"])
        out.append({"contract": declared_in[e["astId"]], "label": e["label"], "slot": int(e["slot"]),
                    "offset": int(e["offset"]), "bytes": sig["bytes"], "type": sig})
    return sorted(out, key=lambda e: (e["slot"], e["offset"], e["contract"], e["label"]))


def _span(e: dict) -> tuple:
    start = e["slot"] * 32 + e["offset"]
    return start, start + (e["bytes"] if e["bytes"] <= 32 else ((e["bytes"] + 31) // 32) * 32)


def _gap(e: dict) -> bool:
    return e["label"] == "__gap" and e["type"]["encoding"] == "inplace" and "base" in e["type"]


def _struct_extended(old: dict, new: dict) -> bool:
    if "members" not in old or "members" not in new or old["label"] != new["label"]:
        return False
    return len(new["members"]) > len(old["members"]) and new["members"][:len(old["members"])] == old["members"]


def _map_value_extended(old: dict, new: dict) -> bool:
    """A mapping whose value type (recursively through mapping values) is a struct extended at its end."""
    if old.get("encoding") != "mapping" or new.get("encoding") != "mapping" or old.get("key") != new.get("key"):
        return False
    ov, nv = old["value"], new["value"]
    return _struct_extended(ov, nv) or _map_value_extended(ov, nv)


def layout_diff(a: list, b: list) -> dict:
    """H5: entries are identified by (contract, label). persisted: same slot, offset and type signature; moved: other
    slot or offset; retyped: same position, other type (kind "struct_extended" for a mapping whose struct value gains
    members at its end, else "changed"); added / removed: only in b / only in a. gap_resized: a "__gap" array whose
    length changed. overlap: an entry of b that is not persisted and whose byte span meets the span of an entry of a
    that is neither a __gap nor at the same position in b. Compatible iff nothing is moved, every retyped entry is
    struct_extended, and nothing overlaps."""
    ka = {(e["contract"], e["label"]): e for e in a}
    kb = {(e["contract"], e["label"]): e for e in b}
    persisted, moved, retyped, gap_resized = [], [], [], []
    for k in sorted(set(ka) & set(kb)):
        x, y = ka[k], kb[k]
        if (x["slot"], x["offset"]) != (y["slot"], y["offset"]):
            if _gap(x) and _gap(y):
                gap_resized.append({"contract": k[0], "label": k[1], "from": [x["slot"], x["bytes"]],
                                    "to": [y["slot"], y["bytes"]]})
            else:
                moved.append({"contract": k[0], "label": k[1], "from": [x["slot"], x["offset"]],
                              "to": [y["slot"], y["offset"]]})
        elif x["type"] != y["type"]:
            if _gap(x) and _gap(y):
                gap_resized.append({"contract": k[0], "label": k[1], "from": [x["slot"], x["bytes"]],
                                    "to": [y["slot"], y["bytes"]]})
            else:
                kind = "struct_extended" if _map_value_extended(x["type"], y["type"]) else "changed"
                retyped.append({"contract": k[0], "label": k[1], "kind": kind})
        else:
            persisted.append({"contract": k[0], "label": k[1]})
    added = [{"contract": k[0], "label": k[1], "slot": kb[k]["slot"], "offset": kb[k]["offset"]}
             for k in sorted(set(kb) - set(ka))]
    removed = [{"contract": k[0], "label": k[1], "slot": ka[k]["slot"], "offset": ka[k]["offset"]}
               for k in sorted(set(ka) - set(kb))]
    same_pos = {k for k in set(ka) & set(kb) if (ka[k]["slot"], ka[k]["offset"]) == (kb[k]["slot"], kb[k]["offset"])}
    pk = {(p["contract"], p["label"]) for p in persisted}
    overlap = []
    for k in sorted(kb):
        if k in pk:
            continue
        s0, s1 = _span(kb[k])
        for ko in sorted(ka):
            if _gap(ka[ko]) or ko in same_pos:
                continue
            t0, t1 = _span(ka[ko])
            if s0 < t1 and t0 < s1:
                overlap.append({"contract": k[0], "label": k[1], "meets": {"contract": ko[0], "label": ko[1]}})
    compatible = not moved and all(r["kind"] == "struct_extended" for r in retyped) and not overlap
    return {"persisted": persisted, "moved": moved, "retyped": retyped, "added": added, "removed": removed,
            "gap_resized": gap_resized, "overlap": overlap, "compatible": compatible}


# ---------------------------------------------------------------------------------------------------- H6 basis
def basis(root: Path = ROOT, log=None) -> dict:
    """H1-H6 over every ref: the refs, each ref's builds under every configuration, the versions (maximal runs of
    consecutive refs whose code identity under the sidecar's version_config is equal), each version's
    reinitializers and layout, and the migration edges between consecutive versions."""
    side = load(root / "spec" / "M3" / "lib" / "history.json")
    cfg = load(root / "config" / "holon.json")
    repo = cfg["extract"]["sources"][side["target"]["repo"]]
    confs = side["compiler_configs"]
    vconf = side["version_config"]
    rs = refs(side, repo)
    per_ref = []
    with tempfile.TemporaryDirectory(prefix="i63-") as td:
        for r in rs:
            tree = Path(td) / r["commit"][:12]
            if not tree.exists():
                tree.mkdir()
                materialize(repo, r["commit"], tree, side["contract"]["build_paths"])
            item = {"ref": r["ref"], "commit": r["commit"], "time": r["time"], "builds": {}}
            try:
                b0 = None
                for cname in sorted(confs):
                    b = build(side, cfg, tree, confs[cname])
                    ident = code_identity(bytes.fromhex(b["code"]), b["ranges"])
                    item["builds"][cname] = {"sha256": sha256_bytes(ident), "length": len(bytes.fromhex(b["code"])),
                                             "ranges": b["ranges"]}
                    if cname == vconf:
                        b0 = b
                item["layout"] = layout_entries(b0["layout"], b0["declared_in"])
                item["reinitializers"] = reinitializers(b0["ast"], side, b0["unit_text"])
                item["source_sha256"] = sha256_bytes(b0["unit_text"].encode("utf-8"))
                item["error"] = None
            except (RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as e:
                item["error"] = str(e)[:500]
            per_ref.append(item)
            if log:
                log(f"{r['ref']}: {'error ' + item['error'] if item['error'] else item['builds'][vconf]['sha256'][:12]}")
    versions = []
    for it in per_ref:
        if it["error"] is not None:
            continue
        key = it["builds"][vconf]["sha256"]
        if versions and versions[-1]["code"][vconf]["sha256"] == key:
            versions[-1]["refs"].append(it["ref"])
            continue
        versions.append({"id": f"V{len(versions) + 1}", "refs": [it["ref"]], "commit": it["commit"],
                         "time": it["time"], "code": it["builds"], "source_sha256": it["source_sha256"],
                         "layout": it["layout"],
                         "layout_sha256": sha256_bytes(json.dumps(it["layout"], sort_keys=True).encode()),
                         "reinitializers": it["reinitializers"]})
    edges = []
    for v, w in zip(versions, versions[1:]):
        top = max((x["version"] for x in v["reinitializers"]), default=0)
        diff = layout_diff(v["layout"], w["layout"])
        edges.append({"from": v["id"], "to": w["id"],
                      "introduced": [x for x in w["reinitializers"] if x["version"] > top],
                      "layout": diff, "compatible": diff["compatible"],
                      "in_flight": sorted(f"{p['contract']}.{p['label']}" for p in diff["persisted"])})
    return {"basis_version": "holon-history-basis/0.1", "sidecar_sha256": sha256_bytes(SIDECAR.read_bytes()),
            "target": side["target"], "contract": side["contract"], "version_config": vconf,
            "refs": [{k: it[k] for k in ("ref", "commit", "time", "error")} | {"builds": it.get("builds", {})}
                     for it in per_ref],
            "versions": versions, "edges": edges}


# ---------------------------------------------------------------------------------------------------- H7 matching
def match(bas: dict, code: bytes) -> list:
    """Every (version, configuration) whose build equals the deployed runtime code: the deployed code takes that
    build's ranges (zeroed) and loses its CBOR metadata, and its sha256 must be the build's identity sha256."""
    hits = []
    for v in bas["versions"]:
        for cname, b in sorted(v["code"].items()):
            if sha256_bytes(code_identity(code, b["ranges"])) == b["sha256"]:
                hits.append({"version": v["id"], "config": cname})
    return hits


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i63")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    doc = basis(log=lambda s: print(s, flush=True))
    text = json.dumps(doc, indent=1, sort_keys=True) + "\n"
    if a.write:
        BASIS.write_text(text, encoding="utf-8")
        print(f"wrote {BASIS.relative_to(ROOT)}")
    else:
        print(text[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
