"""`holon replay`: run REFUTED witnesses on the real implementations (whitepaper §8.7, §9.6, M0_SPEC §8).

A model refutation is a hypothesis about the code. It becomes a finding only when the
real implementation does the same thing on the same input; a witness that does not
replay is a model defect.

    python -m holon replay --morph /path/to/morph-checkout [--forge forge] [--solc PATH] [--work DIR]

Steps:
  1. check the checkout is at the commit the facts were extracted from;
  2. Go: copy common/ + bindings/ into a scratch workspace, add replay/M0/go/holon_replay_test.go,
     `go test -run TestHolonReplay`;
  3. Solidity: copy contracts/ into a scratch Foundry project, add
     replay/M0/solidity/HolonReplay.t.sol (a harness inheriting the real Rollup),
     `forge test --match-contract HolonReplay`;
  4. write replay/M0/report.json (with the sha256 of each witness it ran);
  5. stamp `replay` into the result records whose witness hash matches the report.

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

ROOT = Path(__file__).resolve().parents[1]
HOLON_LINE = re.compile(r"HOLON (\S+) (passed|failed) (.*)")

# Solidity dependencies at the versions morph's package.json pins (git deps by commit).
NPM_DEPS = ["@openzeppelin/contracts@4.9.3", "@openzeppelin/contracts-upgradeable@4.9.3"]
GIT_DEPS = {
    "forge-std": ("https://github.com/foundry-rs/forge-std", "46264e9788017fc74f9f58b7efa0bc6e1df6d410"),
    "ds-test": ("https://github.com/dapphub/ds-test", "6da7dd8f7395f83e1fb6fa88a64ba9a030f85d4f"),
    "@rari-capital/solmate": ("https://github.com/transmissions11/solmate", "8f9b23f8838670afda0fd8983f2c41e8037ae6bc"),
}

# What each side is expected to show, and why a side is not applicable in M0.
PLAN = {
    "L_par_hdr_v2": {"go": "TestHolonReplay/L_par_hdr_v2",
                     "solidity": "needs a full commitBatch deployment (byte 0 = 2 is written on the commit path): M1"},
    "L_dom_hdr": {"go": "TestHolonReplay/L_dom_hdr", "solidity": "test_L_dom_hdr_witness_accepted"},
    "L_par_hdr_ssvh": {"go": "TestHolonReplay/L_par_hdr_ssvh",
                       "solidity": "needs a full commitBatch deployment (ssvh is written as zero on the commit path): M1"},
}


def witness_sha256(witness: dict | None) -> str | None:
    return None if witness is None else hashlib.sha256(ir.canonical_json(witness)).hexdigest()


def _run(cmd: list[str], cwd: Path, env: dict | None = None, timeout: int = 3600) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=cwd, env={**os.environ, **(env or {})}, capture_output=True, text=True,
                       timeout=timeout)
    return p.returncode, p.stdout + p.stderr


def _holon_lines(out: str) -> dict[str, tuple[str, str]]:
    return {m.group(1): (m.group(2), m.group(3).strip()) for m in HOLON_LINE.finditer(out)}


def check_checkout(morph: Path, commit: str) -> str:
    code, out = _run(["git", "rev-parse", "HEAD"], morph)
    sha = out.strip()
    if code != 0 or not sha.startswith(commit):
        raise SystemExit(f"{morph} is at {sha or '?'}, expected {commit}")
    return sha


def replay_go(morph: Path, work: Path, results: Path) -> tuple[dict, str]:
    ws = work / "go"
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    for d in ("bindings", "common"):
        shutil.copytree(morph / d, ws / d, symlinks=True)
    (ws / "go.work").write_text("go 1.24.0\n\nuse (\n\t./bindings\n\t./common\n)\n")
    shutil.copy(ROOT / "replay" / "M0" / "go" / "holon_replay_test.go", ws / "common" / "batch")
    shutil.copytree(results, ws / "holon_results")
    cmd = ["go", "test", "./batch", "-run", "TestHolonReplay", "-v", "-count=1"]
    code, out = _run(cmd, ws / "common", {"HOLON_RESULTS": str(ws / "holon_results")})
    return _holon_lines(out), f"(cd common && HOLON_RESULTS=… {' '.join(cmd)})  # exit {code}"


def _sol_deps(proj: Path) -> None:
    nm = proj / "node_modules"
    if not (nm / "@openzeppelin" / "contracts").exists():
        _run(["npm", "init", "-y"], proj)
        code, out = _run(["npm", "install", "--silent", "--no-audit", "--no-fund", *NPM_DEPS], proj)
        if code != 0:
            raise SystemExit(f"npm install failed: {out[-1000:]}")
    for name, (url, rev) in GIT_DEPS.items():
        d = nm / name
        if not d.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            _run(["git", "clone", "-q", url, str(d)], proj)
            _run(["git", "checkout", "-q", rev], d)


def replay_solidity(morph: Path, work: Path, results: Path, forge: str, solc: str | None) -> tuple[dict, str]:
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
    shutil.copy(ROOT / "replay" / "M0" / "solidity" / "HolonReplay.t.sol", proj / "test")
    shutil.rmtree(proj / "holon_results", ignore_errors=True)
    shutil.copytree(results, proj / "holon_results")  # forge may only read inside the project
    cmd = [forge, "test", "--match-contract", "HolonReplay", "-vv", "--offline"] + (["--use", solc] if solc else [])
    code, out = _run(cmd, proj, {"HOLON_RESULTS": "holon_results"})
    lines = _holon_lines(out)
    # forge reports per-test pass/fail; the harness logs a HOLON line on success
    for test in re.findall(r"\[FAIL[^\]]*\] (\w+)\(", out):
        lines.setdefault(test, ("failed", "forge: " + test + " failed"))
    for test in re.findall(r"\[PASS\] (\w+)\(", out):
        lines.setdefault(test, ("passed", "forge: " + test + " passed"))
    shown = " ".join("forge" if c == forge else "<solc 0.8.24>" if c == solc else c for c in cmd)
    return lines, f"HOLON_RESULTS=holon_results {shown}  # exit {code}"


def build_report(morph_sha: str, records: dict, go: tuple | None, sol: tuple | None) -> dict:
    laws, shas = {}, {}
    for lid, plan in PLAN.items():
        rec = records.get(lid)
        shas[lid] = witness_sha256(rec.get("witness") if rec else None)
        entry = {}
        for side, (lines, command) in (("go", go), ("solidity", sol)):
            key = plan[side]
            if (go if side == "go" else sol) is None:
                entry[side] = {"status": "not_run", "observed": "toolchain not provided", "command": ""}
            elif side == "solidity" and " " in key:  # a reason, not a test name
                entry[side] = {"status": "not_applicable", "observed": key, "command": ""}
            else:
                test_key = lid if side == "go" else key
                status, observed = (lines or {}).get(test_key, ("failed", f"no result for {test_key}"))
                entry[side] = {"status": status, "command": command, "observed": observed}
        laws[lid] = entry
    return {"morph_commit": morph_sha, "laws": laws, "witness_sha256": shas}


def replay_status(report: dict | None, lid: str, witness: dict | None) -> dict:
    """The record's replay field: derived from the report, only if the witness is the one replayed."""
    if not report or lid not in report.get("laws", {}):
        return {"status": "not_run", "detail": "no replay report entry"}
    e = report["laws"][lid]
    if report.get("witness_sha256", {}).get(lid) != witness_sha256(witness):
        return {"status": "not_run", "detail": "replay report is for a different witness"}
    sides = {s: e[s]["status"] for s in ("go", "solidity") if s in e}
    if "failed" in sides.values():
        status = "failed"
    elif "passed" in sides.values():
        status = "passed"
    elif sides and all(v == "not_applicable" for v in sides.values()):
        status = "not_applicable"
    else:
        status = "not_run"
    detail = "; ".join(f"{s}: {v}" for s, v in sorted(sides.items())) + f" @ morph {report['morph_commit'][:12]}"
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
    morph = Path(args.morph).resolve()
    facts = F.load(ROOT / "facts" / "morph_header.json")
    sha = check_checkout(morph, facts["target"]["commit"])
    results = ROOT / "results" / args.milestone
    work = Path(args.work or ROOT / "build" / "replay").resolve()
    records = {p.stem: json.loads(p.read_text()) for p in results.glob("L_*.json")}
    go = replay_go(morph, work, results) if shutil.which("go") else None
    forge = args.forge or shutil.which("forge")
    sol = replay_solidity(morph, work, results, forge, args.solc) if forge else None
    report = build_report(sha, records, go, sol)
    out = ROOT / "replay" / args.milestone / "report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    changed = stamp_records(args.milestone, results, report)
    for lid, e in report["laws"].items():
        print(f"{lid:16s} go={e['go']['status']:14s} solidity={e['solidity']['status']}")
    print(f"wrote {out.relative_to(ROOT)}; updated records: {changed or 'none'}")
    bad = [lid for lid, e in report["laws"].items() if "failed" in (e["go"]["status"], e["solidity"]["status"])]
    if bad:
        print(f"MODEL DEFECT: witnesses that do not replay: {bad}")
    return 1 if bad else 0
