"""I43 preregistration readers. No build module is imported at collection time."""
from __future__ import annotations

import json
import hashlib
import io
import re
import tokenize
from pathlib import Path

from tests_m3._m3 import ROOT, load_json, validate

CENSUS = Path("spec/M3/lib/I43/promotion_census.json")
MILESTONES = ("M0", "M1", "M2", "M3")
COUNTS = {"M0": 5, "M1": 8, "M2": 6, "M3": 73}
FORBIDDEN = re.compile(
    r"\b(sorry|admit|axiom|unsafe|partial|implemented_by|extern|native_decide|bv_decide|"
    r"run_tac|run_cmd|import)\b|(?<!\w)#(?:eval|exit|print|check|reduce)\b"
)
MORPH = re.compile(
    r"(?i)(win_at|batchdata|rollup|morph|sequencer|batchheader|blobversionedhash|"
    r"withdrawalroot|l1messagepopped|enc_sol)"
)


def census() -> dict:
    return load_json(ROOT / CENSUS)


def base_rows():
    """Re-join registry, individual IR and primary records, not summary verdicts."""
    selected, excluded, debt = [], [], []
    for m in MILESTONES:
        reg = load_json(ROOT / "laws" / m / "REGISTRY.json")["statements"]
        summary = load_json(ROOT / "results" / m / "summary.json")
        for law_id, statement_hash in sorted(reg.items()):
            generated = sorted((ROOT / "gen" / m).rglob(law_id + ".law.json"))
            ir_path = (generated[0] if generated else ROOT / "laws" / m / (law_id + ".json"))
            rec_path = ROOT / "results" / m / (law_id + ".json")
            if not generated and m != "M0":
                debt.append((m, law_id, "generated_ir_absent"))
            if not ir_path.is_file():
                debt.append((m, law_id, "missing_ir"))
            if not rec_path.is_file():
                excluded.append((m, law_id, "MISSING_RECORD"))
                debt.append((m, law_id, "missing_individual_record"))
                continue
            rec = load_json(rec_path)
            if summary.get(law_id) != rec["status"]:
                debt.append((m, law_id, "summary_disagreement"))
            if rec["status"] != "PROVED" or not ir_path.is_file():
                excluded.append((m, law_id, rec["status"]))
                continue
            ir = load_json(ir_path)
            assert ir["law_id"] == law_id and rec["statement_hash"] == statement_hash
            proof_class = next(
                (a["generator"] for a in rec["attempts"]
                 if a.get("kind") == "proof" and a.get("exit_code") == 0 and "generator" in a), None
            )
            selected.append({
                "milestone": m, "law_id": law_id, "sort": ir["rule"],
                "proof_class": proof_class, "ir_path": ir_path.relative_to(ROOT).as_posix(),
                "record_path": rec_path.relative_to(ROOT).as_posix(),
                "statement_hash": statement_hash,
            })
        debt.extend((m, law_id, "unregistered_summary_entry") for law_id in sorted(set(summary) - set(reg)))
    return selected, excluded, debt


def assert_lean_source(test, path: Path, theorem: str) -> None:
    from holon.lean import strip_comments, forbidden
    code = strip_comments(path.read_text(encoding="utf-8"))
    test.assertEqual(forbidden(code), [], str(path))
    test.assertIsNone(FORBIDDEN.search(code), str(path))
    test.assertRegex(code, r"\btheorem\s+" + re.escape(theorem) + r"\b")


def _normalize(src: str) -> str:
    return " ".join(src.split())


def canonical_lean_statement_hash(src: str, theorem_name: str) -> str:
    """Hash only the comment-free declaration through its proposition, never the proof."""
    from holon.lean import strip_comments
    code = strip_comments(src)
    matches = list(re.finditer(r"(?m)^\s*theorem\s+" + re.escape(theorem_name) + r"\b", code))
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one theorem {theorem_name}")
    header = code[matches[0].start():].split(":=", 1)[0]
    if ":" not in header:
        raise AssertionError(f"missing proposition: {theorem_name}")
    return "sha256:" + hashlib.sha256(_normalize(header).encode("utf-8")).hexdigest()


def canonical_bend_statement_hash(src: str, law_id: str) -> str:
    from holon.bend import strip_comments
    code = strip_comments(src)
    matches = list(re.finditer(r"(?m)^\s*law\s+" + re.escape(law_id) + r"\s*:", code))
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one law {law_id}")
    rest = code[matches[0].start():]
    next_decl = re.search(r"(?m)^\s*(?:law|def|import|from)\s+", rest[matches[0].end() - matches[0].start():])
    declaration = rest[:matches[0].end() - matches[0].start() + next_decl.start()] if next_decl else rest
    return "sha256:" + hashlib.sha256(_normalize(declaration).encode("utf-8")).hexdigest()


