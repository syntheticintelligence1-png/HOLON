"""I80 instrument (= I37a: Bundle II's extraction and acquisition), fixed at the I80 prereg (BUILD_PLAN §0.1,
"instruments are inputs").

The contract is the docstring of tests_m3/test_bundle2_extraction.py (rules E1-E6, M1-M4, L1-L8, C1-C6, A1-A3). This
module writes the rules the tests decide a second time, independently of holon/: it never imports holon. It reads the
sidecar (spec/M3/lib/bundle2.json), config/holon.json (the pinned solc and Solidity dependencies), the target
repository's git objects (read-only, lazy fetching disabled: a missing object is an InstrumentError, never a fetch),
committed records of earlier keys (I63's receipt of the Rollup's initialization, the adopted Rollup document) and, after
the build, the committed documents and records. It reuses I63's instrument (tests_m3/_i63.py, fixed at I63's prereg)
for the toolchain check, the layout entries and the code identity, and tests_m2/_keccak.py for keccak256.

  git(repo, *args)                 read-only git, lazy fetching disabled (protocol.allow=never), no auto gc
  materialize(repo, commit, dest)  the commit's contracts/ tree written under dest (git archive; no checkout)
  ast_actions(root, unit, name, c) rule E1's action set over solc's AST: the action names of a contract
  interfaces(root)                 every member's solc ABI, actions with selectors, getters and storage layout
  structure(ifaces, member)        P1/P2's construction facts: action names, own families, inherited entries, constants
  link_table(docs, wiring)         rule L2 over documents: the static link rows
  public_input(docs, links)        rule E4 over documents: the argument views of the link rows into a COMMIT call
  cost_sites(docs)                 rule E5 over documents: every loop record, its count and whether it is a cost term
  anchor(root)                     A1: the verifier the Rollup's initialization receipt names
  tag_blobs(root)                  A2: the blobs of every member's units at every pinned tag and at the head
  head_builds(root)                A2: the members' head builds under I63's configurations (code identity, length)
  basis(root)                      the content of spec/M3/lib/bundle2_basis.json (A1-A2)
  random_corpus(side)              C3's random part, regenerated (random.Random(seed), the sidecar's draw order)
  recount(steps, ifaces, links)    C6 recounted from the per-step evidence: traces, steps, frames_ok,
                                   by_member_action and links_ok, from the harness's frames alone

  python -m tests_m3._i80 --write   recompute spec/M3/lib/bundle2_basis.json (only at the prereg)
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import random
import subprocess
import sys
import tarfile
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDECAR = ROOT / "spec" / "M3" / "lib" / "bundle2.json"
BASIS = ROOT / "spec" / "M3" / "lib" / "bundle2_basis.json"
ROW = 13


class InstrumentError(RuntimeError):
    """An input the rules refuse (a moved tag, a missing object, an unpinned toolchain, a receipt that is not I63's)."""


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


def side_of(root: Path = ROOT) -> dict:
    return load(root / "spec" / "M3" / "lib" / "bundle2.json")


# ---------------------------------------------------------------------------------------------------- git, read-only
def _git_env() -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", LC_ALL="C")
    return env


def git(repo: str, *args: str, binary: bool = False):
    """git with lazy fetching disabled: in a partial clone a missing object fails instead of being fetched from the
    target's origin (the I63 incident), and no automatic gc runs."""
    cmd = ["git", "-C", str(repo), "-c", "protocol.allow=never", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
           "-c", "core.fsmonitor=false", *args]
    p = subprocess.run(cmd, capture_output=True, env=_git_env(), stdin=subprocess.DEVNULL)
    if p.returncode != 0:
        raise InstrumentError(f"git {' '.join(args)}: {p.stderr.decode(errors='replace').strip()[:300]}")
    return p.stdout if binary else p.stdout.decode()


def repo_of(root: Path = ROOT) -> str:
    side = side_of(root)
    cfg = load(root / "config" / "holon.json")
    repo = (cfg.get("extract") or {}).get("sources", {}).get(side["target"]["repo"])
    if not repo or not Path(repo).is_dir():
        raise InstrumentError(f"config extract.sources has no checkout of {side['target']['repo']}")
    return repo


def materialize(repo: str, commit: str, dest: Path, paths=("contracts",)) -> None:
    data = git(repo, "archive", "--format=tar", commit, "--", *paths, binary=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        tf.extractall(dest, filter="data")


def _toolchain(root: Path) -> dict:
    cfg = load(root / "config" / "holon.json")
    i63().check_toolchain(cfg)
    return cfg


# ---------------------------------------------------------------------------------------------------- solc
def _solc_out(cfg: dict, tree: Path, unit: str, select: dict, settings: dict | None = None) -> dict:
    """solc --standard-json on one unit of a materialized tree (by default: no optimizer, cancun)."""
    text = (tree / unit).read_text(encoding="utf-8")
    st = dict(settings or {"evmVersion": "cancun", "optimizer": {"enabled": False}})
    st["outputSelection"] = select
    inp = json.dumps({"language": "Solidity", "sources": {unit: {"content": text}}, "settings": st})
    cmd = [cfg["replay"]["solc"], "--standard-json", "--base-path", ".", "--include-path",
           str(Path(cfg["replay"]["sol_deps"]) / "node_modules")]
    p = subprocess.run(cmd, input=inp, capture_output=True, text=True, cwd=str(tree), timeout=3600)
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


def _actions(out: dict, name: str) -> list:
    """Rule E1's action set over a solc output's AST: [(name, selector or None, kind, declaring contract)], most derived
    first: every external or public FunctionDefinition with a body (kinds function, receive, fallback) of the contract
    and its bases, one per selector (receive and fallback by kind)."""
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
    return acts


def ast_actions(root: Path, unit: str, name: str, commit: str) -> list:
    """The sorted action names of a contract at a commit (its tree materialized from git objects), by _actions."""
    cfg = _toolchain(root)
    repo = repo_of(root)
    with tempfile.TemporaryDirectory(prefix="i80-ast-") as td:
        tree = Path(td) / "t"
        tree.mkdir()
        materialize(repo, commit, tree)
        out = _solc_out(cfg, tree, unit, {"*": {"": ["ast"]}})
    return sorted(n for n, _, _, _ in _actions(out, name))


def _abi_type(x: dict) -> str:
    t = x["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(_abi_type(c) for c in x["components"]) + ")" + t[len("tuple"):]
    return t


def member_commit(root: Path, m: dict) -> str:
    return load(root / m["document"])["target"]["commit"] if m.get("adopted") else m["commit"]


def interfaces(root: Path = ROOT) -> dict:
    """{member: {"contract", "commit", "actions", "getters", "layout", "own", "constants"}} for every member and
    extracted_only member of the sidecar, from the pinned solc at the member's commit (tree from git objects):
    actions: _actions sorted by name, each {"name", "selector" ("0x" + 8 hex; "0x" for receive and fallback), "kind",
    "signature", "payable", "inputs", "outputs", "declared_in"}; getters: {name: selector} of the ABI functions that
    are no action (public state variables' getters); layout: I63's layout entries (with the declaring contract); own:
    the contract's own non-constant, non-immutable state variables in declaration order; constants: {name: the
    literal's value as a decimal string, or None when the initializer is not a number literal} of its own constants."""
    side = side_of(root)
    cfg = _toolchain(root)
    repo = repo_of(root)
    by_commit: dict = {}
    for m in side["members"] + side["extracted_only"]:
        by_commit.setdefault(member_commit(root, m), []).append(m)
    out = {}
    with tempfile.TemporaryDirectory(prefix="i80-if-") as td:
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
                for n, sel, kind, decl in _actions(o, name):
                    sig, e = abi["0x" + sel] if sel else abi[kind]
                    acts.append({"name": n, "selector": "0x" + sel if sel else "0x", "kind": kind, "signature": sig,
                                 "payable": e.get("stateMutability") == "payable", "inputs": e.get("inputs") or [],
                                 "outputs": e.get("outputs") or [], "declared_in": decl})
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
    """The construction facts of one document from solc: action names, the own families in declaration order, the
    number of inherited layout entries and the own constants."""
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


# ---------------------------------------------------------------------------------------------------- rule L2
def link_table(docs: dict, wiring: dict) -> list:
    """Rule L2's static link rows over the members' documents: every call record of every action whose receiver is
    ["storage", f] or ["immutable", f] with "<member>.<f>" in the wiring; the callee is the wired member, and the
    called function is, in the callee's document, an action of that name (kind action), else a storage family of
    that name (kind getter); a low-level "address.<kind>" call is the callee's receive (kind receive). Rows are
    [member, action, src, fn, callee, kind, target], sorted."""
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


# ---------------------------------------------------------------------------------------------------- rule E4
def _view(t):
    if isinstance(t, list) and len(t) == 3 and t[0] == "word" and isinstance(t[1], list) and len(t[1]) == 2 \
            and t[1][0] == "param" and isinstance(t[2], int):
        return {"input": t[1][1], "from": t[2], "length": 32}
    if isinstance(t, list) and len(t) == 3 and t[0] == ">>" and isinstance(t[2], int) and 0 < t[2] < 256 \
            and t[2] % 8 == 0:
        inner = _view(t[1])
        if "input" in inner and inner["length"] == 32:
            return {"input": inner["input"], "from": inner["from"], "length": (256 - t[2]) // 8}
        return {"term": t}
    if isinstance(t, list) and len(t) == 2 and t[0] == "param":
        return {"param": t[1]}
    if isinstance(t, list) and len(t) == 2 and t[0] == "immutable":
        return {"immutable": t[1]}
    if isinstance(t, list) and len(t) == 2 and t[0] == "keccak256" and isinstance(t[1], list) \
            and t[1][:1] == ["abi.encodePacked"]:
        return {"hash": "keccak256", "packed": [_view(x) for x in t[1][1:]]}
    return {"term": t}


def public_input(docs: dict, links: list) -> list:
    """Rule E4: for every link row of kind action whose call record is a COMMIT edge (its "commit" is true), the views
    of the call's argument terms (_view: a 32-byte word of an input at an offset, its leading bytes by a right shift,
    a parameter, an immutable, a keccak256 of abi.encodePacked components, else the term itself). Rows
    {"member", "action", "src", "fn", "args"}, in link order."""
    out = []
    for m, a, src, fn, _callee, kind, _target in links:
        if kind != "action":
            continue
        act = next(x for x in docs[m]["actions"] if x["name"] == a)
        recs = [c for c in act.get("calls") or [] if c["src"] == src and c["fn"] == fn and c.get("commit")]
        for c in recs[:1]:
            out.append({"member": m, "action": a, "src": src, "fn": fn, "args": [_view(x) for x in c.get("args") or []]})
    return out


# ---------------------------------------------------------------------------------------------------- rule E5
def cost_sites(docs: dict) -> list:
    """Rule E5: one row per loop record of every action of every member document: [member, action, loop src, the
    record's seq, whether a cost term of the action names the loop's span, the record's count term], sorted by member,
    action and seq."""
    rows = []
    for m, doc in sorted(docs.items()):
        for a in sorted(doc["actions"], key=lambda x: x["name"]):
            spans = {t.get("loop") for t in (a.get("cost") or {}).get("terms") or []}
            for lp in sorted(a.get("loops") or [], key=lambda x: x["seq"]):
                rows.append([m, a["name"], lp["src"], lp["seq"], lp["src"] in spans, lp.get("count")])
    return rows


# ---------------------------------------------------------------------------------------------------- A1-A2
def anchor(root: Path = ROOT) -> dict:
    """A1: the Rollup proxy's UpdateVerifier(address,address) logs in I63's committed receipt of its initialization:
    [{"emitter", "old", "new", "block"}], and the receipt's sha256."""
    side = side_of(root)
    a = side["acquisition"]["anchor"]
    p = root / a["receipt"]
    rc = load(p)
    rc = rc.get("receipt", rc)
    t0 = "0x" + keccak(a["event"].encode()).hex()
    logs = []
    for lg in rc.get("logs") or []:
        if lg.get("topics") and lg["topics"][0].lower() == t0:
            logs.append({"emitter": lg["address"].lower(), "old": "0x" + lg["topics"][1][-40:].lower(),
                         "new": "0x" + lg["topics"][2][-40:].lower(), "block": int(lg["blockNumber"], 16)})
    return {"receipt": a["receipt"], "receipt_sha256": sha256_bytes(p.read_bytes()), "logs": logs}


def tag_blobs(root: Path = ROOT) -> dict:
    """A2: {ref: {member: {unit: blob or None}}} over the sidecar's pinned tags (checked at their pins) and "head", from
    the refs' trees (git ls-tree; no blob is read)."""
    side = side_of(root)
    repo = repo_of(root)
    acq = side["acquisition"]
    refs = dict(acq["tags"])
    for t, c in sorted(refs.items()):
        got = git(repo, "rev-parse", "--verify", "-q", f"{t}^{{commit}}").strip()
        if got != c:
            raise InstrumentError(f"tag {t} is at {got}, not its pin {c}")
    refs["head"] = side["target"]["head"]
    out = {}
    for ref, c in sorted(refs.items()):
        out[ref] = {}
        for m, units in sorted(acq["units"].items()):
            rows = git(repo, "ls-tree", c, "--", *units).splitlines()
            have = {ln.split("\t", 1)[1]: ln.split()[2] for ln in rows if ln.strip()}
            out[ref][m] = {u: have.get(u) for u in units}
    return out


def head_builds(root: Path = ROOT, log=None) -> dict:
    """A2: every member's (and extracted_only member's) head build under every configuration of the sidecar (I63's
    three): {member: {config: {"sha256": I63's code identity, "length", "ranges"}}}."""
    side = side_of(root)
    acq = side["acquisition"]
    cfg = _toolchain(root)
    repo = repo_of(root)
    out = {}
    with tempfile.TemporaryDirectory(prefix="i80-head-") as td:
        tree = Path(td) / "head"
        tree.mkdir()
        materialize(repo, side["target"]["head"], tree)
        for m in sorted([x for x in side["members"] if not x.get("adopted")] + side["extracted_only"],
                        key=lambda x: x["name"]):
            unit, name = m["source"], m["contract"]
            out[m["name"]] = {}
            for cname, conf in sorted(acq["compiler_configs"].items()):
                b = i63().build({"contract": {"source": unit, "name": name}}, cfg, tree, conf)
                code = bytes.fromhex(b["code"])
                out[m["name"]][cname] = {"sha256": sha256_bytes(i63().code_identity(code, b["ranges"])),
                                         "length": len(code), "ranges": b["ranges"]}
            if log:
                log(f"{m['name']}: {out[m['name']]['hardhat']['sha256'][:12]}")
    return out


def basis(root: Path = ROOT, log=None) -> dict:
    return {"basis_version": "holon-bundle2-basis/0.1",
            "sidecar_sha256": sha256_bytes((root / "spec" / "M3" / "lib" / "bundle2.json").read_bytes()),
            "anchor": anchor(root), "tags": tag_blobs(root), "builds": head_builds(root, log)}


# ---------------------------------------------------------------------------------------------------- rule C3
def random_corpus(side: dict) -> list:
    """C3's random part: random.Random(seed); per trace the prefix rows, then per step op = rng.choice(sorted ops as
    ints), then one rng.choice per field of the op from its pool; rows zero-padded to 13 words."""
    rp = side["corpus"]["random"]
    rng = random.Random(rp["seed"])
    ops = sorted(int(k) for k in rp["ops"])
    out = []
    for _ in range(rp["traces"]):
        tr = [list(r) for r in rp["prefix"]]
        for _ in range(rp["steps"]):
            op = rng.choice(ops)
            row = [op] + [rng.choice(rp["pools"][f]) for f in rp["ops"][str(op)]]
            tr.append(row + [0] * (ROW - len(row)))
        out.append(tr)
    return out


# ---------------------------------------------------------------------------------------------------- rule C6
def recount(steps_doc: dict, ifaces: dict, links: list) -> dict:
    """C6 from the per-step evidence (results/M3/bundle2/steps.json; each step {"trace", "compared", "status",
    "frames": [[parent, callee, selector, persisted]...]} with parent -1 for the top frame), from the harness's frames
    alone: traces and compared steps; frames_ok {member: {action: n}} (persisted frames on a member whose selector is an
    action's); by_member_action {member: {action: {"ok", "revert"}}} (the top frame of every compared step);
    links_ok [[member, action, src, fn, n]] for every row of links: n the persisted frames on the row's callee with the
    row's target selector whose parent frame is on the row's member with its action's selector."""
    names = {m: {a["selector"]: a["name"] for a in f["actions"]} for m, f in ifaces.items()}

    def target_sel(callee, kind, target):
        if kind == "receive":
            return "0x"
        if kind == "getter":
            return ifaces[callee]["getters"][target]
        s = [a["selector"] for a in ifaces[callee]["actions"] if a["name"] == target]
        if len(s) != 1:
            raise InstrumentError(f"link target {callee}.{target}: {len(s)} actions")
        return s[0]
    want = {}
    for r in links:
        key = (r[0], r[1], r[4], target_sel(r[4], r[5], r[6]))
        if key in want:
            raise InstrumentError(f"two link rows share (member, action, callee, selector) {key}")
        want[key] = r
    frames_ok, bma, lk = {}, {}, Counter()
    traces, compared = set(), 0
    for st in steps_doc["steps"]:
        traces.add(st["trace"])
        fr = st.get("frames") or []
        for parent, callee, sel, ok in fr:
            act = names.get(callee, {}).get(sel)
            if ok and act is not None:
                frames_ok.setdefault(callee, Counter())[act] += 1
            if ok and parent >= 0:
                p = fr[parent]
                pact = names.get(p[1], {}).get(p[2])
                if (p[1], pact, callee, sel) in want:
                    lk[(p[1], pact, callee, sel)] += 1
        if st.get("compared"):
            compared += 1
            top = [f for f in fr if f[0] < 0]
            if top:
                act = names.get(top[0][1], {}).get(top[0][2])
                if act is not None:
                    e = bma.setdefault(top[0][1], {}).setdefault(act, {"ok": 0, "revert": 0})
                    e["ok" if st.get("status") == "ok" else "revert"] += 1
    return {"traces": len(traces), "steps": compared,
            "frames_ok": {m: dict(sorted(c.items())) for m, c in sorted(frames_ok.items())},
            "by_member_action": {m: dict(sorted(v.items())) for m, v in sorted(bma.items())},
            "links_ok": sorted([*r[:4], lk[k]] for k, r in want.items())}


# ---------------------------------------------------------------------------------------------------- main
def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="python -m tests_m3._i80")
    ap.add_argument("--write", action="store_true", help="recompute spec/M3/lib/bundle2_basis.json")
    a = ap.parse_args(argv)
    if not a.write:
        ap.print_help()
        return 2
    b = basis(ROOT, log=lambda s: print(s, file=sys.stderr))
    BASIS.write_text(json.dumps(b, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {BASIS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
