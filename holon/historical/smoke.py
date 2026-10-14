"""`python -m holon historical smoke`: the synthetic smoke fixtures, through the same decode and header checks, never
counted (the contract is the docstring of tests_m2/test_historical_exit.py; the instrument's synthetic_smoke).

    python -m holon historical smoke [--milestone M2]

The fixture file is the instrument's synthetic_smoke.path in the pinned checkout at synthetic_smoke.commit (its bytes
must hash to synthetic_smoke.sha256). Each fixture's calldata is decoded by holon.historical.abi: under the pinned ABI
when its selector is a pinned function's ("pinned"), else under the signature of the checkout's history that names
it ("history"). Its decoded first argument (the commit's input struct) is compared with the fixture's "expected", key
by key: a key names the struct member of that name, or the one member the instrument's synthetic_smoke.aliases maps
it to (spec/<M>/lib/historical_exit_smoke.json; the fixture file's own names). Its parent header goes through
holon.historical.header_checks: {length, ok_sol, ok_go}.

results/<M>/historical/synthetic_smoke.json: {"label": "synthetic_smoke", "counted": false, "source": {path, commit,
sha256}, "fixtures": [{name, selector, abi, decoded_equals_expected, parent: {length, ok_sol, ok_go}}]}. Synthetic
inputs never enter a window, a record, a metric or the exit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import types
from pathlib import Path

from .. import ir

ROOT = Path(__file__).resolve().parents[2]


def write(doc, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(ir.canonical_json(doc) + b"\n")
    tmp.replace(path)


def norm(v):
    if isinstance(v, (bytes, bytearray)):
        return "0x" + bytes(v).hex()
    if isinstance(v, str) and v.startswith("0x"):
        return v.lower()
    if isinstance(v, bool):
        return int(v)
    return v


def aliases(milestone: str, root: Path) -> dict:
    p = Path(root) / "spec" / milestone / "lib" / "historical_exit_smoke.json"
    return json.loads(p.read_text()).get("aliases", {}) if p.is_file() else {}


def run(milestone: str = "M2", root: Path = ROOT) -> dict:
    from . import abi as A
    from . import target as TG
    from .checks import header_checks
    from .stepper import instrument
    from ..replay import check_checkout, morph_path, replay_config
    inst = instrument(milestone, root)
    sm = inst["synthetic_smoke"]
    checkout = morph_path(types.SimpleNamespace(), root)
    sha = check_checkout(checkout, sm["commit"])
    data = (checkout / sm["path"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != sm["sha256"]:
        raise SystemExit(f"historical smoke: {sm['path']} does not hash to the instrument's sha256")
    doc = json.loads(data)
    tgt = TG.load(milestone, root)
    cfg = replay_config(root)
    pabi = A.PinnedAbi(checkout, sha, cfg["solc"], tgt)
    al = aliases(milestone, root)
    out = []
    for f in doc["fixtures"]:
        cd = bytes.fromhex(f["data"][2:])
        sel = "0x" + cd[:4].hex()
        if sel in pabi.pinned:
            fn, how = pabi.pinned[sel], "pinned"
        elif sel in pabi.legacy:
            fn, how = pabi.legacy[sel][0], "history"
        else:
            fn, how = None, None
        ok = False
        parent = None
        if fn is not None:
            try:
                dec = A.decode(fn, cd)
            except A.AbiError:
                dec = None
            if dec is not None:
                first = next(iter(dec.values()))
                if isinstance(first, dict):
                    got = {}
                    for k, v in f.get("expected", {}).items():
                        name = k if k in first else al.get(k)
                        got[k] = norm(first.get(name)) if name in first else None
                    ok = all(got[k] == norm(v) for k, v in f.get("expected", {}).items()) and bool(f.get("expected"))
                    hb = first.get(tgt["parent_header"])
                    if isinstance(hb, (bytes, bytearray)):
                        hc = header_checks(bytes(hb))
                        parent = {k: hc[k] for k in ("length", "ok_sol", "ok_go")}
        out.append({"name": f["name"], "selector": f.get("selector") or sel, "abi": how,
                    "decoded_equals_expected": ok, "parent": parent})
    return {"label": sm["label"], "counted": False,
            "source": {"path": sm["path"], "commit": sm["commit"], "sha256": sm["sha256"]}, "fixtures": out}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon historical smoke")
    ap.add_argument("--milestone", default="M2")
    a = ap.parse_args(argv)
    doc = run(a.milestone, ROOT)
    out = ROOT / "results" / a.milestone / "historical" / "synthetic_smoke.json"
    write(doc, out)
    for f in doc["fixtures"]:
        print(f"{f['name']:40s} {f['selector']} {f['abi']} decoded_equals_expected={f['decoded_equals_expected']} "
              f"parent={f['parent']}")
    print(f"wrote {out}")
    return 0
