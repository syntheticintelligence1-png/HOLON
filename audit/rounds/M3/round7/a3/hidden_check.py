"""Cheap first pass: for every commit C in frm..to and every laws/M3/L*.json path whose blob at C differs from its blob
at every parent of C (a change C itself introduces), list the pairs at which holon audit regress reports no
hash change; then compute the statement hash (holon.audit.regress.law_hash) at C and at each parent only for those,
and print the ones whose hash differs from every parent's (a real statement change the tool does not report)."""
import json, subprocess, sys, collections
from pathlib import Path
sys.path.insert(0, '.')
from holon.audit.regress import Git, History, law_hash, statement_entries, _ir
from holon.statement_diff import covers
frm, to, rep_path = sys.argv[1:4]
rep = json.load(open(rep_path))
reported = {(x['commit'], x['law_id']) for x in rep['hash_changes'] if x['milestone'] == 'M3'}
def run(*a):
    return subprocess.run(['git', *a], capture_output=True, text=True).stdout
commits = run('rev-list', f'{frm}..{to}', '--', 'laws/M3').split()
merges = set(run('rev-list', '--merges', f'{frm}..{to}').split())
commits = list(dict.fromkeys(commits + [m for m in merges]))
lt = {}
def tree(c):
    if c not in lt:
        d = {}
        for line in run('ls-tree', '-r', c, '--', 'laws/M3/').splitlines():
            meta, path = line.split('\t', 1)
            if path.endswith('.json') and '/L' in path:
                d[path] = meta.split()[2]
        lt[c] = d
    return lt[c]
cand = []
for c in commits:
    ps = run('rev-parse', f'{c}^@').split()
    tc = tree(c)
    tps = [tree(p) for p in ps]
    for path, b in tc.items():
        if any(tp.get(path) == b for tp in tps):
            continue
        if all(path not in tp for tp in tps):
            continue        # an addition
        lid = Path(path).stem
        if (c[:7], lid) in reported:
            continue
        cand.append((c, ps, path))
print('candidate pairs (blob changed vs every parent, no reported hash change):', len(cand))
git = Git(Path('.'))
hist = History(git, to)
entries = statement_entries(hist)
hidden = []
for c, ps, path in cand:
    bc = hist.blob(c, path)
    hc = law_hash(hist, c, path, bc)
    hps = []
    for p in ps:
        bp = hist.blob(p, path)
        if bp is not None:
            hps.append((p, law_hash(hist, p, path, bp), bp))
    if hps and all(hp != hc for _p, hp, _b in hps):
        lid = Path(path).stem
        covs = []
        for p, hp, bp in hps:
            ch = {"law_id": lid, "old": _ir(bp), "new": _ir(bc), "old_hash": hp, "new_hash": hc}
            covs.append([n for n, e in entries if covers(e, ch)])
        hidden.append({"commit": c[:8], "law": lid, "parents": [p[:8] for p, _h, _b in hps], "covered_by": covs})
print('real statement changes the tool does not report:', len(hidden))
print('of which uncovered against some parent:', sum(1 for h in hidden if any(not x for x in h['covered_by'])))
print(json.dumps(hidden[:40], indent=1))
