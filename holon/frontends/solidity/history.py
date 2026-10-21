"""Deployment history of one upgradeable contract (I63 = I28a; whitepaper §10.1 deployment history, Def 4.3 S_k/A_k and
the MIG edges; docs/HUMAN_ANSWERS.md Q18: code-derived history is the model, the on-chain timeline an independent check).

  python -m holon history extract [--check]    the versions and MIG edges, from the target repository's tags (H1-H6)
  python -m holon history fetch [--check]      the proxy's upgrades read on chain (H7; the one command that touches
                                               the network); --check verifies the snapshot offline and writes nothing
  python -m holon history timeline [--check]   every upgrade matched against the versions (H7's match, H8)
  common options: --sidecar PATH (default spec/M3/lib/history.json), --root PATH

The contract is the docstring of tests_m3/test_history.py (rules H1-H8, formats, exit codes). Everything specific to a
target comes from the sidecar: the repository, head commit and pinned tags, the contract's source unit, name and build
paths, the compiler configurations and the one that defines a version, the proxy, the event topics, the upgrade source
and its window, the RPC and the output paths. Exit codes: 0 written (or --check reproduced), 1 --check differs,
2 refused (a missing or stale input; nothing written), 3 an extraction or fetch error (nothing written).

Method, written independently of the prereg's instrument: tags are read with `git for-each-ref` and checked against the
sidecar's pins, a source unit's presence with `git ls-tree`; the CBOR tail is located from the code's end; layout diffs
and in-flight sets work on byte ranges; matches are looked up through the builds' distinct range sets. Receipts are
stored in I59's canonical form (holon.historical.store), so their sha256 must be the one I59's index recorded.
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

from .. import ExtractionError, Refused

ROOT = Path(__file__).resolve().parents[3]
SIDECAR = "spec/M3/lib/history.json"
HISTORY_VERSION = "holon-history/0.1"
ONCHAIN_VERSION = "holon-onchain/0.1"
TIMELINE_VERSION = "holon-timeline/0.1"
HEAD_REF = "head"
NO_MATCH = "no version's build matches"
SEVERAL = "builds of several versions match"


# ------------------------------------------------------------------------------------------------------ plumbing
def render(doc) -> bytes:
    """Canonical JSON: sorted keys, indent 1, a final newline."""
    return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _file_sha(p: Path) -> str:
    return _sha(Path(p).read_bytes())


def _read_json(p: Path, what: str) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(f"{what} {p}: {e}") from e


class Ctx:
    """The sidecar, the configuration and the paths every command reads."""

    def __init__(self, root: Path, sidecar: str):
        self.root = Path(root)
        self.side_rel = sidecar
        self.side_path = self.root / sidecar
        self.side = _read_json(self.side_path, "sidecar")
        self.side_sha = _file_sha(self.side_path)
        self.cfg = _read_json(self.root / "config" / "holon.json", "config")
        outs = self.side.get("outputs") or {}
        for k in ("history", "onchain", "receipts", "code", "timeline"):
            if not isinstance(outs.get(k), str):
                raise Refused(f"sidecar outputs.{k} is missing")
        self.out = outs

    def path(self, rel: str) -> Path:
        return self.root / rel

    def repo(self) -> str:
        srcs = (self.cfg.get("extract") or {}).get("sources") or {}
        repo = srcs.get(self.side["target"]["repo"])
        if not repo or not Path(repo).is_dir():
            raise Refused(f"config extract.sources has no checkout of {self.side['target']['repo']}")
        return repo


def _git(repo: str, *args: str, binary: bool = False, ok: bool = False):
    p = subprocess.run(["git", "-C", repo, *args], capture_output=True, timeout=600)
    if p.returncode != 0:
        if ok:
            return None
        raise ExtractionError(f"git {' '.join(args)}: {p.stderr.decode(errors='replace').strip()[:300]}")
    return p.stdout if binary else p.stdout.decode()


# ------------------------------------------------------------------------------------------------------ H1 refs
def list_refs(ctx: Ctx) -> list[dict]:
    """H1: the sidecar's pinned tags, each present, at its pinned commit and holding the contract's source unit (else
    Refused), by committer time then tag name; then the sidecar's head as ref "head"."""
    repo = ctx.repo()
    unit = ctx.side["contract"]["source"]
    peeled = {}
    for ln in _git(repo, "for-each-ref", "--format=%(refname:strip=2)%00%(*objectname)%00%(objectname)",
                   "refs/tags").splitlines():
        if ln:
            name, deref, obj = ln.split("\x00")
            peeled[name] = deref or obj
    found = []
    for name, pin in sorted(ctx.side["tags"].items()):
        commit = peeled.get(name)
        if commit and _git(repo, "cat-file", "-t", commit).strip() == "tag":     # a tag of a tag: peel to the end
            commit = (_git(repo, "rev-parse", "--verify", "-q", f"{commit}^{{commit}}", ok=True) or "").strip()
        if commit != pin:
            raise Refused(f"tag {name} is missing or not at its pinned commit {pin} (found {commit})")
        if not _has_unit(repo, pin, unit):
            raise Refused(f"tag {name}: its tree has no {unit}")
        found.append({"ref": name, "commit": pin, "time": _commit_time(repo, pin)})
    found.sort(key=lambda r: (r["time"], r["ref"]))
    head = ctx.side["head"]
    found.append({"ref": HEAD_REF, "commit": head, "time": _commit_time(repo, head)})
    return found


