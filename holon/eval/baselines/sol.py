"""The Solidity baselines (I52_baselines.json: slither, echidna, medusa, hevm, halmos) and their shared build.

Build (setup, outside the budget). The target's Foundry project root is the nearest ancestor of a labelled .sol file
holding foundry.toml (else the repository root, with Foundry's defaults). Its submodules are fetched at their gitlinked
commits, its npm dependencies installed from its lockfile when its remappings name node_modules (Morph: holon.replay's
pinned sol_deps tree). A unit project beside the checkout then compiles only what the baselines analyse: holon_src/
HolonScope.sol importing every scope .sol file, with the project's compiler settings (forge config) and its remappings
made absolute, plus holon_target/=<project root>/. The harness rule's generated contracts (H_<C> for the fuzzers,
HS_<C> for halmos) are added to holon_src/ after slither has run on the scope-only build.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath

from . import core

FORGE = None


def forge() -> str:
    return core.config()["replay"]["forge"]


def solc_pinned() -> str:
    return core.config()["replay"]["solc"]


def env() -> dict:
    hevm = core.config()["hevm"]
    path = [str(core.PY), str(Path(forge()).parent), str(Path(hevm["path"]).parent), str(Path(hevm["solver"]["path"]).parent),
            str(core.TOOLS / "echidna-2.4.0"), str(core.TOOLS / "medusa-1.5.1"), "/usr/local/bin", "/usr/bin", "/bin",
            "/opt/node22/bin"]
    return {"PATH": ":".join(path), "FOUNDRY_DISABLE_NIGHTLY_WARNING": "1"}


# ------------------------------------------------------------------------------------------------- build
def project_root(src: Path, files: list[str]) -> Path:
    for f in files:
        if not f.endswith(".sol"):
            continue
        p = (src / f).parent
        while True:
            if (p / "foundry.toml").is_file():
                return p
            if p == src:
                break
            p = p.parent
    return src


def _pragma(text: str) -> str | None:
    m = re.search(r"^\s*pragma\s+solidity\s+([^;]+);", text, re.M)
    return m.group(1).strip() if m else None


def build(system: str, target: str) -> dict:
    """The unit project (cached): {"ok", "unit", "proj", "src", "log", "setup_s", "submodules", "scope", "reason"}."""
    src = core.checkout(system, target)
    unit = core.WORK / system / target / "sol"
    state = unit / "holon-build.json"
    if state.is_file():
        return core.load(state)
    shutil.rmtree(unit, ignore_errors=True)
    (unit / "holon_src").mkdir(parents=True)
    logs, setup = [], 0.0
    sol_scope = core.scope_files(src, system, target, ".sol")
    proj = project_root(src, core.labelled_files(system, target))
    out = {"ok": False, "unit": str(unit), "proj": str(proj), "src": str(src), "scope": sol_scope, "submodules": [],
           "reason": None}

    def step(argv, cwd, timeout=3600, e=None):
        nonlocal setup
        code, text, dt = core.run_setup(argv, cwd, timeout, {**env(), **(e or {})})
        setup += dt
        logs.append(f"$ {' '.join(argv)}  (in {cwd}, exit {code})\n{core.tail(text, 3000)}")
        return code, text

    try:
        if system == "corpus":
            subs = [s for s in core.submodules_list(src) if (src / s["path"]).resolve().is_relative_to(proj.resolve())
                    or proj == src]
            out["submodules"] = core.fetch_submodules(src, subs)
        if system == "morph":
            from ... import replay
            replay._sol_deps(proj)
        cfg_has = (proj / "foundry.toml").is_file()
        if cfg_has:
            remaps_txt = step([forge(), "remappings"], proj)[1]
        else:
            remaps_txt = ""
        needs_nm = "node_modules" in remaps_txt or (not cfg_has and (proj / "package.json").is_file())
        if system == "corpus" and needs_nm and not (proj / "node_modules").is_dir() and (proj / "package.json").is_file():
            if (proj / "yarn.lock").is_file():
                step(["yarn", "install", "--frozen-lockfile", "--ignore-scripts", "--non-interactive"], proj)
            else:
                step(["npm", "ci", "--ignore-scripts", "--no-audit", "--no-fund"], proj)
        conf = {}
        if cfg_has:
            code, text = step([forge(), "config", "--json"], proj)
            if code == 0:
                conf = json.JSONDecoder().raw_decode(text[text.index("{"):])[0]
            remaps_txt = step([forge(), "remappings"], proj)[1]
        remaps = []
        for line in remaps_txt.splitlines():
            line = line.strip()
            if "=" not in line or line.startswith("Error"):
                continue
            k, v = line.split("=", 1)
            if ":" in k:
                continue
            vp = Path(v) if v.startswith("/") else proj / v
            remaps.append(f"{k}={vp}{'/' if v.endswith('/') else ''}")
        for d in sorted(p.name for p in proj.iterdir() if p.is_dir() and not p.name.startswith(".")):
            if d not in ("out", "cache", "artifacts", "forge-artifacts"):
                remaps.append(f"{d}/={proj / d}/")
        remaps.append(f"holon_target/={proj}/")
        if system == "morph":
            remaps.append(f"node_modules/={proj / 'node_modules'}/")
        solc = conf.get("solc") or conf.get("solc_version")
        if system == "morph":
            solc = solc_pinned()
        first = (src / sol_scope[0]).read_text(encoding="utf-8", errors="replace") if sol_scope else ""
        pragma = _pragma(first) or ">=0.4.0"
        lines = ["[profile.default]", "src = 'holon_src'", "out = 'out'", "libs = []", "test = 'holon_test'",
                 "script = 'holon_script'", "build_info = true", "ast = true",
                 "extra_output = ['storageLayout', 'metadata']", "bytecode_hash = 'none'",
                 f"allow_paths = [{json.dumps(str(proj))}, {json.dumps(str(src))}]",
                 "remappings = [" + ", ".join(json.dumps(r) for r in sorted(set(remaps))) + "]"]
        if solc:
            lines.append(f"solc = {json.dumps(str(solc))}")
        else:
            lines.append("auto_detect_solc = true")
        for k in ("evm_version", "optimizer", "optimizer_runs", "via_ir"):
            if k in conf and conf[k] is not None:
                lines.append(f"{k} = {json.dumps(conf[k])}")
        (unit / "foundry.toml").write_text("\n".join(lines) + "\n")
        imports = "".join(f'import "holon_target/{(src / f).relative_to(proj).as_posix()}";\n' for f in sol_scope
                          if (src / f).resolve().is_relative_to(proj.resolve()))
        (unit / "holon_src" / "HolonScope.sol").write_text(f"// SPDX-License-Identifier: UNLICENSED\npragma solidity {pragma};\n{imports}")
        code, text = step([forge(), "build", "--root", str(unit)], unit, e={"FOUNDRY_PROFILE": "default"})
        if code != 0:
            out["reason"] = "forge build of the scope failed: " + core.tail(text, 600)
        else:
            out["ok"] = True
    except Exception as ex:  # noqa: BLE001
        out["reason"] = f"setup failed: {type(ex).__name__}: {ex}"
    out["setup_s"] = round(setup, 3)
    (unit / "holon-build.log").write_text("\n\n".join(logs))
    out["log"] = str(unit / "holon-build.log")
    state.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


# ------------------------------------------------------------------------------------------------- artifacts
def _line_starts(text: str) -> list[int]:
    starts = [0]
    for i, ch in enumerate(text.encode("utf-8")):
        if ch == 10:
            starts.append(i + 1)
    return starts


def _line_of(starts: list[int], off: int) -> int:
    lo, hi = 0, len(starts)
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if starts[mid] <= off:
            lo = mid
        else:
            hi = mid
    return lo + 1


def rel_of(b: dict, abs_or_import: str) -> str | None:
    """A compiler source path -> the checkout-relative path (or None outside the checkout)."""
    src, proj = Path(b["src"]), Path(b["proj"])
    p = abs_or_import
    if p.startswith("holon_target/"):
        cand = proj / p[len("holon_target/"):]
    elif p.startswith("/"):
        cand = Path(p)
    else:
        cand = Path(b["unit"]) / p
    try:
        return cand.resolve().relative_to(src.resolve()).as_posix()
    except ValueError:
        return None


def artifacts(b: dict) -> list[dict]:
    """Every compiled contract: {name, file (checkout-relative or None), kind, abstract, abi, deployed, bytecode, ast
    functions: {selector or name: (rel file, a, b)}}."""
    out = []
    unit = Path(b["unit"])
    for j in sorted((unit / "out").glob("*/*.json")):
        if j.parent.name == "build-info":
            continue
        try:
            d = core.load(j)
        except Exception:  # noqa: BLE001
            continue
        ast = d.get("ast") or {}
        path = ast.get("absolutePath") or ""
        rel = rel_of(b, path)
        name = j.stem
        node = next((n for n in ast.get("nodes", []) if n.get("nodeType") == "ContractDefinition" and n.get("name") == name), None)
        if node is None:
            continue
        funcs = {}
        if rel:
            text = (Path(b["src"]) / rel).read_text(encoding="utf-8", errors="replace")
            starts = _line_starts(text)
            for f in node.get("nodes", []):
                if f.get("nodeType") != "FunctionDefinition":
                    continue
                s, n, _ = (int(x) for x in f["src"].split(":"))
                span = (rel, _line_of(starts, s), _line_of(starts, s + max(n - 1, 0)))
                key = f.get("functionSelector") or f.get("kind") + ":" + f.get("name", "")
                funcs[key] = span
                funcs["name:" + f.get("name", "")] = span
        out.append({"name": name, "file": rel, "kind": node.get("contractKind"), "abstract": bool(node.get("abstract")),
                    "abi": d.get("abi", []), "deployed": (d.get("deployedBytecode") or {}).get("object", ""),
                    "bytecode": (d.get("bytecode") or {}).get("object", ""), "functions": funcs,
                    "contract_span": (rel, *[_line_of(starts, int(node["src"].split(":")[0]))] * 2) if rel else None})
    return out


def deployables(b: dict) -> list[dict]:
    scope = set(b["scope"])
    seen, out = set(), []
    for a in artifacts(b):
        if a["file"] in scope and a["kind"] == "contract" and not a["abstract"] and len(a["bytecode"]) > 2 \
                and a["name"] not in seen and "__$" not in a["bytecode"]:
            seen.add(a["name"])
            out.append(a)
    return sorted(out, key=lambda a: a["name"])


def selector_span(a: dict, selector: str):
    return a["functions"].get(selector.lower().removeprefix("0x"))


# ------------------------------------------------------------------------------------------------- harness rule
def _type(p: dict) -> str | None:
    t, it = p["type"], p.get("internalType") or p["type"]
    suffix = t[len(t.rstrip("[]0123456789")):] if t.startswith("tuple") else ""
    if t.startswith("tuple"):
        m = re.match(r"struct ([A-Za-z0-9_.]+)", it)
        return m.group(1) + suffix if m else None
    m = re.match(r"(enum|contract|interface) ([A-Za-z0-9_.]+)(.*)", it)
    if m:
        return m.group(2) + m.group(3)
    if "function" in t:
        return None
    return t


def _dynamic(t: str, p: dict) -> bool:
    return t.endswith("]") or p["type"] in ("bytes", "string") or p["type"].startswith("tuple")


def _decl(p: dict, i: int, prefix: str) -> tuple[str, str] | None:
    t = _type(p)
    if t is None:
        return None
    loc = " memory" if _dynamic(t, p) else ""
    return f"{t}{loc} {prefix}{i}", t


def _default(p: dict, i: int) -> list[str] | None:
    t = _type(p)
    if t is None:
        return None
    d = _decl(p, i, "a")[0]
    if p["type"] == "address" and (p.get("internalType") or "").startswith(("contract", "interface")):
        return [f"{d} = {t}(address(this));"]
    if p["type"] == "address":
        return [f"{d} = address(this);"]
    if p["type"] == "address payable":
        return [f"{d} = payable(address(this));"]
    return [f"{d};"]


def harnesses(b: dict, deps: list[dict]) -> dict:
    """Write H_<C>.sol and HS_<C>.sol per deployable; returns {C: {"skipped": [...], "fuzz": bool, "halmos": bool,
    "forward": {harness fn signature: target selector}}}."""
    info = {}
    hdir = Path(b["unit"]) / "holon_src"
    pragma = _pragma((hdir / "HolonScope.sol").read_text()) or ">=0.4.0"
    for a in deps:
        ctor = next((x for x in a["abi"] if x["type"] == "constructor"), {"inputs": [], "stateMutability": "nonpayable"})
        pre = []
        for i, p in enumerate(ctor["inputs"]):
            d = _default(p, i)
            if d is None:
                pre = None
                break
            pre += d
        rec = {"skipped": [], "fuzz": False, "halmos": False, "forward": {}}
        info[a["name"]] = rec
        if pre is None:
            rec["skipped"].append("constructor: a parameter type the generator cannot express")
            continue
        args = ", ".join(f"a{i}" for i in range(len(ctor["inputs"])))
        body_f, body_h = [], []
        for k, fn in enumerate(x for x in a["abi"] if x["type"] == "function"):
            if fn.get("stateMutability") in ("view", "pure"):
                continue
            decls = [_decl(p, i, "x") for i, p in enumerate(fn["inputs"])]
            sig = f"{fn['name']}({','.join(p['type'] for p in fn['inputs'])})"
            if any(d is None for d in decls):
                rec["skipped"].append(sig)
                continue
            params = ", ".join(d[0] for d in decls)
            call = ", ".join(f"x{i}" for i in range(len(decls)))
            pay = fn.get("stateMutability") == "payable"
            body_f.append(f"    function {fn['name']}({params}) public{' payable' if pay else ''} {{\n"
                          f"        c.{fn['name']}{'{value: msg.value}' if pay else ''}({call});\n    }}")
            body_h.append(f"    function check_{fn['name']}_{k}({params}) public {{\n        c.{fn['name']}({call});\n    }}")
            rec["forward"][sig] = sig
            rec["forward"][f"check_{fn['name']}_{k}"] = sig
        imp = f'import "holon_target/{(Path(b["src"]) / a["file"]).relative_to(Path(b["proj"])).as_posix()}";'
        head = f"// SPDX-License-Identifier: UNLICENSED\npragma solidity {pragma};\n{imp}\n"
        ctor_body = "\n".join("        " + x for x in pre)
        (hdir / f"H_{a['name']}.sol").write_text(
            head + f"contract H_{a['name']} {{\n    {a['name']} c;\n    constructor() payable {{\n{ctor_body}\n"
            f"        c = new {a['name']}({args});\n    }}\n" + "\n".join(body_f) + "\n}\n")
        (hdir / f"HS_{a['name']}.sol").write_text(
            head + f"contract HS_{a['name']} {{\n    {a['name']} c;\n    function setUp() public {{\n{ctor_body}\n"
            f"        c = new {a['name']}({args});\n    }}\n" + "\n".join(body_h) + "\n}\n")
        rec["fuzz"] = rec["halmos"] = True
    return info


def build_harnesses(system: str, target: str) -> dict:
    """The harness build (cached), in its own unit project beside the scope-only one (so slither and the miner read a
    build without generated contracts): returns {"ok", "reason", "info", "deployables", "setup_s", "unit"}."""
    b = build(system, target)
    hunit = core.WORK / system / target / "solh"
    state = hunit / "holon-harness.json"
    if state.is_file():
        return core.load(state)
    out = {"ok": False, "reason": b["reason"], "info": {}, "deployables": [], "setup_s": 0.0, "unit": str(hunit)}
    if b["ok"]:
        shutil.rmtree(hunit, ignore_errors=True)
        hunit.mkdir(parents=True)
        shutil.copyfile(Path(b["unit"]) / "foundry.toml", hunit / "foundry.toml")
        shutil.copytree(Path(b["unit"]) / "holon_src", hunit / "holon_src")
        deps = deployables(b)
        out["deployables"] = [a["name"] for a in deps]
        out["info"] = harnesses(dict(b, unit=str(hunit)), deps)
        code, text, dt = core.run_setup([forge(), "build", "--root", str(hunit)], hunit, 3600, env())
        out["setup_s"] = round(dt, 3)
        if code != 0:
            # a harness the compiler rejects is dropped (recorded) and the rest rebuilt once
            bad = sorted(set(re.findall(r"holon_src/(HS?_[A-Za-z0-9_]+)\.sol", text)))
            for n in bad:
                (hunit / "holon_src" / f"{n}.sol").unlink(missing_ok=True)
                c = n.split("_", 1)[1]
                if c in out["info"]:
                    out["info"][c]["fuzz" if n.startswith("H_") else "halmos"] = False
                    out["info"][c]["skipped"].append(f"{n}: rejected by the compiler")
            code, text, dt = core.run_setup([forge(), "build", "--root", str(hunit)], hunit, 3600, env())
            out["setup_s"] = round(out["setup_s"] + dt, 3)
        out["ok"] = code == 0
        out["reason"] = None if code == 0 else "harness build failed: " + core.tail(text, 600)
        (hunit / "holon-harness.log").write_text(text)
    state.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    return out


# ------------------------------------------------------------------------------------------------- the runners
def _base(b: dict, h: dict | None = None) -> dict:
    return {"setup_s": round(b.get("setup_s", 0) + ((h or {}).get("setup_s") or 0), 3),
            "submodules": b.get("submodules", []), "scope": b.get("scope", [])}


def _error(b: dict, reason: str, h: dict | None = None) -> dict:
    return {"status": "error", "reason": reason, "findings": [], "units": [], "commands": [], "seeds": {},
            "budget_exhausted": None, **_base(b, h)}


def _src_loc(b: dict, sm: dict):
    f = sm.get("filename_absolute") or sm.get("filename_relative") or ""
    rel = rel_of(b, f)
    lines = sm.get("lines") or []
    if not rel or not lines:
        return None
    return core.loc(rel, min(lines), max(lines))


def run_slither(system: str, target: str, wall: float, cpu: int) -> dict:
    b = build(system, target)
    if not b["ok"]:
        return _error(b, b["reason"])
    unit = Path(b["unit"])
    js = unit / "slither.json"
    js.unlink(missing_ok=True)
    argv = [str(core.PY / "slither"), ".", "--ignore-compile", "--json", str(js)]
    u = core.Units(wall, 1)
    r = core.run_bounded(argv, unit, u.share(), cpu, env(), unit / "slither.log")
    u.done("slither", r["wall_s"], r["cpu_s"], exit=r["exit"], timed_out=r["timed_out"])
    if not js.is_file():
        return {**_error(b, "slither produced no JSON: " + core.tail(r["output"], 600)), "units": u.used,
                "commands": [" ".join(argv)]}
    data = core.load(js)
    fs = []
    for d in (data.get("results") or {}).get("detectors", []):
        locs = [x for x in (_src_loc(b, e.get("source_mapping") or {}) for e in d.get("elements", [])) if x]
        fs.append(core.finding(d.get("check", "?"), (d.get("description") or "").strip(), locs,
                               f"{d.get('impact')}/{d.get('confidence')}"))
    return {"status": "run", "reason": None if data.get("success") else f"slither reported an error: {data.get('error')}",
            "findings": fs, "units": u.used, "commands": [" ".join(argv)], "seeds": {},
            "budget_exhausted": r["timed_out"], **_base(b)}


def _target_span(arts: dict, cname: str, sig_or_name: str):
    a = arts.get(cname)
    if not a:
        return None
    name = sig_or_name.split("(")[0]
    if name.startswith("check_"):
        name = name[len("check_"):].rsplit("_", 1)[0]
    span = a["functions"].get("name:" + name)
    return core.loc(span[0], span[1], span[2], f"{cname}.{name}") if span else None


def _harness_units(system, target):
    b = build(system, target)
    if not b["ok"]:
        return b, None, _error(b, b["reason"])
    h = build_harnesses(system, target)
    if not h["ok"]:
        return b, h, _error(b, h["reason"], h)
    return b, h, None


def _fuzz(system, target, wall, cpu, tool):
    b, h, err = _harness_units(system, target)
    if err:
        return err
    unit = Path(h["unit"])
    arts = {a["name"]: a for a in artifacts(b)}
    names = [c for c in h["deployables"] if h["info"][c]["fuzz"]]
    u = core.Units(wall, len(names))
    fs, cmds, exhausted = [], [], False
    for c in names:
        if tool == "echidna":
            argv = [str(core.TOOLS / "echidna-2.4.0" / "echidna"), ".", "--contract", f"H_{c}", "--test-mode",
                    "assertion", "--workers", "1", "--timeout", str(int(u.share())), "--format", "text",
                    "--crytic-args", "--ignore-compile"]
            cfgp = None
        else:
            cfgp = unit / f"medusa_{c}.json"
            cfgp.write_text(json.dumps({
                "fuzzing": {"workers": 1, "timeout": int(u.share()), "targetContracts": [f"H_{c}"],
                            "corpusDirectory": "", "testLimit": 0,
                            "testing": {"stopOnFailedTest": False, "assertionTesting": {"enabled": True},
                                        "propertyTesting": {"enabled": False}, "optimizationTesting": {"enabled": False}}},
                "compilation": {"platform": "crytic-compile",
                                "platformConfig": {"target": ".", "solcVersion": "", "exportDirectory": "",
                                                   "args": ["--ignore-compile"]}}}, indent=1))
            argv = [str(core.TOOLS / "medusa-1.5.1" / "medusa"), "fuzz", "--config", str(cfgp), "--no-color"]
        r = core.run_bounded(argv, unit, u.share() + 60, cpu, env(), unit / f"{tool}_{c}.log")
        u.done(c, r["wall_s"], r["cpu_s"], exit=r["exit"], timed_out=r["timed_out"])
        exhausted |= r["timed_out"]
        cmds.append(" ".join(argv))
        out = r["output"]
        if tool == "echidna":
            hits = re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*\([^)]*\)):\s*failed", out, re.M) + \
                re.findall(r"Test ([A-Za-z_][A-Za-z0-9_]*\([^)]*\)) falsified", out)
        else:
            hits = re.findall(r"\[FAILED\]\s*Assertion Test:\s*H_[A-Za-z0-9_]+\.([A-Za-z_][A-Za-z0-9_]*\([^)]*\))", out)
        for sig in sorted(set(hits)):
            l = _target_span(arts, c, sig)
            fs.append(core.finding("assertion-failure", f"{tool}: assertion failure (stock property) when calling "
                                   f"{c}.{sig} through the harness", [l] if l else [], None,
                                   {"output": core.tail(out[out.find(sig):], 1200)}))
    return {"status": "run", "reason": None if names else "no deployable scope contract with a harness",
            "findings": fs, "units": u.used, "commands": cmds, "seeds": {"echidna": "none: echidna 2.4.0 refuses --seed with --timeout (a wall-clock budget makes runs non-deterministic); the budget wins"} if tool == "echidna" else
            {"medusa": "not seedable from the configuration used (recorded)"}, "budget_exhausted": exhausted,
            "harness": h["info"], **_base(b, h)}


def run_echidna(system, target, wall, cpu):
    return _fuzz(system, target, wall, cpu, "echidna")


def run_medusa(system, target, wall, cpu):
    return _fuzz(system, target, wall, cpu, "medusa")


def run_hevm(system, target, wall, cpu):
    b = build(system, target)
    if not b["ok"]:
        return _error(b, b["reason"])
    unit = Path(b["unit"])
    hv = core.config()["hevm"]
    deps = deployables(b)
    u = core.Units(wall, len(deps))
    fs, cmds, exhausted = [], [], False
    for a in deps:
        argv = [hv["path"], "symbolic", "--code", a["deployed"], "--solver", "cvc5"]
        r = core.run_bounded(argv, unit, u.share(), cpu, env(), unit / f"hevm_{a['name']}.log")
        u.done(a["name"], r["wall_s"], r["cpu_s"], exit=r["exit"], timed_out=r["timed_out"])
        exhausted |= r["timed_out"]
        cmds.append(" ".join(argv[:2] + ["--code", f"<runtime bytecode of {a['name']}>"] + argv[4:]))
        out = r["output"]
        if "counterexample" in out.lower() and "no counterexample" not in out.lower():
            sels = sorted(set(m.lower() for m in re.findall(r"Calldata:\s*\n?\s*0x([0-9a-fA-F]{8})", out)))
            sels += sorted(set(m.lower() for m in re.findall(r"\b0x([0-9a-f]{8})[0-9a-f]*\b", out))) if not sels else []
            spans = [selector_span(a, s) for s in sels]
            locs = [core.loc(s[0], s[1], s[2]) for s in spans if s]
            fs.append(core.finding("assertion-violation", f"hevm: counterexample to the default assertion check in "
                                   f"{a['name']}", locs or ([core.loc(*a['contract_span'])] if a['contract_span'] else []),
                                   None, {"output": core.tail(out, 1500)}))
    return {"status": "run", "reason": None if deps else "no deployable scope contract", "findings": fs,
            "units": u.used, "commands": cmds, "seeds": {}, "budget_exhausted": exhausted, **_base(b)}


def run_halmos(system, target, wall, cpu):
    b, h, err = _harness_units(system, target)
    if err:
        return err
    unit = Path(h["unit"])
    arts = {a["name"]: a for a in artifacts(b)}
    names = [c for c in h["deployables"] if h["info"][c]["halmos"]]
    u = core.Units(wall, len(names))
    fs, cmds, exhausted = [], [], False
    for c in names:
        argv = [str(core.PY / "halmos"), "--root", ".", "--contract", f"HS_{c}", "--function", "check_"]
        r = core.run_bounded(argv, unit, u.share(), cpu, env(), unit / f"halmos_{c}.log")
        u.done(c, r["wall_s"], r["cpu_s"], exit=r["exit"], timed_out=r["timed_out"])
        exhausted |= r["timed_out"]
        cmds.append(" ".join(argv))
        for fn in sorted(set(re.findall(r"\[FAIL\]\s+(check_[A-Za-z0-9_]+)\(", r["output"]))):
            l = _target_span(arts, c, fn)
            fs.append(core.finding("assertion-failure", f"halmos: counterexample (assertion failure) for {c} via "
                                   f"{fn}", [l] if l else [], None, {"output": core.tail(r["output"], 1200)}))
    return {"status": "run", "reason": None if names else "no deployable scope contract with a harness",
            "findings": fs, "units": u.used, "commands": cmds, "seeds": {}, "budget_exhausted": exhausted,
            "harness": h["info"], **_base(b, h)}


RUNNERS = {"slither": run_slither, "echidna": run_echidna, "medusa": run_medusa, "hevm": run_hevm,
           "halmos": run_halmos}
