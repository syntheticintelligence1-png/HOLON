"""I84's instrument (= I37b: Bundle II's laws over I80's extraction). The contract is the docstring of
tests_m3/test_bundle2_laws.py; this module writes its rules a second time, independently of holon/ (it imports nothing
from holon/), over the committed documents, I80's declaration, the target's git objects (read with lazy fetching
disabled) and the build's records:

  basis(root)                the construction facts the prereg fixes (spec/M3/lib/bundle2_laws_basis.json): the deploy
                             script's router configuration (rule LD1), the consumers (FC1-FC3), the public-input views
                             (E4), the field classes and their measures (FM1-FM3), the state-indexed cost sites (D1),
                             the gas ceiling and the expected law ids (N1)
  resolve(...)               the router's getVerifier, as MultipleVersionRollupVerifier.sol:99-122 reads (rule LD2)
  fit / errors / kstar       the calibration (K3-K4) and the least backlog out of En_G (D2), in exact rationals
  intrinsic(calldata)        a Cancun transaction's intrinsic gas (EIP-2028)

Nothing here runs holon, forge or Bend.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from fractions import Fraction
from pathlib import Path

SIDE_REL = "spec/M3/lib/bundle2_laws.json"
BASIS_REL = "spec/M3/lib/bundle2_laws_basis.json"
BASIS_VERSION = "holon-bundle2-laws-basis/0.1"
HEADER_INPUT = "_batchHeader"
STORE_OPS = ("mstore", "mstore8")


# ------------------------------------------------------------------------------------------------ reading
def load(root: Path, rel: str):
    return json.loads((Path(root) / rel).read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def target_repo(root: Path) -> Path:
    cfg = load(root, "config/holon.json")
    return Path(cfg["extract"]["sources"]["morph-l2/morph"])


def git_blob(repo: Path, commit: str, path: str) -> bytes:
    """A blob of the target at a commit, read from its objects only (no fetch, no promisor read)."""
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    p = subprocess.run(["git", "-C", str(repo), "-c", "protocol.allow=never", "show", f"{commit}:{path}"],
                       capture_output=True, env=env)
    if p.returncode != 0:
        raise ValueError(f"git show {commit[:12]}:{path}: {p.stderr.decode(errors='replace').strip()}")
    return p.stdout


def git_blob_id(repo: Path, commit: str, path: str) -> str:
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C"}
    p = subprocess.run(["git", "-C", str(repo), "-c", "protocol.allow=never", "rev-parse", f"{commit}:{path}"],
                       capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise ValueError(f"git rev-parse {commit[:12]}:{path}: {p.stderr.strip()}")
    return p.stdout.strip()


# ------------------------------------------------------------------------------------------------ terms
def is_op(t, op: str | None = None) -> bool:
    return isinstance(t, list) and bool(t) and isinstance(t[0], str) and (op is None or t[0] == op)


def subterms(t):
    yield t
    if isinstance(t, list):
        for x in t:
            yield from subterms(x)
    elif isinstance(t, dict):
        for x in t.values():
            yield from subterms(x)


def member_ref(t):
    """(param, member) of ["member", ["param", P], m], else None."""
    if is_op(t, "member") and len(t) == 3 and is_op(t[1], "param") and isinstance(t[2], str):
        return (t[1][1], t[2])
    return None


def mentions(t, ref) -> bool:
    return any(member_ref(x) == ref for x in subterms(t))


HASH_HEADS = ("keccak256", "sha256")


def reads_value(t, ref) -> bool:
    """The member ref occurs in t outside every hash preimage: a check that holds it only inside a keccak256 or sha256
    term binds it to that hash's other side (under CF), never to a value, so it does not constrain the member."""
    if member_ref(t) == ref:
        return True
    if is_op(t) and t[0] in HASH_HEADS:
        return False
    if isinstance(t, list):
        return any(reads_value(x, ref) for x in t)
    if isinstance(t, dict):
        return any(reads_value(x, ref) for x in t.values())
    return False


