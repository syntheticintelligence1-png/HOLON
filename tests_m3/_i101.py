"""I101's instrument (tests_m3/test_audit_fixes_i101.py): the scratch copies of the M3 audit tree, F-M3-37's hollow
round, the one-at-a-time changes to round 9, F-M3-42's subset runs in a detached worktree, and the target-agnostic
scan's inputs. It imports nothing from holon/ or tools/: it runs `python -m holon` and git in subprocesses, and reuses
I100's target-name scan (tests_m3/_i100.py). Fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
M = "M3"
OUT = "docs/iterations/I101"
BASE = "a3666ec50b05269d0faa8c512d583f90a94f0a57"         # the lead after #164 (the M4 stack's landing)
RULE = f"spec/{M}/lib/audit_evidence.json"
PROBE_ROUND, PROBE_TARGET = 8, "dadfb28040931f447d4b22e2760a6e2f8e54aeab"   # F-M3-37's reproduction: round 8's target
TAMPERED = 9                                                # the round B2 changes one record at a time
SUBSET_LAW = "L_par_rt_BatchHeaderV0_Bytes_BatchHeaderBytes_Version_v0"     # F-M3-42's reproduction
SUBSET_PAIR = (SUBSET_LAW, "L_par_rt_BatchHeaderV1_Bytes_BatchHeaderBytes_Version_v1")
KEPT = ("model", "core")                                    # gen/<M>/ directories a subset run must not empty
MERGED = ("summary.json", "deps.json")                      # results/<M>/ files a subset run must not cut down


def sha256(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def holon(args, cwd: Path = ROOT, timeout: int = 3600) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1"}
    return subprocess.run([sys.executable, "-m", "holon", *[str(a) for a in args]], cwd=str(cwd), env=env,
                          capture_output=True, text=True, timeout=timeout)


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def load(p: Path):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def write(p: Path, obj, indent: int = 1) -> None:
    Path(p).write_text(json.dumps(obj, indent=indent, sort_keys=True) + "\n", encoding="utf-8")


# ================================================================== scratch copies of the M3 audit tree
def copy_audit_tree(dst: Path, rule: bytes | None) -> Path:
    """The committed M3 audit tree (rounds, findings) and spec/M3/lib's policy and rulings, as
    tests_m3/test_audit_evidence.py builds it; rule: the bytes of the evidence rule to put beside them (None: no rule)."""
    shutil.copytree(ROOT / "audit" / "rounds" / M, dst / "audit" / "rounds" / M)
    shutil.copy(ROOT / "audit" / f"{M}_findings.jsonl", dst / "audit" / f"{M}_findings.jsonl")
    (dst / "spec" / M / "lib").mkdir(parents=True)
    for name in ("audit_loop.json", "audit_rulings.json"):
        shutil.copy(ROOT / "spec" / M / "lib" / name, dst / "spec" / M / "lib" / name)
    if rule is not None:
        (dst / RULE).write_bytes(rule)
    return dst


def base_rule() -> bytes:
    """The evidence rule at the base: F-M3-27's, which reads each record's header only."""
    return subprocess.run(["git", "-C", str(ROOT), "show", f"{BASE}:{RULE}"], check=True, capture_output=True).stdout


def verdicts(root: Path) -> tuple[list, dict]:
    """(holon audit round's problems, holon audit converge's status document) on the root."""
    p = holon(["audit", "round", "--milestone", M, "--root", root, "--json"])
    rep = json.loads(p.stdout)
    out = Path(root) / "status.json"
    q = holon(["audit", "converge", "--milestone", M, "--root", root, "--out", out])
    if q.returncode != 0:
        raise AssertionError(q.stdout[-1500:] + q.stderr[-1500:])
    return rep["problems"], load(out)


def row(st: dict, n: int) -> dict:
    return next(r for r in st["rounds"] if r["round"] == n)


# ================================================================== F-M3-37's hollow round
def probe_tree(dst: Path, target: str = PROBE_TARGET) -> Path:
    """F-M3-37's reproduction root: the target commit's audit/, spec/M3/lib and spec/schemas trees (git archive), as
    audit/rounds/M3/round8/a7_hollow_round.py builds it, before its hollow round is added."""
    data = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar", target, "audit", f"spec/{M}/lib",
                           "spec/schemas"], check=True, capture_output=True).stdout
    Path(dst).mkdir(parents=True, exist_ok=True)
    subprocess.run(["tar", "-xf", "-", "-C", str(dst)], input=data, check=True, capture_output=True)
    return dst


def hollow_round(root: Path, n: int, target: str) -> None:
    """Round n of M3 as F-M3-37's probe writes its round 8: it claims to count under HUMAN_ANSWERS Q9b, with a1.json
    holding one refused mutant, a2.json one unsupported case, and a4.json and packet.json only the four header fields
    the F-M3-27 rule reads; every attack A1-A7 marked run and citing them, no finding."""
    root = Path(root)
    rel = f"audit/rounds/{M}/round{n}"
    d = root / rel
    assert not (root / f"audit/rounds/{M}/round{n}.json").exists(), f"round {n} already exists"
    d.mkdir(parents=True)
    head = {"milestone": M, "round": n, "target_commit": target}
    a1 = {"a1_version": "holon-audit-a1/0.1", **head, "checkout": {"repo": "x", "commit": "0" * 40},
          "spec": {"path": f"{rel}/s.json", "sha256": "0" * 64, "body": {}},
          "budget": {"law_timeout_s": 1, "max_law_runs": 0}, "law_runs": 0,
          "scope": {"documents": [], "reachable": [], "out_of_reach": []}, "baseline": {"documents": {}, "runs": {}},
          "mutations": [{"id": "m1", "file": "x.sol", "spec_sha256": "0" * 64, "diff": None, "documents": {},
                         "derivation": None, "runs": {}, "not_run": {}, "verdict": "refused", "why": "nothing applied",
                         "obstructions": []}],
          "summary": {"detected": [], "missed": [], "incomplete": [], "refused": ["m1"]},
          "attack": {"id": "A1", "category": "mutation_adequacy", "auditor_type": "A1", "run": True, "tried": "-",
                     "result": "no_finding", "findings": [], "evidence": [f"{rel}/a1.json"]}}
    a2 = {"a2_version": "holon-audit-a2/0.1", **head, "spec": {"path": f"{rel}/s.json", "sha256": "0" * 64,
                                                                "body": {}},
          "cases": [{"id": "c1", "entry": {"kind": "go", "document": "none"}, "verdict": "unsupported",
                     "why": "nothing"}],
          "summary": {"agree": [], "disagree": [], "unsupported": ["c1"]},
          "attack": {"id": "A2", "category": "model_vs_code", "auditor_type": "A2", "run": True, "tried": "-",
                     "result": "no_finding", "findings": [], "evidence": [f"{rel}/a2.json"]}}
    a4 = {"a4_version": "holon-audit-a4/0.1", **head}
    pk = {"packet_version": "holon-audit-packet/0.1", **head}
    for name, obj in (("a1.json", a1), ("a2.json", a2), ("a4.json", a4), ("packet.json", pk)):
        write(d / name, obj)
    ev = {"A1": [f"{rel}/a1.json"], "A2": [f"{rel}/a2.json"], "A4": [f"{rel}/a4.json"]}
    cats = [("A1", "mutation_adequacy", "A1"), ("A2", "model_vs_code", "A2"), ("A3", "statement_fidelity", "A3"),
            ("A4", "vacuity", "A4"), ("A5", "bindings_ledger", "A4"), ("A6", "determinism", None),
            ("A7", "gate_evasion", None)]
    attacks = []
    for i, c, t in cats:
        a = {"id": i, "category": c, "run": True, "tried": "-", "result": "no_finding", "findings": [],
             "evidence": ev.get(i, [])}
        if t:
            a["auditor_type"] = t
        attacks.append(a)
    rnd = {"round": n, "milestone": M, "target_commit": target, "round_version": "holon-audit-round/0.2",
           "dry_run": False, "packet": {"path": f"{rel}/packet.json", "sha256": sha256(d / "packet.json")},
           "auditor": {"session": f"i101-hollow-probe/round{n}/never-a-real-session", "family": "same",
                       "ruling": "HUMAN_ANSWERS Q9b", "counts_toward_convergence": True},
           "attacks": attacks, "findings": [], "notes": "a fabricated round with hollow evidence (I101's B1, P1)"}
    (root / f"audit/rounds/{M}/round{n}.json").write_text(json.dumps(rnd, indent=1) + "\n", encoding="utf-8")


def last_round(root: Path) -> int:
    return max(int(p.stem[5:]) for p in (Path(root) / "audit" / "rounds" / M).glob("round*.json"))


# ================================================================== B2: one change at a time to round 9
def _rd(root: Path, name: str) -> Path:
    return Path(root) / "audit" / "rounds" / M / f"round{TAMPERED}" / name


def _change(p: Path, f) -> None:
    d = load(p)
    f(d)
    write(p, d)


def _all(items: str, verdict: str, verdicts: tuple):
    def f(d):
        for x in d[items]:
            x["verdict"] = verdict
        d["summary"] = {v: (sorted(x["id"] for x in d[items]) if v == verdict else []) for v in verdicts}
    return f


def _drop_one_law(d) -> None:
    lid = sorted(d["laws"])[0]
    cls = d["laws"].pop(lid)["class"]
    d["counts"][cls] -= 1


def _empty_laws(d) -> None:
    d["laws"] = {}
    d["counts"] = {k: 0 for k in d["counts"]}


def _off_by_one(d) -> None:
    k = sorted(d["counts"])[0]
    d["counts"][k] += 1


def _schema_break(d) -> None:
    lid = sorted(d["laws"])[0]
    d["laws"][lid]["why"] = 7


def _empty_packet(root: Path) -> None:
    _change(_rd(root, "packet.json"), lambda d: d.__setitem__("laws", {}))
    rp = Path(root) / "audit" / "rounds" / M / f"round{TAMPERED}.json"
    r = load(rp)
    r["packet"]["sha256"] = sha256(_rd(root, "packet.json"))
    rp.write_text(json.dumps(r, indent=1) + "\n", encoding="utf-8")


TAMPERS = {
    "every A1 mutant refused": lambda s: _change(_rd(s, "a1.json"), _all(
        "mutations", "refused", ("detected", "missed", "incomplete", "refused"))),
    "every A2 case unsupported": lambda s: _change(_rd(s, "a2.json"), _all(
        "cases", "unsupported", ("agree", "disagree", "unsupported"))),
    "a4.json's laws emptied": lambda s: _change(_rd(s, "a4.json"), _empty_laws),
    "a4.json without one of the packet's laws": lambda s: _change(_rd(s, "a4.json"), _drop_one_law),
    "a4.json's counts off by one": lambda s: _change(_rd(s, "a4.json"), _off_by_one),
    "a4.json failing its schema": lambda s: _change(_rd(s, "a4.json"), _schema_break),
    "packet.json's laws emptied": _empty_packet,
}


# ================================================================== F-M3-42: subset runs in a detached worktree
def subset_run(laws, work: Path, commit: str = "HEAD") -> dict:
    """`holon run --milestone M3 --laws <laws>` in a detached worktree of commit (under work, removed after): the exit
    code, each law's status, the files git status lists (deleted and changed), and whether results/M3/summary.json and
    deps.json are byte-identical to the commit's."""
    wt = Path(work) / "wt"
    git(ROOT, "worktree", "add", "--detach", str(wt), commit)
    try:
        p = holon(["run", "--milestone", M, "--laws", ",".join(laws)], cwd=wt, timeout=5400)
        st = {}
        for lid in laws:
            rp = wt / "results" / M / f"{lid}.json"
            st[lid] = load(rp).get("status") if rp.is_file() else None
        lines = [ln for ln in git(wt, "status", "--porcelain", "--untracked-files=all").splitlines() if ln.strip()]
        deleted = sorted(ln[3:] for ln in lines if "D" in ln[:2])
        changed = sorted(ln[3:] for ln in lines if "D" not in ln[:2])
        same = {f: git(wt, "status", "--porcelain", "--", f"results/{M}/{f}").strip() == "" for f in MERGED}
        return {"laws": list(laws), "exit": p.returncode, "status": st, "deleted": deleted, "changed": changed,
                "identical": same, "tail": (p.stdout + p.stderr)[-1200:]}
    finally:
        subprocess.run(["git", "-C", str(ROOT), "worktree", "remove", "--force", str(wt)], capture_output=True)
        subprocess.run(["git", "-C", str(ROOT), "worktree", "prune"], capture_output=True)


# ================================================================== B7: the lines I101 adds under holon/
def added_lines(root: Path, base: str, head: str) -> list[tuple[str, str]]:
    out, cur = [], None
    for ln in git(root, "diff", "-U0", f"{base}..{head}", "--", "holon/").splitlines():
        if ln.startswith("+++ "):
            cur = ln[6:] if ln.startswith("+++ b/") else None
        elif ln.startswith("+") and cur:
            out.append((cur, ln[1:]))
    return out
