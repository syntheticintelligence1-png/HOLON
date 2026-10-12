"""A3, the cross-commit regression audit (whitepaper §9.5 A3; BUILD_PLAN I10; debt D-a).

    python -m holon audit regress --from A --to B [--json] [--root DIR]

It reads git history and nothing else (rev-parse, rev-list, log, ls-tree, cat-file, merge-base
--is-ancestor): no checkout, no write to the repository, its index or its config. It is an audit tool,
not a gate check: what it reports is for a human to judge, and it exits 0 whenever it could read the
history.

Reported:
  hash_changes  every statement-hash change of a law file laws/<M>/L*.json between A and B: for each commit
                in A..B that changes the file, the hash before and after it. Hashes are holon.ir.statement_hash
                of each version (0.3 laws with their refs into the facts file at that commit). A law added in
                A..B is not a change; a law deleted in A..B is reported with new = null; a version that does
                not parse hashes as "invalid:<sha256 of its bytes>".
  laws          for every law file at B, keyed "<M>/<law_id>":
                  law_commit         the first commit adding laws/<M>/<law_id>.json
                  result_commit      the first commit adding results/<M>/<law_id>.json (null if none)
                  prediction_commit  the first commit whose predictions file for <M> names the law as an entry
                                     (a `laws[]` item with that `law_id`), in spec/<M>/predictions.json (M1 on)
                                     or in the frozen predictions/<M>.json (M0, the same format); null if none
                  flag               one of
                    no_prediction                                   no prediction entry names the law
                    no_result                                       a prediction, but no result record
                    prediction_first                                the prediction commit is a proper ancestor
                                                                    of the result commit
                    result_same_commit_prediction_later_or_together the result came in the law's own commit and
                                                                    the prediction in that commit or later
                    result_later_prediction_later_or_together       the result came after the law's commit and
                                                                    the prediction not before the result
"First" means earliest in B's history in topological order (git rev-list --topo-order --reverse B), over
the whole history of B, not only A..B: a law added before A still has a first commit. Commits are given
as 7-character prefixes.

Residual risk, stated plainly: a prediction committed together with its result looks the same whether it
was written before the run or after it. A3 sees commits, not experiments, so it flags every such law alike
and cannot single out the ones labelled post hoc.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .prereg import Fatal, Git, parse_json, preflight

DEFAULT_ROOT = Path(__file__).resolve().parents[2]
SHORT = 7
_LAW_FILE = re.compile(r"^laws/(M[0-9]+)/(L[^/]*)\.json$")
FLAGS = ("no_prediction", "no_result", "prediction_first", "result_same_commit_prediction_later_or_together",
         "result_later_prediction_later_or_together")


def prediction_files(m: str) -> list[str]:
    return [f"spec/{m}/predictions.json", f"predictions/{m}.json"]


class History:
    def __init__(self, git: Git, to: str):
        self.git, self.to = git, to
        self.order = {c: i for i, c in enumerate(git.commits("--topo-order", "--reverse", to))}

    def log(self, *args: str) -> list[str]:
        """Commits (oldest first, topological) of `git log <args>`."""
        return self.git.out("log", "--topo-order", "--reverse", "--no-renames", "--format=%H", *args).split()

    def first_adds(self, *prefixes: str) -> dict[str, str]:
        """path -> the first commit in B's history that adds it."""
        out: dict[str, str] = {}
        text = self.git.out("log", "--topo-order", "--reverse", "--no-renames", "--diff-filter=A", "--format=C %H",
                            "--name-only", self.to, "--", *prefixes)
        commit = None
        for line in text.splitlines():
            if line.startswith("C "):
                commit = line[2:].strip()
            elif line.strip() and commit:
                out.setdefault(line.strip(), commit)
        return out

    def blob(self, commit: str, path: str) -> bytes | None:
        return self.git.blob(commit, path)

    def earliest(self, commits) -> str | None:
        cs = [c for c in commits if c]
        return min(cs, key=lambda c: self.order.get(c, len(self.order))) if cs else None

    def proper_ancestor(self, a: str, b: str) -> bool:
        return a != b and self.git.run("merge-base", "--is-ancestor", a, b).returncode == 0


def law_hash(hist: History, commit: str, path: str, data: bytes) -> str:
    import hashlib
    from ..gen.oracles import OracleError
    from ..gen.refs import law_hash as lh
    try:
        law = parse_json(data)
        facts = None
        orc = None
        if law.get("ir_version") == "holon-ir/0.3":
            fb = hist.blob(commit, law.get("facts", ""))
            facts = parse_json(fb) if fb is not None else {}
            if any("hyp" in p for p in law["statement"].get("assume", [])):   # I12: the hypotheses it names
                from pathlib import PurePosixPath
                sb = hist.blob(commit, (PurePosixPath(law["facts"]).parent.parent / "lib" / "oracles.json").as_posix())
                orc = parse_json(sb) if sb is not None else None
        return lh(law, facts, orc)
    except (ValueError, KeyError, TypeError, AttributeError, OracleError):
        return "invalid:sha256:" + hashlib.sha256(data).hexdigest()


