"""`holon checker-upgrade`: try a candidate checker in a scratch copy and report what changes (§8.8, I3).

  python -m holon checker-upgrade --to FINGERPRINT [--bend-cmd CMD] [--milestones M0,M1] [--out PATH]

The repository is copied (without .git, caches, node_modules, tmp and build) into a temporary
directory. In the copy only, config/holon.json gets bend.pinned_fingerprint = FINGERPRINT (and
bend.cmd = CMD when --bend-cmd is given). Then, for each milestone, `holon run` regenerates every
record and `holon gate` re-checks everything under the candidate, in the copy. Every result record
is compared with the one in the tree (`seconds` stripped, artifact paths made relative to their
gen dir, canonical JSON), and each law whose record differs is listed with the differing top-level
keys.

The candidate must really be the checker named by --to: if it is not, GENV fails in the copy and
the report says so. Nothing in the real tree is changed except the report written to --out
(default results/checker_upgrade/<from>-<to>.json, 12-hex prefixes). Adopting the candidate is a
human config change (bend.pinned_fingerprint, and bend.cmd if the command changes) made after
reading this report; this tool never adopts it. Exit 0 iff every gate passed in the copy.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import bend, ir

ROOT = Path(__file__).resolve().parents[1]
FP_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COPY_IGNORE = (".git", "__pycache__", "*.pyc", "node_modules", "tmp", "build", ".venv", "venv")
PATH_KEYS = ("laws", "proof", "model")


def _fp(s: str) -> str:
    if not FP_RE.match(s):
        raise argparse.ArgumentTypeError(f"not a checker fingerprint (sha256:<64 hex>): {s!r}")
    return s


def _hex(fp: str | None) -> str:
    return (fp or "unpinned").split(":", 1)[-1][:12]


def _strip_seconds(x):
    if isinstance(x, dict):
        return {k: _strip_seconds(v) for k, v in x.items() if k != "seconds"}
    if isinstance(x, list):
        return [_strip_seconds(v) for v in x]
    return x


def norm_records(root: Path, m: str) -> dict[str, dict]:
    """root/results/<m>/L_*.json with `seconds` removed and artifact paths relative to root/gen/<m>."""
    gen = (root / "gen" / m).resolve()

    def rel(p):
        if p is None:
            return None
        q = Path(p)
        q = q if q.is_absolute() else root / q
        try:
            return q.resolve().relative_to(gen).as_posix()
        except ValueError:
            return f"<outside gen>/{q.name}"
    out = {}
    for f in sorted((root / "results" / m).glob("L_*.json")):
        r = _strip_seconds(json.loads(f.read_text()))
        if isinstance(r.get("artifacts"), dict):
            r["artifacts"] = {k: (rel(v) if k in PATH_KEYS else v) for k, v in r["artifacts"].items()}
        if isinstance(r.get("non_vacuity"), dict) and r["non_vacuity"].get("law"):
            r["non_vacuity"] = {**r["non_vacuity"], "law": rel(r["non_vacuity"]["law"])}
        out[f.stem] = r
    return out


def record_diffs(committed: dict[str, dict], candidate: dict[str, dict]) -> list[dict]:
    """One entry per law whose normalised record differs, with the differing top-level keys."""
    out = []
    for lid in sorted(set(committed) | set(candidate)):
        a, b = committed.get(lid), candidate.get(lid)
        if a is None or b is None:
            out.append({"law_id": lid, "keys": ["<record missing in the " + ("tree" if a is None else "candidate run")
                                                + ">"],
                        "committed_status": (a or {}).get("status"), "candidate_status": (b or {}).get("status")})
            continue
        if ir.canonical_json(a) == ir.canonical_json(b):
            continue
        keys = sorted(k for k in set(a) | set(b)
                      if (k in a) != (k in b) or ir.canonical_json(a.get(k)) != ir.canonical_json(b.get(k)))
        out.append({"law_id": lid, "keys": keys, "committed_status": a.get("status"),
                    "candidate_status": b.get("status")})
    return out


def _tail(p: subprocess.CompletedProcess, n: int = 1500) -> str:
    return (p.stdout + p.stderr)[-n:]


def try_milestone(copy: Path, m: str, env: dict, root: Path) -> dict:
    py = [sys.executable, "-m", "holon"]
    run = subprocess.run(py + ["run", "--milestone", m], cwd=copy, env=env, capture_output=True, text=True,
                         timeout=7200)
    report = copy / f"gate_{m}.json"
    gate = subprocess.run(py + ["gate", "--milestone", m, "--root", str(copy), "--report", str(report)], cwd=copy,
                          env=env, capture_output=True, text=True, timeout=7200)
    rep = json.loads(report.read_text()) if report.exists() else None
    passed = gate.returncode == 0 and isinstance(rep, dict) and rep.get("passed") is True
    statuses = {lid: r.get("status") for lid, r in sorted(norm_records(copy, m).items())}
    out = {"gate_passed": passed, "run_exit_code": run.returncode, "gate_exit_code": gate.returncode,
           "record_diffs": record_diffs(norm_records(root, m), norm_records(copy, m)), "statuses": statuses}
    if run.returncode != 0:
        out["run_output_tail"] = _tail(run)
    if isinstance(rep, dict):
        out["gate_failures"] = {g: c.get("detail") for g, c in sorted(rep.get("checks", {}).items())
                                if not c.get("passed")}
    else:
        out["gate_output_tail"] = _tail(gate)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="holon checker-upgrade",
                                 description="run holon and the gate under a candidate checker in a scratch copy "
                                             "and report every record diff (adoption is a human config change)")
    ap.add_argument("--to", required=True, type=_fp, help="the candidate checker's fingerprint (sha256:...)")
    ap.add_argument("--bend-cmd", help="the candidate checker command (default: the configured one)")
    ap.add_argument("--milestones", default="M0,M1")
    ap.add_argument("--out", help="report path (default results/checker_upgrade/<from>-<to>.json)")
    a = ap.parse_args(argv)
    root = ROOT
    milestones = [m.strip() for m in a.milestones.split(",") if m.strip()]
    if not milestones:
        ap.error("--milestones is empty")
    src_cfg = bend.config(root)
    frm = src_cfg["bend"].get("pinned_fingerprint")
    out = Path(a.out) if a.out else root / "results" / "checker_upgrade" / f"{_hex(frm)}-{_hex(a.to)}.json"

    tmp = Path(tempfile.mkdtemp(prefix="holon-checker-upgrade-"))
    try:
        copy = tmp / "repo"
        shutil.copytree(root, copy, ignore=shutil.ignore_patterns(*COPY_IGNORE))
        cfg_path = copy / "config" / "holon.json"
        cfg = json.loads(cfg_path.read_text()) if cfg_path.exists() else src_cfg
        cfg["bend"]["pinned_fingerprint"] = a.to
        env = dict(os.environ)
        if a.bend_cmd:
            cfg["bend"]["cmd"] = shlex.split(a.bend_cmd)
            env.pop("HOLON_BEND_CMD", None)  # the copy's config names the candidate; no override wins over it
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")
        env["PYTHONPATH"] = str(copy) + os.pathsep + env.get("PYTHONPATH", "")
        env["HOLON_BUILD_DIR"] = str(tmp / "build")  # nothing compiled is reused from the caller's cache
        results = {}
        for m in milestones:
            print(f"checker-upgrade: {m}: holon run + gate under {a.to} ...", flush=True)
            results[m] = try_milestone(copy, m, env, root)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    rep = {"from": frm, "to": a.to, "bend_cmd": shlex.split(a.bend_cmd) if a.bend_cmd else None,
           "milestones": results,
           "note": "dry run in a scratch copy; adopting the candidate is a human change to config/holon.json "
                   "(bend.pinned_fingerprint, and bend.cmd if the command changes)"}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n")
    for m, r in results.items():
        counts: dict[str, int] = {}
        for st in r["statuses"].values():
            counts[st] = counts.get(st, 0) + 1
        print(f"{m}: gate {'PASSED' if r['gate_passed'] else 'FAILED'}, {len(r['record_diffs'])} record diffs, "
              + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())))
        for d in r["record_diffs"]:
            print(f"  {d['law_id']}: {', '.join(d['keys'])}")
        for g, detail in r.get("gate_failures", {}).items():
            print(f"  {g} FAIL: {str(detail)[:300]}")
    ok = all(r["gate_passed"] for r in results.values())
    print(f"checker-upgrade {_hex(frm)} -> {_hex(a.to)}: {'all gates passed' if ok else 'GATE FAILED'}; "
          f"report {out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
