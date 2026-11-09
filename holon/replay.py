"""`holon replay`: run REFUTED witnesses on the real implementations (whitepaper §8.7, §9.6, M0_SPEC §8).

A model refutation is a hypothesis about the code. It becomes a finding only when the
real implementation does the same thing on the same input; a witness that does not
replay is a model defect.

    python -m holon replay --morph /path/to/morph-checkout [--forge forge] [--solc PATH] [--work DIR]

Steps:
  1. check the checkout is at the commit the facts were extracted from, and the toolchain
     (forge, solc, the Solidity dependencies) against the sha256 pins in config/holon.json replay;
  2. Go: copy common/ + bindings/ into a scratch workspace, add replay/M0/go/holon_replay_test.go,
     `go test -run TestHolonReplay`;
  3. Solidity, two ways, chosen per law from its claim:
     - a claim that calls the commit-path encoder enc_sol runs on the commit path: the witness's
       pinned version becomes a one-step trace from s0 through the M1 Foundry harness, which deploys
       the real Rollup (holon.mreplay.m0_commit_sides);
     - any other claim runs through replay/M0/solidity/HolonReplay.t.sol, a harness inheriting the
       real Rollup to reach an internal function;
  4. write replay/M0/report.json (with the sha256 of each witness it ran, and the toolchain);
  5. stamp `replay` into the result records whose witness hash matches the report.

Every side records how it ran (`provenance`, whitepaper §10.9) and whether the real code showed its
part of the obstruction (`obstruction_observed`, set from the real code's output). holon.filter
turns the sides into the record's provisional filter_bin.

`holon run` re-applies the report on every run (holon.pipeline), so the records stay
deterministic functions of (facts, laws, report).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import facts as F
from . import ir
from .evidence import expected_provenance

ROOT = Path(__file__).resolve().parents[1]
HOLON_LINE = re.compile(r"HOLON (\S+) (passed|failed) (.*)")
DEFAULT_SOL_DEPS = Path.home() / ".holon" / "tools" / "sol_deps"
DEFAULT_MORPH = "/root/work/morph"

# Solidity dependencies at the versions morph's package.json pins (git deps by commit).
NPM_DEPS = ["@openzeppelin/contracts@4.9.3", "@openzeppelin/contracts-upgradeable@4.9.3"]
GIT_DEPS = {
    "forge-std": ("https://github.com/foundry-rs/forge-std", "46264e9788017fc74f9f58b7efa0bc6e1df6d410"),
    "ds-test": ("https://github.com/dapphub/ds-test", "6da7dd8f7395f83e1fb6fa88a64ba9a030f85d4f"),
    "@rari-capital/solmate": ("https://github.com/transmissions11/solmate", "8f9b23f8838670afda0fd8983f2c41e8037ae6bc"),
}

# The Go test that replays each M0 witness. The Solidity side is derived from the law's claim
# (solidity_kind): the commit path for enc_sol claims, the internal harness test otherwise.
PLAN = {
    "L_par_hdr_v2": {"go": "TestHolonReplay/L_par_hdr_v2"},
    "L_dom_hdr": {"go": "TestHolonReplay/L_dom_hdr", "solidity": "test_L_dom_hdr_witness_accepted"},
    "L_par_hdr_ssvh": {"go": "TestHolonReplay/L_par_hdr_ssvh"},
}
COMMIT_PATH = "commit_path"


def solidity_kind(law: dict) -> str:
    """COMMIT_PATH when the claim compares the commit-path encoder enc_sol with a Go reading;
    otherwise the name of the internal-harness test in HolonReplay.t.sol."""
    calls = [x.get("call") for x in law["statement"]["claim"]["eq"]]
    if "enc_sol" in calls:
        return COMMIT_PATH
    return PLAN[law["law_id"]]["solidity"]


def witness_sha256(witness: dict | None) -> str | None:
    return None if witness is None else hashlib.sha256(ir.canonical_json(witness)).hexdigest()


def _run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 3600) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def _holon_lines(out: str) -> dict[str, tuple[str, str]]:
    return {m.group(1): (m.group(2), m.group(3).strip()) for m in HOLON_LINE.finditer(out)}


REPLAYED_TREES = ("contracts", "common", "bindings", "node")


def check_checkout(morph: Path, commit: str) -> str:
    """The checkout must be at exactly the facts' full commit, with no uncommitted change in the trees
    the replays copy: the report attests that commit's code ran."""
    code, out = _run(["git", "rev-parse", "HEAD"], morph)
    sha = out.strip()
    full = commit
    if len(commit) < 40:  # the frozen M0 facts record a 7-character prefix: resolve it in the checkout
        c2, o2 = _run(["git", "rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}"], morph)
        full = o2.strip() if c2 == 0 else ""
    if code != 0 or len(full) != 40 or sha != full:
        raise SystemExit(f"{morph} is at {sha or '?'}, expected the commit {commit} ({full or 'unresolved'})")
    # the replays copy these trees whole: untracked and ignored files would be compiled too
    code, out = _run(["git", "status", "--porcelain", "--untracked-files=all", "--ignored=matching", "--",
                      *REPLAYED_TREES], morph, {"GIT_OPTIONAL_LOCKS": "0"})
    if code != 0 or out.strip():
        raise SystemExit(f"{morph} has uncommitted changes in the replayed trees: {out.strip()[:500]}")
    return sha


