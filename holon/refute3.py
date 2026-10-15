"""`holon refute` (I40; the contract is the docstring of tests_m3/test_refute.py): the refutation engines over a
milestone's laws, the witnesses' concretization, emitted tests, their replay and the final filter.

  python -m holon refute --milestone M [--root DIR] [--sidecar PATH] [--only STAGE,..] [--check] [--results DIR]
                         [--gen-dir DIR] [--laws ID,..]

Stages, in order: layouts, smt, fuzz, bmc, emit, replay, filter. A test milestone (T<n>) needs --sidecar (its I40
sidecar, whose "base" is the milestone sidecar spec/M3/lib/refute.json) and runs BMC on the laws holon run left
undecided in --results (and on those --laws names: a control query, whose PROVED record is never rewritten); a law BMC
refutes gets its counter-law (I30's generator, checked by Bend and BendTT) and its record as I30's pipeline writes a
REFUTED record. Exit 0 ok; 1 unreadable input or a --check difference; 2 a solver pin mismatch (nothing written).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from . import bmc as BMC
from .gen import foundry as FG
from .smt import run as SR

ROOT = Path(__file__).resolve().parents[1]
STAGES = ("layouts", "smt", "fuzz", "bmc", "emit", "replay", "filter")


def dumps(o) -> str:
    return json.dumps(o, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def load(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def rel(p: Path, root: Path) -> str:
    try:
        return str(Path(p).resolve().relative_to(Path(root).resolve()))
    except ValueError:
        return str(p)


# ------------------------------------------------------------------------------------------------ the toolchain
def toolchain(root: Path) -> dict:
    from .replay import toolchain as tc
    return tc(argparse.Namespace(forge=None, solc=None, write_pins=False), root)


def sol_project(work: Path, root: Path, tc: dict, src_dir: Path | None = None, files: list | None = None,
                binding: dict | None = None) -> Path:
    """A scratch Foundry project: a fixture's sources under src/ (or the binding's checkout tree), the pinned
    dependencies, and the given harness files under test/ (a ".txt" suffix dropped)."""
    from .replay_fragments import TOY_FOUNDRY, TOY_REMAP, harness_project
    from .replay import _sol_deps
    if binding is not None:
        from .replay import check_checkout, morph_path
        checkout = morph_path(argparse.Namespace(), root)
        check_checkout(checkout, None)
        proj = harness_project(binding, work, root, checkout, tc)
        return proj
    proj = Path(work) / "solidity"
    (proj / "src").mkdir(parents=True, exist_ok=True)
    for f in sorted(Path(src_dir).glob("*.sol")):
        shutil.copy(f, proj / "src" / f.name)
    (proj / "foundry.toml").write_text(TOY_FOUNDRY)
    (proj / "remappings.txt").write_text(TOY_REMAP)
    _sol_deps(proj, Path(tc["sol_deps"]))
    (proj / "test").mkdir(exist_ok=True)
    for f in files or []:
        name = Path(f).name
        if name.endswith(".txt"):
            name = name[:-4]
        shutil.copy(root / f, proj / "test" / name)
    return proj


def run_tests(proj: Path, tc: dict, tests: dict) -> dict:
    """Run emitted tests (name -> Solidity text) in a project: per test {"passed", "outcomes"} from its logs."""
    import re
    out = {}
    for name, text in sorted(tests.items()):
        f = proj / "test" / f"{name}.t.sol"
        f.write_text(text, encoding="utf-8")
    p = subprocess.run(["nice", "-n", "10", tc["forge"], "test", "--offline", "--use", tc["solc"], "-vv",
                        "--match-contract", "^HolonWitness_", "--match-test", r"^test_witness\(\)$"], cwd=proj, capture_output=True, text=True,
                       timeout=7200)
    text = p.stdout + p.stderr
    cur = None
    blocks: dict = {}
    for line in text.splitlines():
        m = re.search(r"Ran \d+ tests? for test/(\S+)\.t\.sol:(\S+)", line)
        if m:
            cur = m.group(1)
            blocks.setdefault(cur, {"lines": []})
            continue
        if cur is not None:
            blocks[cur]["lines"].append(line)
    for name in tests:
        b = blocks.get(name)
        if b is None:
            out[name] = {"passed": False, "outcomes": [], "log": text[-1500:]}
            continue
        body = "\n".join(b["lines"])
        passed = bool(re.search(r"\[PASS\] test_witness\(\)", body))
        outs = []
        for m in re.finditer(r"HOLON (\d+) (ok|rev): (0x[0-9a-fA-F]*)", body):
            if m.group(2) == "ok":
                outs.append("ok")
            else:
                outs.append("rev " + revert_key(bytes.fromhex(m.group(3)[2:])))
        out[name] = {"passed": passed, "outcomes": outs}
    return out


def revert_key(ret: bytes) -> str:
    if ret[:4] == bytes.fromhex(FG.PANIC_SELECTOR) and len(ret) == 36:
        return f"panic:0x{int.from_bytes(ret[4:], 'big'):02x}"
    if ret[:4] == bytes.fromhex(FG.ERROR_SELECTOR) and len(ret) >= 68:
        n = int.from_bytes(ret[36:68], "big")
        return ret[68:68 + n].decode("utf-8", "replace")
    return "0x" + ret.hex()


# ------------------------------------------------------------------------------------------------ attempts
def bmc_attempt(r: dict | None, H: int, rlimit: int, reason: str | None = None, accepted: int = 0,
                discarded: list | None = None) -> dict:
    if r is None:
        return {"engine": "bmc", "bound": {"H": H}, "budget": {"rlimit": rlimit}, "result": "not_run", "candidates": 0,
                "accepted": 0, "discarded": [], "reason": reason, "length": None, "largest_k": 0}
    disc = discarded or []
    cands = accepted + len(disc)
    return {"engine": "bmc", "bound": {"H": H}, "budget": {"rlimit": rlimit}, "result": r["verdict"],
            "candidates": cands, "accepted": accepted, "discarded": disc, "reason": reason or r["reason"],
            "length": r["length"], "largest_k": r["largest_k"]}


# ------------------------------------------------------------------------------------------------ targets of a law
def law_targets(e: dict) -> list[tuple[str, dict]]:
    """(entry point, BMC target) of a law's derivation entry: a realize law's hit at each entry point (its realization
    check fails at the last step); a width law's narrowing store at its span (a stored value of more than its width)."""
    out = []
    if e.get("subform") == "realize":
        for h in e.get("hits") or []:
            out.append((h["action"], {"kind": "check", "action": h["action"], "check": h["at"]}))
    elif e.get("subform") == "width":
        b = e["basis"]
        out.append((None, {"kind": "store", "span": b["span"], "width": int(b["width"])}))
    return out