def _has_unit(repo: str, commit: str, unit: str) -> bool:
    out = _git(repo, "ls-tree", "--name-only", commit, "--", unit, ok=True)
    return bool(out) and unit in out.splitlines()


def _commit_time(repo: str, commit: str) -> int:
    return int(_git(repo, "log", "-1", "--format=%ct", commit).strip())


# ------------------------------------------------------------------------------------------------------ H2 builds
def _toolchain(ctx: Ctx) -> tuple[str, Path]:
    """The pinned solc and the pinned dependency tree (config replay.solc_sha256, replay.sol_deps_sha256), else
    Refused."""
    from ...replay import tree_sha256
    rep = ctx.cfg.get("replay") or {}
    solc, pin = rep.get("solc"), rep.get("solc_sha256")
    if not solc or not Path(solc).is_file():
        raise Refused(f"solc missing: config replay.solc = {solc!r}")
    if _file_sha(Path(solc)) != pin:
        raise Refused(f"solc {solc} is not the pin config replay.solc_sha256")
    nm = Path(rep.get("sol_deps") or "") / "node_modules"
    if not nm.is_dir() or tree_sha256(nm) != rep.get("sol_deps_sha256"):
        raise Refused(f"{nm} is missing or not the pin config replay.sol_deps_sha256")
    return solc, nm


def _materialize(repo: str, commit: str, dest: Path, paths: list) -> None:
    blob = _git(repo, "archive", "--format=tar", commit, "--", *paths, binary=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
        tf.extractall(dest, filter="data")


def compile_ref(ctx: Ctx, solc: str, deps: Path, tree: Path, conf: dict) -> dict:
    """One configuration's build at a materialized tree: runtime code, its immutable and link ranges, the storage
    layout, the unit's AST and bytes, and the declaring contract of every state variable (by AST id)."""
    unit, name = ctx.side["contract"]["source"], ctx.side["contract"]["name"]
    try:
        text = (tree / unit).read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ExtractionError(f"{unit}: {e}") from e
    sel = {unit: {name: ["evm.deployedBytecode.object", "evm.deployedBytecode.immutableReferences",
                         "evm.deployedBytecode.linkReferences", "storageLayout"]}, "*": {"": ["ast"]}}
    settings = {"evmVersion": conf["evm_version"],
                "optimizer": {"enabled": True, "runs": int(conf["optimizer_runs"])},
                "metadata": {"bytecodeHash": conf["bytecode_hash"]}, "outputSelection": sel}
    cmd = [solc, "--standard-json", "--base-path", ".", "--include-path", str(deps)]
    req = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}}, "settings": settings})
    p = subprocess.run(cmd, input=req, capture_output=True, text=True, cwd=str(tree), timeout=7200)
    try:
        out = json.loads(p.stdout)
    except ValueError as e:
        raise ExtractionError(f"solc gave no JSON (exit {p.returncode}): {p.stderr.strip()[:300]}") from e
    errors = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errors:
        raise ExtractionError("; ".join((e.get("formattedMessage") or e.get("message", ""))[:300] for e in errors[:3]))
    try:
        c = out["contracts"][unit][name]
    except KeyError as e:
        raise ExtractionError(f"solc produced no {name} in {unit}") from e
    dep = c["evm"]["deployedBytecode"]
    imm = [[int(r["start"]), int(r["length"])] for rs in (dep.get("immutableReferences") or {}).values() for r in rs]
    lnk = [[int(r["start"]), int(r["length"])] for f in (dep.get("linkReferences") or {}).values()
           for rs in f.values() for r in rs]
    owner = {}
    for src in out.get("sources", {}).values():
        for cd in src["ast"].get("nodes", []):
            if cd.get("nodeType") != "ContractDefinition":
                continue
            for v in cd.get("nodes", []):
                if v.get("nodeType") == "VariableDeclaration" and v.get("stateVariable"):
                    owner[v["id"]] = cd["name"]
    return {"code": bytes.fromhex(dep["object"]), "ranges": sorted(imm + lnk), "layout": c["storageLayout"],
            "ast": out["sources"][unit]["ast"], "text": text, "owner": owner}


