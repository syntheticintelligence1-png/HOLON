"""I69 instrument (= I36a: Bundle I's extraction and acquisition), fixed at the I69 prereg (BUILD_PLAN §0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_bundle_extraction.py (rules E1-E7, M1-M6, L1-L8, C1-C6, A1-A7). This
module writes the rules the tests decide a second time, independently of holon/: it never imports holon. It reads the
sidecar (spec/M3/lib/bundle.json), config/holon.json (the pinned solc and Solidity dependencies), the target
repository's git objects (read-only, with lazy fetching disabled: a missing object is an InstrumentError, never a fetch),
committed records of earlier keys (I63's cutover receipt, I23's call record, the adopted Rollup document) and, after
the build, the committed snapshot, documents and records. It reuses I63's instrument (tests_m3/_i63.py, fixed at I63's
prereg) for rules H2-H8 and tests_m2/_keccak.py for keccak256.

  git(repo, *args)                read-only git, lazy fetching disabled (protocol.allow=never), no auto gc
  materialize(repo, commit, dest)  the commit's contracts/ tree written under dest (git archive; no checkout)
  build(cfg, tree, unit, name, c)  one configuration's build: runtime code, ranges, immutables by name, layout, AST
  registry_basis(root)            A2: rules H1-H6 over the registry's pinned tags (I63's functions), immutables by name
  member_builds(root)             A2: the head builds of the four members under every configuration
  basis(root)                     the content of spec/M3/lib/bundle_basis.json (registry and members)
  closure_table(root)             the blobs of L1Staking.sol and its imports at every pinned tag (disclosed facts)
  tags_with_unit(tags, unit)      the pinned tags whose tree holds a source unit
  ast_actions(root, unit, name, commit)   rule E2 over solc's AST: the action names of a contract
  link_table(docs, wiring)        rule L2 over documents: the static link rows
  relay_leaf / relay_root / poke_slot     rule C4's relay inputs (the seed's planted literals)
  cutover_registries(root)        the SubmitterContractUpdated log of I63's committed cutover receipt
  queue_of_i23(root)              the receiver of the Rollup's IL1MessageQueue calls in I23's record
  decode(receipt, proxy, events)  A4: the proxy's Upgraded, AdminChanged and Initialized logs of a receipt
  match(entries, code)            A5: the (key, config) builds a deployed runtime code equals (I63's identity)
  words_at(code, ranges)          the 32-byte words of a code at an immutable's ranges
  timeline(root, basis)           A4-A6, recomputed from the committed snapshot's raw logs, receipts and code: decides
                                  I69-P1 and I69-P2 (InstrumentError when the snapshot is not what A3 says it is)
  interfaces(root)                the members' solc ABI, E2 action names with selectors and kinds, and storage layouts
  structure(root)                 R5: per document, E2's action names, own families in declaration order, inherited
                                  entries and constants, from solc (the frontend's construction facts)
  random_corpus(side, ifaces)     C3's random part, regenerated (random.Random(seed), the docstring's draw order)
  m1_sha256(corpus)               C3: the sha256 of the corpus's m1 part as holon.mreplay.random_corpus returns it
  recount(steps, ifaces, links)   C6 recounted from the per-step evidence: traces, steps, frames_ok,
                                  by_member_action and links_ok, from the harness's frames
  canon_receipt(obj)              I59's canonical receipt bytes (holon.historical.store's fields, written again)
  second_read(root, host)         A7: the anchor read from a host of the sidecar's rpc.second (the only network read
                                  of this module; run once, by --second-read, after the build's fetch)
  second_read_differences(root)   A7: what the committed second read and the snapshot disagree on

  python -m tests_m3._i69 --write         recompute spec/M3/lib/bundle_basis.json (only at the prereg)
  python -m tests_m3._i69 --second-read   write results/M3/bundle/second_read.json (A7; once, after the fetch)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ROOT / "spec" / "M3" / "lib" / "bundle.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "bundle_basis.json"
ROLLUP_DOC = ROOT / "spec" / "M2" / "facts" / "morph_rollup.extracted.json"
CUTOVER = ROOT / "results" / "M3" / "history" / "receipts" / \
    "0xdeb5268cbec1b47c77ad46cb8dd29491833e45ae374d2905f94f4e0499e8110e.json"
I23_TRANS = ROOT / "results" / "M2" / "historical" / "trans.json"
SUBMITTER_UPDATED = "SubmitterContractUpdated(address,address,uint256)"
RELAY_SIG = "relayMessage(address,address,uint256,uint256,bytes)"
REGISTRY_IMPORTS = ("contracts/contracts/l1/staking/L1Staking.sol", "contracts/contracts/l1/staking/IL1Staking.sol",
                    "contracts/contracts/libraries/staking/Staking.sol",
                    "contracts/contracts/libraries/common/Types.sol",
                    "contracts/contracts/libraries/constants/Predeploys.sol",
                    "contracts/contracts/l2/staking/IL2Staking.sol",
                    "contracts/contracts/libraries/ICrossDomainMessenger.sol")


class InstrumentError(RuntimeError):
    """An input the rules refuse (a moved tag, a missing object, an unpinned toolchain, a receipt that is not I59's)."""


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def keccak(b: bytes) -> bytes:
    from tests_m2._keccak import keccak256
    return keccak256(b)


def selector(sig: str) -> str:
    return keccak(sig.encode()).hex()[:8]


def i63():
    import tests_m3._i63 as I
    return I


# ---------------------------------------------------------------------------------------------------- git, read-only
def _git_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C")
    return env


def git(repo: str, *args: str, binary: bool = False):
    """git with lazy fetching disabled: in a partial clone a missing object fails instead of being fetched from the
    target's origin (the I63 incident, docs/iterations/I63.md), and no automatic gc runs."""
    cmd = ["git", "-C", str(repo), "-c", "protocol.allow=never", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
           "-c", "core.fsmonitor=false", *args]
    p = subprocess.run(cmd, capture_output=True, env=_git_env(), stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise InstrumentError(f"git {' '.join(args)}: {p.stderr.decode(errors='replace').strip()[:300]}")
    return p.stdout if binary else p.stdout.decode()


def repo_of(root: Path = ROOT) -> str:
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    cfg = load(root / "config" / "holon.json")
    repo = (cfg.get("extract") or {}).get("sources", {}).get(side["target"]["repo"])
    if not repo or not Path(repo).is_dir():
        raise InstrumentError(f"config extract.sources has no checkout of {side['target']['repo']}")
    return repo


def peel(repo: str, tag: str) -> str:
    return git(repo, "rev-parse", "--verify", "-q", f"{tag}^{{commit}}").strip()


def materialize(repo: str, commit: str, dest: Path, paths=("contracts",)) -> None:
    data = git(repo, "archive", "--format=tar", commit, "--", *paths, binary=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(dest, filter="data")


# ---------------------------------------------------------------------------------------------------- builds
def build(cfg: dict, tree: Path, unit: str, name: str, conf: dict) -> dict:
    """One configuration's build of contract `name` in `unit` at a materialized tree (I63's H2 settings): runtime
    code, immutable and link ranges (sorted), the ranges of every immutable by its name, the storage layout and the
    unit's AST."""
    rep = cfg["replay"]
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
    names = {}
    for src in out["sources"].values():
        stack = [src["ast"]]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                if n.get("nodeType") == "VariableDeclaration" and n.get("mutability") == "immutable":
                    names[str(n["id"])] = n["name"]
                stack.extend(v for v in n.values() if isinstance(v, (dict, list)))
            elif isinstance(n, list):
                stack.extend(n)
    imm = {}
    for aid, rs in (d.get("immutableReferences") or {}).items():
        imm.setdefault(names.get(str(aid), f"ast:{aid}"), []).extend([[r["start"], r["length"]] for r in rs])
    ranges = sorted([x for v in imm.values() for x in v]
                    + [[r["start"], r["length"]] for f in (d.get("linkReferences") or {}).values()
                       for rs in f.values() for r in rs])
    decl = {}
    for src in out["sources"].values():
        for node in src["ast"].get("nodes", []):
            if node.get("nodeType") == "ContractDefinition":
                for v in node.get("nodes", []):
                    if v.get("nodeType") == "VariableDeclaration" and v.get("stateVariable"):
                        decl[v["id"]] = node["name"]
    return {"code": d["object"].lower(), "ranges": ranges, "immutables": {k: sorted(v) for k, v in sorted(imm.items())},
            "layout": c["storageLayout"], "ast": out["sources"][unit]["ast"], "unit_text": text, "declared_in": decl}


def _identity(b: dict) -> dict:
    code = bytes.fromhex(b["code"])
    return {"sha256": sha256_bytes(i63().code_identity(code, b["ranges"])), "length": len(code),
            "ranges": b["ranges"], "immutables": b["immutables"]}


def _toolchain(root: Path) -> dict:
    cfg = load(root / "config" / "holon.json")
    i63().check_toolchain(cfg)
    return cfg


def registry_refs(root: Path = ROOT) -> list:
    """A1: the registry's pinned tags, each present at its pinned commit and holding the unit (else InstrumentError),
    by committer time then tag name; no head ref (the unit is absent at the head)."""
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    reg = side["acquisition"]["registry"]
    repo = repo_of(root)
    out = []
    for t, pinned in sorted(reg["tags"].items()):
        if peel(repo, t) != pinned:
            raise InstrumentError(f"tag {t} is missing or not at its pinned commit {pinned}")
        if reg["contract"]["source"] not in git(repo, "ls-tree", "--name-only", pinned, "--",
                                                reg["contract"]["source"]).split():
            raise InstrumentError(f"tag {t}: its tree has no {reg['contract']['source']}")
        out.append({"ref": t, "commit": pinned, "time": int(git(repo, "show", "-s", "--format=%ct", pinned).strip())})
    out.sort(key=lambda r: (r["time"], r["ref"]))
    return out


def registry_basis(root: Path = ROOT, log=None) -> dict:
    """A2: I63's H2-H6 over the registry's refs (every configuration; versions under the sidecar's version_config;
    layouts, reinitializers and MIG edges as I63's), plus every build's immutable ranges by name."""
    I = i63()
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    acq = side["acquisition"]
    unit, name = acq["registry"]["contract"]["source"], acq["registry"]["contract"]["name"]
    cfg = _toolchain(root)
    repo = repo_of(root)
    confs, vconf = acq["compiler_configs"], acq["version_config"]
    shim = {"contract": {"source": unit, "name": name}}
    per_ref = []
    with tempfile.TemporaryDirectory(prefix="i69-reg-") as td:
        for r in registry_refs(root):
            tree = Path(td) / r["commit"][:12]
            tree.mkdir()
            materialize(repo, r["commit"], tree, acq["registry"]["contract"]["build_paths"])
            item = {"ref": r["ref"], "commit": r["commit"], "time": r["time"], "builds": {}}
            try:
                b0 = None
                for cname in sorted(confs):
                    b = build(cfg, tree, unit, name, confs[cname])
                    item["builds"][cname] = _identity(b)
                    if cname == vconf:
                        b0 = b
                item["layout"] = I.layout_entries(b0["layout"], b0["declared_in"])
                item["reinitializers"] = I.reinitializers(b0["ast"], shim, b0["unit_text"])
                item["source_sha256"] = sha256_bytes(b0["unit_text"].encode("utf-8"))
                item["error"] = None
            except (RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as e:
                item["error"] = str(e)[:500]
            per_ref.append(item)
            if log:
                log(f"registry {r['ref']}: {item['error'] or item['builds'][vconf]['sha256'][:12]}")
    versions = []
    for it in per_ref:
        if it["error"] is not None:
            continue
        key = it["builds"][vconf]["sha256"]
        if versions and versions[-1]["code"][vconf]["sha256"] == key:
            versions[-1]["refs"].append(it["ref"])
            continue
        versions.append({"id": f"V{len(versions) + 1}", "refs": [it["ref"]], "commit": it["commit"], "time": it["time"],
                         "code": it["builds"], "source_sha256": it["source_sha256"], "layout": it["layout"],
                         "layout_sha256": sha256_bytes(json.dumps(it["layout"], sort_keys=True).encode()),
                         "reinitializers": it["reinitializers"]})
    edges = []
    for v, w in zip(versions, versions[1:]):
        top = max((x["version"] for x in v["reinitializers"]), default=0)
        diff = I.layout_diff(v["layout"], w["layout"])
        edges.append({"from": v["id"], "to": w["id"], "introduced": [x for x in w["reinitializers"] if x["version"] > top],
                      "layout": diff, "compatible": diff["compatible"],
                      "in_flight": I.in_flight(v["layout"], w["layout"], diff)})
    return {"contract": acq["registry"]["contract"], "version_config": vconf,
            "refs": [{k: it[k] for k in ("ref", "commit", "time", "error")} | {"builds": it.get("builds", {})}
                     for it in per_ref],
            "versions": versions, "edges": edges}


def member_builds(root: Path = ROOT, log=None) -> dict:
    """A2: the four members' head builds (the head commit's tree materialized from git objects) under every
    configuration: code identity, length, ranges and immutable ranges by name. No layout (the documents give it)."""
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    acq = side["acquisition"]
    cfg = _toolchain(root)
    repo = repo_of(root)
    out = {}
    with tempfile.TemporaryDirectory(prefix="i69-head-") as td:
        tree = Path(td) / "head"
        tree.mkdir()
        materialize(repo, side["target"]["head"], tree)
        for m, c in sorted(acq["members"].items()):
            out[m] = {"source": c["source"], "name": c["name"], "builds": {}}
            for cname in sorted(acq["compiler_configs"]):
                out[m]["builds"][cname] = _identity(build(cfg, tree, c["source"], c["name"],
                                                          acq["compiler_configs"][cname]))
            if log:
                log(f"member {m}: {out[m]['builds']['hardhat']['sha256'][:12]}")
    return out


def basis(root: Path = ROOT, log=None) -> dict:
    side_sha = sha256_bytes((root / "spec" / "M3" / "lib" / "bundle.json").read_bytes())
    return {"basis_version": "holon-bundle-basis/0.1", "sidecar_sha256": side_sha,
            "registry": registry_basis(root, log), "members": member_builds(root, log)}


# ---------------------------------------------------------------------------------------------------- disclosed facts
def closure_table(root: Path = ROOT) -> dict:
    """{tag: {path: blob}} of L1Staking.sol and its six repository imports at every pinned registry tag, from the
    tags' trees (no blob is read)."""
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    repo = repo_of(root)
    out = {}
    for t, c in sorted(side["acquisition"]["registry"]["tags"].items()):
        rows = git(repo, "ls-tree", c, "--", *REGISTRY_IMPORTS).splitlines()
        out[t] = {ln.split("\t", 1)[1]: ln.split()[2] for ln in rows if ln.strip()}
    return out


def tags_with_unit(tags: dict, unit: str, root: Path = ROOT) -> list:
    """The tags of {tag: pinned commit} whose pinned commit's tree holds the unit (git ls-tree; no blob is read)."""
    repo = repo_of(root)
    return sorted(t for t, c in tags.items() if unit in git(repo, "ls-tree", "--name-only", c, "--", unit).split())


def blob_text(blob: str, root: Path = ROOT) -> str:
    return git(repo_of(root), "cat-file", "blob", blob)


def cutover_registries(root: Path = ROOT) -> dict:
    """The SubmitterContractUpdated(address,address,uint256) log of I63's committed cutover receipt: the old registry
    (topic 1), the new one (topic 2) and the legacy cutover batch index (topic 3)."""
    rc = load(root / CUTOVER.relative_to(ROOT))
    t0 = "0x" + keccak(SUBMITTER_UPDATED.encode()).hex()
    logs = [lg for lg in rc["logs"] if lg["topics"] and lg["topics"][0] == t0]
    if len(logs) != 1:
        raise InstrumentError(f"the cutover receipt holds {len(logs)} SubmitterContractUpdated logs")
    t = logs[0]["topics"]
    return {"emitter": logs[0]["address"].lower(), "old": "0x" + t[1][-40:], "new": "0x" + t[2][-40:],
            "index": int(t[3], 16), "receipt_sha256": sha256_bytes((root / CUTOVER.relative_to(ROOT)).read_bytes())}


def queue_of_i23(root: Path = ROOT) -> dict:
    """I23's historical call record: every address it names, by count (the queue receives the Rollup's
    IL1MessageQueue calls, which outnumber its other calls)."""
    import re
    text = (root / I23_TRANS.relative_to(ROOT)).read_text()
    c = Counter(a.lower() for a in re.findall(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])", text))
    d = json.loads(text)
    q = sum(v for k, v in d["calls_by_fn"].items() if k.startswith("IL1MessageQueue."))
    return {"counts": dict(c), "queue_calls": q}


# ---------------------------------------------------------------------------------------------------- rule E2
def _solc_out(cfg: dict, tree: Path, unit: str, select: dict) -> dict:
    """solc --standard-json on one unit of a materialized tree (no optimizer, cancun), with the given outputSelection."""
    text = (tree / unit).read_text(encoding="utf-8")
    inp = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}},
                      "settings": {"evmVersion": "cancun", "optimizer": {"enabled": False}, "outputSelection": select}})
    cmd = [cfg["replay"]["solc"], "--standard-json", "--base-path", ".", "--include-path",
           str(Path(cfg["replay"]["sol_deps"]) / "node_modules")]
    p = subprocess.run(cmd, input=inp, capture_output=True, text=True, cwd=str(tree), timeout=1800)
    out = json.loads(p.stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise InstrumentError("; ".join((e.get("formattedMessage") or e["message"])[:300] for e in errs[:3]))
    return out


def _nodes(out: dict) -> dict:
    nodes = {}
    for src in out["sources"].values():
        stack = [src["ast"]]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                if isinstance(n.get("id"), int):
                    nodes[n["id"]] = n
                stack.extend(v for v in n.values() if isinstance(v, (dict, list)))
            elif isinstance(n, list):
                stack.extend(n)
    return nodes


def _e2(out: dict, name: str) -> list:
    """Rule E2 over a solc output's AST: [(action name, selector or None, kind, declaring contract)], most derived
    first."""
    nodes = _nodes(out)
    cs = [n for n in nodes.values() if n.get("nodeType") == "ContractDefinition" and n.get("name") == name]
    if len(cs) != 1:
        raise InstrumentError(f"contract {name} found {len(cs)} times")
    seen, acts = set(), []
    for cid in cs[0].get("linearizedBaseContracts") or [cs[0]["id"]]:
        for f in nodes[cid].get("nodes") or []:
            if f.get("nodeType") != "FunctionDefinition" or f.get("visibility") not in ("external", "public"):
                continue
            if f.get("kind") not in ("function", "receive", "fallback") or f.get("body") is None:
                continue
            key = f.get("functionSelector") or f.get("kind")
            if key in seen:
                continue
            seen.add(key)
            acts.append((f.get("name") or f.get("kind"), f.get("functionSelector"), f.get("kind"),
                         nodes[cid].get("name")))
    count = Counter(n for n, _, _, _ in acts)
    return [(f"{n}_{s}" if count[n] > 1 and s else n, s, k, d) for n, s, k, d in acts]


def ast_actions(root: Path, unit: str, name: str, commit: str) -> list:
    """Rule E2 over solc's AST (AST only, the pinned solc; the commit's tree materialized from git objects): every
    external or public FunctionDefinition with a body (kinds function, receive, fallback) of the contract and its
    bases, most derived first, one per selector (receive and fallback by kind); named by its name (its kind for
    receive and fallback), or <name>_<8 hex digits of its selector> when another action has the same name. Sorted."""
    cfg = _toolchain(root)
    repo = repo_of(root)
    with tempfile.TemporaryDirectory(prefix="i69-ast-") as td:
        tree = Path(td) / "t"
        tree.mkdir()
        materialize(repo, commit, tree)
        out = _solc_out(cfg, tree, unit, {"*": {"": ["ast"]}})
    return sorted(n for n, _, _, _ in _e2(out, name))


# ---------------------------------------------------------------------------------------------------- interfaces
def _abi_type(x: dict) -> str:
    t = x["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(_abi_type(c) for c in x["components"]) + ")" + t[len("tuple"):]
    return t


def member_commit(root: Path, m: dict) -> str:
    """A sidecar member's commit: its own, or for the adopted Rollup its document's target commit."""
    return load(root / m["document"])["target"]["commit"] if m.get("adopted") else m["commit"]


def interfaces(root: Path = ROOT) -> dict:
    """{member: {"contract", "commit", "actions", "getters", "layout", "own", "constants"}} for every member and
    extracted_only member of the sidecar, from the pinned solc at the member's commit (tree from git objects):
    actions: rule E2's actions sorted by name, each {"name", "selector" ("0x" + 8 hex; "0x" for receive and fallback),
    "kind", "signature" (the ABI's canonical signature; "receive" or "fallback"), "payable", "inputs", "outputs"};
    getters: {name: selector} of the ABI functions that are no action (public state variables' getters); layout:
    I63's layout entries (with the declaring contract); own: the contract's own non-constant, non-immutable state
    variables in declaration order; constants: {name: the literal's value, or None when the initializer is not a
    number literal} of the contract's own constants."""
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    cfg = _toolchain(root)
    repo = repo_of(root)
    by_commit: dict = {}
    for m in side["members"] + side["extracted_only"]:
        by_commit.setdefault(member_commit(root, m), []).append(m)
    out = {}
    with tempfile.TemporaryDirectory(prefix="i69-if-") as td:
        for commit in sorted(by_commit):
            tree = Path(td) / commit[:12]
            tree.mkdir()
            materialize(repo, commit, tree)
            for m in sorted(by_commit[commit], key=lambda x: x["name"]):
                unit, name = m["source"], m["contract"]
                o = _solc_out(cfg, tree, unit, {unit: {name: ["abi", "storageLayout"]}, "*": {"": ["ast"]}})
                c = o["contracts"][unit][name]
                abi = {}
                for e in c["abi"]:
                    if e["type"] == "function":
                        sig = f"{e['name']}({','.join(_abi_type(x) for x in e['inputs'])})"
                        abi["0x" + selector(sig)] = (sig, e)
                    elif e["type"] in ("receive", "fallback"):
                        abi[e["type"]] = (e["type"], e)
                acts = []
                for n, sel, kind, _decl in _e2(o, name):
                    sig, e = abi["0x" + sel] if sel else abi[kind]
                    acts.append({"name": n, "selector": "0x" + sel if sel else "0x", "kind": kind, "signature": sig,
                                 "payable": e.get("stateMutability") == "payable", "inputs": e.get("inputs") or [],
                                 "outputs": e.get("outputs") or []})
                sels = {a["selector"] for a in acts}
                getters = {e["name"]: k for k, (_s, e) in abi.items() if e["type"] == "function" and k not in sels}
                nodes = _nodes(o)
                decl = {}
                for n in nodes.values():
                    if n.get("nodeType") == "ContractDefinition":
                        for v in n.get("nodes") or []:
                            if v.get("nodeType") == "VariableDeclaration" and v.get("stateVariable"):
                                decl[v["id"]] = n["name"]
                cs = [n for n in nodes.values() if n.get("nodeType") == "ContractDefinition" and n.get("name") == name]
                own, consts = [], {}
                for v in cs[0].get("nodes") or []:
                    if v.get("nodeType") != "VariableDeclaration" or not v.get("stateVariable"):
                        continue
                    if v.get("constant"):
                        val = v.get("value") or {}
                        consts[v["name"]] = (str(int(val["value"])) if val.get("nodeType") == "Literal"
                                             and val.get("kind") == "number" and str(val.get("value", "")).isdigit()
                                             else None)
                    elif v.get("mutability") != "immutable":
                        own.append(v["name"])
                out[m["name"]] = {"contract": name, "commit": commit, "actions": sorted(acts, key=lambda a: a["name"]),
                                  "getters": dict(sorted(getters.items())),
                                  "layout": i63().layout_entries(c["storageLayout"], decl), "own": own,
                                  "constants": consts}
    return out


def structure(ifaces: dict, member: str) -> dict:
    """R5's construction facts of one document from solc: E2's action names, the own families in declaration order,
    the number of inherited layout entries and the own constants."""
    f = ifaces[member]
    own_names = set(f["own"])
    return {"actions": sorted(a["name"] for a in f["actions"]), "storage": f["own"],
            "inherited": len([e for e in f["layout"] if not (e["contract"] == f["contract"] and e["label"] in own_names)]),
            "constants": f["constants"]}


def slot_of(ifaces: dict, member: str, label: str) -> int:
    hits = [e["slot"] for e in ifaces[member]["layout"] if e["label"] == label]
    if len(hits) != 1:
        raise InstrumentError(f"{member}.{label}: {len(hits)} layout entries")
    return hits[0]


# ---------------------------------------------------------------------------------------------------- rule C3
M1_SHA_FORM = "sha256 of json.dumps(traces, sort_keys=True, separators=(',', ':')) of the 300 lists of row dicts"


def m1_traces(corpus: dict) -> list:
    """C3's m1 part of a corpus document as holon.mreplay.random_corpus returns it: the row dict of every step of
    every m1 trace, traces in corpus order."""
    return [[st["row"] for st in tr["steps"]] for tr in corpus["traces"] if tr["source"] == "m1"]


def m1_sha256(corpus: dict) -> str:
    return sha256_bytes(json.dumps(m1_traces(corpus), sort_keys=True, separators=(",", ":")).encode())


def _uint_bits(t: str) -> int:
    return int(t[4:] or 256)


def random_corpus(side: dict, ifaces: dict) -> list:
    """C3's random part, as the docstring of tests_m3/test_bundle_extraction.py defines it: [{"id", "source":
    "random", "steps"}]."""
    import random
    R = side["corpus"]["random"]
    rng = random.Random(R["seed"])
    members = sorted(m["name"] for m in side["members"])
    num, den = (int(x) for x in R["warp"]["probability"].split("/"))
    out = []
    for t in range(R["traces"]):
        uints = list(R["uints"])

        def arg(x: dict):
            ty = x["type"]
            if ty.endswith("]"):
                base, n = ty[:ty.rindex("[")], ty[ty.rindex("[") + 1:-1]
                k = rng.choice(R["array_lengths"]) if n == "" else int(n)
                return [arg(dict(x, type=base)) for _ in range(k)]
            if ty == "tuple":
                return [arg(c) for c in x["components"]]
            if ty == "address":
                return rng.choice(R["addresses"])
            if ty == "bool":
                return rng.choice([False, True])
            if ty.startswith("uint"):
                v = rng.choice(uints) % (1 << _uint_bits(ty))
                if v not in uints:
                    uints.append(v)
                return v
            if ty.startswith("int"):
                v = rng.choice(uints) % (1 << (int(ty[3:] or 256) - 1))
                if v not in uints:
                    uints.append(v)
                return v
            if ty == "bytes":
                return rng.choice(R["bytes"])
            if ty.startswith("bytes"):
                return rng.choice(R["words"])[:2 + 2 * int(ty[5:])]
            raise InstrumentError(f"C3: no pool for the ABI type {ty}")
        steps = []
        for _ in range(R["steps"]):
            warp = rng.choice(R["warp"]["seconds"]) if rng.randrange(den) < num else 0
            m = rng.choice(members)
            a = rng.choice(ifaces[m]["actions"])
            caller = rng.choice(R["callers"])
            value = rng.choice(R["values"]) if a["payable"] else 0
            args = [arg(x) for x in a["inputs"]]
            st = {"call": {"to": m, "fn": a["signature"], "caller": caller, "value": value, "args": args}}
            if warp:
                st["warp"] = warp
            steps.append(st)
        out.append({"id": f"random/{t:03d}", "source": "random", "steps": steps})
    return out


def corpus_differences(corpus: dict, side: dict, ifaces: dict, m1_sha: str) -> list:
    """C3: what a corpus document and the rule disagree on (the m1 part against its pinned sha256, the seed part
    against the sidecar's traces verbatim, the random part against random_corpus, the sources counted)."""
    bad = []
    srcs = [tr["source"] for tr in corpus["traces"]]
    if srcs != sorted(srcs, key=lambda x: ("m1", "seed", "random").index(x)):
        bad.append("the traces are not m1, then seed, then random")
    counts = {k: srcs.count(k) for k in ("m1", "seed", "random")}
    if corpus.get("sources") != counts:
        bad.append(f"sources {corpus.get('sources')} are not the counted {counts}")
    m1 = [tr for tr in corpus["traces"] if tr["source"] == "m1"]
    if [tr["id"] for tr in m1] != [f"m1/{i:03d}" for i in range(len(m1))]:
        bad.append("the m1 ids are not m1/000.. in order")
    if any(set(st) != {"row"} for tr in m1 for st in tr["steps"]):
        bad.append("an m1 step is not a row")
    elif m1_sha256(corpus) != m1_sha:
        bad.append("the m1 part is not the pinned one")
    seed = {tr["id"]: tr["steps"] for tr in corpus["traces"] if tr["source"] == "seed"}
    if seed != {f"seed/{k}": v for k, v in side["corpus"]["seed"].items()}:
        bad.append("the seed part is not the sidecar's traces verbatim")
    rnd = [tr for tr in corpus["traces"] if tr["source"] == "random"]
    if rnd != random_corpus(side, ifaces):
        bad.append("the random part is not rule C3's")
    return bad


# ---------------------------------------------------------------------------------------------------- rule C6
def _target_selector(ifaces: dict, callee: str, kind: str, target: str) -> str:
    if kind == "receive":
        return "0x"
    if kind == "getter":
        return ifaces[callee]["getters"][target]
    sels = [a["selector"] for a in ifaces[callee]["actions"] if a["name"] == target]
    if len(sels) != 1:
        raise InstrumentError(f"link target {callee}.{target}: {len(sels)} actions")
    return sels[0]


def recount(steps_doc: dict, ifaces: dict, links: list) -> dict:
    """C6 from the per-step evidence (results/M3/bundle/steps.json), using the harness's frames only: traces and
    compared steps; frames_ok {member: {action: n}} (kept frames on a member whose selector is an action's);
    by_member_action {member: {action: {"ok", "revert"}}} (the top-level frame of every compared step); links_ok
    [[member, action, src, fn, n]] for every row of links, n the kept frames on the row's callee with the row's target
    selector whose parent frame is on the row's member with its action's selector."""
    names = {m: {a["selector"]: a["name"] for a in f["actions"]} for m, f in ifaces.items()}
    want = {}
    for r in links:
        key = (r[0], r[1], r[4], _target_selector(ifaces, r[4], r[5], r[6]))
        if key in want:
            raise InstrumentError(f"two link rows share (member, action, callee, selector) {key}")
        want[key] = r
    frames_ok, bma, lk = {}, {}, Counter()
    traces = set()
    compared = 0
    for st in steps_doc["steps"]:
        traces.add(st["trace"])
        fr = st.get("frames") or []
        for parent, _caller, callee, sel, _value, ok in fr:
            act = names.get(callee, {}).get(sel)
            if ok and act is not None:
                frames_ok.setdefault(callee, Counter())[act] += 1
            if ok and parent >= 0:
                p = fr[parent]
                pact = names.get(p[2], {}).get(p[3])
                if (p[2], pact, callee, sel) in want:
                    lk[(p[2], pact, callee, sel)] += 1
        if st.get("compared"):
            compared += 1
            top = [f for f in fr if f[0] < 0]
            if top:
                act = names.get(top[0][2], {}).get(top[0][3])
                if act is not None:
                    e = bma.setdefault(top[0][2], {}).setdefault(act, {"ok": 0, "revert": 0})
                    e["ok" if st.get("status") == "ok" else "revert"] += 1
    return {"traces": len(traces), "steps": compared,
            "frames_ok": {m: dict(sorted(c.items())) for m, c in sorted(frames_ok.items())},
            "by_member_action": {m: dict(sorted(v.items())) for m, v in sorted(bma.items())},
            "links_ok": sorted([*r[:4], lk[k]] for k, r in want.items())}


# ---------------------------------------------------------------------------------------------------- rule L2
def link_table(docs: dict, wiring: dict) -> list:
    """Rule L2's static link rows over the members' documents: every call record of every action whose receiver is
    ["storage", f] or ["immutable", f] with "<member>.<f>" in the wiring; the callee is the wired member, and the
    called function is, in the callee's document, an action of that name (kind action), else a storage family of
    that name (kind getter); a low-level "address.call" carrying a value and no data is the callee's receive (kind
    receive). Rows are (member, action, src, fn, callee, kind), sorted."""
    rows = []
    for m, doc in sorted(docs.items()):
        for a in doc["actions"]:
            for c in a.get("calls") or []:
                rcv = c.get("receiver")
                if not (isinstance(rcv, list) and len(rcv) == 2 and rcv[0] in ("storage", "immutable")):
                    continue
                callee = wiring.get(f"{m}.{rcv[1]}")
                if callee is None:
                    continue
                fn = c["fn"]
                cd = docs.get(callee)
                if fn.startswith("address."):
                    kind, target = "receive", "receive"
                else:
                    f = fn.split(".", 1)[1]
                    names = {x["name"] for x in cd["actions"]} if cd else set()
                    fams = {x["name"] for x in cd["storage"]} if cd else set()
                    kind = "action" if f in names else "getter" if f in fams else "unresolved"
                    target = f
                rows.append([m, a["name"], c["src"], fn, callee, kind, target])
    return sorted(rows)


# ---------------------------------------------------------------------------------------------------- rule C4
def _w(x: int) -> bytes:
    return int(x).to_bytes(32, "big")


def relay_leaf(frm: int, to: int, value: int, nonce: int, message: bytes) -> bytes:
    """keccak256 of abi.encodeWithSignature("relayMessage(address,address,uint256,uint256,bytes)", ...)."""
    body = _w(frm) + _w(to) + _w(value) + _w(nonce) + _w(160) + _w(len(message)) + message \
        + bytes((-len(message)) % 32)
    return keccak(bytes.fromhex(selector(RELAY_SIG)) + body)


def relay_root(leaf: bytes, nonce: int) -> bytes:
    """Verify.sol's fold with 32 zero siblings at index nonce."""
    node = leaf
    for h in range(32):
        node = keccak(bytes(32) + node) if (nonce >> h) & 1 else keccak(node + bytes(32))
    return node


def poke_slot(root_word: bytes, family_slot: int) -> bytes:
    return keccak(root_word + _w(family_slot))


# ---------------------------------------------------------------------------------------------------- A4-A6 on chain
def topic(sig: str) -> str:
    return "0x" + keccak(sig.encode()).hex()


def decode(receipt: dict, proxy: str, events: dict) -> dict:
    """The proxy's logs of a receipt, in log-index order: Upgraded implementations, Initialized versions and
    AdminChanged pairs; plus the receipt's from and contractAddress."""
    proxy = proxy.lower()
    up, ini, adm = [], [], []
    for lg in sorted(receipt["logs"], key=lambda x: int(x["logIndex"], 16)):
        if lg["address"].lower() != proxy or not lg["topics"]:
            continue
        t0 = lg["topics"][0].lower()
        data = lg["data"][2:]
        words = [data[i:i + 64] for i in range(0, len(data), 64)]
        if t0 == events["Upgraded"].lower():
            up.append("0x" + lg["topics"][1][-40:].lower())
        elif t0 == events["Initialized"].lower():
            ini.append(int(words[0], 16))
        elif t0 == events["AdminChanged"].lower():
            adm.append({"previous": "0x" + words[0][-40:], "new": "0x" + words[1][-40:]})
    return {"upgraded": up, "initialized": ini, "admin_changed": adm, "from": receipt["from"].lower(),
            "contract_address": (receipt.get("contractAddress") or "").lower() or None}


def match(entries: dict, code: bytes) -> list:
    """Every (key, config) of {key: {config: build}} whose identity the deployed code has under that build's ranges
    (I63's H7), sorted."""
    I = i63()
    hits = []
    for key, builds in sorted(entries.items()):
        for cname, b in sorted(builds.items()):
            if sha256_bytes(I.code_identity(code, b["ranges"])) == b["sha256"]:
                hits.append([key, cname])
    return hits


def words_at(code: bytes, ranges: list) -> list:
    return sorted({"0x" + code[s:s + n].hex() for s, n in ranges})


def _code(root: Path, side: dict, address: str) -> bytes:
    p = root / side["outputs"]["code"] / f"{address.lower()}.hex"
    if not p.is_file():
        raise InstrumentError(f"{p.relative_to(root)} is missing")
    return bytes.fromhex(p.read_text().strip())


def _low20(word: str) -> str:
    w = word.lower()[2:] if word.startswith("0x") else word.lower()
    if len(w) != 64 or int(w[:24] or "0", 16) != 0:
        raise InstrumentError(f"{word} is not an address word")
    return "0x" + w[-40:]


def timeline(root: Path = ROOT, bas: dict | None = None, ifaces: dict | None = None) -> dict:
    """A4-A6 recomputed from the committed snapshot, trusting none of holon's derived fields:
    - the snapshot's fetch block is at or after the window's end, and every log of a proxy lies in [the window's
      from_block, the fetch block], has the proxy's address and is unique by (block, log_index);
    - the proxies' addresses are the sidecar's (registry, submitter, queue), and the messenger's is the low 20 bytes
      of the MESSENGER word of the queue's last implementation in the window;
    - each proxy's upgrades are rebuilt from its raw logs whose topic 0 is Upgraded (the implementation is topic 1);
      for each, the committed receipt (results/M3/bundle/receipts/<tx>.json) has that transactionHash, blockNumber
      and status 0x1, and holds the log at its log index with the same address, topics and data; decoded (A4) from
      that receipt; matched (A5) on the committed code of the implementation;
    - the EIP-1967 implementation slot word the snapshot read at the fetch block names the implementation of the
      proxy's last Upgraded log at or before the fetch block (the scan's completeness at its end);
    - the whitelist's address is the low 20 bytes of the queue proxy's word at the queue's whitelistChecker slot
      (solc's layout at the head), and its committed code is matched against the Whitelist's head builds.
    Upgrades after the window's end are listed apart ("after_window"); P1 and P2 read the window's."""
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    bas = bas or load(root / "spec" / "M3" / "lib" / "bundle_basis.json")
    ifaces = ifaces or interfaces(root)
    snap = load(root / side["outputs"]["onchain"])
    acq = side["acquisition"]
    events = {k: v.lower() for k, v in acq["events"].items()}
    lo, hi = acq["window"]["from_block"], acq["window"]["to_block"]
    fb = snap["fetch_block"]
    if not isinstance(fb, int) or fb < hi:
        raise InstrumentError(f"the fetch block {fb} is before the window's end {hi}")
    if snap.get("window") != [lo, hi]:
        raise InstrumentError("the snapshot's window is not the sidecar's")
    if sorted(snap["proxies"]) != sorted(acq["proxies"]):
        raise InstrumentError(f"the snapshot's proxies {sorted(snap['proxies'])} are not the sidecar's")
    reg = {v["id"]: v["code"] for v in bas["registry"]["versions"]}
    mem = {m: x["builds"] for m, x in bas["members"].items()}
    out = {"fetch_block": fb, "window": [lo, hi], "proxies": {}}
    order = [n for n in ("registry", "submitter", "queue", "messenger") if n in snap["proxies"]]
    for pname in order:
        px = snap["proxies"][pname]
        want = acq["proxies"][pname].get("address")
        src = acq["proxies"][pname].get("immutable")
        if src:
            q = out["proxies"][src["member"]]["upgrades"]
            words = q[-1]["immutables"].get(src["name"]) if q and q[-1]["matches"] else None
            if not words or len(words) != 1:
                raise InstrumentError(f"the last implementation of {src['member']} in the window gives no single "
                                      f"{src['name']} word")
            want = _low20(words[0])
        if px["address"] != want:
            raise InstrumentError(f"proxy {pname}: the snapshot's address {px['address']} is not {want}")
        seen = set()
        for lg in px["logs"]:
            if not (lo <= lg["block"] <= fb):
                raise InstrumentError(f"proxy {pname}: a log at block {lg['block']} outside [{lo}, {fb}]")
            if (lg["block"], lg["log_index"]) in seen:
                raise InstrumentError(f"proxy {pname}: two logs at {(lg['block'], lg['log_index'])}")
            seen.add((lg["block"], lg["log_index"]))
            if lg.get("address", px["address"]).lower() != px["address"]:
                raise InstrumentError(f"proxy {pname}: a log of another address")
        raw = sorted((lg for lg in px["logs"] if lg["topics"] and lg["topics"][0].lower() == events["Upgraded"]),
                     key=lambda x: (x["block"], x["log_index"]))
        ups, after = [], []
        for lg in raw:
            impl = _low20(lg["topics"][1])
            rp = root / side["outputs"]["receipts"] / f"{lg['tx']}.json"
            if not rp.is_file():
                raise InstrumentError(f"{rp.relative_to(root)} is missing")
            rc = json.loads(rp.read_bytes())
            if (rc.get("transactionHash", "").lower() != lg["tx"].lower() or int(rc["blockNumber"], 16) != lg["block"]
                    or rc.get("status") != "0x1"):
                raise InstrumentError(f"{rp.relative_to(root)}: not the successful transaction of the log")
            same = [x for x in rc["logs"] if int(x["logIndex"], 16) == lg["log_index"]]
            if len(same) != 1 or same[0]["address"].lower() != px["address"] \
                    or [t.lower() for t in same[0]["topics"]] != [t.lower() for t in lg["topics"]] \
                    or same[0]["data"].lower() != lg["data"].lower():
                raise InstrumentError(f"{rp.relative_to(root)}: no log equal to the snapshot's at {lg['log_index']}")
            dec = decode(rc, px["address"], acq["events"])
            if impl not in dec["upgraded"]:
                raise InstrumentError(f"{lg['tx']}: the decoded Upgraded logs do not name {impl}")
            code = _code(root, side, impl)
            entries = reg if pname == "registry" else {pname: mem[pname]} if pname in mem else {}
            hits = match(entries, code)
            imm = {}
            if len(hits) == 1:
                b = entries[hits[0][0]][hits[0][1]]
                imm = {k: words_at(code, r) for k, r in b["immutables"].items()}
            u = {"block": lg["block"], "tx": lg["tx"].lower(), "log_index": lg["log_index"], "implementation": impl,
                 "decoded": dec, "matches": hits, "immutables": imm}
            (ups if lg["block"] <= hi else after).append(u)
        last = (ups + after)[-1]["implementation"] if ups + after else None
        slot = px.get("implementation_slot") or {}
        if slot.get("slot", "").lower() != acq["eip1967"]["implementation_slot"].lower() or slot.get("block") != fb:
            raise InstrumentError(f"proxy {pname}: no EIP-1967 implementation slot read at the fetch block")
        if _low20(slot["word"]) != last:
            raise InstrumentError(f"proxy {pname}: the implementation slot names {_low20(slot['word'])}, the scan's last "
                                  f"Upgraded log {last}")
        out["proxies"][pname] = {"address": px["address"], "upgrades": ups, "after_window": after, "current": last}
    wl = snap["whitelist"]
    so = acq["whitelist"]["slot_of"]
    qslot = slot_of(ifaces, so["member"], so["family"])
    if wl.get("slot") != qslot or wl.get("block") != fb or wl.get("proxy") != snap["proxies"][so["member"]]["address"]:
        raise InstrumentError(f"the whitelist word is not the {so['member']} proxy's slot {qslot} at the fetch block")
    if wl["address"] != _low20(wl["word"]):
        raise InstrumentError("the whitelist address is not its word's low 20 bytes")
    wcode = _code(root, side, wl["address"])
    out["whitelist"] = {"address": wl["address"], "matches": match({"whitelist": mem["whitelist"]}, wcode)}
    return out


# ---------------------------------------------------------------------------------------------------- A7 anchor read
RECEIPT_FIELDS = ("blockHash", "blockNumber", "contractAddress", "from", "gasUsed", "logs", "status", "to",
                  "transactionHash", "transactionIndex", "type")
LOG_FIELDS = ("address", "blockHash", "blockNumber", "data", "logIndex", "topics", "transactionHash",
              "transactionIndex")
QTY = {"blockNumber", "logIndex", "transactionIndex", "gas", "nonce", "type", "value", "status", "gasUsed"}


def _canon(obj: dict, fields: tuple) -> dict:
    out = {}
    for k in fields:
        v = obj.get(k)
        if k == "logs":
            v = [_canon(x, LOG_FIELDS) for x in (v or [])]
        elif k in QTY:
            v = None if v is None else hex(int(v, 16)) if isinstance(v, str) else v
        elif isinstance(v, str):
            v = v.lower()
        elif isinstance(v, list):
            v = [x.lower() if isinstance(x, str) else x for x in v]
        out[k] = v
    return out


def canon_receipt(obj: dict) -> bytes:
    """I59's canonical receipt bytes (holon/historical/store.py canon_bytes, written again): the receipt fields and
    log fields above, quantities without leading zeros, hex lowercased, compact JSON with sorted keys."""
    return json.dumps(_canon(obj, RECEIPT_FIELDS), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _rpc(url: str, method: str, params: list, tries: int = 4):
    import time
    import urllib.request
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    err = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={"content-type": "application/json",
                                                                  "user-agent": "holon-i69-instrument/0.1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read())
            if "error" in d:
                raise InstrumentError(f"{method}: {str(d['error'])[:200]}")
            return d["result"]
        except Exception as e:  # noqa: BLE001
            err = e
            time.sleep(1 + 2 * i)
    raise InstrumentError(f"{url} {method}: {err}")


def _logs(url: str, address: str, topics: list, lo: int, hi: int) -> list:
    """eth_getLogs of one address over [lo, hi] with topic 0 in topics, in adaptive chunks."""
    out, a, step = [], lo, 500000
    while a <= hi:
        b = min(hi, a + step - 1)
        try:
            got = _rpc(url, "eth_getLogs", [{"address": address, "topics": [topics], "fromBlock": hex(a),
                                             "toBlock": hex(b)}], tries=2)
        except InstrumentError:
            if step <= 1000:
                raise
            step //= 4
            continue
        out.extend(got)
        a = b + 1
        step = min(step * 2, 2000000)
    return out


def _log_row(lg: dict) -> dict:
    return {"block": int(lg["blockNumber"], 16), "tx": lg["transactionHash"].lower(),
            "log_index": int(lg["logIndex"], 16), "topics": [t.lower() for t in lg["topics"]],
            "data": lg["data"].lower()}


def second_read(root: Path = ROOT, host: str | None = None, log=None) -> dict:
    """A7: from the first host of the sidecar's rpc.second that answers (or `host`), read again what the committed
    snapshot says: each proxy's logs of the three topics over [the window's from_block, the snapshot's fetch block];
    every committed receipt (its canonical sha256); every committed code file's address at the latest block; each
    proxy's EIP-1967 implementation slot and the queue proxy's whitelist slot at the latest block (with that block)."""
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    acq = side["acquisition"]
    snap = load(root / side["outputs"]["onchain"])
    hosts = [host] if host else list(acq["rpc"]["second"])
    url = None
    for h in hosts:
        try:
            _rpc(h, "eth_blockNumber", [], tries=2)
            url = h
            break
        except InstrumentError:
            continue
    if url is None:
        raise InstrumentError("no host of rpc.second answers")
    latest = int(_rpc(url, "eth_blockNumber", []), 16)
    topics = sorted(v.lower() for v in acq["events"].values())
    lo, fb = acq["window"]["from_block"], snap["fetch_block"]
    doc = {"second_read_version": "holon-bundle-second-read/0.1", "host": url,
           "methods": ["eth_blockNumber", "eth_getCode", "eth_getLogs", "eth_getStorageAt",
                       "eth_getTransactionReceipt"],
           "fetch_block": fb, "latest_block": latest, "proxies": {}, "receipts": {}, "code": {}}
    for pname, px in sorted(snap["proxies"].items()):
        rows = sorted((_log_row(lg) for lg in _logs(url, px["address"], topics, lo, fb)),
                      key=lambda r: (r["block"], r["log_index"]))
        slot = _rpc(url, "eth_getStorageAt", [px["address"], acq["eip1967"]["implementation_slot"], hex(latest)])
        doc["proxies"][pname] = {"address": px["address"], "logs": rows, "implementation_slot_latest": slot.lower()}
        if log:
            log(f"{pname}: {len(rows)} logs")
    wl = snap["whitelist"]
    doc["whitelist_slot_latest"] = _rpc(url, "eth_getStorageAt", [wl["proxy"], hex(wl["slot"]), hex(latest)]).lower()
    for rp in sorted((root / side["outputs"]["receipts"]).glob("*.json")):
        rc = _rpc(url, "eth_getTransactionReceipt", [rp.stem])
        doc["receipts"][rp.stem] = sha256_bytes(canon_receipt(rc))
    for cp in sorted((root / side["outputs"]["code"]).glob("*.hex")):
        code = bytes.fromhex(_rpc(url, "eth_getCode", [cp.stem, hex(latest)])[2:])
        doc["code"][cp.stem] = {"sha256": sha256_bytes(code), "length": len(code)}
    return doc


def second_read_differences(root: Path = ROOT) -> list:
    """A7: the committed second read against the committed snapshot, receipts and code files: equal logs per proxy,
    receipt bytes hashing to the second read's canonical sha256, code files hashing to the second read's, and the
    slot words at the second read's latest block equal to the snapshot's at its fetch block. [] when they agree."""
    side = load(root / "spec" / "M3" / "lib" / "bundle.json")
    snap = load(root / side["outputs"]["onchain"])
    sr = load(root / side["outputs"]["second_read"])
    bad = []
    if sr.get("host") not in side["acquisition"]["rpc"]["second"]:
        bad.append(f"the second read's host {sr.get('host')} is not in rpc.second")
    if sr.get("fetch_block") != snap["fetch_block"]:
        bad.append("the second read is not over the snapshot's fetch block")
    for pname, px in sorted(snap["proxies"].items()):
        mine = sorted(({k: lg[k] for k in ("block", "tx", "log_index", "topics", "data")} for lg in px["logs"]),
                      key=lambda r: (r["block"], r["log_index"]))
        mine = [dict(r, tx=r["tx"].lower(), topics=[t.lower() for t in r["topics"]], data=r["data"].lower())
                for r in mine]
        other = (sr["proxies"].get(pname) or {})
        if other.get("logs") != mine:
            bad.append(f"proxy {pname}: the logs differ")
        if (other.get("implementation_slot_latest") or "").lower() != px["implementation_slot"]["word"].lower():
            bad.append(f"proxy {pname}: the implementation slot differs")
    if sr.get("whitelist_slot_latest", "").lower() != snap["whitelist"]["word"].lower():
        bad.append("the whitelist slot differs")
    rdir, cdir = root / side["outputs"]["receipts"], root / side["outputs"]["code"]
    if sorted(sr["receipts"]) != sorted(p.stem for p in rdir.glob("*.json")):
        bad.append("the second read's receipts are not the committed ones")
    for tx, sha in sorted(sr["receipts"].items()):
        p = rdir / f"{tx}.json"
        if p.is_file() and sha256_bytes(p.read_bytes()) != sha:
            bad.append(f"receipt {tx} differs")
    if sorted(sr["code"]) != sorted(p.stem for p in cdir.glob("*.hex")):
        bad.append("the second read's code files are not the committed ones")
    for a, c in sorted(sr["code"].items()):
        p = cdir / f"{a}.hex"
        if p.is_file() and sha256_bytes(bytes.fromhex(p.read_text().strip())) != c["sha256"]:
            bad.append(f"code {a} differs")
    return bad


def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i69")
    ap.add_argument("--write", action="store_true", help="recompute spec/M3/lib/bundle_basis.json (the prereg only)")
    ap.add_argument("--second-read", action="store_true", help="A7: write results/M3/bundle/second_read.json")
    ap.add_argument("--host", default=None, help="with --second-read: one host of the sidecar's rpc.second")
    a = ap.parse_args(argv)
    if a.write:
        b = basis(ROOT, log=lambda s: print(s, file=sys.stderr))
        BASIS.write_text(json.dumps(b, indent=1, sort_keys=True) + "\n")
        print(f"wrote {BASIS.relative_to(ROOT)}")
        return 0
    if a.second_read:
        side = load(SIDECAR)
        if a.host and a.host not in side["acquisition"]["rpc"]["second"]:
            print(f"{a.host} is not in the sidecar's rpc.second", file=sys.stderr)
            return 2
        doc = second_read(ROOT, a.host, log=lambda s: print(s, file=sys.stderr))
        out = ROOT / side["outputs"]["second_read"]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        print(f"wrote {out.relative_to(ROOT)}")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
