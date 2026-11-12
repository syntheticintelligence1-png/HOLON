"""I102's instrument (tests_m3/test_regress_parents_i102.py): a synthetic branchy law history that holds both of the
findings' failures (a phantom change and a hidden one), the base's `holon audit regress` run on it from a detached
worktree of the base, round 7's own checkers (audit/rounds/M3/round7/a3/hidden_check.py and parent_check.py) on a
regress output, and the real-history ranges the findings name. It imports nothing from holon/ or tools/: it runs
`python -m holon` and git in subprocesses. Fixed at the prereg (C_K) and pinned by sha256 in the key's thresholds.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = "docs/iterations/I102"
BASE = "82134fffd850dad60321ce57242a1541a93a8a2c"            # the lead after #165 (I101)
SEED = "8a1dbe7f16eb79f283e7b7115bd9f427ebb116fe"            # I10's seed: the start of every regress range of I10
ROUND7 = ("fe1f88f2fac7e7654ed10e7ed36021ca261ce060",       # F-M3-30: the first commit touching laws/M3 ...
          "ef39bed5897aa7e8a0a147cb369f190a9e6e3fcc")       # ... to round 7's target
ROUND7_PHANTOM_SITES = ("8afa57b", "1214153", "41c7e34")    # where the base reports its 408 uncovered changes
ROUND2 = ("2b4578afc7bb71c19715c1df680c824b218bd4ec",       # F-M3-07: round 1's target ...
          "c3eda1976c6811ff181fd71ae6ad1166f7e86a49")       # ... to round 2's
ROUND2_EQUAL_MERGES = ("41c7e34", "ecbb695")                # merges whose every law equals the first parent's
CHECKERS = ROOT / "audit" / "rounds" / "M3" / "round7" / "a3"
SHORT = 7


def run(args, cwd: Path = ROOT, timeout: int = 7200, check: bool = False) -> subprocess.CompletedProcess:
    env = {**os.environ, "BEND_NO_TELEMETRY": "1", "GIT_OPTIONAL_LOCKS": "0"}
    p = subprocess.run([str(a) for a in args], cwd=str(cwd), env=env, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        raise AssertionError(f"{' '.join(map(str, args))}: exit {p.returncode}\n{p.stdout[-1500:]}\n{p.stderr[-1500:]}")
    return p


def git(root: Path, *args: str) -> str:
    return run(["git", "-C", root, *args], check=True).stdout


def regress(code: Path, repo: Path, frm: str, to: str) -> dict:
    """`holon audit regress --json` of the code at `code` over the history of `repo`."""
    p = run([sys.executable, "-m", "holon", "audit", "regress", "--from", frm, "--to", to, "--json", "--root", repo],
            cwd=code, check=True)
    return json.loads(p.stdout)


def base_tree(work: Path) -> Path:
    """A detached worktree of the base: its code is the base's regress."""
    wt = Path(work) / "base"
    git(ROOT, "worktree", "add", "--detach", str(wt), BASE)
    return wt


def drop_tree(wt: Path) -> None:
    run(["git", "-C", ROOT, "worktree", "remove", "--force", wt])
    run(["git", "-C", ROOT, "worktree", "prune"])


def checker(script: str, *args, cwd: Path = ROOT) -> str:
    """One of round 7's checkers, run as its auditor ran it: from the repository root, with that root's holon."""
    return run([sys.executable, CHECKERS / script, *args], cwd=cwd, check=True).stdout


# ================================================================== the synthetic history
def law(lid: str, field: str | None) -> dict:
    claim = {"var": "h"} if field is None else {"field": field, "of": {"var": "h"}}
    return {"ir_version": "holon-ir/0.1", "law_id": lid, "rule": "PAR", "facts_sha256": "", "milestone": "M9",
            "statement": {"forall": [{"name": "h", "type": "Hdr"}], "assume": [], "claim": {"eq": [claim, claim]}}}


def line(lid: str, old: str | None, new: str | None) -> dict:
    return {"kind": "strengthening", "law_id": lid, "old": law(lid, old), "new": law(lid, new), "reason": "synthetic"}


