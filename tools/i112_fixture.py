"""I112: plant a refusal into a compiled, well-formed Solidity transitions document (tests_m6/test_i112_run_wall.py).

    python tools/i112_fixture.py layout IN OUT   one struct field's offset moved off the compiler's member layout
    python tools/i112_fixture.py slot IN OUT     one family's slot moved off the compiler's layout (no entry at all)

Each edit is stated and deterministic: the first storage family (in document order) with a field of nonzero width
whose type is narrower than a word gets that field's offset plus one (layout); the first family gets its slot plus
1000 (slot). The compiler's layout (inside the document's extraction info) is left as compiled, so holon.machine's
check of the document against it refuses: MemberLayoutError for layout (the per-document refusal class
member_layout), a plain ModelError for slot (a refusal of the milestone, I112-P6). The contract name is suffixed so
that the planted document is a model of its own.
"""
from __future__ import annotations

import json
import sys


def main(argv: list[str]) -> int:
    kind, src, dst = argv
    d = json.loads(open(src, encoding="utf-8").read())
    fam = d["storage"]
    if kind == "layout":
        hit = next(((s, f) for s in fam for f in s.get("fields") or [] if 0 < int(f.get("width") or 0) < 256), None)
        if hit is None:
            print("i112_fixture: no struct field narrower than a word", file=sys.stderr)
            return 1
        hit[1]["offset"] = int(hit[1].get("offset", 0)) + 1
    elif kind == "slot":
        fam[0]["slot"] = int(fam[0]["slot"]) + 1000
    else:
        print(f"i112_fixture: unknown edit {kind!r}", file=sys.stderr)
        return 2
    open(dst, "w", encoding="utf-8").write(json.dumps(d, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
