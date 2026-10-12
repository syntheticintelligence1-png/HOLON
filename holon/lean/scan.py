"""Emitted-Lean scanner: rejects escape hatches and unbounded `decide`.

The kernel already checks the proofs; the scanner exists so the *files* carry
no construct that would let a proof pretend to be checked: no `sorry`, `admit`,
`axiom`, `native_decide`, `implemented_by`, `unsafe`, `partial`, `opaque`,
`extern`, `noncomputable` and no `decide` except on the instantiated witness
goals of a counter/existential proof (`exact ⟨w, by decide⟩` — a closed,
fully concrete goal). `#eval` lines are allowed only in test-generated files
(never in `gen/lean/`).
"""

import re
from pathlib import Path

FORBIDDEN = [
    r"\bsorry\b",
    r"\badmit\b",
    r"\baxiom\b",
    r"\bnative_decide\b",
    r"\bimplemented_by\b",
    r"\bunsafe\b",
    r"\bpartial\b",
    r"\bopaque\b",
    r"\bextern\b",
    r"\bnoncomputable\b",
    r"\bset_option\s+debug\b",
    r"decl_name%",
    r"@\[implemented_by\]",
]

# `decide` is allowed only inside an instantiated witness term: `by decide⟩`
# on a line that closes an `exact ⟨..⟩` proof. Any other use is unbounded.
DECIDE_OK = re.compile(r"by\s+decide\s*⟩")
DECIDE = re.compile(r"\bdecide\b")

RE_EVAL = re.compile(r"^\s*#eval\b", re.M)


def scan_text(text: str, *, allow_eval: bool = False) -> list[str]:
    """Return the list of violations (empty when the file is clean)."""
    out = []
    for pat in FORBIDDEN:
        for mt in re.finditer(pat, text):
            out.append(f"forbidden {pat!r} at offset {mt.start()}: "
                       f"{text[max(0, mt.start() - 40):mt.end() + 40]!r}")
    for mt in DECIDE.finditer(text):
        line = text[text.rfind("\n", 0, mt.start()) + 1:text.find("\n", mt.start())
                    if text.find("\n", mt.start()) != -1 else len(text)]
        if not (DECIDE_OK.search(line) and "exact ⟨" in line):
            out.append(f"`decide` outside an instantiated witness goal: {line.strip()!r}")
    if not allow_eval and RE_EVAL.search(text):
        out.append("`#eval` in an emitted proof file (test files only)")
    return out


def scan_file(path: Path, *, allow_eval: bool = False) -> list[str]:
    return scan_text(path.read_text(), allow_eval=allow_eval)


def scan_dir(path: Path) -> list[str]:
    out = []
    for f in sorted(path.rglob("*.lean")):
        for v in scan_file(f):
            out.append(f"{f}: {v}")
    return out
