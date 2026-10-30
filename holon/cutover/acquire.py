"""Rules A1-A3: the registry's explorer record decided by the sidecar's compile-match criterion, and the eras of the
migration with the implementations live in the old version's era.

results/<M>/cutover/acquisition.json: {"acquisition_version", "registry": {proxy, implementation, set_block}, "explorer":
{record, sha256, verified, compiler, contract, settings}, "compile_match", "unit_equal", "units": {path: equal |
equal_modulo_import_prefix | differs | not_in_tag}, "label", "eras", "era_implementations"}. The compile runs the pinned
solc on the explorer's recorded standard-JSON input (its own settings, its own sources) with an output selection of the
named contract's runtime code; the identity is I63's (immutable and link ranges zeroed, CBOR metadata stripped).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from . import BundleError, Ctx, Refused, render, sha256_bytes, sha256_file

ACQUISITION_VERSION = "holon-cutover-acquisition/0.1"


def explorer_entry(rec: dict) -> dict:
    r = rec["response"]
    res = r.get("result") if isinstance(r, dict) else None
    if not isinstance(res, list) or not res:
        raise Refused("the explorer record holds no getsourcecode result")
    return res[0]


def standard_input(entry: dict) -> dict | None:
    src = entry.get("SourceCode")
    if not src:
        return None
    t = str(src).strip()
    if t.startswith("{{") and t.endswith("}}"):
        return json.loads(t[1:-1])
    if t.startswith("{"):
        obj = json.loads(t)
        return obj if "sources" in obj else {"language": "Solidity", "sources": obj, "settings": {}}
    return {"language": "Solidity", "sources": {f"{entry.get('ContractName') or 'Contract'}.sol": {"content": t}},
            "settings": {}}


def runtime_identity(ctx: Ctx, inp: dict, name: str) -> tuple:
    """(identity sha256, ranges) of contract `name` compiled from the recorded input by the pinned solc."""
    from ..frontends import Refused as FRefused
    from ..frontends.solidity import compile as comp
    from ..frontends.solidity.history import identity as code_identity
    try:
        solc, _sha, _ver = comp.check_solc(ctx.cfg, "0.8.24")
    except FRefused as e:
        raise Refused(str(e)) from e
    settings = dict(inp.get("settings") or {})
    settings["outputSelection"] = {"*": {"*": ["evm.deployedBytecode.object",
                                               "evm.deployedBytecode.immutableReferences",
                                               "evm.deployedBytecode.linkReferences"]}}
    req = {"language": inp.get("language") or "Solidity", "sources": inp["sources"], "settings": settings}
    with tempfile.TemporaryDirectory(prefix="holon-cutover-acq-") as d:
        p = subprocess.run([solc, "--standard-json"], input=json.dumps(req, sort_keys=True), capture_output=True,
                           text=True, cwd=d, timeout=7200)
    out = json.loads(p.stdout)
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise BundleError("; ".join((e.get("formattedMessage") or e["message"])[:300] for e in errs[:3]))
    hits = [c for f in out.get("contracts", {}).values() for n, c in f.items() if n == name]
    if len(hits) != 1:
        raise BundleError(f"the recorded input compiles {len(hits)} contracts named {name}")
    dep = hits[0]["evm"]["deployedBytecode"]
    ranges = sorted([[r["start"], r["length"]] for rs in (dep.get("immutableReferences") or {}).values() for r in rs]
                    + [[r["start"], r["length"]] for f in (dep.get("linkReferences") or {}).values()
                       for rs in f.values() for r in rs])
    return sha256_bytes(code_identity(bytes.fromhex(dep["object"]), ranges)), ranges


def tag_text(ctx: Ctx, commit: str, path: str) -> str | None:
    repo = ctx.bundle().source_repo()
    p = subprocess.run(["git", "-C", repo, "-c", "protocol.allow=never", "-c", "gc.auto=0", "-c",
                        "maintenance.auto=false", "show", f"{commit}:{path}"], capture_output=True,
                       env={"GIT_TERMINAL_PROMPT": "0", "PATH": "/usr/bin:/bin:/usr/local/bin"})
    return p.stdout.decode("utf-8") if p.returncode == 0 else None


def build(ctx: Ctx, log=print) -> dict:
    from ..frontends.solidity.history import identity as code_identity
    acq = ctx.side["acquisition"]
    reg = acq["registry"]
    rel = f"{ctx.out('explorer')}/{reg['implementation']}.json"
    if not ctx.path(rel).is_file():
        raise Refused(f"{rel} is missing (A1: the explorer is read once, by the session)")
    rec = ctx.load(rel)
    entry = explorer_entry(rec)
    inp = standard_input(entry)
    unit = acq["unit"]
    root_dir = unit["path"].split("/", 1)[0] + "/"
    units, unit_equal, compile_match = {}, False, False
    if inp is not None:
        for path, s in sorted(inp["sources"].items()):
            text = (s.get("content") or "").replace("\r\n", "\n")
            tagged = tag_text(ctx, unit["commit"], root_dir + path)
            if tagged is None:
                units[path] = "not_in_tag"
            elif tagged == text:
                units[path] = "equal"
            elif tagged == _strip_prefix(text):
                units[path] = "equal_modulo_import_prefix"
            else:
                units[path] = "differs"
            if root_dir + path == unit["path"]:
                unit_equal = sha256_bytes(text.encode("utf-8")) == unit["sha256"]
        ident, ranges = runtime_identity(ctx, inp, reg["contract"])
        code = bytes.fromhex(ctx.path(reg["code"]).read_text(encoding="utf-8").strip().removeprefix("0x"))
        compile_match = ident == sha256_bytes(code_identity(code, ranges))
    labels = acq["labels"]
    label = labels["verified"] if (inp is not None and unit_equal and compile_match) else labels["tag_matched"]
    eras = {k: dict(v) for k, v in sorted(acq["eras"].items())}
    tl = ctx.load(reg["timeline"])
    lo, hi = eras[sorted(eras)[0]]["from_block"], eras[sorted(eras)[0]]["to_block"]
    live = {}
    for name, px in sorted(tl["proxies"].items()):
        before = [u for u in px["upgrades"] if u["block"] <= lo]
        inside = [u for u in px["upgrades"] if lo < u["block"] < hi]
        cur = before[-1] if before else None
        live[name] = {"proxy": px["address"], "implementation": cur["implementation"] if cur else None,
                      "set_block": cur["block"] if cur else None, "matches": cur["matches"] if cur else [],
                      "upgrades_inside_era": [u["implementation"] for u in inside]}
    log(f"label: {label}; compile match {compile_match}; unit equal {unit_equal}")
    doc = {"acquisition_version": ACQUISITION_VERSION, "sidecar": ctx.ref(ctx.side_rel),
           "registry": {k: reg[k] for k in ("proxy", "implementation", "set_block", "contract")},
           "explorer": {"record": rel, "sha256": sha256_file(ctx.path(rel)), "verified": inp is not None,
                        "compiler": entry.get("CompilerVersion"), "contract": entry.get("ContractName"),
                        "settings": (inp or {}).get("settings")},
           "compile_match": compile_match, "unit_equal": unit_equal, "units": units, "label": label,
           "eras": eras, "era_implementations": live}
    return {ctx.out("acquisition"): render(doc)}


def _strip_prefix(text: str) -> str:
    """A verified unit read back with the import prefix the verification added removed: an import path that starts
    with node_modules/ is read as the package path a remapping resolves."""
    return text.replace('"node_modules/', '"')