# ------------------------------------------------------------------------------------------------ test milestones
def test_milestone(a, root: Path) -> int:
    from .sorts import run3 as R3
    from .sorts import search3 as S3
    sc = load(root / a.sidecar)
    base = load(root / sc["base"])
    solver = base["solver"]
    why = SR.pin_check(solver)
    if why:
        print(f"holon refute: the pinned solver is not installed as pinned: {why}")
        return 2
    only = [s.strip() for s in (a.only or ",".join(STAGES)).split(",") if s.strip()]
    res = Path(a.results).resolve()
    gen = Path(a.gen_dir).resolve() if a.gen_dir else root / "gen" / a.milestone
    laws_named = [x.strip() for x in (a.laws or "").split(",") if x.strip()]
    dv = load(root / "laws" / a.milestone / "DERIVATION.json")
    entries = {e["law_id"]: e for e in dv["laws"]}
    recs = {p.stem: load(p) for p in sorted(res.glob("L*.json"))}
    todo = sorted(lid for lid, r in recs.items() if (r.get("status") != "PROVED" or lid in laws_named)
                  and lid in entries)
    doc_rel = sc["documents"][0]
    doc = load(root / doc_rel)
    m = BMC.Machine(doc, base["smt"]["byte_length_max"])
    bm = sc["bmc"]
    H = int(bm.get("H", base["bmc"]["H"]))
    rlimit = int(base["solver"]["rlimit_per_query"])
    principals = sorted(bm["principals"].items())
    prob = BMC.Problem(m, {}, [(n, int(x, 16)) for n, x in principals if isinstance(x, str)],
                       int(bm["clock_origin"]), H, rlimit, int(base["blob_count_max"]), answers=bm.get("answers") or {})
    rp = res / "refute.json"
    state = load(rp) if rp.is_file() else {"laws": {}}
    ctx = R3.Ctx(a.milestone, root, sc["model_sidecar"], gen, res, log=lambda *x: None)
    try:
        if "bmc" in only:
            for lid in todo:
                e = entries[lid]
                atts = []
                found = {}
                for entry, tgt in law_targets(e):
                    r = BMC.search(prob, tgt, solver, gen / "refute" / "smt" / "bmc", f"{lid}.{entry or 'law'}")
                    acc, disc = 0, []
                    if r["verdict"] == "path":
                        if recs[lid].get("status") == "PROVED":
                            disc.append({"witness": {"steps": r["path"]}, "checker": {
                                "exit_code": None, "marker": "a PROVED record is never rewritten (control query)"}})
                        else:
                            found[entry] = r["path"]
                    atts.append(dict(bmc_attempt(r, H, rlimit, accepted=0, discarded=disc), entry=entry))
                state["laws"][lid] = {"attempts": atts}
                if found and recs[lid].get("status") != "PROVED":
                    rec = refute_record(ctx, lid, e, recs[lid], found, atts)
                    if rec is not None:
                        (res / f"{lid}.json").write_text(dumps(rec), encoding="utf-8")
                        recs[lid] = rec
                        for at in atts:
                            w = rec["witnesses"].get(at["entry"]) or {}
                            if at["result"] == "path":
                                if w.get("status") == "REFUTED":
                                    at["accepted"], at["candidates"] = 1, 1
                                else:
                                    at["discarded"] = [{"witness": w.get("witness"), "checker": w.get("checker") or
                                                        {"exit_code": None, "marker": "not_run"}}]
                                    at["candidates"] = 1
            rp.write_text(dumps(state), encoding="utf-8")
        if "emit" in only or "replay" in only:
            tests = {}
            for lid, r in sorted(recs.items()):
                if r.get("status") != "REFUTED":
                    continue
                for entry, w in sorted((r.get("witnesses") or {}).items()):
                    if w.get("status") != "REFUTED":
                        continue
                    steps = w["witness"]["steps"]
                    exp = w.get("expected") or model_expected(ctx, doc_rel, steps)
                    name = FG.sanitize(f"{lid}__{entry}")
                    deploy = {"kind": "new", "import": f"../src/{Path(sc['harness']['source']).name}",
                              "contract": doc["contract"]}
                    tests[name] = (lid, entry, FG.test_text(name, steps, exp, deploy, note=f"{lid} at {entry}"), exp)
            tdir = gen / "tests"
            if "emit" in only:
                shutil.rmtree(tdir, ignore_errors=True)
                tdir.mkdir(parents=True, exist_ok=True)
                for name, (_l, _e, text, _x) in sorted(tests.items()):
                    (tdir / f"{name}.t.sol").write_text(text, encoding="utf-8")
            if "replay" in only and tests:
                tc = toolchain(root)
                work = Path(tempfile.mkdtemp(prefix="holon-refute-"))
                try:
                    proj = sol_project(work, root, tc, src_dir=(root / sc["harness"]["source"]).parent,
                                       files=sc["harness"]["files"])
                    out = run_tests(proj, tc, {n: t for n, (_l, _e, t, _x) in tests.items()})
                finally:
                    shutil.rmtree(work, ignore_errors=True)
                rep = {"records": {}}
                for name, (lid, entry, _t, exp) in sorted(tests.items()):
                    o = out[name]
                    st = "passed" if o["passed"] and o["outcomes"] == exp else "failed"
                    rep["records"].setdefault(lid, {"entries": {}})["entries"][entry] = {
                        "status": st, "outcomes": o["outcomes"], "expected": exp,
                        "test": rel(gen / "tests" / f"{name}.t.sol", root)}
                    r = recs[lid]
                    r["witnesses"][entry]["replay"] = {"status": st, "detail": " / ".join(o["outcomes"]),
                                                       "panic_site": None}
                for lid, x in rep["records"].items():
                    r = recs[lid]
                    sts = [y["status"] for y in x["entries"].values()]
                    r["replay"] = {"status": "passed" if sts and all(s == "passed" for s in sts) else "failed",
                                   "detail": "; ".join(f"{k}: {' / '.join(v['outcomes'])}"
                                                       for k, v in sorted(x["entries"].items()))}
                    (res / f"{lid}.json").write_text(dumps(r), encoding="utf-8")
                (res / "replay.json").write_text(dumps(rep), encoding="utf-8")
    finally:
        ctx.close()
    return 0