_ATOM_HEADS = ("storage", "env", "param", "call", "blobhash", "word", "byte", "map", "immutable", "count", "iter")


def atoms(t) -> set:
    """The non-literal leaves a term reads: member refs (not descended into), storage, env, params, calls, blobhash,
    word and byte reads, abstract counts."""
    out = set()

    def go(x):
        r = member_ref(x)
        if r is not None:
            out.add(("member",) + r)
            return
        if is_op(x) and x[0] in _ATOM_HEADS:
            out.add((x[0], json.dumps(x[1:], sort_keys=True)))
            return
        if isinstance(x, list):
            for y in x:
                go(y)
        elif isinstance(x, dict):
            for y in x.values():
                go(y)

    go(t)
    return out


_CMP = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        "==": lambda a, b: a == b, "!=": lambda a, b: a != b}


def evaluate(t, ref, value: int):
    """t with every occurrence of the member ref replaced by value; ints, comparisons, + - and the boolean
    connectives. Raises ValueError on anything else."""
    if isinstance(t, bool):
        return t
    if isinstance(t, int):
        return t
    if member_ref(t) == ref:
        return value
    if is_op(t):
        op, args = t[0], t[1:]
        if op in _CMP:
            return _CMP[op](evaluate(args[0], ref, value), evaluate(args[1], ref, value))
        if op == "!":
            return not evaluate(args[0], ref, value)
        if op == "&&":
            return all(evaluate(a, ref, value) for a in args)
        if op == "||":
            return any(evaluate(a, ref, value) for a in args)
        if op == "+":
            return sum(evaluate(a, ref, value) for a in args)
        if op == "-":
            return evaluate(args[0], ref, value) - evaluate(args[1], ref, value)
    raise ValueError(f"not evaluable: {json.dumps(t)[:120]}")


# ------------------------------------------------------------------------------------------------ actions
def actions(doc: dict) -> dict:
    return {a["name"]: a for a in doc["actions"]}


def header_images(a: dict) -> list:
    """The memory images of the headers an action commits: the mem term of every write whose value is
    keccak256(slice(mem(...), ..)) (the committed header, rule FM1)."""
    out = []
    for w in a.get("writes") or []:
        v = w.get("value")
        if is_op(v, "keccak256") and is_op(v[1], "slice") and is_op(v[1][1], "mem"):
            out.append(v[1][1])
    return out


def store_at(image, offset: int):
    """(op, value) of the store at offset in a mem image (inside `when` guards too), else None."""
    for x in subterms(image):
        if is_op(x) and x[0] in STORE_OPS and len(x) == 3 and x[1] == offset:
            return (x[0], x[2])
    return None


def checks_of(a: dict) -> list:
    """Every check and guard expression of an action except the ABI decoder's range checks (kind abi)."""
    out = []
    for sec in ("checks", "guards"):
        for r in a.get(sec) or []:
            if r.get("kind") == "abi":
                continue
            if "expr" in r:
                out.append(r["expr"])
    return out


