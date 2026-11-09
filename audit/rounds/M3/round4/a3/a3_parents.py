"""A3 cross-check: for each hash change the topological walk of `holon audit regress` reports as uncovered,
recompute the law's statement hash at each git parent of that commit and ask whether the parent->commit pair is
covered by a laws/STATEMENT_DIFF.jsonl line at B (holon.statement_diff.covers). Reads git history only."""
import json, sys
from pathlib import Path
root = Path(sys.argv[1]); report = json.load(open(sys.argv[2])); to = sys.argv[3]
sys.path.insert(0, str(root))
from holon.audit.prereg import Git
from holon.audit.regress import History, law_hash, statement_entries, _ir
from holon.statement_diff import covers
git = Git(root); hist = History(git, to); entries = statement_entries(hist)
cache = {}
def H(c, path):
    k = (c, path)
    if k not in cache:
        data = hist.blob(c, path)
        cache[k] = (law_hash(hist, c, path, data) if data is not None else None, _ir(data))
    return cache[k]
rows = []
for ch in report["hash_changes"]:
    if ch["covered_by"]:
        continue
    path = f"laws/{ch['milestone']}/{ch['law_id']}.json"
    full = git.out("rev-parse", ch["commit"]).strip()
    parents = git.out("log", "-1", "--format=%P", full).split()
    hc, irc = H(full, path)
    per = []
    for p in parents:
        hp, irp = H(p, path)
        cov = []
        if hp is not None and hp != hc:
            cand = {"law_id": ch["law_id"], "old": irp, "new": irc, "old_hash": hp, "new_hash": hc}
            cov = [n for n, e in entries if irp is not None and covers(e, cand)]
        per.append({"parent": p[:7], "hash": hp, "same": hp == hc, "covered_by": cov})
    ok = any(x["same"] for x in per) or any(x["covered_by"] for x in per)
    rows.append({"law_id": ch["law_id"], "commit": ch["commit"], "walk_old": ch["old"], "new": ch["new"],
                 "parents": per, "explained_by_parents": ok})
json.dump(rows, sys.stdout, indent=1, sort_keys=True)