def replay_go(morph: Path, work: Path, results: Path, harness: Path | None = None,
              test: str = "TestHolonReplay") -> tuple[dict, str]:
    """The Go side: harness (default M0's replay/M0/go/holon_replay_test.go) beside the real common/batch code, its
    test run on the witnesses in results."""
    ws = work / "go"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    for d in ("bindings", "common"):
        shutil.copytree(morph / d, ws / d, symlinks=True)
    (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
    shutil.copy(harness or ROOT / "replay" / "M0" / "go" / "holon_replay_test.go", ws / "common" / "batch")
    shutil.copytree(results, ws / "holon_results")
    cmd = ["go", "test", "./batch", "-run", test, "-v", "-count=1"]
    code, out = _run(cmd, ws / "common", {"HOLON_RESULTS": str(ws / "holon_results")})
    return _holon_lines(out), f"(cd common && HOLON_RESULTS=… {' '.join(cmd)})  # exit {code}"


def replay_config(root: Path | None = None) -> dict:
    p = Path(root or ROOT) / "config" / "holon.json"
    return dict(json.loads(p.read_text()).get("replay") or {}) if p.exists() else {}


def file_sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree_sha256(d: Path) -> str:
    """sha256 over (relative path, file sha256) of every file under d, in sorted order; .git
    directories and npm's .package-lock.json bookkeeping are skipped."""
    h = hashlib.sha256()
    files = sorted(f for f in Path(d).rglob("*")
                   if f.is_file() and ".git" not in f.relative_to(d).parts and f.name != ".package-lock.json")
    for f in files:
        h.update(f"{f.relative_to(d).as_posix()}\0{file_sha256(f)}\n".encode())
    return h.hexdigest()


def ensure_sol_deps(deps: Path) -> Path:
    """The Solidity dependencies at the versions morph's package.json pins, installed once under
    `deps` (outside the repo: BUILD_PLAN §0.2 item 6). Returns deps/node_modules."""
    nm = deps / "node_modules"
    if not (nm / "@openzeppelin" / "contracts").exists():
        deps.mkdir(parents=True, exist_ok=True)
        _run(["npm", "init", "-y"], deps)
        code, out = _run(["npm", "install", "--silent", "--no-audit", "--no-fund", *NPM_DEPS], deps)
        if code != 0:
            raise SystemExit(f"npm install failed: {out[-1000:]}")
    for name, (url, rev) in GIT_DEPS.items():
        d = nm / name
        if not d.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            _run(["git", "clone", "-q", url, str(d)], deps)
            _run(["git", "checkout", "-q", rev], d)
    return nm


def _sol_deps(proj: Path, nm_src: Path | None = None) -> None:
    """Give the scratch Foundry project the pinned dependency tree (a copy, so forge never reads
    outside the project)."""
    nm_src = nm_src or ensure_sol_deps(Path(replay_config().get("sol_deps") or DEFAULT_SOL_DEPS))
    nm = proj / "node_modules"
    if nm.exists() and tree_sha256(nm) == tree_sha256(nm_src):
        return
    shutil.rmtree(nm, ignore_errors=True)
    shutil.copytree(nm_src, nm, symlinks=False, ignore=shutil.ignore_patterns(".git"))


PIN_KEYS = ("forge_sha256", "solc_sha256", "sol_deps_sha256")
GO_PIN = "go_version"  # `go version` output: Go sides (and Go's append growth) depend on it


def go_version() -> str:
    return subprocess.run(["go", "version"], capture_output=True, text=True).stdout.strip()


def toolchain(args, root: Path | None = None) -> dict:
    """Resolve forge, solc and the Solidity dependencies, and check them against config/holon.json
    replay.*_sha256. A missing or different pin refuses to run, unless --write-pins, which records
    the current values (a human should review that config change)."""
    root = Path(root or ROOT)
    cfg = replay_config(root)
    forge = getattr(args, "forge", None) or cfg.get("forge") or shutil.which("forge")
    solc = getattr(args, "solc", None) or cfg.get("solc")
    if not forge or not Path(forge).exists():
        raise SystemExit(f"forge not found ({forge!r}); set config replay.forge or pass --forge")
    if not solc or not Path(solc).exists():
        raise SystemExit(f"solc not found ({solc!r}); set config replay.solc or pass --solc")
    deps = Path(cfg.get("sol_deps") or DEFAULT_SOL_DEPS)
    nm = ensure_sol_deps(deps)
    got = {"forge_sha256": file_sha256(forge), "solc_sha256": file_sha256(solc), "sol_deps_sha256": tree_sha256(nm),
           GO_PIN: go_version()}
    if getattr(args, "write_pins", False):
        p = root / "config" / "holon.json"
        doc = json.loads(p.read_text())
        doc["replay"] = {**doc.get("replay", {}), "forge": str(forge), "solc": str(solc), "sol_deps": str(deps),
                         "morph": str(getattr(args, "morph", None) or cfg.get("morph") or DEFAULT_MORPH), **got}
        p.write_text(json.dumps(doc, indent=2) + "\n")
        print(f"wrote replay pins to {p}: {got}")
    else:
        for k in (*PIN_KEYS, GO_PIN):
            if cfg.get(k) != got[k]:
                raise SystemExit(f"config/holon.json replay.{k} is {cfg.get(k)!r} but the toolchain gives {got[k]}; "
                                 "refusing to replay with an unpinned toolchain (--write-pins records new pins)")
    return {"forge": str(forge), "solc": str(solc), "sol_deps": nm, **got}


def morph_path(args, root: Path | None = None) -> Path:
    m = getattr(args, "morph", None) or replay_config(root).get("morph") or DEFAULT_MORPH
    return Path(m).resolve()


def replay_solidity(morph: Path, work: Path, results: Path, forge: str, solc: str | None, harness: Path | None = None,
                    contract: str = "HolonReplay") -> tuple[dict, str]:
    """The Solidity side: harness (default M0's replay/M0/solidity/HolonReplay.t.sol) in a scratch copy of the real
    contracts, its contract's tests run on the witnesses in results."""
    proj = work / "solidity"
    proj.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(proj / "contracts", ignore_errors=True)
    shutil.copytree(morph / "contracts" / "contracts", proj / "contracts")
    # mocks and the repo's own tests pull extra dependencies the harness does not need
    for d in ("mock", "test"):
        shutil.rmtree(proj / "contracts" / d, ignore_errors=True)
    for f in ("foundry.toml", "remappings.txt"):
        shutil.copy(morph / "contracts" / f, proj / f)
    _sol_deps(proj)
    (proj / "test").mkdir(exist_ok=True)
    shutil.copy(harness or ROOT / "replay" / "M0" / "solidity" / "HolonReplay.t.sol", proj / "test")
    shutil.rmtree(proj / "holon_results", ignore_errors=True)
    shutil.copytree(results, proj / "holon_results")  # forge may only read inside the project
    cmd = [forge, "test", "--match-contract", contract, "-vv", "--offline"] + (["--use", solc] if solc else [])
    code, out = _run(cmd, proj, {"HOLON_RESULTS": "holon_results"})
    lines = _holon_lines(out)
    # forge reports per-test pass/fail; the harness logs a HOLON line on success
    for test in re.findall(r"\[FAIL[^\]]*\] (\w+)\(", out):
        lines.setdefault(test, ("failed", "forge: " + test + " failed"))
    for test in re.findall(r"\[PASS\] (\w+)\(", out):
        lines.setdefault(test, ("passed", "forge: " + test + " passed"))
    shown = " ".join("forge" if c == forge else "<solc 0.8.24>" if c == solc else c for c in cmd)
    return lines, f"HOLON_RESULTS=holon_results {shown}  # exit {code}"


def build_report(morph_sha: str, records: dict, laws: dict, go: tuple | None, sol: tuple | None,
                 commit: dict | None, tc: dict | None) -> dict:
    """replay/M0/report.json: laws[lid] maps each side name to a side object (and nothing else: the
    frozen tests/test_50_replay.py reads every value of an M0 entry as a side).

    Go sides and the internal-harness Solidity side pass exactly when the real code shows the
    model's half of the obstruction on the witness (the harness compares the real output with the
    witness), so for them obstruction_observed is that pass. Commit-path sides come from
    holon.mreplay.m0_commit_sides, which checks the committed header itself."""
    out, shas = {}, {}
    for lid, plan in PLAN.items():
        rec = records.get(lid)
        shas[lid] = witness_sha256(rec.get("witness") if rec else None)
        entry = {}
        lines, command = go if go is not None else (None, "")
        if go is None:
            entry["go"] = _side("not_run", "toolchain not provided", "", "library_api")
        else:
            st, obs = (lines or {}).get(lid, ("failed", f"no result for {plan['go']}"))
            entry["go"] = _side(st, obs, command, "library_api")
        kind = solidity_kind(laws[lid])
        if kind != COMMIT_PATH and expected_provenance(laws[lid], "solidity") != "internal_harness":
            raise ValueError(f"{lid}: the HolonReplay.t.sol harness reaches internal functions; the IR says "
                             f"{expected_provenance(laws[lid], 'solidity')}")
        if kind == COMMIT_PATH:
            entry["solidity"] = (commit or {}).get(lid) or _side("not_run", "commit path not run", "", "public_schedule")
        elif sol is None:
            entry["solidity"] = _side("not_run", "toolchain not provided", "", "internal_harness")
        else:
            lines, command = sol
            st, obs = (lines or {}).get(kind, ("failed", f"no result for {kind}"))
            entry["solidity"] = _side(st, obs, command, "internal_harness")
        out[lid] = entry
    rep = {"morph_commit": morph_sha, "laws": out, "witness_sha256": shas}
    if tc is not None:
        rep["toolchain"] = {k: tc[k] for k in (*PIN_KEYS, GO_PIN)}
    return rep


def _side(status: str, observed: str, command: str, provenance: str, observed_ok: bool | None = None) -> dict:
    ok = status == "passed" if observed_ok is None else (status == "passed" and observed_ok)
    return {"status": status, "observed": observed, "command": command, "provenance": provenance,
            "obstruction_observed": bool(ok)}


def replay_status(report: dict | None, lid: str, witness: dict | None) -> dict:
    """The record's replay field: derived from the report, only if the witness is the one replayed."""
    if not report or lid not in report.get("laws", {}):
        return {"status": "not_run", "detail": "no replay report entry"}
    e = report["laws"][lid]
    if report.get("witness_sha256", {}).get(lid) != witness_sha256(witness):
        return {"status": "not_run", "detail": "replay report is for a different witness"}
    if "status" in e:  # M1 trace replay: one verdict per law
        return {"status": e["status"], "detail": f"{e.get('observed', '')} @ morph {report['morph_commit'][:12]}"[:500]}
    sides = {s: e[s]["status"] for s in ("go", "solidity") if s in e}
    if "failed" in sides.values():
        status = "failed"
    elif "not_run" in sides.values():
        status = "not_run"
    elif "passed" in sides.values():
        status = "passed"
    elif sides and all(v == "not_applicable" for v in sides.values()):
        status = "not_applicable"
    else:
        status = "not_run"
    def shown(side: str, v: str) -> str:
        # a side not replayed yet must say so in the record too, not only in the report
        if v == "not_applicable" and str(e[side].get("observed", "")).startswith("model-only pending replay"):
            return "model-only pending replay"
        return v
    detail = "; ".join(f"{s}: {shown(s, v)}" for s, v in sorted(sides.items())) + f" @ morph {report['morph_commit'][:12]}"
    return {"status": status, "detail": detail}


def load_report(milestone: str, root: Path | None = None) -> dict | None:
    p = Path(root or ROOT) / "replay" / milestone / "report.json"
    return json.loads(p.read_text()) if p.exists() else None


def stamp_records(milestone: str, results: Path, report: dict) -> list[str]:
    changed = []
    for lid in report["laws"]:
        p = results / f"{lid}.json"
        if not p.exists():
            continue
        rec = json.loads(p.read_text())
        new = replay_status(report, lid, rec.get("witness")) if rec.get("status") == "REFUTED" else rec["replay"]
        if new != rec["replay"]:
            rec["replay"] = new
            p.write_text(json.dumps(rec, indent=2, sort_keys=True) + "\n")
            changed.append(lid)
    return changed


def main_replay(args) -> int:
    from . import ir as _ir
    if _ir.ir_version_of(args.milestone, ROOT) == "holon-ir/0.2":
        from .mreplay import main_replay_m1
        return main_replay_m1(args)
    if _ir.ir_version_of(args.milestone, ROOT) == "holon-ir/0.3":   # SORT-site witnesses per entry point (I15)
        from .mreplay import main_replay_m2
        return main_replay_m2(args)
    from .mreplay import m0_commit_sides
    morph = morph_path(args)
    facts = F.load(ROOT / "facts" / "morph_header.json")
    sha = check_checkout(morph, facts["target"]["commit"])
    tc = toolchain(args)
    results = ROOT / "results" / args.milestone
    work = Path(args.work or ROOT / "build" / "replay").resolve()
    records = {p.stem: json.loads(p.read_text()) for p in ir.record_files(results)}
    laws = {p.stem: json.loads(p.read_text()) for p in (ROOT / "laws" / args.milestone).glob(ir.LAW_GLOB)}
    go = replay_go(morph, work, results) if shutil.which("go") else None
    sol = replay_solidity(morph, work, results, tc["forge"], tc["solc"])
    commit = m0_commit_sides(morph, work / "commit", records, laws, facts, tc)
    report = build_report(sha, records, laws, go, sol, commit, tc)
    out = ROOT / "replay" / args.milestone / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    changed = stamp_records(args.milestone, results, report)
    for lid, e in report["laws"].items():
        print(f"{lid:16s} " + "  ".join(f"{s}={v['status']}/observed={v['obstruction_observed']}/{v['provenance']}"
                                        for s, v in sorted(e.items())))
    print(f"wrote {out.relative_to(ROOT)}; updated records: {changed or 'none'}")
    bad = [lid for lid, e in report["laws"].items() if any(v["status"] == "failed" for v in e.values())]
    unseen = [lid for lid, e in report["laws"].items()
              if lid not in bad and not all(v["obstruction_observed"] for v in e.values())]
    if bad:
        print(f"MODEL DEFECT: witnesses that do not replay: {bad}")
    if unseen:
        print(f"NOT REPRODUCED: the obstruction did not show on every side: {unseen}")
    return 1 if bad or unseen else 0


# ================================================================== I98: the M3 PAR laws' library-level replays
# A REFUTED M3 PAR law whose claim compares a Go library call with a Solidity internal function that no public schedule
# reaches (I40's BMC found no path) is replayed as the M0 laws are: replay/M3/par/'s harnesses (a Go test beside the real
# code, a Foundry harness inheriting the real Rollup) on the checkout at the commit of the documents the law was
# compiled from. The report replay/M3/par/report.json has the base format (laws: {law: {go, solidity}}, witness_sha256,
# morph_commit), which G6 binds (holon.sorts.gate3.Gate3.g6_other) and the records' replay fields are stamped from.
# The plan names each law's two tests, as M0's PLAN does.
PLAN_M3 = {
    "L_par_dom_BatchHeaderBytes_validate_ok_load_sol": {
        "go": "L_par_dom_BatchHeaderBytes_validate_ok_load_sol",
        "solidity": "test_L_par_dom_BatchHeaderBytes_validate_ok_load_sol"},
}
PAR_HARNESS = {"go": ("replay/M3/par/go/holon_par_test.go", "TestHolonPar"),
               "solidity": ("replay/M3/par/solidity/HolonPar.t.sol", "HolonPar")}


def par_commit(milestone: str, laws: dict, root: Path | None = None) -> str:
    """The one target commit of the documents the laws' facts were compiled from."""
    root = Path(root or ROOT)
    commits = set()
    for law in laws.values():
        doc = json.loads((root / law["facts"]).read_text())
        for d in doc.get("documents") or [law["facts"]]:
            t = json.loads((root / d).read_text()).get("target") or {}
            if t.get("commit"):
                commits.add(t["commit"])
    if len(commits) != 1:
        raise SystemExit(f"{milestone}'s PAR library laws name {len(commits)} target commits ({sorted(commits)}); "
                         "replaying them needs exactly one")
    return commits.pop()


def main_replay_par(args) -> int:
    """`holon replay-par --milestone M3` (I98): PLAN_M3's REFUTED records on the real code, into
    replay/<M>/par/report.json; then each record's replay field (replay_status) and witness_provenance from it."""
    from .filter import record_fields
    from .refute_m3 import write_record
    m = args.milestone
    results = ROOT / "results" / m
    laws = {lid: json.loads((ROOT / "laws" / m / f"{lid}.json").read_text()) for lid in sorted(PLAN_M3)
            if (ROOT / "laws" / m / f"{lid}.json").is_file()}
    records = {lid: json.loads((results / f"{lid}.json").read_text()) for lid in laws if (results / f"{lid}.json").is_file()}
    todo = sorted(lid for lid, r in records.items() if r.get("status") == "REFUTED")
    rp = ROOT / "replay" / m / "par" / "report.json"
    if not todo:
        print(f"holon replay-par: no REFUTED record of the plan in {m}")
        return 0
    morph = morph_path(args)
    sha = check_checkout(morph, par_commit(m, {lid: laws[lid] for lid in todo}))
    tc = toolchain(args)
    work = Path(getattr(args, "work", None) or ROOT / "build" / "replay-par").resolve()
    gh, gt = PAR_HARNESS["go"]
    sh, sc = PAR_HARNESS["solidity"]
    go = replay_go(morph, work, results, ROOT / gh, gt) if shutil.which("go") else None
    sol = replay_solidity(morph, work, results, tc["forge"], tc["solc"], ROOT / sh, sc)
    out, shas = {}, {}
    for lid in todo:
        plan = PLAN_M3[lid]
        shas[lid] = witness_sha256(records[lid].get("witness"))
        entry = {}
        if go is None:
            entry["go"] = _side("not_run", "toolchain not provided", "", "library_api")
        else:
            lines, command = go
            st, obs = (lines or {}).get(plan["go"], ("failed", f"no result for {gt}/{plan['go']}"))
            entry["go"] = _side(st, obs, command, "library_api")
        lines, command = sol
        st, obs = (lines or {}).get(plan["solidity"], ("failed", f"no result for {plan['solidity']}"))
        entry["solidity"] = _side(st, obs, command, "internal_harness")
        out[lid] = entry
    report = {"milestone": m, "morph_commit": sha, "go_version": tc[GO_PIN], "laws": out, "witness_sha256": shas,
              "toolchain": {k: tc[k] for k in (*PIN_KEYS, GO_PIN)}}
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    changed = []
    for lid in todo:
        p = results / f"{lid}.json"
        rec = json.loads(p.read_text())
        wp, _ = record_fields(report, lid, rec.get("witness"), witness_sha256)
        new = dict(rec, replay=replay_status(report, lid, rec.get("witness")), witness_provenance=wp)
        if new != rec:
            write_record(p, new)
            changed.append(lid)
    for lid, e in out.items():
        print(f"{lid}: " + "  ".join(f"{k}={v['status']}/observed={v['obstruction_observed']}/{v['provenance']}"
                                     for k, v in sorted(e.items())))
    print(f"holon replay-par: wrote {rp.relative_to(ROOT)}; updated records: {changed or 'none'}")
    return 1 if any(v["status"] != "passed" for e in out.values() for v in e.values()) else 0