def field_class(doc: dict, offset: int, width: int) -> dict:
    """Rule FM1-FM3 for a consumer field at (offset, width bytes) of a committed header: over every action that commits
    a header image, the stored value at offset. An input member (mstore8 of it, or an mstore of it shifted left by
    256 - 8 * width) is free when no non-ABI check of the action reads its value (outside a hash preimage: reads_value),
    F = 8 * width bits; checked when some do, with the admitted values those closed in it allow (width <= 2:
    enumerated), exact when every such check is closed in it and a bound [1, log2 |admitted|] when one reads it jointly
    with other atoms; anything else is computed (F within [1, 8 * width])."""
    bits = 8 * width
    seen = []
    for name, a in sorted(actions(doc).items()):
        for img in header_images(a):
            st = store_at(img, offset)
            if st is None:
                continue
            op, val = st
            ref = None
            if op == "mstore8" and width == 1:
                ref = member_ref(val)
            elif op == "mstore" and is_op(val, "<<") and len(val) == 3 and val[2] == 256 - bits:
                ref = member_ref(val[1])
            elif op == "mstore" and bits == 256:
                ref = member_ref(val)
            if ref is None:
                seen.append({"action": name, "class": "computed"})
                continue
            reading = [e for e in checks_of(a) if reads_value(e, ref)]
            if not reading:
                seen.append({"action": name, "class": "free", "member": list(ref)})
                continue
            closed = [e for e in reading if atoms(e) == {("member",) + ref}]
            joint = [e for e in reading if atoms(e) != {("member",) + ref}]
            if width > 2:
                seen.append({"action": name, "class": "checked_wide", "member": list(ref)})
                continue
            admitted = [v for v in range(1 << bits) if all(evaluate(e, ref, v) for e in closed)]
            seen.append({"action": name, "class": "checked_joint" if joint else "checked", "member": list(ref),
                         "admitted": admitted})
    classes = sorted({s["class"] for s in seen})
    if not seen:
        return {"class": "absent", "kind": "bound", "lower": 1.0, "upper": float(bits), "actions": []}
    acts = sorted(s["action"] for s in seen)
    if classes == ["free"]:
        return {"class": "free", "kind": "value", "value": float(bits), "lower": float(bits), "upper": float(bits),
                "actions": acts}
    if classes == ["checked"] and len({tuple(s["admitted"]) for s in seen}) == 1:
        n = len(seen[0]["admitted"])
        v = round(math.log2(n), 6) if n else 0.0
        return {"class": "checked", "kind": "value", "value": v, "lower": v, "upper": v, "actions": acts,
                "admitted": seen[0]["admitted"]}
    if set(classes) <= {"checked", "checked_joint"}:
        n = max(len(s["admitted"]) for s in seen)
        return {"class": "checked_joint", "kind": "bound", "lower": 1.0, "upper": round(math.log2(n), 6),
                "actions": acts, "admitted": sorted({v for s in seen for v in s["admitted"]})}
    return {"class": "computed" if classes == ["computed"] else "mixed", "kind": "bound", "lower": 1.0,
            "upper": float(bits), "actions": acts}


# ------------------------------------------------------------------------------------------------ consumers
def consumers(root: Path, side: dict) -> list:
    """Rule FC1-FC2: the derivation document's call edges whose callee is a decoder of the codec document of the
    sidecar's header codec, one entry per decoder (sorted by getter), with its read (offset, width, via) and the edges
    (caller, site) that reach it."""
    dd = load(root, side["inputs"]["derivation_document"])
    cd = load(root, side["inputs"]["codec_document"])
    codec = side["consumers"]["codec"]
    reads = {}
    for dec in cd["go"]["codecs"]["decoders"]:
        f = dec["function"]
        if f.startswith(codec + ".") and len(dec.get("reads") or []) == 1:
            reads[f] = dec["reads"][0]
    out = {}
    for e in dd["go"]["calls"]["edges"]:
        f = e.get("callee")
        if f in reads:
            g = f[len(codec) + 1:]
            ent = out.setdefault(g, {"getter": g, "function": f, "offset": reads[f]["offset"],
                                     "width": reads[f]["width"], "via": reads[f]["via"], "edges": []})
            ent["edges"].append({"caller": e["caller"], "site": e["site"]})
    for ent in out.values():
        ent["edges"] = sorted(ent["edges"], key=lambda x: (x["caller"], x["site"]))
    return [out[g] for g in sorted(out)]


def receiver_sites(root: Path, side: dict) -> list:
    """Rule FC3: each stated receiver site's line, read from the target's git objects at the pinned commit, equals the
    sidecar's text, and is the file's only BatchHeaderBytes( construction."""
    repo = target_repo(root)
    commit = side["deployment"]["router"]["source"]["commit"]
    out = []
    for s in side["consumers"]["receiver"]["sites"]:
        text = git_blob(repo, commit, s["path"]).decode("utf-8")
        lines = text.split("\n")
        out.append({"function": s["function"], "path": s["path"], "line": s["line"],
                    "matches": lines[s["line"] - 1] == s["text"],
                    "constructions": sum(ln.count("BatchHeaderBytes(") for ln in lines),
                    "blob": git_blob_id(repo, commit, s["path"])})
    return out


