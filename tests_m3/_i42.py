"""Readers for I42's frozen preregistration and future generated artifacts."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

from holon import lean
from tests_m3._m3 import ROOT, load_json

INSTRUMENT = ROOT / "spec/M3/lib/I42/basis.json"
CORE = ROOT / "gen/core/I42"
RESULTS = ROOT / "results/M3/I42"
THEOREMS = (
    "lemma_6_2_congruence",
    "thm_6_3_domain_coherence",
    "thm_6_4_fundamental_cycle_basis",
    "cor_6_5_global_frame",
)
PREREQUISITES = (
    "prereq_domain_encode_v1",
    "prereq_domain_validate_v1",
    "prereq_right_inv_codec_v1",
    "prereq_right_inv_load_v1",
    "prereq_tree_gauge_rooted_at_header_v1",
    "prereq_fund_cycle_flat_sol_go_v1",
)
BASELINE = {"holon/sorts/model3.py", "holon/sorts/termsize.py"}


def instrument() -> dict:
    return load_json(INSTRUMENT)


def tree_hashes(path: Path) -> dict[str, str]:
    return {p.relative_to(path).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file()}


def historical_status(law: str) -> str:
    return load_json(ROOT / "results/M3" / (law + ".json"))["status"]


def git_changed(*paths: str) -> list[str]:
    proc = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *paths],
                          cwd=ROOT, check=True, text=True, capture_output=True)
    return proc.stdout.splitlines()


def strip_comments(text: str) -> str:
    """Remove Bend/Lean comments, including nested /- -/ blocks."""
    out = []
    i = depth = 0
    while i < len(text):
        if text.startswith("/-", i):
            depth += 1
            i += 2
        elif depth and text.startswith("-/", i):
            depth -= 1
            i += 2
        elif depth:
            if text[i] == "\n":
                out.append("\n")
            i += 1
        elif text.startswith("--", i) or text[i] == "#":
            i = text.find("\n", i)
            if i < 0:
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def require_expected_law(laws: str, proof: str, name: str) -> None:
    """Refuse commented-out, absent and vacuous claims even if Bend exits 0."""
    laws, proof = strip_comments(laws), strip_comments(proof)
    pattern = rf"(?m)^\s*law\s+{re.escape(name)}\s*:"
    match = re.search(pattern, laws)
    if not match:
        raise AssertionError(f"missing law {name}")
    if not re.search(rf"\bdef\s+Laws\.{re.escape(name)}\s*\(", proof):
        raise AssertionError(f"missing proof {name}")
    statement = laws[match.end():]
    statement = re.split(r"(?m)^\s*(?:law|def|data|type|from|import)\s+", statement, maxsplit=1)[0]
    if not statement.strip() or trivial_statement(statement):
        raise AssertionError(f"vacuous law {name}")


def trivial_statement(text: str) -> bool:
    trivial = r"(?:True|true|Bool\.true\s*==\s*Bool\.true|0\s*==\s*0|Unit\.new\s*==\s*Unit\.new)"
    return bool(re.search(rf"(?m)^\s*(?:{trivial})\s*$", text) or
                re.search(rf":\s*{trivial}\s*(?:\Z|(?=\n\s*(?:law|def)))", text))


def statement_hash(laws: str) -> str:
    """SHA256 of ordered, whitespace-normalized non-comment law declarations."""
    code = strip_comments(laws)
    declarations = re.findall(
        r"(?ms)^\s*law\s+\w+\s*:.*?(?=^\s*(?:law|def|data|type|from|import)\s+|\Z)",
        code)
    if not declarations:
        raise AssertionError("no law declarations")
    canonical = "\n".join(" ".join(decl.split()) for decl in declarations)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def check_lean_file(path: Path, expect: list[str]) -> dict:
    src = path.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as tmpdir:
        res = lean.check_text(src, tmpdir, expect=expect, timeout=120)
    return res


def morph_identifiers(path: Path) -> set[str]:
    from tests_m2.test_target_agnostic_exhaustive import code_py, identifiers

    source = path.read_text(encoding="utf-8")
    if path.suffix == ".py":
        pattern = re.compile(r"(?<![\w$])(" +
                             "|".join(sorted(map(re.escape, identifiers()), key=len, reverse=True)) +
                             r")(?![\w$])")
        return set(pattern.findall(code_py(source)))
    code = strip_comments(source)
    pattern = re.compile(
        r"(batchheader|morph|sequencerset|l1messagepopped|"
        r"withdrawalroot|blobversionedhash|batchindex|batchcache|enc_sol)",
        re.IGNORECASE)
    return set(pattern.findall(code))
