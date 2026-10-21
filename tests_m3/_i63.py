"""I63 instrument (= I28a: deployment history and the on-chain cross-check), fixed at the I63 prereg (BUILD_PLAN §0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_history.py, rules H1-H8. This module writes those rules out a second
time, independently of holon/, so that the tests can decide what holon must write and decide the predictions
themselves. It reads the history sidecar (spec/M3/lib/history.json), config/holon.json (the pinned solc and Solidity
dependencies), the target repository's git objects, I59's index, and the committed snapshot (receipts and code); nothing
here imports holon/.

  refs(side, repo)            H1: the sidecar's pinned tags, checked against the repository, by commit time; then head
  build(side, cfg, tree, c)   H2: one compiler configuration's build of the contract at a materialized ref
  code_identity(code, ranges) H2: the runtime code, immutable and link ranges zeroed, CBOR metadata stripped
  reinitializers(ast, side)   H3: the contract's initializer functions and their versions
  layout_entries(layout)      H4: the storage layout as entries with canonical type signatures
  layout_diff(a, b)           H5: what an upgrade from layout a to layout b does to every entry
  in_flight(a, b, diff)       H6: what the new layout reads of the old state
  basis(root)                 H1-H6 over every ref: the versions and the migration edges (spec/M3/lib/history_basis.json)
  match(basis, code)          H7: the versions and configurations whose build a deployed runtime code equals
  receipt_hashes(index)       H7: I59's sha256 of every upgrade transaction's canonical receipt
  decode(side, receipt, i)    H7: the proxy's Upgraded (at log index i), Initialized and AdminChanged logs of a receipt
  timeline(root, basis)       H8, from the committed receipts (checked against I59) and code files

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
NO_MATCH = "no version's build matches"
SEVERAL = "builds of several versions match"


class InstrumentError(RuntimeError):
    """An input the rules refuse (a moved tag, an unpinned dependency tree, a receipt I59 did not fetch)."""


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git(repo: str, *args: str, binary: bool = False):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, check=True)
    return p.stdout if binary else p.stdout.decode()


# ---------------------------------------------------------------------------------------------------- H1 refs
def refs(side: dict, repo: str) -> list:
    """The sidecar's pinned tags: each must exist, peel to its pinned commit and hold the contract's source unit (else
    InstrumentError); ordered by the commit's committer time, then by tag name; then the head commit as ref "head"."""
    src = side["contract"]["source"]
    out = []
    for t, pinned in sorted(side["tags"].items()):
        p = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "-q", f"{t}^{{commit}}"], capture_output=True,
                           text=True)
        if p.returncode != 0 or p.stdout.strip() != pinned:
            raise InstrumentError(f"tag {t} is missing or no longer at its pinned commit {pinned}")
        if subprocess.run(["git", "-C", repo, "cat-file", "-e", f"{pinned}:{src}"], capture_output=True).returncode:
            raise InstrumentError(f"tag {t}: its tree has no {src}")
        out.append({"ref": t, "commit": pinned, "time": int(git(repo, "show", "-s", "--format=%ct", pinned).strip())})
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
def deps_tree_sha256(nm: Path) -> str:
    """sha256 over (relative path, file sha256) of every file under nm, sorted; .git directories and npm's
    .package-lock.json skipped (config replay.sol_deps_sha256's definition)."""
    h = hashlib.sha256()
    files = sorted(f for f in nm.rglob("*")
                   if f.is_file() and ".git" not in f.relative_to(nm).parts and f.name != ".package-lock.json")
    for f in files:
        h.update(f"{f.relative_to(nm).as_posix()}\0{sha256_bytes(f.read_bytes())}\n".encode())
    return h.hexdigest()