# ------------------------------------------------------------------------------------------------ deploy script
def deploy_script(root: Path, side: dict) -> dict:
    """Rule LD1: the router's constructor arguments as the target's deploy script writes them (the stated lines, read
    from the git objects; the versions are the integer list literal)."""
    src = side["deployment"]["router"]["source"]
    repo = target_repo(root)
    lines = git_blob(repo, src["commit"], src["path"]).decode("utf-8").split("\n")
    v, w, d = (lines[n - 1] for n in src["lines"])
    lit = v.split("=", 1)[1].strip()
    versions = json.loads(lit)
    return {"path": src["path"], "commit": src["commit"], "blob": git_blob_id(repo, src["commit"], src["path"]),
            "lines": src["lines"], "versions": versions,
            "matches": [v == src["versions_line"], w == src["verifiers_line"], d == src["deploy_line"]],
            "verifiers": w.split("=", 1)[1].strip()}


# ------------------------------------------------------------------------------------------------ E4 and links
def header_ranges(args) -> list:
    """The [from, to) ranges of the header input that the view's arguments read, recursively through hashes."""
    out = set()
    for x in subterms(args):
        if isinstance(x, dict) and x.get("input") == HEADER_INPUT and isinstance(x.get("from"), int):
            out.add((x["from"], x["from"] + x["length"]))
    return sorted(out)


def pi_rows(decl: dict) -> list:
    """Rule E4's rows, with the ranges their hash argument (the PI) reads and the ranges every argument reads."""
    out = []
    for r in decl["public_input"]:
        hashes = [a for a in r["args"] if isinstance(a, dict) and a.get("hash")]
        out.append({"member": r["member"], "action": r["action"], "src": r["src"], "fn": r["fn"],
                    "pi": header_ranges(hashes), "all": header_ranges(r["args"]),
                    "pi_immutables": sorted({x["immutable"] for x in subterms(hashes)
                                             if isinstance(x, dict) and "immutable" in x})})
    return out


def link_rows(decl: dict) -> list:
    return [r for r in decl["links"] if r[5] == "action"]


def state_cost_sites(decl: dict) -> list:
    """Rule D1: E5's rows whose count term reads storage only (no parameter, input, env or abstract count)."""
    out = []
    for r in decl["cost_sites"]:
        at = atoms(r[5])
        if at and all(a[0] == "storage" for a in at) and not any(is_op(x, "count") for x in subterms(r[5])):
            out.append(r)
    return out


# ------------------------------------------------------------------------------------------------ law ids (N1)
def lines_tag(src: str) -> str:
    return src.rsplit(":", 1)[1].replace("-", "_")


def law_ids(root: Path, side: dict, decl: dict, cons: list) -> dict:
    members = {m["name"]: m["contract"] for m in decl["members"]}
    ldom = sorted(f"L_par_ldom_{members[r[0]]}_{r[1]}_{members[r[4]]}_{r[6]}" for r in link_rows(decl))
    rdoc = load(root, side["inputs"]["rollup_document"])
    member = side["consumers"]["receiver"]["solidity_member"]
    pi = []
    for row in pi_rows(decl):
        a = actions(rdoc)[row["action"]]
        has = any(member in [f["name"] for f in (p.get("fields") or [])] or p["name"] == member
                  for p in a.get("params") or [])
        if has:
            pi += [f"L_fact_pi_{members[row['member']]}_{row['action']}_{c['getter']}" for c in cons]
    disch = sorted(f"L_disch_self_{members[r[0]]}_{r[1]}_{lines_tag(r[2])}" for r in state_cost_sites(decl))
    return {"link_domain": ldom, "public_input": sorted(pi), "self_controlled": disch}


