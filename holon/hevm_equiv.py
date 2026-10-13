"""Optional hevm equivalence for the top codec edges (I20; BUILD_PLAN I20: hevm equivalence between the bytecode of
the codec library's store functions and Yul generated from the model layout; whitepaper L1; Q16 allows the install).

    python -m holon hevm [--binding replay/M2/hevm_store.json] [--out results/M2/hevm.json] [--morph PATH]
                         [--hevm PATH] [--solver PATH] [--work DIR] [--smttimeout S]

For every version the binding lists, two runtime bytecodes are compared by `hevm equivalence` on symbolic calldata:
  A  the real store functions: a wrapper generated from the binding's calls (the encoder edge's own call sequence),
     compiled in a scratch copy of the pinned checkout with its Foundry profile and the pinned solc. Field f's value
     is calldata word i (i: f's position in the facts' field widths); a constant argument is passed as the binding
     gives it; the header is a fresh `new bytes(L)`, returned raw (a fallback returning bytes).
  B  Yul generated from the facts' encoder ops (holon.facts.src_cells, as holon.layout applies them): each op becomes
     one mstore / mstore8 of the same cells, a field's bytes taken from its calldata word; the region [0, L) is
     returned. A byte the model leaves undetermined makes the version not comparable.
hevm proves that both return the same bytes for every calldata (and every call value), or gives a counterexample.

A negative control per version runs hevm once more against a mutant of side B (the first masked field loses its
top bit): it must come out "not_equivalent", or the record shows that the check did not discriminate.

The tools are pinned in config/holon.json "hevm" (version, url and sha256 of hevm and of its solver cvc5, and where
they are installed): a binary is used only when its sha256 is the pin's. results/M2/hevm.json (canonical JSON, no
timings): {"status": "run" | "not_run", "reason", ...}. "not_run" when hevm or its SMT solver cannot be found, is not
the pinned binary, or does not start (the reason says which); "run" otherwise, with one entry per
(edge, version): {"edge", "version", "result": "equivalent" | "not_equivalent" | "unknown", "detail", "a_sha256",
"b_sha256"}, the tool and solver digests and the pins. Nothing here names a target: the codec's names come from the
binding and the facts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import facts as F

ROOT = Path(__file__).resolve().parents[1]
BINDING = Path("replay") / "M2" / "hevm_store.json"
OUT = Path("results") / "M2" / "hevm.json"
TOOLS = Path.home() / ".holon" / "tools"
WRAPPER = "HolonHevmStore.sol"


class HevmError(RuntimeError):
    pass


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def pins(root: Path = ROOT) -> dict:
    """config/holon.json "hevm": {version, url, sha256, path, solver: {name, version, url, sha256, path}}."""
    cfg = json.loads((Path(root) / "config" / "holon.json").read_text())
    h = cfg.get("hevm")
    if not isinstance(h, dict) or not isinstance(h.get("solver"), dict):
        raise HevmError("config/holon.json pins no hevm (\"hevm\": {version, url, sha256, path, solver})")
    return h


def find_tool(explicit: str | None, env: str, pin: dict) -> tuple[Path | None, str | None]:
    """(the binary, None) for an explicit path, else $env, else the pin's path, when its sha256 is the pin's; else
    (None, why)."""
    for c in (explicit, os.environ.get(env), pin.get("path")):
        if c:
            p = Path(c)
            if not p.is_file():
                return None, f"{p} does not exist"
            got = sha256_file(p)
            if got != pin.get("sha256"):
                return None, f"{p} has sha256 {got}, not the pinned {pin.get('sha256')} ({pin.get('url')})"
            return p, None
    return None, "no path given and none pinned"


def _out(cmd: list[str], env: dict | None = None, timeout: int = 60, cwd: Path | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env={**os.environ, **(env or {})},
                           cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, f"{type(e).__name__}: {e}"
    return p.returncode, p.stdout + p.stderr


# ---------------------------------------------------------------- side B: Yul from the model layout
def field_words(facts: dict) -> dict[str, int]:
    """field -> its calldata word (the facts' field order)."""
    return {f: i for i, f in enumerate(F.widths(facts))}


def _cell_runs(cells: list[list]) -> list[tuple]:
    """Runs of the op's cells: ("field", name, k0, n, j0) for consecutive bytes of one field, ("const", v, j)."""
    runs: list = []
    for j, c in enumerate(cells):
        if c[0] == "field":
            last = runs[-1] if runs else None
            if last and last[0] == "field" and last[1] == c[1] and last[2] + last[3] == c[2] and last[4] + last[3] == j:
                runs[-1] = ("field", c[1], last[2], last[3] + 1, last[4])
            else:
                runs.append(("field", c[1], c[2], 1, j))
        elif c[0] == "const":
            runs.append(("const", int(c[1]), j))
        else:
            raise HevmError(f"cell {c} has no Yul form")
    return runs


def op_value(cells: list[list], widths: dict, words: dict) -> str:
    """The Yul expression of the L = len(cells) bytes an op writes (big-endian, in the low L bytes of a word)."""
    L = len(cells)
    parts = []
    for r in _cell_runs(cells):
        if r[0] == "const":
            if r[1]:
                sh = 8 * (L - 1 - r[2])
                parts.append(f"shl({sh}, {r[1]})" if sh else str(r[1]))
            continue
        _, name, k0, n, j0 = r
        W = widths[name]
        src = f"calldataload({32 * words[name]})"
        down = 8 * (W - k0 - n)
        v = f"shr({down}, {src})" if down else src
        if n < 32:
            v = f"and({v}, {hex((1 << (8 * n)) - 1)})"
        up = 8 * (L - j0 - n)
        parts.append(f"shl({up}, {v})" if up else v)
    if not parts:
        return "0"
    out = parts[0]
    for x in parts[1:]:
        out = f"or({out}, {x})"
    return out


def model_yul(facts: dict, fn: str, version: int) -> str:
    """A Yul block that writes the encoder's ops for one version at memory 0x80 and returns the header."""
    from .layout import layout
    f = facts["functions"][fn]
    w = F.widths(facts)
    words = field_words(facts)
    length = int(f["length_by_version"][str(version)])
    lay = layout(facts, fn, version)
    bad = [i for i, c in enumerate(lay) if c[0] == "unknown"]
    if bad:
        raise HevmError(f"{fn} v{version}: the model leaves bytes {bad[:5]} undetermined")
    lines = ["{", "    let p := 0x80"]
    for op in f["ops"]:
        if not F.when_ok(op.get("when"), version):
            continue
        cells = F.src_cells(op["src"], w)
        F.check_op_width(fn, op, len(cells))
        if op["op"] == "mstore8":
            lines.append(f"    mstore8(add(p, {op['offset']}), {op_value(cells, w, words)})")
        elif op["op"] == "mstore":
            lines.append(f"    mstore(add(p, {op['offset']}), {op_value(cells, w, words)})")
        else:
            raise HevmError(f"{fn}: op {op['op']} has no Yul form here")
    lines += [f"    return(p, {length})", "}", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- side A: the real store functions
def wrapper_source(binding: dict, facts: dict) -> str:
    """The Solidity wrapper (one contract per version) that calls the binding's store functions."""
    words = field_words(facts)
    w = F.widths(facts)
    lines = ["// SPDX-License-Identifier: MIT",
             "// Generated by holon/hevm_equiv.py from replay/M2/hevm_store.json: side A of the hevm equivalence.",
             "pragma solidity =0.8.24;", ""]
    for name, path in binding["imports"]:
        lines.append(f'import {{{name}}} from "../{path}";')
    for v in binding["versions"]:
        lines += ["", f"contract HolonHevmStoreV{v} {{",
                  "    fallback(bytes calldata) external payable returns (bytes memory h) {",
                  f"        h = new bytes({binding['length'][v]});",
                  "        uint256 p;",
                  "        assembly {",
                  "            p := add(h, 32)",
                  "        }"]
        for call in binding["calls"]:
            fn, arg = call[0], call[1]
            when = call[2] if len(call) > 2 else None
            if not F.when_ok(when, int(v)):
                continue
            if "field" in arg:
                expr = f"_w({words[arg['field']]})"
                if w[arg["field"]] == 32:
                    expr = f"bytes32({expr})"
            else:
                expr = arg["const"]
            lines.append(f"        {fn}(p, {expr});")
        lines += ["    }", "",
                  "    function _w(uint256 i) private pure returns (uint256 v) {",
                  "        assembly {",
                  "            v := calldataload(mul(i, 32))",
                  "        }",
                  "    }",
                  "}"]
    return "\n".join(lines) + "\n"


def build_a(binding: dict, facts: dict, work: Path, morph: Path, tc: dict) -> dict[str, str]:
    """version -> the runtime bytecode (hex, no 0x) of side A."""
    from .replay_fragments import forge_build, foundry_out, harness_project
    proj = harness_project({"project": {"kind": "checkout", "foundry_dir": binding["foundry_dir"],
                                         "drop": binding.get("drop", [])}, "harness": {"files": []}},
                           work, ROOT, morph, tc)
    (proj / "test" / WRAPPER).write_text(wrapper_source(binding, facts))
    forge_build(proj, tc)
    out = {}
    for v in binding["versions"]:
        art = json.loads((foundry_out(proj) / WRAPPER / f"HolonHevmStoreV{v}.json").read_text())
        code = art["deployedBytecode"]["object"]
        out[v] = code[2:] if code.startswith("0x") else code
    return out


def build_b(binding: dict, facts: dict, work: Path, solc: str) -> dict[str, str]:
    """version -> the bytecode (hex) of side B: the Yul block compiled by the pinned solc (no optimizer)."""
    out = {}
    for v in binding["versions"]:
        y = work / f"model_v{v}.yul"
        y.write_text(model_yul(facts, binding["encoder"], int(v)))
        code, text = _out([solc, "--strict-assembly", "--bin", str(y)], timeout=120)
        m = re.search(r"Binary representation:\s*\n([0-9a-fA-F]+)", text)
        if code != 0 or not m:
            raise HevmError(f"solc --strict-assembly failed on version {v}: {text[-800:]}")
        out[v] = m.group(1).lower()
    return out


ANSI = re.compile(r"\x1b\[[0-9;]*m")
SUMMARY = ("contracts behave equivalently", "no discrepancies found", "contracts do not behave equivalently",
           "not equivalent", "contracts may not behave equivalently", "partially explore", "smt solver says")


def verdict(code: int, text: str) -> tuple[str, str]:
    """(result, detail) from hevm equivalence's exit code and output: "equivalent" only when hevm exits 0 and says
    the contracts behave equivalently with no discrepancy; "not_equivalent" when it reports differing behaviours;
    "unknown" otherwise (a partial exploration, an SMT unknown, a crash). detail keeps hevm's summary lines (never
    a counterexample's calldata, which the solver may choose differently on another run)."""
    lines = [ANSI.sub("", l).strip() for l in text.splitlines()]
    summary = [l for l in lines if any(k in l.lower() for k in SUMMARY)]
    low = "\n".join(summary).lower()
    detail = "; ".join(dict.fromkeys(summary)) or f"exit {code}: {lines[-1] if lines else ''}"
    if code == 0 and "contracts behave equivalently" in low and "no discrepancies found" in low \
            and "partially" not in low:
        return "equivalent", detail
    if "do not behave equivalently" in low or "not equivalent." in low:
        return "not_equivalent", detail
    return "unknown", detail


def control_yul(yul: str) -> tuple[str, str] | None:
    """A mutant of a model block for the negative control: the first masked field loses its top bit."""
    m = re.search(r"and\((calldataload\(\d+\)|shr\(\d+, calldataload\(\d+\)\)), 0x(f+)\)", yul)
    if m is None:
        return None
    mask = int(m.group(2), 16)
    new = m.group(0).replace(hex(mask), hex(mask >> 1))
    return yul.replace(m.group(0), new, 1), f"{m.group(0)} -> {new}"


def run(args) -> int:
    from .replay import PIN_KEYS, check_checkout, morph_path, toolchain
    root = ROOT
    bpath = root / (args.binding or BINDING)
    binding = json.loads(bpath.read_text())
    facts_path = root / binding["facts"]
    facts = F.load(facts_path)
    out = Path(args.out) if args.out else root / OUT
    rec = {"binding": bpath.relative_to(root).as_posix(), "facts": binding["facts"],
           "facts_sha256": sha256_file(facts_path), "edges": []}
    pin = pins(root)
    hevm, why_h = find_tool(args.hevm, "HOLON_HEVM", pin)
    solver, why_s = find_tool(args.solver, "HOLON_HEVM_SOLVER", pin["solver"])
    why = None
    if hevm is None:
        why = f"hevm {pin.get('version')} is not installed as pinned in config/holon.json ({why_h})"
    elif solver is None:
        why = f"the SMT solver {pin['solver'].get('name')} {pin['solver'].get('version')} is not installed as pinned " \
              f"in config/holon.json ({why_s})"
    if why is None:
        c, v = _out([str(hevm), "version"])
        c2, sv = _out([str(solver), "--version"])
        if c != 0 or c2 != 0:
            why = f"hevm or its solver does not start: {v.strip()[:200]} {sv.strip()[:200]}"
    if why is not None:
        rec.update({"status": "not_run", "reason": why})
        write(out, rec)
        print(f"hevm: not_run: {why}")
        return 0
    rec["hevm"] = {"version": v.strip().split()[0], "sha256": sha256_file(hevm), "source": pin["url"]}
    rec["solver"] = {"name": "cvc5", "version": sv.splitlines()[0].strip(), "sha256": sha256_file(solver),
                     "source": pin["solver"]["url"]}
    morph = morph_path(args, root)
    rec["morph_commit"] = check_checkout(morph, facts["target"]["commit"])
    tc = toolchain(argparse.Namespace(forge=None, solc=None, write_pins=False, morph=str(morph)), root)
    rec["toolchain"] = {k: tc[k] for k in PIN_KEYS}
    tmp = None
    work = Path(args.work).resolve() if args.work else Path(tempfile.mkdtemp(prefix="holon-hevm-"))
    if not args.work:
        tmp = work
    try:
        work.mkdir(parents=True, exist_ok=True)
        a = build_a(binding, facts, work, morph, tc)
        b = build_b(binding, facts, work, tc["solc"])
        env = {"PATH": f"{solver.parent}{os.pathsep}{os.environ.get('PATH', '')}"}
        for ver in binding["versions"]:
            fa, fb = work / f"a_v{ver}.hex", work / f"b_v{ver}.hex"
            fa.write_text(a[ver])
            fb.write_text(b[ver])
            cmd = [str(hevm), "equivalence", "--code-a-file", str(fa), "--code-b-file", str(fb), "--solver", "cvc5",
                   "--smttimeout", str(args.smttimeout), "--num-solvers", "1"]
            code, text = _out(cmd, env, timeout=args.smttimeout * 20 + 600, cwd=work)
            res, detail = verdict(code, text)
            rec["edges"].append({"edge": binding["encoder"], "version": int(ver), "result": res, "detail": detail,
                                 "a_sha256": hashlib.sha256(bytes.fromhex(a[ver])).hexdigest(),
                                 "b_sha256": hashlib.sha256(bytes.fromhex(b[ver])).hexdigest()})
            print(f"hevm: {binding['encoder']} v{ver}: {res} ({detail[:120]})")
            ctl = control_yul((work / f"model_v{ver}.yul").read_text())
            if ctl is not None:   # a negative control: a mutant of side B must not be proved equivalent
                yc = work / f"control_v{ver}.yul"
                yc.write_text(ctl[0])
                c3, t3 = _out([tc["solc"], "--strict-assembly", "--bin", str(yc)], timeout=120)
                m3 = re.search(r"Binary representation:\s*\n([0-9a-fA-F]+)", t3)
                if c3 != 0 or not m3:
                    raise HevmError(f"solc --strict-assembly failed on the control of version {ver}")
                fc = work / f"control_v{ver}.hex"
                fc.write_text(m3.group(1).lower())
                cmd[cmd.index(str(fb))] = str(fc)
                code, text = _out(cmd, env, timeout=args.smttimeout * 20 + 600, cwd=work)
                cres, cdetail = verdict(code, text)
                rec.setdefault("controls", []).append({"edge": binding["encoder"], "version": int(ver),
                                                       "mutation": ctl[1], "result": cres, "detail": cdetail})
                print(f"hevm: control v{ver} ({ctl[1]}): {cres}")
    except HevmError as e:
        rec.update({"status": "not_run", "reason": f"the comparison could not be built: {e}"})
        write(out, rec)
        print(f"hevm: not_run: {e}")
        return 0
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    rec["command"] = ("hevm equivalence --code-a-file <A v> --code-b-file <B v> --solver cvc5 --smttimeout "
                      f"{args.smttimeout} --num-solvers 1   # A: the store functions wrapped as the binding's calls "
                      "(forge build, pinned solc); B: solc --strict-assembly --bin of the model's Yul")
    results = {e["result"] for e in rec["edges"]}
    rec["status"] = "run"
    rec["reason"] = (f"hevm ran on {len(rec['edges'])} (edge, version) pairs: "
                     + ", ".join(f"{e['edge']} v{e['version']} {e['result']}" for e in rec["edges"])
                     + "; negative controls (one mutated mask in side B each): "
                     + ", ".join(f"v{c['version']} {c['result']}" for c in rec.get("controls", [])))
    write(out, rec)
    return 0 if results <= {"equivalent"} else 1


def write(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="holon hevm", description=__doc__.split("\n\n")[0])
    ap.add_argument("--binding")
    ap.add_argument("--out")
    ap.add_argument("--morph")
    ap.add_argument("--hevm")
    ap.add_argument("--solver")
    ap.add_argument("--work")
    ap.add_argument("--smttimeout", type=int, default=300)
    args = ap.parse_args(argv)
    try:
        return run(args)
    except HevmError as e:
        print(f"hevm: {e}", file=sys.stderr)
        return 2
