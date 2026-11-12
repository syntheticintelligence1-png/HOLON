"""A3, the cross-commit regression audit (whitepaper §9.5 A3; BUILD_PLAN I10; debt D-a).

    python -m holon audit regress --from A --to B [--json] [--root DIR]

It reads git history and nothing else (rev-parse, rev-list, log, ls-tree, cat-file, merge-base
--is-ancestor): no checkout, no write to the repository, its index or its config. It is an audit tool,
not a gate check: what it reports is for a human to judge, and it exits 0 whenever it could read the
history.

Reported:
  hash_changes  every statement-hash change of a law file laws/<M>/L*.json, or of a law set's laws/<M>/<set>/L*.json
                (the derivation law set, the bounded games), between A and B, each against the commit's own
                parents (F-M3-07, F-M3-30; I102). The commits are those of A..B that touch laws/
                (`git rev-list A..B -- laws/`), with every merge of A..B. A law file changes at commit C when its
                version at C (its statement hash, or absent) is none of the versions its parents (`git rev-parse
                C^@`) hold. A file that no parent of C holds is an addition, not a change (see additions). A file
                deleted at C is reported with new = null. Each change names the parent it is measured against
                ("parent": the first parent of C that holds the file), with old the hash there. A merge whose other
                parents hold the file under other hashes also lists each such edge in other_parents ({"parent",
                "old", "covered_by"}). Hashes are holon.ir.statement_hash of each version (0.3 laws with their refs
                into the facts file, the target library and the oracle sidecar at that commit); a version that does
                not parse hashes as "invalid:<sha256 of its bytes>". covered_by: the laws/STATEMENT_DIFF.jsonl lines
                at B whose entry carries exactly the two statements of that edge (holon.statement_diff.covers; a
                catalog_rederivation line also carries the two hashes reported here, F30); [] when no entry covers
                the change (since the M2/1 audit, F-M2-34). Before I102 each version was compared with the previous
                commit of a path-limited log, which on branchy history is often another branch's commit: changes no
                commit made were reported, and changes commits made were left out.
  additions     every law file added in A..B: {"milestone", "law_id", "commit"} (the law set grows; no hash change)
  transitions   per law, what its result record says at A and at B, where it differs: status, the kernels and
                their results ("name:result"), independence_class and premises (whitepaper §9.5 A3: law sets,
                premises and proof strengths across commits)
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
# I102: hash_changes also reads a milestone's law sets in subdirectories (laws/M3/derivation, laws/M5/games), whose
# statements law_hash hashes the same way; additions, laws and transitions keep laws/<M>/L*.json
_ANY_LAW_FILE = re.compile(r"^laws/(M[0-9]+)/(?:[a-z][a-z0-9_]*/)?(L[^/]*)\.json$")
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


def anchor_at(hist: History, commit: str, facts_rel: str, blob: bytes | None = None) -> str:
    """The facts file whose libraries apply to facts_rel at a commit (holon.gen.targetlib.anchor): a window view's
    declaration's abstraction (the view's extraction block names a window declaration, holon-window/0.1, whose
    abstraction is a file at that commit; I65), else facts_rel itself. blob: facts_rel's bytes at the commit, when the
    caller has read them."""
    from pathlib import PurePosixPath
    from ..gen.targetlib import WINDOW_VERSION

    def rel_ok(x) -> bool:
        p = PurePosixPath(x) if isinstance(x, str) and x else None
        return p is not None and not p.is_absolute() and ".." not in p.parts
    try:
        b = blob if blob is not None else hist.blob(commit, facts_rel) if rel_ok(facts_rel) else None
        doc = parse_json(b) if b is not None and b'"declaration"' in b else None
        ex = doc.get("extraction") if isinstance(doc, dict) else None
        drel = ex.get("declaration") if isinstance(ex, dict) else None
        db = hist.blob(commit, drel) if rel_ok(drel) else None
        decl = parse_json(db) if db is not None else None
    except ValueError:
        return facts_rel
    ab = decl.get("abstraction") if isinstance(decl, dict) and decl.get("window_version") == WINDOW_VERSION else None
    return ab if rel_ok(ab) and hist.blob(commit, ab) is not None else facts_rel


def lib_docs_at(hist: History, commit: str, facts_rel: str, blob: bytes | None = None) -> list[dict]:
    """The target-library documents of a facts file as they were at a commit (holon.gen.targetlib.lib_files: the
    global spec/lib/*.lib.json, then those of the facts' milestone, each sorted; a window view: its abstraction's,
    anchor_at). blob: the facts file's bytes at the commit, when the caller has read them."""
    from pathlib import PurePosixPath
    mine = (PurePosixPath(anchor_at(hist, commit, facts_rel, blob)).parent.parent / "lib").as_posix()
    out = []
    for d in ["spec/lib"] + ([mine] if mine != "spec/lib" else []):
        names = sorted(p for p in hist.git.out("ls-tree", "--name-only", commit, "--", d + "/").splitlines()
                       if p.endswith(".lib.json"))
        for p in names:
            b = hist.blob(commit, p)
            if b is not None:
                out.append(parse_json(b))
    return out


def law_hash(hist: History, commit: str, path: str, data: bytes) -> str:
    import hashlib
    from ..gen.oracles import OracleError
    from ..gen.refs import law_hash as lh
    try:
        law = parse_json(data)
        facts = None
        orc = None
        lib = None
        if law.get("ir_version") == "holon-ir/0.3":
            fb = hist.blob(commit, law.get("facts", ""))
            facts = parse_json(fb) if fb is not None else {}
            lib = lib_docs_at(hist, commit, law.get("facts", ""), fb)
            if law.get("milestone") not in ("M0", "M1"):   # I12: the sidecar of an M2+ model (hyp refs, parameters)
                from pathlib import PurePosixPath
                sb = hist.blob(commit, (PurePosixPath(law["facts"]).parent.parent / "lib" / "oracles.json").as_posix())
                orc = parse_json(sb) if sb is not None else None
        return lh(law, facts, orc, lib=lib)
    except (ValueError, KeyError, TypeError, AttributeError, OracleError, Fatal):
        return "invalid:sha256:" + hashlib.sha256(data).hexdigest()


def statement_entries(hist: History) -> list[tuple[int, dict]]:
    """(line number, entry) of laws/STATEMENT_DIFF.jsonl at B."""
    b = hist.blob(hist.to, "laws/STATEMENT_DIFF.jsonl")
    out = []
    for n, line in enumerate((b or b"").decode("utf-8", errors="replace").splitlines(), start=1):
        try:
            e = json.loads(line) if line.strip() else None
        except ValueError:
            e = None
        if isinstance(e, dict):
            out.append((n, e))
    return out


def hash_changes(hist: History, frm: str) -> list[dict]:
    """Every statement-hash change of a law file in frm..to, each against its commit's own parents (F-M3-07,
    F-M3-30; I102; the module docstring's hash_changes). Blobs are compared first: only a file whose blob at C is
    none of its parents' blobs is hashed, at C and at each parent holding it."""
    from ..statement_diff import covers
    git, to = hist.git, hist.to
    entries = statement_entries(hist)
    trees: dict[str, dict[str, str]] = {}
    hashes: dict[tuple[str, str], str | None] = {}

    def tree(rev: str) -> dict[str, str]:
        """path -> blob id of every law file at rev."""
        if rev not in trees:
            d = {}
            for ln in git.out("ls-tree", "-r", rev, "--", "laws/").splitlines():
                meta, _tab, path = ln.partition("\t")
                if _ANY_LAW_FILE.match(path):
                    d[path] = meta.split()[2]
            trees[rev] = d
        return trees[rev]

    def hash_of(rev: str, path: str) -> str | None:
        if (rev, path) not in hashes:
            data = hist.blob(rev, path)
            hashes[(rev, path)] = law_hash(hist, rev, path, data) if data is not None else None
        return hashes[(rev, path)]

    def edge(lid: str, parent: str, c: str, path: str) -> tuple[str | None, list[int]]:
        old, new = hash_of(parent, path), hash_of(c, path)
        ch = {"law_id": lid, "old": _ir(hist.blob(parent, path)), "new": _ir(hist.blob(c, path)), "old_hash": old,
              "new_hash": new}
        return old, [n for n, e in entries if ch["old"] is not None and covers(e, ch)]

    commits = list(dict.fromkeys(hist.log(f"{frm}..{to}", "--", "laws/")
                                 + git.out("rev-list", "--topo-order", "--reverse", "--merges", f"{frm}..{to}").split()))
    commits.sort(key=lambda c: hist.order.get(c, len(hist.order)))
    found: list[tuple[str, int, dict]] = []
    for c in commits:
        parents = git.out("rev-parse", f"{c}^@").split()
        tc, tps = tree(c), [tree(p) for p in parents]
        for path in sorted(set(tc).union(*tps)):
            bc, bps = tc.get(path), [tp.get(path) for tp in tps]
            if bc in bps or all(b is None for b in bps):
                continue    # the version of some parent, or an addition (no parent holds the file)
            h = hash_of(c, path)
            holding = [p for p, b in zip(parents, bps) if b is not None]
            if any(hash_of(p, path) == h for p in holding):
                continue    # a new blob, the same statement as a parent's
            m, lid = _ANY_LAW_FILE.match(path).groups()
            first, rest = holding[0], holding[1:]
            old, cov = edge(lid, first, c, path)
            item = {"milestone": m, "law_id": lid, "old": old, "new": h, "commit": c[:SHORT], "parent": first[:SHORT],
                    "covered_by": cov}
            if rest:
                item["other_parents"] = [dict(zip(("parent", "old", "covered_by"), (p[:SHORT], *edge(lid, p, c, path))))
                                         for p in rest]
            found.append((path, hist.order.get(c, len(hist.order)), item))
    return [item for _path, _i, item in sorted(found, key=lambda x: (x[0], x[1]))]


def _ir(data: bytes | None):
    try:
        x = parse_json(data) if data is not None else None
    except ValueError:
        return None
    return x if isinstance(x, dict) else None


def additions(hist: History, frm: str) -> list[dict]:
    """Law files added in A..B (the law set grows)."""
    out = []
    text = hist.git.out("log", "--topo-order", "--reverse", "--no-renames", "--diff-filter=A", "--format=C %H",
                        "--name-only", f"{frm}..{hist.to}", "--", "laws/")
    commit = None
    for line in text.splitlines():
        if line.startswith("C "):
            commit = line[2:].strip()
        elif line.strip() and commit and _LAW_FILE.match(line.strip()):
            m, lid = _LAW_FILE.match(line.strip()).groups()
            out.append({"milestone": m, "law_id": lid, "commit": commit[:SHORT]})
    return out


def _strength(rec) -> dict | None:
    if not isinstance(rec, dict):
        return None
    ks = rec.get("kernels")
    kernels = sorted(f"{k.get('name')}:{k.get('result')}" for k in ks if isinstance(k, dict)) if isinstance(ks, list) \
        else [f"{(rec.get('kernel') or {}).get('name')}:{(rec.get('kernel') or {}).get('verdict')}"]
    return {"status": rec.get("status"), "kernels": kernels, "independence_class": rec.get("independence_class"),
            "premises": rec.get("premises")}


def transitions(hist: History, frm: str, law_keys: list[str]) -> list[dict]:
    """Per law at B: the fields of _strength that differ between its result record at A and at B."""
    out = []
    for key in law_keys:
        m, lid = key.split("/", 1)
        rel = f"results/{m}/{lid}.json"
        a, b = _strength(_ir(hist.blob(frm, rel))), _strength(_ir(hist.blob(hist.to, rel)))
        if a == b:
            continue
        row = {"law": key}
        for f in ("status", "kernels", "independence_class", "premises"):
            va, vb = (a or {}).get(f), (b or {}).get(f)
            if va != vb:
                row[f] = [va, vb]
        out.append(row)
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
    return {"from": a[:SHORT], "to": b[:SHORT], "hash_changes": hash_changes(hist, a), "laws": laws,
            "additions": additions(hist, a), "transitions": transitions(hist, a, sorted(laws))}


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
        cov = f"covered by STATEMENT_DIFF line(s) {h['covered_by']}" if h["covered_by"] else "NOT covered by any entry"
        print(f"  {h['milestone']}/{h['law_id']} at {h['commit']} (against parent {h['parent']}): {h['old']} -> "
              f"{h['new']} ({cov})")
    print(f"{len(rep['additions'])} law files added: "
          + ", ".join(f"{x['milestone']}/{x['law_id']}@{x['commit']}" for x in rep["additions"][:40])
          + (" ..." if len(rep["additions"]) > 40 else ""))
    print(f"{len(rep['transitions'])} laws whose status, kernels, independence class or premises changed")
    for t in rep["transitions"]:
        print(f"  {t['law']}: " + "; ".join(f"{k} {v[0]} -> {v[1]}" for k, v in t.items() if k != "law"))
    counts = {f: sum(1 for r in rep["laws"].values() if r["flag"] == f) for f in FLAGS}
    print(f"{len(rep['laws'])} laws: " + ", ".join(f"{f} {n}" for f, n in counts.items() if n))
    for k, r in rep["laws"].items():
        print(f"  {k:28s} law {r['law_commit']}  result {r['result_commit']}  prediction {r['prediction_commit']}  {r['flag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
