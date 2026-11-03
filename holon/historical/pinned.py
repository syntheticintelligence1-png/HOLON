"""The deployed implementation against the pinned build (I23-P1; the instrument's implementation.comparison).

pinned_build(inst, code, root) compiles the instrument's pinned source (implementation.pinned: source, contract, the
checkout of config extract.sources / replay.morph at pinned.commit) with the pinned solc (config replay.solc, sha256
replay.solc_sha256) under each of the instrument's compiler_configs (optimizer runs, evm version, metadata bytecode
hash), standard JSON, base path the checkout, include path <replay.sol_deps>/node_modules. It compares the runtime
code read from the chain with each build's deployedBytecode, every immutableReferences range masked (zeroed) on both
sides, and every linkReferences range too:

    {"matched_config": "<name>" | null, "equal_masked": bool, "immutables_masked": n,
     "configs": {"<name>": {"equal_masked": bool, "length": n, "immutables_masked": n, "first_difference": n | null}}}

matched_config is the first configuration (by name) whose masked bytes are equal; immutables_masked is that
configuration's number of masked ranges (else the first configuration's). A build is cached outside the repository
(holon.bend.build_dir()/historical/) by the sha256 of its standard-JSON input and of the solc binary.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class PinnedError(RuntimeError):
    pass


def _config(root: Path) -> dict:
    return json.loads((Path(root) / "config" / "holon.json").read_text())


def checkout(cfg: dict, commit: str, root: Path = ROOT) -> Path:
    import types
    from ..replay import morph_path
    for p in list(((cfg.get("extract") or {}).get("sources") or {}).values()) + [str(morph_path(types.SimpleNamespace(), root))]:
        if not p or not Path(p).is_dir():
            continue
        head = subprocess.run(["git", "-C", str(p), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=60)
        if head.returncode == 0 and head.stdout.strip() == commit:
            return Path(p)
    raise PinnedError(f"no checkout at the pinned commit {commit} (config extract.sources, the replay checkout)")


def build(inst: dict, name: str, root: Path = ROOT) -> dict:
    """{"object": hex, "immutables": [[start, length], ..], "links": [[start, length], ..]} of one configuration."""
    from ..bend import build_dir
    cfg = _config(root)
    rep = cfg.get("replay") or {}
    solc, pin = rep.get("solc"), rep.get("solc_sha256")
    if not solc or not Path(solc).is_file():
        raise PinnedError(f"the pinned solc {solc!r} is missing")
    sha = hashlib.sha256(Path(solc).read_bytes()).hexdigest()
    if sha != pin:
        raise PinnedError(f"solc {solc} hashes to {sha}, not the pin replay.solc_sha256")
    pin_ = inst["implementation"]["pinned"]
    cc = inst["implementation"]["compiler_configs"][name]
    src = checkout(cfg, pin_["commit"], root)
    unit = pin_["source"]
    settings = {"evmVersion": cc["evm_version"], "optimizer": {"enabled": True, "runs": int(cc["optimizer_runs"])},
                "metadata": {"bytecodeHash": cc["bytecode_hash"]},
                "outputSelection": {unit: {pin_["contract"]: ["evm.deployedBytecode.object",
                                                              "evm.deployedBytecode.immutableReferences",
                                                              "evm.deployedBytecode.linkReferences"]}}}
    inp = json.dumps({"language": "Solidity", "sources": {unit: {"content": (src / unit).read_text()}},
                      "settings": settings}, sort_keys=True)
    key = hashlib.sha256((sha + inp).encode()).hexdigest()
    cache = build_dir(root) / "historical" / f"pinned-{key[:24]}.json"
    if cache.is_file():
        try:
            return json.loads(cache.read_text())
        except ValueError:
            pass
    cmd = [solc, "--standard-json", "--base-path", "."]
    deps = rep.get("sol_deps")
    if deps and (Path(deps) / "node_modules").is_dir():
        cmd += ["--include-path", str(Path(deps) / "node_modules")]
    p = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=3600, cwd=str(src))
    try:
        out = json.loads(p.stdout)
    except ValueError:
        raise PinnedError(f"solc produced no JSON (exit {p.returncode}): {p.stderr[:400]}") from None
    errs = [e for e in out.get("errors", []) if e.get("severity") == "error"]
    if errs:
        raise PinnedError("compile errors: " + "; ".join((e.get("formattedMessage") or e.get("message", ""))[:300]
                                                        for e in errs[:3]))
    c = ((out.get("contracts") or {}).get(unit) or {}).get(pin_["contract"])
    if not c:
        raise PinnedError(f"no {pin_['contract']} in {unit} in the solc output")
    d = c["evm"]["deployedBytecode"]
    imm = sorted([r["start"], r["length"]] for refs in (d.get("immutableReferences") or {}).values() for r in refs)
    links = sorted([r["start"], r["length"]] for f in (d.get("linkReferences") or {}).values()
                   for refs in f.values() for r in refs)
    res = {"object": d["object"].lower(), "immutables": imm, "links": links}
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_name(cache.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(res, sort_keys=True))
    os.replace(tmp, cache)
    return res


def masked(code: bytes, ranges: list) -> bytes:
    b = bytearray(code)
    for start, n in ranges:
        b[start:start + n] = bytes(min(n, max(0, len(b) - start)))
    return bytes(b)


def pinned_build(inst: dict, code: bytes, root: Path = ROOT) -> dict:
    out = {}
    for name in sorted(inst["implementation"]["compiler_configs"]):
        b = build(inst, name, root)
        ref = bytes.fromhex(b["object"])
        ranges = b["immutables"] + b["links"]
        x, y = masked(code, ranges), masked(ref, ranges)
        diff = next((i for i in range(min(len(x), len(y))) if x[i] != y[i]), None)
        if diff is None and len(x) != len(y):
            diff = min(len(x), len(y))
        out[name] = {"equal_masked": x == y, "length": len(ref), "immutables_masked": len(b["immutables"]),
                     "first_difference": diff}
    hit = next((n for n in sorted(out) if out[n]["equal_masked"]), None)
    first = sorted(out)[0] if out else None
    return {"matched_config": hit, "equal_masked": hit is not None,
            "immutables_masked": out[hit or first]["immutables_masked"] if out else 0, "configs": out}
