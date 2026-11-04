"""The OWN half of `holon replay-go --milestone M` (BUILD_PLAN row I35; rule W12 of the docstring of tests_m3/test_own.py):
every REFUTED OWN record's witness, run on the real Go code.

From the carrier documents alone (holon.own) and the records' witnesses it generates one internal test of the types'
package (the package of the Go document's that holds them), on a scratch copy of the pinned checkout (the Go document's
extraction config names it, as holon.goreplay's):
  alias      x := the constructor(); the trace's calls; v := V() (the view result); before := v's bytes; the call of
             W; after := v's bytes; after every call, cap() of every modelled field (and the view's after V);
  lost_write var x T (the type's zero value); res := m() (the result case allocated at the lost write's site);
             len(x.F) afterwards and len(res).
A byte-slice parameter takes the witness's bytes in order; every other parameter its type's zero value (a type whose
zero value cannot be written without naming it leaves the law not_run, with the reason). replay/<M>/own/report.json:
  {"milestone", "morph_commit", "go_version", "laws": {law: {"go": {"status", "provenance": "library_api",
   "obstruction_observed", "observed", "expected", "caps": [{"step", "field", "model", "real"}], "command"}}},
   "witness_sha256": {law: sha256}}
A side passes iff the obstruction is observed exactly as the model states it (the view's bytes before and after, or the
two lengths) and every capacity agrees with the compiled model's (A-go-growth's check). The records' replay,
witness_provenance and filter_bin follow the report (holon.own_run reads it when it decides; stamp() here).
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import bend
from . import own as OW
from .gen import ownheap as OH

IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
TEST_FILE = "holon_own_replay_test.go"
ZERO = {"bool": "false", "string": '""', "error": "nil", "any": "nil"}
NUMERIC = re.compile(r"^(u?int(8|16|32|64)?|uintptr|byte|rune|float(32|64)|complex(64|128))$")


class Refused(Exception):
    """Exit 2: nothing is written."""


def _load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def zero(t: str) -> str | None:
    """The Go source of a parameter type's zero value, without naming the type (None when that needs its name)."""
    if not isinstance(t, str):
        return None
    if t.startswith(("[]", "*", "map[", "func(", "chan ", "<-chan ", "chan<- ")) or t.startswith("interface"):
        return "nil"
    if NUMERIC.match(t):
        return "0"
    return ZERO.get(t)


def go_bytes(hexstr: str) -> str:
    b = bytes.fromhex(hexstr[2:] if hexstr.startswith("0x") else hexstr)
    return "[]byte{" + ", ".join(f"0x{x:02x}" for x in b) + "}"


def call_src(doc: dict, name: str, recv: str, args_hex: list[str], results: int | None = None,
             lhs: str | None = None) -> str:
    """One Go call of method name on recv, the witness's bytes for its byte-slice parameters in order."""
    m = doc["methods"][name]
    if not IDENT.match(name):
        raise Refused(f"method {name!r} cannot be named in a generated test")
    it = iter(args_hex)
    args = []
    for p in (m.get("params") or [])[1:]:
        if p.get("type") == "[]byte":
            try:
                args.append(go_bytes(next(it)))
            except StopIteration:
                raise Refused(f"{name}: the witness has fewer byte arguments than the method's byte-slice parameters")
        else:
            z = zero(p.get("type"))
            if z is None:
                raise Refused(f"{name}: the parameter {p.get('name')} of type {p.get('type')} has no zero value a test "
                              "can write without naming its type")
            args.append(z)
    if next(it, None) is not None:
        raise Refused(f"{name}: the witness has more byte arguments than the method's byte-slice parameters")
    n = len(m.get("results") or []) if results is None else results
    call = f"{recv}.{name}({', '.join(args)})"
    if lhs is not None:
        return f"{lhs} = {call}"
    return call if n == 0 else f"{', '.join(['_'] * n)} = {call}"


def _caps_src(fields: list[str], view: bool) -> str:
    kv = [f'"{f}": cap(x.{f})' for f in fields] + (['"$view": cap(v)'] if view else [])
    return "caps = append(caps, map[string]int{" + ", ".join(kv) + "})"