def _write(repo: Path, laws: dict, lines: list) -> None:
    d = repo / "laws" / "M9"
    d.mkdir(parents=True, exist_ok=True)
    for lid, field in laws.items():
        (d / f"{lid}.json").write_text(json.dumps(law(lid, field), indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (repo / "laws" / "STATEMENT_DIFF.jsonl").write_text("".join(json.dumps(x, sort_keys=True) + "\n" for x in lines),
                                                        encoding="utf-8")


def _commit(repo: Path, msg: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=i102", "-c", "user.email=i102@example.invalid", "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD").strip()


def synthetic(dst: Path) -> dict:
    """A seed A, two branches x and y from it, and their merge MX:
      A   L_x, L_h, L_j and L_k at v1 (claim h = h);
      X1  (on x) L_x to vX, L_h to vH and L_j to vJ, each with its STATEMENT_DIFF line;
      Y1  (on y) L_x to vY, L_h to vH (the same change as X1's) and L_k to vK, each with its line;
      MX  (x, merging y) L_x regenerated to vXY with its line against X1's vX; L_h, L_j and L_k as merged.
    Its real statement changes, each against its commit's own parent: X1's three and Y1's three (against A) and MX's
    one (against X1; MX's L_x differs from Y1's too). Every one is covered by a line. A per-path log in topological
    order compares X1's and Y1's L_x with each other (a phantom change no commit made), and drops Y1's L_h (the merge
    is TREESAME to its first parent for that file, so that log never visits Y1 for it: a hidden change)."""
    repo = Path(dst) / "repo"
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "x")
    base = {"L_x": None, "L_h": None, "L_j": None, "L_k": None}
    _write(repo, base, [])
    a = _commit(repo, "A: seed")
    xl = [line("L_x", None, "vX"), line("L_h", None, "vH"), line("L_j", None, "vJ")]
    _write(repo, {**base, "L_x": "vX", "L_h": "vH", "L_j": "vJ"}, xl)
    x1 = _commit(repo, "X1")
    git(repo, "checkout", "-q", "-b", "y", a)
    yl = [line("L_x", None, "vY"), line("L_h", None, "vH"), line("L_k", None, "vK")]
    _write(repo, {**base, "L_x": "vY", "L_h": "vH", "L_k": "vK"}, yl)
    y1 = _commit(repo, "Y1")
    git(repo, "checkout", "-q", "x")
    run(["git", "-C", repo, "-c", "user.name=i102", "-c", "user.email=i102@example.invalid", "merge", "--no-ff",
         "--no-commit", "y"])   # conflicts on L_x and STATEMENT_DIFF.jsonl, resolved below
    _write(repo, {"L_x": "vXY", "L_h": "vH", "L_j": "vJ", "L_k": "vK"},
           xl + [yl[0], yl[2], line("L_x", "vX", "vXY")])
    mx = _commit(repo, "MX: merge y")
    return {"repo": repo, "A": a, "X1": x1, "Y1": y1, "MX": mx}


def expected(s: dict) -> set:
    """(commit, law, parent) of each real statement change of the synthetic history (short shas)."""
    c = {k: v[:SHORT] for k, v in s.items() if k != "repo"}
    return {(c["X1"], "L_x", c["A"]), (c["X1"], "L_h", c["A"]), (c["X1"], "L_j", c["A"]),
            (c["Y1"], "L_x", c["A"]), (c["Y1"], "L_h", c["A"]), (c["Y1"], "L_k", c["A"]),
            (c["MX"], "L_x", c["X1"])}


def parents_of(repo: Path, commit: str) -> list[str]:
    return git(repo, "rev-parse", f"{commit}^@").split()


def hash_at(code: Path, repo: Path, commit: str, path: str) -> str | None:
    """The statement hash of a law file at a commit, as the code at `code` computes it (holon.audit.regress.law_hash),
    or None when the commit does not hold the file. Run in a child process: the instrument imports no holon code."""
    prog = ("import sys, json\nfrom pathlib import Path\nfrom holon.audit.regress import Git, History, law_hash\n"
            "repo, c, p = sys.argv[1:4]\nh = History(Git(Path(repo)), c)\nb = h.blob(c, p)\n"
            "print(json.dumps(None if b is None else law_hash(h, c, p, b)))\n")
    return json.loads(run([sys.executable, "-c", prog, repo, commit, path], cwd=code, check=True).stdout)
