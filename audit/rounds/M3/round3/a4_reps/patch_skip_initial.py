"""A4 representative search (scratch tree only, never the repository): make the laws' own inhabitant generators skip
the initial state, so that the inhabitant they find, emit and check in both kernels has a non-empty prefix.
  holon/symd/search.py  SymSearch.inhabitant: its candidate function returns None on an empty trace
  holon/disch/search.py LawSearch.inhabit: a candidate with an empty trace is skipped
Prints the two replacements it made."""
import sys
from pathlib import Path
tree = Path(sys.argv[1])
p = tree / "holon/symd/search.py"
t = p.read_text()
old = "        def at(trace, g):\n            if sub == \"omega\":"
assert t.count(old) == 1, "symd anchor"
t = t.replace(old, "        def at(trace, g):\n            if not trace:   # A4 scratch patch: no initial-state inhabitant\n                return None\n            if sub == \"omega\":")
p.write_text(t)
print("patched", p.relative_to(tree))
p = tree / "holon/disch/search.py"
t = p.read_text()
old = "        for trace, g, t in self.candidates():\n            if max_states is not None and n >= max_states:\n                return None\n            n += 1\n"
assert t.count(old) == 1, "disch anchor"
t = t.replace(old, old + "            if not trace:   # A4 scratch patch: no initial-state inhabitant\n                continue\n")
p.write_text(t)
print("patched", p.relative_to(tree))