def alias_block(lid: str, doc: dict, law_basis: dict, witness: dict, fns: dict) -> str:
    """fns: the Go document's functions (a constructor the test calls takes no parameter)."""
    V, W = law_basis["view"], law_basis["writer"]
    fields = list(doc["modelled"])
    if not all(IDENT.match(f) for f in fields):
        raise Refused(f"a modelled field of {doc['stem']} cannot be named in a generated test")
    ctors = [c for c in doc.get("constructors") or [] if not (fns.get(c["function"]) or {}).get("params")]
    if not ctors:
        raise Refused("the carrier has no constructor without parameters")
    fid = ctors[0]["function"]
    cname = fid.rsplit(".", 1)[-1]
    if not IDENT.match(cname):
        raise Refused(f"the constructor {fid!r} cannot be named")
    vm = doc["methods"][V]
    if len(vm.get("params") or []) > 1:
        raise Refused(f"the view {V} takes parameters")
    rs = sorted({v["result"] for v in doc["views"] if v["method"] == V})
    if len(rs) != 1:
        raise Refused(f"the view {V} returns its views in results {rs}")
    nres = len(vm.get("results") or [])
    lhs = ", ".join("v" if i == rs[0] else "_" for i in range(nres))
    lines = [f"x := {cname}()", "caps := []map[string]int{}"]
    for c in witness.get("p") or []:
        lines += [call_src(doc, c["method"], "x", c["args"]), _caps_src(fields, False)]
    lines += [f"{lhs} := x.{V}()", _caps_src(fields, True), "o[\"view_before\"] = hex.EncodeToString(v)",
              call_src(doc, witness["w"]["method"], "x", witness["w"]["args"]), _caps_src(fields, True),
              "o[\"view_after\"] = hex.EncodeToString(v)", "o[\"caps\"] = caps"]
    if witness["w"]["method"] != W:
        raise Refused(f"the witness's last call is {witness['w']['method']}, not the writer {W}")
    return _block(lid, lines)


def lost_block(lid: str, doc: dict, law_basis: dict) -> str:
    m, f = law_basis["method"], law_basis["field"]
    if not IDENT.match(f):
        raise Refused(f"the field {f!r} cannot be named")
    md = doc["methods"][m]
    site = None
    for x in doc["lost_writes"]:
        if x["method"] == m and x["field"] == f:
            v = x.get("value")
            site = v[1][1] if isinstance(v, list) and len(v) > 1 and isinstance(v[1], list) and len(v[1]) > 1 else None
    rs = _results_with_fresh(doc, m, site)
    idx = rs[0] if len(rs) == 1 else None
    if idx is None:
        raise Refused(f"{m}: no slice result case allocates at the lost write's site {site}")
    nres = len(md.get("results") or [])
    lhs = ", ".join("res" if i == idx else "_" for i in range(nres))
    tname = doc["type"].rsplit(".", 1)[-1]
    if not IDENT.match(tname):
        raise Refused(f"the type {doc['type']!r} cannot be named")
    lines = [f"var x {tname}", call_src(doc, m, "x", [], lhs=lhs).replace(" = ", " := ", 1),
             f"o[\"field_len_after\"] = len(x.{f})", "o[\"assigned_len\"] = len(res)"]
    return _block(lid, lines)


def _results_with_fresh(doc: dict, m: str, site) -> list[int]:
    """The result indexes of method m with a slice result case allocated at site (each case carries its result)."""
    return sorted({c.get("result") for c in doc["methods"][m].get("cases") or []
                   if c.get("backing") == ["fresh", site] and isinstance(c.get("result"), int)})


def _block(lid: str, lines: list[str]) -> str:
    body = "\n".join("\t\t" + ln for ln in lines)
    return f'''\t// {lid}
\tfunc() {{
\t\to := map[string]any{{}}
\t\tout["{lid}"] = o
\t\tdefer func() {{
\t\t\tif r := recover(); r != nil {{
\t\t\t\to["panic"] = fmt.Sprint(r)
\t\t\t}}
\t\t}}()
{body}
\t}}()
'''


def test_text(pkg: str, blocks: list[str]) -> str:
    if not IDENT.match(pkg):
        raise Refused(f"package name {pkg!r}")
    return f'''// GENERATED by holon.ownreplay from OWN carrier documents and the records' witnesses; do not edit.
package {pkg}

import (
\t"encoding/hex"
\t"encoding/json"
\t"fmt"
\t"os"
\t"testing"
)

var _ = hex.EncodeToString

func TestHolonOwn(t *testing.T) {{
\tout := map[string]any{{}}
{"".join(blocks)}\tjs, err := json.Marshal(out)
\tif err != nil {{
\t\tt.Fatalf("encode output: %v", err)
\t}}
\tif err := os.WriteFile(os.Getenv("HOLON_OWN_OUT"), js, 0o644); err != nil {{
\t\tt.Fatalf("write output: %v", err)
\t}}
}}
'''


