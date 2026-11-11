"""For each commit the regress tool reports with an uncovered M3 hash change, recompute the change against each of
the commit's own parents (git rev-parse c^@), and check whether a STATEMENT_DIFF line at the target covers it."""
import json, subprocess, sys, collections
sys.path.insert(0, '.')
from holon.audit.regress import Git, History, law_hash, statement_entries, _ir
from holon.statement_diff import covers
to = sys.argv[1]
rep = json.load(open(sys.argv[2]))
git = Git(__import__('pathlib').Path('.'))
hist = History(git, to)
entries = statement_entries(hist)
unc = [h for h in rep['hash_changes'] if not h['covered_by']]
by_commit = collections.defaultdict(list)
for h in unc:
    by_commit[h['commit']].append(h)
summary = {}
for c, hs in sorted(by_commit.items()):
    full = subprocess.run(['git', 'rev-parse', c], capture_output=True, text=True).stdout.strip()
    parents = subprocess.run(['git', 'rev-parse', f'{full}^@'], capture_output=True, text=True).stdout.split()
    stats = collections.Counter()
    for h in hs:
        path = f"laws/{h['milestone']}/{h['law_id']}.json"
        data = hist.blob(full, path)
        hc = law_hash(hist, full, path, data)
        assert hc == h['new'], (c, h['law_id'], hc, h['new'])
        res = []
        for p in parents:
            pb = hist.blob(p, path)
            ph = law_hash(hist, p, path, pb) if pb is not None else None
            if ph is None:
                res.append('absent_in_parent')
            elif ph == hc:
                res.append('same_as_parent')
            else:
                ch = {"law_id": h['law_id'], "old": _ir(pb), "new": _ir(data), "old_hash": ph, "new_hash": hc}
                cov = [n for n, e in entries if covers(e, ch)]
                res.append('changed_covered' if cov else 'changed_UNCOVERED')
        stats[tuple(res)] += 1
        stats['reported_old_equals_some_parent' if any(
            law_hash(hist, p, path, hist.blob(p, path)) == h['old'] for p in parents if hist.blob(p, path) is not None)
            else 'reported_old_is_no_parent'] += 1
    summary[c] = {"parents": [p[:8] for p in parents], "n": len(hs), "per_parent": {"|".join(k) if isinstance(k, tuple) else k: v for k, v in stats.items()}}
print(json.dumps(summary, indent=1))