def assert_lean_matches_ir(lean_path: Path, law_id: str, milestone: str, row: dict) -> None:
    """Independently bind the emitted proposition to archival IR and the manifest."""
    from holon.lean import strip_comments, forbidden
    src = strip_comments(lean_path.read_text(encoding="utf-8"))
    assert forbidden(src) == [], (lean_path, forbidden(src))
    assert FORBIDDEN.search(src) is None, lean_path
    law = load_json(ROOT / "laws" / milestone / (law_id + ".json"))
    assert law["law_id"] == law_id and law["milestone"] == milestone
    name = row.get("theorem_name", law_id)
    match = re.search(r"(?m)^\s*theorem\s+" + re.escape(name) + r"\b", src)
    assert match is not None, (lean_path, name)
    header = src[match.start():].split(":=", 1)[0]
    assert ":" in header, (lean_path, "no proposition")
    prop = header.split(":", 1)[1]
    assert re.search(r"(?:=|≠)", prop), (lean_path, "no equality claim")
    conclusion = re.split(r"(?:→|->)", prop)[-1].strip()
    assert not re.fullmatch(r"(?:True|0\s*=\s*0|rfl)", conclusion), lean_path
    trivial = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*\1", conclusion)
    assert trivial is None, (lean_path, "identity in place of law")
    st = law["statement"]
    binders = st.get("binders", st.get("forall", []))
    for binder in binders:
        assert re.search(r"\b" + re.escape(binder["name"]) + r"\b", prop), (lean_path, binder)
        assert "∀" in prop or "∃" in prop or re.search(r"\bforall\b", prop), lean_path
    for key in ("fn", "call", "obsv"):
        def symbols(node):
            if isinstance(node, dict):
                if key in node and isinstance(node[key], str):
                    yield node[key]
                for value in node.values():
                    yield from symbols(value)
            elif isinstance(node, list):
                for value in node:
                    yield from symbols(value)
        for symbol in set(symbols(st)):
            assert re.search(r"\b" + re.escape(symbol) + r"\b", prop), (lean_path, symbol)
    assert prop.count("→") + prop.count("->") >= len(st.get("assume", [])), lean_path
    if law["ir_version"] == "holon-ir/0.1":
        from holon.gen.lean_laws import emit, law_prop
        facts = load_json(ROOT / law["facts"])
        expected = " ".join(line.strip() for line in law_prop(emit(law, facts, row["statement_hash"]), mark=False))
        assert _normalize(expected) in _normalize(prop), (lean_path, "M0 proposition differs from IR")
    computed = canonical_lean_statement_hash(src, name)
    assert row.get("lean_statement_hash") and row["lean_statement_hash"] == computed, (lean_path, computed)


def assert_target_agnostic(test) -> None:
    from holon.bend import strip_comments as strip_bend
    from holon.lean import strip_comments as strip_lean
    registered = set().union(*(load_json(ROOT / "laws" / m / "REGISTRY.json")["statements"] for m in MILESTONES))
    for rel in ("holon/lean_promoted.py", "holon/result_views.py", "holon/gen/equivariance.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        code = tokenize.untokenize(
            (tok.type, "" if tok.type == tokenize.COMMENT else tok.string)
            for tok in tokenize.generate_tokens(io.StringIO(text).readline))
        test.assertIsNone(MORPH.search(code), rel)
        if rel in ("holon/lean_promoted.py", "holon/result_views.py"):
            test.assertFalse(registered & set(re.findall(r"\bL_[A-Za-z0-9_]+\b", code)), rel)
    for path in sorted((ROOT / "gen/core/I43").rglob("*")):
        if path.is_file():
            code = strip_bend(path.read_text(encoding="utf-8")) if path.suffix == ".bend" else (
                strip_lean(path.read_text(encoding="utf-8"))
                if path.suffix == ".lean" else re.sub(r"(?m)^\s*#.*$", "", path.read_text(encoding="utf-8")))
            test.assertIsNone(MORPH.search(code), str(path))


def assert_effective_record(test, row: dict, record: dict) -> None:
    archive = load_json(ROOT / row["record_path"])
    test.assertEqual(record["law_id"], row["law_id"])
    test.assertEqual(record["statement_hash"], row["statement_hash"])
    test.assertEqual(record["status"], "PROVED")
    test.assertEqual(record["independence_class"], "I2")
    lean = [k for k in record["kernels"] if k["name"] == "lean4"]
    test.assertEqual(len(lean), 1)
    test.assertEqual(lean[0]["result"], "checked")
    test.assertEqual(lean[0]["role"], "second-independent")
    test.assertTrue((ROOT / lean[0]["source"]).is_file())
    test.assertEqual(archive["status"], "PROVED")
    test.assertEqual(validate(record, ROOT / "schemas/result_record.schema.json"), [])
    test.assertEqual(validate(record, ROOT / "spec/schemas/result_record_v2.schema.json"), [])
