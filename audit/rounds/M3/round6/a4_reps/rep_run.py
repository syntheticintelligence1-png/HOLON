"""Round 6 A4: run one law in a scratch tree with its own inhabitant search made to skip the empty prefix, so the
law's own generator writes (and both kernels check) an inhabitant whose state is not the initial state. The patch
wraps the search's per-prefix callback only; nothing else of holon changes. Usage: rep_run.py <tree> <law id>"""
import sys
tree, lid = sys.argv[1], sys.argv[2]
sys.path.insert(0, tree)
import holon.undo.search as US
_orig = US.UndoSearch.over_prefixes
def over_prefixes(self, entry, at):
    return _orig(self, entry, lambda trace, g: None if not trace else at(trace, g))
US.UndoSearch.over_prefixes = over_prefixes
from holon.__main__ import main
sys.exit(main(["run", "--milestone", "M3", "--laws", lid]))
