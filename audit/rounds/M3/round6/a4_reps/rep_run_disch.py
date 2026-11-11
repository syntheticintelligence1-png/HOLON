"""Round 6 A4: run one DISCH law in a scratch tree with its own inhabitant search (holon.disch.search.LawSearch)
restricted to candidate states reached by a non-empty prefix, so the law's own generator writes (and both kernels
check) an inhabitant whose state is not the initial state. Usage: rep_run_disch.py <tree> <law id>"""
import sys
tree, lid = sys.argv[1], sys.argv[2]
sys.path.insert(0, tree)
import holon.disch.search as DS
_cands = DS.LawSearch.candidates
def candidates(self, *a, **k):
    for trace, g, t in _cands(self, *a, **k):
        if trace:
            yield trace, g, t
DS.LawSearch.candidates = candidates
from holon.__main__ import main
sys.exit(main(["run", "--milestone", "M3", "--laws", lid]))