def check_toolchain(cfg: dict) -> None:
    """The pinned solc (replay.solc_sha256) and the pinned dependency tree (replay.sol_deps_sha256), else
    InstrumentError."""
    rep = cfg["replay"]
    if sha256_bytes(Path(rep["solc"]).read_bytes()) != rep["solc_sha256"]:
        raise InstrumentError("the pinned solc does not hash to config replay.solc_sha256")
    nm = Path(rep["sol_deps"]) / "node_modules"
    if not nm.is_dir() or deps_tree_sha256(nm) != rep["sol_deps_sha256"]:
        raise InstrumentError("<replay.sol_deps>/node_modules is missing or not config replay.sol_deps_sha256")


def build(side: dict, cfg: dict, tree: Path, conf: dict) -> dict:
    """One configuration's build: {"code": hex, "ranges": [[start, length]..], "layout": storageLayout, "ast": unit
    AST, "unit_text": the unit's source, "declared_in": {astId: contract}}. solc is config replay.solc,
    --standard-json, base path the tree, include path <replay.sol_deps>/node_modules."""
    rep = cfg["replay"]
    unit, name = side["contract"]["source"], side["contract"]["name"]
    settings = {"evmVersion": conf["evm_version"], "optimizer": {"enabled": True, "runs": int(conf["optimizer_runs"])},
                "metadata": {"bytecodeHash": conf["bytecode_hash"]},
                "outputSelection": {unit: {name: ["evm.deployedBytecode.object",
                                                  "evm.deployedBytecode.immutableReferences",
                                                  "evm.deployedBytecode.linkReferences", "storageLayout"]},
                                    "*": {"": ["ast"]}}}
    text = (tree / unit).read_text(encoding="utf-8")
    inp = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}}, "settings": settings})
    cmd = [rep["solc"], "--standard-json", "--base-path", ".", "--include-path",
           str(Path(rep["sol_deps"]) / "node_modules")]
    p = subprocess.run(cmd, input=inp, capture_output=True, text=True, cwd=str(tree), timeout=7200)
    out = json.loads(p.stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise RuntimeError("; ".join((e.get("formattedMessage") or e["message"])[:300] for e in errs[:3]))
    c = out["contracts"][unit][name]
    d = c["evm"]["deployedBytecode"]
    ranges = [[r["start"], r["length"]] for refs_ in (d.get("immutableReferences") or {}).values() for r in refs_]
    ranges += [[r["start"], r["length"]] for f in (d.get("linkReferences") or {}).values()
               for refs_ in f.values() for r in refs_]
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
    `initializer` (version 1) or `reinitializer(k)`: [{"name", "version", "line"}], by version then name. A
    reinitializer whose argument is not one integer literal makes the ref an extraction error (ValueError)."""
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
                        raise ValueError(f"{f['name']}: reinitializer's argument is not one integer literal")
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


def _meets(x: dict, y: dict) -> bool:
    s0, s1 = _span(x)
    t0, t1 = _span(y)
    return s0 < t1 and t0 < s1


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
        for ko in sorted(ka):
            if _gap(ka[ko]) or ko in same_pos:
                continue
            if _meets(kb[k], ka[ko]):
                overlap.append({"contract": k[0], "label": k[1], "meets": {"contract": ko[0], "label": ko[1]}})
    compatible = not moved and all(r["kind"] == "struct_extended" for r in retyped) and not overlap
    return {"persisted": persisted, "moved": moved, "retyped": retyped, "added": added, "removed": removed,
            "gap_resized": gap_resized, "overlap": overlap, "compatible": compatible}


# ---------------------------------------------------------------------------------------------------- H6 basis
def in_flight(a: list, b: list, diff: dict) -> list:
    """H6: every entry of b that is not a __gap and whose byte span meets the span of an entry of a that is not a
    __gap: {"entry": "<contract>.<label>", "kind": "unchanged" (persisted) | "retyped" (same contract, label and
    position, another type) | "reinterpreted" (any other entry), "reads": the entries of a it meets, sorted}, sorted
    by entry."""
    persisted = {(p["contract"], p["label"]) for p in diff["persisted"]}
    retyped = {(r["contract"], r["label"]) for r in diff["retyped"]}
    out = []
    for y in b:
        if _gap(y):
            continue
        reads = sorted(f"{x['contract']}.{x['label']}" for x in a if not _gap(x) and _meets(y, x))
        if not reads:
            continue
        k = (y["contract"], y["label"])
        kind = "unchanged" if k in persisted else "retyped" if k in retyped else "reinterpreted"
        out.append({"entry": f"{k[0]}.{k[1]}", "kind": kind, "reads": reads})
    return sorted(out, key=lambda r: r["entry"])


def basis(root: Path = ROOT, log=None) -> dict:
    """H1-H6 over every ref: the refs, each ref's builds under every configuration, the versions (maximal runs of
    consecutive refs whose code identity under the sidecar's version_config is equal), each version's
    reinitializers and layout, and the migration edges between consecutive versions."""
    side = load(root / "spec" / "M3" / "lib" / "history.json")
    cfg = load(root / "config" / "holon.json")
    check_toolchain(cfg)
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
                      "in_flight": in_flight(v["layout"], w["layout"], diff)})
    return {"basis_version": "holon-history-basis/0.2", "sidecar_sha256": sha256_bytes(SIDECAR.read_bytes()),
            "target": side["target"], "contract": side["contract"], "version_config": vconf,
            "refs": [{k: it[k] for k in ("ref", "commit", "time", "error")} | {"builds": it.get("builds", {})}
                     for it in per_ref],
            "versions": versions, "edges": edges}


# ---------------------------------------------------------------------------------------------------- H7 on chain
def match(bas: dict, code: bytes) -> list:
    """Every (version, configuration) whose build equals the deployed runtime code: the deployed code takes that
    build's ranges (zeroed) and loses its CBOR metadata, and its sha256 must be the build's identity sha256. In
    version order, then by configuration name."""
    hits = []
    for v in bas["versions"]:
        for cname, b in sorted(v["code"].items()):
            if sha256_bytes(code_identity(code, b["ranges"])) == b["sha256"]:
                hits.append({"version": v["id"], "config": cname})
    return hits


def upgrade_items(side: dict, index: dict) -> list:
    """I59's Upgraded log items: [(block, log_index, tx)] by block then log index."""
    topic = side["events"]["Upgraded"]
    return sorted((it["block"], it["log_index"], it["tx"]) for it in index["items"]
                  if it.get("kind") == "log" and it.get("topic") == topic)


def receipt_hashes(index: dict) -> dict:
    """{tx: the sha256 of I59's canonical receipt bytes} for every receipt item of I59's index."""
    return {it["tx"]: it["sha256"] for it in index["items"] if it.get("kind") == "receipt"}


def _words(data: str) -> list:
    h = data[2:] if data.startswith("0x") else data
    return [h[i:i + 64] for i in range(0, len(h), 64)]


def _addr(word: str) -> str:
    return "0x" + word[-40:].lower()


def decode(side: dict, receipt: dict, log_index: int) -> dict:
    """H7 from one canonical receipt: of the logs the proxy emitted (log address == the sidecar's proxy), in log-index
    order, the Upgraded log at log_index (topic 1: the implementation), every Initialized log (the version, the first
    data word) and every AdminChanged log (previous and new admin, a data word each); and the receipt's sender and
    contractAddress."""
    proxy = side["proxy"]["address"].lower()
    ev = {k: v.lower() for k, v in side["events"].items()}
    logs = sorted((lg for lg in receipt["logs"] if lg["address"].lower() == proxy),
                  key=lambda lg: int(lg["logIndex"], 16))
    up = [lg for lg in logs if int(lg["logIndex"], 16) == log_index and lg["topics"][0].lower() == ev["Upgraded"]]
    if len(up) != 1:
        raise InstrumentError(f"{receipt['transactionHash']}: no Upgraded log of the proxy at log index {log_index}")
    return {"implementation": _addr(up[0]["topics"][1]),
            "initialized": [int(_words(lg["data"])[0], 16) for lg in logs
                            if lg["topics"][0].lower() == ev["Initialized"]],
            "admin_changed": [{"previous": _addr(_words(lg["data"])[0]), "new": _addr(_words(lg["data"])[1])}
                              for lg in logs if lg["topics"][0].lower() == ev["AdminChanged"]],
            "from": receipt["from"].lower(),
            "contract_address": (receipt.get("contractAddress") or "").lower() or None}


def snapshot(root: Path = ROOT) -> list:
    """Every upgrade of I59's index, decoded from the committed receipt (whose sha256 must be I59's receipt hash for
    that transaction, else InstrumentError), with the committed code of its implementation: [{"block", "log_index",
    "tx", **decode(..), "code": bytes}]."""
    side = load(root / "spec" / "M3" / "lib" / "history.json")
    index = load(root / side["upgrades"]["path"])
    hashes = receipt_hashes(index)
    out = []
    for block, log_index, tx in upgrade_items(side, index):
        raw = (root / side["outputs"]["receipts"] / f"{tx}.json").read_bytes()
        if sha256_bytes(raw) != hashes.get(tx):
            raise InstrumentError(f"receipts/{tx}.json is not I59's receipt (sha256 {sha256_bytes(raw)})")
        d = decode(side, json.loads(raw), log_index)
        code = bytes.fromhex((root / side["outputs"]["code"] / f"{d['implementation']}.hex").read_text().strip())
        out.append({"block": block, "log_index": log_index, "tx": tx, **d, "code": code})
    return out


# ---------------------------------------------------------------------------------------------------- H8 timeline
def timeline(root: Path = ROOT, bas: dict | None = None) -> dict:
    """H8 over the snapshot: per upgrade its matches, its version (the one version every match names, else null), its
    expected Initialized versions (the reinitializer versions of its version above the baseline: the larger of the top
    reinitializer version of the previous matched upgrade's version and the highest Initialized version logged by any
    earlier upgrade transaction, 0 when neither exists; null when its version is null), its logged Initialized
    versions (sorted) and consistent (expected == logged, false when expected is null); downgrades; coverage debt;
    never-deployed versions."""
    bas = bas if bas is not None else load(BASIS)
    order = {v["id"]: i for i, v in enumerate(bas["versions"])}
    reinit = {v["id"]: [x["version"] for x in v["reinitializers"]] for v in bas["versions"]}
    ups, prev, logged_max, seen = [], None, 0, []
    for u in snapshot(root):
        m = match(bas, u["code"])
        vs = sorted({x["version"] for x in m}, key=order.get)
        ver = vs[0] if len(vs) == 1 else None
        exp = None
        if ver is not None:
            base = max(max(reinit[prev], default=0) if prev else 0, logged_max)
            exp = sorted(k for k in reinit[ver] if k > base)
        got = sorted(u["initialized"])
        ups.append({"block": u["block"], "tx": u["tx"], "implementation": u["implementation"], "matches": m,
                    "version": ver, "expected_initialized": exp, "initialized": got,
                    "consistent": exp is not None and exp == got})
        logged_max = max([logged_max] + got)
        if ver is not None:
            seen.append((u["block"], ver))
            prev = ver
    downs = []
    for i, (blk, ver) in enumerate(seen):
        later_than = [v for _, v in seen[:i] if order[v] > order[ver]]
        if later_than:
            downs.append({"block": blk, "version": ver, "after": max(later_than, key=lambda v: order[v])})
    debt = [{"block": u["block"], "implementation": u["implementation"], "reason": NO_MATCH}
            for u in ups if not u["matches"]] + \
           [{"block": u["block"], "implementation": u["implementation"], "reason": SEVERAL}
            for u in ups if u["matches"] and u["version"] is None]
    named = {m["version"] for u in ups for m in u["matches"]}
    return {"upgrades": ups, "downgrades": downs, "coverage_debt": sorted(debt, key=lambda d: d["block"]),
            "never_deployed": [v["id"] for v in bas["versions"] if v["id"] not in named]}


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