def drop_cbor(code: bytes) -> bytes:
    """The code without solc's CBOR metadata tail: the last two bytes give the tail's length n; the tail is removed when
    it fits and starts with a CBOR map head (0xa0..0xb7)."""
    if len(code) < 3:
        return code
    n = (code[-2] << 8) | code[-1]
    head = len(code) - 2 - n
    if n == 0 or head < 0 or not 0xA0 <= code[head] <= 0xB7:
        return code
    return code[:head]


def identity(code: bytes, ranges: list) -> bytes:
    """H2: every immutable and link range zeroed, then the CBOR metadata dropped."""
    buf = bytearray(code)
    for start, length in ranges:
        end = min(len(buf), start + length)
        if start < end:
            buf[start:end] = b"\x00" * (end - start)
    return drop_cbor(bytes(buf))


# ------------------------------------------------------------------------------------------------------ H3 initializers
def initializers(ast: dict, contract: str, text: str) -> list[dict]:
    """H3: the contract's own functions carrying `initializer` (version 1) or `reinitializer(k)`: [{"name", "version",
    "line"}] by version then name; a reinitializer whose argument is not one integer literal is an ExtractionError."""
    raw = text.encode("utf-8")
    found = []
    defs = [n for n in ast.get("nodes", []) if n.get("nodeType") == "ContractDefinition" and n.get("name") == contract]
    for cd in defs:
        for fn in cd.get("nodes", []):
            if fn.get("nodeType") != "FunctionDefinition":
                continue
            for mod in fn.get("modifiers") or []:
                which = (mod.get("modifierName") or {}).get("name")
                if which == "initializer":
                    version = 1
                elif which == "reinitializer":
                    args = mod.get("arguments") or []
                    if len(args) != 1 or args[0].get("nodeType") != "Literal" or args[0].get("kind") != "number":
                        raise ExtractionError(f"{fn['name']}: the reinitializer's argument is not an integer literal")
                    try:
                        version = int(args[0]["value"], 0)
                    except ValueError as e:
                        raise ExtractionError(f"{fn['name']}: reinitializer({args[0]['value']}) is not an integer") from e
                else:
                    continue
                offset = int(fn["src"].split(":", 1)[0])
                found.append({"name": fn["name"], "version": version, "line": raw.count(b"\n", 0, offset) + 1})
    found.sort(key=lambda r: (r["version"], r["name"]))
    return found


# ------------------------------------------------------------------------------------------------------ H4 layouts
def _signature(types: dict, tid: str) -> dict:
    t = types[tid]
    sig = {"label": t["label"], "encoding": t["encoding"], "bytes": int(t["numberOfBytes"])}
    for part in ("key", "value", "base"):
        if part in t:
            sig[part] = _signature(types, t[part])
    if "members" in t:
        sig["members"] = [{"label": m["label"], "slot": int(m["slot"]), "offset": int(m["offset"]),
                           "type": _signature(types, m["type"])} for m in t["members"]]
    return sig


def layout(storage_layout: dict, owner: dict) -> list[dict]:
    """H4: one entry per state variable, its declaring contract by AST id, in (slot, offset, contract, label) order."""
    types = storage_layout.get("types") or {}
    rows = []
    for e in storage_layout.get("storage") or []:
        if e["astId"] not in owner:
            raise ExtractionError(f"state variable {e['label']} (ast id {e['astId']}) has no declaring contract")
        sig = _signature(types, e["type"])
        rows.append({"contract": owner[e["astId"]], "label": e["label"], "slot": int(e["slot"]),
                     "offset": int(e["offset"]), "bytes": sig["bytes"], "type": sig})
    rows.sort(key=lambda r: (r["slot"], r["offset"], r["contract"], r["label"]))
    return rows