def model_expected(ctx, doc_rel: str, steps: list) -> list[str]:
    from .sorts import run3 as R3
    ev, init, model_f, mm, doc = ctx.model(doc_rel)
    outs, _c = R3.model_outcomes(model_f(), [R3.step_of_json(s) for s in steps])
    return outs


def refute_record(ctx, lid: str, e: dict, old: dict, found: dict, atts: list) -> dict | None:
    """The record of a law BMC found witnesses for, as I30's pipeline writes it (holon.sorts.run3.Decider): a counter-
    law per entry point on the law's typed model, checked by Bend and BendTT; REFUTED when one is accepted."""
    from .sorts import run3 as R3
    from .sorts import search3 as S3
    import shutil as _sh
    d = R3.Decider(ctx)
    law_ir = json.loads((ctx.laws_dir / f"{lid}.json").read_text())
    doc_rel = e["facts"]
    ev, init, model_f, mm, doc = ctx.model(doc_rel)
    hashes = ev.hashes()
    law = dict(e)
    lp = d.write_law(law_ir, doc_rel, True, hashes)
    pdir = d.paths(lid)["proofs"]
    _sh.rmtree(pdir, ignore_errors=True)
    witnesses = {}
    primary = None
    fns = R3.fn_names(doc)
    for entry, path in sorted(found.items()):
        steps = [R3.step_of_json(s) for s in path]
        p, checker, verdict, tables = d.emit_counter(law, doc_rel, steps, model_f, ev, hashes, pdir / f"entry_{entry}",
                                                     f"the BMC witness of entry point {entry} (I40), every premise by "
                                                     "computation")
        wj = {"steps": [R3.step_json(doc, st, fns) for st in steps],
              "hashes": {h: [["0x" + k[2:], "0x%064x" % v] for k, v in sorted(tables[h].items())] for h in hashes}}
        ok = checker["marker"] == "ALL PROOFS CHECK" and verdict == "checked"
        witnesses[entry] = {"status": "REFUTED" if ok else "UNKNOWN", "witness": wj,
                            "laws": R3.rel(lp, ctx.root) if ok else None, "proof": R3.rel(p, ctx.root) if ok else None,
                            "checker": checker, "verdict": verdict, "stage": None, "search_stage": "BMC",
                            "bound": f"BMC: H = {len(path)} steps", "replay": {"status": "not_run", "detail": "",
                                                                               "panic_site": None}}
        if ok and primary is None:
            primary = entry
        if not ok:
            _sh.rmtree(pdir / f"entry_{entry}", ignore_errors=True)
    for k, w in (old.get("witnesses") or {}).items():
        witnesses.setdefault(k, w)
    attempts = list(old.get("attempts") or []) + [dict(x) for x in atts]
    if primary is None:
        lp = d.write_law(law_ir, doc_rel, False, hashes)
        return None
    steps = [R3.step_of_json(s) for s in found[primary]]
    p, checker, verdict, _t = d.emit_counter(law, doc_rel, steps, model_f, ev, hashes, pdir,
                                             f"the primary witness (entry point {primary}, BMC), every premise by "
                                             "computation")
    prim = {"proof": R3.rel(p, ctx.root), "checker": checker, "verdict": verdict}
    rec = d.record(law_ir, e, "REFUTED", witnesses, attempts, lp, doc_rel, primary, prim, None)
    rec["replay"] = {"status": "not_run", "detail": ""}
    return rec


# ------------------------------------------------------------------------------------------------ CLI
def main(argv: list) -> int:
    ap = argparse.ArgumentParser(prog="holon refute")
    ap.add_argument("--milestone", required=True)
    ap.add_argument("--root")
    ap.add_argument("--sidecar")
    ap.add_argument("--only")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--results")
    ap.add_argument("--gen-dir")
    ap.add_argument("--laws")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve() if a.root else ROOT
    try:
        if a.milestone.startswith("T"):
            if not a.sidecar or not a.results:
                print("holon refute: a test milestone needs --sidecar and --results")
                return 1
            return test_milestone(a, root)
        from . import refute_m3
        return refute_m3.main(a, root)
    except (OSError, ValueError, KeyError) as x:
        print(f"holon refute: {type(x).__name__}: {x}")
        return 1