def model_caps(cm: OH.CompiledModel, witness: dict, V: str, W: str) -> list[dict]:
    """[{"step", "field", "model"}] of the compiled model at an alias witness: after each call of the trace, after V
    (the view's capacity too) and after W."""
    cr = cm.carrier

    def cv(c):
        return OH.call_value(cr, c["method"], [list(bytes.fromhex(a[2:])) for a in c["args"]])
    p = [cv(c) for c in witness.get("p") or []]
    vcall = OH.call_value(cr, V, [])
    wcall = cv(witness["w"])
    traces = [(f"after call {i + 1} ({c['method']})", p[:i + 1]) for i, c in enumerate(witness.get("p") or [])]
    traces += [(f"after {V}", p + [vcall]), (f"after {W}", p + [vcall, wcall])]
    exprs = [{"fn": "run", "args": [{"val": t}, {"fn": "s0", "args": []}]} for _, t in traces]
    exprs.append({"fn": f"view_{OH.bname(V)}", "args": [{"fn": "run", "args": [{"val": p}, {"fn": "s0", "args": []}]}]})
    res = cm.calls(exprs)
    out = []
    for (step, _), st in zip(traces, res[:-1]):
        if not isinstance(st, dict) or "error" in st:
            raise Refused(f"the compiled model failed at {step}: {st}")
        for i, f in enumerate(cr.fields):
            out.append({"step": step, "field": f, "model": int(st[f"f{i + 1}"]["cap"])})
        if step == f"after {V}":
            vr = res[-1]
            out.append({"step": step, "field": "$view", "model": int(vr["v"]["cap"])})
    return out