def hash_changes(hist: History, frm: str) -> list[dict]:
    git, to = hist.git, hist.to

    def law_paths(rev: str) -> set[str]:
        return {p for p in git.out("ls-tree", "-r", "--name-only", rev, "--", "laws/").splitlines() if _LAW_FILE.match(p)}
    touched = {p for p in git.out("log", "--no-renames", "--format=", "--name-only", f"{frm}..{to}", "--", "laws/").splitlines()
               if _LAW_FILE.match(p)}
    out = []
    for path in sorted(law_paths(frm) | law_paths(to) | touched):
        m, lid = _LAW_FILE.match(path).groups()
        b = hist.blob(frm, path)
        prev = law_hash(hist, frm, path, b) if b is not None else None
        for c in hist.log(f"{frm}..{to}", "--", path):
            data = hist.blob(c, path)
            h = law_hash(hist, c, path, data) if data is not None else None
            if prev is not None and h != prev:
                out.append({"milestone": m, "law_id": lid, "old": prev, "new": h, "commit": c[:SHORT]})
            prev = h
    return out


def predictions_first(hist: History, m: str) -> dict[str, str]:
    """law_id -> the first commit whose predictions file for milestone m names it in laws[]."""
    found: dict[str, list[str]] = {}
    for pf in prediction_files(m):
        for c in hist.log(hist.to, "--", pf):
            data = hist.blob(c, pf)
            if data is None:
                continue
            try:
                doc = parse_json(data)
            except ValueError:
                continue
            items = doc.get("laws") if isinstance(doc, dict) else None
            for x in items if isinstance(items, list) else []:
                if isinstance(x, dict) and isinstance(x.get("law_id"), str):
                    found.setdefault(x["law_id"], []).append(c)
    return {lid: hist.earliest(cs) for lid, cs in found.items()}


def flag(hist: History, law_c: str | None, res_c: str | None, pred_c: str | None) -> str:
    if pred_c is None:
        return "no_prediction"
    if res_c is None:
        return "no_result"
    if hist.proper_ancestor(pred_c, res_c):
        return "prediction_first"
    if res_c == law_c:
        return "result_same_commit_prediction_later_or_together"
    return "result_later_prediction_later_or_together"


def audit(root: Path, frm: str, to: str) -> dict:
    git = Git(root)
    preflight(git, root)
    a = git.out("rev-parse", "--verify", f"{frm}^{{commit}}").strip()
    b = git.out("rev-parse", "--verify", f"{to}^{{commit}}").strip()
    hist = History(git, b)
    adds = hist.first_adds("laws/", "results/")
    laws: dict[str, dict] = {}
    preds: dict[str, dict] = {}
    for path in sorted(git.out("ls-tree", "-r", "--name-only", b, "--", "laws/").splitlines()):
        mt = _LAW_FILE.match(path)
        if not mt:
            continue
        m, lid = mt.groups()
        if m not in preds:
            preds[m] = predictions_first(hist, m)
        law_c, res_c, pred_c = adds.get(path), adds.get(f"results/{m}/{lid}.json"), preds[m].get(lid)
        laws[f"{m}/{lid}"] = {"law_commit": law_c and law_c[:SHORT], "result_commit": res_c and res_c[:SHORT],
                              "prediction_commit": pred_c and pred_c[:SHORT], "flag": flag(hist, law_c, res_c, pred_c)}
    return {"from": a[:SHORT], "to": b[:SHORT], "hash_changes": hash_changes(hist, a), "laws": laws}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="holon audit regress", description=__doc__.splitlines()[0])
    ap.add_argument("--from", dest="frm", required=True)
    ap.add_argument("--to", default="HEAD")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    a = ap.parse_args(argv)
    try:
        rep = audit(Path(a.root).resolve(), a.frm, a.to)
    except Fatal as e:
        print(f"holon audit regress: {e}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(rep, indent=2, sort_keys=True))
        return 0
    print(f"A3 {rep['from']}..{rep['to']}: {len(rep['hash_changes'])} statement-hash changes")
    for h in rep["hash_changes"]:
        print(f"  {h['milestone']}/{h['law_id']} at {h['commit']}: {h['old']} -> {h['new']}")
    counts = {f: sum(1 for r in rep["laws"].values() if r["flag"] == f) for f in FLAGS}
    print(f"{len(rep['laws'])} laws: " + ", ".join(f"{f} {n}" for f, n in counts.items() if n))
    for k, r in rep["laws"].items():
        print(f"  {k:28s} law {r['law_commit']}  result {r['result_commit']}  prediction {r['prediction_commit']}  {r['flag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
