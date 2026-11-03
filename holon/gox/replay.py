"""The replays of the Go part of rule PAR (I93; contract rule G10 of tests_m3/test_go_laws.py): `holon gox replay
--milestone M [--laws ID,..]` writes replay/<M>/gox/<law>.json for each go_branch and go_recompute law, from the witness
holon.gox.model's G9 rule names, on a scratch copy of the pinned checkout (offline).

  go_branch     an internal test of F's package runs F on the witness, X's bytes the compression sidecar's sample
                stream (its seed and construction), and the sidecar's enc on X; agree when F returns p's constants while
                |enc(X)| makes q's value differ from p's.
  go_recompute  an internal test builds the witness's state with the package's constructor (the function with no
                parameter returning *T) and its append method (the method of *T whose parameters name the witness's
                fields), checks the state is the witness's, and prints G's hash; a forge harness inheriting the pinned
                contract computes the store's value through the internal function its frame calls, at the inputs the
                Go preimage's cells name (the loop count from the witness's rest); agree when the digests differ.

Every name comes from the sidecars, the documents and the pinned sources; nothing here names a target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import model as G
from .lawrun import gox_entries, witness_sha256, branch_record_witness, recompute_record_witness, dumps

ROOT = Path(__file__).resolve().parents[2]
TEST_NAME = "TestHolonGox"
GO_FILE = "holon_gox_test.go"


class ReplayError(ValueError):
    pass


def split_fn(fid: str) -> tuple[str, str | None, str]:
    """(package path, receiver type or None, name) of a Go function id."""
    if fid.startswith("("):
        recv, name = fid[1:].split(").", 1)
        pkg, typ = recv.lstrip("*").rsplit(".", 1)
        return pkg, typ, name
    pkg, name = fid.rsplit(".", 1)
    return pkg, None, name


STREAM = '''func hgxStream(seed string, n int) []byte {
	var acc []byte
	for j := uint32(0); len(acc) < n; j++ {
		var be [4]byte
		binary.BigEndian.PutUint32(be[:], j)
		d := sha256.Sum256(append([]byte(seed), be[:]...))
		acc = append(acc, d[:]...)
	}
	return acc[:n]
}

func hgxErr(err error) any {
	if err == nil {
		return nil
	}
	return err.Error()
}
'''


# ------------------------------------------------------------------------------------------------ Go runs
def run_go(root: Path, doc: dict, pkg_path: str, text: str) -> dict:
    """Run the generated internal test of pkg_path on a scratch copy of the pinned checkout; its JSON output."""
    from ..frontends.go.extract import check_go, go_env, make_workspace, resolve_src
    from ..goreplay import _module_dir
    cfg = json.loads((root / doc["extraction"]["config"]["path"]).read_text(encoding="utf-8"))
    src = resolve_src(cfg, root)
    go, _tok = check_go(root)
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != doc["target"]["commit"]:
        raise ReplayError(f"{src} is at {head!r}, not at the document's commit")
    pkgs = {p["path"]: p["dir"] for p in doc["go"]["packages"]}
    if pkg_path not in pkgs:
        raise ReplayError(f"{pkg_path} is not a package of the document")
    parent = Path(tempfile.mkdtemp(prefix="holon-gox-"))
    try:
        ws = parent / "src"
        ws.mkdir()
        make_workspace(src, ws)
        mod = _module_dir(ws, pkgs[pkg_path])
        pdir = ws / pkgs[pkg_path]
        (pdir / GO_FILE).write_text(text, encoding="utf-8")
        out = parent / "out.json"
        env = go_env(GOTOOLCHAIN="local", HOLON_GOX_OUT=str(out))
        rel = pdir.relative_to(mod).as_posix()
        p = subprocess.run([go, "test", f"./{rel}", "-run", f"^{TEST_NAME}$", "-count=1", "-v"], cwd=mod, env=env,
                           capture_output=True, text=True, timeout=3600)
        if p.returncode != 0 or not out.exists():
            raise ReplayError(f"the generated Go test failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2500:]}")
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def _go_pkg_name(pkg_path: str) -> str:
    return pkg_path.rsplit("/", 1)[-1]


def branch_go(b: dict, w: dict, compression: dict) -> tuple[str, str]:
    """(package path, test text) of the go_branch replay."""
    pkg, typ, name = split_fn(b["function"])
    tr = G.branch_tr(b)
    x_tr = G.Tr(call=tr.call)
    x_tr.length(b["arg"])
    leaves = [v for v in x_tr.vars if v != "e"]
    vals = w["values"]
    seed = compression["sample"]["seed"]
    n = w["x_length"]
    off, cuts = 0, {}
    for v in leaves:
        cuts[v] = (off, off + vals[v])
        off += vals[v]
    if off != n:
        raise ReplayError("the witness's operands do not add up to |X|")
    params = b["params"]
    recv = params[0]["name"] if typ is not None else None
    lines = []
    if recv is not None:
        lines.append(f"\t{recv} := &{typ}{{}}")
    args = []
    for v, (k, t) in tr.vars.items():
        if v in cuts and isinstance(t, list) and t[:1] == ["len"] and t[1][:1] == ["field"] \
                and t[1][1] == ["param", recv]:
            a, z = cuts[v]
            lines.append(f"\t{recv}.{t[1][2]} = x[{a}:{z}]")
    for p in params[1:] if recv is not None else params:
        lv, iv = "n_" + G.ident(p["name"]), "i_" + G.ident(p["name"])
        if lv in cuts:
            a, z = cuts[lv]
            args.append(f"x[{a}:{z}]")
        elif iv in vals:
            args.append(str(vals[iv]))
        elif p["type"] == "[]byte":
            args.append("x[0:0]")
        else:
            raise ReplayError(f"a parameter {p['name']} the witness does not give")
    enc_pkg, _et, enc_name = split_fn(compression["codec"]["enc"])
    call = f"{recv}.{name}({', '.join(args)})" if recv is not None else f"{name}({', '.join(args)})"
    nres = 2
    text = (f"package {_go_pkg_name(pkg)}\n\nimport (\n\t\"crypto/sha256\"\n\t\"encoding/binary\"\n\t\"encoding/hex\"\n"
            f"\t\"encoding/json\"\n\t\"os\"\n\t\"testing\"\n\n\thgxenc \"{enc_pkg}\"\n)\n\n" + STREAM + "\n"
            + f"func {TEST_NAME}(t *testing.T) {{\n\tx := hgxStream({json.dumps(seed)}, {n})\n"
            + "\n".join(lines) + "\n"
            + f"\tr0, r1 := {call}\n\tenc, encErr := hgxenc.{enc_name}(x)\n\tsum := sha256.Sum256(x)\n"
            + "\tout := map[string]any{\"returns\": []any{r0, hgxErr(r1)}, \"enc_length\": len(enc), "
            + "\"enc_error\": hgxErr(encErr), \"x_sha256\": hex.EncodeToString(sum[:])}\n"
            + "\tb, _ := json.Marshal(out)\n\tif err := os.WriteFile(os.Getenv(\"HOLON_GOX_OUT\"), b, 0o644); err != nil {\n"
            + "\t\tt.Fatal(err)\n\t}\n}\n")
    del nres
    return pkg, text


def judge_branch(b: dict, w: dict, obs: dict) -> tuple[str, str]:
    pv = b["p_value"][1]
    if obs.get("enc_error") is not None:
        return "disagree", f"enc failed on X: {obs['enc_error']}"
    if obs["returns"] != [pv, None]:
        return "disagree", f"F returned {obs['returns']}, not p's ({pv}, nil)"
    q = obs["enc_length"] > w["bound"] if b["q_value"][0] == ">" else obs["enc_length"] >= w["bound"]
    if q == pv:
        return "disagree", f"|enc(X)| = {obs['enc_length']}: q's value equals p's"
    return "agree", (f"F short-cuts to ({pv}, nil) on |X| = {w['x_length']} while |enc(X)| = {obs['enc_length']} "
                     f"exceeds the bound {w['bound']}: q's value is {q}")


# ------------------------------------------------------------------------------------------------ go_recompute
def _ctor_and_append(doc: dict, pkg: str, typ: str, fields: list, lists: list) -> tuple[str, str, list]:
    """(the constructor, the append method, its parameters) of *T: the analyzed function of the package with no
    parameter returning *T, and the method of *T (other than read-only ones) the most of whose parameters name one of
    fields (a parameter name that is a field's name or a prefix of it)."""
    fs = doc["go"]["functions"]
    ptr = f"*{pkg}.{typ}"
    ctors = sorted(f for f, v in fs.items() if not f.startswith("(") and f.rsplit(".", 1)[0] == pkg
                   and not v["params"] and v["results"] == [ptr])
    if len(ctors) != 1:
        raise ReplayError(f"{len(ctors)} constructors of {ptr}")
    best, score = None, 0
    for f, v in sorted(fs.items()):
        if not f.startswith(f"(*{pkg}.{typ}).") or v["results"]:
            continue
        ps = v["params"][1:]
        named = {fl for fl in fields for p in ps if fl == p["name"] or fl.startswith(p["name"])}
        s = len(named)
        if s > score and all(fl in named for fl in lists):   # every byte-string field the witness sets is a parameter
            best, score = f, s
    if best is None:
        raise ReplayError(f"no append method of {ptr}")
    return ctors[0], best, fs[best]["params"][1:]


def recompute_go(doc: dict, b: dict, w: dict) -> tuple[str, str]:
    pkg, typ, name = split_fn(b["function"])
    g = G.recompute_parts(b)["g"]
    fields = {}
    for n, t in list(g.lists.items()) + list(g.nats.items()):
        fields[t[2]] = (n, t)
    ctor, app, aps = _ctor_and_append(doc, pkg, typ, list(fields), [t[2] for t in g.lists.values()])
    ctor_name, app_name = split_fn(ctor)[2], split_fn(app)[2]
    lines = [f"\tv := {ctor_name}()"]
    per = {}
    for p in aps:
        fl = next((f for f in fields if f == p["name"] or f.startswith(p["name"])), None)
        n = fields[fl][0] if fl else None
        cells = w["lists"].get(n) if n else None
        per[p["name"]] = (p, cells)
    for k in range(w["appends"]):
        args = []
        for p in aps:
            pp, cells = per[p["name"]]
            if cells and pp["type"] == "[]byte":
                stride = len(cells) // w["appends"]
                args.append("[]byte{" + ", ".join(str(c) for c in cells[k * stride:(k + 1) * stride]) + "}")
            else:
                args.append("nil")
        lines.append(f"\tv.{app_name}({', '.join(args)})")
    checks = []
    for fl, (n, t) in fields.items():
        if n in w["lists"]:
            checks.append(f"\t\"{fl}\": len(v.{fl}) == {len(w['lists'][n])},")
        elif n in w["nats"]:
            checks.append(f"\t\"{fl}\": int(v.{fl}) == {w['nats'][n]},")
    text = (f"package {_go_pkg_name(pkg)}\n\nimport (\n\t\"encoding/hex\"\n\t\"encoding/json\"\n\t\"os\"\n\t\"testing\"\n)\n\n"
            + f"func {TEST_NAME}(t *testing.T) {{\n" + "\n".join(lines) + "\n"
            + "\tstate := map[string]bool{\n" + "\n".join(checks) + "\n\t}\n"
            + f"\th := v.{name}()\n"
            + "\tout := map[string]any{\"state\": state, \"go_digest\": hex.EncodeToString(h[:])}\n"
            + "\tb, _ := json.Marshal(out)\n\tif err := os.WriteFile(os.Getenv(\"HOLON_GOX_OUT\"), b, 0o644); err != nil {\n"
            + "\t\tt.Fatal(err)\n\t}\n}\n")
    return pkg, text


def _sol_frame(sdoc: dict, act: dict, val) -> tuple[str, str]:
    """(the source file, the call site span) of the frame that builds the stored value's memory: the stack's last site
    of the mstore that writes the memory term's first store."""
    first = val[1][1][1]
    for m in act.get("mstores") or []:
        if m.get("op") == "mstore" and m.get("offset") == first[1] and m.get("value") == first[2] and m.get("stack"):
            site = m["stack"][-1]
            f, span = site.rsplit(":", 1)
            return f, span
    raise ReplayError("no mstore of the stored value's frame")


def solidity_harness(root: Path, b: dict, w: dict, checkout: Path) -> tuple[str, dict, Path]:
    """(the harness text, the call's input values, the foundry project dir) of the go_recompute replay's Solidity side."""
    sol = b["solidity"]
    sdoc = json.loads((root / sol["document"]).read_text(encoding="utf-8"))
    act = next(a for a in sdoc["actions"] if a["name"] == sol["action"])
    src_rel, span = _sol_frame(sdoc, act, sol["value"])
    lines = (checkout / src_rel).read_text(encoding="utf-8").splitlines()
    a, z = (int(x) for x in (span.split("-") + [span])[:2])
    call = " ".join(lines[a - 1:z])
    m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^;]*)\)\s*;", call)
    if not m:
        raise ReplayError(f"no call at {src_rel}:{span}")
    fn, argtext = m.group(1), m.group(2)
    args = [x.strip() for x in argtext.split(",")]
    text = (checkout / src_rel).read_text(encoding="utf-8")
    d = re.search(rf"function\s+{re.escape(fn)}\s*\(([^)]*)\)", text)
    if not d:
        raise ReplayError(f"no declaration of {fn}")
    types = [x.strip().split()[0] for x in d.group(1).split(",") if x.strip()]
    c = re.search(r"constructor\s*\(([^)]*)\)", text)
    ctypes = [x.strip().split()[0] for x in (c.group(1).split(",") if c else []) if x.strip()]
    pragma = re.search(r"(?m)^pragma solidity[^;]*;", text).group(0)
    contract = sdoc["contract"]
    # the inputs: each prefix byte cell's member takes the Go preimage's cells at its offsets (big-endian); the loop
    # count member takes the witness's rest length in words; every other argument is 0
    lay = G.sol_layout(sol)
    goc = w["go_preimage"]
    vals: dict = {}
    for off, cell in enumerate(lay["prefix"]):
        if cell[:1] == ["byte"] and isinstance(cell[1], list) and cell[1][:1] == ["member"]:
            vals.setdefault(cell[1][2], []).append((cell[2], goc[off] if off < len(goc) else 0))
    inputs = {k: int.from_bytes(bytes(v for _k, v in sorted(cs)), "big") for k, cs in vals.items()}
    count = lay["loop"]["count"]
    rest = sum(len(w["lists"][r]) for r in w["rest"]) // 32
    if isinstance(count, list) and count[:1] == ["member"]:
        inputs[count[2]] = rest
    argv = []
    for ex in args:
        mm = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.([A-Za-z_][A-Za-z0-9_]*)", ex)
        argv.append(str(inputs.get(mm.group(1), 0)) if mm else "0")
    root_dir = next(p for p in (checkout / src_rel).parents if (p / "foundry.toml").is_file())
    imp = (checkout / src_rel).relative_to(root_dir).as_posix()
    params = ", ".join(f"{t} a{i}" for i, t in enumerate(types))
    harness = (f"// SPDX-License-Identifier: UNLICENSED\n{pragma}\n\nimport {{Test}} from \"forge-std/Test.sol\";\n"
               f"import {{{contract}}} from \"../{imp}\";\n\n"
               f"contract HolonGoxH is {contract} {{\n    constructor() {contract}({', '.join('0' for _ in ctypes)}) {{}}\n\n"
               f"    function holonGox({params}) external view returns (bytes32) {{\n"
               f"        return {fn}({', '.join(f'a{i}' for i in range(len(types)))});\n    }}\n}}\n\n"
               f"contract HolonGoxTest is Test {{\n    function test_gox() public {{\n"
               f"        HolonGoxH h = new HolonGoxH();\n        emit log_bytes32(h.holonGox({', '.join(argv)}));\n"
               f"    }}\n}}\n")
    return harness, {"function": fn, "args": dict(zip(args, argv)), "inputs": inputs}, root_dir