# ------------------------------------------------------------------------------------------------------ H5 diffs
def _bytes_of(e: dict) -> range:
    """The storage bytes an entry occupies: its own bytes for a word or less, whole slots beyond a word."""
    first = e["slot"] * 32 + e["offset"]
    size = e["bytes"] if e["bytes"] <= 32 else -(-e["bytes"] // 32) * 32
    return range(first, first + size)


def _touch(x: dict, y: dict) -> bool:
    a, b = _bytes_of(x), _bytes_of(y)
    return a.start < b.stop and b.start < a.stop


def _is_gap(e: dict) -> bool:
    return e["label"] == "__gap" and e["type"]["encoding"] == "inplace" and "base" in e["type"]


def _struct_grows(old: dict, new: dict) -> bool:
    om, nm = old.get("members"), new.get("members")
    return (om is not None and nm is not None and old["label"] == new["label"] and len(nm) > len(om)
            and nm[:len(om)] == om)


def _mapping_value_grows(old: dict, new: dict) -> bool:
    if old.get("encoding") != "mapping" or new.get("encoding") != "mapping" or old.get("key") != new.get("key"):
        return False
    return _struct_grows(old["value"], new["value"]) or _mapping_value_grows(old["value"], new["value"])


def diff_layouts(old: list, new: list) -> dict:
    """H5, from layout old to layout new; entries are identified by (declaring contract, label)."""
    a = {(e["contract"], e["label"]): e for e in old}
    b = {(e["contract"], e["label"]): e for e in new}
    out = {k: [] for k in ("persisted", "moved", "retyped", "added", "removed", "gap_resized", "overlap")}
    kept = set()
    for k in sorted(a.keys() & b.keys()):
        x, y = a[k], b[k]
        same_place = (x["slot"], x["offset"]) == (y["slot"], y["offset"])
        if same_place and x["type"] == y["type"]:
            out["persisted"].append({"contract": k[0], "label": k[1]})
            kept.add(k)
        elif _is_gap(x) and _is_gap(y):
            out["gap_resized"].append({"contract": k[0], "label": k[1], "from": [x["slot"], x["bytes"]],
                                       "to": [y["slot"], y["bytes"]]})
        elif not same_place:
            out["moved"].append({"contract": k[0], "label": k[1], "from": [x["slot"], x["offset"]],
                                 "to": [y["slot"], y["offset"]]})
        else:
            kind = "struct_extended" if _mapping_value_grows(x["type"], y["type"]) else "changed"
            out["retyped"].append({"contract": k[0], "label": k[1], "kind": kind})
    for k in sorted(b.keys() - a.keys()):
        out["added"].append({"contract": k[0], "label": k[1], "slot": b[k]["slot"], "offset": b[k]["offset"]})
    for k in sorted(a.keys() - b.keys()):
        out["removed"].append({"contract": k[0], "label": k[1], "slot": a[k]["slot"], "offset": a[k]["offset"]})
    # overlap: a new entry that is not persisted, meeting an old entry that is neither a gap nor still at its place
    stayed = {k for k in a.keys() & b.keys() if (a[k]["slot"], a[k]["offset"]) == (b[k]["slot"], b[k]["offset"])}
    olds = [k for k in sorted(a) if not _is_gap(a[k]) and k not in stayed]
    for k in sorted(b):
        if k in kept:
            continue
        for ko in olds:
            if _touch(b[k], a[ko]):
                out["overlap"].append({"contract": k[0], "label": k[1], "meets": {"contract": ko[0], "label": ko[1]}})
    out["compatible"] = (not out["moved"] and not out["overlap"]
                         and all(r["kind"] == "struct_extended" for r in out["retyped"]))
    return out


def reads_of_old(old: list, new: list, diff: dict) -> list[dict]:
    """H6's in-flight set: the new layout's non-gap entries whose bytes meet old non-gap state, with what they read."""
    unchanged = {(p["contract"], p["label"]) for p in diff["persisted"]}
    retyped = {(r["contract"], r["label"]) for r in diff["retyped"]}
    olds = [e for e in old if not _is_gap(e)]
    rows = []
    for y in new:
        if _is_gap(y):
            continue
        hit = sorted(f"{x['contract']}.{x['label']}" for x in olds if _touch(y, x))
        if hit:
            k = (y["contract"], y["label"])
            kind = "unchanged" if k in unchanged else ("retyped" if k in retyped else "reinterpreted")
            rows.append({"entry": f"{k[0]}.{k[1]}", "kind": kind, "reads": hit})
    rows.sort(key=lambda r: r["entry"])
    return rows


# ------------------------------------------------------------------------------------------------------ H6 history
def extract(ctx: Ctx, log=None) -> dict:
    """H1-H6: the history document."""
    solc, deps = _toolchain(ctx)
    repo = ctx.repo()
    confs = ctx.side["compiler_configs"]
    vconf = ctx.side["version_config"]
    if vconf not in confs:
        raise Refused(f"sidecar version_config {vconf!r} is not a compiler configuration")
    rows = []
    with tempfile.TemporaryDirectory(prefix="holon-history-") as td:
        for r in list_refs(ctx):
            tree = Path(td) / r["commit"]
            if not tree.is_dir():
                tree.mkdir()
                _materialize(repo, r["commit"], tree, ctx.side["contract"]["build_paths"])
            row = {"ref": r["ref"], "commit": r["commit"], "time": r["time"], "builds": {}, "error": None}
            try:
                main_build = None
                for cname in sorted(confs):
                    bd = compile_ref(ctx, solc, deps, tree, confs[cname])
                    row["builds"][cname] = {"sha256": _sha(identity(bd["code"], bd["ranges"])),
                                            "length": len(bd["code"]), "ranges": bd["ranges"]}
                    if cname == vconf:
                        main_build = bd
                row["layout"] = layout(main_build["layout"], main_build["owner"])
                row["reinitializers"] = initializers(main_build["ast"], ctx.side["contract"]["name"],
                                                     main_build["text"])
                row["source_sha256"] = _sha(main_build["text"].encode("utf-8"))
            except ExtractionError as e:
                row["error"] = str(e)[:500]
            rows.append(row)
            if log:
                log(f"{r['ref']}: {row['error'] or row['builds'][vconf]['sha256'][:12]}")
    versions = []
    for row in rows:
        if row["error"] is not None:
            continue
        ident = row["builds"][vconf]["sha256"]
        if versions and versions[-1]["code"][vconf]["sha256"] == ident:
            versions[-1]["refs"].append(row["ref"])
            continue
        lay = row["layout"]
        versions.append({"id": f"V{len(versions) + 1}", "refs": [row["ref"]], "commit": row["commit"],
                         "time": row["time"], "code": row["builds"], "source_sha256": row["source_sha256"],
                         "layout": lay, "layout_sha256": _sha(json.dumps(lay, sort_keys=True).encode()),
                         "reinitializers": row["reinitializers"]})
    edges = []
    for old, new in zip(versions, versions[1:]):
        top = max([x["version"] for x in old["reinitializers"]] or [0])
        d = diff_layouts(old["layout"], new["layout"])
        edges.append({"from": old["id"], "to": new["id"],
                      "introduced": [x for x in new["reinitializers"] if x["version"] > top],
                      "layout": d, "compatible": d["compatible"],
                      "in_flight": reads_of_old(old["layout"], new["layout"], d)})
    return {"history_version": HISTORY_VERSION, "sidecar": {"path": ctx.side_rel, "sha256": ctx.side_sha},
            "target": ctx.side["target"], "contract": ctx.side["contract"], "version_config": vconf,
            "refs": [{"ref": w["ref"], "commit": w["commit"], "time": w["time"], "error": w["error"],
                      "builds": w["builds"]} for w in rows],
            "versions": versions, "edges": edges}


# ------------------------------------------------------------------------------------------------------ H7 on chain
def _index(ctx: Ctx) -> tuple[list, dict]:
    """The upgrade source's Upgraded log items [(block, log_index, tx)] by block then log index, and its receipt hashes
    {tx: sha256}."""
    up = ctx.side["upgrades"]
    path = ctx.path(up["path"])
    if not path.is_file() or path.stat().st_size < 1000:
        raise Refused(f"{up['path']} is missing or an LFS pointer (git lfs pull --include {up['path']})")
    from ...ir import canonical_json
    idx = _read_json(path, "upgrade source")
    content = {k: v for k, v in idx.items() if k != "index_sha256"}
    if idx.get("index_sha256") != up["index_sha256"] or _sha(canonical_json(content)) != up["index_sha256"]:
        raise Refused(f"{up['path']}: its content hash is not the sidecar's upgrades.index_sha256")
    topic = ctx.side["events"]["Upgraded"]
    items = sorted((int(i["block"]), int(i["log_index"]), i["tx"]) for i in idx.get("items", [])
                   if i.get("kind") == "log" and i.get("topic") == topic)
    if len(items) != int(up["count"]):
        raise Refused(f"{up['path']}: {len(items)} Upgraded items, the sidecar says {up['count']}")
    receipts = {i["tx"]: i["sha256"] for i in idx.get("items", []) if i.get("kind") == "receipt"}
    return items, receipts


def _word_address(word_hex: str) -> str:
    return "0x" + word_hex[-40:].lower()


def _words(data: str) -> list[str]:
    h = data[2:] if data.startswith("0x") else data
    return [h[i:i + 64] for i in range(0, len(h), 64)]


def read_receipt(ctx: Ctx, receipt: dict, log_index: int) -> dict:
    """H7's facts of one upgrade from its receipt: the proxy's Upgraded log at log_index, its Initialized and
    AdminChanged logs (in log-index order), the sender and the contractAddress."""
    proxy = ctx.side["proxy"]["address"].lower()
    ev = {k: v.lower() for k, v in ctx.side["events"].items()}
    mine = sorted((lg for lg in receipt.get("logs") or [] if (lg.get("address") or "").lower() == proxy),
                  key=lambda lg: int(lg["logIndex"], 16))
    kind = {id(lg): (lg.get("topics") or [""])[0].lower() for lg in mine}
    upg = [lg for lg in mine if int(lg["logIndex"], 16) == log_index and kind[id(lg)] == ev["Upgraded"]]
    if len(upg) != 1:
        raise ExtractionError(f"{receipt.get('transactionHash')}: no Upgraded log of the proxy at log index {log_index}")
    return {"implementation": _word_address(upg[0]["topics"][1]),
            "initialized": [int(_words(lg["data"])[0], 16) for lg in mine if kind[id(lg)] == ev["Initialized"]],
            "admin_changed": [{"previous": _word_address(w[0]), "new": _word_address(w[1])}
                              for lg in mine if kind[id(lg)] == ev["AdminChanged"] for w in [_words(lg["data"])]],
            "from": (receipt.get("from") or "").lower(),
            "contract_address": (receipt.get("contractAddress") or "").lower() or None}


def fetch(ctx: Ctx) -> tuple[dict, dict, dict]:
    """H7: the snapshot document, {tx: canonical receipt bytes} and {implementation: code bytes}."""
    from ...historical.net import Http, Rpc, SourceError, TransientError, host
    from ...historical.store import canon_bytes
    items, hashes = _index(ctx)
    url = ctx.side["rpc"]["url"]
    rpc = Rpc(Http(), url)
    ups, receipts, codes, times = [], {}, {}, {}
    try:
        for block, log_index, tx in items:
            raw = rpc.call("eth_getTransactionReceipt", [tx])
            if not isinstance(raw, dict) or int(raw["blockNumber"], 16) != block:
                raise ExtractionError(f"{tx}: no receipt in block {block}")
            canon = canon_bytes(raw, "receipt")
            if _sha(canon) != hashes.get(tx):
                raise ExtractionError(f"{tx}: the receipt read differs from I59's (sha256 {_sha(canon)})")
            receipts[tx] = canon
            facts = read_receipt(ctx, json.loads(canon), log_index)
            impl = facts["implementation"]
            if block not in times:
                times[block] = int(rpc.call("eth_getBlockByNumber", [hex(block), False])["timestamp"], 16)
            if impl not in codes:
                code = bytes.fromhex(rpc.call("eth_getCode", [impl, "latest"])[2:])
                if not code:
                    raise ExtractionError(f"implementation {impl} has no code")
                codes[impl] = code
            ups.append({"block": block, "time": times[block], "tx": tx, "log_index": log_index,
                        "receipt_sha256": _sha(canon), **facts,
                        "code_sha256": _sha(codes[impl]), "code_length": len(codes[impl])})
    except (SourceError, TransientError, KeyError, ValueError, IndexError, TypeError) as e:
        raise ExtractionError(f"fetch: {e}") from e
    up = ctx.side["upgrades"]
    doc = {"onchain_version": ONCHAIN_VERSION, "sidecar": {"path": ctx.side_rel, "sha256": ctx.side_sha},
           "index": {"path": up["path"], "sha256": up["index_sha256"]},
           "rpc": {"host": host(url), "methods": ctx.side["rpc"]["methods"]},
           "proxy": {"address": ctx.side["proxy"]["address"].lower(), "chain": ctx.side["proxy"]["chain"]},
           "window": up["window"], "upgrades": ups}
    return doc, receipts, codes


def check_snapshot(ctx: Ctx) -> list[str]:
    """fetch --check: the committed snapshot against the sidecar, I59's index (Upgraded items and receipt hashes), its
    receipts (re-read) and its code files. Returns the differences."""
    p = ctx.path(ctx.out["onchain"])
    if not p.is_file():
        raise Refused(f"{ctx.out['onchain']} is missing")
    doc = _read_json(p, "snapshot")
    items, hashes = _index(ctx)
    bad = []
    if doc.get("onchain_version") != ONCHAIN_VERSION:
        bad.append("onchain_version")
    if doc.get("sidecar") != {"path": ctx.side_rel, "sha256": ctx.side_sha}:
        bad.append("the sidecar changed after the fetch")
    if doc.get("index") != {"path": ctx.side["upgrades"]["path"], "sha256": ctx.side["upgrades"]["index_sha256"]}:
        bad.append("the snapshot's index is not the sidecar's upgrade source")
    from ...historical.net import host
    if doc.get("proxy") != {"address": ctx.side["proxy"]["address"].lower(), "chain": ctx.side["proxy"]["chain"]}:
        bad.append("the snapshot's proxy is not the sidecar's")
    if doc.get("window") != ctx.side["upgrades"]["window"]:
        bad.append("the snapshot's window is not the sidecar's")
    if doc.get("rpc") != {"host": host(ctx.side["rpc"]["url"]), "methods": ctx.side["rpc"]["methods"]}:
        bad.append("the snapshot's rpc is not the sidecar's")
    ups = doc.get("upgrades") or []
    if [(u["block"], u["log_index"], u["tx"]) for u in ups] != items:
        bad.append("the upgrades are not the upgrade source's Upgraded logs")
    for u in ups:
        rp = ctx.path(ctx.out["receipts"]) / f"{u['tx']}.json"
        try:
            raw = rp.read_bytes()
        except OSError:
            bad.append(f"{ctx.out['receipts']}/{u['tx']}.json is missing")
            continue
        if not (_sha(raw) == u.get("receipt_sha256") == hashes.get(u["tx"])):
            bad.append(f"{ctx.out['receipts']}/{u['tx']}.json is not I59's receipt")
            continue
        try:
            facts = read_receipt(ctx, json.loads(raw), u["log_index"])
        except (ExtractionError, ValueError, KeyError, IndexError) as e:
            bad.append(f"{u['tx']}: {e}")
            continue
        if any(u.get(k) != v for k, v in facts.items()):
            bad.append(f"{u['tx']}: the snapshot's fields are not its receipt's")
        cp = ctx.path(ctx.out["code"]) / f"{u['implementation']}.hex"
        try:
            code = bytes.fromhex(cp.read_text().strip())
        except (OSError, ValueError):
            bad.append(f"{ctx.out['code']}/{u['implementation']}.hex is missing or not hex")
            continue
        if (_sha(code), len(code)) != (u.get("code_sha256"), u.get("code_length")):
            bad.append(f"{ctx.out['code']}/{u['implementation']}.hex does not hash to the snapshot's code_sha256")
    for rel, want in ((ctx.out["receipts"], {f"{u['tx']}.json" for u in ups}),
                      (ctx.out["code"], {f"{u['implementation']}.hex" for u in ups})):
        d = ctx.path(rel)
        stray = sorted(f.name for f in d.iterdir() if f.name not in want) if d.is_dir() else []
        if stray:
            bad.append(f"{rel} holds files no upgrade names: {', '.join(stray)}")
    return bad


# ------------------------------------------------------------------------------------------------------ H8 timeline
def timeline(ctx: Ctx) -> dict:
    """H7's match and H8, from the committed history and the checked snapshot."""
    hp, op = ctx.path(ctx.out["history"]), ctx.path(ctx.out["onchain"])
    for rel, p in ((ctx.out["history"], hp), (ctx.out["onchain"], op)):
        if not p.is_file():
            raise Refused(f"{rel} is missing")
    hist, snap = _read_json(hp, "history"), _read_json(op, "snapshot")
    for name, d in (("history", hist), ("snapshot", snap)):
        if d.get("sidecar") != {"path": ctx.side_rel, "sha256": ctx.side_sha}:
            raise Refused(f"the {name} is stale: written under another sidecar")
    bad = check_snapshot(ctx)
    if bad:
        raise Refused("the snapshot does not check: " + "; ".join(bad))
    versions = hist["versions"]
    rank = {v["id"]: i for i, v in enumerate(versions)}
    by_ranges: dict[tuple, list] = {}       # a build's ranges -> [(version rank, config, identity sha256)]
    for v in versions:
        for cname, b in v["code"].items():
            by_ranges.setdefault(tuple(map(tuple, b["ranges"])), []).append((rank[v["id"]], cname, b["sha256"]))
    tops = {v["id"]: max([x["version"] for x in v["reinitializers"]] or [0]) for v in versions}
    reinit = {v["id"]: [x["version"] for x in v["reinitializers"]] for v in versions}
    rows, prev, high, seen = [], None, 0, []
    for u in snap["upgrades"]:
        code = bytes.fromhex((ctx.path(ctx.out["code"]) / f"{u['implementation']}.hex").read_text().strip())
        hits = []
        for ranges, cands in by_ranges.items():
            h = _sha(identity(code, [list(r) for r in ranges]))
            hits += [(rk, cname) for rk, cname, s in cands if s == h]
        hits.sort()
        matches = [{"version": versions[rk]["id"], "config": cname} for rk, cname in hits]
        ids = sorted({m["version"] for m in matches}, key=rank.get)
        ver = ids[0] if len(ids) == 1 else None
        expected = None
        if ver is not None:
            base = max(tops[prev] if prev is not None else 0, high)
            expected = sorted(k for k in reinit[ver] if k > base)
        logged = sorted(u["initialized"])
        rows.append({"block": u["block"], "tx": u["tx"], "implementation": u["implementation"], "matches": matches,
                     "version": ver, "expected_initialized": expected, "initialized": logged,
                     "consistent": expected is not None and expected == logged})
        high = max([high] + logged)
        if ver is not None:
            seen.append((u["block"], ver))
            prev = ver
    downgrades = []
    for i, (blk, ver) in enumerate(seen):
        newer = [v for _, v in seen[:i] if rank[v] > rank[ver]]
        if newer:
            downgrades.append({"block": blk, "version": ver, "after": max(newer, key=rank.get)})
    debt = [{"block": r["block"], "implementation": r["implementation"], "reason": NO_MATCH}
            for r in rows if not r["matches"]]
    debt += [{"block": r["block"], "implementation": r["implementation"], "reason": SEVERAL}
             for r in rows if r["matches"] and r["version"] is None]
    debt.sort(key=lambda d: d["block"])
    named = {m["version"] for r in rows for m in r["matches"]}
    return {"timeline_version": TIMELINE_VERSION,
            "history": {"path": ctx.out["history"], "sha256": _file_sha(hp)},
            "onchain": {"path": ctx.out["onchain"], "sha256": _file_sha(op)},
            "upgrades": rows, "downgrades": downgrades, "coverage_debt": debt,
            "never_deployed": [v["id"] for v in versions if v["id"] not in named]}


# ------------------------------------------------------------------------------------------------------ CLI
def _write_or_check(path: Path, data: bytes, check: bool) -> int:
    if check:
        if not path.is_file():
            print(f"missing: {path}", file=sys.stderr)
            return 1
        if path.read_bytes() != data:
            print(f"differs: {path}", file=sys.stderr)
            return 1
        print(f"reproduced: {path}")
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"wrote {path}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon history")
    ap.add_argument("command", choices=["extract", "fetch", "timeline"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--sidecar", default=SIDECAR)
    ap.add_argument("--root", default=str(ROOT))
    a = ap.parse_args(argv)
    try:
        ctx = Ctx(Path(a.root), a.sidecar)
        if a.command == "extract":
            doc = extract(ctx, log=lambda s: print(s, file=sys.stderr, flush=True))
            return _write_or_check(ctx.path(ctx.out["history"]), render(doc), a.check)
        if a.command == "fetch":
            if a.check:
                bad = check_snapshot(ctx)
                for b in bad:
                    print(f"differs: {b}", file=sys.stderr)
                if not bad:
                    print(f"reproduced: {ctx.path(ctx.out['onchain'])}")
                return 1 if bad else 0
            out = ctx.path(ctx.out["onchain"])
            if out.exists():
                raise Refused(f"{ctx.out['onchain']} exists: the snapshot is written once, then only checked")
            doc, receipts, codes = fetch(ctx)
            rdir, cdir = ctx.path(ctx.out["receipts"]), ctx.path(ctx.out["code"])
            rdir.mkdir(parents=True, exist_ok=True)
            cdir.mkdir(parents=True, exist_ok=True)
            for tx, canon in sorted(receipts.items()):
                (rdir / f"{tx}.json").write_bytes(canon)
            for impl, code in sorted(codes.items()):
                (cdir / f"{impl}.hex").write_text(code.hex() + "\n")
            return _write_or_check(out, render(doc), False)
        doc = timeline(ctx)
        return _write_or_check(ctx.path(ctx.out["timeline"]), render(doc), a.check)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    except (KeyError, TypeError) as e:
        print(f"refused: a malformed sidecar, configuration or input ({type(e).__name__}: {e})", file=sys.stderr)
        return 2
    except (subprocess.SubprocessError, OSError) as e:
        print(f"error: {type(e).__name__}: {e}", file=sys.stderr)
        return 3
    except ExtractionError as e:
        print(f"error: {e}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