# ------------------------------------------------------------------------------------------------ LD2: the router
def resolve(latest: dict, legacy: dict, version: int, index: int):
    """getVerifier(version, index): the latest verifier when its start is at most index, else the last legacy entry
    whose start is at most index; None when none is (ErrorVerifierNotFound). latest: {version: (start, verifier)},
    legacy: {version: [(start, verifier), ..]} in push order; an unset version reads (0, 0)."""
    start, ver = latest.get(version, (0, 0))
    if start > index:
        for s, v in reversed(legacy.get(version, [])):
            if s <= index:
                return v
        return None
    return ver


def in_domain(latest: dict, legacy: dict, version: int, index: int) -> bool:
    v = resolve(latest, legacy, version, index)
    return v is not None and v != 0


# ------------------------------------------------------------------------------------------------ K: calibration
def intrinsic(calldata: bytes) -> int:
    return 21000 + sum(4 if b == 0 else 16 for b in calldata)


def fit(points: dict, ks: list) -> tuple:
    """Ordinary least squares of cost on iters over ks: (c0, c1) as Fractions."""
    xs = [Fraction(points[k]["iters"]) for k in ks]
    ys = [Fraction(points[k]["cost"]) for k in ks]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    c1 = sxy / sxx
    return my - c1 * mx, c1


def errors(c0, c1, points: dict, ks: list) -> dict:
    """{k: |c0 + c1 * iters - cost| / cost} as Fractions."""
    out = {}
    for k in ks:
        y = Fraction(points[k]["cost"])
        out[k] = abs(c0 + c1 * Fraction(points[k]["iters"]) - y) / y
    return out


def kstar(c0, c1, ceiling: int) -> int | None:
    """The least integer k >= 0 with c0 + c1 * k > ceiling (None when c1 <= 0 and c0 <= ceiling)."""
    c0, c1 = Fraction(c0), Fraction(c1)
    if c0 > ceiling:
        return 0
    if c1 <= 0:
        return None
    k = (Fraction(ceiling) - c0) / c1
    n = math.floor(k) + 1
    return max(n, 0)


# ------------------------------------------------------------------------------------------------ basis
def basis(root: Path) -> dict:
    root = Path(root)
    side = load(root, SIDE_REL)
    decl = load(root, side["inputs"]["declaration"])
    rdoc = load(root, side["inputs"]["rollup_document"])
    cons = consumers(root, side)
    classes = {c["getter"]: field_class(rdoc, c["offset"], c["width"]) for c in cons}
    refute = load(root, side["gas"]["ceiling"]["from"])
    out = {
        "basis_version": BASIS_VERSION,
        "sidecar_sha256": sha256_file(root / SIDE_REL),
        # the declaration and the router's document are regenerated by I84's build (the frontend's loop rule moves the
        # router's document, and the declaration names its sha256), and I40's refute sidecar is a live sidecar: the
        # basis reads only their stable sections and the gas ceiling's value
        "inputs_sha256": {p: sha256_file(root / p) for p in sorted(set(side["inputs"].values()))
                          if p not in (side["inputs"]["declaration"], side["inputs"]["router_document"],
                                       side["inputs"]["refute_sidecar"])},
        "deploy_script": deploy_script(root, side),
        "receiver_sites": receiver_sites(root, side),
        "consumers": cons,
        "field_classes": classes,
        "public_input": pi_rows(decl),
        "links": link_rows(decl),
        "state_cost_sites": state_cost_sites(decl),
        "gas_ceiling": refute[side["gas"]["ceiling"]["key"]],
        "law_ids": law_ids(root, side, decl, cons),
    }
    return json.loads(json.dumps(out, sort_keys=True))  # JSON's own types: tuples become lists, as on disk


def main() -> int:
    import sys
    root = Path(__file__).resolve().parents[1]
    out = json.dumps(basis(root), indent=1, sort_keys=True) + "\n"
    if len(sys.argv) > 1 and sys.argv[1] == "--write":
        (root / BASIS_REL).write_text(out)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