def run_solidity(root: Path, harness: str, checkout: Path, foundry_dir: Path) -> str:
    from ..replay import toolchain
    from ..replay_fragments import forge_build, harness_project

    class A:
        pass
    tc = toolchain(A(), root)
    work = Path(tempfile.mkdtemp(prefix="holon-gox-sol-"))
    try:
        hf = work / "HolonGox.t.sol"
        hf.write_text(harness, encoding="utf-8")
        binding = {"project": {"kind": "checkout", "foundry_dir": foundry_dir.relative_to(checkout).as_posix(),
                               "drop": ["mock", "test"]}, "harness": {"files": [str(hf)]}}
        proj = harness_project(binding, work, root, checkout, tc)
        forge_build(proj, tc)
        p = subprocess.run([tc["forge"], "test", "--match-contract", "^HolonGoxTest$", "--offline", "--use", tc["solc"],
                            "-vv"], cwd=proj, capture_output=True, text=True, timeout=3600)
        mm = re.search(r"0x[0-9a-fA-F]{64}", p.stdout)
        if p.returncode != 0 or not mm:
            raise ReplayError(f"the forge harness failed (exit {p.returncode}): {(p.stdout + p.stderr)[-2500:]}")
        return mm.group(0)[2:].lower()
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ the CLI
def replay_law(root: Path, m: str, lid: str, e: dict) -> dict:
    from .basis import Ctx
    from ..replay import morph_path
    cx = Ctx(root, m)
    b = e["basis"]
    if e["subform"] == "go_branch":
        w = G.branch_witness(b)
        wr = branch_record_witness(b, w)
        pkg, text = branch_go(b, w, cx.compression)
        obs = run_go(root, cx.doc, pkg, text)
        verdict, detail = judge_branch(b, w, obs)
        return {"law_id": lid, "kind": "go_branch", "witness_sha256": witness_sha256(wr), "witness": wr,
                "observed": obs, "verdict": verdict, "detail": detail,
                "harness_sha256": hashlib.sha256(text.encode()).hexdigest()}

    class A:
        pass
    w = G.recompute_witness(b)
    wr = recompute_record_witness(b, w)
    pkg, text = recompute_go(cx.doc, b, w)
    obs = run_go(root, cx.doc, pkg, text)
    checkout = morph_path(A(), root)
    harness, call, fdir = solidity_harness(root, b, w, checkout)
    sd = run_solidity(root, harness, checkout, fdir)
    obs = {**obs, "solidity_digest": sd, "solidity_call": call}
    if not all(obs["state"].values()):
        verdict, detail = "disagree", f"the constructor and append method do not build the witness: {obs['state']}"
    elif obs["go_digest"] == sd:
        verdict, detail = "disagree", "the digests agree"
    else:
        verdict, detail = "agree", (f"{b['function']} hashes the witness's {w['go_preimage_length']}-byte preimage to "
                                    f"{obs['go_digest'][:16]}..; the contract's {call['function']} at {call['args']} "
                                    f"gives {sd[:16]}..")
    return {"law_id": lid, "kind": "go_recompute", "witness_sha256": witness_sha256(wr), "witness": wr,
            "observed": obs, "verdict": verdict, "detail": detail,
            "harness_sha256": hashlib.sha256((text + harness).encode()).hexdigest()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon gox replay")
    ap.add_argument("cmd", choices=["replay"])
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--laws")
    ap.add_argument("--root")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    ents = {k: v for k, v in gox_entries(a.milestone, root).items() if v["subform"] in ("go_branch", "go_recompute")}
    ids = [x.strip() for x in a.laws.split(",")] if a.laws else sorted(ents)
    out_dir = root / "replay" / a.milestone / "gox"
    out_dir.mkdir(parents=True, exist_ok=True)
    rc = 0
    for lid in ids:
        if lid not in ents:
            print(f"holon gox replay: {lid} is not a replayed gox law", file=sys.stderr)
            return 3
        try:
            r = replay_law(root, a.milestone, lid, ents[lid])
        except (ReplayError, G.ModelDebt, OSError) as ex:
            r = {"law_id": lid, "verdict": "error", "detail": f"{type(ex).__name__}: {ex}"}
            rc = 1
        (out_dir / f"{lid}.json").write_text(dumps(r), encoding="utf-8")
        print(f"{lid}: {r['verdict']} ({r['detail'][:160]})")
    return rc