def build(root: Path, milestone: str) -> dict | None:
    """The OWN report of the milestone's REFUTED OWN records (rule W12); None when there is none."""
    from .frontends.go.extract import check_go, go_env, make_workspace, resolve_src
    from .goreplay import _module_dir
    from .replay import witness_sha256
    from .rules import own as OR
    todo = {}
    for p in sorted((root / "laws" / milestone).glob("L*.json")):
        law = _load(p)
        if law.get("rule") != OR.RULE:
            continue
        rp = root / "results" / milestone / f"{law['law_id']}.json"
        rec = _load(rp) if rp.is_file() else None
        doc = _load(root / law["facts"]) if isinstance(law.get("facts"), str) and (root / law["facts"]).is_file() \
            else None
        if rec is None or rec.get("status") != "REFUTED" or not OW.is_own(doc):
            continue
        todo[law["law_id"]] = (law, doc, rec)
    if not todo:
        return None
    docs = {law["facts"]: doc for law, doc, _ in todo.values()}
    go_docs = {doc["document"] for doc in docs.values()}
    if len(go_docs) != 1:
        raise Refused(f"the carriers come from {len(go_docs)} Go documents")
    go_doc = _load(root / next(iter(go_docs)))
    pkgs = {p["path"]: p["dir"] for p in go_doc["go"]["packages"]}
    by_pkg: dict[str, list] = {}
    plan, blocks_of = {}, {}
    for lid, (law, doc, rec) in sorted(todo.items()):
        pkg = doc["type"].rsplit(".", 1)[0]
        basis = next(e["basis"] for e in OR.elements(doc) if e["law_id"] == lid)
        try:
            if pkg not in pkgs:
                raise Refused(f"the package {pkg} is not one of the Go document's")
            if law["subform"] == "alias":
                block = alias_block(lid, doc, basis, rec["witness"], go_doc["go"]["functions"])
                raw = (root / law["facts"]).read_bytes()
                cm = OH.CompiledModel.build(doc, hashlib.sha256(raw).hexdigest(), OW.model_name(doc),
                                            OH.growth_of(root, milestone), bend.config(root))
                expected = {"view_before": rec["difference"]["view_before"][2:],
                            "view_after": rec["difference"]["view_after"][2:]}
                caps = model_caps(cm, rec["witness"], basis["view"], basis["writer"])
            else:
                block = lost_block(lid, doc, basis)
                expected = {"field_len_after": rec["difference"]["field_len_after"],
                            "assigned_len": rec["difference"]["assigned_len"]}
                caps = []
        except (Refused, KeyError, TypeError, ValueError) as e:
            plan[lid] = {"not_run": str(e)}
            continue
        by_pkg.setdefault(pkg, []).append(lid)
        blocks_of[lid] = block
        plan[lid] = {"expected": expected, "caps": caps, "witness": rec["witness"]}
    cfg = _load(root / go_doc["extraction"]["config"]["path"])
    src = resolve_src(cfg, root)
    head = subprocess.run(["git", "-C", str(src), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != go_doc["target"]["commit"]:
        raise Refused(f"{src} is at {head!r}, not at the Go document's commit {go_doc['target']['commit']}")
    dirty = subprocess.run(["git", "-C", str(src), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    if dirty:
        raise Refused(f"{src} has local changes: {dirty[:500]}")
    go, go_version = check_go(root)
    observed, commands = {}, {}
    for pkg, lids in sorted(by_pkg.items()):
        parent = Path(tempfile.mkdtemp(prefix="holon-ownreplay-"))
        try:
            ws = parent / "src"
            ws.mkdir()
            make_workspace(src, ws)
            pdir = ws / pkgs[pkg]
            mod = _module_dir(ws, pkgs[pkg])
            (pdir / TEST_FILE).write_text(test_text(pkg.rsplit("/", 1)[-1], [blocks_of[x] for x in lids]),
                                          encoding="utf-8")
            rel = pdir.relative_to(mod).as_posix()
            cmd = ["go", "test", f"./{rel}", "-run", "^TestHolonOwn$", "-count=1"]
            env = go_env(GOTOOLCHAIN="local", HOLON_OWN_OUT=str(parent / "out.json"))
            p = subprocess.run([go] + cmd[1:], cwd=mod, env=env, capture_output=True, text=True, timeout=3600)
            if p.returncode != 0 or not (parent / "out.json").exists():
                raise Refused(f"the generated Go test failed (exit {p.returncode}): {(p.stdout + p.stderr)[-3000:]}")
            got = _load(parent / "out.json")
            for lid in lids:
                observed[lid] = got.get(lid) or {}
                commands[lid] = f"(cd {mod.relative_to(ws).as_posix()} && {' '.join(cmd)})"
        finally:
            shutil.rmtree(parent, ignore_errors=True)
    report = {"milestone": milestone, "morph_commit": go_doc["target"]["commit"], "go_version": go_version,
              "laws": {}, "witness_sha256": {}}
    for lid in sorted(plan):
        pl = plan[lid]
        if "not_run" in pl:
            report["laws"][lid] = {"go": {"status": "not_run", "provenance": "library_api",
                                          "obstruction_observed": False, "observed": {}, "expected": {}, "caps": [],
                                          "command": "", "why": pl["not_run"]}}
            continue
        ob = observed.get(lid, {})
        exp = pl["expected"]
        if "view_before" in exp:
            got = {"view_before": ob.get("view_before"), "view_after": ob.get("view_after")}
            seen = got["view_before"] is not None and got["view_before"] != got["view_after"]
            real = ob.get("caps") or []
            steps = list(dict.fromkeys(c["step"] for c in pl["caps"]))
            caps = []
            for c in pl["caps"]:
                i = steps.index(c["step"])
                caps.append({**c, "real": (real[i] if i < len(real) else {}).get(c["field"])})
            caps_ok = bool(caps) and all(c["model"] == c["real"] for c in caps)
        else:
            got = {"field_len_after": ob.get("field_len_after"), "assigned_len": ob.get("assigned_len")}
            seen = got["field_len_after"] is not None and got["field_len_after"] != got["assigned_len"]
            caps, caps_ok = [], True
        if "panic" in ob:
            got["panic"] = ob["panic"]
        held = seen and got == exp and caps_ok
        report["laws"][lid] = {"go": {"status": "passed" if held else "failed", "provenance": "library_api",
                                      "obstruction_observed": bool(seen and got == exp), "observed": got,
                                      "expected": exp, "caps": caps, "command": commands.get(lid, "")}}
        report["witness_sha256"][lid] = witness_sha256(pl["witness"])
    return report


def stamp(root: Path, milestone: str, report: dict) -> list[str]:
    """Each REFUTED OWN record's replay, witness_provenance and filter_bin from the report: what holon run writes once
    the report exists (holon.own_run)."""
    from .filter import record_fields
    from .refute_m3 import write_record
    from .replay import replay_status, witness_sha256
    out = []
    for lid in sorted(report["laws"]):
        p = root / "results" / milestone / f"{lid}.json"
        rec = _load(p)
        wp, fb = record_fields(report, lid, rec.get("witness"), witness_sha256)
        new = dict(rec, replay=replay_status(report, lid, rec.get("witness")), witness_provenance=wp, filter_bin=fb)
        if new != rec:
            write_record(p, new)
            out.append(lid)
    return out


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True) + "\n"
